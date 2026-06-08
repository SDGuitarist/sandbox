# Roadmap to Fully-Unattended Autopilot

**Status:** Active
**Owner:** Alejandro Guillen
**Last updated:** 2026-06-07
**Goal:** `/autopilot "build the producer app"` → walk away → working, reviewed, committed app. Zero human touches between the one-line description and a passing build.

---

## 0. What "fully unattended" actually means

There are two kinds of human touch in the loop, and they are NOT the same problem:

- **Verification touches** — a human reading a spec or a diff to *catch a defect the machine missed*. These are the obstacle. The entire roadmap is about converting each one into a deterministic gate. Target: **zero.**
- **Authority touches** — a human approving an *outward, hard-to-reverse action* (push to remote, merge to master). These are gated **on purpose** by the safety contract (`CLAUDE.md` → Forbidden Actions, and `~/.claude/CLAUDE.md` → Safety Rule). They are not bugs to remove.

**So "fully unattended" = zero verification touches.** The build runs, gates itself, swarms, assembles, reviews, fixes, and compounds with no human in the loop. The *publish* decision (merge/push) may remain a one-keystroke human gate at the very end — that is a policy choice, not a failure of automation. We call this state **unattended-to-green**: everything up to "ready to merge" is hands-off.

---

## 1. Where the line is drawn today

The `/autopilot` skill **already runs fully unattended from a converged plan** (skill line 10: *"Run the full compound engineering pipeline unattended. After planning and deepening..."*). Zero-prompt execution was achieved on build #6 and held through Run 069 (24 agents).

The attended half is everything *before* the skill starts — turning an idea into a verified swarm spec.

| Phase | Today | Roadmap target |
|---|---|---|
| **A. Plan convergence** (idea → verified spec: deepen → Codex → human structural verify) | ⚠️ Attended | ✅ Unattended |
| **B. Pre-swarm gates** (9w.5/9w.6 completeness + consistency) | ✅ Unattended | ✅ Unattended |
| **C. Swarm execution** (spawn → assemble → smoke/test) | ✅ Unattended | ✅ Unattended |
| **D. Review + fix** (review agents → resolve-todos) | ✅ Unattended | ✅ Unattended |
| **E. Compound** (solution doc → learnings propagation → self-audit) | ✅ Unattended | ✅ Unattended |
| **F. Publish** (push branch / merge to master) | ⚠️ Authority touch | ⚠️ Stays a human gate by policy |

**The whole game is shrinking box A to nothing.** B–E are already there. F is intentionally human.

---

## 2. The strategy: convert every human-catch into a gate

The method is not "hope the AI gets good enough." It is mechanical:

> Every time the human convergence pass catches a defect class, encode that class as a deterministic pre-swarm gate. The human never has to catch *that class* again. Drive the human's catch-rate asymptotically to zero, one failure class (FC) at a time.

This is already proven. Run 069's three biggest manual fixes (B3, C1, C6 — all wrong orchestration-entrypoint signatures) became **Track B / FC50**: an automated gate that now *fails the build pre-spawn* if any entrypoint signature is missing. Human-catch → machine-gate. That is the template for everything below.

---

## 3. Progress ledger — fixes already shipped

These were built in the orchestration-hardening refactor (branch `feat/cpaa-event-replay-simulator`, Codex **GO ×3**, reviewed-but-not-field-proven):

| Track | Failure class | Human-catch it eliminates | Status |
|---|---|---|---|
| **A** | FC51 — assembly base divergence | Manual cherry-pick intervention when worktrees root on a different base than the feature branch | ✅ Shipped, unproven |
| **B** | FC50 — unpinned orchestration entrypoints | Human catching wrong route→module / tool→constants signatures in review | ✅ Shipped, unproven |
| **C** | spec-eval gate precision | A human **`WAIVED_BY_HUMAN`** stop-and-approve decision (was waived 2-for-2) | ✅ Shipped (demoted to advisory) |

Plus the migration noted at skill lines 338–339: cross-section contradiction checks "that Codex would do in manual flow" are being moved into the automated 9w.5/9w.6 gates.

**Next milestone: `validate-on-real-build`** — the next real feature swarm must exercise all three tracks in one run and its reports must contain: the **9w.6 PASS**, the **advisory spec-eval log**, and a **per-worker cherry-pick base in `assembly-summary.md`**. A 9w.6 false-FAIL that aborts before Track A = validation incomplete, not pass. Until this passes, the three tracks are reviewed but not trusted.

---

## 4. Remaining human touchpoints in box A — and the fix that kills each

This is the backlog. Each row is a verification touch still required during plan convergence. The "Kills it" column names the future gate that converts it.

| # | Human touchpoint (today) | Why a human still does it | Kills it (future gate / FC) | State |
|---|---|---|---|---|
| A1 | **Cross-section P0 hunt** — human reads spec sections side-by-side to find contradictions (a field defined one way in §5, used another way in §8) | Documented as "non-optional" because each section is internally consistent but incompatible across sections; AI historically misses these | A **cross-section consistency gate** that diffs every shared field/type/signature across all spec sections and FAILs on mismatch. This is the generalization of FC50 from "signatures" to "all shared declarations." | 🔴 Not built — **the keystone fix** |
| A2 | **Fixture/golden-value sanity** — human confirms seed data, hashes, and golden corpus values are real, not placeholders | Run 069 shipped `EMPTY_PROJECTION_HASH = "0"*64` placeholder (FC9); human computed the real value | A **placeholder-detector gate**: scan constants/fixtures for obvious placeholders (`"0"*N`, `TODO`, `0xDEAD`, empty hashes) and FAIL pre-swarm. Plus auto-run `compute_golden.py` post-assembly. | 🔴 Not built |
| A3 | **Spec-eval waiver judgment** — when spec-eval flags artifacts, a human decides waive vs abort | Gate had ~0% field precision | ✅ **Track C already killed this** — demoted to advisory, no human decision | 🟢 Done |
| A4 | **Auth-matrix completeness** — human spot-checks that every read+write route has the right `@login_required` / ownership rule | Run 069: V2 missed `@login_required` on a GET detail endpoint (FC27, neighbor-pattern skip) | An **authorization-matrix gate**: cross-check the spec's Authorization Matrix (§6) against actual route decorators post-assembly; FAIL on any route absent from the matrix or missing its prescribed guard | 🔴 Not built |
| A5 | **"Is this spec even buildable" gut-check** — human reads the whole plan once to confirm it hangs together | The deepest, least-formalizable judgment | Partially covered by 9w.5/9w.6 today. Long-tail: a **spec-eval harness** scoring buildability — but only re-promoted if its precision is fixed (see deferred items). | 🟡 Partial |
| A6 | **App selection / trigger** | A human decides *what* to build | Intentional entry point — `/autopilot "<description>"` IS the human's one allowed input. Not a defect. | ⚪ By design |

**Reading the ladder:** A3 is done. A1, A2, A4 are the three concrete gates that, once built and field-proven, would collapse box A to near-zero. A5 is the irreducible-judgment long tail. A6 is the intended one-line human input and stays.

---

## 5. The asymptote — and an honest limit

You will reach **unattended-to-green per app-class before you reach it for arbitrary novel specs.** Once the gates have seen enough Flask+SQLite+Jinja swarm specs, a new app in that family converges with no human catches. A genuinely novel architecture may surface a *new* cross-section failure mode the gates haven't encoded yet — and that one run needs a human, who then encodes it as the next FC.

So the true end-state is not "the human is gone forever." It is:

> **The human is only ever needed once per newly-discovered failure class — and after they encode it, never again for that class.** For known app-classes, the catch-rate is already effectively zero.

That is a strictly shrinking obligation. Each run either passes clean (no human catch → proof the gates hold) or surfaces exactly one new FC (→ the next track). There is no steady-state where the human is doing repetitive verification.

---

## 6. The validation protocol (how every run shrinks box A)

This makes the producer app — and every build after it — pull double duty as both an app and a hardening probe.

1. Run plan convergence **attended**, but treat it as a **control group**: log *every* defect the human pass catches that the automated gates did **not**.
2. Each logged catch is classified: is it an existing FC the gates should have caught (→ gate bug), or a new FC (→ new track in §4)?
3. Launch the swarm. Confirm the run's reports contain the validation proofs for whichever tracks are live.
4. After review, fold each new FC into `~/.claude/docs/agent-pitfalls.md` and open the corresponding gate as the next fix.
5. **Exit test for "fully unattended (this app-class)":** two consecutive swarm builds in the same stack where the human convergence pass catches **zero** defects the gates didn't already block.

---

## 7. Definition of done

**Unattended-to-green is achieved for an app-class when:**

- [ ] `validate-on-real-build` passes (all three current tracks field-proven in one run)
- [ ] A1 cross-section consistency gate built + field-proven
- [ ] A2 placeholder/fixture gate built + field-proven
- [ ] A4 authorization-matrix gate built + field-proven
- [ ] Two consecutive same-stack builds with **zero human-only catches** (the §6 exit test)
- [ ] Authority touches (push/merge) remain the only human interaction — by policy, not by gap

When those hold: `/autopilot "<one line>"` → unattended through review → stops at "ready to merge" for a single human keystroke. That is the goal.

---

## 8. Immediate next action

Pick the next swarm app (leaning: producer app) and run its convergence **as the validation probe in §6**. The manual planning is not the permanent state — it is the control group that proves the gates can replace it. Every human catch logged this run is the blueprint for the gate that removes it next run.

> Related: `HANDOFF.md` (validate-on-real-build gate), `BUILD_TRACKING.md` (Run 069 FC catalog), `docs/solutions/2026-06-07-autopilot-orchestration-hardening.md` (Tracks A/B/C rationale), `~/.claude/docs/agent-pitfalls.md` (cross-project FC registry).
