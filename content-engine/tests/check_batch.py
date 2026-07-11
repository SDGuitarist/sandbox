"""Batch-contract verification (plan §Acceptance Tests) — shape, gate ordering, voice.

Runs the deterministic acceptance checks on a staged batch.md:

SHAPE
  - exactly 9 platform-post headers  (^### (Instagram|LinkedIn|Facebook) Post)
  - exactly 3 angle headers          (^## Angle …)

GATE ORDERING (GO-before-draft — the blocked/pre-review state)
  - status is one of: blocked | draft | approved | posted
  - voice_verdict is one of: GO | FIX… | PENDING
  - a batch may be draft/approved/posted ONLY when voice_verdict is GO
  - any non-GO verdict (PENDING/FIX) MUST be status: blocked AND MUST NOT contain the
    "Review & Publish (Alex)" approval section — the approval prompt is GO-only

VOICE (deterministic backstop; voice-guardian is the primary gate)
  - zero em-dashes anywhere in the file
  - zero banned-vocabulary words in the post bodies (the complete SYSTEM_PROMPT list)

Usage:
  lead-scraper/.venv/bin/python content-engine/tests/check_batch.py <batch.md | week-dir>
Exit 0 = all contracts hold, 1 = one or more failed.
"""
import re
import sys
from pathlib import Path

APPROVABLE = {"draft", "approved", "posted"}
ALL_STATUS = {"blocked"} | APPROVABLE

# Complete banned vocabulary — content_pipeline.py SYSTEM_PROMPT rule #2, plus the two
# voice-guardian Tier-1 extras (commendable, noteworthy). Reused verbatim, not paraphrased.
BANNED = [
    "delve", "tapestry", "realm", "leverage", "utilize", "harness", "unlock", "embark",
    "unleash", "elevate", "foster", "beacon", "synergy", "groundbreaking", "cutting-edge",
    "unprecedented", "seamless", "pivotal", "intricate", "robust", "transformative",
    "revolutionize", "supercharge", "streamline", "game-changer", "empower", "innovative",
    "paradigm", "comprehensive", "bespoke", "holistic", "turbocharge", "meticulous",
    "multifaceted", "commendable", "noteworthy",
]
BANNED_RX = re.compile(r"\b(" + "|".join(re.escape(w) for w in BANNED) + r")\b", re.I)
HEADER_RX = re.compile(r"^#{1,6}\s")               # markdown header (has space after #)
POST_RX = re.compile(r"^###\s+(Instagram|LinkedIn|Facebook) Post\s*$")
ANGLE_RX = re.compile(r"^##\s+Angle\b")
APPROVAL_RX = re.compile(r"^##\s+Review & Publish")


def frontmatter_field(text: str, field: str) -> str | None:
    # Look only inside the leading --- ... --- frontmatter block, and strip any inline
    # "# comment" (the template annotates the status line), so parsing is robust.
    fm = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        fm = text[:end] if end != -1 else text
    m = re.search(rf"^{field}:\s*(.+?)\s*$", fm, re.M)
    if not m:
        return None
    val = re.sub(r"\s+#.*$", "", m.group(1)).strip()
    return val.strip('"').strip("'")


def post_bodies(lines: list[str]) -> list[tuple[int, str]]:
    """Yield (start_line, text) for each ### platform-post body (up to the next header)."""
    bodies, i, n = [], 0, len(lines)
    while i < n:
        if POST_RX.match(lines[i]):
            start = i + 1
            j = start
            while j < n and not HEADER_RX.match(lines[j]):
                j += 1
            bodies.append((start + 1, "\n".join(lines[start:j])))
            i = j
        else:
            i += 1
    return bodies


def check_batch(path: Path) -> int:
    text = path.read_text()
    lines = text.splitlines()
    fails = []

    # SHAPE
    posts = sum(1 for ln in lines if POST_RX.match(ln))
    angles = sum(1 for ln in lines if ANGLE_RX.match(ln))
    if posts != 9:
        fails.append(f"shape: {posts} platform-post headers (expected 9)")
    if angles != 3:
        fails.append(f"shape: {angles} angle headers (expected 3)")

    # GATE ORDERING
    status = frontmatter_field(text, "status")
    verdict = frontmatter_field(text, "voice_verdict")
    is_go = verdict == "GO"
    has_approval = any(APPROVAL_RX.match(ln) for ln in lines)

    if status not in ALL_STATUS:
        fails.append(f"gate: status {status!r} not in {sorted(ALL_STATUS)}")
    if not (verdict == "GO" or verdict == "PENDING" or (verdict or "").startswith("FIX")):
        fails.append(f"gate: voice_verdict {verdict!r} not GO/FIX…/PENDING")
    if status in APPROVABLE and not is_go:
        fails.append(f"gate: status {status!r} requires voice_verdict GO (got {verdict!r}) — GO-before-draft")
    if not is_go:
        if status != "blocked":
            fails.append(f"gate: non-GO verdict {verdict!r} must be status: blocked (got {status!r})")
        if has_approval:
            fails.append(f"gate: non-GO verdict {verdict!r} must NOT contain the 'Review & Publish' approval section")
    if is_go and not has_approval:
        fails.append("gate: GO batch is missing the 'Review & Publish' section")

    # VOICE
    if "—" in text:
        n = text.count("—")
        fails.append(f"voice: {n} em-dash(es) in the file (banned everywhere)")
    for start_line, body in post_bodies(lines):
        for m in BANNED_RX.finditer(body):
            off = body[: m.start()].count("\n")
            fails.append(f"voice: banned word {m.group(0)!r} in post body near line {start_line + off}")

    rel = path
    if fails:
        for f in fails:
            print(f"FAIL {rel}: {f}")
        print(f"BATCH CONTRACT: FAIL ({len(fails)} problem(s))")
        return 1
    print(f"ok   {rel}: 9 posts / 3 angles / gate={status}+{verdict} / voice clean")
    print("BATCH CONTRACT: PASS")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_batch.py <batch.md | week-dir>")
        return 2
    target = Path(sys.argv[1])
    if target.is_dir():
        target = target / "batch.md"
    if not target.is_file():
        print(f"{target}: no batch.md")
        return 1
    return check_batch(target)


if __name__ == "__main__":
    sys.exit(main())
