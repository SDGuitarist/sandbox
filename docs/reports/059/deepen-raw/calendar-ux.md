# Deepen Research: Server-Rendered Weekly Calendar UX for Habit Tracking (No JS)

## Summary

The plan's weekly calendar toggle UX is viable without JavaScript, but the Feed-Forward concern about "clunky" multi-day toggling is legitimate. The biggest wins come from three areas: (1) using proper ARIA grid roles so screen readers and keyboards can navigate the calendar, (2) appending a fragment identifier to the POST redirect URL so the page scrolls back to the row the user just toggled, and (3) converting the 7-column grid to a vertical list on mobile. The "dash for future dates" convention is fine but should use `aria-disabled="true"` on the cell rather than hiding it from the tab order entirely.

## Findings

### 1. Accessibility: ARIA Roles and Keyboard Navigation for the Calendar Grid

The W3C WAI-ARIA Authoring Practices Guide defines a **grid pattern** for exactly this kind of interactive two-dimensional layout. The calendar grid in the plan should use semantic ARIA roles rather than relying on visual CSS Grid alone.

**Concrete implementation:**

```html
<div role="grid" aria-label="Habit completions for week of May 19">
  <!-- Header row -->
  <div role="row">
    <div role="columnheader">Habit</div>
    <div role="columnheader">Mon 19</div>
    <div role="columnheader">Tue 20</div>
    <!-- ... -->
  </div>
  <!-- Data rows -->
  <div role="row" aria-label="Exercise">
    <div role="rowheader">Exercise</div>
    <div role="gridcell">
      <form method="POST" action="/habits/1/toggle/2026-05-19">
        <input type="hidden" name="csrf_token" value="...">
        <button type="submit" aria-label="Toggle Exercise for Monday May 19, currently completed" class="completed">
          <!-- green circle -->
        </button>
      </form>
    </div>
    <!-- ... -->
  </div>
</div>
```

**Key rules from the WAI-ARIA grid pattern:**

- Each clickable cell should contain a `<button>` with a descriptive `aria-label` that says: the habit name, the date, and the current state (completed/not completed). Example: `"Toggle Exercise for Monday May 19, currently completed"`.
- Arrow keys should move focus between gridcells. Without JS, this is not achievable natively -- Tab key will cycle through all buttons sequentially, which is acceptable for a no-JS baseline. The ARIA roles still help screen readers announce the grid structure.
- Future-date cells should use `aria-disabled="true"` on a `<span>` rather than omitting the element entirely. This tells screen readers "this cell exists but is not actionable" rather than creating a confusing gap. The `<span>` should NOT be a `<button>` since there is no action.
- Use `role="rowheader"` on the habit name column (not `role="gridcell"`) so screen readers announce the habit name as context for each row.

**Why `role="grid"` and not `role="table"`:** The W3C guidance says to use `role="grid"` when cells contain interactive elements (buttons/links). Use `role="table"` only for static data. Since our cells contain toggle buttons, `role="grid"` is correct.

### 2. Reducing Perceived Latency: Redirect with Fragment Anchors

The Feed-Forward concern is that toggling multiple past days in the calendar will feel slow because each toggle is a full POST + redirect + page reload. The user loses their scroll position each time.

**The no-JS solution: fragment anchors on redirect URLs.**

Each habit row gets an `id` attribute:

```html
<div role="row" id="habit-3" aria-label="Meditation">
```

The toggle route redirects back with the fragment:

```python
@habits_bp.route('/habits/<int:habit_id>/toggle/<target_date>', methods=['POST'])
def toggle_date(habit_id, target_date):
    # ... validation, toggle logic ...
    week_start = request.args.get('week', ...)
    return redirect(url_for('habits.calendar', week=week_start) + f'#habit-{habit_id}')
```

**How this helps:** After the POST, the browser loads the calendar page and immediately scrolls to the `#habit-3` anchor. The user's eyes stay on the row they were working with instead of jumping to the top.

**Limitation:** Fragment identifiers are not sent to the server, so this is purely a client-side scroll behavior. It works in all major browsers without JavaScript. However, the browser's exact scroll position may place the anchor at the very top of the viewport -- adding `scroll-margin-top` in CSS can offset this:

```css
[id^="habit-"] {
  scroll-margin-top: 80px; /* account for any sticky header */
}
```

**Additional latency reduction techniques (no JS required):**

- Keep the calendar page lightweight (no heavy assets). The plan's approach of a single `style.css` with no framework is already optimal.
- Use `Cache-Control` headers for static assets so only the HTML is re-fetched on redirect.
- Consider adding a `<meta http-equiv="x-dns-prefetch-control" content="on">` in the base template -- marginal but free.

### 3. Sticky Habit Name Column

**Yes, the habit name column should be sticky** when the grid overflows horizontally on narrow screens. Without it, users scrolling the date columns lose context about which row belongs to which habit.

**Implementation with CSS Grid:**

```css
.calendar-grid {
  display: grid;
  grid-template-columns: 120px repeat(7, minmax(48px, 1fr));
  gap: 4px;
  overflow-x: auto; /* enable horizontal scroll on narrow screens */
}

/* Sticky first column */
.calendar-grid [role="rowheader"],
.calendar-grid [role="columnheader"]:first-child {
  position: sticky;
  left: 0;
  background: white; /* must have opaque background to cover scrolling content */
  z-index: 1;
}
```

**Important caveats from CSS-Tricks research:**

- The sticky cell **must** have an opaque `background` set. Without it, the scrolling cells will be visible underneath.
- Use `z-index: 1` on sticky cells so they layer above the scrolling content.
- The `overflow-x: auto` belongs on the grid container (or a wrapper `<div>`), not on the grid cells.
- Per-axis sticky positioning is now natively supported in Chrome 148+ (March 2026), meaning `position: sticky` can stick to different scroll containers on different axes. For older browsers, the single-axis approach (sticky left only) works fine.

**Alternative for the plan's simpler case:** Since the plan only has 8 columns (1 label + 7 days), horizontal overflow will only happen on very narrow screens (< ~400px). See Finding #6 for the mobile responsive approach, which may eliminate the need for horizontal scroll entirely.

### 4. Visual Affordances: Clickable vs. Non-Clickable Cells

Research from Smashing Magazine and UX literature shows that the most important affordance is **cursor change + visual contrast**, not just color.

**Concrete CSS for the three states:**

```css
/* Clickable: completed (green circle) */
.cell-completed button {
  background: #22c55e;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  border: 2px solid transparent;
  cursor: pointer;
}
.cell-completed button:hover {
  border-color: #16a34a;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.3);
}
.cell-completed button:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* Clickable: not completed (gray circle) */
.cell-incomplete button {
  background: #e5e7eb;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  border: 2px solid transparent;
  cursor: pointer;
}
.cell-incomplete button:hover {
  background: #d1d5db;
  border-color: #9ca3af;
}
.cell-incomplete button:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* Non-clickable: future date */
.cell-future {
  display: flex;
  align-items: center;
  justify-content: center;
}
.cell-future span {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f3f4f6;
  opacity: 0.4;
  cursor: not-allowed; /* signals "you can't do this" */
}
```

**Key affordance rules:**

1. **Clickable cells use `<button>`** with `cursor: pointer` -- the browser's hand cursor is the strongest affordance for clickability.
2. **Non-clickable cells use `<span>`** with `cursor: not-allowed` -- visually distinct from pointer.
3. **Hover states only on clickable cells** -- the border/shadow change on hover confirms "this responds to interaction."
4. **`:focus-visible`** (not `:focus`) for keyboard focus rings -- prevents showing focus rings on mouse clicks while preserving them for keyboard users.
5. **Future cells have lower opacity (0.4)** -- the reduced opacity combined with the non-pointer cursor creates a clear "unavailable" signal.

**Accessibility note on disabled states:** Research from MDN and CSS-Tricks recommends using `aria-disabled="true"` on the `<span>` for future dates rather than the HTML `disabled` attribute. Reason: `disabled` removes the element from the tab order entirely, which can confuse keyboard-only users who "lose" cells in the grid. `aria-disabled="true"` keeps the element discoverable by screen readers while announcing it as non-functional. Since we are using a `<span>` (not a `<button>`), neither `disabled` nor `aria-disabled` adds native behavior -- but `aria-disabled` provides the screen reader announcement.

### 5. Future Dates: "Dash" Convention vs. Alternatives

The plan uses a light gray dash for future dates. This is **not a widely established convention** in habit tracker UIs. Research shows most popular habit trackers use one of these patterns:

| Pattern | Used By | Pros | Cons |
|---------|---------|------|------|
| **Faded/dimmed circle** | Habitify, Streaks | Consistent shape with completed/incomplete cells; clear visual hierarchy | Could be confused with "not completed" at a glance |
| **Empty cell (no indicator)** | Google Calendar, Notion | Clean; no visual noise for dates that haven't happened | Users may think data is missing |
| **Dash or line** | Plan's current proposal | Visually distinct from circles | Not a standard convention; may confuse users |
| **Grayed-out with date visible** | Most calendar apps | Shows the date exists but is inactive | Requires enough contrast for readability |

**Recommendation: Use a dimmed/faded circle at low opacity** instead of a dash. This keeps the visual shape consistent across all cells (completed = solid green circle, not completed = gray outline circle, future = very faint circle at 40% opacity). The consistent shape makes the grid scannable at a glance. The dash introduces a different visual shape that breaks the pattern and requires the user to learn a third symbol.

The dimmed circle also aligns with the "faded" convention used by iOS habit trackers (Streaks, Habitify) and calendar apps -- users already associate "faded = not yet available."

### 6. Mobile Responsiveness for 7-Column Grids

A 7-column grid with a label column (8 columns total) does not fit on a 375px mobile screen. Each cell needs at least 40-48px for a tap target (WCAG 2.5.5 Target Size minimum is 44x44px), so 8 columns x 44px = 352px minimum -- barely fits without any gap or padding.

**Two viable approaches:**

**Option A: Horizontal scroll with sticky first column (recommended for this app)**

Keep the 7-column grid but wrap it in a horizontally scrollable container. The habit name column sticks to the left.

```css
.calendar-wrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch; /* smooth momentum scroll on iOS */
}

.calendar-grid {
  display: grid;
  grid-template-columns: 100px repeat(7, 48px);
  gap: 4px;
  min-width: max-content; /* prevent grid from shrinking below minimum */
}
```

This preserves the weekly calendar mental model (users expect to see a full week). The horizontal scroll is a familiar pattern on mobile (tables, schedules, Trello boards).

**Option B: Stack to vertical list on mobile**

```css
@media (max-width: 500px) {
  .calendar-grid {
    grid-template-columns: 1fr;
  }
  /* Each row becomes: Habit Name, then 7 circles in a horizontal strip */
  .calendar-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }
}
```

This changes the mental model from "grid" to "list of habits with inline day indicators." It is more touch-friendly but loses the column alignment that lets you scan "how did I do on Wednesday across all habits?"

**Recommendation for the plan:** Go with **Option A (horizontal scroll)** because:
1. The weekly calendar is the core feature -- collapsing it defeats the purpose.
2. 7 columns of 48px circles fits in ~436px, meaning most phones can see 5-6 days without scrolling. Only 1-2 columns overflow.
3. The sticky first column keeps context visible during scroll.
4. Touch users intuitively understand horizontal swipe on data grids.

**Additional mobile consideration: tap target size.** WCAG 2.5.5 requires interactive targets to be at least 44x44 CSS pixels. The plan's circles should be sized accordingly:

```css
.cell-completed button,
.cell-incomplete button {
  min-width: 44px;
  min-height: 44px;
  /* visual circle can be smaller (32px) with padding to reach 44px touch target */
  padding: 6px;
}
```

## Recommended Plan Changes

- **Add `role="grid"`, `role="row"`, `role="rowheader"`, `role="columnheader"`, and `role="gridcell"` to the calendar HTML structure.** Each toggle button should have an `aria-label` describing the habit name, date, and current state. Add this to the "Weekly Calendar UI Design" section of the plan.

- **Add fragment anchor redirect to the toggle_date route.** After POST, redirect to `/calendar?week=YYYY-MM-DD#habit-{habit_id}`. Add `id="habit-{habit_id}"` to each habit row in the calendar template. Add `scroll-margin-top: 80px` to those IDs in CSS. This directly addresses the Feed-Forward "least confident" concern about perceived clunkiness.

- **Replace the "dash for future dates" with a dimmed circle at 40% opacity.** Keep the same shape (circle) for all three states -- solid green for completed, gray outline for not completed, faded circle for future. This is more consistent and matches established habit tracker conventions.

- **Add `cursor: pointer` to clickable cells and `cursor: not-allowed` to future cells.** Add `:hover` border/shadow effects to clickable buttons only. Add `:focus-visible` outlines for keyboard accessibility. These are the minimum visual affordances to distinguish clickable from non-clickable.

- **Use `aria-disabled="true"` on future date cells** instead of simply rendering a non-interactive element with no ARIA annotation. This makes the grid navigable by screen readers.

- **Add horizontal scroll with sticky first column for mobile.** Wrap the calendar grid in a scrollable container. Make the habit name column `position: sticky; left: 0` with opaque background. Set minimum button size to 44x44px for WCAG touch target compliance.

- **Add a line to the CSS section** specifying `scroll-margin-top` for habit row anchors and `-webkit-overflow-scrolling: touch` for the calendar wrapper.

- **No change needed** to the toggle logic, streak computation, database schema, or route structure. All recommendations are CSS/HTML template changes only.
