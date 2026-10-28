"""Turn a user message plus an optional attachment into model input. Shared by the API and evals."""

import base64

from medina.agent import Agent
from medina.parsers.spreadsheet import read_rows, rows_to_text

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
SHEET_EXT = (".xlsx", ".xls", ".csv")
PREVIEW_ROWS = 12


class UnsupportedFile(ValueError):
    pass


def build_user_content(agent: Agent, message: str, filename: str | None = None,
                       content_type: str | None = None, data: bytes = b"") -> str | list:
    if not filename:
        return message
    if (content_type or "") in IMAGE_TYPES:
        url = f"data:{content_type};base64,{base64.b64encode(data).decode()}"
        return [{"type": "text", "text": f"{message}\n\n[Attached photo: {filename}]"},
                {"type": "image_url", "image_url": {"url": url}}]
    if filename.lower().endswith(SHEET_EXT):
        agent.tools.attachments[filename] = data  # tools read the full file; the model sees a preview
        try:
            rows = read_rows(data, filename)
        except Exception as e:  # malformed file: let the model explain it to the user
            return f"{message}\n\n[Attached file {filename} could not be read: {e}]"
        preview = rows_to_text(rows[:PREVIEW_ROWS])
        return (f"{message}\n\n[Attached file {filename}: {len(rows)} rows. First rows (numbered as in Excel):]\n{preview}\n"
                f"[Use read_order_file or validate_upload_file with file_name=\"{filename}\".]")
    raise UnsupportedFile(filename)
