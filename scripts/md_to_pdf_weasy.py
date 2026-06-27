#!/usr/bin/env python3
"""Render a Markdown doc to a clean, green-branded PDF via weasyprint.

Handles GFM tables, fenced code, bold/italic, headings, rules. Used for Outlay
internal/strategy docs (market-analysis, product-strategy, feature specs).

Requires: pip install weasyprint markdown
Usage: python scripts/md_to_pdf_weasy.py <in.md> <out.pdf> "Title"
"""
import sys
import markdown
from weasyprint import HTML

CSS = """
@page { size: letter; margin: 0.85in 0.8in 0.75in 0.8in;
        @bottom-right { content: counter(page) " / " counter(pages);
                        font: 8pt "Helvetica"; color: #8a8f98; } }
* { box-sizing: border-box; }
body { font-family: "Georgia", serif; font-size: 10.2pt; line-height: 1.5;
       color: #1F2430; }
h1 { font-size: 22pt; color: #0B513C; margin: 0 0 4pt; line-height: 1.15; }
h2 { font-size: 14pt; color: #0F6B4F; margin: 18pt 0 6pt;
     border-bottom: 1.5px solid #E1DDD2; padding-bottom: 3pt; }
h3 { font-size: 11.5pt; color: #1F2430; margin: 12pt 0 4pt; }
p { margin: 0 0 7pt; }
strong { color: #0B513C; }
a { color: #0F6B4F; text-decoration: none; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.8pt;
       background: #F1EFE8; padding: 1px 4px; border-radius: 3px; color: #0B513C; }
pre { background: #F4F2EC; border: 1px solid #E1DDD2; border-radius: 5px;
      padding: 9px 12px; overflow-x: auto; }
pre code { background: none; padding: 0; color: #1F2430; font-size: 9pt; }
ul, ol { margin: 0 0 8pt; padding-left: 20px; }
li { margin: 0 0 3pt; }
hr { border: none; border-top: 1px solid #E1DDD2; margin: 12pt 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0 12pt;
        font-size: 9pt; line-height: 1.35; }
th { background: #0F6B4F; color: #fff; text-align: left; font-family: "Helvetica";
     padding: 5px 8px; font-size: 8.6pt; }
td { border: 0.5px solid #E1DDD2; padding: 5px 8px; vertical-align: top; }
tr:nth-child(even) td { background: #F6FBF8; }
"""


def build(src, out, title):
    text = open(src).read()
    html_body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])
    doc = f"<html><head><meta charset='utf-8'><title>{title}</title></head><body>{html_body}</body></html>"
    HTML(string=doc).write_pdf(out, stylesheets=[__import__("weasyprint").CSS(string=CSS)])
    print("wrote", out)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], sys.argv[3])
