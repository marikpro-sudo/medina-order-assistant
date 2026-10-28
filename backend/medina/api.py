"""HTTP API for the widget. Run: uv run uvicorn medina.api:app --port 8000

In production the customer id comes from the portal session (signed by the portal module),
not from a free form field; see integration/prestashop/.
"""

import re
import threading
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from data_access.synthetic import default_source
from medina.agent import Agent
from medina.llm import LLM, ROOT
from medina.inputs import UnsupportedFile, build_user_content
from medina.parsers.spreadsheet import read_rows

FILES_DIR = ROOT / ".cache" / "files"
MAX_UPLOAD = 10 * 1024 * 1024
MAX_SESSIONS = 200

app = FastAPI(title="Medina")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_llm = LLM()
_sessions: "OrderedDict[str, tuple[Agent, threading.Lock]]" = OrderedDict()
_sessions_lock = threading.Lock()


def _get_session(session_id: str, customer_id: str) -> tuple[str, Agent, threading.Lock]:
    ds = default_source()
    if ds.get_customer(customer_id) is None:
        raise HTTPException(400, "unknown customer")
    with _sessions_lock:
        entry = _sessions.get(session_id)
        if entry is None or entry[0].tools.customer.customer_id != customer_id:
            session_id = uuid.uuid4().hex
            entry = (Agent(ds, customer_id, _llm, FILES_DIR), threading.Lock())
            _sessions[session_id] = entry
            while len(_sessions) > MAX_SESSIONS:
                _sessions.popitem(last=False)
        _sessions.move_to_end(session_id)
    return session_id, *entry


def _user_content(agent: Agent, message: str, file: UploadFile | None, data: bytes) -> str | list:
    if file is None:
        return message
    try:
        return build_user_content(agent, message, file.filename or "file", file.content_type, data)
    except UnsupportedFile:
        raise HTTPException(415, "unsupported file type")


@app.post("/api/chat")
def chat(
    customer_id: str = Form(...),
    message: str = Form(""),
    session_id: str = Form(""),
    delivery_point: str = Form(""),
    lang: str = Form("ru"),
    file: UploadFile | None = File(None),
):
    data = file.file.read(MAX_UPLOAD + 1) if file else b""
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "file too large")
    if not message.strip() and file is None:
        raise HTTPException(400, "empty message")
    session_id, agent, lock = _get_session(session_id, customer_id)
    with lock:  # one turn at a time per conversation
        content = _user_content(agent, message.strip(), file, data)
        reply = agent.ask(content)
        files = [
            {"file_id": t["result"]["file_id"], "filename": t["result"]["filename"],
             "url": f"/api/files/{t['result']['file_id']}"}
            for t in agent.trace
            if t["tool"] == "build_upload_file" and "file_id" in t["result"]
        ]
    return {"session_id": session_id, "reply": reply, "files": files, "order": agent.tools.last_order}


class ResetRequest(BaseModel):
    session_id: str = ""


@app.post("/api/reset")
def reset(req: ResetRequest):
    with _sessions_lock:
        _sessions.pop(req.session_id, None)
    return {"ok": True}


@app.get("/api/files/{file_id}")
def download(file_id: str):
    if not re.fullmatch(r"[0-9a-f]{12}", file_id):
        raise HTTPException(404)
    path = FILES_DIR / f"order_{file_id}.xls"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="application/vnd.ms-excel", filename="medina_order_upload.xls")


# --- Demo portal endpoints (mock of the existing portal, synthetic data) ---

@app.get("/api/demo/customers")
def demo_customers():
    ds = default_source()
    return [{"customer_id": c.customer_id, "name": c.name, "overdue_debt": c.overdue_debt,
             "branch_plant": c.branch_plant} for c in ds.customers()]


@app.get("/api/demo/catalog")
def demo_catalog(customer_id: str, q: str = "", limit: int = 60):
    ds = default_source()
    c = ds.get_customer(customer_id)
    if c is None:
        raise HTTPException(400, "unknown customer")
    q = q.strip().lower()
    items = []
    # The existing portal search is a plain substring match; Medina's fuzzy search is the contrast.
    for p in ds.products():
        if q and q not in p.name_short.lower() and q not in p.inn.lower() and q != p.ean13:
            continue
        batches = sorted((b for b in ds.batches(p.material_id, c.branch_plant) if b.qty_available > 0),
                         key=lambda b: b.expiry_date)
        items.append({
            "material_id": p.material_id, "ean13": p.ean13, "name": p.name_short, "inn": p.inn,
            "manufacturer": p.manufacturer, "country": p.country, "order_multiple": p.order_multiple,
            "is_prescription": p.is_prescription,
            "batches": [{"batch_id": b.batch_id, "expiry_date": b.expiry_date,
                         "qty": b.qty_available, "price": b.price_customer} for b in batches],
        })
        if len(items) >= limit:
            break
    return items


@app.post("/api/demo/order-upload")
def demo_order_upload(file: UploadFile = File(...)):
    """Emulates the portal's strict upload: exactly 3 columns, any bad row fails the whole file."""
    data = file.file.read(MAX_UPLOAD + 1)
    ds = default_source()
    try:
        rows = read_rows(data, file.filename or "")
    except Exception:
        return {"ok": False, "error": "Ошибка загрузки файла"}
    rows = [r for r in rows if any(c.strip() for c in r)]  # read_rows keeps empty rows for row numbers
    if rows and not rows[0][0].isdigit():
        rows = rows[1:]  # header row
    lines = []
    for r in rows:
        if len(r) != 3:
            return {"ok": False, "error": "Ошибка загрузки файла"}
        ean, mid, qty = r
        p = ds.get_product(mid)
        if p is None or p.ean13 != ean or not qty.isdigit():
            return {"ok": False, "error": "Ошибка загрузки файла"}
        lines.append({"material_id": mid, "name": p.name_short, "qty": int(qty)})
    return {"ok": True, "lines": lines}


@app.get("/medina.js")
def widget_js():
    return FileResponse(ROOT / "widget" / "medina.js", media_type="application/javascript")


@app.get("/")
def root():
    return RedirectResponse("/demo/")


app.mount("/demo", StaticFiles(directory=Path(ROOT / "demo"), html=True), name="demo")
