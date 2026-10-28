"""Eval runner: replay dirty orders against the agent and score them (SPEC section 3).

Usage:
    uv run python -m evals.run [--limit N] [--kinds text_ru,sheet] [--ids a,b]
                                [--no-llm] [--llm-cache/--no-cache] [--out evals/results]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import tempfile
import time
from datetime import datetime
from pathlib import Path

from rapidfuzz import fuzz

from data_access.synthetic import default_source
from medina.agent import Agent
from medina.inputs import build_user_content
from medina.llm import LLM, total_spend

CASES_DIR = Path(__file__).resolve().parent / "cases"
DEFAULT_CASES = str(CASES_DIR / "cases.jsonl")
DEFAULT_OUT = "evals/results"

FUZZY_THRESHOLD = 60


def load_cases(path: str | Path) -> list[dict]:
    """Read one case record per line of JSONL."""
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def baseline_line(text: str, products) -> str | None:
    """Emulate the portal's catalog search for one order line.

    Case-insensitive substring of the line's first word (>= 4 letters) in
    ``name_short`` or ``inn``; the first match in catalog order wins.
    """
    match = _WORD_RE.search(text or "")
    if not match or len(match.group(0)) < 4:
        return None
    word = match.group(0).casefold()
    for product in products:
        if word in product.name_short.casefold() or word in product.inn.casefold():
            return product.material_id
    return None


def _source_of(line) -> str:
    if isinstance(line, dict):
        return str(line.get("source") or "")
    return ""


def align(pred_lines, gold_lines: list[dict]) -> list[tuple]:
    """Pair each gold line with a predicted line, in gold order.

    Positional pairing when counts match; otherwise greedy best fuzzy match
    of ``source`` text (rapidfuzz ratio >= 60). Unmatched gold lines pair
    with None; unmatched predictions are ignored.
    """
    preds = list(pred_lines or [])
    pairs: list[tuple] = []
    if len(preds) == len(gold_lines):
        return list(zip(preds, gold_lines))
    remaining = list(preds)
    for gold in gold_lines:
        best, best_score, best_idx = None, -1.0, -1
        for i, pred in enumerate(remaining):
            score = fuzz.ratio(_source_of(pred).casefold(), str(gold.get("source") or "").casefold())
            if score > best_score:
                best, best_score, best_idx = pred, score, i
        if best is not None and best_score >= FUZZY_THRESHOLD:
            pairs.append((best, gold))
            del remaining[best_idx]
        else:
            pairs.append((None, gold))
    return pairs


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_exact_code(source: str, ids: set[str], eans: set[str]) -> bool:
    """True when the line is already an exact catalog code/EAN (strict upload accepts it)."""
    digits = re.sub(r"\D", "", source or "")
    return bool(digits) and (digits in ids or digits in eans)


def _empty_scores(case: dict) -> dict:
    return {
        "id": case.get("id"), "kind": case.get("kind"),
        "line_correct": 0, "line_total": 0, "line_accuracy": None,
        "baseline_correct": 0, "baseline_total": 0, "baseline_accuracy": None,
        "status_correct": 0, "status_total": 0, "status_accuracy": None,
        "analog_correct": 0, "analog_total": 0, "analog_rate": None,
        "rounded_correct": 0, "rounded_total": 0, "multiple_fix_rate": None,
        "upload_detected": 0, "upload_total": 0, "upload_error_explained": None,
        "broken_fixed": 0, "broken_total": 0, "broken_lines_fixed_or_explained": None,
        "no_structured_output": True,
    }


def _rate(numerator: int, denominator: int):
    return numerator / denominator if denominator else None


def _score_order(case: dict, prediction) -> dict:
    products = default_source().products()
    ids = {p.material_id for p in products}
    eans = {p.ean13 for p in products}
    gold = case.get("gold", [])
    preds = prediction if isinstance(prediction, list) else []
    out = _empty_scores(case)
    out["no_structured_output"] = not prediction
    out["line_total"] = len(gold)
    out["baseline_total"] = len(gold)
    out["status_total"] = len(gold)
    for pred, line in align(preds, gold):
        expect = line.get("expect")
        acceptable = set(line.get("acceptable", []))
        mid = pred.get("material_id") or None if isinstance(pred, dict) else None
        status = pred.get("status") if isinstance(pred, dict) else None
        qty = _as_int(pred.get("qty")) if isinstance(pred, dict) else None
        gold_qty = line.get("gold_qty")
        if pred is None:  # no structured output for this line: nothing to credit
            line_ok = False
        elif expect == "unrecognized":
            line_ok = status == "unrecognized" or not mid
        else:
            line_ok = bool(mid) and mid in acceptable
        out["line_correct"] += line_ok
        status_ok = status == expect or (
            expect in ("found", "rounded") and status in ("found", "rounded")
            and qty is not None and qty == gold_qty
        )
        out["status_correct"] += status_ok
        if expect == "analog":
            out["analog_total"] += 1
            out["analog_correct"] += bool(mid) and mid in acceptable
        if expect == "rounded":
            out["rounded_total"] += 1
            out["rounded_correct"] += qty is not None and qty == gold_qty
        base_mid = baseline_line(str(line.get("source") or ""), products)
        if expect == "unrecognized":
            out["baseline_correct"] += not base_mid
        else:
            out["baseline_correct"] += bool(base_mid) and base_mid in acceptable
        if not _is_exact_code(str(line.get("source") or ""), ids, eans):
            out["broken_total"] += 1
            out["broken_fixed"] += line_ok or status_ok
    out["line_accuracy"] = _rate(out["line_correct"], out["line_total"])
    out["baseline_accuracy"] = _rate(out["baseline_correct"], out["baseline_total"])
    out["status_accuracy"] = _rate(out["status_correct"], out["status_total"])
    out["analog_rate"] = _rate(out["analog_correct"], out["analog_total"])
    out["multiple_fix_rate"] = _rate(out["rounded_correct"], out["rounded_total"])
    out["broken_lines_fixed_or_explained"] = _rate(out["broken_fixed"], out["broken_total"])
    return out


def _score_portal(case: dict, prediction) -> dict:
    out = _empty_scores(case)
    out["no_structured_output"] = prediction is None
    gold = {(e.get("row"), e.get("code")) for e in case.get("gold_errors", [])}
    probs = prediction if isinstance(prediction, list) else []
    pred = {(p.get("row"), p.get("code")) for p in probs if isinstance(p, dict)}
    out["upload_total"] = len(gold)
    out["upload_detected"] = len(gold & pred)
    out["upload_error_explained"] = _rate(out["upload_detected"], out["upload_total"])
    return out


def score_case(case: dict, prediction) -> dict:
    """Score one case. ``prediction`` is last_order lines for order kinds or
    validate_upload_file problems for portal_file; None means no output."""
    if case.get("kind") == "portal_file":
        return _score_portal(case, prediction)
    return _score_order(case, prediction)


def _summed(results: list[dict], num_key: str, den_key: str) -> tuple[int, int]:
    num = sum(r.get(num_key, 0) for r in results if r.get(den_key))
    den = sum(r.get(den_key, 0) for r in results)
    return num, den


def summarize(results: list[dict]) -> dict:
    """Micro-average per-case counters; medians for time, sums for cost."""
    summary: dict = {"n_cases": len(results)}
    summary["n_errors"] = sum(1 for r in results if r.get("error"))
    summary["no_structured_output"] = sum(1 for r in results if r.get("no_structured_output"))
    for num_key, den_key, rate_key in [
        ("line_correct", "line_total", "line_accuracy"),
        ("baseline_correct", "baseline_total", "baseline_accuracy"),
        ("status_correct", "status_total", "status_accuracy"),
        ("analog_correct", "analog_total", "analog_rate"),
        ("rounded_correct", "rounded_total", "multiple_fix_rate"),
        ("upload_detected", "upload_total", "upload_error_explained"),
        ("broken_fixed", "broken_total", "broken_lines_fixed_or_explained"),
    ]:
        num, den = _summed(results, num_key, den_key)
        summary[num_key] = num
        summary[den_key] = den
        summary[rate_key] = _rate(num, den)
    by_kind: dict[str, dict] = {}
    for r in results:
        kind = r.get("kind", "?")
        entry = by_kind.setdefault(kind, {"cases": 0, "line_correct": 0, "line_total": 0,
                                          "baseline_correct": 0, "baseline_total": 0})
        entry["cases"] += 1
        entry["line_correct"] += r.get("line_correct", 0)
        entry["line_total"] += r.get("line_total", 0)
        entry["baseline_correct"] += r.get("baseline_correct", 0)
        entry["baseline_total"] += r.get("baseline_total", 0)
    for entry in by_kind.values():
        entry["line_accuracy"] = _rate(entry["line_correct"], entry["line_total"])
        entry["baseline_accuracy"] = _rate(entry["baseline_correct"], entry["baseline_total"])
    summary["by_kind"] = dict(sorted(by_kind.items()))
    seconds = [r.get("seconds", 0.0) for r in results]
    summary["seconds_per_case"] = statistics.median(seconds) if seconds else None
    long_seconds = [r.get("seconds", 0.0) for r in results if r.get("kind") == "long"]
    summary["seconds_long"] = statistics.median(long_seconds) if long_seconds else None
    summary["usd_total"] = round(sum(r.get("usd", 0.0) for r in results), 5)
    summary["usd_per_case"] = summary["usd_total"] / len(results) if results else 0.0
    return summary


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def markdown_summary(summary: dict) -> str:
    """One markdown table plus headline metrics, printed by main()."""
    lines = [
        "# Eval summary",
        "",
        f"- cases: {summary['n_cases']} "
        f"(errors: {summary['n_errors']}, no structured output: {summary['no_structured_output']})",
        f"- line_accuracy: {_fmt(summary['line_accuracy'])} "
        f"(baseline {_fmt(summary['baseline_accuracy'])}, n={summary['line_total']})",
        f"- status_accuracy: {_fmt(summary['status_accuracy'])} (n={summary['status_total']})",
        f"- analog_rate: {_fmt(summary['analog_rate'])} (n={summary['analog_total']})",
        f"- multiple_fix_rate: {_fmt(summary['multiple_fix_rate'])} (n={summary['rounded_total']})",
        f"- upload_error_explained: {_fmt(summary['upload_error_explained'])} "
        f"(baseline 0.000, n={summary['upload_total']})",
        f"- broken_lines_fixed_or_explained: {_fmt(summary['broken_lines_fixed_or_explained'])} "
        f"(n={summary['broken_total']})",
        f"- seconds_per_case (median): {_fmt(summary['seconds_per_case'])}; "
        f"seconds_long (median): {_fmt(summary['seconds_long'])}",
        f"- usd_total: {_fmt(summary['usd_total'], 5)}; "
        f"usd_per_case: {_fmt(summary['usd_per_case'], 5)}",
        "",
        "| kind | cases | lines | line_accuracy | baseline_accuracy |",
        "|---|---|---|---|---|",
    ]
    for kind, entry in summary["by_kind"].items():
        lines.append(f"| {kind} | {entry['cases']} | {entry['line_total']} | "
                     f"{_fmt(entry['line_accuracy'])} | {_fmt(entry['baseline_accuracy'])} |")
    return "\n".join(lines)


def _content_type_for(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    return None


def _extract_prediction(case: dict, agent: Agent):
    if case.get("kind") == "portal_file":
        for call in reversed(agent.trace):
            if call.get("tool") == "validate_upload_file":
                result = call.get("result") or {}
                if isinstance(result, dict) and isinstance(result.get("problems"), list):
                    return result["problems"]
                return None
        return None
    return agent.tools.last_order


def run_case(case: dict, llm: LLM) -> dict:
    """Run one case through the agent. The only function that calls the model."""
    started = time.time()
    cost_before = total_spend()
    with tempfile.TemporaryDirectory(prefix="medina_eval_") as tmp:
        try:
            agent = Agent(default_source(), case["customer_id"], llm, Path(tmp))
            attachment = case.get("attachment")
            if attachment:
                data = (CASES_DIR / attachment).read_bytes()
                filename = Path(attachment).name
                content = build_user_content(agent, case.get("message", ""), filename,
                                             _content_type_for(filename), data)
            else:
                content = build_user_content(agent, case.get("message", ""))
            calls = 0
            original_chat = llm.chat

            def counting_chat(messages, tools=None):
                nonlocal calls
                calls += 1
                return original_chat(messages, tools)

            llm.chat = counting_chat
            try:
                agent.ask(content)
            finally:
                llm.chat = original_chat
            prediction = _extract_prediction(case, agent)
            scores = score_case(case, prediction)
            return {**scores, "seconds": time.time() - started, "model_calls": calls,
                    "usd": round(total_spend() - cost_before, 5), "prediction": prediction}
        except Exception as exc:  # one bad case must not stop the run
            return {**_empty_scores(case), "seconds": time.time() - started,
                    "model_calls": 0, "usd": 0.0, "prediction": None,
                    "error": f"{type(exc).__name__}: {exc}"}


AGENT_METRICS = ("line_accuracy", "status_accuracy", "analog_rate", "multiple_fix_rate",
                 "upload_error_explained", "broken_lines_fixed_or_explained")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Replay eval cases against the agent.")
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--kinds", default=None, help="comma-separated kinds to run")
    parser.add_argument("--ids", default=None, help="comma-separated case ids to run")
    parser.add_argument("--no-llm", action="store_true", help="baseline metrics only, offline")
    parser.add_argument("--llm-cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if args.kinds:
        wanted = {k.strip() for k in args.kinds.split(",") if k.strip()}
        cases = [c for c in cases if c.get("kind") in wanted]
    if args.ids:
        wanted_ids = {i.strip() for i in args.ids.split(",") if i.strip()}
        cases = [c for c in cases if c.get("id") in wanted_ids]
    if args.limit is not None:
        cases = cases[: args.limit]

    results = []
    if args.no_llm:
        for case in cases:
            started = time.time()
            try:
                scores = score_case(case, None)
                results.append({**scores, "seconds": time.time() - started,
                                "model_calls": 0, "usd": 0.0, "prediction": None})
            except Exception as exc:
                results.append({**_empty_scores(case), "seconds": time.time() - started,
                                "model_calls": 0, "usd": 0.0, "prediction": None,
                                "error": f"{type(exc).__name__}: {exc}"})
    else:
        llm = LLM(use_cache=args.llm_cache)
        for case in cases:
            try:
                results.append(run_case(case, llm))
            except Exception as exc:  # run_case already guards; last resort
                results.append({**_empty_scores(case), "seconds": 0.0,
                                "model_calls": 0, "usd": 0.0, "prediction": None,
                                "error": f"{type(exc).__name__}: {exc}"})

    summary = summarize(results)
    if args.no_llm:  # agent metrics are meaningless without a model run
        for key in AGENT_METRICS:
            summary[key] = None
        for entry in summary.get("by_kind", {}).values():
            entry["line_accuracy"] = None
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(out_dir / f"{stamp}.jsonl", "w", encoding="utf-8") as f:
        for record in results:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    with open(out_dir / f"{stamp}_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(markdown_summary(summary))


if __name__ == "__main__":
    main()
