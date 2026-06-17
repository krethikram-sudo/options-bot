#!/usr/bin/env python3
"""Generate ModelPilot sales collateral PDFs (tables) from the canonical data.

Produces:
  - ModelPilot-Where-We-Save-Customer.pdf  (customer-facing one-slide: savings by
    work type with cut-vs-Opus and cut-vs-Sonnet, + which teams it saves for)
  - ModelPilot-Personas-UseCases.pdf       (internal: full fitness map incl. the
    protected categories)

Keep the data tables below in sync with `modelpilot/PERSONAS_USECASES.md`
(measured per-category numbers come from `modelpilot.goldenset.evaluate`).

Requires: pip install reportlab
Usage: python scripts/make_sales_pdfs.py [--out DIR]
"""
import argparse
import os
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle

INK = colors.HexColor("#0a0a0a"); VIO = colors.HexColor("#6d28d9")
MUT = colors.HexColor("#6b6b72"); GRN = colors.HexColor("#166534")
GREEN = colors.HexColor("#dcfce7"); AMBER = colors.HexColor("#fef3c7"); RED = colors.HexColor("#fee2e2")
_ss = getSampleStyleSheet()


def _styles():
    return {
        "H1": ParagraphStyle('H1', parent=_ss['Title'], fontSize=18, textColor=INK, spaceAfter=2, leading=22),
        "H2": ParagraphStyle('H2', parent=_ss['Heading2'], fontSize=12.5, textColor=VIO, spaceBefore=13, spaceAfter=6, leading=15),
        "sub": ParagraphStyle('sub', parent=_ss['BodyText'], fontSize=9.5, textColor=MUT, spaceAfter=9, leading=12.5),
        "cell": ParagraphStyle('cell', parent=_ss['BodyText'], fontSize=9, leading=11.5, textColor=INK),
        "cellb": ParagraphStyle('cellb', parent=_ss['BodyText'], fontSize=9, leading=11.5, textColor=INK, fontName='Helvetica-Bold'),
        "cg": ParagraphStyle('cg', parent=_ss['BodyText'], fontSize=9, leading=11.5, textColor=GRN, fontName='Helvetica-Bold'),
        "hd": ParagraphStyle('hd', parent=_ss['BodyText'], fontSize=9, leading=11.5, textColor=colors.white, fontName='Helvetica-Bold'),
        "note": ParagraphStyle('note', parent=_ss['BodyText'], fontSize=8, textColor=MUT, leading=11, spaceBefore=6),
    }


def _grid(header_bg=VIO):
    return [('BACKGROUND', (0, 0), (-1, 0), header_bg), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e3e3e7")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5)]


# --- canonical data (keep in sync with PERSONAS_USECASES.md) ---
# (work type, routes_to, routed%, cut_vs_opus, cut_vs_sonnet, bucket)
SAVINGS = [
    ("Short Q&A / lookups", "Haiku", "100%", "~80%", "~67%", "g"),
    ("Simple code / SQL", "Haiku", "100%", "~80%", "~67%", "g"),
    ("Rewrite / reformat", "Haiku", "91%", "~73%", "~61%", "g"),
    ("Data / field extraction", "Haiku", "89%", "~71%", "~59%", "g"),
    ("Translation", "Haiku", "87%", "~70%", "~58%", "g"),
    ("Classification / triage", "Haiku", "85%", "~68%", "~57%", "g"),
    ("Summaries (short)", "Haiku", "75%", "~60%", "~50%", "g"),
    ("Summaries (long / dense)", "Sonnet", "66%", "~26%", "—", "a"),
    ("Conversation / advice", "Sonnet", "40%", "~16%", "—", "a"),
]
PERSONAS = [
    ("Customer support / CX (+ support-AI products)", "triage/intent, ticket & thread summaries, draft replies, FAQ Q&A, translation"),
    ("Operations / back-office / data entry", "document & form extraction, routing/tagging classification"),
    ("Legal / claims / clinical / compliance ops", "contract & record extraction, document summaries, classification"),
    ("Sales / marketing ops", "first-draft emails/copy, lead enrichment & extraction, summaries, translation"),
    ("Analysts & engineers (routine work)", "simple SQL & queries, data extraction, snippets, lookups"),
]
PROTECTED = "Complex coding, debugging, math, agents, open-ended analysis, creative long-form — kept on the top model (quality protected, ~0 savings)."


def build_customer(outdir):
    s = _styles(); out = os.path.join(outdir, "ModelPilot-Where-We-Save-Customer.pdf")
    doc = SimpleDocTemplate(out, pagesize=landscape(letter), leftMargin=0.55 * inch, rightMargin=0.55 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.45 * inch, title="ModelPilot — Where we cut your Claude bill")
    P = lambda t, st="cell": Paragraph(t, s[st])
    fl = [Paragraph("Where ModelPilot cuts your Claude bill", s["H1"]),
          Paragraph("We route each request to the cheapest model that's good enough — and prove it on your own "
                    "traffic. These are the work types we route down; your hard reasoning stays on the top model.", s["sub"])]
    rows = [[P("Work type", "hd"), P("Routes to", "hd"), P("Typically routed", "hd"), P("Cut vs Opus", "hd"), P("Cut vs Sonnet", "hd")]]
    bg = []
    for i, (a, b, c, d, e, k) in enumerate(SAVINGS, 1):
        rows.append([P(a, "cellb"), P(b), P(c), P(d, "cg"), P(e, "cg")]); bg.append((i, GREEN if k == "g" else AMBER))
    t = Table(rows, colWidths=[2.5 * inch, 1.2 * inch, 1.5 * inch, 1.4 * inch, 1.4 * inch], repeatRows=1)
    st = _grid() + [('ALIGN', (2, 0), (-1, -1), 'CENTER')] + [('BACKGROUND', (0, i), (-1, i), c) for i, c in bg]
    t.setStyle(TableStyle(st)); fl.append(t)
    fl.append(Paragraph("Who on your team this saves for", s["H2"]))
    pr = [[P("Team / role", "hd"), P("The work we cut costs on", "hd")]]
    for a, b in PERSONAS:
        pr.append([P(a, "cellb"), P(b)])
    t2 = Table(pr, colWidths=[3.2 * inch, 6.2 * inch], repeatRows=1)
    t2.setStyle(TableStyle(_grid() + [('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f6fef9"))]))
    fl.append(t2)
    fl.append(Paragraph("Illustrative ranges at public list prices; your savings depend on your traffic mix and "
                        "current model. We measure the real number on your own traffic with a held-out control arm, "
                        "and you pay only a share of what we actually save (no savings, no bill).", s["note"]))
    doc.build(fl); print("wrote", out)


def build_personas(outdir):
    s = _styles(); out = os.path.join(outdir, "ModelPilot-Personas-UseCases.pdf")
    doc = SimpleDocTemplate(out, pagesize=landscape(letter), leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.45 * inch, title="ModelPilot — Personas & Use Cases")
    P = lambda t, st="cell": Paragraph(t, s[st])
    fl = [Paragraph("ModelPilot — what we optimize, and what we protect", s["H1"]),
          Paragraph("Internal. Savings categories (green/amber) route to a cheaper model; protected (red) stay on the "
                    "top model. 0% false-downgrade across all. Measured on a 147-prompt calibration set; real number "
                    "is per-customer via the control arm.", s["sub"])]
    full = [(a, b, "g") for (a, b, _, _, _, _) in []]  # placeholder removed below
    rows = [[P("Work type", "hd"), P("Routes to", "hd"), P("Routed", "hd"), P("Fitness", "hd")]]
    items = [(a, b, c, "STRONG" if k == "g" else "MODERATE", GREEN if k == "g" else AMBER) for (a, b, c, _, _, k) in SAVINGS]
    items += [("Complex coding", "Top model", "0%", "PROTECTED", RED), ("Debugging", "Top model", "0%", "PROTECTED", RED),
              ("Math / quant reasoning", "Top model", "0%", "PROTECTED", RED), ("Agentic / tool-use", "Top model", "0%", "PROTECTED", RED),
              ("Open-ended analysis / strategy", "Top model", "0%", "PROTECTED", RED), ("Creative long-form", "Sonnet floor", "0%", "PROTECTED", RED)]
    bg = []
    for i, (a, routes, routed, fit, col) in enumerate(items, 1):
        rows.append([P(a, "cellb"), P(routes), P(routed), P(fit, "cellb")]); bg.append((i, col))
    t = Table(rows, colWidths=[2.6 * inch, 1.4 * inch, 1.0 * inch, 1.4 * inch], repeatRows=1)
    st = _grid() + [('ALIGN', (2, 0), (2, -1), 'CENTER')] + [('BACKGROUND', (3, i), (3, i), c) for i, c in bg]
    t.setStyle(TableStyle(st)); fl.append(t)
    fl.append(Paragraph(PROTECTED + " That conservatism is the trust pitch — we don't bill savings we didn't make.", s["note"]))
    doc.build(fl); print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    build_customer(a.out)
    build_personas(a.out)


if __name__ == "__main__":
    main()
