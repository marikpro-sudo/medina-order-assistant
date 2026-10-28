"""Deterministic synthetic data generator for the pharma B2B portal.

Builds a reproducible catalog of products, batches, customers and order
history from ``data/inn_catalog.py``. All randomness comes from a single
``random.Random(seed)`` instance and no wall-clock input is used, so the
same seed always produces byte-identical output files.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import string
from calendar import monthrange
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from data.inn_catalog import INN_GROUPS
from data.schema import (
    PLANTS,
    Batch,
    Customer,
    DeliveryPoint,
    OrderHistoryLine,
    Product,
)

REF_DATE = date(2026, 10, 28)
HISTORY_START = date(2025, 10, 28)
HISTORY_END = date(2026, 10, 27)

TARGET_PRODUCTS = 400
N_OUT_OF_STOCK = 60
N_SHORT_EXPIRY = 40

_PLANTS = sorted(PLANTS.keys())
_PACK_RE = re.compile(r"№(\d+)")
_ORDER_MULTIPLES = (1, 5, 10, 20)
_ORDER_WEIGHTS = (0.55, 0.2, 0.15, 0.1)
_OTHER_PREFIXES = ("590", "800", "890")


def _ean_check_digit(first12: str) -> str:
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(first12))
    return str((10 - total % 10) % 10)


def _country_prefix(country: str) -> str:
    if country == "Казахстан":
        return "487"
    if country == "Россия":
        return "460"
    if country == "Германия":
        return "400"
    code = sum(ord(c) for c in country)
    return _OTHER_PREFIXES[code % len(_OTHER_PREFIXES)]


def _pick_order_multiple(rng: random.Random, infusion: bool) -> int:
    if infusion:
        return 10 if rng.random() < 0.6 else 20
    draw = rng.random()
    cumulative = 0.0
    for multiple, weight in zip(_ORDER_MULTIPLES, _ORDER_WEIGHTS):
        cumulative += weight
        if draw < cumulative:
            return multiple
    return _ORDER_MULTIPLES[-1]


def _make_ean13(rng: random.Random, country: str, used: set[str]) -> str:
    prefix = _country_prefix(country)
    while True:
        body = prefix + f"{rng.randint(0, 999_999_999):09d}"
        full = body + _ean_check_digit(body)
        if full not in used:
            used.add(full)
            return full


def _collect_base_specs() -> list[dict]:
    """One spec per (INN group, brand, form index), in catalog order."""
    specs = []
    for group in INN_GROUPS:
        for brand, manufacturer, country, is_original, form_indices in group["brands"]:
            for form_index in form_indices:
                dosage_form, form_abbr, strength, pack = group["forms"][form_index]
                specs.append(
                    {
                        "group": group,
                        "brand": brand,
                        "manufacturer": manufacturer,
                        "country": country,
                        "is_original": is_original,
                        "dosage_form": dosage_form,
                        "form_abbr": form_abbr,
                        "strength": strength,
                        "pack": pack,
                    }
                )
    return specs


def _short_name(spec: dict) -> str:
    return f"{spec['brand']} {spec['form_abbr']} {spec['strength']} {spec['pack']}"


def _full_name(spec: dict) -> str:
    group = spec["group"]
    return (
        f"{spec['brand']} ({group['inn']}), {spec['dosage_form']}, "
        f"{spec['strength']}, {spec['pack']}, "
        f"{spec['manufacturer']}, {spec['country']}"
    )


def _add_pack_variants(rng: random.Random, specs: list[dict]) -> None:
    """Grow the catalog to TARGET_PRODUCTS by doubling pack sizes."""
    names = {_short_name(s) for s in specs}
    attempts = 0
    while len(specs) < TARGET_PRODUCTS:
        attempts += 1
        if attempts > 100_000:  # pragma: no cover - safety net
            raise RuntimeError("Could not reach target product count")
        src = rng.choice(specs)
        match = _PACK_RE.fullmatch(src["pack"])
        if match is None:
            continue
        new_pack = f"№{int(match.group(1)) * 2}"
        copy = dict(src, pack=new_pack)
        if _short_name(copy) in names:
            continue
        names.add(_short_name(copy))
        specs.append(copy)


def _build_products(rng: random.Random) -> tuple[list[Product], list[float]]:
    specs = _collect_base_specs()
    _add_pack_variants(rng, specs)
    inn_base: dict[str, float] = {}
    for spec in specs:
        inn = spec["group"]["inn"]
        if inn not in inn_base:
            inn_base[inn] = rng.uniform(300.0, 5000.0)
    used_ean: set[str] = set()
    products: list[Product] = []
    base_prices: list[float] = []
    for seq, spec in enumerate(specs, start=10001):
        group = spec["group"]
        base = inn_base[group["inn"]]
        if spec["is_original"]:
            base_price = base * rng.uniform(1.5, 3.0)
        else:
            base_price = base * rng.uniform(0.8, 1.2)
        base_price = min(max(base_price, 300.0), 15000.0)
        infusion = "инфузий" in spec["dosage_form"]
        products.append(
            Product(
                material_id="1000000000000" + f"{seq:05d}",
                ean13=_make_ean13(rng, spec["country"], used_ean),
                name_short=_short_name(spec),
                name_full=_full_name(spec),
                inn=group["inn"],
                inn_lat=group["inn_lat"],
                dosage_form=spec["dosage_form"],
                strength=spec["strength"],
                atc_code=group["atc"],
                pharm_group=group["group"],
                brand=spec["brand"],
                manufacturer=spec["manufacturer"],
                country=spec["country"],
                is_original=spec["is_original"],
                is_prescription=group["rx"],
                is_marked=rng.random() < 0.3,
                order_multiple=_pick_order_multiple(rng, infusion),
                storage_temp=group["storage"],
                category_path=group["category"],
            )
        )
        base_prices.append(base_price)
    return products, base_prices


def _add_months(day: date, months: int) -> date:
    total = day.month - 1 + months
    year = day.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def _pick_expiry(rng: random.Random, short: bool) -> date:
    if short:
        return REF_DATE + timedelta(days=rng.randint(1, 90))
    return _add_months(REF_DATE, rng.randint(6, 36))


def _pick_manufacture(rng: random.Random, expiry: date) -> date:
    made = _add_months(expiry, -rng.randint(24, 36))
    if made >= REF_DATE:
        made = REF_DATE - timedelta(days=rng.randint(1, 300))
    return made


def _make_batch_id(rng: random.Random, made: date, used: set[str]) -> str:
    while True:
        batch_id = (
            f"{made.year % 100:02d}{made.month:02d}"
            f"{rng.choice(string.ascii_uppercase)}{rng.randint(0, 999):03d}"
        )
        if batch_id not in used:
            used.add(batch_id)
            return batch_id


def _build_batches(
    rng: random.Random, products: list[Product], base_prices: list[float]
) -> list[Batch]:
    base_price = {p.material_id: b for p, b in zip(products, base_prices)}
    out_of_stock = set(rng.sample(range(len(products)), N_OUT_OF_STOCK))
    candidates = [i for i in range(len(products)) if i not in out_of_stock]
    short_expiry = set(rng.sample(candidates, N_SHORT_EXPIRY))
    batches: list[Batch] = []
    used_ids: dict[str, set[str]] = {p.material_id: set() for p in products}
    for index, product in enumerate(products):
        material_id = product.material_id
        if index in out_of_stock:
            if rng.random() < 0.5:
                continue
            plants = rng.sample(_PLANTS, rng.randint(1, 2))
            for plant in plants:
                expiry = _pick_expiry(rng, short=False)
                made = _pick_manufacture(rng, expiry)
                batches.append(
                    Batch(
                        material_id=material_id,
                        plant=plant,
                        batch_id=_make_batch_id(rng, made, used_ids[material_id]),
                        expiry_date=expiry.isoformat(),
                        manufacture_date=made.isoformat(),
                        qty_available=0,
                        price_customer=round(
                            base_price[material_id] * rng.uniform(0.95, 1.05), 2
                        ),
                    )
                )
            continue
        short_left = index in short_expiry
        made_any = False
        for plant in _PLANTS:
            if rng.random() >= 0.8:
                continue
            for _ in range(rng.randint(1, 3)):
                short = short_left
                short_left = False
                expiry = _pick_expiry(rng, short)
                made = _pick_manufacture(rng, expiry)
                batches.append(
                    Batch(
                        material_id=material_id,
                        plant=plant,
                        batch_id=_make_batch_id(rng, made, used_ids[material_id]),
                        expiry_date=expiry.isoformat(),
                        manufacture_date=made.isoformat(),
                        qty_available=rng.randint(5, 2000),
                        price_customer=round(
                            base_price[material_id] * rng.uniform(0.95, 1.05), 2
                        ),
                    )
                )
                made_any = True
        if not made_any:
            plant = rng.choice(_PLANTS)
            expiry = _pick_expiry(rng, index in short_expiry)
            made = _pick_manufacture(rng, expiry)
            batches.append(
                Batch(
                    material_id=material_id,
                    plant=plant,
                    batch_id=_make_batch_id(rng, made, used_ids[material_id]),
                    expiry_date=expiry.isoformat(),
                    manufacture_date=made.isoformat(),
                    qty_available=rng.randint(5, 2000),
                    price_customer=round(
                        base_price[material_id] * rng.uniform(0.95, 1.05), 2
                    ),
                )
            )
    return batches


_CITIES = ("Алматы", "Астана", "Шымкент", "Караганда", "Актобе", "Павлодар", "Тараз")
_BRANCH_BY_CITY = {
    "Алматы": "P03",
    "Тараз": "P03",
    "Шымкент": "P03",
    "Астана": "P01",
    "Караганда": "P01",
    "Павлодар": "P01",
    "Актобе": "P02",
}
_PHARMACY_ROOTS = (
    "Береке", "Шипагер", "Дәрігер", "Жанұя", "Салауат", "Арай", "Нұр",
    "Дәру", "Мейірім", "Сенім", "Үміт", "Қамқор", "Саулық", "Шипа",
    "Өмір", "Денсаулық", "Ромашка", "Василёк", "Незабудка", "Календула",
    "Эвкалипт", "Шалфей", "Мелисса", "Душица", "Алтей", "Солодка",
    "Подорожник", "Зверобой",
)
_STREETS = (
    "Ромашковая", "Сиреневая", "Цветочная", "Яблоневая", "Степная",
    "Солнечная", "Зелёная", "Новая", "Садовая", "Полевая", "Луговая",
    "Весенняя", "Горная", "Дружбы", "Здоровья", "Школьная", "Вишнёвая",
    "Абрикосовая", "Тюльпановая", "Жасминовая",
)


def _build_customers(rng: random.Random) -> list[Customer]:
    pool = list(_PHARMACY_ROOTS) + [f"{root} Плюс" for root in _PHARMACY_ROOTS]
    rng.shuffle(pool)
    debtors = set(rng.sample(range(50), 5))
    customers = []
    for i in range(50):
        customer_id = f"C{100001 + i}"
        if i < 45:
            name = f"Аптека «{pool[i]}»"
        else:
            name = f"ТОО «Медцентр {pool[i]}»"
        city = rng.choice(_CITIES)
        points = []
        for k in range(1, rng.randint(1, 3) + 1):
            street = rng.choice(_STREETS)
            house = rng.randint(1, 150)
            points.append(
                DeliveryPoint(
                    point_id=f"{customer_id}-{k:02d}",
                    name=f"Точка {k}",
                    address=f"г. {city}, ул. {street}, д. {house}",
                )
            )
        customers.append(
            Customer(
                customer_id=customer_id,
                name=name,
                delivery_points=points,
                branch_plant=_BRANCH_BY_CITY[city],
                credit_limit=float(rng.randint(10, 100) * 100_000),
                overdue_debt=round(rng.uniform(50_000, 2_000_000), 2)
                if i in debtors
                else 0.0,
            )
        )
    return customers


def _history_months() -> list[tuple[int, int]]:
    months = []
    year, month = HISTORY_START.year, HISTORY_START.month
    for _ in range(12):
        months.append((year, month))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return months


def _season_weight(season: str | None, month: int) -> float:
    if season == "cold":
        return 3.0 if month in (10, 11, 12, 1, 2, 3) else 0.5
    if season == "allergy":
        return 3.0 if month in (4, 5, 6, 7, 8) else 0.5
    return 1.0


def _weighted_sample(
    rng: random.Random, items: list[str], weights: list[float], k: int
) -> list[str]:
    scored = [(rng.random() ** (1.0 / w), item) for item, w in zip(items, weights)]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:k]]


def _build_order_history(
    rng: random.Random, products: list[Product], customers: list[Customer]
) -> list[OrderHistoryLine]:
    season_by_inn = {group["inn"]: group["season"] for group in INN_GROUPS}
    season_by_material = {p.material_id: season_by_inn[p.inn] for p in products}
    multiple_by_material = {p.material_id: p.order_multiple for p in products}
    materials = [p.material_id for p in products]
    lines: list[OrderHistoryLine] = []
    for customer in customers:
        assortment = rng.sample(materials, rng.randint(30, 80))
        for point in customer.delivery_points:
            for year, month in _history_months():
                last_day = monthrange(year, month)[1]
                low = HISTORY_START.day if (year, month) == (2025, 10) else 1
                high = HISTORY_END.day if (year, month) == (2026, 10) else last_day
                weights = [
                    _season_weight(season_by_material[m], month) for m in assortment
                ]
                for _ in range(rng.randint(2, 4)):
                    day = date(year, month, rng.randint(low, high))
                    picked = _weighted_sample(
                        rng, assortment, weights, rng.randint(5, 20)
                    )
                    for material_id in picked:
                        multiple = multiple_by_material[material_id]
                        lines.append(
                            OrderHistoryLine(
                                customer_id=customer.customer_id,
                                delivery_point=point.point_id,
                                date=day.isoformat(),
                                material_id=material_id,
                                qty=multiple * rng.randint(1, 10),
                            )
                        )
    lines.sort(
        key=lambda line: (line.date, line.customer_id, line.delivery_point, line.material_id)
    )
    return lines


def generate(seed: int = 42) -> dict[str, list]:
    """Build all synthetic entities deterministically from ``seed``."""
    rng = random.Random(seed)
    products, base_prices = _build_products(rng)
    batches = _build_batches(rng, products, base_prices)
    customers = _build_customers(rng)
    order_history = _build_order_history(rng, products, customers)
    return {
        "products": products,
        "batches": batches,
        "customers": customers,
        "order_history": order_history,
    }


def write(out_dir: Path, seed: int = 42) -> None:
    """Generate data with ``seed`` and write the four output files."""
    data = generate(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name in ("products", "batches", "customers"):
        payload = json.dumps(
            [asdict(item) for item in data[name]], ensure_ascii=False, indent=1
        )
        (out / f"{name}.json").write_text(payload, encoding="utf-8", newline="\n")
    with open(out / "order_history.csv", "w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["customer_id", "delivery_point", "date", "material_id", "qty"])
        for line in data["order_history"]:
            writer.writerow(
                [line.customer_id, line.delivery_point, line.date, line.material_id, line.qty]
            )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic data.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args(argv)
    write(args.out, seed=args.seed)


if __name__ == "__main__":
    main()
