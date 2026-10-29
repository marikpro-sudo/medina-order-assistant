# Medina widget — specification

Single file `widget/medina.js`, vanilla JS (ES2020), no dependencies, no build step. Target size < 40 KB.
Embedded with one line:

```html
<script src="https://host/medina.js" data-api="https://host" data-customer="C100001" data-lang="ru" defer></script>
```

| attribute | default | meaning |
|---|---|---|
| `data-api` | origin of the script URL | backend base URL |
| `data-customer` | required | customer id from the portal session |
| `data-point` | empty | delivery point id (optional, sent to backend) |
| `data-lang` | `ru` | `ru`, `kk` or `en` (initial UI language; unknown values fall back to `ru`) |
| `data-color` | `#0E7C66` | primary color |

The script also exposes `window.Medina = { open(), close(), send(text), setLang(lang), reset() }`.

## Isolation

- All DOM inside one host element `<div id="medina-root">` appended to `document.body`, with `attachShadow({mode: "open"})`.
- All CSS inside the shadow root; `:host { all: initial }`. CSS custom properties: `--m-primary`, `--m-bg`, `--m-text`, `--m-muted`, `--m-border`.
- Font: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`, 14px.
- z-index of host: 2147483000.
- No globals besides `window.Medina`. Wrap everything in an IIFE.

## States and layout

1. **Launcher** (panel closed): round button 60×60 px, fixed bottom 20px right 20px, primary color, white chat-bubble SVG icon,
   shadow. `aria-label` "Открыть Medina". Small red dot badge when there is an unread assistant reply.
2. **Panel open**: fixed right 20px bottom 90px, width 400px, height `min(640px, calc(100vh - 110px))`, radius 16px, shadow.
   - **Wide mode** ("развернуть"): width `min(760px, calc(100vw - 40px))`, height `calc(100vh - 110px)`.
   - **Mobile** (`max-width: 600px`): full screen (inset 0, radius 0); the launcher is hidden while open.
3. **Minimized** ("свернуть"): panel replaced by a pill bar 260×48 at the launcher position: "Medina · продолжить" — click restores.
   The launcher is hidden while minimized.

Header (primary background, white text): circle avatar with letter "M", title "Medina", subtitle (i18n `subtitle`),
then icon buttons: language toggle (cycles ru → kk → en → ru; shows the NEXT language code: `KZ` when ru, `EN` when kk, `RU` when en; `aria-label`/`title`: ru "Язык", kk "Тіл", en "Language"), new chat (↺), expand/restore (⤢ / ⤡), minimize (—), close (×).
All with `aria-label` and `title`. Esc key minimizes.

Body: scrollable message list. Footer: attachment chip row (when a file is selected), then input row:
paperclip button, auto-growing textarea (1–6 rows), send button (arrow SVG, disabled when empty and no file).
Below the input: small muted disclaimer (i18n `disclaimer`).

## Messages

- User: right-aligned bubble, primary-tinted background (`color-mix(in srgb, var(--m-primary) 12%, white)`). Shows attached file name as a chip.
- Assistant: left-aligned, light gray background, full width allowed for tables.
- System/error: centered muted text; errors get a "Повторить" button that resends the last user message.
- Typing indicator (three animated dots + i18n `typing`) while a request is in flight. Disable send while in flight.
- Auto-scroll to bottom on new message.

### Markdown rendering (assistant only)

Implement a small safe renderer: **escape HTML first**, then apply:
- paragraphs and line breaks; `**bold**`, `*italic*`, `` `code` ``; `- ` / `* ` and `1. ` lists; `### ` headings (render as bold line);
- links `[text](url)` only for `http(s):` URLs or URLs starting with `/` (open in new tab, `rel="noopener"`);
- GFM tables: header row, separator row `|---|`, body rows. Wrap the table in a horizontally scrollable div.
  Table cells whose text starts with a status symbol get a class: `✓` → ok (green), `⇄` → swap (blue), `↻` → round (amber), `⚠` → warn (orange), `✗` → err (red).
  Style: small font (12.5px), zebra rows, sticky header.
Never use `innerHTML` with unescaped server text.

### Action buttons

Under every assistant message that contains a table, show a row of buttons:
1. i18n `download` — if the response included `files` (see API), it is a link to the file's `url` (download attribute).
   Otherwise clicking sends the message i18n `ask_file`.
2. i18n `edit` — puts i18n `edit_prefix` into the textarea and focuses it.
3. i18n `explain` — sends i18n `ask_explain`.
If a response has `files` but no table, still show the download link button.

## Welcome screen

When the conversation is empty: greeting (i18n `greeting`, large), short line i18n `intro`, then 5 capability cards
(2-column grid, 1 column under 360px wide). Each card: emoji icon + title. Click behavior:

| # | icon | title key | click |
|---|---|---|---|
| 1 | 📝 | `card_list` | send `ex_list` |
| 2 | 📷 | `card_upload` | open file picker |
| 3 | 🔁 | `card_analogs` | send `ex_analogs` |
| 4 | 🍂 | `card_season` | send `ex_season` |
| 5 | ✅ | `card_check` | open file picker, then the message text defaults to `ex_check` |

## Files

- Paperclip opens `<input type=file accept=".xls,.xlsx,.csv,image/*">` (single file, max 10 MB, else show error).
- Drag & drop onto the panel and pasting an image into the textarea also attach.
- Selected file shows as a chip with name and × to remove. Sending with a file and empty text uses `ex_check` for spreadsheets and `ex_photo` for images.

## Backend API

`POST {api}/api/chat` as `multipart/form-data`: `session_id` (may be empty on first call), `customer_id`, `delivery_point`, `lang`, `message`, optional `file`.
Response JSON:

```json
{"session_id": "abc", "reply": "markdown text", "files": [{"file_id": "x", "filename": "order_x.xls", "url": "/api/files/x"}]}
```

Relative file URLs are resolved against `data-api`. `POST {api}/api/reset` with JSON `{"session_id": "..."}` on "new chat".
Non-2xx or network error → error message with retry. Timeout 180 s (AbortController).

## Persistence

`localStorage` key `medina:v1:<customer>` holds `{state: "closed"|"open"|"minimized", wide, lang, session_id, unread, messages}`
(last 60 messages; each `{role, text, files, ts}`; file contents are never stored). Every read/write is wrapped in try/catch;
the widget works without storage. Restore state on page load (open panel stays open across page navigation).

## i18n strings

| key | ru | kk | en |
|---|---|---|---|

| subtitle | Ассистент заказа | Тапсырыс көмекшісі | Order assistant |
| greeting | Здравствуйте! Я Medina — помогу собрать заказ | Сәлеметсіз бе! Мен Medina — тапсырыс жинауға көмектесемін | Hello! I'm Medina — I'll help you put an order together |
| intro | Пишите как удобно: списком, с опечатками, по-русски или по-казахски. | Өзіңізге ыңғайлы жазыңыз: тізіммен, қатемен, орысша немесе қазақша. | Write the way you like: a list, with typos, in Russian, Kazakh or English. |
| card_list | Вставь список — соберу заказ | Тізімді қойыңыз — тапсырыс жинаймын | Paste a list — I'll build the order |
| card_upload | Загрузи фото или Excel заказа | Тапсырыстың фотосын немесе Excel файлын жүктеңіз | Upload a photo or Excel of an order |
| card_analogs | Чего нет в наличии? Подберу аналоги | Қоймада жоқ па? Аналогын табамын | Out of stock? I'll find analogs |
| card_season | Что дозаказать к сезону простуд? | Суық тию маусымына не тапсырыс беру керек? | What to reorder for the cold season? |
| card_check | Проверь мой файл перед загрузкой | Жүктеу алдында файлымды тексеріңіз | Check my file before upload |
| ex_list | Собери заказ: нурафен 200 таб 10 уп, омез 20 - 5, аквадетрим 10, парацетамол свечи 250 №10 20 шт, амоксиклав 875 5 уп | Тапсырыс жинаңыз: нурафен 200 таб 10 қорап, омез 20 - 5, аквадетрим 10, парацетамол шам 250 №10 20 дана | Build an order: nurafen 200 tab 10 packs, omez 20 - 5, akvadetrim 10, paracetamol suppositories 250 №10 20 pcs, amoksiklav 875 5 packs |
| ex_analogs | Парацетамол свечи 250 мг №10 нет в наличии — подбери аналоги | Парацетамол шам 250 мг №10 қоймада жоқ — аналогын табыңыз | Paracetamol suppositories 250 mg №10 are out of stock — find analogs |
| ex_season | Что дозаказать к сезону простуд? | Суық тию маусымына не тапсырыс беру керек? | What should I reorder for the cold season? |
| ex_check | Проверь этот файл перед загрузкой на портал | Порталға жүктемес бұрын осы файлды тексеріңіз | Check this file before I upload it to the portal |
| ex_photo | Собери заказ по фото | Фото бойынша тапсырыс жинаңыз | Build an order from this photo |
| placeholder | Напишите заказ или вопрос… | Тапсырысты немесе сұрақты жазыңыз… | Type an order or a question… |
| typing | Medina печатает… | Medina жазып жатыр… | Medina is typing… |
| download | Скачать файл для Order upload | Order upload үшін файлды жүктеу | Download file for Order upload |
| edit | Изменить | Өзгерту | Edit |
| explain | Пояснить замены | Ауыстыруларды түсіндіру | Explain replacements |
| ask_file | Сформируй файл для загрузки | Жүктеуге арналған файлды жасаңыз | Build the upload file |
| ask_explain | Поясни замены | Ауыстыруларды түсіндіріңіз | Explain the replacements |
| edit_prefix | Изменить: | Өзгерту: | Change: |
| new_chat | Новый разговор | Жаңа сөйлесу | New chat |
| expand | Развернуть | Кеңейту | Expand |
| restore | Уменьшить | Кішірейту | Shrink |
| minimize | Свернуть | Жию | Minimize |
| close | Закрыть | Жабу | Close |
| open | Открыть Medina | Medina-ны ашу | Open Medina |
| continue | Medina · продолжить | Medina · жалғастыру | Medina · continue |
| attach | Прикрепить файл | Файл тіркеу | Attach file |
| send | Отправить | Жіберу | Send |
| error | Не удалось получить ответ. | Жауап алу мүмкін болмады. | Could not get a reply. |
| retry | Повторить | Қайталау | Retry |
| too_big | Файл больше 10 МБ | Файл 10 МБ-тан үлкен | The file is larger than 10 MB |
| disclaimer | Medina не даёт медицинских советов. Заказ всегда подтверждаете вы. | Medina медициналық кеңес бермейді. Тапсырысты әрқашан өзіңіз растайсыз. | Medina gives no medical advice. You always confirm the order. |
