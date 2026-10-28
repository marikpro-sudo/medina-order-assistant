"""Agent tools: pure functions over a DataSource, bound to the current customer session.

Every tool returns a JSON-serializable dict. The customer comes from the session (portal login),
never from model arguments, so the model cannot query another customer's data.
"""

import math
import uuid
from datetime import date
from pathlib import Path

import xlwt

from data.schema import PLANTS, Batch, Product
from data_access.base import DataSource
from data_access.search import CatalogSearch, product_form_family

SHORT_EXPIRY_DAYS = 90
UPLOAD_HEADERS = ("Штрихкод", "Код товара", "Количество")


class Toolbox:
    def __init__(self, ds: DataSource, customer_id: str, files_dir: Path):
        self.ds = ds
        self.customer = ds.get_customer(customer_id)
        if self.customer is None:
            raise ValueError(f"unknown customer {customer_id}")
        self.plant = self.customer.branch_plant
        self.files_dir = files_dir
        self.search = CatalogSearch(ds.products())
        self.attachments: dict[str, bytes] = {}  # spreadsheets the user attached in this session

    # --- helpers ---

    def _stock(self, material_id: str, plant: str | None = None) -> int:
        return sum(b.qty_available for b in self.ds.batches(material_id, plant or self.plant))

    def _batches_in_stock(self, material_id: str, plant: str | None = None) -> list[Batch]:
        items = [b for b in self.ds.batches(material_id, plant or self.plant) if b.qty_available > 0]
        return sorted(items, key=lambda b: b.expiry_date)

    def _days_left(self, b: Batch) -> int:
        return (date.fromisoformat(b.expiry_date) - self.ds.today()).days

    def _product_brief(self, p: Product) -> dict:
        return {
            "material_id": p.material_id,
            "ean13": p.ean13,
            "name": p.name_short,
            "inn": p.inn,
            "dosage_form": p.dosage_form,
            "strength": p.strength,
            "manufacturer": p.manufacturer,
            "country": p.country,
            "is_original": p.is_original,
            "is_prescription": p.is_prescription,
            "order_multiple": p.order_multiple,
            "stock_in_branch": self._stock(p.material_id),
        }

    def _batch_brief(self, b: Batch) -> dict:
        days = self._days_left(b)
        return {
            "batch_id": b.batch_id,
            "expiry_date": b.expiry_date,
            "days_to_expiry": days,
            "short_expiry": days <= SHORT_EXPIRY_DAYS,
            "qty_available": b.qty_available,
            "price": b.price_customer,
        }

    # --- tools ---

    def search_products(self, query: str, limit: int = 5) -> dict:
        hits = self.search.search(query, limit=limit)
        return {
            "query": query,
            "results": [
                {**self._product_brief(h.product), "score": h.score, "matched_on": h.matched_on}
                for h in hits
            ],
        }

    def search_many(self, queries: list[str], limit: int = 3) -> dict:
        """Batch search: one tool round trip for a whole order."""
        return {"results": [self.search_products(q, limit) for q in queries]}

    def check_lines(self, lines: list[dict]) -> dict:
        return {"lines": [self.check_line(str(l.get("material_id", "")), l.get("qty", 0)) for l in lines]}

    def get_batches(self, material_id: str, plant: str | None = None) -> dict:
        p = self.ds.get_product(material_id)
        if p is None:
            return {"error": f"product {material_id} not found"}
        plant = plant or self.plant
        return {
            "material_id": material_id,
            "name": p.name_short,
            "plant": plant,
            "plant_name": PLANTS.get(plant, plant),
            "batches": [self._batch_brief(b) for b in self._batches_in_stock(material_id, plant)],
        }

    def find_analogs(self, material_id: str, limit: int = 5) -> dict:
        """In-stock analogs: same INN+form+strength, then same INN+form, then same ATC level 4."""
        src = self.ds.get_product(material_id)
        if src is None:
            return {"error": f"product {material_id} not found"}
        src_form = product_form_family(src.dosage_form)
        tiers: list[tuple[int, str, Product]] = []
        for p in self.ds.products():
            if p.material_id == src.material_id or self._stock(p.material_id) <= 0:
                continue
            same_form = product_form_family(p.dosage_form) == src_form
            if p.inn == src.inn and same_form and p.strength == src.strength:
                tiers.append((1, "same_inn_form_strength", p))
            elif p.inn == src.inn and same_form:
                tiers.append((2, "same_inn_form_other_strength", p))
            elif p.atc_code[:5] == src.atc_code[:5] and p.inn != src.inn and same_form:
                tiers.append((3, "same_atc_group", p))

        def best_expiry(p: Product) -> str:
            batches = self._batches_in_stock(p.material_id)
            return batches[-1].expiry_date if batches else ""

        def short_only(p: Product) -> bool:
            batches = self._batches_in_stock(p.material_id)
            return all(self._days_left(b) <= SHORT_EXPIRY_DAYS for b in batches)

        # Within a tier: analogs with only short-expiry stock go last, then longest shelf life first.
        tiers.sort(key=lambda t: (t[0], short_only(t[2]), _neg_date(best_expiry(t[2])), t[2].name_short))
        analogs = []
        for tier, kind, p in tiers[:limit]:
            batches = self._batches_in_stock(p.material_id)
            analogs.append({
                **self._product_brief(p),
                "match": kind,
                "tier": tier,
                "best_batch": self._batch_brief(batches[-1]),
            })
        return {
            "source": {**self._product_brief(src)},
            "analogs": analogs,
            "note": "Tier 2 changes strength and tier 3 changes the active ingredient: the customer must confirm.",
        }

    def check_line(self, material_id: str, qty: int) -> dict:
        p = self.ds.get_product(material_id)
        if p is None:
            return {"material_id": material_id, "status": "error", "issues": [
                {"code": "unknown_product", "message": "Код товара не найден в каталоге"}]}
        issues = []
        try:
            requested = int(qty)
        except (TypeError, ValueError):
            requested = 0
        if requested <= 0:
            return {"material_id": material_id, "status": "error", "issues": [
                {"code": "bad_qty", "message": "Количество должно быть больше нуля"}]}
        final_qty = math.ceil(requested / p.order_multiple) * p.order_multiple
        if final_qty != requested:
            issues.append({"code": "rounded_to_multiple",
                           "message": f"Кратность {p.order_multiple}: {requested} → {final_qty}"})
        if p.is_prescription:
            issues.append({"code": "prescription", "message": "Рецептурный препарат"})

        stock = self._stock(material_id)
        batches = self._batches_in_stock(material_id)
        other = {pl: self._stock(material_id, pl) for pl in PLANTS if pl != self.plant}
        other = {pl: q for pl, q in other.items() if q > 0}
        if stock <= 0:
            issues.append({"code": "out_of_stock_in_branch",
                           "message": "Нет в наличии в вашем филиале",
                           "other_branches": {PLANTS[pl]: q for pl, q in other.items()}})
        elif stock < final_qty:
            issues.append({"code": "insufficient_stock",
                           "message": f"В филиале доступно {stock}, запрошено {final_qty}",
                           "available": stock})
        if batches and all(self._days_left(b) <= SHORT_EXPIRY_DAYS for b in batches):
            issues.append({"code": "short_expiry",
                           "message": f"Доступна только партия с коротким сроком: до {batches[-1].expiry_date}"})

        codes = {i["code"] for i in issues}
        if "out_of_stock_in_branch" in codes:
            status = "unavailable"
        elif codes & {"insufficient_stock", "short_expiry", "prescription"}:
            status = "warning"
        elif "rounded_to_multiple" in codes:
            status = "adjusted"
        else:
            status = "ok"
        return {
            "material_id": material_id,
            "name": p.name_short,
            "requested_qty": requested,
            "qty": final_qty,
            "order_multiple": p.order_multiple,
            "stock_in_branch": stock,
            "nearest_expiry": batches[0].expiry_date if batches else None,
            "status": status,
            "issues": issues,
        }

    def get_customer_status(self) -> dict:
        c = self.customer
        warning = None
        if c.overdue_debt > 0:
            warning = (f"Просроченная задолженность {c.overdue_debt:,.0f} ₸. "
                       "Загрузка заказа может быть заблокирована до погашения.").replace(",", " ")
        return {
            "customer_id": c.customer_id,
            "name": c.name,
            "branch": PLANTS.get(c.branch_plant, c.branch_plant),
            "delivery_points": [{"point_id": d.point_id, "name": d.name, "address": d.address}
                                for d in c.delivery_points],
            "credit_limit": c.credit_limit,
            "overdue_debt": c.overdue_debt,
            "warning": warning,
        }

    def build_upload_file(self, lines: list[dict]) -> dict:
        """Write an .xls in the portal's order-upload format. Each line: {material_id, qty}."""
        rows, report = [], []
        for i, line in enumerate(lines, start=1):
            mid = str(line.get("material_id", "")).strip()
            p = self.ds.get_product(mid)
            try:
                qty = int(line.get("qty", 0))
            except (TypeError, ValueError):
                qty = 0
            if p is None:
                report.append({"line": i, "material_id": mid, "included": False, "reason": "unknown_product"})
                continue
            if qty <= 0:
                report.append({"line": i, "material_id": mid, "included": False, "reason": "bad_qty"})
                continue
            if qty % p.order_multiple:
                report.append({"line": i, "material_id": mid, "included": False,
                               "reason": f"qty_not_multiple_of_{p.order_multiple}"})
                continue
            rows.append((p.ean13, p.material_id, str(qty)))
            report.append({"line": i, "material_id": mid, "name": p.name_short, "qty": qty, "included": True})

        file_id = uuid.uuid4().hex[:12]
        self.files_dir.mkdir(parents=True, exist_ok=True)
        path = self.files_dir / f"order_{file_id}.xls"
        _write_xls(path, rows)
        return {"file_id": file_id, "filename": path.name, "rows": len(rows), "report": report}


def _write_xls(path: Path, rows: list[tuple[str, str, str]]) -> None:
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Order")
    text = xlwt.easyxf(num_format_str="@")  # all cells stored as text
    for col, h in enumerate(UPLOAD_HEADERS):
        ws.write(0, col, h, text)
    for r, row in enumerate(rows, start=1):
        for col, value in enumerate(row):
            ws.write(r, col, value, text)
    wb.save(str(path))


def _neg_date(iso: str) -> int:
    return -date.fromisoformat(iso).toordinal() if iso else 0
