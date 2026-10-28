"""Read .xlsx / .xls / .csv into rows of strings and render them compactly for the model."""

from medina.parsers.order_table import MAX_ROWS, read_cells

__all__ = ["MAX_ROWS", "read_rows", "rows_to_text"]


def read_rows(data: bytes, filename: str) -> list[list[str]]:
    return [[cell.value for cell in row] for row in read_cells(data, filename)]


def rows_to_text(rows: list[list[str]]) -> str:
    """Pipe-separated rows with 1-based row numbers, so the model can cite rows."""
    return "\n".join(f"{i}: " + " | ".join(r) for i, r in enumerate(rows, start=1))
