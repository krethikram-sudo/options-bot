// Service worker: proxies preview calls to the local gateway. Content scripts
// are subject to the page's CORS; the worker fetches under host_permissions.

const GATEWAY = "http://127.0.0.1:8400";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "modelpilot-preview") return;
  fetch(`${GATEWAY}/modelpilot/preview`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(msg.body),
  })
    .then((r) => r.json())
    .then((data) => sendResponse({ ok: true, data }))
    .catch((err) => sendResponse({ ok: false, error: String(err) }));
  return true; // keep the message channel open for the async response
});
