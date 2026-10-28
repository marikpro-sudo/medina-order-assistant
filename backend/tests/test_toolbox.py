"""Toolbox tests over the real synthetic data source (no hardcoded ids)."""

from datetime import date

import pytest
import xlrd

from data_access.synthetic import default_source
from medina.tools.schemas import TOOL_METHODS, TOOL_SCHEMAS
from medina.tools.toolbox import SHORT_EXPIRY_DAYS, UPLOAD_HEADERS, Toolbox


@pytest.fixture(scope="session")
def ds():
    return default_source()


@pytest.fixture()
def toolbox(ds, tmp_path):
    # Function scope: tmp_path is per-test; first customer pins the branch.
    customer = ds.customers()[0]
    return Toolbox(ds, customer.customer_id, tmp_path)


def branch_stock(ds, material_id, plant):
    return sum(b.qty_available for b in ds.batches(material_id, plant))


def days_left(ds, batch):
    return (date.fromisoformat(batch.expiry_date) - ds.today()).days


def find_product(ds, plant, predicate):
    # Catalog order scan: deterministic first match, no hardcoded ids.
    for product in ds.products():
        if predicate(product):
            return product
    raise AssertionError("no matching product in synthetic data")


def clean_adjustable(ds, plant):
    # Non-Rx, multiple of 10, in stock, not short-expiry-only (clean "adjusted").
    def ok(p):
        if p.is_prescription or p.order_multiple != 10:
            return False
        if branch_stock(ds, p.material_id, plant) < 10:
            return False
        batches = [b for b in ds.batches(p.material_id, plant) if b.qty_available > 0]
        return bool(batches) and any(days_left(ds, b) > SHORT_EXPIRY_DAYS for b in batches)

    return find_product(ds, plant, ok)


def test_unknown_customer(ds, tmp_path):
    with pytest.raises(ValueError):
        Toolbox(ds, "NO_SUCH_CUSTOMER", tmp_path)


def test_check_line_rounds_to_multiple(toolbox, ds):
    product = clean_adjustable(ds, toolbox.plant)
    res = toolbox.check_line(product.material_id, 7)
    assert res["qty"] == 10
    assert res["status"] == "adjusted"
    assert {i["code"] for i in res["issues"]} >= {"rounded_to_multiple"}


def test_check_line_exact_multiple_has_no_rounding_issue(toolbox, ds):
    product = clean_adjustable(ds, toolbox.plant)
    res = toolbox.check_line(product.material_id, 10)
    assert res["qty"] == 10
    assert "rounded_to_multiple" not in {i["code"] for i in res["issues"]}


@pytest.mark.parametrize("bad_qty", [0, "abc"])
def test_check_line_bad_qty(toolbox, ds, bad_qty):
    product = clean_adjustable(ds, toolbox.plant)
    res = toolbox.check_line(product.material_id, bad_qty)
    assert res["status"] == "error"
    assert {i["code"] for i in res["issues"]} == {"bad_qty"}


def test_check_line_unknown_product(toolbox):
    res = toolbox.check_line("000000000000000000", 10)
    assert res["status"] == "error"
    assert {i["code"] for i in res["issues"]} == {"unknown_product"}


def test_check_line_prescription(toolbox, ds):
    def ok(p):
        stock = branch_stock(ds, p.material_id, toolbox.plant)
        return p.is_prescription and stock >= p.order_multiple

    product = find_product(ds, toolbox.plant, ok)
    res = toolbox.check_line(product.material_id, product.order_multiple)
    assert "prescription" in {i["code"] for i in res["issues"]}
    assert res["status"] == "warning"


def test_check_line_out_of_stock_in_branch(toolbox, ds):
    def ok(p):
        if branch_stock(ds, p.material_id, toolbox.plant) != 0:
            return False
        total = sum(b.qty_available for b in ds.batches(p.material_id))
        return total > 0

    product = find_product(ds, toolbox.plant, ok)
    res = toolbox.check_line(product.material_id, product.order_multiple)
    assert res["status"] == "unavailable"
    codes = {i["code"] for i in res["issues"]}
    assert "out_of_stock_in_branch" in codes
    others = next(i for i in res["issues"] if i["code"] == "out_of_stock_in_branch")
    assert others["other_branches"]


def test_check_line_insufficient_stock(toolbox, ds):
    def ok(p):
        return branch_stock(ds, p.material_id, toolbox.plant) > 0

    product = find_product(ds, toolbox.plant, ok)
    stock = branch_stock(ds, product.material_id, toolbox.plant)
    res = toolbox.check_line(product.material_id, stock + product.order_multiple)
    assert "insufficient_stock" in {i["code"] for i in res["issues"]}


def test_check_lines_order(toolbox, ds):
    a = clean_adjustable(ds, toolbox.plant)
    b = find_product(ds, toolbox.plant, lambda p: p.material_id != a.material_id)
    lines = [{"material_id": a.material_id, "qty": 7},
             {"material_id": b.material_id, "qty": b.order_multiple}]
    res = toolbox.check_lines(lines)
    assert [line["material_id"] for line in res["lines"]] == [a.material_id, b.material_id]


def test_get_batches(toolbox, ds):
    def ok(p):
        batches = [b for b in ds.batches(p.material_id, toolbox.plant) if b.qty_available > 0]
        return len(batches) >= 2

    product = find_product(ds, toolbox.plant, ok)
    res = toolbox.get_batches(product.material_id)
    assert "error" not in res
    expiries = [b["expiry_date"] for b in res["batches"]]
    assert expiries == sorted(expiries)  # ascending by expiry
    assert all(b["qty_available"] > 0 for b in res["batches"])
    for b in res["batches"]:
        assert b["short_expiry"] == (b["days_to_expiry"] <= SHORT_EXPIRY_DAYS)


def test_get_batches_unknown(toolbox):
    assert "error" in toolbox.get_batches("000000000000000000")


def find_source_with_analogs(toolbox, ds, limit):
    # First branch-out-of-stock product yielding at least 2 analogs.
    for product in ds.products():
        if branch_stock(ds, product.material_id, toolbox.plant) != 0:
            continue
        res = toolbox.find_analogs(product.material_id, limit=limit)
        if len(res.get("analogs", [])) >= 2:
            return product, res
    raise AssertionError("no out-of-stock product with analogs found")


def test_find_analogs(toolbox, ds):
    limit = 3
    source, res = find_source_with_analogs(toolbox, ds, limit)
    analogs = res["analogs"]
    assert len(analogs) <= limit
    assert all(a["stock_in_branch"] > 0 for a in analogs)
    assert all(a["material_id"] != source.material_id for a in analogs)
    tiers = [a["tier"] for a in analogs]
    assert tiers == sorted(tiers)  # non-decreasing tiers
    for a in analogs:
        if a["tier"] == 1:
            assert a["inn"] == source.inn
            assert a["strength"] == source.strength
    # Longest shelf life first: best_batch expiry non-increasing per tier.
    for tier in set(tiers):
        expiries = [a["best_batch"]["expiry_date"] for a in analogs if a["tier"] == tier]
        assert expiries == sorted(expiries, reverse=True)


def test_get_customer_status(ds, tmp_path):
    debtor = next(c for c in ds.customers() if c.overdue_debt > 0)
    ok = next(c for c in ds.customers() if c.overdue_debt == 0)
    bad = Toolbox(ds, debtor.customer_id, tmp_path).get_customer_status()
    assert bad["overdue_debt"] > 0
    assert bad["warning"]
    good = Toolbox(ds, ok.customer_id, tmp_path).get_customer_status()
    assert good["warning"] is None


def test_search_many(toolbox):
    queries = ["нурофен 400", "анальгин", "qwerty zzz"]
    res = toolbox.search_many(queries)
    assert [r["query"] for r in res["results"]] == queries


def test_build_upload_file(toolbox, ds):
    good_a = clean_adjustable(ds, toolbox.plant)
    good_b = find_product(
        ds, toolbox.plant,
        lambda p: p.material_id != good_a.material_id
        and branch_stock(ds, p.material_id, toolbox.plant) >= 2 * p.order_multiple)
    lines = [
        {"material_id": good_a.material_id, "qty": good_a.order_multiple},
        {"material_id": good_b.material_id, "qty": 2 * good_b.order_multiple},
        {"material_id": "000000000000000000", "qty": 10},  # unknown id
        {"material_id": good_a.material_id, "qty": 0},  # bad qty
        {"material_id": good_a.material_id, "qty": 7},  # not a multiple of 10
    ]
    res = toolbox.build_upload_file(lines)
    assert res["rows"] == 2
    included = [r for r in res["report"] if r["included"]]
    excluded = [r for r in res["report"] if not r["included"]]
    assert len(included) == res["rows"] == 2
    assert len(excluded) == 3 and all(r["reason"] for r in excluded)

    path = toolbox.files_dir / res["filename"]
    assert path.suffix == ".xls"
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    assert [sheet.cell_value(0, c) for c in range(sheet.ncols)] == list(UPLOAD_HEADERS)
    assert sheet.nrows == res["rows"] + 1
    wanted = {r["material_id"]: str(r["qty"]) for r in included}
    for row in range(1, sheet.nrows):
        assert all(sheet.cell_type(row, c) == xlrd.XL_CELL_TEXT
                   for c in range(sheet.ncols))  # every cell stored as text
        ean13, material_id, qty = (sheet.cell_value(row, c) for c in range(3))
        assert qty == wanted[material_id]
        assert ds.get_product(material_id).ean13 == ean13


def test_tool_schemas_match_methods():
    methods = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
    assert methods <= set(TOOL_METHODS)  # every schema maps to a method
    for method in TOOL_METHODS.values():
        assert callable(getattr(Toolbox, method))
    for schema in TOOL_SCHEMAS:
        params = schema["function"]["parameters"]
        for field in params.get("required", []):
            assert field in params["properties"]
