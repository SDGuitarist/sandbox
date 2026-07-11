"""Render-fidelity dims check (plan §Acceptance Tests verification command).

Asserts each PNG is EXACTLY the card canvas — 1080x1350 (4:5 portrait, the format the
template settled on in Phase 0 Spike B; the plan's older "1080x1080" text is stale).

Usage:
  lead-scraper/.venv/bin/python content-engine/tests/check_render.py [PNG ...]

With no args, checks every PNG under content-engine/out/ and content-engine/staging/.
Prints "<path>: 1080x1350 OK" per file; exits non-zero on the first mismatch/missing file.
Pure stdlib (reads the PNG IHDR header) — no Pillow/Playwright needed.
"""
import struct
import sys
from pathlib import Path

W, H = 1080, 1350
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

    failed = False
    for p in pngs:
        if not p.exists():
            print(f"{p}: MISSING")
            failed = True
            continue
        w, h = png_dims(p)
        if (w, h) == (W, H):
            print(f"{p}: {w}x{h} OK")
        else:
            print(f"{p}: {w}x{h} FAIL (expected {W}x{H})")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
