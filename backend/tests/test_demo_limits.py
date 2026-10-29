"""Tests for the public-demo safeguards (synthetic data only, no network/model calls)."""

import hashlib
import json
import time
from collections import OrderedDict, defaultdict, deque
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import medina.agent
import medina.api as api
from medina.api import LIMIT_REPLIES, MAX_MESSAGE
from medina.llm import BudgetExceeded, LLM


def _boom_client():
    """Object whose every attribute access fails loudly (proves no API call)."""

    class _Boom:
        def __getattr__(self, name):
            raise AssertionError(f"model client must not be used (accessed {name!r})")

    return _Boom()


def _write_usage(tmp_path, usd_values):
    usage_log = tmp_path / "usage.jsonl"
    usage_log.write_text(
        "".join(json.dumps({"usd": v}) + "\n" for v in usd_values), encoding="utf-8"
    )
    return usage_log


def _cache_key(llm, messages, tools=None):
    payload = {"model": llm.model, "messages": messages, "reasoning_effort": llm.reasoning_effort}
    if tools:
        payload["tools"] = tools
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest(), payload


def _valid_customer_id():
    from data_access.synthetic import default_source

    return default_source().customers()[0].customer_id


# 1. Health check.
def test_health():
    client = TestClient(api.app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# 2. Spend cap raises before any API call.
def test_spend_cap_raises_without_api_call(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDINA_MAX_SPEND_USD", "1")
    llm = LLM(cache_dir=tmp_path / "cache")
    llm.usage_log = _write_usage(tmp_path, [2.0])
    llm._client = _boom_client()
    with pytest.raises(BudgetExceeded):
        llm.chat([{"role": "user", "content": "x"}])


# 3. Cache is still served over the cap.
def test_cache_served_over_cap(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDINA_MAX_SPEND_USD", "1")
    llm = LLM(cache_dir=tmp_path / "cache")
    llm.usage_log = _write_usage(tmp_path, [2.0])
    llm._client = _boom_client()
    messages = [{"role": "user", "content": "x"}]
    key, payload = _cache_key(llm, messages)
    llm.cache_dir.mkdir(parents=True, exist_ok=True)
    (llm.cache_dir / f"{key}.json").write_text(
        json.dumps(
            {"payload": payload, "message": {"role": "assistant", "content": "cached"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert llm.chat(messages) == {"role": "assistant", "content": "cached"}


# 4. Cap disabled -> the spend check does not raise (stubbed client).
@pytest.mark.parametrize("env_value", ["unset", "0"])
def test_cap_disabled_allows_call(monkeypatch, tmp_path, env_value):
    if env_value == "unset":
        monkeypatch.delenv("MEDINA_MAX_SPEND_USD", raising=False)
    else:
        monkeypatch.setenv("MEDINA_MAX_SPEND_USD", "0")
    llm = LLM(cache_dir=tmp_path / "cache")
    llm.usage_log = tmp_path / "usage.jsonl"

    class _Message:
        def model_dump(self, exclude_none=True):  # noqa: ARG002
            return {"role": "assistant", "content": "hi"}

    fake_resp = SimpleNamespace(choices=[SimpleNamespace(message=_Message())], usage=None)
    fake_completions = SimpleNamespace(create=lambda **kwargs: fake_resp)
    fake_chat = SimpleNamespace(completions=fake_completions)
    llm._client = SimpleNamespace(chat=fake_chat)

    assert llm.chat([{"role": "user", "content": "x"}]) == {
        "role": "assistant",
        "content": "hi",
    }


# 5. Rate limiter bookkeeping.
def test_rate_limited(monkeypatch):
    monkeypatch.setattr(api, "RATE_PER_HOUR", 2)
    monkeypatch.setattr(api, "_hits", defaultdict(deque))
    assert api._rate_limited("1.1.1.1") is False
    assert api._rate_limited("1.1.1.1") is False
    assert api._rate_limited("1.1.1.1") is True
    assert api._rate_limited("2.2.2.2") is False

    monkeypatch.setattr(api, "RATE_PER_HOUR", 0)
    assert api._rate_limited("1.1.1.1") is False
    assert api._rate_limited("1.1.1.1") is False


# 6. Client IP extraction.
def test_client_ip():
    req_fwd = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"},
        client=SimpleNamespace(host="9.9.9.9"),
    )
    assert api._client_ip(req_fwd) == "1.2.3.4"
    req_direct = SimpleNamespace(headers={}, client=SimpleNamespace(host="9.9.9.9"))
    assert api._client_ip(req_direct) == "9.9.9.9"


def _limited_client(monkeypatch, ip):
    """TestClient with RATE_PER_HOUR=1 and `ip` already over the limit."""
    monkeypatch.setattr(api, "RATE_PER_HOUR", 1)
    monkeypatch.setattr(api, "_hits", defaultdict(deque))
    api._hits[ip].append(time.time())
    # Prove no agent/model call happens even if the guard regresses.
    monkeypatch.setattr(
        medina.agent.Agent,
        "ask",
        lambda self, content: (_ for _ in ()).throw(
            AssertionError("agent must not be called when rate limited")
        ),
    )
    return TestClient(api.app)


# 7. /api/chat over the rate limit (en + unknown-lang fallback to ru).
def test_chat_over_rate_limit_en(monkeypatch):
    ip = "10.20.30.40"
    client = _limited_client(monkeypatch, ip)
    resp = client.post(
        "/api/chat",
        data={"customer_id": _valid_customer_id(), "message": "hello", "lang": "en"},
        headers={"X-Forwarded-For": ip},
    )
    assert resp.status_code == 200
    assert resp.json()["reply"] == LIMIT_REPLIES["rate"]["en"]


def test_chat_over_rate_limit_unknown_lang_falls_back_to_ru(monkeypatch):
    ip = "10.20.30.41"
    client = _limited_client(monkeypatch, ip)
    resp = client.post(
        "/api/chat",
        data={"customer_id": _valid_customer_id(), "message": "hello", "lang": "xx"},
        headers={"X-Forwarded-For": ip},
    )
    assert resp.status_code == 200
    assert resp.json()["reply"] == LIMIT_REPLIES["rate"]["ru"]


# 8. /api/chat over MAX_MESSAGE -> 413.
def test_chat_message_too_long(monkeypatch):
    monkeypatch.setattr(api, "RATE_PER_HOUR", 0)
    monkeypatch.setattr(api, "_hits", defaultdict(deque))
    client = TestClient(api.app)
    resp = client.post(
        "/api/chat",
        data={
            "customer_id": _valid_customer_id(),
            "message": "x" * (MAX_MESSAGE + 1),
            "lang": "ru",
        },
    )
    assert resp.status_code == 413


# 9. /api/chat rolls the session back on BudgetExceeded.
def test_chat_budget_rollback(monkeypatch):
    monkeypatch.setattr(api, "RATE_PER_HOUR", 0)
    monkeypatch.setattr(api, "_hits", defaultdict(deque))
    monkeypatch.setattr(api, "_sessions", OrderedDict())

    def fake_ask(self, content):
        self.messages.append({"role": "user", "content": content})
        self.messages.append({"role": "assistant", "content": "partial"})
        raise BudgetExceeded("cap")

    monkeypatch.setattr(medina.agent.Agent, "ask", fake_ask)
    client = TestClient(api.app)
    resp = client.post(
        "/api/chat",
        data={"customer_id": _valid_customer_id(), "message": "hello", "lang": "ru"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == LIMIT_REPLIES["budget"]["ru"]
    session = api._sessions[body["session_id"]][0]
    # Fresh session: only the system message remains after the rollback.
    assert len(session.messages) == 1
