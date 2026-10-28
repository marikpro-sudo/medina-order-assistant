# Evals — specification

Goal: measure Medina on realistic "dirty" orders against gold answers, cheaply and reproducibly.
All cases are generated deterministically from the synthetic catalog (`data/synthetic`).

## 1. Case generator — `evals/generate_cases.py`

`uv run python -m evals.generate_cases` (seed 7) writes `evals/cases/cases.jsonl` and attachments into
`evals/cases/files/`. Uses `data_access.synthetic.default_source()` and `data.inn_catalog.INN_GROUPS`.

100 cases:

| kind | n | input |
|---|---|---|
| `text_ru` | 40 | Russian message, 3–12 lines, typical pharmacy shorthand |
| `text_kk` | 15 | Kazakh message (greeting/connectives in Kazakh, units `қорап`, `дана`, `шт`) |
| `sheet` | 20 | `.xlsx`/`.xls`/`.csv` with foreign layouts (title rows, `№` column, other header names ru/kk/en, cp1251 `;` CSV, names instead of codes, some EAN-only) |
| `portal_file` | 10 | intended portal format with injected errors (see below) |
| `photo` | 10 | PNG of a handwritten-style list (see section 2) |
| `long` | 5 | Russian message with 30 lines (for timing) |

Customers: cycle through all 50; at least 10 cases use the 5 debtors.

### Line generation (text, sheet, photo, long)
Pick a gold product, then render its line text with one or more noise operators (rng):
- brand + strength + form shorthand ("нурофен 200 таб"), INN instead of brand ("ибупрофен 200 таб"),
  brand only when the brand has a single strength/form;
- typos: drop / swap / duplicate one letter in the name word (max 1 per word, only words ≥ 5 letters);
- Latin transliteration of the name (10% of lines);
- pack "№20", quantity forms: "10", "10 уп", "x10", "10шт", "- 10", Kazakh "10 қорап", "10 дана";
- line separators: newline, comma, ";".

Line scenarios and gold `expect`:
- `found` (≈60%): product in stock in the customer's branch, qty a multiple of `order_multiple`;
- `rounded` (≈15%): qty not a multiple → `gold_qty` = rounded up;
- `analog` (≈15%): product with zero stock in the customer's branch that has ≥ 1 in-stock product with
  the same INN + dosage-form family + strength → `acceptable` = those in-stock products;
- `unrecognized` (≈5%): non-catalog item ("бахилы", "маски медицинские", "шприц 5 мл") or gibberish;
- `clarify` (≈5%): INN only, without strength, where the catalog has several strengths → any product of that
  INN is acceptable, status should be `clarify`.

`acceptable` for `found`/`rounded`: the gold product plus products of the same brand, form and strength that
differ only in pack size **if the line text has no pack number**; and, when the line text uses the INN instead of
the brand, every product with the same INN, form family and strength.

### portal_file errors (1–3 per file, 5–15 rows, all other rows correct, text cells)
`not_text` (codes stored as numbers), `bad_ean` (wrong check digit), `bad_material_id` (17 digits or unknown),
`ean_code_mismatch`, `bad_qty` ("10 уп", "0", empty), `not_multiple`, `column_count` (extra name column),
`duplicate`. Gold lists `{row, code}` per injected error (row = 1-based file row, header is row 1).

### Case record (one JSON per line)
```json
{"id": "text_ru_007", "kind": "text_ru", "customer_id": "C100012", "message": "...",
 "attachment": "files/sheet_003.xlsx" | null, "content_type": "image/png" | null,
 "gold": [{"source": "нурафен 200 таб 7 уп", "expect": "rounded", "material_id": "1000…", "acceptable": ["1000…"], "gold_qty": 10}],
 "gold_errors": [{"row": 4, "code": "not_text"}]}
```

## 2. Photos — `evals/render_photo.py`
`render_list(lines: list[str], path, seed)` with Pillow: lined-paper background (off-white, light blue lines),
handwriting-like font (first available of `C:/Windows/Fonts/Inkfree.ttf`, `segoepr.ttf`, `segoesc.ttf`,
`/usr/share/fonts/**/DejaVuSans.ttf`), 26–32 px, per-line jitter ±3 px and rotation ±1.5°, whole image rotated
±2°, slight Gaussian blur and noise, 900 px wide, PNG.

## 3. Runner — `evals/run.py`
`uv run python -m evals.run [--limit N] [--kinds text_ru,sheet] [--ids a,b] [--no-llm]`

- For each case: fresh `Agent(default_source(), customer_id, LLM(), tmp files dir)`, input via
  `medina.inputs.build_user_content`, one `agent.ask(...)` turn. Record wall time, number of model calls,
  and cost (diff of `.cache/usage.jsonl` totals; cached calls cost 0).
- Prediction for order cases = `agent.tools.last_order` (from `present_order`); if None, the case scores 0 on
  line metrics and is counted in `no_structured_output`.
- Align predicted lines to gold by position; if counts differ, align by best fuzzy match of `source` text
  (rapidfuzz ratio ≥ 60).
- portal_file cases: prediction = the `problems` of the last `validate_upload_file` call in `agent.trace`.
- Baseline (no LLM, always computed): emulate the portal's catalog search — case-insensitive substring of the
  line's first word (≥ 4 letters) in `name_short` or `inn`; take the first match in catalog order.
  For portal files the baseline is "whole file fails, no row reported".
- Results: `evals/results/<timestamp>.jsonl` (per case) and `evals/results/<timestamp>_summary.json`,
  and print a markdown summary table.

### Metrics
- `line_accuracy`: lines whose predicted material ∈ `acceptable` (for `unrecognized`: predicted status
  unrecognized or material null) / all gold lines. Same for `baseline_accuracy`.
- `status_accuracy`: predicted status == expected status (`rounded` and `found` count as equal when qty matches).
- `analog_rate`: `analog` lines with an in-stock acceptable product / all `analog` lines.
- `multiple_fix_rate`: `rounded` lines with predicted qty == `gold_qty` / all `rounded` lines.
- `upload_error_explained`: injected portal-file errors detected with the right row and code / all injected errors
  (baseline 0: the portal reports only "Ошибка загрузки файла").
- `broken_lines_fixed_or_explained`: over text/sheet/photo/long cases, lines that the strict upload would reject
  (not exact catalog codes) and that Medina resolved or explained / all such lines.
- `seconds_per_case` (median) and `seconds_long` (median for `long`), `usd_total`, `usd_per_case`.
Per-kind breakdown of line_accuracy.
