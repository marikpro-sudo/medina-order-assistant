"""Tests for the deterministic synthetic data generator (`data/generate.py`).

All checks run against seed-42 output: determinism, product/batch/customer
shape rules, and order-history properties.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

import pytest

from data.generate import REF_DATE, generate, write
from data.inn_catalog import INN_GROUPS
from data.schema import Batch, Customer, OrderHistoryLine, Product

SEED = 42
ALT_SEED = 7
FILES = ("products.json", "batches.json", "customers.json", "order_history.csv")
HISTORY_START = "2025-10-28"
HISTORY_END = "2026-10-27"
HEADER = ["customer_id", "delivery_point", "date", "material_id", "qty"]


@pytest.fixture(scope="module")
def out_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("synthetic-seed42")
    write(out, seed=SEED)
    return out


def _read_json(out: Path, name: str) -> list[dict]:
    return json.loads((out / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def products(out_dir: Path) -> list[dict]:
    return _read_json(out_dir, "products.json")


@pytest.fixture(scope="module")
def batches(out_dir: Path) -> list[dict]:
    return _read_json(out_dir, "batches.json")


@pytest.fixture(scope="module")
def customers(out_dir: Path) -> list[dict]:
    return _read_json(out_dir, "customers.json")


@pytest.fixture(scope="module")
def order_rows(out_dir: Path) -> list[dict]:
    with open(out_dir / "order_history.csv", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == HEADER
        return list(reader)


def test_generate_api_shape() -> None:
    data = generate(seed=SEED)
    assert set(data) == {"products", "batches", "customers", "order_history"}
    assert all(isinstance(p, Product) for p in data["products"])
    assert all(isinstance(b, Batch) for b in data["batches"])
    assert all(isinstance(c, Customer) for c in data["customers"])
    assert all(isinstance(line, OrderHistoryLine) for line in data["order_history"])


def test_same_seed_byte_identical(out_dir: Path, tmp_path: Path) -> None:
    rerun = tmp_path / "rerun"
    write(rerun, seed=SEED)
    for name in FILES:
        assert (rerun / name).read_bytes() == (out_dir / name).read_bytes()


def test_different_seed_differs(out_dir: Path, tmp_path: Path) -> None:
    alt = tmp_path / "alt"
    write(alt, seed=ALT_SEED)
    assert (alt / "products.json").read_bytes() != (out_dir / "products.json").read_bytes()


def test_product_count_and_material_ids(products: list[dict]) -> None:
    assert 380 <= len(products) <= 420
    ids = [p["material_id"] for p in products]
    assert len(set(ids)) == len(ids)
    for mid in ids:
        assert len(mid) == 18 and mid.isdigit() and mid.startswith("1000000000000")


def _ean_valid(code: str) -> bool:
    if len(code) != 13 or not code.isdigit():
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(code[:12]))
    return (10 - total % 10) % 10 == int(code[12])


def test_ean13_unique_and_valid(products: list[dict]) -> None:
    codes = [p["ean13"] for p in products]
    assert len(set(codes)) == len(codes)
    assert all(_ean_valid(code) for code in codes)


def test_order_multiple_and_inn_coverage(products: list[dict]) -> None:
    for p in products:
        assert p["order_multiple"] in (1, 5, 10, 20)
    counts = Counter(p["inn"] for p in products)
    for group in INN_GROUPS:
        assert counts[group["inn"]] >= 2, group["inn"]


def test_stock_and_prescription_shares(
    products: list[dict], batches: list[dict]
) -> None:
    by_material: dict[str, list[dict]] = defaultdict(list)
    for batch in batches:
        by_material[batch["material_id"]].append(batch)
    n = len(products)
    out_of_stock = sum(
        1
        for p in products
        if all(b["qty_available"] == 0 for b in by_material.get(p["material_id"], []))
    )
    assert 0.12 <= out_of_stock / n <= 0.18
    short_limit = (REF_DATE + timedelta(days=90)).isoformat()
    short_expiry = sum(
        1
        for p in products
        if any(
            b["qty_available"] > 0 and b["expiry_date"] <= short_limit
            for b in by_material.get(p["material_id"], [])
        )
    )
    assert 0.07 <= short_expiry / n <= 0.13
    prescription = sum(1 for p in products if p["is_prescription"])
    assert 0.07 <= prescription / n <= 0.15


def test_batch_dates(batches: list[dict]) -> None:
    ref = REF_DATE.isoformat()
    assert batches
    for b in batches:
        assert b["expiry_date"] > ref, b
        if b["qty_available"] > 0:
            assert b["manufacture_date"] < ref < b["expiry_date"], b
        else:
            assert b["manufacture_date"] < ref, b


def test_customers(customers: list[dict]) -> None:
    assert len(customers) == 50
    assert sum(1 for c in customers if c["overdue_debt"] > 0) == 5
    assert all(c["overdue_debt"] == 0.0 for c in customers if c["overdue_debt"] <= 0)
    points = [p["point_id"] for c in customers for p in c["delivery_points"]]
    assert all(c["delivery_points"] for c in customers)
    assert len(set(points)) == len(points)


def test_order_history(
    products: list[dict], customers: list[dict], order_rows: list[dict]
) -> None:
    assert order_rows
    product_ids = {p["material_id"] for p in products}
    multiple = {p["material_id"]: p["order_multiple"] for p in products}
    season = {group["inn"]: group["season"] for group in INN_GROUPS}
    product_season = {p["material_id"]: season[p["inn"]] for p in products}
    point_ids = {p["point_id"] for c in customers for p in c["delivery_points"]}
    customer_ids = {c["customer_id"] for c in customers}
    months: set[str] = set()
    cold_qty = 0
    warm_qty = 0
    keys = []
    for row in order_rows:
        assert row["material_id"] in product_ids
        assert row["delivery_point"] in point_ids
        assert row["customer_id"] in customer_ids
        assert HISTORY_START <= row["date"] <= HISTORY_END
        months.add(row["date"][:7])
        qty = int(row["qty"])
        assert qty % multiple[row["material_id"]] == 0
        if product_season[row["material_id"]] == "cold":
            if int(row["date"][5:7]) in (10, 11, 12, 1, 2, 3):
                cold_qty += qty
            else:
                warm_qty += qty
        keys.append(
            (row["date"], row["customer_id"], row["delivery_point"], row["material_id"])
        )
    assert len(months) == 12
    assert keys == sorted(keys)
    assert cold_qty > 1.5 * warm_qty
