// Mock portal page: catalog, cart, strict order upload. Hosts the Medina widget.
(() => {
  const API = location.origin;
  const params = new URLSearchParams(location.search);
  const customerId = params.get("customer") || "C100004";
  const lang = params.get("lang") || "ru";
  // Page UI language: en for ?lang=en, Russian text otherwise (kk keeps Russian page text).
  const pageLang = lang === "en" ? "en" : "ru";
  const CART_KEY = `demo-cart:${customerId}`;
  const $ = (id) => document.getElementById(id);

  // Small page dictionary (English comments).
  const I18N = {
    ru: {
      page_title: "ФармаОпт B2B · демо",
      banner: "Демо-стенд Medina. Портал-макет, все данные синтетические.",
      logo: "ФармаОпт",
      customer_label: "Клиент",
      cart_btn: "Корзина",
      tab_catalog: "Каталог",
      tab_cart: "Корзина",
      tab_upload: "Загрузка заказа",
      search_ph: "Поиск по названию, МНН или штрихкоду",
      search_btn: "Найти",
      th_product: "Товар",
      th_manufacturer: "Производитель",
      th_batch: "Серия",
      th_expiry: "Годен до",
      th_stock: "Остаток",
      th_price: "Цена, ₸",
      th_qty: "Кол-во",
      cart_title: "Корзина",
      cart_th_product: "Товар",
      cart_th_code: "Код товара",
      cart_th_qty: "Кол-во",
      cart_clear: "Очистить",
      cart_place: "Оформить заказ",
      cart_place_title: "В демо заказ не оформляется",
      upload_title: "Загрузка заказа (Order upload)",
      upload_desc: "Файл .xls или .csv строго из трёх колонок: <b>Штрихкод | Код товара | Количество</b>, все значения — текстом.",
      upload_btn: "Загрузить",
      debt_overdue: "Просроченная ДЗ: {amount} ₸",
      debt_none: "Просроченной ДЗ нет",
      search_empty: "По запросу «{q}» ничего не найдено.",
      oos: "Временно отсутствует на складе",
      analogs: "Показать аналоги",
      add: "В корзину",
      remove: "Удалить",
      cart_empty: "Корзина пуста",
      upload_ok: "Загружено строк: {n}. Товары добавлены в корзину.",
      upload_analyze: "Разобрать файл с Medina",
      medina_reject: "Портал не принял этот файл: «Ошибка загрузки файла». Найди ошибки по строкам",
      medina_analogs: "{name} нет в наличии — подбери аналоги"
    },
    en: {
      page_title: "PharmaOpt B2B · demo",
      banner: "Medina demo. Mock portal, all data is synthetic.",
      logo: "PharmaOpt",
      customer_label: "Customer",
      cart_btn: "Cart",
      tab_catalog: "Catalog",
      tab_cart: "Cart",
      tab_upload: "Order upload",
      search_ph: "Search by name, INN or barcode",
      search_btn: "Find",
      th_product: "Product",
      th_manufacturer: "Manufacturer",
      th_batch: "Batch",
      th_expiry: "Expiry",
      th_stock: "Stock",
      th_price: "Price, ₸",
      th_qty: "Qty",
      cart_title: "Cart",
      cart_th_product: "Product",
      cart_th_code: "Product code",
      cart_th_qty: "Qty",
      cart_clear: "Clear",
      cart_place: "Place order",
      cart_place_title: "Orders are not placed in the demo",
      upload_title: "Order upload",
      upload_desc: "An .xls or .csv file with exactly three columns — <b>Штрихкод (barcode) | Код товара (product code) | Количество (quantity)</b>, all values as text.",
      upload_btn: "Upload",
      debt_overdue: "Overdue debt: {amount} ₸",
      debt_none: "No overdue debt",
      search_empty: "No results for “{q}”.",
      oos: "Temporarily out of stock",
      analogs: "Show analogs",
      add: "Add to cart",
      remove: "Remove",
      cart_empty: "Cart is empty",
      upload_ok: "Uploaded rows: {n}. Items added to the cart.",
      upload_analyze: "Analyze the file with Medina",
      medina_reject: "The portal rejected this file: “File upload error”. Find the errors row by row",
      medina_analogs: "{name} is out of stock — find analogs"
    }
  };
  const tr = (key) => (I18N[pageLang] && I18N[pageLang][key]) || I18N.ru[key] || key;

  // Apply static strings from data-i18n attributes.
  function applyI18n() {
    document.documentElement.lang = pageLang;
    document.title = tr("page_title");
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;
      if (key === "logo") {
        // Keep the B2B badge span; replace only the first text node.
        const node = Array.from(el.childNodes).find((n) => n.nodeType === 3);
        if (node) node.textContent = tr(key) + " ";
        else el.prepend(document.createTextNode(tr(key) + " "));
        return;
      }
      if (key === "upload_desc") {
        el.innerHTML = tr(key);
        return;
      }
      // Preserve nested elements (e.g. cart count): update only direct text.
      const first = Array.from(el.childNodes).find((n) => n.nodeType === 3 && n.textContent.trim() !== "");
      if (el.children.length > 0 && first) first.textContent = tr(key) + " ";
      else el.textContent = tr(key);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = tr(el.getAttribute("data-i18n-placeholder"));
    });
    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      el.title = tr(el.getAttribute("data-i18n-title"));
    });
  }

  const fmt = (n) => Number(n).toLocaleString(pageLang === "en" ? "en-US" : "ru-RU", { maximumFractionDigits: 0 });
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const daysTo = (iso) => Math.round((new Date(iso) - new Date("2026-10-28")) / 86400000);

  // Localize synthetic customer display names for the en page.
  function localizeCustomerName(name) {
    if (pageLang !== "en") return String(name);
    return String(name).replace(/^Клиент /, "Customer ").replace("(ЛПУ)", "(clinic)");
  }

  // --- cart (browser storage only; demo convenience) ---
  function loadCart() {
    try { return JSON.parse(localStorage.getItem(CART_KEY)) || []; } catch { return []; }
  }
  function saveCart(cart) {
    try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch { /* storage unavailable */ }
    renderCart(cart);
  }
  function addToCart(lines) {
    const cart = loadCart();
    for (const l of lines) {
      const ex = cart.find((c) => c.material_id === l.material_id);
      if (ex) ex.qty += l.qty; else cart.push({ ...l });
    }
    saveCart(cart);
  }
  function renderCart(cart = loadCart()) {
    $("cart-count").textContent = cart.length;
    $("cart").innerHTML = cart.length ? cart.map((c, i) => `
      <tr><td class="name">${esc(c.name)}</td><td>${esc(c.material_id)}</td><td class="num">${c.qty}</td>
      <td><button class="link" data-del="${i}" type="button">${esc(tr("remove"))}</button></td></tr>`).join("")
      : `<tr><td colspan="4" class="muted">${esc(tr("cart_empty"))}</td></tr>`;
  }
  $("cart").addEventListener("click", (e) => {
    const i = e.target.dataset.del;
    if (i === undefined) return;
    const cart = loadCart(); cart.splice(Number(i), 1); saveCart(cart);
  });
  $("cart-clear").addEventListener("click", () => saveCart([]));

  // --- tabs ---
  function showTab(name) {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${name}`));
  }
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("cart-btn").addEventListener("click", () => showTab("cart"));

  // --- customers and debt ---
  async function loadCustomers() {
    const list = await (await fetch(`${API}/api/demo/customers`)).json();
    const suffix = pageLang === "en" ? " · overdue debt" : " · ДЗ";
    $("customer").innerHTML = list.map((c) =>
      `<option value="${c.customer_id}" ${c.customer_id === customerId ? "selected" : ""}>${esc(localizeCustomerName(c.name))}${c.overdue_debt > 0 ? suffix : ""}</option>`).join("");
    const me = list.find((c) => c.customer_id === customerId);
    const debt = $("debt");
    debt.classList.toggle("bad", !!(me && me.overdue_debt > 0));
    if (me && me.overdue_debt > 0) {
      debt.textContent = tr("debt_overdue").replace("{amount}", fmt(me.overdue_debt));
    } else {
      debt.textContent = tr("debt_none");
    }
  }
  $("customer").addEventListener("change", (e) => {
    params.set("customer", e.target.value);
    location.search = params.toString();
  });

  // --- catalog ---
  async function loadCatalog(q = "") {
    const url = `${API}/api/demo/catalog?customer_id=${encodeURIComponent(customerId)}&q=${encodeURIComponent(q)}&limit=60`;
    const items = await (await fetch(url)).json();
    $("catalog-info").textContent = q && !items.length ? tr("search_empty").replace("{q}", q) : "";
    $("catalog").innerHTML = items.map(rowHtml).join("");
  }
  function rowHtml(p) {
    const sub = pageLang === "en"
      ? `${esc(p.inn)} · code ${esc(p.material_id)} · pack multiple ${p.order_multiple}`
      : `${esc(p.inn)} · код ${esc(p.material_id)} · кратность ${p.order_multiple}`;
    const head = `<td><div class="name">${esc(p.name)}${p.is_prescription ? '<span class="rx">Rx</span>' : ""}</div>
      <div class="sub">${sub}</div></td>
      <td>${esc(p.manufacturer)}<div class="sub">${esc(p.country)}</div></td>`;
    if (!p.batches.length) {
      return `<tr>${head}<td colspan="4" class="oos">${esc(tr("oos"))}</td>
        <td></td><td><button class="link" data-analogs="${esc(p.name)}" type="button">${esc(tr("analogs"))}</button></td></tr>`;
    }
    const b = p.batches[0];
    const short = daysTo(b.expiry_date) <= 90 ? "short" : "";
    return `<tr>${head}<td>${esc(b.batch_id)}</td><td class="${short}">${esc(b.expiry_date)}</td>
      <td class="num">${fmt(p.batches.reduce((s, x) => s + x.qty, 0))}</td><td class="num">${fmt(b.price)}</td>
      <td><input type="number" min="${p.order_multiple}" step="${p.order_multiple}" value="${p.order_multiple}"></td>
      <td><button data-add="${esc(p.material_id)}" data-name="${esc(p.name)}" type="button">${esc(tr("add"))}</button></td></tr>`;
  }
  $("catalog").addEventListener("click", (e) => {
    const t = e.target;
    if (t.dataset.add) {
      const qty = Number(t.closest("tr").querySelector("input").value) || 1;
      addToCart([{ material_id: t.dataset.add, name: t.dataset.name, qty }]);
    } else if (t.dataset.analogs && window.Medina) {
      window.Medina.open();
      window.Medina.send(tr("medina_analogs").replace("{name}", t.dataset.analogs));
    }
  });
  $("search-form").addEventListener("submit", (e) => { e.preventDefault(); loadCatalog($("q").value); });

  // --- strict order upload (emulates the current portal behaviour) ---
  $("upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = $("upload-file").files[0];
    const out = $("upload-result");
    if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    const res = await (await fetch(`${API}/api/demo/order-upload`, { method: "POST", body: fd })).json();
    if (res.ok) {
      addToCart(res.lines);
      out.innerHTML = `<div class="alert ok">${esc(tr("upload_ok").replace("{n}", res.lines.length))}</div>`;
    } else {
      // Translate the API's Russian error on the client for the en page.
      const errText = res.error === "Ошибка загрузки файла" && pageLang === "en" ? "File upload error" : res.error;
      out.innerHTML = `<div class="alert err">${esc(errText)}
        <button id="ask-medina" type="button">${esc(tr("upload_analyze"))}</button></div>`;
      $("ask-medina").addEventListener("click", () => window.Medina &&
        window.Medina.sendFile(f, tr("medina_reject")));
    }
  });

  // --- embed the widget: one script tag, as on the real portal ---
  const s = document.createElement("script");
  s.src = `${API}/medina.js`;
  s.dataset.api = API;
  s.dataset.customer = customerId;
  s.dataset.lang = lang;
  document.body.appendChild(s);

  applyI18n();
  renderCart();
  loadCustomers();
  loadCatalog();
})();
