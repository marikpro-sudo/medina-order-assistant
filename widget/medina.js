(() => {
'use strict';

// i18n strings (exact, UTF-8). Keys used across layout, cards and API prompts.
const STR = {
  ru: {
    subtitle: 'Ассистент заказа',
    greeting: 'Здравствуйте! Я Medina — помогу собрать заказ',
    intro: 'Пишите как удобно: списком, с опечатками, по-русски или по-казахски.',
    card_list: 'Вставь список — соберу заказ',
    card_upload: 'Загрузи фото или Excel заказа',
    card_analogs: 'Чего нет в наличии? Подберу аналоги',
    card_season: 'Что дозаказать к сезону простуд?',
    card_check: 'Проверь мой файл перед загрузкой',
    ex_list: 'Собери заказ: нурафен 200 таб 10 уп, омез 20 - 5, аквадетрим 10, парацетамол свечи 250 №10 20 шт, амоксиклав 875 5 уп',
    ex_analogs: 'Парацетамол свечи 250 мг №10 нет в наличии — подбери аналоги',
    ex_season: 'Что дозаказать к сезону простуд?',
    ex_check: 'Проверь этот файл перед загрузкой на портал',
    ex_photo: 'Собери заказ по фото',
    placeholder: 'Напишите заказ или вопрос…',
    typing: 'Medina печатает…',
    download: 'Скачать файл для Order upload',
    edit: 'Изменить',
    explain: 'Пояснить замены',
    ask_file: 'Сформируй файл для загрузки',
    ask_explain: 'Поясни замены',
    edit_prefix: 'Изменить:',
    new_chat: 'Новый разговор',
    expand: 'Развернуть',
    restore: 'Уменьшить',
    minimize: 'Свернуть',
    close: 'Закрыть',
    open: 'Открыть Medina',
    continue: 'Medina · продолжить',
    attach: 'Прикрепить файл',
    send: 'Отправить',
    error: 'Не удалось получить ответ.',
    retry: 'Повторить',
    too_big: 'Файл больше 10 МБ',
    disclaimer: 'Medina не даёт медицинских советов. Заказ всегда подтверждаете вы.'
  },
  kk: {
    subtitle: 'Тапсырыс көмекшісі',
    greeting: 'Сәлеметсіз бе! Мен Medina — тапсырыс жинауға көмектесемін',
    intro: 'Өзіңізге ыңғайлы жазыңыз: тізіммен, қатемен, орысша немесе қазақша.',
    card_list: 'Тізімді қойыңыз — тапсырыс жинаймын',
    card_upload: 'Тапсырыстың фотосын немесе Excel файлын жүктеңіз',
    card_analogs: 'Қоймада жоқ па? Аналогын табамын',
    card_season: 'Суық тию маусымына не тапсырыс беру керек?',
    card_check: 'Жүктеу алдында файлымды тексеріңіз',
    ex_list: 'Тапсырыс жинаңыз: нурафен 200 таб 10 қорап, омез 20 - 5, аквадетрим 10, парацетамол шам 250 №10 20 дана',
    ex_analogs: 'Парацетамол шам 250 мг №10 қоймада жоқ — аналогын табыңыз',
    ex_season: 'Суық тию маусымына не тапсырыс беру керек?',
    ex_check: 'Порталға жүктемес бұрын осы файлды тексеріңіз',
    ex_photo: 'Фото бойынша тапсырыс жинаңыз',
    placeholder: 'Тапсырысты немесе сұрақты жазыңыз…',
    typing: 'Medina жазып жатыр…',
    download: 'Order upload үшін файлды жүктеу',
    edit: 'Өзгерту',
    explain: 'Ауыстыруларды түсіндіру',
    ask_file: 'Жүктеуге арналған файлды жасаңыз',
    ask_explain: 'Ауыстыруларды түсіндіріңіз',
    edit_prefix: 'Өзгерту:',
    new_chat: 'Жаңа сөйлесу',
    expand: 'Кеңейту',
    restore: 'Кішірейту',
    minimize: 'Жию',
    close: 'Жабу',
    open: 'Medina-ны ашу',
    continue: 'Medina · жалғастыру',
    attach: 'Файл тіркеу',
    send: 'Жіберу',
    error: 'Жауап алу мүмкін болмады.',
    retry: 'Қайталау',
    too_big: 'Файл 10 МБ-тан үлкен',
    disclaimer: 'Medina медициналық кеңес бермейді. Тапсырысты әрқашан өзіңіз растайсыз.'
  }
};

const MAX_BYTES = 10 * 1024 * 1024;
const TIMEOUT_MS = 180000;
const ACCEPT = '.xls,.xlsx,.csv,image/*';

// Find our own script tag: currentScript first, else last medina.js script.
function findScript() {
  try {
    if (document.currentScript && document.currentScript.src) return document.currentScript;
  } catch (e) { /* ignore */ }
  const all = document.querySelectorAll('script[src]');
  for (let i = all.length - 1; i >= 0; i--) {
    if (all[i].src.indexOf('medina.js') !== -1) return all[i];
  }
  return null;
}

// Read widget config from the script tag attributes.
function readConfig() {
  const s = findScript();
  const get = (k) => (s && s.getAttribute('data-' + k)) || '';
  let api = get('api');
  if (!api && s && s.src) {
    try { api = new URL(s.src, document.baseURI).origin; } catch (e) { api = ''; }
  }
  if (!api) api = location.origin;
  return {
    api: api.replace(/\/+$/, ''),
    customer: get('customer'),
    token: get('token'), // signed by the portal module in production; replaces customer/point
    point: get('point'),
    lang: get('lang') === 'kk' ? 'kk' : 'ru',
    color: get('color') || '#0E7C66'
  };
}

// Escape untrusted text before any markdown transform.
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    c === '&' ? '&amp;' : c === '<' ? '&lt;' : c === '>' ? '&gt;' : c === '"' ? '&quot;' : '&#39;'
  ));
}

// Keep only safe link targets: http(s) or root-relative.
function safeHref(u) {
  const v = String(u).trim();
  if (/^https?:\/\//i.test(v) || /^\/(?!\/)/.test(v)) return v; // reject protocol-relative //host
  return '';
}

// Inline markdown on already-escaped text: code, links, bold, italic.
function inlineMd(s) {
  let out = esc(s);
  out = out.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, text, url) => {
    const h = safeHref(url);
    if (!h) return text;
    // h comes from already-escaped text; escaping again would turn & into &amp;amp;
    return '<a href="' + h + '" target="_blank" rel="noopener noreferrer">' + text + '</a>';
  });
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[\s(>])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  return out;
}

// Split a table row on pipes, trimming edge pipes and cells.
function splitRow(line) {
  let v = line.trim();
  if (v.charAt(0) === '|') v = v.slice(1);
  if (v.charAt(v.length - 1) === '|') v = v.slice(0, -1);
  return v.split('|').map((c) => c.trim());
}

// A separator row looks like |---|---|.
function isSep(line) {
  const v = line.trim().replace(/^\||\|$/g, '');
  return v.indexOf('-') !== -1 && /^[\s:|\-]+$/.test(v);
}

// Status class for table cells starting with a symbol.
function statusClass(cell) {
  const c = cell.charAt(0);
  if (c === '✓') return 'm-ok';
  if (c === '⇄') return 'm-swap';
  if (c === '↻') return 'm-round';
  if (c === '⚠') return 'm-warn';
  if (c === '✗') return 'm-err';
  return '';
}

// Render one GFM table block into a scrollable wrapper.
function tableHtml(head, body) {
  let h = '<div class="m-tw"><table class="m-t"><thead><tr>';
  head.forEach((c) => { h += '<th>' + inlineMd(c) + '</th>'; });
  h += '</tr></thead><tbody>';
  body.forEach((row, i) => {
    h += '<tr class="' + (i % 2 ? 'm-alt' : '') + '">';
    row.forEach((c) => {
      const k = statusClass(c);
      h += '<td' + (k ? ' class="' + k + '"' : '') + '>' + inlineMd(c) + '</td>';
    });
    h += '</tr>';
  });
  return h + '</tbody></table></div>';
}

// Small safe markdown renderer for assistant text (escapes first).
function renderMd(src) {
  const lines = String(src).split('\n');
  let html = '';
  let para = [];
  let ul = [];
  let ol = [];
  const closeLists = () => {
    if (ul.length) { html += '<ul>' + ul.map((x) => '<li>' + inlineMd(x) + '</li>').join('') + '</ul>'; ul = []; }
    if (ol.length) { html += '<ol>' + ol.map((x) => '<li>' + inlineMd(x) + '</li>').join('') + '</ol>'; ol = []; }
  };
  const flushPara = () => {
    if (para.length) { html += '<p>' + para.map(inlineMd).join('<br>') + '</p>'; para = []; }
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const t = line.trim();
    // GFM table: header row + separator row.
    if (t.indexOf('|') !== -1 && i + 1 < lines.length && isSep(lines[i + 1])) {
      flushPara(); closeLists();
      const head = splitRow(line);
      const body = [];
      i += 2;
      while (i < lines.length && lines[i].trim().indexOf('|') !== -1 && lines[i].trim() !== '') {
        body.push(splitRow(lines[i]));
        i++;
      }
      i--;
      html += tableHtml(head, body);
      continue;
    }
    if (/^#{1,6}\s/.test(t)) {
      flushPara(); closeLists();
      html += '<div class="m-h">' + inlineMd(t.replace(/^#{1,6}\s+/, '')) + '</div>';
      continue;
    }
    let m = t.match(/^[-*]\s+(.*)$/);
    if (m) { flushPara(); if (ol.length) closeLists(); ul.push(m[1]); continue; }
    m = t.match(/^\d+[.)]\s+(.*)$/);
    if (m) { flushPara(); if (ul.length) closeLists(); ol.push(m[1]); continue; }
    if (t === '') { flushPara(); closeLists(); continue; }
    para.push(line.trim());
  }
  flushPara(); closeLists();
  return html || '<p></p>';
}

// True when the reply text contains a GFM table.
function hasTable(src) {
  const lines = String(src).split('\n');
  for (let i = 0; i + 1 < lines.length; i++) {
    if (lines[i].indexOf('|') !== -1 && isSep(lines[i + 1])) return true;
  }
  return false;
}

// Resolve a backend file url against data-api when relative.
function fileUrl(url, api) {
  const u = String(url || '');
  if (/^https?:\/\//i.test(u)) return u;
  try { return new URL(u, api + '/').href; } catch (e) { return u; }
}

const cfg = readConfig();
let lang = cfg.lang;
let sessionId = '';
let messages = []; // {role, text, files, ts}
let state = 'closed'; // closed | open | minimized
let wide = false;
let unread = false;
let inFlight = false;
let pendingFile = null; // File object awaiting send
let lastUser = null; // {text} for retry

const t = (k) => (STR[lang] && STR[lang][k]) || STR.ru[k] || k;
const storeKey = () => 'medina:v1:' + cfg.customer;

// Load persisted widget state (tolerant of missing storage).
function loadState() {
  try {
    const raw = localStorage.getItem(storeKey());
    if (!raw) return;
    const d = JSON.parse(raw);
    if (d.lang === 'ru' || d.lang === 'kk') lang = d.lang;
    if (d.state === 'open' || d.state === 'minimized') state = d.state;
    wide = !!d.wide;
    unread = !!d.unread;
    sessionId = typeof d.session_id === 'string' ? d.session_id : '';
    if (Array.isArray(d.messages)) {
      messages = d.messages.filter((m) => m && m.role && typeof m.text === 'string').slice(-60);
    }
  } catch (e) { /* storage unavailable: run without it */ }
}

// Persist last 60 messages; file contents are never stored.
function saveState() {
  try {
    const slim = messages.slice(-60).map((m) => ({
      role: m.role, text: m.text, ts: m.ts,
      files: (m.files || []).map((f) => ({ filename: f.filename, url: f.url, file_id: f.file_id }))
    }));
    localStorage.setItem(storeKey(), JSON.stringify({
      state, wide, lang, session_id: sessionId, unread, messages: slim
    }));
  } catch (e) { /* storage unavailable */ }
}

// Create an element with optional class and text.
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

// All widget CSS lives in the shadow root.
function cssText() {
  return ':host{all:initial}' +
    '.m-f{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:14px;color:var(--m-text,#1c1e21);' +
    '--m-primary:' + cfg.color + ';--m-bg:#fff;--m-text:#1c1e21;--m-muted:#6b7280;--m-border:#e5e7eb}' +
    '.m-launch{position:fixed;right:20px;bottom:20px;width:60px;height:60px;border-radius:50%;border:0;cursor:pointer;' +
    'background:var(--m-primary);box-shadow:0 8px 24px rgba(0,0,0,.22),0 2px 6px rgba(0,0,0,.14);' +
    'display:flex;align-items:center;justify-content:center;padding:0;z-index:2147483000;' +
    'transition:transform .18s ease,opacity .18s ease}' +
    '.m-launch:hover{transform:scale(1.05)}' +
    '.m-dot{position:absolute;top:4px;right:4px;width:12px;height:12px;border-radius:50%;background:#e5484d;border:2px solid #fff}' +
    '.m-panel{position:fixed;right:20px;bottom:90px;width:400px;height:min(640px,calc(100vh - 110px));' +
    'background:var(--m-bg);border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.2),0 2px 8px rgba(0,0,0,.1);' +
    'display:flex;flex-direction:column;overflow:hidden;z-index:2147483000;' +
    'opacity:0;transform:translateY(8px) scale(.98);pointer-events:none;transition:opacity .18s ease,transform .18s ease}' +
    '.m-panel.m-open{opacity:1;transform:none;pointer-events:auto}' +
    '.m-panel.m-wide{width:min(760px,calc(100vw - 40px));height:calc(100vh - 110px)}' +
    '.m-mini{position:fixed;right:20px;bottom:20px;width:260px;height:48px;border:0;border-radius:24px;cursor:pointer;' +
    'background:var(--m-primary);color:#fff;font-size:14px;box-shadow:0 8px 24px rgba(0,0,0,.22);z-index:2147483000;' +
    'transition:opacity .18s ease,transform .18s ease}' +
    '.m-hide{display:none!important}' +
    '.m-head{background:var(--m-primary);color:#fff;display:flex;align-items:center;gap:8px;padding:8px 8px 8px 16px}' +
    '.m-av{width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,.2);color:#fff;' +
    'display:flex;align-items:center;justify-content:center;font-weight:700;flex:none}' +
    '.m-tt{flex:1;min-width:0;line-height:1.25}.m-tt b{font-size:14px}.m-tt span{display:block;font-size:12px;opacity:.85}' +
    '.m-ib{border:0;background:transparent;color:#fff;cursor:pointer;font-size:15px;min-width:32px;height:32px;' +
    'border-radius:8px;padding:0 6px}.m-ib:hover{background:rgba(255,255,255,.18)}' +
    '.m-list{flex:1;overflow-y:auto;overflow-x:hidden;min-width:0;padding:16px;display:flex;flex-direction:column;gap:8px;background:var(--m-bg)}' +
    '.m-u{align-self:flex-end;max-width:85%;background:color-mix(in srgb,var(--m-primary) 12%,white);' +
    'border:1px solid var(--m-border);border-radius:16px 16px 4px 16px;padding:8px 12px;white-space:pre-wrap;overflow-wrap:anywhere}' +
    '.m-a{align-self:stretch;max-width:100%;min-width:0;box-sizing:border-box;background:#f1f2f4;border-radius:4px 16px 16px 16px;padding:8px 12px;overflow-wrap:anywhere}' +
    '.m-a p{margin:0 0 8px}.m-a p:last-child{margin:0}.m-a ul,.m-a ol{margin:4px 0;padding-left:20px}' +
    '.m-a code{background:#e4e6ea;border-radius:4px;padding:1px 5px;font-size:12.5px}' +
    '.m-a a{color:var(--m-primary)}.m-h{font-weight:700;margin:4px 0}' +
    '.m-tw{overflow-x:auto;margin:8px -4px;max-width:100%}' +
    '.m-t{border-collapse:collapse;font-size:12.5px;min-width:100%}' +
    '.m-t th,.m-t td{border:1px solid var(--m-border);padding:6px 8px;text-align:left;vertical-align:top;' +
    'min-width:44px;max-width:220px;overflow-wrap:break-word}' +
    '.m-t td:first-child,.m-t th:first-child{min-width:0;white-space:nowrap}' +
    '.m-t thead th{background:#e9ebee;position:sticky;top:0}' +
    '.m-t tr.m-alt td{background:#f7f8fa}' +
    '.m-ok{color:#0e7c3a;background:#e6f4ea}.m-swap{color:#0b5cad;background:#e3f0fc}' +
    '.m-round{color:#8a5a00;background:#fdf3d7}.m-warn{color:#b35400;background:#fdeee0}.m-err{color:#b3261e;background:#fdecea}' +
    '.m-s{align-self:center;color:var(--m-muted);font-size:12.5px;text-align:center}' +
    '.m-errb{align-self:center;color:#b3261e;background:#fdecea;border:1px solid #f5c6c2;border-radius:8px;padding:8px 12px;text-align:center}' +
    '.m-linkb{border:1px solid var(--m-primary);background:#fff;color:var(--m-primary);border-radius:8px;' +
    'padding:4px 12px;margin-top:8px;cursor:pointer;font-size:13px}' +
    '.m-acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}' +
    '.m-acts button,.m-acts a{border:1px solid var(--m-primary);background:#fff;color:var(--m-primary);border-radius:8px;' +
    'padding:4px 12px;cursor:pointer;font-size:13px;text-decoration:none}' +
    '.m-acts button:hover,.m-acts a:hover{background:color-mix(in srgb,var(--m-primary) 10%,white)}' +
    '.m-ty{align-self:flex-start;background:#f1f2f4;border-radius:4px 16px 16px 16px;padding:8px 12px;color:var(--m-muted)}' +
    '.m-ty i{display:inline-block;width:6px;height:6px;border-radius:50%;background:#9aa0a6;margin-right:4px;animation:mb 1s infinite}' +
    '.m-ty i:nth-child(2){animation-delay:.15s}.m-ty i:nth-child(3){animation-delay:.3s}' +
    '@keyframes mb{0%,100%{opacity:.3}50%{opacity:1}}' +
    '.m-w{text-align:center;padding:8px 0}.m-w h2{font-size:18px;margin:8px 0}' +
    '.m-w p{color:var(--m-muted);margin:0 0 16px}' +
    '.m-cards{display:grid;grid-template-columns:1fr 1fr;gap:8px;text-align:left}' +
    '@media (max-width:360px){.m-cards{grid-template-columns:1fr}}' +
    '.m-card{display:flex;align-items:center;gap:10px;border:1px solid var(--m-border);border-radius:12px;padding:10px 12px;' +
    'cursor:pointer;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.06);font:inherit;font-size:13px;line-height:1.3;' +
    'text-align:left;color:inherit}' +
    '.m-card:hover{border-color:var(--m-primary);box-shadow:0 4px 12px rgba(0,0,0,.08)}' +
    '.m-card .m-ci{font-size:18px;flex:none}' +
    '.m-foot{border-top:1px solid var(--m-border);padding:8px 8px 4px;background:var(--m-bg)}' +
    '.m-chip{display:inline-flex;align-items:center;gap:8px;background:#eef2f1;border-radius:8px;padding:4px 8px;margin:0 8px 8px;font-size:13px}' +
    '.m-chip button{border:0;background:transparent;cursor:pointer;font-size:14px;color:var(--m-muted)}' +
    '.m-fchip{display:inline-block;background:rgba(0,0,0,.07);border-radius:8px;padding:2px 8px;font-size:12px;margin-top:4px}' +
    '.m-row{display:flex;gap:8px;align-items:flex-end;padding:0 8px}' +
    '.m-clip{border:0;background:transparent;cursor:pointer;font-size:18px;color:var(--m-muted);padding:8px 4px;flex:none}' +
    '.m-in{flex:1;border:1px solid var(--m-border);border-radius:8px;padding:8px;font-size:14px;resize:none;' +
    'font-family:inherit;line-height:20px;max-height:120px}' +
    '.m-send{flex:none;width:36px;height:36px;border-radius:50%;border:0;cursor:pointer;background:var(--m-primary);color:#fff}' +
    '.m-send:disabled{opacity:.4;cursor:default}' +
    '.m-dis{color:var(--m-muted);font-size:11.5px;text-align:center;padding:4px 8px 8px}' +
    '@media (max-width:600px){.m-panel{right:0;left:0;top:0;bottom:0;width:auto;height:auto;border-radius:0}}' +
    '@media (prefers-reduced-motion:reduce){.m-panel,.m-launch,.m-mini{transition:none!important}.m-ty i{animation:none!important}}';
}

let root; // shadow root
let launchBtn; let dotEl; let panel; let miniBtn;
let listEl; let areaEl; let sendBtn; let clipBtn; let fileInput;
let chipRow; let chipName; let langBtn; let expBtn;
let typingEl = null;

// Refresh enabled/disabled state of the send button.
function refreshSend() {
  const hasText = areaEl.value.trim().length > 0;
  sendBtn.disabled = inFlight || (!hasText && !pendingFile);
}

// Grow the textarea between 1 and 6 rows.
function autogrow() {
  areaEl.style.height = 'auto';
  const line = 20;
  const max = line * 6 + 16;
  areaEl.style.height = Math.min(areaEl.scrollHeight, max) + 'px';
  refreshSend();
}

// Choose default message text when sending a bare file.
function defaultForFile(f) {
  if (f && f.type && f.type.indexOf('image/') === 0) return t('ex_photo');
  return t('ex_check');
}

// Attach a file after size validation (max 10 MB).
function attachFile(f) {
  if (!f) return;
  if (f.size > MAX_BYTES) { addSystem(t('too_big')); return; }
  pendingFile = f;
  chipName.textContent = f.name;
  chipRow.classList.remove('m-hide');
  refreshSend();
}

function clearFile() {
  pendingFile = null;
  fileInput.value = '';
  chipRow.classList.add('m-hide');
  refreshSend();
}

// Append a centered system/error line to the message list.
function addSystem(text, canRetry) {
  const box = el('div', canRetry ? 'm-errb' : 'm-s', text);
  listEl.appendChild(box);
  if (canRetry) {
    const b = el('button', 'm-linkb', t('retry'));
    b.setAttribute('aria-label', t('retry'));
    b.addEventListener('click', () => { box.remove(); b.remove(); doSend(lastUser ? lastUser.text : '', lastUser ? lastUser.file : null); });
    listEl.appendChild(b);
  }
  listEl.scrollTop = listEl.scrollHeight;
  return box;
}

// Show or hide the typing indicator.
function setTyping(on) {
  if (on && !typingEl) {
    typingEl = el('div', 'm-ty');
    typingEl.appendChild(el('span', null, t('typing') + ' '));
    for (let i = 0; i < 3; i++) typingEl.appendChild(el('i'));
    listEl.appendChild(typingEl);
    listEl.scrollTop = listEl.scrollHeight;
  } else if (!on && typingEl) {
    typingEl.remove();
    typingEl = null;
  }
  refreshSend();
}

// One capability card on the welcome screen.
function cardBtn(icon, title, onClick) {
  const b = el('button', 'm-card');
  b.setAttribute('aria-label', title);
  b.appendChild(el('span', 'm-ci', icon));
  b.appendChild(el('span', null, title));
  b.addEventListener('click', onClick);
  return b;
}

// Empty-state welcome screen with 5 capability cards.
function welcomeEl() {
  const w = el('div', 'm-w');
  w.appendChild(el('h2', null, t('greeting')));
  w.appendChild(el('p', null, t('intro')));
  const g = el('div', 'm-cards');
  g.appendChild(cardBtn('📝', t('card_list'), () => doSend(t('ex_list'))));
  g.appendChild(cardBtn('📷', t('card_upload'), () => fileInput.click()));
  g.appendChild(cardBtn('🔁', t('card_analogs'), () => doSend(t('ex_analogs'))));
  g.appendChild(cardBtn('🍂', t('card_season'), () => doSend(t('ex_season'))));
  g.appendChild(cardBtn('✅', t('card_check'), () => {
    if (!areaEl.value.trim()) { areaEl.value = t('ex_check'); autogrow(); }
    fileInput.click();
  }));
  w.appendChild(g);
  return w;
}

// Action buttons under an assistant message with a table (or files).
function actionsEl(msg) {
  const row = el('div', 'm-acts');
  const files = msg.files || [];
  if (files.length && files[0].url) {
    const a = el('a', null, t('download'));
    a.href = fileUrl(files[0].url, cfg.api);
    a.setAttribute('download', files[0].filename || '');
    a.setAttribute('target', '_blank');
    a.setAttribute('rel', 'noopener noreferrer');
    row.appendChild(a);
  } else {
    const d = el('button', null, t('download'));
    d.addEventListener('click', () => doSend(t('ask_file')));
    row.appendChild(d);
  }
  const e = el('button', null, t('edit'));
  e.setAttribute('aria-label', t('edit'));
  e.addEventListener('click', () => {
    areaEl.value = t('edit_prefix') + ' ';
    areaEl.focus();
    autogrow();
  });
  row.appendChild(e);
  const x = el('button', null, t('explain'));
  x.setAttribute('aria-label', t('explain'));
  x.addEventListener('click', () => doSend(t('ask_explain')));
  row.appendChild(x);
  return row;
}

// Render the whole message list (welcome screen when empty).
function renderAll() {
  while (listEl.firstChild) listEl.firstChild.remove();
  typingEl = null;
  if (!messages.length) listEl.appendChild(welcomeEl());
  messages.forEach((m) => {
    if (m.role === 'user') {
      const b = el('div', 'm-u', m.text);
      if (m.files && m.files.length && m.files[0].filename) {
        b.appendChild(el('br'));
        b.appendChild(el('span', 'm-fchip', '📎 ' + m.files[0].filename));
      }
      listEl.appendChild(b);
    } else if (m.role === 'assistant') {
      const b = el('div', 'm-a');
      b.innerHTML = renderMd(m.text); // safe: renderer escapes first
      listEl.appendChild(b);
      if (hasTable(m.text) || (m.files && m.files.length)) listEl.appendChild(actionsEl(m));
    } else {
      listEl.appendChild(el('div', 'm-s', m.text));
    }
  });
  if (inFlight) setTyping(true);
  listEl.scrollTop = messages.length ? listEl.scrollHeight : 0; // welcome screen starts at the top
}

// Apply open/minimized/closed visibility and restore persisted flags.
function applyState() {
  const isOpen = state === 'open';
  panel.classList.toggle('m-open', isOpen);
  launchBtn.classList.toggle('m-hide', isOpen || state === 'minimized');
  miniBtn.classList.toggle('m-hide', state !== 'minimized');
  dotEl.classList.toggle('m-hide', !unread || isOpen);
  panel.classList.toggle('m-wide', wide);
  expBtn.textContent = wide ? '⤡' : '⤢';
  expBtn.setAttribute('aria-label', wide ? t('restore') : t('expand'));
  expBtn.setAttribute('title', wide ? t('restore') : t('expand'));
}

function setTexts() {
  document.documentElement.setAttribute('lang', lang);
  launchBtn.setAttribute('aria-label', t('open'));
  launchBtn.setAttribute('title', t('open'));
  miniBtn.textContent = t('continue');
  miniBtn.setAttribute('aria-label', t('continue'));
  areaEl.placeholder = t('placeholder');
  sendBtn.setAttribute('aria-label', t('send'));
  sendBtn.setAttribute('title', t('send'));
  clipBtn.setAttribute('aria-label', t('attach'));
  clipBtn.setAttribute('title', t('attach'));
  langBtn.textContent = lang === 'ru' ? 'KZ' : 'RU';
  renderAll();
}

function openPanel() {
  state = 'open';
  unread = false;
  applyState();
  saveState();
  areaEl.focus();
}

function closePanel() {
  state = 'closed';
  applyState();
  saveState();
}

function minimizePanel() {
  state = 'minimized';
  applyState();
  saveState();
}

// POST /api/chat with FormData; 180 s timeout via AbortController.
function postChat(fd) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  return fetch(cfg.api + '/api/chat', { method: 'POST', body: fd, signal: ctrl.signal })
    .then((r) => {
      clearTimeout(timer);
      if (!r.ok) throw new Error('http ' + r.status);
      return r.json();
    }, (e) => { clearTimeout(timer); throw e; });
}

// POST /api/reset with JSON on "new chat".
function postReset() {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  return fetch(cfg.api + '/api/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
    signal: ctrl.signal
  }).then((r) => { clearTimeout(timer); return r; },
    (e) => { clearTimeout(timer); throw e; });
}

// Send a message (text and/or the pending file) to the backend.
function doSend(text, file) {
  const msg = (text != null ? String(text) : areaEl.value).trim();
  const f = file !== undefined ? file : pendingFile;
  const body = msg || (f ? defaultForFile(f) : '');
  if (!body || inFlight) return;
  inFlight = true;
  lastUser = { text: body, file: f };
  messages.push({ role: 'user', text: body, files: f ? [{ filename: f.name }] : [], ts: Date.now() });
  messages = messages.slice(-60);
  areaEl.value = '';
  autogrow();
  clearFile();
  renderAll();
  setTyping(true);
  const fd = new FormData();
  fd.append('session_id', sessionId || '');
  fd.append('customer_id', cfg.customer);
  if (cfg.token) fd.append('token', cfg.token);
  fd.append('delivery_point', cfg.point || '');
  fd.append('lang', lang);
  fd.append('message', body);
  if (f) fd.append('file', f, f.name);
  postChat(fd).then((d) => {
    inFlight = false;
    sessionId = (d && d.session_id) || sessionId;
    const reply = (d && d.reply) || '';
    const files = Array.isArray(d && d.files) ? d.files : [];
    messages.push({ role: 'assistant', text: reply, files, ts: Date.now() });
    messages = messages.slice(-60);
    if (state !== 'open') unread = true;
    // Order tables need room: widen the panel once on desktop.
    if (hasTable(reply) && !wide && window.innerWidth > 800) wide = true;
    setTyping(false);
    renderAll();
    applyState();
    saveState();
  }).catch(() => {
    inFlight = false;
    setTyping(false);
    addSystem(t('error'), true);
    saveState();
  });
}

// Clear the conversation and start a new backend session.
function resetChat() {
  messages = [];
  sessionId = '';
  unread = false;
  postReset().catch(() => { /* offline reset still clears locally */ });
  renderAll();
  applyState();
  saveState();
}

// Build the shadow DOM: launcher, panel, minimized pill.
function buildDom(shadow) {
  const wrap = el('div', 'm-f');
  const st = el('style', null, cssText());
  wrap.appendChild(st);

  launchBtn = el('button', 'm-launch');
  launchBtn.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
    '<path d="M12 3C6.5 3 2 6.9 2 11.7c0 2.7 1.4 5.1 3.7 6.7-.1 1-.7 2.6-2.2 3.6 2.4.1 4.2-1.1 5-2 1.4.4 2.9.6 4.5.6 5.5 0 10-3.9 10-8.7S17.5 3 12 3z" fill="#fff"/></svg>';
  dotEl = el('span', 'm-dot m-hide');
  launchBtn.appendChild(dotEl);
  launchBtn.addEventListener('click', openPanel);
  wrap.appendChild(launchBtn);

  panel = el('div', 'm-panel');
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Medina');

  const head = el('div', 'm-head');
  head.appendChild(el('div', 'm-av', 'M'));
  const tt = el('div', 'm-tt');
  tt.appendChild(el('b', null, 'Medina'));
  tt.appendChild(el('span', null, t('subtitle')));
  tt.lastChild.className = 'm-sub';
  head.appendChild(tt);

  langBtn = el('button', 'm-ib', 'KZ');
  langBtn.addEventListener('click', () => {
    lang = lang === 'ru' ? 'kk' : 'ru';
    head.querySelector('.m-sub').textContent = t('subtitle');
    setTexts();
    saveState();
  });
  const newBtn = el('button', 'm-ib', '↺');
  newBtn.setAttribute('aria-label', t('new_chat'));
  newBtn.setAttribute('title', t('new_chat'));
  newBtn.addEventListener('click', resetChat);
  expBtn = el('button', 'm-ib', '⤢');
  expBtn.addEventListener('click', () => { wide = !wide; applyState(); saveState(); });
  const minBtn = el('button', 'm-ib', '—');
  minBtn.setAttribute('aria-label', t('minimize'));
  minBtn.setAttribute('title', t('minimize'));
  minBtn.addEventListener('click', minimizePanel);
  const closeBtn = el('button', 'm-ib', '×');
  closeBtn.setAttribute('aria-label', t('close'));
  closeBtn.setAttribute('title', t('close'));
  closeBtn.addEventListener('click', closePanel);
  [langBtn, newBtn, expBtn, minBtn, closeBtn].forEach((b) => head.appendChild(b));
  panel.appendChild(head);

  listEl = el('div', 'm-list');
  listEl.setAttribute('role', 'log');
  listEl.setAttribute('aria-live', 'polite');
  panel.appendChild(listEl);

  const foot = el('div', 'm-foot');
  chipRow = el('div', 'm-chip m-hide');
  chipName = el('span');
  const chipX = el('button', null, '×');
  chipX.setAttribute('aria-label', t('close'));
  chipX.addEventListener('click', clearFile);
  chipRow.appendChild(chipName);
  chipRow.appendChild(chipX);
  foot.appendChild(chipRow);

  const row = el('div', 'm-row');
  clipBtn = el('button', 'm-clip', '📎');
  clipBtn.addEventListener('click', () => fileInput.click());
  fileInput = el('input');
  fileInput.type = 'file';
  fileInput.accept = ACCEPT;
  fileInput.style.display = 'none';
  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files[0]) attachFile(fileInput.files[0]);
  });
  areaEl = el('textarea', 'm-in');
  areaEl.rows = 1;
  areaEl.addEventListener('input', autogrow);
  areaEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSend(); }
  });
  areaEl.addEventListener('paste', (e) => {
    const items = (e.clipboardData && e.clipboardData.files) || [];
    if (items.length && items[0].type.indexOf('image/') === 0) attachFile(items[0]);
  });
  sendBtn = el('button', 'm-send');
  sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
    '<path d="M12 19V5m-7 7 7-7 7 7" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  sendBtn.addEventListener('click', () => doSend());
  row.appendChild(clipBtn);
  row.appendChild(areaEl);
  row.appendChild(sendBtn);
  row.appendChild(fileInput);
  foot.appendChild(row);
  foot.appendChild(el('div', 'm-dis', t('disclaimer')));
  panel.appendChild(foot);

  // Drag & drop a file anywhere onto the panel.
  panel.addEventListener('dragover', (e) => e.preventDefault());
  panel.addEventListener('drop', (e) => {
    e.preventDefault();
    const fs = (e.dataTransfer && e.dataTransfer.files) || [];
    if (fs.length) attachFile(fs[0]);
  });
  wrap.appendChild(panel);

  miniBtn = el('button', 'm-mini m-hide', t('continue'));
  miniBtn.addEventListener('click', openPanel);
  wrap.appendChild(miniBtn);

  shadow.appendChild(wrap);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state === 'open') minimizePanel();
  });
}

// Public API handle.
function api() {
  return {
    open: openPanel,
    close: closePanel,
    send: (text) => doSend(text),
    setLang: (l) => { if (l === 'ru' || l === 'kk') { lang = l; setTexts(); saveState(); } },
    reset: resetChat
  };
}

function init() {
  loadState();
  const host = document.createElement('div');
  host.id = 'medina-root';
  document.body.appendChild(host);
  root = host.attachShadow({ mode: 'open' });
  buildDom(root);
  setTexts();
  applyState();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

window.Medina = api();
})();
