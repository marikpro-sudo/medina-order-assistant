"""Chat Completions tool definitions for the Toolbox methods.

Search and line checks are batched so a whole order costs one round trip each.
"""


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_MATERIAL_ID = {"type": "string", "description": "18-digit product code from search results"}
_LINES = {"type": "array", "items": {
    "type": "object",
    "properties": {"material_id": _MATERIAL_ID, "qty": {"type": "integer"}},
    "required": ["material_id", "qty"]}}

TOOL_SCHEMAS = [
    _fn("search_products",
        "Find catalog products for one or more queries (one product per query) by brand, INN, "
        "EAN-13 or product code. Tolerates typos, Latin transliteration and Kazakh. Include "
        "strength/form/pack if known (e.g. 'нурофен 200 мг таб №20'); never include the order quantity. "
        "Send all lines of an order in a single call.",
        {"queries": {"type": "array", "items": {"type": "string"}},
         "limit": {"type": "integer", "description": "results per query, default 3"}},
        ["queries"]),
    _fn("get_batches",
        "In-stock batches (expiry, quantity, price) of a product in the customer's branch.",
        {"material_id": _MATERIAL_ID}, ["material_id"]),
    _fn("find_analogs",
        "In-stock substitutes for a product: same INN+form+strength first, then same INN and form, "
        "then same ATC group. Sorted by shelf life.",
        {"material_id": _MATERIAL_ID, "limit": {"type": "integer", "description": "default 5"}},
        ["material_id"]),
    _fn("check_lines",
        "Validate order lines before upload: pack multiple (rounds up), prescription status, "
        "stock in the customer's branch, short expiry. Send all lines in one call.",
        {"lines": _LINES}, ["lines"]),
    _fn("get_customer_status",
        "Customer's branch, delivery points, credit limit and overdue debt.",
        {}, []),
    _fn("read_order_file",
        "Extract order lines from an attached spreadsheet in any layout (any column names, title rows, "
        "Russian/Kazakh). Lines with a valid barcode or product code come back already resolved; "
        "the rest come with a search_query for search_products.",
        {"file_name": {"type": "string"}}, ["file_name"]),
    _fn("validate_upload_file",
        "Check an attached file meant for the portal's strict order upload (Штрихкод | Код товара | "
        "Количество, text cells) row by row: why the portal would reject it and how to fix each row. "
        "Returns fixable_lines that can be passed to check_lines and build_upload_file.",
        {"file_name": {"type": "string"}}, ["file_name"]),
    _fn("suggest_reorder",
        "Reorder suggestions for the next 30 days from this customer's order history: same period last "
        "year blended with recent demand, rounded to pack multiples, with stock and a reason per item.",
        {"limit": {"type": "integer", "description": "default 12"},
         "seasonal_only": {"type": "boolean",
                           "description": "true for season questions (e.g. cold season): only items whose demand "
                                          "rises in this period"}}, []),
    _fn("present_order",
        "Record the final result of an order before showing the table: exactly one item per line of the "
        "user's order, in the user's order. status: found | rounded | analog | clarify | unrecognized. "
        "For analog set replaces to the unavailable product's material_id. material_id null if none.",
        {"lines": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "the user's original line text"},
                "material_id": {"type": ["string", "null"]},
                "qty": {"type": "integer"},
                "status": {"type": "string", "enum": ["found", "rounded", "analog", "clarify", "unrecognized"]},
                "replaces": {"type": ["string", "null"]},
            },
            "required": ["source", "material_id", "qty", "status"]}}},
        ["lines"]),
    _fn("build_upload_file",
        "Create the .xls file in the portal's order-upload format from the final lines. "
        "Quantities must already be multiples of order_multiple (use the qty from check_lines).",
        {"lines": _LINES}, ["lines"]),
]

# Tool name -> Toolbox method name.
TOOL_METHODS = {
    "search_products": "search_many",
    "get_batches": "get_batches",
    "find_analogs": "find_analogs",
    "check_lines": "check_lines",
    "get_customer_status": "get_customer_status",
    "read_order_file": "read_order_file",
    "validate_upload_file": "validate_upload_file",
    "suggest_reorder": "suggest_reorder",
    "present_order": "present_order",
    "build_upload_file": "build_upload_file",
}
