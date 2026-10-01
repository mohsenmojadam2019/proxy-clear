const api = globalThis.browser || globalThis.chrome;
const NATIVE_HOST = "com.proxyclear.helper";

function isFirefox() {
  return typeof globalThis.browser !== "undefined" &&
    globalThis.browser.runtime &&
    typeof globalThis.browser.runtime.getBrowserInfo === "function";
}

function chromeCall(fn, context, arg) {
  return new Promise((resolve, reject) => {
    try {
      fn.call(context, arg, (result) => {
        const err = chrome.runtime && chrome.runtime.lastError;
        if (err) reject(new Error(err.message));
        else resolve(result);
      });
    } catch (error) {
      reject(error);
    }
  });
}

async function getBrowserProxy() {
  if (!api.proxy || !api.proxy.settings) {
    return { supported: false, reason: "proxy API is unavailable" };
  }
  let current;
  if (isFirefox()) current = await api.proxy.settings.get({});
  else current = await chromeCall(api.proxy.settings.get, api.proxy.settings, {});
  const value = current && current.value ? current.value : {};
  return {
    supported: true,
    browser: isFirefox() ? "firefox" : "chromium",
    mode: value.proxyType || value.mode || "unknown",
    levelOfControl: current && current.levelOfControl ? current.levelOfControl : null,
    value
  };
}

async function setBrowserDirect() {
  if (!api.proxy || !api.proxy.settings) {
    return { ok: false, reason: "proxy API is unavailable" };
  }
  if (isFirefox()) {
    await api.proxy.settings.set({ value: { proxyType: "none" } });
  } else {
    await chromeCall(api.proxy.settings.set, api.proxy.settings, {
      value: { mode: "direct" },
      scope: "regular"
    });
    try {
      await chromeCall(api.proxy.settings.set, api.proxy.settings, {
        value: { mode: "direct" },
        scope: "incognito_persistent"
      });
    } catch (_) {}
  }
  return { ok: true, state: await getBrowserProxy() };
}

async function sendNative(message) {
  if (isFirefox()) return await api.runtime.sendNativeMessage(NATIVE_HOST, message);
  return await new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage(NATIVE_HOST, message, (response) => {
      const err = chrome.runtime.lastError;
      if (err) reject(new Error(err.message));
      else resolve(response);
    });
  });
}

async function setBadge(ok) {
  if (!api.action || !api.action.setBadgeText) return;
  try {
    const payload = { text: ok ? "OK" : "!" };
    if (isFirefox()) await api.action.setBadgeText(payload);
    else await chromeCall(api.action.setBadgeText, api.action, payload);
  } catch (_) {}
}

async function handle(action) {
  if (action === "scan") {
    const [browserState, nativeState] = await Promise.all([
      getBrowserProxy(),
      sendNative({ action: "scan" })
    ]);
    const result = { ok: true, browser: browserState, system: nativeState };
    await setBadge(nativeState && nativeState.ok !== false);
    return result;
  }
  if (action === "clear") {
    const browserResult = await setBrowserDirect();
    const nativeResult = await sendNative({ action: "clear" });
    const ok = browserResult.ok && nativeResult && nativeResult.ok !== false;
    await setBadge(ok);
    return { ok, browser: browserResult, system: nativeResult };
  }
  throw new Error("Unknown action: " + action);
}

api.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !["scan", "clear"].includes(message.action)) return false;
  handle(message.action)
    .then((result) => sendResponse(result))
    .catch((error) => sendResponse({ ok: false, error: String(error.message || error) }));
  return true;
});

api.runtime.onInstalled.addListener(() => {
  handle("scan").catch(() => setBadge(false));
});
