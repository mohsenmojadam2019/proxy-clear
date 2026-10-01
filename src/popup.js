const api = globalThis.browser || globalThis.chrome;
const clearBtn = document.getElementById("clearBtn");
const scanBtn = document.getElementById("scanBtn");
const title = document.getElementById("statusTitle");
const text = document.getElementById("statusText");
const details = document.getElementById("details");
const dot = document.getElementById("dot");

function runtimeSend(message) {
  if (typeof browser !== "undefined") return browser.runtime.sendMessage(message);
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      const err = chrome.runtime.lastError;
      if (err) reject(new Error(err.message));
      else resolve(response);
    });
  });
}

function setBusy(busy) {
  clearBtn.disabled = busy;
  scanBtn.disabled = busy;
}

function summarize(result) {
  if (!result || result.ok === false) {
    dot.className = "status-dot bad";
    title.textContent = "خطا در بررسی";
    text.textContent = result && result.error ? result.error : "پاسخ معتبر دریافت نشد.";
    details.textContent = JSON.stringify(result || {}, null, 2);
    return;
  }
  const browserMode = result.browser && result.browser.mode
    ? result.browser.mode
    : result.browser && result.browser.state && result.browser.state.mode
      ? result.browser.state.mode
      : "unknown";
  const sys = result.system || {};
  const findings = sys.scan && Array.isArray(sys.scan.findings) ? sys.scan.findings.length : 0;
  const rootFindings = sys.scan && sys.scan.system && Array.isArray(sys.scan.system.findings)
    ? sys.scan.system.findings.length
    : 0;
  const total = findings + rootFindings;
  const direct = ["direct", "none"].includes(browserMode);

  dot.className = "status-dot " + (direct && total === 0 ? "good" : "warn");
  title.textContent = direct && total === 0 ? "Proxy پاک است" : "Proxy یا تنظیم باقی‌مانده پیدا شد";
  text.textContent = "Browser: " + browserMode + " | موارد سیستم: " + total;
  details.textContent = JSON.stringify(result, null, 2);
}

async function scan() {
  setBusy(true);
  title.textContent = "در حال بررسی…";
  text.textContent = "Chrome / Firefox / GNOME / فایل‌های سیستم";
  try { summarize(await runtimeSend({ action: "scan" })); }
  catch (error) { summarize({ ok: false, error: error.message }); }
  finally { setBusy(false); }
}

async function clearAll() {
  setBusy(true);
  title.textContent = "در حال پاک‌سازی…";
  text.textContent = "تنظیمات Proxy حذف و حالت Direct فعال می‌شود.";
  try { summarize(await runtimeSend({ action: "clear" })); }
  catch (error) { summarize({ ok: false, error: error.message }); }
  finally { setBusy(false); }
}

clearBtn.addEventListener("click", clearAll);
scanBtn.addEventListener("click", scan);
scan();
