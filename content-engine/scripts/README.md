# content-engine scripts

## Weekly batch review (Sunday-evening cron)

`open-weekly-batch.sh` opens the NEXT weekly batch to review — the earliest-named week whose
`batch.md` is not yet `status: posted` — `batch.md` in TextEdit and that week's graphics in
Preview. So with a backlog of pre-generated future weeks it surfaces the nearest un-posted one;
once you set a week to `status: posted`, the next Sunday it advances to the following week. It
only OPENS an already-staged batch; generation is `/content-batch` (Max-covered), never this script.

Scheduled by a **macOS LaunchAgent** (launchd), not a Claude session — so it runs whether or
not Claude Code is open. A Claude cloud cron can't do this: it runs in the cloud and can't
open apps on this Mac. That's why this is launchd.

- **Live agent:** `~/Library/LaunchAgents/com.alexguillen.weekly-content-batch.plist`
  (the copy here in the repo is a versioned reference/backup).
- **Schedule:** Sunday (`Weekday 0`) at `18:00`.
- **Log:** `~/Library/Logs/weekly-content-batch.log`

### Manage it

```sh
# Test it right now (opens the windows for real):
launchctl kickstart -k gui/$(id -u)/com.alexguillen.weekly-content-batch

# See what it WOULD open, without opening anything:
bash content-engine/scripts/open-weekly-batch.sh --dry-run

# Confirm it's loaded / see next run:
launchctl print gui/$(id -u)/com.alexguillen.weekly-content-batch | grep -iE 'state|weekday|hour|minute'

# Change the time: edit Hour/Minute in the LIVE plist, then reload:
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.alexguillen.weekly-content-batch.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.alexguillen.weekly-content-batch.plist

# Remove it entirely:
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.alexguillen.weekly-content-batch.plist
rm ~/Library/LaunchAgents/com.alexguillen.weekly-content-batch.plist
```

Note: if you move the sandbox repo, update the script path in the live plist.
