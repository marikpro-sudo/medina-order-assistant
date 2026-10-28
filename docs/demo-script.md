# Medina demo script (3:00)

Shot-by-shot script for the hackathon video. Run the demo locally at http://localhost:8000/demo/.

- The mock portal is titled "ФармаОпт B2B · демо" on screen. All data is synthetic.
- The UI text is in Russian and Kazakh. The voice-over is in English.
- Medina never places orders and gives no medical advice. Say this once, in shot 4.

| Time | Screen | Action | Voice-over |
|---|---|---|---|
| 0:00–0:25 | Slide, then the portal tab "Загрузка заказа" | Show a slide with three input types: a text message, a photo of a handwritten list, and an Excel file in the pharmacy's own layout. Switch to the portal tab. Upload a broken .xls file (one bad row) and click upload. The red "Ошибка загрузки файла" appears. It has no row number. | Pharmacies send orders in every format. Messages. Photos of handwritten lists. Excel in their own layout. Russian and Kazakh, with typos. The portal accepts one format: an .xls with exactly three text columns. One bad row fails the whole file. The only error is generic. No row number. |
| 0:25–0:45 | Portal tab "Загрузка заказа", then the Medina widget | Click "Разобрать файл с Medina". The widget opens with the same file. Scroll through the list of problems by row: wrong check digit, barcode and code mismatch, "10 уп" instead of a number, numbers stored instead of text cells, pack multiple, duplicates. Pause on the corrected-file offer. | Medina reads the same file. It lists every problem, by row. A wrong check digit. A barcode that does not match the code. "10 уп" instead of a number. Numbers where the portal expects text. Wrong pack multiple. Duplicates. Then it offers a corrected file. |
| 0:45–1:10 | Medina widget, welcome screen, then the table view | Show the greeting "Здравствуйте! Я Medina — помогу собрать заказ" and the five capability cards. Click "Вставь список — соберу заказ". Paste a messy Russian list (prepared text, with typos). Show the table with statuses: ✓ found, ⇄ analog, ↻ rounded to pack multiple, ⚠ clarify, ✗ not recognized, plus quantity and expiry. Pause on the overdue-debt warning above the table for a customer marked "ДЗ". | Start with a greeting and five things Medina can do. Paste a messy list, with typos. Medina turns it into a table. Each line gets a status. Found. Analog. Rounded to the pack multiple. Needs clarification. Not recognized. Quantity and expiry are shown too. For a customer marked ДЗ, an overdue-debt warning appears above the table. |
| 1:10–1:35 | Medina widget, then the portal tab "Загрузка заказа" | Click "Скачать файл для Order upload". The .xls file downloads. Switch to the portal tab and upload the file. Show that it is accepted and the lines appear in the cart. | Medina gives you a file for the portal's own upload. Upload it. It is accepted. The lines go to the cart. The portal's upload is still the only way to order. Medina never places orders. A person always confirms. Medina gives no medical advice. |
| 1:35–1:55 | Medina widget | Click the paperclip and attach the prepared photo of a handwritten list (synthetic). Send it. Show that the lines are read and matched into the same table with statuses. | Have a handwritten list? Attach a photo with the paperclip. Medina reads it and matches each line the same way. |
| 1:55–2:15 | Medina widget, then the Kazakh UI | Switch the interface to KZ. Type the prepared question in Kazakh. Show the answer in Kazakh. | Switch the interface to Kazakh. Ask in Kazakh. Medina answers in Kazakh. |
| 2:15–2:40 | Medina widget, then the catalog | Type "Что дозаказать к сезону простуд?" Show the suggestions, each with a reason. Point out the reasons: the pharmacy's history and distributor-wide seasonality. Then open the catalog, find an out-of-stock item, and click "Показать аналоги". Medina opens with in-stock analogs: same INN, form, and strength first, sorted by shelf life. | Ask what to reorder for the cold season. Medina suggests items from this pharmacy's history and from distributor-wide seasonality. Each line has a reason. Out of stock? Click "Показать аналоги". Medina opens with in-stock analogs. The same INN, which is the active ingredient, comes first, then form and strength. Sorted by shelf life. |
| 2:40–3:00 | Slides: architecture, metrics, embed | Show the architecture slide: runs entirely on Muse Spark via the Meta Model API, with tool calling. Show "Built with Muse Code and Claude Code". Show the metrics slide with the literal placeholder `<metrics from README Evaluation section>`. Show the embed slide: one line, `<script src=".../medina.js">`, added to the existing PrestaShop portal through a thin module. | Medina runs entirely on Muse Spark, through the Meta Model API, using tool calling. We built it with Muse Code and Claude Code. Here are our results. To add it to an existing PrestaShop portal, you add one script line and a thin module. Thank you. |

## Before recording

- Start the local demo server and open http://localhost:8000/demo/. Confirm the portal title and that the UI is in Russian.
- Prepare synthetic inputs only:
  - a broken .xls with exactly three text columns and one bad row (shot 1);
  - the messy Russian list as text (shot 3);
  - a photo of a handwritten list (shot 5);
  - the Kazakh question as text (shot 6).
- Check the seed data: a customer marked "ДЗ" with overdue debt, an out-of-stock item with in-stock analogs, and the seasonal items for the cold-season question.
- Set the screen to 1080p, zoom the browser so the widget text is readable, hide bookmarks, close other tabs, and turn off notifications.
- Prepare four slides: the three input types with the problem, the architecture (Muse Spark, Meta Model API, tool calling, Muse Code, Claude Code), the metrics slide with the literal placeholder `<metrics from README Evaluation section>`, and the embed slide with `<script src=".../medina.js">`.
- Test the microphone in a quiet room. Read the voice-over aloud once per shot and check that each shot fits its time range.
- Rehearse once from start to finish and note the total time.

## Fallbacks

- Local server down or page does not load: restart the server, reload, and if it still fails, use a pre-recorded clip of that shot.
- Widget slow to respond: cut to the pre-recorded clip of the same step and keep the voice-over.
- Photo not read: use the pasted list from shot 3 and narrate that the photo flow works the same way.
- Kazakh answer slow: use the pre-recorded clip for shot 6.
- Upload not accepted in shot 4: download the .xls again from Medina and retry once. If it still fails, use the pre-recorded clip.
- Running over time: cut the out-of-stock analog part of shot 7 first, then shorten the voice-over in shot 2.
