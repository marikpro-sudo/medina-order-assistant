# Muse Code task log

Implementation tasks delegated to Muse Code (`muse exec`, model `muse-spark-1.3-contributor`) through the
`muse-coder` subagent. Each task gets a written spec with an acceptance check; Claude Code reviews the diff,
runs the checks and fixes what is needed.

Note: Muse's shell sandbox could not run commands on the development machine (Windows ACL error), so Muse
wrote the files and the acceptance checks were run by the subagent afterwards.

| # | Date | Task | Result | Review |
|---|---|---|---|---|
| 1 | 2026-10-29 | Deterministic synthetic data generator `data/generate.py` + tests `data/tests/test_generate.py` (400 products, batches by branch, 50 customers, 12-month seasonal history) | First run interrupted by a network error after writing the generator; second run reviewed it and wrote 10 tests. All passed. Commit `2de7b0e`. | Accepted with fixes: JSON written with `\n` line endings so output is byte-identical across OSes; return type annotation. |
| 2 | 2026-10-29 | Tests for catalog search and agent tools (`backend/tests/test_search.py`, `test_toolbox.py`), data-driven, no hardcoded ids | 39 tests, all passed on first run. Commit `a9d8420`. | Accepted as is. |
| 3 | 2026-10-29 | Chat widget `widget/medina.js` from `widget/SPEC.md` (Shadow DOM, states, markdown tables with status colors, welcome cards, file attach, persistence, ru/kk) | 802 lines, syntax and content checks passed. Commit `85fe932`. | Accepted with fixes after browser testing: protocol-relative links were allowed, URLs double-escaped, card titles 20px, table cells `nowrap` (1116px wide table), list-level horizontal scroll; added auto-wide panel for tables and `data-token`. |
| 4 | 2026-11-02 | Order table parser `backend/medina/parsers/order_table.py` (read cells with text/number type from .xlsx/.xls/.csv, header row and column detection by ru/kk/en keywords and by content, quantity parsing like "10 уп"/"5шт"/"10 қорап", total rows skipped) + `backend/tests/test_order_table.py`; `spreadsheet.read_rows` rebuilt on top of it | First run stopped by us before writing; second run wrote 3 files. 28 new tests. Commit `946e473` [Muse Code]. | Fixed in `2a6247e` (review): a test used Cyrillic inside a `b"..."` literal (SyntaxError, Muse could not run tests). Code accepted as is; `read_rows` now keeps empty rows so row numbers match Excel — demo upload adjusted to skip them. |

Tasks 1–3 predate the `[Muse Code]` commit tag convention; from task 4 on, Muse commits are tagged and review fixes are separate `fix: ... (review)` commits.
