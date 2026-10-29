"""HTTP API for the widget. Run: uv run uvicorn medina.api:app --port 8000

In production the customer id comes from the portal session (signed by the portal module),
not from a free form field; see integration/prestashop/.
"""

import logging
import os
import re
import threading
import time
import uuid
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from openai import APIError
from pydantic import BaseModel

from data_access.synthetic import default_source
from medina.agent import UI_LANGUAGES, Agent
from medina.llm import LLM, ROOT, BudgetExceeded
from medina.inputs import UnsupportedFile, build_user_content
from medina.parsers.spreadsheet import read_rows

FILES_DIR = ROOT / ".cache" / "files"
MAX_UPLOAD = 10 * 1024 * 1024
MAX_SESSIONS = 200

log = logging.getLogger("medina")
app = FastAPI(title="Medina")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_llm = LLM()
_sessions: "OrderedDict[str, tuple[Agent, threading.Lock]]" = OrderedDict()
_sessions_lock = threading.Lock()


def _get_session(session_id: str, customer_id: str, lang: str = "ru") -> tuple[str, Agent, threading.Lock]:
    ds = default_source()
    if ds.get_customer(customer_id) is None:
        raise HTTPException(400, "unknown customer")
    with _sessions_lock:
        entry = _sessions.get(session_id)
        if entry is None or entry[0].tools.customer.customer_id != customer_id:
            session_id = uuid.uuid4().hex
            entry = (Agent(ds, customer_id, _llm, FILES_DIR, ui_lang=lang), threading.Lock())
            _sessions[session_id] = entry
            while len(_sessions) > MAX_SESSIONS:
                _sessions.popitem(last=False)
        _sessions.move_to_end(session_id)
    return session_id, *entry


def _with_language_hint(content: str | list, lang: str) -> str | list:
    """Tool results are in Russian, which pulls replies into Russian; state the UI language each turn."""
    name = UI_LANGUAGES.get(lang)
    if not name or lang == "ru":
        return content
    hint = f"\n\n[Interface language: {name}. Reply in {name} unless this message is written in another language.]"
    if isinstance(content, str):
        return content + hint
    return [{**p, "text": p["text"] + hint} if p.get("type") == "text" else p for p in content]


def _user_content(agent: Agent, message: str, file: UploadFile | None, data: bytes) -> str | list:
    if file is None:
        return message
    try:
        return build_user_content(agent, message, file.filename or "file", file.content_type, data)
    except UnsupportedFile:
        raise HTTPException(415, "unsupported file type")


MAX_MESSAGE = 4000
RATE_PER_HOUR = int(os.environ.get("MEDINA_RATE_PER_HOUR", "0") or 0)  # 0 = no limit (local dev)
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()

LIMIT_REPLIES = {
    "budget": {"ru": "Демо-лимит запросов к модели на сегодня исчерпан. Посмотрите видео-демо или запустите проект локально.",
               "kk": "Модельге сұраныстардың демо-лимиті таусылды. Видео-демоны қараңыз немесе жобаны жергілікті іске қосыңыз.",
               "en": "The demo's model budget is used up. Please watch the demo video or run the project locally."},
    "model": {"ru": "Модель сейчас недоступна, попробуйте позже.",
              "kk": "Модель қазір қолжетімсіз, кейінірек қайталап көріңіз.",
              "en": "The model is unavailable right now, please try again later."},
    "rate": {"ru": "Слишком много сообщений за час с одного адреса. Попробуйте чуть позже.",
             "kk": "Бір мекенжайдан сағатына хабарлама тым көп. Кейінірек қайталап көріңіз.",
             "en": "Too many messages from one address this hour. Please try again a bit later."},
}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def _rate_limited(ip: str) -> bool:
    if not RATE_PER_HOUR:
        return False
    now = time.time()
    with _hits_lock:
        q = _hits[ip]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= RATE_PER_HOUR:
            return True
        q.append(now)
        return False


@app.on_event("startup")
def _log_available_models() -> None:
    """Deployment diagnostics: which models this API key can reach from here (the key itself is never logged)."""
    try:
        ids = sorted(m.id for m in _llm.client.models.list())
        log.warning("model API reachable; configured model %s %s; available: %s", _llm.model,
                    "FOUND" if _llm.model in ids else "MISSING", ", ".join(ids))
    except Exception as e:  # diagnostics only: never block startup
        log.warning("model list unavailable: %s: %s", type(e).__name__, str(e)[:300])


@app.get("/api/health")
def health():
    """Cheap liveness check for the host and the keep-alive job: no model call."""
    return {"ok": True}


@app.post("/api/chat")
def chat(
    request: Request,
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
    if len(message) > MAX_MESSAGE:
        raise HTTPException(413, "message too long")
    lang_key = lang if lang in ("ru", "kk", "en") else "ru"
    if _rate_limited(_client_ip(request)):
        return {"session_id": session_id, "reply": LIMIT_REPLIES["rate"][lang_key], "files": [], "order": None}
    session_id, agent, lock = _get_session(session_id, customer_id, lang)
    with lock:  # one turn at a time per conversation
        content = _with_language_hint(_user_content(agent, message.strip(), file, data), lang)
        history_len = len(agent.messages)
        try:
            reply = agent.ask(content)
        except BudgetExceeded:
            del agent.messages[history_len:]  # roll back the unfinished turn so the session stays valid
            return {"session_id": session_id, "reply": LIMIT_REPLIES["budget"][lang_key], "files": [], "order": None}
        except (APIError, KeyError) as e:  # model API unreachable/refused, or no API key configured
            del agent.messages[history_len:]
            status = getattr(e, "status_code", None)
            detail = f"{type(e).__name__}{f' {status}' if status else ''}"
            log.error("model call failed: %s: %s", detail, str(e)[:500])
            return {"session_id": session_id, "files": [], "order": None,
                    "reply": f"{LIMIT_REPLIES['model'][lang_key]} ({detail})"}
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
