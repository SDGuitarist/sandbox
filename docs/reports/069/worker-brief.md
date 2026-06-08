# CPAA Run 069 — Shared Swarm Worker Brief

You are a swarm worker for CPAA Run 069 (24-agent build). Build against the
**FROZEN, converged, binding-reviewed spec**. Do NOT modify the plan.

## READ FIRST (both are in your worktree / on disk)

1. **The full shared spec:**
   `docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md` — read it
   FULLY (§1–§16). It is the single source of truth for every name, signature,
   route, schema, transaction contract, and coordinated behavior. Your exact
   assignment is your row in **§15 Swarm Agent Assignment**.
2. **The pitfalls registry:**
   `/Users/alejandroguillen/.claude/docs/agent-pitfalls.md` — apply general
   failure classes FC1–FC10 always, plus the per-agent-type rules for your role.

## STRICT RULES

1. Create ONLY your assigned files — nothing else.
2. Use EXACT names from the spec's **§5 Export Names Table** for every function,
   route, blueprint, endpoint, class, constant, template, and variable. If a
   name is not in the spec, do not invent one — use the simplest name matching
   spec patterns. (FC1)
3. No design decisions — the spec decides everything.
4. Import across agent boundaries ONLY as defined in the **§6 Cross-Boundary
   Wiring Table**. Match the return TYPE in §5 when naming variables. (FC2/FC3)
5. Follow the **§2 directory structure** exactly. Every file lives under
   `cpaa-replay/`.
6. Ambiguity → simplest interpretation.
7. No extra features, comments, or TODOs beyond the spec. (FC26: never write a
   comment claiming a mitigation you didn't implement.)
8. Production-quality code. No placeholders.
9. Create any directories your files need.
10. **Transaction boundaries (FC29):** follow **§9 Transaction Contracts**
    exactly. Commit ONLY if the spec says your function commits; otherwise let
    the caller own the transaction. Python 3.14 + sqlite3: use `with conn:` for
    commit scope (FC6/FC14). Never `executescript()` inside a `with conn:`.
11. **Validate every input in your own handler** even if you think another layer
    does it (FC4). For new routes, copy the full guard chain the spec
    prescribes — auth → CSRF → validation → business logic → error handling
    (FC27). Access control / infra errors fail CLOSED, never open (FC10).
12. **Bash:** one command per call, no `&&`/`;`/loops/`cd`/`python3 -c`,
    no `echo` for file content (FC8). Use the Write tool for files.

## WHEN DONE (FC37 — uncommitted work is lost)

From your worktree root (your working directory):
- `git add <your assigned files>`
- `git commit -m "<role>: <concise description>"`

Then reply with ONLY a short summary: your role, the files you created, your
commit hash, the cross-boundary exports you created, and the cross-boundary
imports you used. **Do NOT paste file contents** — keep the reply compact.
