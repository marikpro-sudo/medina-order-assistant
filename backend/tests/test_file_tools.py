"""File tool tests: validate_upload_file, read_order_file, suggest_reorder, present_order.

No LLM or network calls. Files are built in memory with xlwt/openpyxl, product
ids are picked dynamically from the synthetic catalog (no hardcoded ids).
"""

import io

import openpyxl
import pytest
import xlwt

from data_access.synthetic import default_source
from medina.tools.toolbox import Toolbox


@pytest.fixture(scope="module")
def ds():
    return default_source()


@pytest.fixture()
def toolbox(ds, tmp_path):
    customer = ds.customers()[0]
    return Toolbox(ds, customer.customer_id, tmp_path)


def find_product(ds, predicate):
    for product in ds.products():
        if predicate(product):
            return product
    raise AssertionError("no matching product in synthetic data")


def multi_product(ds, plant, multiple=10):
    return find_product(ds, plant, lambda p: p.order_multiple == multiple)


def _xls_bytes(rows: list[list], numeric: set[tuple[int, int]] | None = None) -> bytes:
    """Build an .xls; every cell is text except positions in ``numeric``."""
    numeric = numeric or set()
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Order")
    text = xlwt.easyxf(num_format_str="@")
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if (r, c) in numeric:
                ws.write(r, c, int(value))
            else:
                ws.write(r, c, str(value), text)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _xlsx_bytes(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _ean_bad(ean: str) -> str:
    return ean[:-1] + str((int(ean[-1]) + 1) % 10)


def _problems_by_code(result):
    out = {}
    for problem in result.get("problems", []):
        out.setdefault(problem["code"], []).append(problem["row"])
    return out


def _valid_row(product, qty=None):
    return [product.ean13, product.material_id, str(qty if qty is not None else 2 * product.order_multiple)]


# --- validate_upload_file: correct file ---

def test_validate_correct_file(toolbox, ds):
    products = ds.products()[:3]
    rows = [["Штрихкод", "Код товара", "Количество"]]
    rows += [_valid_row(p) for p in products]
    toolbox.attachments["order.xls"] = _xls_bytes(rows)
    res = toolbox.validate_upload_file("order.xls")
    assert "error" not in res
    assert res["header_ok"] is True
    assert res["would_fail"] is False
    assert res["problems"] == []
    assert len(res["fixable_lines"]) == 3


# --- validate_upload_file: injected errors, each with the right row and code ---

def test_validate_not_multiple(toolbox, ds):
    product = multi_product(ds, toolbox.plant)
    toolbox.attachments["f.xls"] = _xls_bytes(
        [["Штрихкод", "Код товара", "Количество"], _valid_row(product, product.order_multiple + 1)])
    by_code = _problems_by_code(toolbox.validate_upload_file("f.xls"))
    assert by_code.get("not_multiple") == [2]


def test_validate_bad_qty(toolbox, ds):
    product = ds.products()[0]
    toolbox.attachments["f.xls"] = _xls_bytes(
        [["Штрихкод", "Код товара", "Количество"], [product.ean13, product.material_id, "10 уп"]])
    by_code = _problems_by_code(toolbox.validate_upload_file("f.xls"))
    assert by_code.get("bad_qty") == [2]


def test_validate_ean_code_mismatch(toolbox, ds):
    first, second = ds.products()[0], ds.products()[1]
    toolbox.attachments["f.xls"] = _xls_bytes(
        [["Штрихкод", "Код товара", "Количество"],
         [first.ean13, second.material_id, str(2 * second.order_multiple)]])
    by_code = _problems_by_code(toolbox.validate_upload_file("f.xls"))
    assert by_code.get("ean_code_mismatch") == [2]


def test_validate_bad_ean_check_digit(toolbox, ds):
    product = next(p for p in ds.products() if ds.get_by_ean(_ean_bad(p.ean13)) is None)
    bad = _ean_bad(product.ean13)
    toolbox.attachments["f.xls"] = _xls_bytes(
        [["Штрихкод", "Код товара", "Количество"],
         [bad, product.material_id, str(2 * product.order_multiple)]])
    res = toolbox.validate_upload_file("f.xls")
    assert _problems_by_code(res).get("bad_ean") == [2]
    message = next(p["message"] for p in res["problems"] if p["code"] == "bad_ean")
    assert "контрольная" in message


def test_validate_bad_material_id(toolbox, ds):
    product = ds.products()[0]
    toolbox.attachments["f.xls"] = _xls_bytes(
        [["Штрихкод", "Код товара", "Количество"],
         [product.ean13, "12345678901234567", str(2 * product.order_multiple)]])
    by_code = _problems_by_code(toolbox.validate_upload_file("f.xls"))
    assert by_code.get("bad_material_id") == [2]


def test_validate_not_text(toolbox, ds):
    product = multi_product(ds, toolbox.plant)
    data = _xls_bytes(
        [["Штрихкод", "Код товара", "Количество"],
         [product.ean13, product.material_id, str(2 * product.order_multiple)]],
        numeric={(1, 2)})
    toolbox.attachments["f.xls"] = data
    by_code = _problems_by_code(toolbox.validate_upload_file("f.xls"))
    assert by_code.get("not_text") == [2]


def test_validate_column_count(toolbox, ds):
    product = ds.products()[0]
    toolbox.attachments["f.xls"] = _xls_bytes(
        [["Штрихкод", "Код товара", "Количество"],
         [product.ean13, product.material_id, "10", "доп. колонка"]])
    by_code = _problems_by_code(toolbox.validate_upload_file("f.xls"))
    assert by_code.get("column_count") == [2]


def test_validate_duplicate(toolbox, ds):
    product = ds.products()[0]
    row = _valid_row(product)
    toolbox.attachments["f.xls"] = _xls_bytes(
        [["Штрихкод", "Код товара", "Количество"], row, list(row)])
    by_code = _problems_by_code(toolbox.validate_upload_file("f.xls"))
    assert by_code.get("duplicate") == [3]


# --- validate_upload_file: attachment resolution ---

def test_validate_unknown_file_no_attachments(toolbox):
    assert toolbox.attachments == {}
    res = toolbox.validate_upload_file("missing.xls")
    assert "error" in res


def test_validate_single_attachment_any_name(toolbox, ds):
    product = ds.products()[0]
    toolbox.attachments["real_name.xls"] = _xls_bytes(
        [["Штрихкод", "Код товара", "Количество"], _valid_row(product)])
    res = toolbox.validate_upload_file("typo_name.xls")
    assert "error" not in res
    assert res["would_fail"] is False


# --- read_order_file ---

def test_read_order_file_title_and_numbered(toolbox):
    data = _xlsx_bytes([
        ["Заказ от аптеки"],
        [""],
        ["№", "Наименование", "Кол-во"],
        ["1", "Тестовит 200 мг таб", 10],
        ["2", "Примерол 5 мг капс", 5],
    ])
    toolbox.attachments["order.xlsx"] = data
    res = toolbox.read_order_file("order.xlsx")
    assert "error" not in res
    assert len(res["lines"]) == 2
    assert [line["row"] for line in res["lines"]] == [4, 5]
    for line, qty in zip(res["lines"], [10, 5]):
        assert line["search_query"]
        assert "resolved" not in line
        assert line["qty"] == qty


def test_read_order_file_ean_resolved(toolbox, ds):
    first, second = ds.products()[2], ds.products()[3]
    data = _xlsx_bytes([
        ["Наименование", "Штрихкод", "Количество"],
        [first.name_short, first.ean13, 2 * first.order_multiple],
        [second.name_short, second.ean13, 2 * second.order_multiple],
    ])
    toolbox.attachments["order.xlsx"] = data
    res = toolbox.read_order_file("order.xlsx")
    assert "error" not in res
    assert [line["resolved"]["material_id"] for line in res["lines"]] == [
        first.material_id, second.material_id]


# --- suggest_reorder ---

def _customer_with_seasonal_suggestions(ds, tmp_path):
    for customer in ds.customers():
        if not ds.history(customer.customer_id):
            continue
        toolbox = Toolbox(ds, customer.customer_id, tmp_path)
        suggestions = toolbox.suggest_reorder(seasonal_only=True)["suggestions"]
        if suggestions:
            return toolbox, suggestions
    raise AssertionError("no customer with seasonal suggestions in synthetic data")


def test_suggest_reorder_seasonal_only(ds, tmp_path):
    toolbox, suggestions = _customer_with_seasonal_suggestions(ds, tmp_path)
    assert suggestions
    seasonality = toolbox._inn_seasonality()
    for item in suggestions:
        assert seasonality[item["inn"]] >= 1.3
        product = ds.get_product(item["material_id"])
        assert item["qty"] % product.order_multiple == 0
        assert item["reason"]


def test_suggest_reorder_all_is_superset(ds, tmp_path):
    toolbox, seasonal = _customer_with_seasonal_suggestions(ds, tmp_path)
    all_items = toolbox.suggest_reorder(seasonal_only=False)["suggestions"]
    assert len(all_items) >= len(seasonal)


# --- present_order ---

def test_present_order_valid(toolbox, ds):
    product = multi_product(ds, toolbox.plant)
    lines = [{"source": "test line", "material_id": product.material_id,
              "qty": product.order_multiple, "status": "found"}]
    res = toolbox.present_order(lines)
    assert res["ok"] is True
    assert res["problems"] == []
    assert toolbox.last_order is not None
    assert toolbox.last_order[0]["material_id"] == product.material_id


def test_present_order_problems(toolbox, ds):
    product = multi_product(ds, toolbox.plant)
    base = {"source": "test line", "material_id": product.material_id,
            "qty": product.order_multiple, "status": "found"}
    unknown = dict(base, material_id="199999999999999999")
    assert toolbox.present_order([unknown])["ok"] is False
    assert toolbox.present_order([unknown])["problems"]
    bad_status = dict(base, status="mystery")
    assert toolbox.present_order([bad_status])["ok"] is False
    assert toolbox.present_order([bad_status])["problems"]
    bad_qty = dict(base, qty=product.order_multiple + 1)
    res = toolbox.present_order([bad_qty])
    assert res["ok"] is False
    assert res["problems"]
