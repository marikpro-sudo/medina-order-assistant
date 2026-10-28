"""Runner and metrics tests (no LLM calls; hand-built predictions)."""

from pathlib import Path

from data_access.synthetic import default_source
from evals.run import (
    align,
    baseline_line,
    load_cases,
    main,
    markdown_summary,
    score_case,
    summarize,
)

def _pick(pred):
    # Real products: scoring checks quantities against the chosen product's pack multiple.
    return next(p.material_id for p in default_source().products() if pred(p))


MID_A = _pick(lambda p: 10 % p.order_multiple == 0)
MID_B = _pick(lambda p: p.material_id != MID_A)
MID_C = _pick(lambda p: 20 % p.order_multiple == 0 and p.material_id not in (MID_A, MID_B))


def _order_case():
    return {
        "id": "text_ru_900", "kind": "text_ru", "customer_id": "C100001",
        "message": "test", "attachment": None, "content_type": None,
        "gold": [
            {"source": "nurofen 200 mg tab 10", "expect": "found",
             "material_id": MID_A, "acceptable": [MID_A], "gold_qty": 10},
            {"source": "bakhily 5 pcs", "expect": "unrecognized",
             "material_id": None, "acceptable": [], "gold_qty": 0},
            {"source": "panadol 500 mg tab 19", "expect": "rounded",
             "material_id": MID_C, "acceptable": [MID_C], "gold_qty": 20},
        ],
        "gold_errors": [],
    }


def _perfect_prediction():
    return [
        {"source": "nurofen 200 mg tab 10", "material_id": MID_A, "qty": 10, "status": "found"},
        {"source": "bakhily 5 pcs", "material_id": None, "qty": 0, "status": "unrecognized"},
        {"source": "panadol 500 mg tab 19", "material_id": MID_C, "qty": 20, "status": "rounded"},
    ]


def test_perfect_prediction_scores_one():
    scores = score_case(_order_case(), _perfect_prediction())
    assert scores["line_accuracy"] == 1.0
    assert scores["status_accuracy"] == 1.0
    assert scores["multiple_fix_rate"] == 1.0


def test_wrong_material_lowers_line_accuracy():
    pred = _perfect_prediction()
    pred[0] = dict(pred[0], material_id=MID_B)
    scores = score_case(_order_case(), pred)
    assert scores["line_accuracy"] == 2 / 3


def test_unrecognized_counts_as_correct_with_status():
    pred = [
        {"source": "nurofen 200 mg tab 10", "material_id": MID_A, "qty": 10, "status": "found"},
        {"source": "bakhily 5 pcs", "material_id": None, "qty": 0, "status": "unrecognized"},
        {"source": "panadol 500 mg tab 19", "material_id": "wrong", "qty": 20, "status": "rounded"},
    ]
    scores = score_case(_order_case(), pred)
    assert scores["line_accuracy"] == 2 / 3  # only the rounded line is wrong


def test_unrecognized_counts_as_correct_with_null_material():
    pred = _perfect_prediction()
    pred[1] = {"source": "bakhily 5 pcs", "material_id": None, "qty": 0, "status": "found"}
    scores = score_case(_order_case(), pred)
    assert scores["line_accuracy"] == 1.0


def test_rounded_wrong_qty_misses_multiple_fix_rate():
    pred = _perfect_prediction()
    pred[2] = dict(pred[2], qty=19)
    scores = score_case(_order_case(), pred)
    assert scores["multiple_fix_rate"] == 0.0
    # the material is still right, so line accuracy is unaffected
    assert scores["line_accuracy"] == 1.0


def test_align_fuzzy_when_counts_differ():
    gold = [
        {"source": "nurofen 200 mg tablets 10", "expect": "found",
         "material_id": MID_A, "acceptable": [MID_A], "gold_qty": 10},
        {"source": "aspirin 100 mg tablets 5", "expect": "found",
         "material_id": MID_B, "acceptable": [MID_B], "gold_qty": 5},
    ]
    pred = [
        {"source": "nurofen 200 mg tablets 10", "material_id": MID_A, "qty": 10, "status": "found"},
        {"source": "completely unrelated line here", "material_id": "zzz", "qty": 1, "status": "found"},
        {"source": "aspirin 100 mg tablets 5", "material_id": MID_B, "qty": 5, "status": "found"},
    ]
    pairs = align(pred, gold)
    assert [p["material_id"] for p, _ in pairs] == [MID_A, MID_B]
    case = {"id": "x", "kind": "text_ru", "customer_id": "C100001",
            "message": "", "attachment": None, "content_type": None,
            "gold": gold, "gold_errors": []}
    assert score_case(case, pred)["line_accuracy"] == 1.0


def test_align_positional_when_counts_match():
    gold = [{"source": "aaa bbb"}, {"source": "ccc ddd"}]
    pred = [{"source": "x"}, {"source": "y"}]
    pairs = align(pred, gold)
    assert pairs == [(pred[0], gold[0]), (pred[1], gold[1])]


def test_portal_file_scoring():
    case = {"id": "portal_file_900", "kind": "portal_file", "customer_id": "C100001",
            "message": "", "attachment": None, "content_type": None,
            "gold": [], "gold_errors": [{"row": 2, "code": "bad_qty"}, {"row": 3, "code": "duplicate"}]}
    full = [{"row": 2, "code": "bad_qty", "message": "m"}, {"row": 3, "code": "duplicate", "message": "m"}]
    assert score_case(case, full)["upload_error_explained"] == 1.0
    partial = [{"row": 2, "code": "bad_qty", "message": "m"}, {"row": 9, "code": "not_text", "message": "m"}]
    assert score_case(case, partial)["upload_error_explained"] == 0.5
    assert score_case(case, None)["upload_error_explained"] == 0.0


def test_baseline_line_exact_substring_and_gibberish():
    products = default_source().products()
    target = next(p for p in products if len(p.inn) >= 4)
    found = baseline_line(target.inn, products)
    assert found is not None
    match = default_source().get_product(found)
    assert target.inn.casefold() in match.name_short.casefold() \
        or target.inn.casefold() in match.inn.casefold()
    assert baseline_line("zzxqwv 10", products) is None
    assert baseline_line("а б", products) is None


def test_summarize_aggregates():
    case = _order_case()
    good = {**score_case(case, _perfect_prediction()), "seconds": 2.0, "usd": 0.01}
    bad_pred = [dict(p, material_id="wrong", status="found") for p in _perfect_prediction()]
    bad = {**score_case(case, bad_pred), "seconds": 4.0, "usd": 0.03}
    summary = summarize([good, bad])
    assert summary["n_cases"] == 2
    assert summary["line_total"] == 6
    assert summary["line_accuracy"] == 0.5
    assert summary["usd_total"] == 0.04
    assert summary["usd_per_case"] == 0.02
    assert summary["seconds_per_case"] == 3.0
    assert summary["by_kind"]["text_ru"]["cases"] == 2
    text = markdown_summary(summary)
    assert "baseline" in text and "text_ru" in text


def test_main_no_llm_offline(tmp_path, monkeypatch, capsys):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    out = tmp_path / "results"
    main(["--no-llm", "--limit", "5", "--out", str(out)])
    summaries = list(out.glob("*_summary.json"))
    assert len(summaries) == 1
    assert "baseline" in capsys.readouterr().out


def test_load_cases_default_shape(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    cases = load_cases("evals/cases/cases.jsonl")
    assert len(cases) == 100
    assert all({"id", "kind", "gold", "gold_errors"} <= set(c) for c in cases)
