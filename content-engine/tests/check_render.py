"""Render-fidelity dims check (plan §Acceptance Tests verification command).

Asserts each PNG is EXACTLY one of the two valid card canvases:
  4:5 portrait 1080x1350  (LinkedIn / Facebook card)
  1:1 square   1080x1080  (Instagram card)
The 4:5 is the format the template settled on in Phase 0 Spike B (the plan's older
"1080x1080"-only text is stale); the 1:1 was added for Instagram's square graphic.

Usage:
  lead-scraper/.venv/bin/python content-engine/tests/check_render.py [PNG ...]

With no args, checks every PNG under content-engine/out/ and content-engine/staging/.
Prints "<path>: 1080x1350 OK (4x5)" per file; exits non-zero on the first bad/missing file.
Pure stdlib (reads the PNG IHDR header) — no Pillow/Playwright needed.
"""
import struct
import sys
from pathlib import Path

# name -> (width, height). Mirrors render.FORMATS.
VALID = {"4x5": (1080, 1350), "1x1": (1080, 1080)}
ROOT = Path(__file__).resolve().parents[1]  # content-engine/


def png_dims(path: Path) -> tuple[int, int]:
    """Read width/height from the PNG IHDR chunk (first 24 bytes)."""
    with path.open("rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def main() -> int:
    args = sys.argv[1:]
    if args:
        pngs = [Path(a) for a in args]
    else:
        pngs = sorted((ROOT / "out").glob("*.png")) + sorted((ROOT / "staging").rglob("*.png"))

    if not pngs:
        print("no PNGs to check")
        return 0

    by_dims = {dims: name for name, dims in VALID.items()}
    expected = " or ".join(f"{w}x{h}" for w, h in VALID.values())
    failed = False
    for p in pngs:
        if not p.exists():
            print(f"{p}: MISSING")
            failed = True
            continue
        w, h = png_dims(p)
        name = by_dims.get((w, h))
        if name:
            print(f"{p}: {w}x{h} OK ({name})")
        else:
            print(f"{p}: {w}x{h} FAIL (expected {expected})")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
