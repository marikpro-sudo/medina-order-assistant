"""Tests for order_table parsing (synthetic data only, generated in-memory)."""

import io
from datetime import datetime

import openpyxl
import pytest
import xlwt

from medina.parsers import spreadsheet
from medina.parsers.order_table import (
    detect_columns,
    extract_lines,
    find_header_row,
    parse_order_file,
    parse_qty,
    read_cells,
)


def _ean(base12: str) -> str:
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base12))
    return base12 + str((10 - total % 10) % 10)


EAN1 = _ean("487000000001")
EAN2 = _ean("487000000002")
EAN3 = _ean("487000000003")
EAN4 = _ean("487000000004")
MAT1 = "100000000000000001"
MAT2 = "100000000000000002"


def _xlsx_bytes(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _xls_bytes(rows: list[list]) -> bytes:
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Sheet1")
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            ws.write(i, j, value)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_portal_xls_all_text():
    data = _xls_bytes([
        ["Штрихкод", "Код товара", "Количество"],
        [EAN1, MAT1, "10"],
        [EAN2, MAT2, "5"],
    ])
    result = parse_order_file(data, "order.xls")
    assert result["header_row"] == 1
    assert result["columns"] == {"ean": "A", "material_id": "B", "qty": "C"}
    assert len(result["lines"]) == 2
    first, second = result["lines"]
    assert (first["ean"], first["material_id"], first["qty"]) == (EAN1, MAT1, 10)
    assert (second["ean"], second["material_id"], second["qty"]) == (EAN2, MAT2, 5)
    assert first["row"] == 2 and second["row"] == 3
    for line in result["lines"]:
        assert line["cells_text"] == {"ean": True, "material_id": True, "qty": True}
    assert result["warnings"] == []


def test_xlsx_title_rows_total_and_number_column():
    data = _xlsx_bytes([
        ["Заявка аптеки"],
        [datetime(2026, 10, 1)],
        ["№", "Наименование", "Производитель", "Кол-во, уп"],
        ["1", "Нурофен таб 200мг", "Восток-Фарм", 10],
        ["2", "Парацетамол 500мг", "Глобал Мед", 5],
        ["3", "Ибупрофен 400мг", "Восток-Фарм", 20],
        ["4", "Аспирин 100мг", "Медпоставка", 7],
        ["Итого", "", "", 42],
    ])
    result = parse_order_file(data, "order.xlsx")
    assert result["header_row"] == 3
    assert result["columns"] == {"name": "B", "manufacturer": "C", "qty": "D"}
    assert "A" not in result["columns"].values()
    assert [line["row"] for line in result["lines"]] == [4, 5, 6, 7]
    assert result["lines"][0]["name"] == "Нурофен таб 200мг"
    assert [line["qty"] for line in result["lines"]] == [10, 5, 20, 7]
    assert result["warnings"] == []


def test_csv_cp1251_semicolon():
    text = (
        "Штрих-код;Товар;Количество\n"
        f"{EAN1};Нурофен;10\n"
        f"{EAN2};Парацетамол;5\n"
    )
    result = parse_order_file(text.encode("cp1251"), "order.csv")
    assert result["header_row"] == 1
    assert result["columns"] == {"ean": "A", "name": "B", "qty": "C"}
    assert len(result["lines"]) == 2
    assert result["lines"][0]["ean"] == EAN1
    assert result["lines"][0]["name"] == "Нурофен"
    assert result["lines"][1]["qty"] == 5
    for line in result["lines"]:
        assert all(line["cells_text"].values())
    assert result["warnings"] == []


def test_xlsx_numeric_codes_warn():
    data = _xlsx_bytes([
        ["Штрихкод", "Код товара", "Количество"],
        [int(EAN1), int(MAT1), "5"],
    ])
    result = parse_order_file(data, "order.xlsx")
    assert result["columns"] == {"ean": "A", "material_id": "B", "qty": "C"}
    line = result["lines"][0]
    assert line["ean"] == EAN1
    assert line["material_id"].isdigit() and line["material_id"]
    assert line["cells_text"] == {"ean": False, "material_id": False, "qty": True}
    assert "codes stored as numbers in column A" in result["warnings"]
    assert "codes stored as numbers in column B" in result["warnings"]


def test_kazakh_header():
    data = _xlsx_bytes([
        ["Тауар атауы", "Саны"],
        ["Нурофен", "10"],
        ["Парацетамол", "5"],
    ])
    result = parse_order_file(data, "order.xlsx")
    assert result["header_row"] == 1
    assert result["columns"] == {"name": "A", "qty": "B"}
    assert [line["qty"] for line in result["lines"]] == [10, 5]


def test_no_header_detected_by_content():
    data = _xlsx_bytes([
        ["Парацетамол", "10"],
        [EAN1, "Нурофен", "5"],
        [EAN2, "Ибупрофен", "20"],
        [EAN3, "Аспирин", "7"],
        [EAN4, "Витамин", "15"],
    ])
    rows = read_cells(data, "order.xlsx")
    assert find_header_row(rows) is None
    cols = detect_columns(rows, None)
    assert (cols.ean, cols.name, cols.qty, cols.material_id) == (0, 1, 2, None)
    lines = extract_lines(rows, cols, None)
    assert len(lines) == 5
    third = lines[2]
    assert (third.row, third.name, third.ean, third.qty) == (3, "Ибупрофен", EAN2, 20)
    assert lines[0].qty is None
    result = parse_order_file(data, "order.xlsx")
    assert result["header_row"] is None
    assert result["columns"] == {"ean": "A", "name": "B", "qty": "C"}
    assert result["warnings"] == []


@pytest.mark.parametrize(("raw", "expected"), [
    ("10", 10), ("10.0", 10), ("10,0", 10), (" 10 ", 10),
    ("10 уп", 10), ("10уп.", 10), ("5шт", 5), ("5 шт.", 5),
    ("x10", 10), ("х10", 10), ("10 пач", 10), ("10 дана", 10), ("10 қорап", 10),
    ("", None), ("abc", None), ("0", None), ("-3", None), ("2.5", None), ("1,5", None),
])
def test_parse_qty(raw, expected):
    assert parse_qty(raw) == expected


def test_unsupported_extension():
    with pytest.raises(ValueError):
        read_cells(b"Штрихкод", "order.txt")


def test_corrupt_file():
    with pytest.raises(ValueError):
        read_cells(b"this is not a spreadsheet", "order.xlsx")


def test_read_rows_still_returns_strings():
    data = _xlsx_bytes([["Штрихкод", "Количество"], ["4870000000012", "10"]])
    rows = spreadsheet.read_rows(data, "orders.xlsx")
    assert rows == [["Штрихкод", "Количество"], ["4870000000012", "10"]]
    assert all(isinstance(cell, str) for row in rows for cell in row)
    assert spreadsheet.rows_to_text(rows).splitlines()[0] == "1: Штрихкод | Количество"
    assert spreadsheet.MAX_ROWS == 300
