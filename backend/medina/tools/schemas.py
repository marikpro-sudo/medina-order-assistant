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
    "build_upload_file": "build_upload_file",
}
