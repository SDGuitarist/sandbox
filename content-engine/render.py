"""Amplify AI content-engine — data-driven card renderer.

Two clean layers (per plan §Architecture):
  render_template(data) -> html   PURE. No I/O, no browser. Fills template/card.html.
  render_to_png(html, out)        Playwright I/O. Screenshots the html to a PNG.

Card data schema (JSON):
  {
    "eyebrow": "Prompting 101",        # small kicker above the headline (optional)
    "title":   "The 5-Layer",          # headline, ink-colored
    "accent":  "Prompt",               # optional trailing word, ember-colored, wraps
    "items": [                          # 3-5 rows (the 1:1 square has the least room)
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

# Canvas formats. 4:5 portrait is the LinkedIn/Facebook card; 1:1 square is the
# Instagram card (same design, retuned spacing via .fmt-1x1 in template/card.html).
FORMATS = {"4x5": (1080, 1350), "1x1": (1080, 1080)}
DEFAULT_FORMAT = "4x5"

# Back-compat: the default canvas size (used by check_render.py's older imports).
W, H = FORMATS[DEFAULT_FORMAT]


def render_template(data: dict, fmt: str = DEFAULT_FORMAT) -> str:
    """PURE: card data -> a fully self-contained HTML string (logo inlined as a
    data URI, fonts via <link>). Deterministic given `data` + `fmt`. No I/O, no
    browser. `fmt` is one of FORMATS ("4x5" portrait or "1x1" square)."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}; expected one of {sorted(FORMATS)}")
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
        .replace("@@FMT@@", "fmt-" + fmt)
        .replace("@@LOGO@@", _LOGO_URI)
        .replace("@@EYEBROW@@", escape(data.get("eyebrow", "")))
        .replace("@@TITLE_HTML@@", title_html)
        .replace("@@LAYERS@@", layers)
        .replace("@@SITE@@", escape(data.get("site") or BRAND_SITE))
        .replace("@@TAGLINE@@", escape(data.get("tagline") or BRAND_TAGLINE))
    )


def render_to_png(html: str, out: Path, fmt: str = DEFAULT_FORMAT) -> Path:
    """Playwright I/O: render `html` and screenshot the format's canvas to `out`."""
    from playwright.sync_api import sync_playwright

    w, h = FORMATS[fmt]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.evaluate("async () => { await document.fonts.ready; }")
        page.wait_for_timeout(500)
        page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": w, "height": h})
        browser.close()
    return out


def main():
    # CLI: render.py [data.json] [out.png] [4x5|1x1]
    # A trailing format token is accepted in the last position even without an out
    # path, so `render.py data.json 1x1` does what it looks like (renders 1:1 to the
    # default -1x1 out path) instead of writing a file literally named "1x1".
    args = sys.argv[1:]
    fmt = DEFAULT_FORMAT
    if args and args[-1] in FORMATS:
        fmt = args.pop()
    if len(args) > 2 or (len(args) == 2 and args[1] in FORMATS):
        sys.exit(f"usage: render.py [data.json] [out.png] [{'|'.join(FORMATS)}]")
    data_path = Path(args[0]) if args else ROOT / "data" / "the-5-layer-prompt.json"
    out = Path(args[1]) if len(args) > 1 else ROOT / "out" / f"{data_path.stem}-{fmt}.png"
    data = json.loads(data_path.read_text())
    render_to_png(render_template(data, fmt), out, fmt)
    print("WROTE", out, f"({FORMATS[fmt][0]}x{FORMATS[fmt][1]})")


if __name__ == "__main__":
    main()
