# Vague Demo Spec (F-C1 — Track C scorer fixture)

A deliberately under-specified spec. Its only job is to make the shipped spec-eval
SCORER run and emit a verdict + JSON report — proving the scorer is real callable
infrastructure (layer 1, EXERCISED). The point is NOT which verdict appears (the
vague rows below will likely FAIL the scorer); the fixture tolerates any verdict
and asserts only that the scorer ran and produced structured output.

## Routes

| Method | Path | Validation | Error Response |
|--------|------|-----------|----------------|
| POST | /login | validate the credentials | return an error |
| POST | /signup | check the email | reject if bad |

The validation cells ("validate the credentials", "check the email") are vague —
they don't say HOW — so the scorer can exercise its judgment. That is exactly the
class of spec Track C's advisory gate was built to flag, and exactly why the gate
is ADVISORY (layer 2): its observed precision is ~0%, so it informs the self-audit
but never blocks the spawn.
