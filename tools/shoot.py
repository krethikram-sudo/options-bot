#!/usr/bin/env python3
"""Screenshot helper for the visual design loop.

Renders one or more pages at desktop + mobile widths (full page) so they can be
eyeballed and iterated on. Works anywhere a Playwright browser is available
(your local machine, or a web env whose setup pre-installs Chromium). It is NOT
wired into the app — it's a dev utility.

Setup (once):
    pip install playwright && playwright install chromium

Usage:
    # static marketing/legal site
    python3 -m http.server 8000 --directory modelpilot/site &
    python3 tools/shoot.py http://localhost:8000/legal/terms.html http://localhost:8000/index.html

    # console (server-rendered) — start the app first, then point at a route
    python3 tools/shoot.py http://localhost:8080/legal/terms

PNGs land in screenshots/ (gitignored). Default widths: 1280 (desktop) and
390 (mobile, iPhone-ish). Override with --widths 1280,768,390.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from urllib.parse import urlparse

OUT = pathlib.Path("screenshots")


def main() -> int:
    ap = argparse.ArgumentParser(description="Full-page screenshots at multiple widths.")
    ap.add_argument("urls", nargs="+", help="page URLs to shoot")
    ap.add_argument("--widths", default="1280,390", help="comma-separated viewport widths")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed. Run: pip install playwright && playwright install chromium",
              file=sys.stderr)
        return 1

    widths = [int(w) for w in args.widths.split(",") if w.strip()]
    OUT.mkdir(exist_ok=True)
    shot = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for url in args.urls:
            slug = (urlparse(url).path.strip("/") or "index").replace("/", "_").replace(".html", "")
            for w in widths:
                page = browser.new_page(viewport={"width": w, "height": 900},
                                        device_scale_factor=2)
                page.goto(url, wait_until="networkidle")
                dest = OUT / f"{slug}@{w}.png"
                page.screenshot(path=str(dest), full_page=True)
                page.close()
                print(f"  {dest}")
                shot += 1
        browser.close()
    print(f"{shot} screenshot(s) in {OUT}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
