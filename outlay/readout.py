"""VP-ready audit readout — a self-contained, printable HTML one-pager.

The pilot deliverable. `report.py` is a terminal dump for an engineer; this is the
one screen a VP/Finance lead reads in 30 seconds and forwards — the artifact that
turns a design-partner audit into a referenceable proof point. It renders from the
same `serialize.to_dict` payload, so it's decoupled and testable, and it's a
single file (inline CSS, web fonts) that prints straight to PDF from any browser.

On-brand with outlay-ai.com: Fraunces display, Inter body, tabular numerals,
green = in-budget / amber = watch / red = over.
"""

from __future__ import annotations

from datetime import date


def _esc(s: object) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _usd(x: float) -> str:
    x = float(x)
    if abs(x) >= 1000:
        return f"${x:,.0f}"
    if abs(x) >= 1:
        return f"${x:,.2f}"
    return f"${x:.4f}"


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _bar(frac: float, color: str) -> str:
    w = max(0.0, min(1.0, frac)) * 100
    return (
        f'<div class="bar"><span style="width:{w:.1f}%;background:{color}"></span></div>'
    )


def render_html(
    report: dict,
    *,
    company: str | None = None,
    generated: str | None = None,
) -> str:
    """Render the report dict (from `serialize.to_dict`) as a standalone HTML page."""
    company = company or "Your team"
    generated = generated or date.today().isoformat()
    window = report.get("window_days")
    window_str = f"last {window} days" if window else "observed window"

    spend = report["spend"]
    fc = report["forecast"]
    recs = report.get("recommendations", [])
    anomalies = report.get("anomalies", [])
    cal = report.get("calibration")

    total = spend["total_usd"]
    coverage = spend["ticket_coverage"]
    savings_total = sum(r["projected_savings_usd"] for r in recs)

    cov_color = "var(--grn)" if coverage >= 0.6 else "var(--amber)"

    # --- KPI cards ---
    kpis = f"""
    <div class="kpis">
      <div class="kpi">
        <div class="k-label">Total AI spend ({_esc(window_str)})</div>
        <div class="k-val num">{_usd(total)}</div>
      </div>
      <div class="kpi">
        <div class="k-label">Mapped to a ticket</div>
        <div class="k-val num" style="color:{cov_color}">{_pct(coverage)}</div>
        <div class="k-sub num">{_usd(spend['attributed_to_ticket_usd'])} attributed</div>
      </div>
      <div class="kpi">
        <div class="k-label">Forecast · open work</div>
        <div class="k-val num">{_usd(fc['expected_usd'])}</div>
        <div class="k-sub num">likely {_usd(fc['low_usd'])}–{_usd(fc['high_usd'])}</div>
      </div>
      <div class="kpi">
        <div class="k-label">Savings opportunity</div>
        <div class="k-val num" style="color:var(--grn)">{_usd(savings_total)}</div>
        <div class="k-sub">across {len(recs)} work type(s)</div>
      </div>
    </div>"""

    # --- Where the spend went (top tickets) ---
    tickets = report.get("tickets", [])[:8]
    maxc = max((t["cost_usd"] for t in tickets), default=1.0) or 1.0
    ticket_rows = "".join(
        f"""<tr>
          <td class="mono">{_esc(t['ticket_id'])}</td>
          <td>{_esc(t['task_class'])}</td>
          <td>{_esc(t['status'])}</td>
          <td class="r num">{_usd(t['cost_usd'])}</td>
          <td class="barcell">{_bar(t['cost_usd'] / maxc, 'var(--ink)')}</td>
        </tr>"""
        for t in tickets
    ) or '<tr><td colspan="5" class="muted">No ticket-attributed spend in this window.</td></tr>'

    # --- Forecast by class ---
    by_class = fc.get("by_class_usd", {})
    fmax = max(by_class.values(), default=1.0) or 1.0
    class_rows = "".join(
        f"""<div class="cls-row">
          <span class="cls-name">{_esc(k)}</span>
          {_bar(v / fmax, 'var(--grn)')}
          <span class="num cls-amt">{_usd(v)}</span>
        </div>"""
        for k, v in sorted(by_class.items(), key=lambda kv: kv[1], reverse=True)
    ) or '<div class="muted">No costable open items.</div>'

    # --- Flags ---
    if anomalies:
        flag_items = "".join(
            f"""<li><span class="warn-dot">▲</span>
              <b class="mono">{_esc(a['ticket_id'])}</b> ({_esc(a['task_class'])})
              spent <b class="num">{_usd(a['cost_usd'])}</b> —
              <span class="num">{a['ratio']:.1f}×</span> its class median.</li>"""
            for a in anomalies[:5]
        )
        flags = f'<ul class="flags">{flag_items}</ul>'
    else:
        flags = '<p class="muted">No outlier tickets this window — spend is within normal range per work type.</p>'

    # --- Savings opportunity ---
    if recs:
        rec_rows = "".join(
            f"""<tr>
              <td>{_esc(r['task_class'])}</td>
              <td class="mono">{_esc(r['incumbent_model'])} → {_esc(r['candidate_model'])}</td>
              <td class="r num">{_usd(r['projected_savings_usd'])}</td>
              <td><span class="pill {'ok' if r['confidence'] == 'validated' else 'watch'}">
                {'validated' if r['confidence'] == 'validated' else 'needs validation'}</span></td>
            </tr>"""
            for r in recs
        )
        savings_block = f"""
        <table class="tbl">
          <thead><tr><th>Work type</th><th>Suggested routing</th><th class="r">Est. savings</th><th>Confidence</th></tr></thead>
          <tbody>{rec_rows}</tbody>
        </table>"""
    else:
        savings_block = '<p class="muted">No downgrade opportunities detected in this window.</p>'

    # --- Accuracy (trust line) ---
    accuracy_block = ""
    if cal and cal.get("n_evaluated", 0) > 0:
        acc = cal["accuracy"]
        size = cal.get("size")
        size_line = ""
        if size and size.get("improves"):
            size_line = (
                f" Conditioning on work size cut estimate error "
                f"{_pct(size['error_reduction'])} on your data."
            )
        accuracy_block = f"""
        <div class="trust">
          <b>Forecast accuracy (measured on your history):</b> the median estimate lands within
          ~<span class="num">{_pct(cal['mdape'])}</span> of actual
          (backtested on {cal['n_evaluated']} closed tickets).{_esc(size_line)}
          We measure this rather than assert it — and report coverage where we can't.
        </div>"""

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Spend Audit — {_esc(company)} · Outlay</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;450;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{{
    --ink:#0c0e12; --body:#3b414c; --mut:#7b818d; --faint:#a4a9b3;
    --line:#e8e6df; --line2:#f0eee7; --paper:#fbfaf6; --paper2:#f6f4ed;
    --navy:#13203a; --grn:#0f6b4f; --grn-d:#0a4f3a; --grn-l:#e7f1ec;
    --amber:#b45309; --amber-l:#fbf0df; --red:#b3261e;
    --disp:"Fraunces",Georgia,serif; --sans:"Inter",-apple-system,system-ui,sans-serif;
    --mono:ui-monospace,Menlo,Consolas,monospace;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:var(--sans);color:var(--body);background:var(--paper2);
    font-size:14.5px;line-height:1.55;-webkit-font-smoothing:antialiased}}
  .num{{font-variant-numeric:tabular-nums lining-nums}}
  .mono{{font-family:var(--mono);font-size:.92em}}
  .muted{{color:var(--mut)}}
  .sheet{{max-width:900px;margin:24px auto;background:#fff;border:1px solid var(--line);
    border-radius:16px;padding:40px 44px;box-shadow:0 30px 60px -40px rgba(19,32,58,.35)}}
  .mast{{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:24px}}
  .brand{{font-family:var(--disp);font-weight:700;font-size:24px;color:var(--ink);letter-spacing:-.02em}}
  .brand .dot{{color:var(--grn)}}
  .mast .ey{{font-family:var(--sans);font-size:11.5px;font-weight:600;letter-spacing:.13em;text-transform:uppercase;color:var(--grn);margin-top:6px}}
  .mast h1{{font-family:var(--disp);font-size:26px;color:var(--ink);margin:4px 0 0;letter-spacing:-.015em}}
  .mast .meta{{text-align:right;font-size:12.5px;color:var(--mut);line-height:1.7}}
  .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}}
  .kpi{{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
  .k-label{{font-size:11px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;color:var(--mut)}}
  .k-val{{font-family:var(--disp);font-weight:700;font-size:26px;color:var(--ink);letter-spacing:-.02em;margin-top:6px;line-height:1.1}}
  .k-sub{{font-size:12px;color:var(--mut);margin-top:3px}}
  h2{{font-family:var(--disp);font-size:17px;color:var(--ink);font-weight:600;margin:26px 0 12px;letter-spacing:-.01em}}
  .tbl{{width:100%;border-collapse:collapse;font-size:13.5px}}
  .tbl th{{text-align:left;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--mut);padding:7px 10px;border-bottom:1px solid var(--line)}}
  .tbl td{{padding:8px 10px;border-bottom:1px solid var(--line2);vertical-align:middle}}
  .tbl td.r,.tbl th.r{{text-align:right}}
  .tbl tr:last-child td{{border-bottom:none}}
  .barcell{{width:130px}}
  .bar{{height:7px;border-radius:5px;background:#eceae3;overflow:hidden}}
  .bar>span{{display:block;height:100%;border-radius:5px}}
  .cls-row{{display:grid;grid-template-columns:120px 1fr 80px;align-items:center;gap:12px;padding:5px 0}}
  .cls-name{{font-size:13px;color:var(--ink);font-weight:500}}
  .cls-amt{{text-align:right;font-size:13px;font-weight:600;color:var(--ink)}}
  .flags{{list-style:none;padding:0;margin:0;display:grid;gap:8px}}
  .flags li{{font-size:13.5px}}
  .warn-dot{{color:var(--amber);font-weight:700;margin-right:6px}}
  .pill{{font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;border-radius:999px;padding:2px 8px}}
  .pill.ok{{color:var(--grn-d);background:var(--grn-l)}}
  .pill.watch{{color:var(--amber);background:var(--amber-l)}}
  .cols{{display:grid;grid-template-columns:1fr 1fr;gap:28px}}
  .trust{{background:var(--grn-l);border:1px solid #cfe3d8;border-radius:12px;padding:14px 16px;font-size:13px;color:var(--grn-d);margin-top:8px}}
  .foot{{border-top:1px solid var(--line);margin-top:28px;padding-top:16px;font-size:11.5px;color:var(--mut);display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}}
  @media(max-width:720px){{.kpis{{grid-template-columns:1fr 1fr}}.cols{{grid-template-columns:1fr}}}}
  @media print{{body{{background:#fff}}.sheet{{box-shadow:none;border:none;margin:0;max-width:none;border-radius:0}}}}
</style>
</head>
<body>
<div class="sheet">
  <div class="mast">
    <div>
      <div class="brand">Out<span class="dot">lay</span></div>
      <div class="ey">AI spend audit</div>
      <h1>{_esc(company)}</h1>
    </div>
    <div class="meta">
      Generated {_esc(generated)}<br>{_esc(window_str)}<br>
      <span style="color:var(--grn)">Read-only · metadata only</span>
    </div>
  </div>

  {kpis}

  <div class="cols">
    <div>
      <h2>Where your AI spend went</h2>
      <table class="tbl">
        <thead><tr><th>Ticket</th><th>Type</th><th>Status</th><th class="r">Cost</th><th></th></tr></thead>
        <tbody>{ticket_rows}</tbody>
      </table>
    </div>
    <div>
      <h2>Forecast for open work</h2>
      {class_rows}
      <p class="muted" style="font-size:12px;margin-top:12px">
        {fc['items_costed']} open items costed; {fc['items_unclassified']} had no history (not costed).
        Likely total {_usd(fc['low_usd'])}–{_usd(fc['high_usd'])}.
      </p>
    </div>
  </div>

  <h2>Flags</h2>
  {flags}

  <h2>Savings opportunity</h2>
  {savings_block}

  {accuracy_block}

  <div class="foot">
    <span>Outlay · budget AI spend by scope of work · outlay-ai.com</span>
    <span>Prompts, outputs &amp; keys never left {_esc(company)}'s environment.</span>
  </div>
</div>
</body></html>
"""
