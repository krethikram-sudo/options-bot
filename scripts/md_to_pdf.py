#!/usr/bin/env python3
"""Render a Markdown file to a clean PDF (headings, bullets, bold, code, links).
Reusable for internal docs (PROSPECTS.md, PILOT_ONEPAGER.md, etc.).
Requires: pip install reportlab
Usage: python scripts/md_to_pdf.py <in.md> <out.pdf> "Title"
"""
import re, sys
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem

def inline(t):
    t = t.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)', r'<i>\1</i>', t)
    t = re.sub(r'`([^`]+)`', r'<font face="Courier" size=9>\1</font>', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" color="#2563eb">\1</a>', t)
    t = re.sub(r'(?<!["\>])(https?://[^\s)]+)', r'<a href="\1" color="#2563eb">\1</a>', t)
    return t

def build(src, out, title):
    ss = getSampleStyleSheet()
    vio = colors.HexColor("#6d28d9"); ink = colors.HexColor("#0a0a0a"); mut = colors.HexColor("#6b6b72")
    H1 = ParagraphStyle('H1', parent=ss['Title'], fontSize=20, textColor=ink, spaceAfter=6, leading=24)
    H2 = ParagraphStyle('H2', parent=ss['Heading2'], fontSize=14, textColor=vio, spaceBefore=14, spaceAfter=5, leading=17)
    H3 = ParagraphStyle('H3', parent=ss['Heading3'], fontSize=11.5, textColor=ink, spaceBefore=8, spaceAfter=3, leading=14)
    body = ParagraphStyle('body', parent=ss['BodyText'], fontSize=9.5, leading=13.5, textColor=ink, spaceAfter=4)
    bullet = ParagraphStyle('bullet', parent=body, leftIndent=14, bulletIndent=4, spaceAfter=2)
    quote = ParagraphStyle('quote', parent=body, leftIndent=14, textColor=mut, fontName='Helvetica-Oblique', spaceAfter=4)
    foot = ParagraphStyle('foot', parent=body, fontSize=8, textColor=mut)
    doc = SimpleDocTemplate(out, pagesize=letter, leftMargin=0.7*inch, rightMargin=0.7*inch,
                            topMargin=0.7*inch, bottomMargin=0.6*inch, title=title)
    fl=[]; lines=open(src).read().split('\n')
    for ln in lines:
        s=ln.rstrip()
        if not s.strip(): fl.append(Spacer(1,4)); continue
        if s.strip()=='---': fl.append(Spacer(1,3)); fl.append(HRFlowable(width="100%", color=colors.HexColor("#e3e3e7"))); fl.append(Spacer(1,3)); continue
        if s.startswith('### '): fl.append(Paragraph(inline(s[4:]), H3)); continue
        if s.startswith('## '): fl.append(Paragraph(inline(s[3:]), H2)); continue
        if s.startswith('# '): fl.append(Paragraph(inline(s[2:]), H1)); continue
        if s.startswith('> '): fl.append(Paragraph(inline(s[2:]), quote)); continue
        m=re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)', s)
        if m:
            txt=inline(m.group(3)); pre='• ' if m.group(2) in('-','*') else m.group(2)+' '
            fl.append(Paragraph(pre+txt, bullet)); continue
        if s.lstrip().startswith('|'):
            cells=[c.strip() for c in s.strip().strip('|').split('|')]
            if set(''.join(cells))<=set('-: '): continue
            fl.append(Paragraph(inline(' · '.join(c for c in cells if c)), body)); continue
        fl.append(Paragraph(inline(s), body))
    doc.build(fl)
    print("wrote", out)

build(sys.argv[1], sys.argv[2], sys.argv[3])
