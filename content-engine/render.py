"""Amplify AI content-engine — data-driven card renderer.

Two clean layers (per plan §Architecture):
  render_template(data) -> html   PURE. No I/O, no browser. Fills template/card.html.
  render_to_png(html, out)        Playwright I/O. Screenshots the html to a PNG.

Card data schema (JSON):
  {
    "eyebrow": "Prompting 101",        # small kicker above the headline (optional)
    "title":   "The 5-Layer",          # headline, ink-colored
    "accent":  "Prompt",               # optional trailing word, ember-colored, wraps
    "items": [                          # 3-6 rows recommended for the 4:5 canvas
      {"label": "Identity", "desc": "who the AI is"},
      ...
    ],
    "site":    "amplifyai.to",          # optional; defaults to brand
    "tagline": "Human-Led AI"           # optional; defaults to brand
  }

CLI:
  lead-scraper/.venv/bin/python content-engine/render.py [data.json] [out.png]
  (defaults: data/the-5-layer-prompt.json -> out/<stem>.png)
"""
import base64
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent                      # content-engine/
_TEMPLATE = (ROOT / "template" / "card.html").read_text()
_LOGO_URI = "data:image/png;base64," + base64.b64encode(
    (ROOT / "assets" / "logo-amplify-ai.png").read_bytes()
).decode()

# Brand defaults (footer). Per-card data may override.
BRAND_SITE = "amplifyai.to"
BRAND_TAGLINE = "Human-Led AI"

# Canvas — 4:5 portrait, matches template/card.html.
W, H = 1080, 1350


def render_template(data: dict) -> str:
    """PURE: card data -> a fully self-contained HTML string (logo inlined as a
    data URI, fonts via <link>). Deterministic given `data`. No I/O, no browser."""
    title_html = escape(data["title"])
    accent = data.get("accent")
    if accent:
        title_html += f' <em>{escape(accent)}</em>'

    layers = "\n".join(
        '<div class="layer">'
        f'<span class="no">{i + 1:02d}</span>'
        f'<span class="lab">{escape(item["label"])}</span>'
        f'<span class="dsc">{escape(item.get("desc", ""))}</span>'
        '</div>'
        for i, item in enumerate(data["items"])
    )

    return (
        _TEMPLATE
        .replace("@@LOGO@@", _LOGO_URI)
        .replace("@@EYEBROW@@", escape(data.get("eyebrow", "")))
        .replace("@@TITLE_HTML@@", title_html)
        .replace("@@LAYERS@@", layers)
        .replace("@@SITE@@", escape(data.get("site") or BRAND_SITE))
        .replace("@@TAGLINE@@", escape(data.get("tagline") or BRAND_TAGLINE))
    )


def render_to_png(html: str, out: Path) -> Path:
    """Playwright I/O: render `html` and screenshot the WxH card to `out`."""
    from playwright.sync_api import sync_playwright

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.evaluate("async () => { await document.fonts.ready; }")
        page.wait_for_timeout(500)
        page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": W, "height": H})
        browser.close()
    return out


def main():
    args = sys.argv[1:]
    data_path = Path(args[0]) if args else ROOT / "data" / "the-5-layer-prompt.json"
    out = Path(args[1]) if len(args) > 1 else ROOT / "out" / f"{data_path.stem}.png"
    data = json.loads(data_path.read_text())
    render_to_png(render_template(data), out)
    print("WROTE", out)


if __name__ == "__main__":
    main()
