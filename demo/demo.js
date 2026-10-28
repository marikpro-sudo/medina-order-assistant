// Mock portal page: catalog, cart, strict order upload. Hosts the Medina widget.
(() => {
  const API = location.origin;
  const params = new URLSearchParams(location.search);
  const customerId = params.get("customer") || "C100004";
  const lang = params.get("lang") || "ru";
  const CART_KEY = `demo-cart:${customerId}`;
  const $ = (id) => document.getElementById(id);

  const fmt = (n) => Number(n).toLocaleString("ru-RU", { maximumFractionDigits: 0 });
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const daysTo = (iso) => Math.round((new Date(iso) - new Date("2026-10-28")) / 86400000);

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
      <td><button class="link" data-del="${i}" type="button">Удалить</button></td></tr>`).join("")
      : `<tr><td colspan="4" class="muted">Корзина пуста</td></tr>`;
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
    $("customer").innerHTML = list.map((c) =>
      `<option value="${c.customer_id}" ${c.customer_id === customerId ? "selected" : ""}>${esc(c.name)}${c.overdue_debt > 0 ? " · ДЗ" : ""}</option>`).join("");
    const me = list.find((c) => c.customer_id === customerId);
    const debt = $("debt");
    if (me && me.overdue_debt > 0) {
      debt.textContent = `Просроченная ДЗ: ${fmt(me.overdue_debt)} ₸`;
      debt.classList.add("bad");
    } else {
      debt.textContent = "Просроченной ДЗ нет";
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
    $("catalog-info").textContent = q && !items.length ? `По запросу «${q}» ничего не найдено.` : "";
    $("catalog").innerHTML = items.map(rowHtml).join("");
  }
  function rowHtml(p) {
    const head = `<td><div class="name">${esc(p.name)}${p.is_prescription ? '<span class="rx">Rx</span>' : ""}</div>
      <div class="sub">${esc(p.inn)} · код ${esc(p.material_id)} · кратность ${p.order_multiple}</div></td>
      <td>${esc(p.manufacturer)}<div class="sub">${esc(p.country)}</div></td>`;
    if (!p.batches.length) {
      return `<tr>${head}<td colspan="4" class="oos">Временно отсутствует на складе</td>
        <td></td><td><button class="link" data-analogs="${esc(p.name)}" type="button">Показать аналоги</button></td></tr>`;
    }
    const b = p.batches[0];
    const short = daysTo(b.expiry_date) <= 90 ? "short" : "";
    return `<tr>${head}<td>${esc(b.batch_id)}</td><td class="${short}">${esc(b.expiry_date)}</td>
      <td class="num">${fmt(p.batches.reduce((s, x) => s + x.qty, 0))}</td><td class="num">${fmt(b.price)}</td>
      <td><input type="number" min="${p.order_multiple}" step="${p.order_multiple}" value="${p.order_multiple}"></td>
      <td><button data-add="${esc(p.material_id)}" data-name="${esc(p.name)}" type="button">В корзину</button></td></tr>`;
  }
  $("catalog").addEventListener("click", (e) => {
    const t = e.target;
    if (t.dataset.add) {
      const qty = Number(t.closest("tr").querySelector("input").value) || 1;
      addToCart([{ material_id: t.dataset.add, name: t.dataset.name, qty }]);
    } else if (t.dataset.analogs && window.Medina) {
      window.Medina.open();
      window.Medina.send(`${t.dataset.analogs} нет в наличии — подбери аналоги`);
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
      out.innerHTML = `<div class="alert ok">Загружено строк: ${res.lines.length}. Товары добавлены в корзину.</div>`;
    } else {
      out.innerHTML = `<div class="alert err">${esc(res.error)}
        <button id="ask-medina" type="button">Разобрать файл с Medina</button></div>`;
      $("ask-medina").addEventListener("click", () => window.Medina &&
        window.Medina.sendFile(f, "Портал не принял этот файл: «Ошибка загрузки файла». Найди ошибки по строкам"));
    }
  });

  // --- embed the widget: one script tag, as on the real portal ---
  const s = document.createElement("script");
  s.src = `${API}/medina.js`;
  s.dataset.api = API;
  s.dataset.customer = customerId;
  s.dataset.lang = lang;
  document.body.appendChild(s);

  renderCart();
  loadCustomers();
  loadCatalog();
})();
