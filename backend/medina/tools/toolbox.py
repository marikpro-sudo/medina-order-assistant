"""Agent tools: pure functions over a DataSource, bound to the current customer session.

Every tool returns a JSON-serializable dict. The customer comes from the session (portal login),
never from model arguments, so the model cannot query another customer's data.
"""

import math
import re
import uuid
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import xlwt

from data.schema import PLANTS, Batch, Product
from data_access.base import DataSource
from data_access.search import CatalogSearch, product_form_family
from medina.parsers.order_table import parse_order_file, read_cells

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
        self.last_order: list[dict] | None = None  # set by present_order; read by the widget API and evals

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


    def present_order(self, lines: list[dict]) -> dict:
        """Record the final structured result of an order turn (one item per user line, in order)."""
        statuses = {"found", "analog", "rounded", "clarify", "unrecognized"}
        clean, problems = [], []
        for i, ln in enumerate(lines, start=1):
            mid = str(ln.get("material_id") or "")
            status = ln.get("status", "")
            p = self.ds.get_product(mid) if mid else None
            if status not in statuses:
                problems.append(f"line {i}: unknown status {status!r}")
            if mid and p is None:
                problems.append(f"line {i}: unknown material_id {mid}")
            try:
                qty = int(ln.get("qty") or 0)
            except (TypeError, ValueError):
                qty = 0
            if p and qty and qty % p.order_multiple:
                problems.append(f"line {i}: qty {qty} is not a multiple of {p.order_multiple}")
            clean.append({"source": str(ln.get("source", "")), "material_id": mid or None,
                          "qty": qty, "status": status, "replaces": ln.get("replaces")})
        self.last_order = clean
        return {"ok": not problems, "problems": problems, "lines": len(clean)}

    # --- attached files ---

    def _attachment(self, file_name: str) -> bytes | None:
        if file_name in self.attachments:
            return self.attachments[file_name]
        if len(self.attachments) == 1:  # the model may shorten or mistype the name
            return next(iter(self.attachments.values()))
        return None

    def read_order_file(self, file_name: str) -> dict:
        """Extract order lines from a spreadsheet in any layout; resolve codes deterministically."""
        data = self._attachment(file_name)
        if data is None:
            return {"error": f"file {file_name} not attached", "attached": list(self.attachments)}
        try:
            parsed = parse_order_file(data, file_name)
        except ValueError as e:
            return {"error": f"cannot read file: {e}"}
        lines = []
        for ln in parsed["lines"]:
            p = self.ds.get_product(ln["material_id"]) if ln["material_id"] else None
            if p is None and ln["ean"]:
                p = self.ds.get_by_ean(ln["ean"])
            item = {"row": ln["row"], "text": ln["name"], "qty": ln["qty"], "qty_raw": ln["qty_raw"]}
            if p is not None:
                item["resolved"] = {"material_id": p.material_id, "name": p.name_short,
                                    "order_multiple": p.order_multiple}
            else:
                item["search_query"] = ln["name"] or ln["ean"] or ln["material_id"]
            lines.append(item)
        return {"file": file_name, "header_row": parsed["header_row"], "columns": parsed["columns"],
                "warnings": parsed["warnings"], "lines": lines}

    def validate_upload_file(self, file_name: str) -> dict:
        """Row-by-row check of a file meant for the portal's strict order upload."""
        data = self._attachment(file_name)
        if data is None:
            return {"error": f"file {file_name} not attached", "attached": list(self.attachments)}
        try:
            rows = read_cells(data, file_name)
        except ValueError as e:
            return {"file": file_name, "would_fail": True,
                    "errors": [{"row": None, "code": "unreadable", "message": f"Файл не читается: {e}"}]}
        start = 1 if rows and rows[0] and not rows[0][0].value.strip().isdigit() else 0
        header_ok = start == 1 and [c.value.strip().lower() for c in rows[0][:3]] == \
            [h.lower() for h in UPLOAD_HEADERS]
        problems, fixed, seen = [], [], {}

        def err(row: int, code: str, message: str, fix: str | None = None) -> None:
            problems.append({"row": row, "code": code, "message": message, **({"fix": fix} if fix else {})})

        for i, r in enumerate(rows[start:], start=start + 1):
            if not any(c.value.strip() for c in r):
                continue
            if len(r) != 3:
                err(i, "column_count", f"Колонок: {len(r)}, нужно 3 (Штрихкод, Код товара, Количество)")
                continue
            ean, mid, qty = (c.value.strip() for c in r)
            if not all(c.is_text for c in r):
                err(i, "not_text", "Значения сохранены как числа, портал принимает только текст",
                    "сохранить ячейки в текстовом формате")
            p_by_id = self.ds.get_product(mid) if re.fullmatch(r"\d{18}", mid) else None
            p_by_ean = self.ds.get_by_ean(ean) if re.fullmatch(r"\d{13}", ean) else None
            if p_by_id is None:
                err(i, "bad_material_id", f"Код товара «{mid}» не найден",
                    f"по штрихкоду: {p_by_ean.material_id}" if p_by_ean else None)
            if re.fullmatch(r"\d{13}", ean) and not _ean_valid(ean):
                err(i, "bad_ean", f"Штрихкод «{ean}»: неверная контрольная цифра",
                    f"по коду товара: {p_by_id.ean13}" if p_by_id else None)
            elif p_by_ean is None:
                err(i, "bad_ean", f"Штрихкод «{ean}» не найден",
                    f"по коду товара: {p_by_id.ean13}" if p_by_id else None)
            if p_by_id and p_by_ean and p_by_id.material_id != p_by_ean.material_id:
                err(i, "ean_code_mismatch", f"Штрихкод относится к «{p_by_ean.name_short}», "
                    f"а код — к «{p_by_id.name_short}»")
            p = p_by_id or p_by_ean
            q = int(qty) if qty.isdigit() else 0
            if q <= 0:
                err(i, "bad_qty", f"Количество «{qty}» должно быть целым числом больше нуля")
            if p is None:
                continue
            if q > 0 and q % p.order_multiple:
                rounded = math.ceil(q / p.order_multiple) * p.order_multiple
                err(i, "not_multiple", f"Кратность {p.order_multiple}: {q} не кратно",
                    f"заменить на {rounded}")
                q = rounded
            if p.material_id in seen:
                err(i, "duplicate", f"Товар уже есть в строке {seen[p.material_id]}", "объединить строки")
            seen.setdefault(p.material_id, i)
            if q > 0:
                fixed.append({"material_id": p.material_id, "qty": q, "row": i, "name": p.name_short})
        blocking = {"column_count", "not_text", "bad_material_id", "bad_ean", "ean_code_mismatch", "bad_qty"}
        return {
            "file": file_name,
            "rows_total": len(rows) - start,
            "header_ok": header_ok,
            "would_fail": any(p["code"] in blocking for p in problems),
            "problems": problems,
            "fixable_lines": fixed,
            "note": "Then run check_lines on fixable_lines for stock, prescription and expiry.",
        }

    # --- reorder suggestions ---

    def suggest_reorder(self, limit: int = 12, seasonal_only: bool = False) -> dict:
        """Next-30-day needs from this customer's history: same period last year blended with recent demand.

        An item is seasonal when last year's same 30 days exceed 1.3x its 12-month monthly average.
        """
        today = self.ds.today()
        history = self.ds.history(self.customer.customer_id)
        if not history:
            return {"suggestions": [], "note": "no order history"}
        last_year_from = today - timedelta(days=365)
        last_year_to = last_year_from + timedelta(days=30)
        recent_from = today - timedelta(days=90)
        season, recent, total, last_order = defaultdict(int), defaultdict(int), defaultdict(int), {}
        for h in history:
            d = date.fromisoformat(h.date)
            total[h.material_id] += h.qty
            if last_year_from <= d < last_year_to:
                season[h.material_id] += h.qty
            if d >= recent_from:
                recent[h.material_id] += h.qty
            last_order[h.material_id] = max(last_order.get(h.material_id, ""), h.date)

        out = []
        for mid in set(season) | set(recent):
            p = self.ds.get_product(mid)
            if p is None:
                continue
            monthly_recent = recent[mid] / 3
            expected = 0.6 * season[mid] + 0.4 * monthly_recent
            seasonal = season[mid] > 1.3 * total[mid] / 12
            if expected <= 0 or (seasonal_only and not seasonal):
                continue
            qty = max(p.order_multiple, math.ceil(expected / p.order_multiple) * p.order_multiple)
            stock = self._stock(mid)
            reason = (f"Прошлый год, {last_year_from:%d.%m}–{last_year_to:%d.%m}: {season[mid]} уп.; "
                      f"последние 3 мес.: в среднем {monthly_recent:.0f} уп./мес.")
            if seasonal:
                reason += f"; сезонный рост: в этот период в {season[mid] / (total[mid] / 12):.1f} раза больше среднего"
            batches = self._batches_in_stock(mid)
            out.append({
                "material_id": mid, "name": p.name_short, "inn": p.inn, "qty": qty, "reason": reason,
                "last_ordered": last_order[mid], "stock_in_branch": stock,
                "available": stock >= qty,
                "nearest_expiry": batches[0].expiry_date if batches else None,
                "_score": expected,
            })
        out.sort(key=lambda x: -x["_score"])
        for x in out:
            del x["_score"]
        return {"period": f"{today:%d.%m.%Y} + 30 дней", "suggestions": out[:limit],
                "note": "Unavailable items: offer find_analogs. Suggestions are based on order history only."}


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


def _ean_valid(ean: str) -> bool:
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(ean[:12]))
    return (10 - total % 10) % 10 == int(ean[12])


def _neg_date(iso: str) -> int:
    return -date.fromisoformat(iso).toordinal() if iso else 0
