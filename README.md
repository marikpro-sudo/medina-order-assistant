# Medina — AI order assistant for a pharmaceutical distributor's B2B portal

Medina is a chat widget for a B2B pharma ordering portal. Pharmacy staff paste orders the way they
actually have them — a message with typos in Russian or Kazakh, a photo of a handwritten list, an Excel
file in their own layout — and Medina turns them into a validated file in the portal's strict
order-upload format. It finds in-stock analogs for missing items, rounds quantities to pack multiples,
flags prescription items, short expiry and overdue debt *before* upload, and explains why a file would be
rejected row by row. A human always confirms; Medina never places an order or gives medical advice.

Meta Global AI Developer Hackathon · Track: **Startups** · Problem statement: **Build for Your World** ·
also a fit for **Best Agentic Use-Case**: a multi-step Muse Spark agent with 10 tools that takes an order from
raw input to a validated upload file. Everything here was built during the hackathon (see the last section).

## Demo video (3 min)

[![Medina demo video](https://img.youtube.com/vi/yqW_9d5NMjA/maxresdefault.jpg)](https://youtu.be/yqW_9d5NMjA)

▶ **https://youtu.be/yqW_9d5NMjA** — recorded from the running app on the mock portal ([`demo/`](demo/)) with
synthetic data; model answers are replayed from the response cache, so waiting time is cut (real answers take
5–16 s). The video is built from code in [`video/`](video/) (Playwright recording + Remotion).

## Live demo

**https://medina-demo.onrender.com/demo/** — the mock portal with Medina (pick a customer at the top; the ones
marked «ДЗ» have overdue debt; `?lang=en` for the English UI). Free hosting: the first visit after a quiet spell may
take up to a minute.

The example cards in the widget answer from cached Muse Spark responses. Free-form requests call the model live;
at the time of submission Meta Model API returns `404 model_not_found` for calls from cloud hosts (a known issue
Meta is investigating — the same key works from a local machine), so if Medina says live calls are unavailable,
use the cards or run the project locally (below). The public demo has a spend cap and a per-IP rate limit.

## The problem

A distributor with ~7,000 SKUs serves thousands of pharmacies and clinics through a B2B portal. The portal's
order upload accepts only a file with exactly three text columns — `Штрихкод | Код товара | Количество`.
Real orders don't look like that:

1. Orders arrive as messages, photos of handwritten lists, and Excel files with other columns, by brand or
   by INN, with typos, in Russian and Kazakh. Someone retypes them line by line.
2. One bad row fails the whole upload with a generic "Ошибка загрузки файла" — no row, no reason.
3. Missing items get analogs only manually, one at a time; search by INN for an out-of-stock item returns nothing.
4. Pack multiples, prescription status, stock in the customer's branch and overdue debt surface only late.
5. There are no reorder suggestions — "contact your manager".

## What Medina does

| Input | Medina |
|---|---|
| Free text, ru/kk, typos, brands or INNs | matches each line to the catalog, checks stock in the customer's branch |
| Photo of a handwritten list | reads it with Muse Spark vision, then the same pipeline |
| Excel/CSV in any layout | detects header and columns (ru/kk/en, by keywords and content), extracts lines |
| A file for the portal that fails | explains every problem by row and offers a corrected file |
| "Что дозаказать к сезону простуд?" | suggestions from the customer's history and distributor-wide seasonality, with a reason each |

The result is a table — source line → matched product → status (✓ found / ⇄ analog / ↻ rounded to pack multiple /
⚠ clarify / ✗ not recognized) → quantity → expiry of the batch — and a one-click `.xls` that the existing
order upload accepts unchanged.

## Architecture

```
portal page ── <script src="medina.js" data-token=…>   (Shadow DOM widget, no framework)
                    │  POST /api/chat (text | photo | spreadsheet)
                    ▼
            FastAPI  ──►  Agent loop (tool calling)  ──►  Muse Spark (Meta Model API, OpenAI-compatible)
                    │            │
                    │            ▼
                    │     Tools: search_products · check_lines · find_analogs · get_batches
                    │            get_customer_status · read_order_file · validate_upload_file
                    │            suggest_reorder · present_order · build_upload_file
                    ▼            │
            DataSource protocol ◄┘   synthetic implementation (this repo) | production adapter (below)
```

- **Model.** `muse-spark-1.3` through the Meta Model API (`https://api.meta.ai/v1`, Chat Completions,
  `tool_choice: auto`, image input as `image_url`). Search and line checks are batched, so a whole order takes
  3–5 model calls. Responses are cached on disk during development; every real call is logged with its cost.
- **Deterministic where possible.** Catalog search (typos, Latin transliteration, Kazakh letters, INN aliases,
  strength/form/pack scoring), pack-multiple rounding, analog tiers (same INN+form+strength → same INN+form →
  same ATC group, in-stock only, longest shelf life first), strict upload validation and spreadsheet parsing are
  plain Python with tests. The model reads messy input, decides, and explains.
- **Safety.** The customer comes from the portal session (signed token), never from model arguments.
  Medina only prepares a file; the portal's own upload stays the single path to an order. No dosing or
  treatment advice.

### Production adapter
`data_access.base.DataSource` is the only thing tools depend on. In production it reads what the portal
already receives from the distributor's ERP batch export — product cards, batches with expiry and stock per
branch, customer prices, customers with delivery points, credit and overdue debt, order history — either from
the portal database tables the import fills or from the intermediate export tables. Read-only. The PrestaShop
side is a thin module that renders one script tag; see [integration/prestashop](integration/prestashop/README.md).

## Repository

| Path | |
|---|---|
| `backend/medina/` | agent loop, LLM client with cache and cost log, tools, prompts, parsers, FastAPI |
| `data_access/` | `DataSource` protocol, synthetic implementation, catalog search |
| `data/` | deterministic synthetic data generator (400 products, 3 branches, 50 customers, 12-month seasonal history) |
| `widget/` | `medina.js` (single file, Shadow DOM, ru/kk) and its spec |
| `demo/` | mock portal page (catalog, cart, strict order upload) hosting the widget |
| `evals/` | 100 dirty orders with gold answers, runner and metrics |
| `integration/prestashop/` | module sketch |

All data is synthetic. No real company, customer, system or ERP field names are used.

## Run it

```bash
uv sync
cp .env.example .env          # set META_API_KEY
uv run pytest                 # unit tests, no API calls
uv run uvicorn medina.api:app --port 8000
# open http://localhost:8000/demo/  (pick a customer; the ones marked "ДЗ" have overdue debt)
```

Console: `uv run python -m medina.cli --customer C100004 --trace`.

## Evaluation

100 generated "dirty" orders with gold answers ([evals/SPEC.md](evals/SPEC.md)): 40 Russian and 15 Kazakh
messages with typos, brands instead of INNs and vice versa, non-multiple quantities; 20 spreadsheets in foreign
layouts; 10 portal files with injected errors; 10 photos of handwritten-style lists; 5 thirty-line orders —
744 order lines. One agent turn per case, `muse-spark-1.3`, reasoning effort `low`.

| Metric | Medina | Baseline |
|---|---|---|
| Line matched to an acceptable product (strict brand) | **95.0%** | 29.8% (portal substring search) |
| Same INN, form and strength as an acceptable product | **98.9%** | — |
| Out-of-stock lines with an in-stock analog proposed | **98.4%** | 0% (manual, one by one) |
| Non-multiple quantities corrected to the pack multiple | **97.1%** | 0% (whole upload fails) |
| Injected upload errors reported with the right row and reason | **100%** (20/20) | 0% ("Ошибка загрузки файла") |
| Lines that would break the strict upload, now fixed or explained | **95.0%** | 0% |
| Status (✓/⇄/↻/⚠/✗) correct | 92.3% | — |

By input: text ru 94.6% · text kk 96.6% · spreadsheets 95.2% · photos 91.1% · 30-line orders 96.0%.

**Time and cost.** Median 16 s per order and 32 s for a 30-line order (3–5 model calls), about $0.04 per order.
Retyping a 30-line order by hand — search each line, pick a batch, enter quantity, check multiples — takes
roughly 15–20 minutes (our estimate at ~30–40 s per line); with Medina it is the 32 s run plus a review of the table.

**Where it misses.** Most strict-brand misses are lines that name a generic whose brand equals the INN
("Амлодипин 10 мг", "Бромгексин 8 мг"): Medina picks another brand of the same INN, form and strength — hence
the 98.9% INN-level figure. Photos lose a few lines to handwriting. Gold answers are generated, so a few
"errors" are genuinely ambiguous lines.

Reproduce: `uv run python -m evals.generate_cases && uv run python -m evals.run` (`--no-llm` for the baseline
only, `--kinds`/`--ids`/`--limit` for subsets). Results of the full runs are in `evals/results/`
(run 2 replays cached model responses except where tool results changed; timings above are from run 1).
The whole project, including development and all eval runs, used about $5 of Meta Model API credit.

## How it was built

Built with Muse Code (Meta) as the coding agent for implementation tasks and Claude Code for planning,
architecture and review. The product itself runs entirely on Muse Spark via the Meta Model API.
Every task delegated to Muse Code and its review outcome is logged in [docs/muse-log.md](docs/muse-log.md);
Muse commits are tagged `[Muse Code]`, review fixes are separate `fix: … (review)` commits.

## Built during the hackathon

All code in this repository was written during the Meta Global AI Developer Hackathon,
2026-10-28 – 2026-11-04. The first commit (`8753298`) is the starting point; nothing was carried over from an
earlier codebase. Built during the hackathon: the Muse Spark agent and its tools, catalog search, text / Excel /
photo intake, the strict upload validator, reorder suggestions, the FastAPI backend, the embeddable widget
(ru/kk/en), the mock portal, the PrestaShop module sketch, the synthetic data generator, the 100-case evals and
the demo video pipeline. Everything shown in the demo video is this code running on synthetic data.
