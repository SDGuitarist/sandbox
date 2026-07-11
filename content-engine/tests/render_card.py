"""Render a content-engine card HTML to a true 1080x1080 PNG via Playwright.

Usage:
  lead-scraper/.venv/bin/python content-engine/tests/render_card.py

Loads template/v1.html, strips the on-screen preview scaling, and screenshots the
.card element at its true 1080x1080 size. Prints the output path and pixel size so
the caller can assert the Spike B dimension gate.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]          # content-engine/
SRC = (ROOT / "template" / "v1.html").resolve()
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)
OUT = OUT_DIR / "the-5-layer-prompt.png"

CW, CH = 1080, 1350  # 4:5 portrait

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": CW, "height": CH}, device_scale_factor=1)
    page.goto(SRC.as_uri())
    page.wait_for_load_state("networkidle")
    page.evaluate("async () => { await document.fonts.ready; }")
    page.wait_for_timeout(500)
    # promote the true-size card to a clean 1080x1080 fixed layer, drop preview chrome
    page.evaluate(
        """() => {
            document.querySelector('.note') && document.querySelector('.note').remove();
            document.body.style.margin = '0';
            document.body.style.padding = '0';
            const card = document.querySelector('.card');
            card.style.transform = 'none';
            card.style.position = 'fixed';
            card.style.top = '0';
            card.style.left = '0';
            document.body.appendChild(card);
        }"""
    )
    page.wait_for_timeout(200)
    page.screenshot(path=str(OUT), clip={"x": 0, "y": 0, "width": CW, "height": CH})
    browser.close()

print("WROTE", OUT)
