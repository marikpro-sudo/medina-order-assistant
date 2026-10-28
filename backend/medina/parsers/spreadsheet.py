"""Read .xlsx / .xls / .csv into rows of strings and render them compactly for the model."""

import csv
import io

import openpyxl
import xlrd

MAX_ROWS = 300


def read_rows(data: bytes, filename: str) -> list[list[str]]:
    name = filename.lower()
    if name.endswith(".xlsx"):
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = [[_cell(v) for v in row] for row in ws.iter_rows(values_only=True)]
    elif name.endswith(".xls"):
        sh = xlrd.open_workbook(file_contents=data).sheet_by_index(0)
        rows = [[_cell(sh.cell_value(r, c)) for c in range(sh.ncols)] for r in range(sh.nrows)]
    elif name.endswith(".csv"):
        text = _decode(data)
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t") if text.strip() else csv.excel
        rows = [list(r) for r in csv.reader(io.StringIO(text), dialect)]
    else:
        raise ValueError(f"unsupported file type: {filename}")
    rows = [r for r in rows if any(c.strip() for c in r)]
    return [_trim(r) for r in rows[:MAX_ROWS]]


def rows_to_text(rows: list[list[str]]) -> str:
    """Pipe-separated rows with 1-based row numbers, so the model can cite rows."""
    return "\n".join(f"{i}: " + " | ".join(r) for i, r in enumerate(rows, start=1))


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))  # Excel stores codes and quantities as floats
    return str(v).strip()


def _trim(row: list[str]) -> list[str]:
    while row and not row[-1].strip():
        row = row[:-1]
    return row


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
