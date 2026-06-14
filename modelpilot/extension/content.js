// ModelPilot for Claude — advisory chip on claude.ai.
//
// Watches the composer; as you type, asks the local gateway which model this
// prompt needs and shows the recommendation + estimated savings BEFORE you
// send. Reads the visible transcript (best-effort) so the gateway's
// session-context routing applies. v0 is strictly advisory: it never touches
// the model picker or the request.
//
// claude.ai's DOM changes without notice — every selector below is a
// best-effort heuristic with fallbacks, and the chip degrades to silence
// rather than breaking the page.

(() => {
  const DEBOUNCE_MS = 700;
  const MODEL_IDS = {
    fable: "claude-fable-5",
    opus: "claude-opus-4-8",
    sonnet: "claude-sonnet-4-6",
    haiku: "claude-haiku-4-5",
  };

  // ---- chip UI --------------------------------------------------------------

  const chip = document.createElement("div");
  chip.id = "modelpilot-chip";
  chip.style.cssText = [
    "position:fixed", "right:18px", "bottom:96px", "z-index:99999",
    "max-width:340px", "padding:8px 12px", "border-radius:10px",
    "font:12px/1.45 -apple-system,'Segoe UI',sans-serif", "color:#1f2430",
    "background:#fff8e8", "border:1px solid #f0e2b8",
    "box-shadow:0 2px 10px rgba(0,0,0,0.12)", "display:none",
  ].join(";");
  document.documentElement.appendChild(chip);

  function showChip(html, palette) {
    const colors = {
      switch: ["#f0faf3", "#d8efe0"],
      stay: ["#f6f7f9", "#e3e3e8"],
      pre: ["#fff8e8", "#f0e2b8"],
      err: ["#fdf2f1", "#efc9c5"],
    }[palette] || ["#fff8e8", "#f0e2b8"];
    chip.style.background = colors[0];
    chip.style.borderColor = colors[1];
    chip.innerHTML = html;
    chip.style.display = "block";
  }

  const usd = (x) => "$" + (Math.abs(x) >= 0.01 ? x.toFixed(2) : x.toFixed(4));

  function sessionTotal(delta) {
    const key = "modelpilot-est-" + location.pathname;
    const total = (parseFloat(sessionStorage.getItem(key)) || 0) + (delta || 0);
    if (delta) sessionStorage.setItem(key, String(total));
    return total;
  }

  // ---- claude.ai DOM heuristics ----------------------------------------------

  function findComposer() {
    return (
      document.querySelector('div[contenteditable="true"][aria-label]') ||
      document.querySelector('div[contenteditable="true"]') ||
      document.querySelector("textarea")
    );
  }

  function draftText(composer) {
    return (composer.value !== undefined ? composer.value : composer.innerText || "").trim();
  }

  function currentBaseline() {
    // The model picker is a button whose label names the model. Scan small
    // buttons for a known model word; default to opus when not found.
    for (const btn of document.querySelectorAll("button")) {
      const label = (btn.innerText || "").toLowerCase();
      if (label.length > 60) continue;
      for (const word of Object.keys(MODEL_IDS)) {
        if (label.includes(word)) return MODEL_IDS[word];
      }
    }
    return MODEL_IDS.opus;
  }

  function visibleTranscript() {
    // Best-effort: claude.ai marks turns with data-testid on most builds.
    // Returns alternating-ish messages, capped, oldest first. Empty list is a
    // fine fallback — the gateway then routes on the draft alone.
    const nodes = document.querySelectorAll(
      '[data-testid="user-message"], [data-testid="assistant-message"], .font-claude-message'
    );
    const messages = [];
    for (const node of Array.from(nodes).slice(-12)) {
      const text = (node.innerText || "").trim().slice(0, 4000);
      if (!text) continue;
      const isUser = (node.getAttribute("data-testid") || "").includes("user");
      messages.push({ role: isUser ? "user" : "assistant", content: text });
    }
    return messages;
  }

  // ---- preview flow -----------------------------------------------------------

  let timer = null;
  let lastDraft = "";

  function requestPreview(draft) {
    const baseline = currentBaseline();
    const messages = visibleTranscript();
    messages.push({ role: "user", content: draft });
    chrome.runtime.sendMessage(
      {
        type: "modelpilot-preview",
        body: {
          model: baseline,
          max_tokens: 1024,
          messages,
          session_id: "claudeai-" + location.pathname,
        },
      },
      (resp) => {
        if (chrome.runtime.lastError || !resp || !resp.ok) {
          showChip(
            "<b>ModelPilot</b> · gateway offline — start it with " +
              "<code>./scripts/install_modelpilot_gateway.sh</code>",
            "err"
          );
          return;
        }
        render(resp.data, baseline);
      }
    );
  }

  function render(p, baseline) {
    const total = usd(sessionTotal(0));
    const meta =
      `<span style="color:#6b7080"> · ${p.category} · conf ${p.confidence}` +
      ` · est. value this chat: <b>${total}</b></span>`;
    if (p.action === "switch" && p.recommended_model !== baseline) {
      showChip(
        `<b>ModelPilot</b> · 💡 <b>${p.recommended_model}</b> is enough for this prompt — ` +
          `est. ${usd(p.est_potential)} of ${baseline.replace("claude-", "")} usage saved ` +
          `if you switch the picker${meta}`,
        "switch"
      );
    } else {
      showChip(
        `<b>ModelPilot</b> · 🛡 ${baseline.replace("claude-", "")} is the right call here${meta}`,
        "stay"
      );
    }
  }

  // When a send happens (draft clears), bank the last estimate into the ticker.
  let lastEstimate = 0;

  function onInput() {
    const composer = findComposer();
    if (!composer) return;
    const draft = draftText(composer);
    if (draft === lastDraft) return;
    if (lastDraft && !draft && lastEstimate > 0) {
      sessionTotal(lastEstimate); // message was sent — accumulate
      lastEstimate = 0;
    }
    lastDraft = draft;
    clearTimeout(timer);
    if (draft.length < 8) {
      chip.style.display = "none";
      return;
    }
    timer = setTimeout(() => {
      requestPreview(draft);
    }, DEBOUNCE_MS);
  }

  // Track the latest estimate so it can be banked on send.
  const origRender = render;
  render = (p, baseline) => {
    lastEstimate = p.action === "switch" ? p.est_potential || 0 : 0;
    origRender(p, baseline);
  };

  // The composer is re-created on navigation; observe rather than bind once.
  document.addEventListener("input", onInput, true);
  new MutationObserver(() => {
    if (!findComposer()) chip.style.display = "none";
  }).observe(document.body, { childList: true, subtree: true });
})();
