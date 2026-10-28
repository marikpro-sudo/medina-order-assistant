"""Acceptance checks for the deterministic eval case generator."""

import json
import re
from collections import Counter

import pytest
import xlrd
from PIL import Image

from data_access.search import product_form_family
from data_access.synthetic import default_source
from evals.generate_cases import ERROR_CODES, generate

EXPECTED_COUNTS = {
    "text_ru": 40, "text_kk": 15, "sheet": 20,
    "portal_file": 10, "photo": 10, "long": 5,
}


@pytest.fixture(scope="module")
def out_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("cases") / "cases"
    generate(out)
    generate(out)
    return out


@pytest.fixture(scope="module")
def cases(out_dir):
    with open(out_dir / "cases.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def stock_in_branch(ds, material_id, customer_id):
    customer = ds.get_customer(customer_id)
    return sum(b.qty_available for b in ds.batches(material_id, customer.branch_plant))


def test_counts_ids_customers(cases):
    assert len(cases) == 100
    assert dict(Counter(c["kind"] for c in cases)) == EXPECTED_COUNTS
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == len(ids)
    ds = default_source()
    for c in cases:
        assert ds.get_customer(c["customer_id"]) is not None
    debtors = {cust.customer_id for cust in ds.customers() if cust.overdue_debt > 0}
    assert len(debtors) == 5
    assert sum(1 for c in cases if c["customer_id"] in debtors) >= 10


def test_gold_lines(cases):
    ds = default_source()
    for c in cases:
        for g in c["gold"]:
            assert g["acceptable"] or g["expect"] == "unrecognized"
            for mid in g["acceptable"]:
                assert ds.get_product(mid) is not None
            if g["expect"] in ("found", "rounded"):
                p = ds.get_product(g["material_id"])
                assert stock_in_branch(ds, g["material_id"], c["customer_id"]) >= g["gold_qty"]
                assert g["gold_qty"] % p.order_multiple == 0
            if g["expect"] == "rounded":
                nums = [int(x) for x in re.findall(r"\d+", g["source"])]
                assert nums and nums[-1] % ds.get_product(g["material_id"]).order_multiple != 0
            if g["expect"] == "analog":
                gold_p = ds.get_product(g["material_id"])
                assert stock_in_branch(ds, g["material_id"], c["customer_id"]) == 0
                assert g["acceptable"]
                for mid in g["acceptable"]:
                    q = ds.get_product(mid)
                    assert stock_in_branch(ds, mid, c["customer_id"]) > 0
                    assert q.inn == gold_p.inn
                    assert q.strength == gold_p.strength
                    assert product_form_family(q.dosage_form) == product_form_family(
                        gold_p.dosage_form)


def test_expect_shares(cases):
    expects = [g["expect"] for c in cases for g in c["gold"]]
    total = len(expects)
    assert total > 0
    share = {k: expects.count(k) / total for k in set(expects)}
    assert 0.45 <= share.get("found", 0) <= 0.75
    assert 0.08 <= share.get("rounded", 0) <= 0.25
    assert 0.08 <= share.get("analog", 0) <= 0.25


def test_portal_files(cases, out_dir):
    portals = [c for c in cases if c["kind"] == "portal_file"]
    assert len(portals) == 10
    for c in portals:
        assert 1 <= len(c["gold_errors"]) <= 3
        for err in c["gold_errors"]:
            assert err["code"] in ERROR_CODES
        data = (out_dir / c["attachment"]).read_bytes()
        book = xlrd.open_workbook(file_contents=data)
        assert book.sheet_by_index(0).nrows >= 6


def test_attachments(cases, out_dir):
    photos = 0
    for c in cases:
        if c["attachment"] is None:
            continue
        path = out_dir / c["attachment"]
        assert path.is_file()
        if path.suffix.lower() == ".png":
            photos += 1
            with Image.open(path) as img:
                assert img.width == 900
    assert photos == 10


def test_determinism(out_dir):
    first = (out_dir / "cases.jsonl").read_bytes()
    generate(out_dir)
    second = (out_dir / "cases.jsonl").read_bytes()
    assert first == second


def test_long_cases(cases):
    longs = [c for c in cases if c["kind"] == "long"]
    assert len(longs) == 5
    for c in longs:
        assert len(c["gold"]) == 30
