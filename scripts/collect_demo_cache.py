"""Copies cached model answers for the demo customer into demo_cache/, which ships in the deploy image.

Judges clicking the demo scenarios get instant answers at no API cost; anything else calls the model.
Only entries whose system prompt matches the current prompt are kept, so stale answers never ship.
"""

import json
import shutil
from pathlib import Path

from data_access.synthetic import default_source
from medina.agent import UI_LANGUAGES, Agent
from medina.llm import LLM, ROOT

DEMO_CUSTOMER = "C100004"
SRC = ROOT / ".cache" / "llm"
DST = ROOT / "demo_cache"


def main() -> None:
    prompts = {Agent(default_source(), DEMO_CUSTOMER, LLM(), ROOT / ".cache" / "files", ui_lang=lang).messages[0]["content"]
               for lang in UI_LANGUAGES}
    shutil.rmtree(DST, ignore_errors=True)
    DST.mkdir()
    kept = 0
    for f in SRC.glob("*.json"):
        payload = json.loads(f.read_text(encoding="utf-8"))["payload"]
        if payload["messages"][0]["content"] in prompts:
            shutil.copy2(f, DST / f.name)
            kept += 1
    size = sum(p.stat().st_size for p in DST.iterdir()) / 1e6
    print(f"kept {kept} cached answers, {size:.1f} MB")


if __name__ == "__main__":
    main()
