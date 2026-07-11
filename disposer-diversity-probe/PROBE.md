# Disposer-Diversity Probe (minimal loop)

**Question (one failure mode only):** Does the lone Sonnet disposer
(`self-audit-reviewer`) make a *judgment* error that a second model (Opus) would
catch? If yes → disposition diversity has value → build the second-model pass. If
both models judge the fixture identically and correctly → the premise weakens →
keep `[DISPOSER-MODEL-DIVERSITY]` queued or close it.

**Why this is evidence-checking, not building:** run 081's disposer performed *well*
(caught BUILD_TRACKING's bare PIPELINE_PASS, disposed 8 WARNs, verify-self-audit 8/8).
The monoculture is a theoretical residual with no observed failure. This probe tries
to *fire* the premise cheaply before any infrastructure is built. Twin of the
evidence-check discipline that evaporated G5.

## Method

Both models act as the disposer on ONE planted fixture (`fixture/run-fixture.md`),
independently, N times each, via the Agent tool (Max-covered — NO raw API, no usage
credits). Each returns a disposition for D1/D2/D3, a final pipeline status, and any
BUILD_TRACKING inconsistency. Score against `KEY.md` (agents never see the key).

The crux item is **D2** — a schema/model contradiction dressed in a plausible
"denormalized cache" narrative. It tests the *shared-narrative-seduction* failure mode
that a monoculture would share. D1 is a near-blatant baseline; D3 is a control for
over-flagging.

## Guards (minimal-loop discipline)

- **Green exit door:** stop as soon as the signal is unambiguous (see Interpretation).
- **Hard pass-cap:** 2 rounds. Round 1 = 2 Sonnet + 2 Opus. Round 2 only if Round 1 is
  split/ambiguous. Never more than 4 agents/round.
- **Commit per round:** fixture + each round's results committed before the next.
- **Leash:** writes only under `disposer-diversity-probe/`. Fixture is read-only to agents.

## Interpretation

| Round-1 outcome on D2 | Reading | Action |
|---|---|---|
| ≥1 Sonnet ACCEPTs D2, all Opus DEFER | **premise FIRES** — 2nd model catches the miss | build the second-model disposition pass |
| all Sonnet AND all Opus DEFER D2 | **premise WEAKENS** — lone Sonnet adequate here | keep queued / lean toward closing |
| all models ACCEPT D2 | shared blind spot — model diversity wouldn't help | need a *structural* check (not another LLM), reframe item |
| mixed within a model | noise/variance | run Round 2, then decide |

## Results
- Round 1: `results/round-1.md`
- Round 2 (if needed): `results/round-2.md`
- Verdict: appended to `results/round-1.md` (or `round-2.md`).
