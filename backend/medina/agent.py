"""Tool-calling agent loop over the Meta Model API."""

import json
from pathlib import Path

from data.schema import PLANTS
from data_access.base import DataSource
from medina.llm import LLM
from medina.tools.schemas import TOOL_METHODS, TOOL_SCHEMAS
from medina.tools.toolbox import Toolbox

PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"
MAX_STEPS = 10
UI_LANGUAGES = {"ru": "Russian", "kk": "Kazakh", "en": "English"}


class Agent:
    def __init__(self, ds: DataSource, customer_id: str, llm: LLM, files_dir: Path, ui_lang: str = "ru"):
        self.tools = Toolbox(ds, customer_id, files_dir)
        self.llm = llm
        c = self.tools.customer
        system = PROMPT_PATH.read_text(encoding="utf-8").format(
            today=ds.today().isoformat(), customer_name=c.name,
            branch=PLANTS.get(c.branch_plant, c.branch_plant),
            ui_language=UI_LANGUAGES.get(ui_lang, "Russian"))
        self.messages: list[dict] = [{"role": "system", "content": system}]
        self.trace: list[dict] = []  # tool calls of the last turn, for debugging and evals

    def ask(self, user_content: str | list) -> str:
        self._drop_old_images()
        self.tools.last_order = None
        self.messages.append({"role": "user", "content": user_content})
        self.trace = []
        for _ in range(MAX_STEPS):
            msg = self.llm.chat(self.messages, TOOL_SCHEMAS)
            self.messages.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content") or ""
            for call in calls:
                result = self._run_tool(call["function"]["name"], call["function"].get("arguments") or "{}")
                self.trace.append({"tool": call["function"]["name"],
                                   "args": call["function"].get("arguments"), "result": result})
                self.messages.append({"role": "tool", "tool_call_id": call["id"],
                                      "content": json.dumps(result, ensure_ascii=False)})
        return "Не удалось завершить обработку запроса. Попробуйте сформулировать короче."

    def _drop_old_images(self) -> None:
        """Images were already read in their turn; resending them every turn would multiply the cost."""
        for m in self.messages:
            if m["role"] == "user" and isinstance(m["content"], list):
                text = " ".join(p.get("text", "") for p in m["content"] if p.get("type") == "text")
                m["content"] = text + "\n[The photo was processed in the reply that follows.]"

    def _run_tool(self, name: str, raw_args: str) -> dict:
        method = TOOL_METHODS.get(name)
        if method is None:
            return {"error": f"unknown tool {name}"}
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError as e:
            return {"error": f"invalid JSON arguments: {e}"}
        try:
            return getattr(self.tools, method)(**args)
        except TypeError as e:
            return {"error": f"bad arguments: {e}"}
