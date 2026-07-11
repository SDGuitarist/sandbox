"""Render-fidelity check (plan §Acceptance Tests verification command).

Two modes:

1. Dims check (default) — asserts each PNG is EXACTLY one of the two valid canvases:
     4:5 portrait 1080x1350  (LinkedIn / Facebook card)
     1:1 square   1080x1080  (Instagram card)
   AND, when a file is named `*-1x1.png` / `*-4x5.png`, that its pixels match that
   suffix (a `-1x1.png` sized 1080x1350 is a FAIL — swapped render).

2. Pairs check (`--pairs <staging-week-dir>`) — asserts the week's graphics are exactly
   N slug-matched 1x1/4x5 PAIRS (default N=3, one per angle), not merely six valid-sized
   PNGs. Every `<slug>-1x1.png` must have a `<slug>-4x5.png` and vice versa, each at the
   right dims. Pass `--pairs <dir> <N>` to require a different pair count.

Usage:
  lead-scraper/.venv/bin/python content-engine/tests/check_render.py [PNG ...]
  lead-scraper/.venv/bin/python content-engine/tests/check_render.py --pairs <week-dir> [N]

Prints per-file / per-pair results; exits non-zero on the first problem.
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


def _suffix_fmt(path: Path) -> str | None:
    """Return '1x1'/'4x5' if the filename ends with that format tag, else None."""
    for name in VALID:
        if path.stem.endswith(f"-{name}"):
            return name
    return None


def check_dims(pngs: list[Path]) -> int:
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
        tag = _suffix_fmt(p)
        if name is None:
            print(f"{p}: {w}x{h} FAIL (expected {expected})")
            failed = True
        elif tag is not None and tag != name:
            print(f"{p}: {w}x{h} FAIL (named -{tag} but pixels are {name})")
            failed = True
        else:
            print(f"{p}: {w}x{h} OK ({name})")
    return 1 if failed else 0


def check_pairs(week_dir: Path, want_pairs: int) -> int:
    if not week_dir.is_dir():
        print(f"{week_dir}: not a directory")
        return 1
    pngs = sorted(week_dir.glob("*.png"))
    if not pngs:
        print(f"{week_dir}: no PNGs")
        return 1

    slugs: dict[str, dict[str, Path]] = {}
    failed = False
    for p in pngs:
        tag = _suffix_fmt(p)
        if tag is None:
            print(f"{p.name}: FAIL (not named -1x1 / -4x5)")
            failed = True
            continue
        slug = p.stem[: -(len(tag) + 1)]  # strip '-<tag>'
        slugs.setdefault(slug, {})[tag] = p

    for slug, got in sorted(slugs.items()):
        for tag, (want_w, want_h) in VALID.items():
            if tag not in got:
                print(f"{slug}: FAIL (missing -{tag})")
                failed = True
                continue
            w, h = png_dims(got[tag])
            if (w, h) != (want_w, want_h):
                print(f"{got[tag].name}: FAIL ({w}x{h}, expected {want_w}x{want_h} for -{tag})")
                failed = True
            else:
                print(f"{got[tag].name}: {w}x{h} OK ({tag})")

    n = len([s for s, g in slugs.items() if set(g) == set(VALID)])
    if n != want_pairs:
        print(f"{week_dir.name}: FAIL ({n} complete slug-matched pairs, expected {want_pairs})")
        failed = True
    else:
        print(f"{week_dir.name}: {n} slug-matched 1x1/4x5 pairs OK")
    return 1 if failed else 0


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--pairs":
        if len(args) < 2:
            print("usage: check_render.py --pairs <week-dir> [N]")
            return 2
        week_dir = Path(args[1])
        want = int(args[2]) if len(args) > 2 else 3
        return check_pairs(week_dir, want)

    if args:
        pngs = [Path(a) for a in args]
    else:
        pngs = sorted((ROOT / "out").glob("*.png")) + sorted((ROOT / "staging").rglob("*.png"))
    return check_dims(pngs)


if __name__ == "__main__":
    sys.exit(main())
