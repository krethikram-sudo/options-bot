"""Interactive chat playground: type prompts, watch the routing and savings.

  GET  /modelpilot/chat       — browser chat UI (vanilla JS, no CDN deps)
  POST /modelpilot/chat/send  — sends the conversation through this gateway's
                                own /v1/messages pipeline, so every message is
                                routed, ledgered, and visible on the dashboard

The send endpoint loops back through the gateway's public endpoint rather
than duplicating routing logic — what you see in the chat is exactly what a
customer's traffic experiences. API key comes from the gateway's environment
(ANTHROPIC_API_KEY) or, failing that, an x-api-key header supplied by the
page (kept in browser localStorage, never persisted server-side).
"""

import os
import uuid

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .pricing import Usage, request_cost

router = APIRouter()


@router.post("/modelpilot/chat/send")
async def chat_send(request: Request):
    payload = await request.json()
    messages = payload.get("messages") or []
    baseline = payload.get("model") or "claude-opus-4-8"
    session_id = payload.get("session_id") or f"chat-{uuid.uuid4().hex[:8]}"
    api_key = request.headers.get("x-api-key") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return JSONResponse({"error": "No API key. Set ANTHROPIC_API_KEY on the gateway, "
                                      "or paste a key into the key field on this page."},
                            status_code=400)

    # In-process loopback through the gateway's own /v1/messages route, so the
    # chat exercises the exact pipeline customer traffic does (routing, ledger,
    # holdout, headers) — no network hop, no dependence on the Host header.
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport,
                                 base_url="http://modelpilot.internal",
                                 timeout=180.0) as loopback:
        resp = await loopback.post(
            "/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "x-session-id": session_id},
            json={"model": baseline, "max_tokens": 1024, "messages": messages},
        )
    if resp.status_code != 200:
        return JSONResponse({"error": f"API error {resp.status_code}: {resp.text[:300]}"},
                            status_code=resp.status_code)

    data = resp.json()
    h = resp.headers
    ran_on = data.get("model", baseline)
    usage = Usage.from_api(data.get("usage") or {})
    cost_actual = request_cost(ran_on, usage) or 0.0
    cost_baseline = request_cost(baseline, usage) or 0.0
    recommended = h.get("x-modelpilot-recommended-model", baseline)
    cost_recommended = request_cost(recommended, usage) or cost_baseline
    applied = ran_on != baseline
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    return {
        "text": text,
        "session_id": session_id,
        "mode": h.get("x-modelpilot-mode", ""),
        "baseline_model": baseline,
        "ran_on": ran_on,
        "recommended_model": recommended,
        "action": h.get("x-modelpilot-action", "stay"),
        "applied": applied,
        "arm": h.get("x-modelpilot-arm", ""),
        "confidence": h.get("x-modelpilot-confidence", ""),
        "category": h.get("x-modelpilot-category", ""),
        "cost_actual": cost_actual,
        "cost_baseline": cost_baseline,
        "saved": (cost_baseline - cost_actual) if applied else 0.0,
        "potential": max(cost_baseline - cost_recommended, 0.0),
        "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
    }


@router.get("/modelpilot/chat")
async def chat_page():
    mode = os.environ.get("MODELPILOT_MODE", "shadow")
    return HTMLResponse(_PAGE.replace("__MODE__", mode))


_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>ModelPilot — chat playground</title>
<style>
  body { font: 15px/1.5 -apple-system, "Segoe UI", sans-serif; margin: 0; color: #1f2430;
         display: flex; flex-direction: column; height: 100vh; }
  header { display: flex; align-items: baseline; gap: 14px; padding: 10px 18px;
           border-bottom: 1px solid #e3e3e8; }
  header h1 { font-size: 1.05rem; margin: 0; }
  #ticker { margin-left: auto; font-weight: 600; color: #2e9e5b; }
  #ticker .muted { color: #6b7080; font-weight: 400; font-size: 0.85rem; }
  header a { color: #2f6fb6; font-size: 0.85rem; }
  #log { flex: 1; overflow-y: auto; padding: 16px 18px; }
  .msg { max-width: 760px; margin: 0 auto 14px; }
  .who { font-size: 0.75rem; color: #6b7080; margin-bottom: 2px; }
  .bubble { white-space: pre-wrap; border-radius: 10px; padding: 10px 14px; }
  .user .bubble { background: #eef3fa; }
  .assistant .bubble { background: #f6f7f9; }
  .meta { font-size: 0.78rem; margin-top: 4px; padding: 5px 10px; border-radius: 6px;
          background: #f0faf3; color: #1f2430; border: 1px solid #d8efe0; }
  .meta.stay { background: #f6f7f9; border-color: #e3e3e8; color: #6b7080; }
  .meta.pre { background: #fff8e8; border-color: #f0e2b8; }
  #modebadge { font-size: 0.72rem; padding: 2px 8px; border-radius: 10px; background: #eef3fa;
               color: #2f6fb6; text-transform: uppercase; letter-spacing: 0.04em; }
  .meta b.save { color: #2e9e5b; }
  .meta .model { font-weight: 600; }
  form { display: flex; gap: 8px; padding: 12px 18px; border-top: 1px solid #e3e3e8; }
  textarea { flex: 1; font: inherit; padding: 9px 12px; border: 1px solid #ccd; border-radius: 8px;
             resize: none; height: 3em; }
  button { font: inherit; padding: 0 22px; border: 0; border-radius: 8px;
           background: #2f6fb6; color: #fff; cursor: pointer; }
  button:disabled { background: #aab; }
  select, input[type=password] { font: inherit; font-size: 0.82rem; padding: 4px 6px;
           border: 1px solid #ccd; border-radius: 6px; }
  details { font-size: 0.8rem; color: #6b7080; }
  .error { color: #b3372f; }
</style></head><body>
<header>
  <h1>ModelPilot chat</h1>
  <span id="modebadge">__MODE__</span>
  <label>baseline:
    <select id="model">
      <option>claude-opus-4-8</option>
      <option>claude-fable-5</option>
      <option>claude-sonnet-4-6</option>
    </select>
  </label>
  <details><summary>API key</summary>
    <input type="password" id="key" placeholder="only if gateway has none">
  </details>
  <div id="ticker">saved $0.0000 <span class="muted">this session</span></div>
  <a href="/modelpilot/dashboard?days=0" target="_blank" id="dash">dashboard ↗</a>
</header>
<div id="log"></div>
<form id="form">
  <textarea id="box" placeholder="Type a prompt — try 'Classify this review as positive or negative: great product!' then something hard, and compare the meta lines"></textarea>
  <button id="send">Send</button>
</form>
<script>
const log = document.getElementById('log'), box = document.getElementById('box');
const form = document.getElementById('form'), send = document.getElementById('send');
const keyEl = document.getElementById('key');
keyEl.value = localStorage.getItem('mp_key') || '';
let messages = [], saved = 0, potential = 0;
const sessionId = 'chat-' + Math.random().toString(36).slice(2, 10);
// Deep-link the dashboard to THIS conversation's live view.
document.getElementById('dash').href = '/modelpilot/dashboard?days=0&session=' + sessionId;
const usd = x => '$' + x.toFixed(4);

function bubble(who, text) {
  const d = document.createElement('div');
  d.className = 'msg ' + who;
  d.innerHTML = '<div class="who">' + (who === 'user' ? 'you' : 'claude') + '</div>';
  const b = document.createElement('div'); b.className = 'bubble'; b.textContent = text;
  d.appendChild(b); log.appendChild(d); log.scrollTop = log.scrollHeight;
  return d;
}

// Pre-execution: the routing decision, shown the moment you hit send —
// BEFORE the model generates anything.
function preMeta(chip, p) {
  chip.className = 'meta pre';
  let line;
  if (p.applied) {
    line = '⚡ ModelPilot selected <span class="model">' + p.will_run_on +
           '</span> for this prompt — <b class="save">est. saving ~' + usd(p.est_saved) +
           '</b> · generating…';
  } else if (p.action === 'switch') {
    line = (p.arm === 'control'
            ? '🎯 holdout control — running ' + p.baseline_model + ' for measurement'
            : '💡 ' + p.mode + ' mode: recommends ' + p.recommended_model +
              ' (~' + usd(p.est_potential) + ') — running ' + p.baseline_model) +
           ' · generating…';
  } else {
    line = '🛡 keeping <span class="model">' + p.baseline_model + '</span> — ' +
           (p.category || 'this task') + ' needs it · generating…';
  }
  chip.innerHTML = line + ' <span style="color:#6b7080">· ' + p.category +
                   ' · conf ' + p.confidence + '</span>';
  log.scrollTop = log.scrollHeight;
}

// Post-execution: the same chip updates with what actually happened.
function meta(chip, r) {
  const switched = r.applied;
  chip.className = 'meta' + (switched ? '' : ' stay');
  let line;
  if (switched) {
    line = '⚡ ran on <span class="model">' + r.ran_on + '</span> — cost ' + usd(r.cost_actual) +
           ' vs ' + usd(r.cost_baseline) + ' on ' + r.baseline_model +
           ' → <b class="save">saved ' + usd(r.saved) + '</b>';
  } else if (r.action === 'switch') {
    line = 'ran on <span class="model">' + r.ran_on + '</span> (' +
           (r.arm === 'control' ? 'holdout control' : r.mode + ' mode — not switched') +
           ') — recommends ' + r.recommended_model +
           ', would save <b class="save">' + usd(r.potential) + '</b>';
  } else {
    line = '🛡 stayed on <span class="model">' + r.ran_on + '</span> — ' +
           (r.category || 'this') + ' needs it (conf ' + r.confidence + ')';
  }
  chip.innerHTML = line + ' <span style="color:#6b7080">· ' + r.category +
                   ' · conf ' + r.confidence + ' · ' + r.usage.input_tokens + '→' +
                   r.usage.output_tokens + ' tok</span>';
  log.scrollTop = log.scrollHeight;
}

form.onsubmit = async (e) => {
  e.preventDefault();
  const text = box.value.trim();
  if (!text) return;
  localStorage.setItem('mp_key', keyEl.value);
  box.value = ''; send.disabled = true;
  bubble('user', text);
  messages.push({role: 'user', content: text});
  const thinking = bubble('assistant', '…');
  const chip = document.createElement('div');
  chip.className = 'meta pre';
  chip.textContent = 'routing…';
  thinking.appendChild(chip);
  const model = document.getElementById('model').value;

  // 1. Pre-execution: ask the gateway which model WILL run this prompt.
  //    Deterministic, so it matches what the send below actually does.
  try {
    const pv = await fetch('/modelpilot/preview', {
      method: 'POST', headers: {'content-type': 'application/json'},
      body: JSON.stringify({model, max_tokens: 1024, messages, session_id: sessionId}),
    });
    if (pv.ok) preMeta(chip, await pv.json());
  } catch (err) { /* preview is advisory — never blocks the send */ }

  // 2. Execute through the gateway; the chip updates with realized numbers.
  try {
    const resp = await fetch('/modelpilot/chat/send', {
      method: 'POST',
      headers: {'content-type': 'application/json',
                ...(keyEl.value ? {'x-api-key': keyEl.value} : {})},
      body: JSON.stringify({messages, model, session_id: sessionId}),
    });
    const r = await resp.json();
    if (!resp.ok) throw new Error(r.error || resp.status);
    thinking.querySelector('.bubble').textContent = r.text;
    messages.push({role: 'assistant', content: r.text});
    meta(chip, r);
    saved += r.saved; potential += r.potential;
    document.getElementById('ticker').innerHTML =
      'saved ' + usd(saved) + ' <span class="muted">this session' +
      (potential > saved ? ' · ' + usd(potential) + ' potential' : '') + '</span>';
  } catch (err) {
    thinking.querySelector('.bubble').innerHTML = '<span class="error">' + err.message + '</span>';
    chip.remove();
    messages.pop();
  }
  send.disabled = false; box.focus();
};
box.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } };
</script>
</body></html>
"""
