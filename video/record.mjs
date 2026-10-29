// Records the demo scenes with Playwright. `node record.mjs --warm` runs the same flow without recording
// to fill the backend's model cache, so the recorded run shows real answers without long waits.
// Output: public/recordings/<scene>.mp4 and public/recordings/timeline.json (event times per scene, ms).

import { execFileSync } from "node:child_process";
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.DEMO_URL || "http://localhost:8001";
const CUSTOMER = "C100004";
const WARM = process.argv.includes("--warm");
const ONLY = process.argv.find((a) => a.startsWith("--only="))?.slice(7);
const OUT = path.resolve("public/recordings");
const ASSETS = path.resolve("assets");
const VIEW = { width: 1440, height: 810 };
const SIZE = VIEW; // Playwright frames are in CSS pixels; Remotion upscales to 1080p

// Visible cursor and click ripple: headless recordings do not show the mouse.
const CURSOR = `
  window.addEventListener('DOMContentLoaded', () => {
    const c = document.createElement('div');
    c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;z-index:2147483647;pointer-events:none;' +
      'background:url("data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2222%22 height=%2222%22><path d=%22M2 2 L2 18 L7 13 L10 20 L13 19 L10 12 L17 12 Z%22 fill=%22black%22 stroke=%22white%22 stroke-width=%221.5%22/></svg>") no-repeat;' +
      'transform:translate(-2px,-2px);transition:left .02s,top .02s';
    document.body.appendChild(c);
    document.addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    document.addEventListener('mousedown', (e) => {
      const r = document.createElement('div');
      r.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;width:36px;height:36px;border-radius:50%;' +
        'border:3px solid rgba(14,124,102,.8);left:' + (e.clientX - 18) + 'px;top:' + (e.clientY - 18) + 'px;' +
        'transition:transform .4s,opacity .4s';
      document.body.appendChild(r);
      requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 450);
    }, true);
  });`;

const timeline = {};
const sleep = (ms) => new Promise((r) => setTimeout(r, WARM ? Math.min(ms, 200) : ms));

async function scene(browser, name, fn) {
  if (ONLY && ONLY !== name) return;
  const context = await browser.newContext({
    viewport: VIEW, deviceScaleFactor: 1, acceptDownloads: true, locale: "ru-RU",
    ...(WARM ? {} : { recordVideo: { dir: OUT, size: SIZE } }),
  });
  await context.addInitScript(CURSOR);
  const page = await context.newPage();
  const t0 = Date.now();
  const events = [];
  const mark = (key) => { events.push({ key, t: Date.now() - t0 }); console.log(`  [${name}] ${key} @${Date.now() - t0}ms`); };
  console.log(`scene ${name}`);
  await fn(page, mark);
  const duration = Date.now() - t0;
  const video = page.video();
  await context.close();
  if (video) {
    const file = path.join(OUT, `${name}.webm`);
    await video.saveAs(file);
    await video.delete();
    // Remotion's frame extraction is unreliable on Playwright's VP8 webm: re-encode to H.264, 30 fps,
    // short GOP for fast seeking.
    execFileSync("npx", ["remotion", "ffmpeg", "-loglevel", "error", "-y", "-i", file, "-r", "30", "-c:v", "libx264",
      "-preset", "fast", "-crf", "18", "-g", "15", "-pix_fmt", "yuv420p", file.replace(".webm", ".mp4")],
      { stdio: "inherit", shell: true });
    timeline[name] = { file: `${name}.mp4`, duration, events };
  }
}

async function moveClick(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.mouse.move(x, y, { steps: 18 });
  await sleep(250);
  await page.mouse.click(x, y);
}

async function openDemo(page, query = "") {
  await page.goto(`${BASE}/demo/?customer=${CUSTOMER}${query}`);
  await page.locator(".m-launch, #medina-root").first().waitFor({ state: "attached" });
  await sleep(1200);
}

// Waits until Medina's reply count grows and the typing indicator is gone.
async function waitReply(page, before) {
  await page.waitForFunction((n) => {
    const r = document.getElementById("medina-root")?.shadowRoot;
    return r && r.querySelectorAll(".m-a").length > n && !r.querySelector(".m-ty");
  }, before, { timeout: 240000 });
  await sleep(600);
}
const replies = (page) => page.evaluate(() => document.getElementById("medina-root").shadowRoot.querySelectorAll(".m-a").length);

// Smoothly scrolls the chat list to show a long answer.
async function readReply(page, pauseMs = 2500) {
  const list = page.locator(".m-list");
  const box = await list.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
  await page.evaluate(() => {
    const l = document.getElementById("medina-root").shadowRoot.querySelector(".m-list");
    const last = [...l.querySelectorAll(".m-a")].pop();
    l.scrollTop = last.offsetTop - 12;
  });
  await sleep(pauseMs);
  for (let i = 0; i < 12; i++) {
    const done = await page.evaluate(() => {
      const l = document.getElementById("medina-root").shadowRoot.querySelector(".m-list");
      return l.scrollTop + l.clientHeight >= l.scrollHeight - 4;
    });
    if (done) break;
    await page.mouse.wheel(0, 140);
    await sleep(900);
  }
  await sleep(pauseMs);
}

const widgetButton = (page, label) => page.locator(`#medina-root button[aria-label="${label}"]`).first();
const launcher = (page) => page.locator('#medina-root [aria-label="Открыть Medina"]').first();

const browser = await chromium.launch();
fs.mkdirSync(OUT, { recursive: true });

// 1. The portal rejects a file with a generic error; Medina explains it row by row.
await scene(browser, "upload_error", async (page, mark) => {
  await openDemo(page);
  mark("start");
  await moveClick(page, page.locator('.tabs button[data-tab="upload"]'));
  await sleep(800);
  await page.locator("#upload-file").setInputFiles(path.join(ASSETS, "zakaz_apteka.xls"));
  await sleep(700);
  await moveClick(page, page.locator("#upload-form button"));
  await page.locator(".alert.err").waitFor();
  mark("portal_error");
  await sleep(3500);
  const n = await replies(page);
  await moveClick(page, page.locator("#ask-medina"));
  mark("ask_medina");
  await waitReply(page, n);
  mark("reply");
  await readReply(page, 3000);
  mark("end");
});

// 2. A messy list becomes a checked table, then a file the strict upload accepts.
await scene(browser, "order_list", async (page, mark) => {
  await openDemo(page);
  mark("start");
  await moveClick(page, launcher(page));
  await sleep(1500);
  mark("welcome");
  await sleep(2500);
  const n = await replies(page);
  await moveClick(page, page.locator("#medina-root .m-card").first());
  mark("sent_list");
  await waitReply(page, n);
  mark("reply");
  await readReply(page, 3000);
  const n2 = await replies(page);
  await moveClick(page, page.locator("#medina-root button", { hasText: "Скачать файл для Order upload" }).last());
  mark("ask_file");
  await waitReply(page, n2);
  mark("file_ready");
  await sleep(1500);
  const link = page.locator("#medina-root a", { hasText: "Скачать файл для Order upload" }).last();
  const [download] = await Promise.all([page.waitForEvent("download"), moveClick(page, link)]);
  const file = path.join(OUT, "medina_order_upload.xls");
  await download.saveAs(file);
  mark("downloaded");
  await sleep(1200);
  await moveClick(page, widgetButton(page, "Свернуть"));
  await sleep(800);
  await moveClick(page, page.locator('.tabs button[data-tab="upload"]'));
  await page.locator("#upload-file").setInputFiles(file);
  await sleep(700);
  await moveClick(page, page.locator("#upload-form button"));
  await page.locator(".alert.ok").waitFor();
  mark("upload_ok");
  await sleep(2500);
  await moveClick(page, page.locator('.tabs button[data-tab="cart"]'));
  mark("cart");
  await sleep(3500);
  mark("end");
});

// 3. Photo of a handwritten list.
await scene(browser, "photo", async (page, mark) => {
  await openDemo(page);
  await moveClick(page, launcher(page));
  await sleep(1200);
  mark("start");
  const n = await replies(page);
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), moveClick(page, widgetButton(page, "Прикрепить файл"))]);
  await chooser.setFiles(path.join(ASSETS, "spisok_foto.png"));
  mark("attached");
  await sleep(1500);
  await moveClick(page, widgetButton(page, "Отправить"));
  mark("sent");
  await waitReply(page, n);
  mark("reply");
  await readReply(page, 3000);
  mark("end");
});

// 4. Kazakh interface and a Kazakh order.
await scene(browser, "kazakh", async (page, mark) => {
  await openDemo(page);
  await moveClick(page, launcher(page));
  await sleep(1000);
  mark("start");
  await moveClick(page, page.locator("#medina-root button", { hasText: /^KZ$/ }).first());
  mark("kz_ui");
  await sleep(2500);
  const n = await replies(page);
  const area = page.locator("#medina-root textarea");
  await moveClick(page, area);
  await area.pressSequentially("Сәлеметсіз бе! Керек: нурофен 200 таб 10 қорап, аквадетрим 5 дана, амоксиклав 875 3 қорап", { delay: WARM ? 0 : 35 });
  await sleep(600);
  await moveClick(page, page.locator('#medina-root button[aria-label="Жіберу"]').first());
  mark("sent");
  await waitReply(page, n);
  mark("reply");
  await readReply(page, 3000);
  mark("end");
});

// 5. Reorder suggestions for the cold season.
await scene(browser, "reorder", async (page, mark) => {
  await openDemo(page);
  await moveClick(page, launcher(page));
  await sleep(1200);
  mark("start");
  const n = await replies(page);
  await moveClick(page, page.locator("#medina-root .m-card").nth(3));
  mark("sent");
  await waitReply(page, n);
  mark("reply");
  await readReply(page, 3000);
  mark("end");
});

// 6. Out-of-stock item in the catalog -> analogs.
await scene(browser, "analogs", async (page, mark) => {
  await openDemo(page);
  mark("start");
  const btn = page.locator("button[data-analogs]").first();
  await btn.scrollIntoViewIfNeeded();
  await sleep(1500);
  mark("out_of_stock");
  const n = await replies(page);
  await moveClick(page, btn);
  mark("sent");
  await waitReply(page, n);
  mark("reply");
  await readReply(page, 3000);
  mark("end");
});

await browser.close();
if (!WARM) {
  const tlFile = path.join(OUT, "timeline.json");
  const prev = fs.existsSync(tlFile) ? JSON.parse(fs.readFileSync(tlFile, "utf8")) : {};
  fs.writeFileSync(tlFile, JSON.stringify({ ...prev, ...timeline }, null, 2));
  console.log("timeline written");
}
