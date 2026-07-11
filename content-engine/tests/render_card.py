"""Convenience entrypoint — renders the default card via the data-driven engine.

The renderer now lives in content-engine/render.py (render_template + render_to_png).
This wrapper is kept so the original command still works:

  lead-scraper/.venv/bin/python content-engine/tests/render_card.py

It renders data/the-5-layer-prompt.json -> out/the-5-layer-prompt.png. To render any
other card, call render.py directly with a data JSON.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render  # noqa: E402

render.main()
