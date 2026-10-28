# Medina — order assistant for a pharmaceutical distributor's B2B portal

Medina is a chat assistant embedded in a pharmaceutical distributor's B2B ordering portal.
Pharmacies and clinics paste messy orders (free text in Russian/Kazakh with typos, photos of
handwritten lists, Excel files with arbitrary columns); Medina matches lines to the catalog,
checks stock, pack multiples, prescription status and customer debt, proposes in-stock analogs,
and produces a file in the portal's strict order-upload format. A human always confirms the order.

## Hard rules

- **No real data.** Everything in this repo is synthetic. Never add real company names, addresses,
  customer names, internal system names, ERP table/field names or credentials. Describe the
  source system only generically ("the distributor's ERP export").
- Secrets live only in `.env` (git-ignored). See `.env.example`.
- Code, comments, docs: English. Medina's user-facing replies: Russian or Kazakh (match the user).
- Medina never gives medical advice or treatment recommendations — only product, INN, form,
  strength, availability, expiry, pack multiple.
- Medina never places an order itself.
- Meta API budget is tight: cache model responses (`.cache/`), use small eval subsets while
  developing, full eval runs at most 3 times.

## Layout

- `data/` — deterministic synthetic data generator (`generate.py`, seeded) and output in `data/synthetic/`.
  The schema mirrors a typical ERP → portal batch export: products, batches per branch, customers, order history.
- `data_access/` — `DataSource` protocol + synthetic implementation + catalog search (fuzzy, translit, EAN).
- `backend/medina/` — tools (pure functions over `DataSource`), LLM client with disk cache, agent loop, prompts, CLI, API.
- `widget/` — single-file embeddable chat widget (Shadow DOM). `demo/` — static mock portal page.
- `integration/prestashop/` — sketch of a thin PrestaShop module that embeds the widget.
- `evals/` — dirty orders with gold answers, runner and metrics.

## Domain notes

- Product code = 18-digit material number (synthetic range `1000000000000xxxxx`).
- Portal order upload: `.xls`/`.csv` with exactly 3 columns `Штрихкод | Код товара | Количество`, all values as text.
- `order_multiple` — quantity must be a multiple of it; round up and explain.

## Commands

- `uv sync` — install
- `uv run pytest` — tests
- `uv run python -m data.generate` — regenerate synthetic data
- `uv run python -m medina.cli` — console agent

## LLM

Meta Model API (OpenAI-compatible), `base_url=https://api.meta.ai/v1`, model `muse-spark-1.3`, key `META_API_KEY`.
