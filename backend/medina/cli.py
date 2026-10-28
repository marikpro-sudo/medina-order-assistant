"""Console chat with Medina. Usage: uv run python -m medina.cli [--customer C100001] [--trace]"""

import argparse
import json
import sys

from data_access.synthetic import default_source
from medina.agent import Agent
from medina.llm import LLM, ROOT, total_spend


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--customer", default="C100001")
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="low")
    ap.add_argument("--trace", action="store_true", help="print tool calls")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()
    for stream in (sys.stdin, sys.stdout):  # Windows consoles default to a legacy code page
        stream.reconfigure(encoding="utf-8")

    llm = LLM(model=args.model, reasoning_effort=args.effort, use_cache=not args.no_cache)
    agent = Agent(default_source(), args.customer, llm, ROOT / ".cache" / "files")
    print(f"Medina · {agent.tools.customer.name} · model {llm.model}. Empty line + Ctrl+Z/D to exit.")
    while True:
        try:
            lines = []
            print("\n> ", end="", flush=True)
            while (line := input()) != "":
                lines.append(line)
        except EOFError:
            break
        if not lines:
            continue
        reply = agent.ask("\n".join(lines))
        if args.trace:
            for t in agent.trace:
                print(f"  [tool] {t['tool']}({t['args']}) -> {json.dumps(t['result'], ensure_ascii=False)[:300]}")
        print("\n" + reply)
    print(f"\nTotal API spend so far: ${total_spend():.3f}")


if __name__ == "__main__":
    main()
