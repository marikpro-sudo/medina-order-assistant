# Submission texts — Meta Global AI Developer Hackathon

Ready-to-paste answers for the Cerebral Valley submission form. Adjust lengths to the form's limits.

## Links
- Repository (public): https://github.com/marikpro-sudo/medina-order-assistant
- Demo video (3 min): https://youtu.be/yqW_9d5NMjA
- Live demo: https://medina-demo.onrender.com/demo/ (example cards answer from cached model responses; live calls from cloud hosts currently hit a known Meta Model API 404 issue — see README)

## Track and problem statement
- Track: **Startups**
- Problem statement: **Build for Your World**
- Bonus category to consider: **Best Agentic Use-Case** (multi-step tool-calling agent that turns messy orders into a validated upload file)

## Project name
Medina — AI order assistant for a pharmaceutical distributor's B2B portal

## Tagline (one line)
Turns messy pharmacy orders — typo-ridden messages in Russian or Kazakh, photos of handwritten lists, Excel in any layout — into a validated file the distributor's portal accepts, with in-stock analogs and problems flagged before upload.

## Short description
Pharmacies order from a distributor's B2B portal that accepts only a strict three-column upload file; one bad row fails the whole file with a generic error. Real orders arrive as messages, photos and spreadsheets in other layouts, by brand or by INN, with typos, in Russian and Kazakh — so staff retype them line by line.

Medina is a chat widget embedded in the portal with one script tag. A Muse Spark agent with tools matches every line to the catalog, checks stock in the customer's branch, pack multiples, prescription status, expiry and overdue debt, proposes in-stock analogs (same INN, form and strength first, longest shelf life), explains row by row why an existing file would be rejected, suggests seasonal reorders from history, and produces a file in the portal's exact format. A person always confirms; the portal's own upload stays the only way to order. Medina gives no medical advice — only product, INN, form, strength, availability, expiry and pack multiples.

## The problem (why it matters)
- Orders come in every format except the one the portal accepts; staff retype ~30-line orders by hand (15–20 minutes each).
- One wrong row fails the entire upload with "file upload error" and no row number.
- Out-of-stock items need analogs found manually, one by one.
- Pack multiples, prescription status, branch stock and overdue debt surface only after the fact.

## How we used Meta's models and tools
- **Muse Spark (`muse-spark-1.3`) via the Meta Model API** is the agent: Chat Completions with tool calling over 10 tools (catalog search, batches, analogs, line checks, customer status, spreadsheet reading, strict upload validation, seasonal reorder, structured order output, upload file builder).
- **Muse Spark vision** reads photos of handwritten order lists.
- **Multilingual**: replies in Russian, Kazakh or English, following the user and the interface language.
- **Muse Code** was the coding agent for implementation tasks (data generator, parsers, tests, eval generator and runner, widget, video composition); every task and its review is logged in `docs/muse-log.md`, and Muse commits are tagged `[Muse Code]`.
- Cost-aware design: batched tools (3–5 model calls per order), disk cache, ~$0.04 per order.

## What we built during the hackathon
Everything in the repository was built from scratch between Oct 28 and Nov 4, 2026 (first commit `8753298`): the agent and tools, catalog search, Excel/CSV/photo intake, strict upload validator, reorder suggestions, FastAPI backend, the embeddable widget (ru/kk/en), the mock portal, the PrestaShop module sketch, a synthetic data generator, 100-case evals and the demo video pipeline. All data is synthetic.

## Results (evals: 100 messy orders, 744 lines)
- 95.0% of lines matched to an acceptable product (portal substring search: 29.8%); 98.9% at INN + form + strength level
- 98.4% of out-of-stock lines got an in-stock analog
- 97.1% of non-multiple quantities corrected
- 100% of injected upload errors reported with the right row and reason (portal: 0%)
- Median 16 s per order, 32 s for a 30-line order

## Impact
Built for a real workflow the author knows first-hand: a pharmaceutical distributor serving thousands of pharmacies and clinics. Medina plugs into the existing portal without changing its catalog, cart or upload flow, so it can be adopted incrementally; the data-access layer has one interface to implement over the portal's existing ERP export.

## Tech stack
Python 3.12, FastAPI, Meta Model API (OpenAI-compatible SDK), rapidfuzz, openpyxl/xlrd/xlwt; vanilla JS widget in Shadow DOM; pytest (113 tests); Playwright + Remotion for the demo video.

## Team
Solo — list the representative's name and email in the form.
