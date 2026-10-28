"""Meta Model API client (OpenAI-compatible Chat Completions) with a disk cache and cost log.

Cache key = hash of (model, messages, tools, reasoning_effort), so replaying a conversation
during development costs nothing. Every real call is appended to .cache/usage.jsonl.
"""

import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# USD per 1M tokens (dev.meta.ai pricing, 2026-10).
PRICES = {
    "standard": {"input": 1.25, "cached": 0.15, "output": 4.25},
    "contributor": {"input": 0.10, "cached": 0.002, "output": 0.20},
}

ROOT = Path(__file__).resolve().parents[2]


class LLM:
    def __init__(self, model: str | None = None, reasoning_effort: str = "low",
                 cache_dir: Path | None = None, use_cache: bool = True):
        self.model = model or os.environ.get("META_MODEL", "muse-spark-1.3")
        self.reasoning_effort = reasoning_effort
        self.cache_dir = cache_dir or ROOT / os.environ.get("MEDINA_CACHE_DIR", ".cache/llm")
        self.use_cache = use_cache
        self.usage_log = ROOT / ".cache" / "usage.jsonl"
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                base_url=os.environ.get("META_BASE_URL", "https://api.meta.ai/v1"),
                api_key=os.environ["META_API_KEY"],
                timeout=180,
            )
        return self._client

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Return the assistant message as a plain dict (role, content, tool_calls)."""
        payload = {"model": self.model, "messages": messages, "reasoning_effort": self.reasoning_effort}
        if tools:
            payload["tools"] = tools
        key = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        cache_file = self.cache_dir / f"{key}.json"
        if self.use_cache and cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))["message"]

        started = time.time()
        resp = self.client.chat.completions.create(**payload)
        msg = resp.choices[0].message.model_dump(exclude_none=True)
        msg = {k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")}
        self._log_usage(resp, time.time() - started)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"payload": payload, "message": msg}, ensure_ascii=False),
                              encoding="utf-8")
        return msg

    def _log_usage(self, resp, seconds: float) -> None:
        u = resp.usage
        if u is None:
            return
        cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        tier = PRICES["contributor" if self.model.endswith("-contributor") else "standard"]
        cost = ((u.prompt_tokens - cached) * tier["input"] + cached * tier["cached"]
                + u.completion_tokens * tier["output"]) / 1e6
        self.usage_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.usage_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": self.model,
                "prompt": u.prompt_tokens, "cached": cached, "completion": u.completion_tokens,
                "usd": round(cost, 5), "seconds": round(seconds, 1),
            }) + "\n")


def total_spend(usage_log: Path = ROOT / ".cache" / "usage.jsonl") -> float:
    if not usage_log.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in usage_log.read_text(encoding="utf-8").splitlines() if line)
