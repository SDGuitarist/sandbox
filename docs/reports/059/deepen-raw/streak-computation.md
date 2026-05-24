# Deepen: Streak Computation Algorithm Correctness and Edge Cases

## Summary

The plan's streak functions are **correct for all stated edge cases** and faithfully reproduce the proven CLI version. The set-deduplication pattern is the right call, and the "yesterday counts" rule is correctly implemented. I found **no bugs** in the algorithm itself. The main findings are: (1) a timezone note worth adding as a code comment, (2) confirmation that in-memory computation is fine at personal scale, and (3) documentation of six concrete edge case traces showing the algorithm produces the expected result in every scenario. One optional plan improvement is suggested for SQL-level streak computation as a future optimization, but it is not needed for the MVP.

## Findings

### 1. Single-date edge case: only today in completions (streak = 1)

**Verdict: Correct.**

Trace through `compute_current_streak(["2026-05-24"])`:
- `completions` is non-empty, passes guard.
- `dates = sorted({date(2026,5,24)}, reverse=True)` = `[date(2026,5,24)]`
- `today = date(2026,5,24)`
- `dates[0] == today` is True, so we do NOT return 0.
- `streak = 1`
- Loop `range(1, 1)` = empty, no iterations.
- Returns `1`. Correct.

Same trace for `compute_longest_streak(["2026-05-24"])`:
- `dates = sorted({date(2026,5,24)})` = `[date(2026,5,24)]`
- `longest = 1`, `current = 1`
- Loop `range(1, 1)` = empty.
- Returns `1`. Correct.

### 2. Old dates with no recent activity (streak = 0)

**Verdict: Correct.**

Trace through `compute_current_streak(["2026-01-15", "2026-01-16", "2026-01-17"])` when today is 2026-05-24:
- `dates = sorted({...}, reverse=True)` = `[date(2026,1,17), date(2026,1,16), date(2026,1,15)]`
- `today = date(2026,5,24)`, `today - timedelta(days=1) = date(2026,5,23)`
- `dates[0]` (2026-01-17) is neither today nor yesterday.
- Returns `0`. Correct.

The "most recent date" check is the right early-exit. Without it, the algorithm would scan all dates and report a streak of 3, which would be misleading because the streak is not current.

### 3. The "yesterday counts" rule

**Verdict: Correct. This is the key UX decision and it is implemented properly.**

The condition `dates[0] != today and dates[0] != today - timedelta(days=1)` returns 0 only when the most recent completion is older than yesterday. This means:

**Scenario A:** User completed Mon-Wed, it is now Thursday morning, user has NOT yet toggled today.
- `dates[0]` = Wednesday = `today - timedelta(days=1)` (yesterday). Condition is False (does NOT return 0).
- Algorithm counts backward: Wed-Tue = 1 day (streak=2), Tue-Mon = 1 day (streak=3).
- Returns `3`. Correct -- the user's streak is preserved until end of Thursday.

**Scenario B:** User completed Mon-Wed, it is now Friday morning, user did NOT complete Thursday.
- `dates[0]` = Wednesday. `today` = Friday. `today - 1` = Thursday.
- Wednesday is neither Friday nor Thursday. Returns `0`. Correct -- the streak broke on Thursday.

**Scenario C:** User completed Mon-Wed and also today (Thursday).
- `dates[0]` = Thursday = `today`. Condition is False.
- Algorithm counts backward: Thu-Wed = 1 day (streak=2), Wed-Tue = 1 day (streak=3), Tue-Mon = 1 day (streak=4).
- Returns `4`. Correct.

This is the standard "grace until end of today" pattern used by Duolingo and other streak-based apps. It prevents the frustrating experience of waking up and seeing streak = 0 before you have had a chance to complete your habit.

### 4. DST / timezone edge cases

**Verdict: Not a bug for this use case, but worth documenting in a code comment.**

`date.today()` uses the system's local timezone. For this app (a single-user personal tool running locally), this is fine. The plan already notes: "System local timezone via `date.today()` (sufficient for single-user personal tool)."

However, there are two scenarios worth being aware of:

**Scenario A: Server timezone differs from user timezone.**
If this app were ever deployed to a cloud server (e.g., Railway), `date.today()` would return the server's timezone (likely UTC). A user in PST (UTC-8) completing a habit at 10 PM local time would see `date.today()` return tomorrow's date on a UTC server. This would cause:
- The toggle to record tomorrow's date instead of today's.
- The streak to look broken because "today" in the user's mind differs from "today" on the server.

**Scenario B: DST transition.**
On DST "spring forward" night, the day is 23 hours long. On "fall back" night, 25 hours. Since `date.today()` works at the date level (not datetime), and Python's `date` type has no concept of time-of-day, DST does not affect the date math. `date(2026,3,8) - date(2026,3,7)` is always `timedelta(days=1)` regardless of DST. **This is not a problem.**

**Recommendation:** Add a one-line comment in the code acknowledging the local-timezone assumption. No code change needed for the MVP.

```python
# Uses system local timezone. Fine for single-user local app.
# If deployed to a remote server, replace with user-specific timezone.
today = date.today()
```

### 5. Performance at personal scale

**Verdict: The in-memory approach is correct and sufficient. No SQL optimization needed.**

The plan's risk analysis already covers this: "At personal scale (365 days x 20 habits = 7,300 comparisons) this is negligible."

Let me quantify more precisely:

- **Worst case:** 10 years of daily data for 1 habit = 3,650 date strings.
- **Operations:** Parse 3,650 strings to dates, deduplicate (set), sort, iterate once. This is O(n log n) dominated by the sort.
- **Wall clock:** On any modern machine, this completes in under 1 millisecond.
- **Memory:** 3,650 `date` objects at ~48 bytes each = ~175 KB. Trivial.

**SQL-level optimization (future, not MVP):** If performance ever became a concern, the streak could be computed in pure SQL using the "date minus row_number" window function technique:

```sql
-- Current streak (most recent consecutive run touching today or yesterday)
WITH ranked AS (
    SELECT completed_date,
           DATE(completed_date, '-' || (ROW_NUMBER() OVER (ORDER BY completed_date DESC) - 1) || ' days') AS grp
    FROM completions
    WHERE habit_id = ?
),
streaks AS (
    SELECT grp, COUNT(*) AS streak_len, MAX(completed_date) AS latest
    FROM ranked
    GROUP BY grp
)
SELECT streak_len FROM streaks
WHERE latest >= DATE('now', '-1 day')
ORDER BY latest DESC
LIMIT 1;
```

This avoids loading all completions into Python. But for a personal tracker, the Python approach is simpler, tested, and fast enough. **No plan change needed.**

### 6. Known streak algorithm bugs in similar apps

**Verdict: The plan's algorithm avoids all commonly reported bugs.**

Research into streak implementations across popular apps (Duolingo, GitHub contributions, fitness trackers) reveals these common failure modes:

**Bug 1: Duplicate entries breaking consecutive-day logic.**
When duplicate dates exist in the list, `date_n - date_n-1 == timedelta(0)` instead of `timedelta(days=1)`, which breaks the streak. **The plan prevents this** with set deduplication AND with the UNIQUE(habit_id, completed_date) constraint at the DB level. Double protection.

**Bug 2: Not handling "today not yet completed" gracefully.**
Some implementations only count the streak if the most recent entry is today, causing the streak to show 0 first thing in the morning. **The plan handles this** with the "yesterday counts" rule.

**Bug 3: Timezone mismatch between storage and computation.**
Duolingo has documented bugs where the timezone stored at account creation differs from the user's current timezone, causing streaks to reset at the wrong hour. **The plan avoids this** by using `date.today()` consistently for both storage (toggle uses `date.today().isoformat()`) and computation. Since both use the same system clock, they cannot diverge. (The risk only appears if the app moves to a remote server -- see Finding 4.)

**Bug 4: Off-by-one in streak counting.**
Some implementations start `streak = 0` and increment on the first match, missing the fact that a single completed day is itself a streak of 1. **The plan correctly initializes `streak = 1`** (the most recent date is already day 1 of the streak) and only increments when consecutive predecessors are found.

**Bug 5: Not sorting before computing.**
If completions are stored in insertion order rather than date order, the consecutive-day check fails. **The plan sorts explicitly** with `sorted(...)`.

**Bug 6: Using stored streak counters instead of computing from raw data.**
Stored counters (e.g., `streak_count: 5` in a habits table) can become stale if the user misses a day and no process decrements the counter. **The plan computes streaks from completions on every request**, which is always correct. The solution doc from the CLI version (2026-04-09) explicitly calls out "Computed > stored for derived values" as a key lesson.

## Recommended Plan Changes

- **None required.** The algorithm is correct for all tested edge cases. The plan's risk analysis already covers the performance question. The timezone limitation is already documented in the Date Handling section.

- **Optional (documentation only):** Consider adding a brief code comment in the prescribed streak functions noting the `date.today()` local-timezone assumption, as shown in Finding 4. This is a future-proofing note, not a correctness fix.

---

*Sources consulted:*
- [How to Build a Streaks Feature (Trophy)](https://trophy.so/blog/how-to-build-a-streaks-feature) -- streak architecture patterns, grace periods, freeze mechanics
- [Designing a Streak System: UX and Psychology (Smashing Magazine)](https://www.smashingmagazine.com/2026/02/designing-streak-system-ux-psychology/) -- streak freeze impact data, grace period best practices
- [Duolingo Streak Wiki](https://duolingo.fandom.com/wiki/Streak) -- timezone bug documentation, midnight boundary issues
- [Duolingo Forum: Day Streak ending too early](https://duolingo.hobune.stream/comment/4276023) -- timezone offset mismatch causing early resets
- [Consecutive Groups in SQL (Simon Willison)](https://til.simonwillison.net/sql/consecutive-groups) -- date-minus-row_number technique
- [How to Calculate Length of Series with SQL (LearnSQL)](https://learnsql.com/blog/how-to-calculate-length-of-series-in-sql/) -- SQL window function streak patterns
- [SQL Story of Unbroken Chains (DEV Community)](https://dev.to/keyridan/sql-story-of-unbroken-chains-of-events-streaks-3lh3) -- consecutive date grouping
- [Handling Timezone and DST in Python (HackSoft)](https://www.hacksoft.io/blog/handling-timezone-and-dst-changes-with-python) -- DST pitfalls with naive datetimes
- [Flask Mega-Tutorial Part XII: Dates and Times (Miguel Grinberg)](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xii-dates-and-times) -- server vs user timezone in Flask
- [Apps That Use Streaks: 10 Real Examples (Trophy)](https://trophy.so/blog/streaks-feature-gamification-examples) -- streak freeze statistics (48% longer average streaks)
- Internal: `docs/solutions/2026-04-09-cli-habit-tracker-streaks.md` -- set deduplication lesson, computed > stored principle
