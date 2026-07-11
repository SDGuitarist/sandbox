#!/bin/bash
# open-weekly-batch.sh — Sunday-evening review ritual for the Amplify content engine.
#
# Opens the most recently prepared weekly batch for review:
#   - batch.md in TextEdit (the 9 posts + voice verdict + review checklist)
#   - all of that week's graphics in Preview (the 1:1 + 4:5 cards)
#
# Run by the launchd agent com.alexguillen.weekly-content-batch (Sundays), but also
# runnable by hand any time:  bash open-weekly-batch.sh            (opens for real)
#                             bash open-weekly-batch.sh --dry-run  (prints, opens nothing)
#
# "Most recent" = the staging/<ISO-week>/ folder with a batch.md, chosen by HIGHEST
# ISO-week NAME (2026-W29 > 2026-W28; %V is zero-padded so it sorts correctly, and the
# year prefix orders across the new-year boundary). Name-based, not mtime, so incidentally
# touching an old week's folder (adding a PNG, a .DS_Store) can't hijack the pick. Nothing
# is generated here; this only OPENS an already-staged batch (generation is /content-batch).

set -u
STAGING="/Users/alejandroguillen/Projects/sandbox/content-engine/staging"
DRY_RUN="${1:-}"

if [ -n "$DRY_RUN" ] && [ "$DRY_RUN" != "--dry-run" ]; then
  echo "unknown argument: $DRY_RUN (use --dry-run, or no args to open for real)"
  exit 2
fi

notify() {  # best-effort desktop notification; ignore if not permitted
  /usr/bin/osascript -e "display notification \"$1\" with title \"Amplify weekly batch\"" 2>/dev/null || true
}

# Highest-named week folder (2026-W29 before 2026-W28) that contains a batch.md.
LATEST_BATCH=""
while IFS= read -r dir; do
  if [ -f "${dir}batch.md" ]; then
    LATEST_BATCH="${dir}batch.md"
    break
  fi
done < <(ls -1d "$STAGING"/*/ 2>/dev/null | sort -r)

if [ -z "$LATEST_BATCH" ]; then
  echo "$(date '+%Y-%m-%d %H:%M') no staged batch.md found under $STAGING"
  notify "No batch staged yet. Run /content-batch to build this week."
  [ "$DRY_RUN" = "--dry-run" ] || open "$STAGING" 2>/dev/null || true
  exit 0
fi

BATCH_DIR="$(dirname "$LATEST_BATCH")"
WEEK="$(basename "$BATCH_DIR")"

echo "$(date '+%Y-%m-%d %H:%M') opening batch for $WEEK: $LATEST_BATCH"
if [ "$DRY_RUN" = "--dry-run" ]; then
  echo "  [dry-run] would open in TextEdit: $LATEST_BATCH"
  echo "  [dry-run] would open in Preview:"
  ls -1 "$BATCH_DIR"/*.png 2>/dev/null | sed 's/^/    /' || echo "    (no PNGs)"
  exit 0
fi

open -a TextEdit "$LATEST_BATCH"
# Open all of the week's graphics in one Preview window (globs the 1:1 + 4:5 cards).
if ls "$BATCH_DIR"/*.png >/dev/null 2>&1; then
  open -a Preview "$BATCH_DIR"/*.png
fi
notify "Opened $WEEK for review: 9 posts + graphics."
