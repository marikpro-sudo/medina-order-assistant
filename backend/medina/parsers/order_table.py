"""Deterministic parsing of pharmacy order tables in arbitrary layouts.

Pharmacies send orders as spreadsheets with title rows above the header,
localized column names and codes stored as numbers. This module extracts
order lines deterministically; an LLM handles what it cannot.
"""

import csv
import io
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime

import openpyxl
import xlrd

MAX_ROWS = 300
_HEADER_SCAN_ROWS = 15
_DATA_SCAN_ROWS = 50

HEADER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ean": ("штрихкод", "штрих-код", "штрих код", "ean", "barcode", "баркод", "шк"),
    "material_id": ("код товара", "код материала", "артикул", "material", "материал", "код"),
    "name": (
        "наименование", "название", "товар", "препарат", "номенклатура",
        "атауы", "тауар", "атау", "name", "product", "description",
    ),
    "qty": (
        "количество", "кол-во", "кол.", "колич", "qty", "quantity",
        "саны", "заказ", "шт", "упак",
    ),
    "manufacturer": ("производитель", "изготовитель", "өндіруші", "manufacturer", "producer"),
}
_ROLE_PRIORITY = ("ean", "material_id", "name", "qty", "manufacturer")

_TOTAL_PREFIXES = ("итого", "всего", "барлығы", "жиыны", "total")

_DIGITS_RE = re.compile(r"[^0-9]")
_WS_RE = re.compile(r"\s+")
_QTY_RE = re.compile(r"(\d+)(?:[.,](\d+))?")
_LETTER_RE = re.compile(r"[A-Za-z\u0400-\u04FF]")


@dataclass(frozen=True)
class Cell:
    value: str  # display string; integers without ".0"; None -> ""
    is_text: bool  # True if stored as text


@dataclass(frozen=True)
class ColumnMap:
    ean: int | None
    material_id: int | None
    name: int | None
    qty: int | None
    manufacturer: int | None


@dataclass(frozen=True)
class OrderLine:
    row: int  # 1-based row number in the file (as a user sees it in Excel)
    name: str
    ean: str
    material_id: str
    qty_raw: str
    qty: int | None
    cells_text: dict[str, bool]  # role -> is_text of the source cell


def read_cells(data: bytes, filename: str) -> list[list[Cell]]:
    """Read the first sheet into display strings, keeping row positions stable.

    Returns all rows up to MAX_ROWS (fully empty rows included, trailing
    empty cells trimmed). Raises ValueError for other extensions or
    unreadable files.
    """
    name = filename.lower()
    if name.endswith(".xlsx"):
        return _read_xlsx(data)
    if name.endswith(".xls"):
        return _read_xls(data)
    if name.endswith(".csv"):
        return _read_csv(data)
    raise ValueError(f"unsupported file type: {filename}")


def find_header_row(rows: list[list[Cell]]) -> int | None:
    """0-based index of the first row among the first 15 with >= 2 keyword cells."""
    for i, row in enumerate(rows[:_HEADER_SCAN_ROWS]):
        if sum(1 for cell in row if _matches_any(cell.value)) >= 2:
            return i
    return None


def detect_columns(rows: list[list[Cell]], header_idx: int | None) -> ColumnMap:
    """Map roles to column indexes, first by header keywords then by content."""
    found: dict[str, int] = {}
    claimed: set[int] = set()
    header: list[Cell] = []
    if header_idx is not None and 0 <= header_idx < len(rows):
        header = rows[header_idx]
        scored: list[tuple[int, int, int, str]] = []
        for col, cell in enumerate(header):
            for priority, role in enumerate(_ROLE_PRIORITY):
                length = _match_len(cell.value, HEADER_KEYWORDS[role])
                if length:
                    scored.append((-length, priority, col, role))
        # Longest keyword match wins, so "штрих-код" beats bare "шт"/"код".
        for _, _, col, role in sorted(scored):
            if role not in found and col not in claimed:
                found[role] = col
                claimed.add(col)
    if header_idx is not None:
        data = rows[header_idx + 1: header_idx + 1 + _DATA_SCAN_ROWS]
    else:
        data = rows[:_DATA_SCAN_ROWS]
    width = max([len(header)] + [len(row) for row in data] + [0])
    # Headers lie ("Штрихкод" over product names): a code column must mostly hold codes.
    for role, is_code in (("ean", _ean_ok), ("material_id", _material_ok)):
        col = found.get(role)
        if col is not None and _share(data, col, is_code) < 0.6:
            del found[role]
            if "name" not in found and _share(data, col, _name_ok) >= 0.6:
                found["name"] = col
            else:
                claimed.discard(col)
    for role, is_code in (("ean", _ean_ok), ("material_id", _material_ok)):
        if role not in found:
            col = _pick_share(data, width, claimed, is_code)
            if col is not None:
                found[role] = col
                claimed.add(col)
    if "qty" not in found:
        col = _pick_qty(data, width, claimed)
        if col is not None:
            found["qty"] = col
            claimed.add(col)
    if "name" not in found:
        col = _pick_share(data, width, claimed, _name_ok, threshold=False)
        if col is not None:
            found["name"] = col
            claimed.add(col)
    return ColumnMap(
        ean=found.get("ean"),
        material_id=found.get("material_id"),
        name=found.get("name"),
        qty=found.get("qty"),
        manufacturer=found.get("manufacturer"),
    )


def parse_qty(s: str) -> int | None:
    """Parse a quantity like "10 уп", "5шт." or "x10" into an int."""
    text = s.strip().lower()
    if not text or "-" in text or "–" in text or "—" in text:
        return None
    match = _QTY_RE.search(text)
    if not match:
        return None
    frac = match.group(2)
    if frac is not None and int(frac) != 0:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def extract_lines(
    rows: list[list[Cell]], cols: ColumnMap, header_idx: int | None
) -> list[OrderLine]:
    """Rows after the header (or all rows), skipping empty and total rows."""
    start = header_idx + 1 if header_idx is not None else 0
    lines = []
    for i in range(start, len(rows)):
        row = rows[i]
        if any(
            cell.value.casefold().startswith(prefix)
            for cell in row
            for prefix in _TOTAL_PREFIXES
        ):
            continue
        ean_cell = _take(row, cols.ean)
        mat_cell = _take(row, cols.material_id)
        name_cell = _take(row, cols.name)
        qty_cell = _take(row, cols.qty)
        name = name_cell.value if name_cell else ""
        ean = _DIGITS_RE.sub("", ean_cell.value) if ean_cell else ""
        material_id = _DIGITS_RE.sub("", mat_cell.value) if mat_cell else ""
        if not name and not ean and not material_id:
            continue
        qty_raw = qty_cell.value if qty_cell else ""
        cells_text = {
            role: cell.is_text
            for role, cell in (("ean", ean_cell), ("material_id", mat_cell), ("qty", qty_cell))
            if cell is not None
        }
        lines.append(
            OrderLine(
                row=i + 1,
                name=name,
                ean=ean,
                material_id=material_id,
                qty_raw=qty_raw,
                qty=parse_qty(qty_raw),
                cells_text=cells_text,
            )
        )
    return lines


def parse_order_file(data: bytes, filename: str) -> dict:
    """Parse any supported order file into lines, column letters and warnings."""
    rows = read_cells(data, filename)
    header_idx = find_header_row(rows)
    cols = detect_columns(rows, header_idx)
    lines = extract_lines(rows, cols, header_idx)
    columns = {
        role: _col_letter(index) for role, index in asdict(cols).items() if index is not None
    }
    warnings: list[str] = []
    if cols.qty is None:
        warnings.append("no quantity column detected")
    if cols.ean is None and cols.material_id is None and cols.name is None:
        warnings.append("no product column detected")
    body = rows[header_idx + 1:] if header_idx is not None else rows
    for role in ("ean", "material_id"):
        index = getattr(cols, role)
        if index is None:
            continue
        numeric = any(
            index < len(row) and row[index].value and not row[index].is_text for row in body
        )
        if numeric:
            warnings.append(f"codes stored as numbers in column {_col_letter(index)}")
    return {
        "header_row": header_idx + 1 if header_idx is not None else None,
        "columns": columns,
        "lines": [asdict(line) for line in lines],
        "warnings": warnings,
    }


def _read_xlsx(data: bytes) -> list[list[Cell]]:
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"cannot read .xlsx file: {exc}") from exc
    try:
        try:
            ws = wb.worksheets[0]
        except IndexError as exc:
            raise ValueError("cannot read .xlsx file: no sheets") from exc
        rows = []
        for raw in ws.iter_rows():
            cells = [
                Cell(value=_display(cell.value), is_text=cell.data_type in ("s", "inlineStr"))
                for cell in raw
            ]
            rows.append(_trim(cells))
            if len(rows) >= MAX_ROWS:
                break
        return rows
    finally:
        wb.close()


def _read_xls(data: bytes) -> list[list[Cell]]:
    try:
        book = xlrd.open_workbook(file_contents=data)
        sheet = book.sheet_by_index(0)
    except Exception as exc:
        raise ValueError(f"cannot read .xls file: {exc}") from exc
    rows = []
    for r in range(min(sheet.nrows, MAX_ROWS)):
        cells = []
        for c in range(sheet.ncols):
            kind = sheet.cell_type(r, c)
            raw = sheet.cell_value(r, c)
            if kind == xlrd.XL_CELL_TEXT:
                cells.append(Cell(value=str(raw).strip(), is_text=True))
            elif kind in (xlrd.XL_CELL_NUMBER, xlrd.XL_CELL_DATE):
                cells.append(Cell(value=_display(float(raw)), is_text=False))
            elif kind == xlrd.XL_CELL_BOOLEAN:
                cells.append(Cell(value=str(int(raw)), is_text=False))
            else:
                cells.append(Cell(value="", is_text=False))
        rows.append(_trim(cells))
    return rows


def _read_csv(data: bytes) -> list[list[Cell]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1251")
        except UnicodeDecodeError as exc:
            raise ValueError(f"cannot decode .csv file: {exc}") from exc
    if not text.strip():
        return []
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
        parsed = list(csv.reader(io.StringIO(text), dialect))
    except csv.Error:
        first = next((line for line in text.splitlines() if line.strip()), "")
        delim = max((";", ",", "\t"), key=lambda d: first.count(d))
        parsed = list(csv.reader(io.StringIO(text), delimiter=delim))
    rows = []
    for record in parsed:
        rows.append(_trim([Cell(value=field.strip(), is_text=True) for field in record]))
        if len(rows) >= MAX_ROWS:
            break
    return rows


def _display(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        text = repr(value)
        if "." in text and "e" not in text and "E" not in text:
            text = text.rstrip("0").rstrip(".")
        return text
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ")
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _trim(cells: list[Cell]) -> list[Cell]:
    while cells and not cells[-1].value:
        cells.pop()
    return cells


def _match_len(text: str, keywords: tuple[str, ...]) -> int:
    folded = text.casefold()
    return max((len(kw) for kw in keywords if kw in folded), default=0)


def _matches_any(text: str) -> bool:
    folded = text.casefold()
    return any(kw in folded for kws in HEADER_KEYWORDS.values() for kw in kws)


def _ean_ok(value: str) -> bool:
    digits = _WS_RE.sub("", value)
    if not re.fullmatch(r"[0-9]{13}", digits):
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == int(digits[12])


def _material_ok(value: str) -> bool:
    return re.fullmatch(r"[0-9]{18}", _WS_RE.sub("", value)) is not None


def _name_ok(value: str) -> bool:
    return len(_LETTER_RE.findall(value)) >= 3


def _share(data, col: int, ok) -> float:
    values = [row[col].value for row in data if col < len(row) and row[col].value]
    return sum(1 for v in values if ok(v)) / len(values) if values else 0.0


def _pick_share(data, width: int, claimed: set[int], ok, threshold: bool = True):
    """Column with the best ok/total share; threshold=True requires >= 60%."""
    best = None
    for col in range(width):
        if col in claimed:
            continue
        good = total = 0
        for row in data:
            if col < len(row):
                value = row[col].value
                if not value:
                    continue
                total += 1
                if ok(value):
                    good += 1
        if not total or not good or (threshold and good * 5 < total * 3):
            continue
        if best is None or good * best[1] > best[0] * total:
            best = (good, total, col)
    return best[2] if best is not None else None


def _pick_qty(data, width: int, claimed: set[int]):
    """Quantity column by content, rejecting 1..N running-number columns."""
    best = None
    for col in range(width):
        if col in claimed:
            continue
        good = total = 0
        values: list[int] = []
        for row in data:
            if col < len(row):
                value = row[col].value
                if not value:
                    continue
                total += 1
                qty = parse_qty(value)
                if qty is not None and qty <= 100000:
                    good += 1
                    values.append(qty)
        if not total or good * 5 < total * 3:
            continue
        if values == list(range(1, len(values) + 1)):
            continue
        if best is None or good * best[1] > best[0] * total:
            best = (good, total, col)
    return best[2] if best is not None else None


def _take(row: list[Cell], index: int | None) -> Cell | None:
    if index is not None and index < len(row):
        return row[index]
    return None


def _col_letter(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name
