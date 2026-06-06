---
title: "Prompting Dashboard Engine (Run 064)"
date: 2026-06-02
run_id: "064"
project: prompt-dashboard
tags: [flask, sqlite, fernet, encryption, swarm, bootstrap, wizard, csrf, idor, share-tokens]
build_method: swarm
agents: 12
files: 62
loc: 3800
status: complete
---

# Prompting Dashboard Engine (Run 064)

## What Was Built

A multi-user Flask + SQLite + Jinja2 + Bootstrap 5 dashboard for Amplify AI's 12-component expert-led prompting method. Three access modes: anonymous share-token visitors, authenticated workshop users, and one admin (Alex). Fernet encryption at rest for prompt content and component answers. Share tokens with SHA-256 hashing.

- **8 blueprints:** auth, wizard, library, grading, sharing, admin, search, export
- **12 database tables** + 1 FTS5 virtual table with 4 triggers
- **62 source files**, ~3800 LOC
- **21/22 smoke tests passing** (1 encryption verification fixed by P1-1 resolution)

## What Went Right

### Spec quality drove zero-conflict assembly (agent-to-agent)
The 12-agent swarm produced 62 files with 0 inter-agent merge conflicts. All conflicts were ghost-file cleanup (Run 061 artifacts). The shared interface spec with all 6 mandatory sections enabled clean vertical splitting.

### Ghost-file cleanup (FC48) caught pre-swarm
26 files from Run 061 detected and removed before swarm launch. The Step 9w.8 cleanup gate added after Run 063 worked correctly.

### Deepening caught critical transaction bug
The architecture-strategist deepening agent identified that autocommit=True requires explicit BEGIN for multi-statement atomicity. This was a P1 fix applied before swarm launch.

## What Went Wrong

### Python 3.14 autocommit + BEGIN/commit silently drops data (P1-1)
The deepening fix (explicit `conn.execute('BEGIN')` + `conn.commit()`) was correct for Python 3.12-3.13 but fails in Python 3.14. The `with conn:` context manager pattern is the only reliable approach. This is a new FC6 variant.

### Wizard agent created hardcoded component models (spec divergence)
The wizard agent ignored the database-backed component_definitions table and created hardcoded Python dicts with completely different component names and clusters. This required a full rewrite of component_models.py and industry_models.py during assembly, plus rewriting all wizard routes.

### Auth agent didn't get its own worktree (FC37 variant)
Agent a7e94ac9 (auth) was assigned to the grading agent's worktree instead of getting its own. The auth files had to be created manually on a separate branch. This is a new variant of FC37 — the agent completed its task but in the wrong worktree.

### Over-encryption of guidance fields (P1-2)
industry_models.py incorrectly applied Fernet encryption to guidance_text (admin-authored, non-sensitive data). This was a neighboring-pattern over-application — the agent saw encrypt/decrypt in adjacent model files and copied the pattern without checking the spec's Encrypted Fields table.

## Risk Resolution (Feed-Forward)

**Risk:** "Fernet encryption/decryption integration with wizard form flow — if key missing/wrong, all saved prompts unreadable"

**What happened:** The encryption module itself worked correctly — startup validation, encrypt/decrypt, empty-string handling. The actual failure mode was "data never written due to Python 3.14 transaction behavior" (P1-1), not encryption key issues. The encryption was the least-buggy part.

**Lesson:** The brainstorm correctly identified the risk area but predicted the wrong failure mode. Transaction behavior changes in Python 3.14 were not foreseeable from prior builds.

## Patterns Worth Reusing

### autocommit=True + `with conn:` for multi-statement writes
In Python 3.14+, the only reliable pattern for multi-statement atomic writes with autocommit=True is `with conn:`. Explicit `BEGIN`/`commit()` silently fails.

### Encrypted Fields Table in spec
Listing every encrypted column explicitly prevented ad-hoc encryption decisions by agents (though one agent still over-applied).

### Ghost-file cleanup gate (Step 9w.8)
Second consecutive build where this gate caught prior-project artifacts. Worth keeping permanent.

## Process Improvements Identified

### 1. Log assembly-phase rewrites in BUILD_TRACKING FAILURES
The wizard agent required a full rewrite during assembly (hardcoded components → DB-backed). This was an FC2 instance but never got a FAILURES row because FAILURES only tracks review-phase findings. Assembly rewrites are significant events that should be logged with failure class attribution. Update the autopilot tracking template to include assembly-phase entries.

### 2. Spec-conformance spot-check at assembly
The ownership gate checks whether agents wrote to correct file paths. It does not check whether the code matches the spec's prescribed data model. For the wizard agent, a grep like "does component_models.py query component_definitions table?" would have caught the divergence before a full rewrite. Consider adding a lightweight content check per agent branch at merge time.

### 3. Pin transaction syntax in spec template
Prescribe `with conn:` directly in the spec template instead of allowing agents to choose between `with conn:`, explicit `BEGIN`/`commit()`, or other patterns. The spec already prescribes transaction boundaries — it should also prescribe the exact syntax. This prevents Python-version-dependent behavior surprises.

### 4. Separate deepening from swarm launch session
Pre-swarm density (15 deepening fixes + 3 consistency rounds + 2 doc reviews in Run 064) consumed significant context before agents launched. Consider: deepen in one session, commit the deepened plan, launch the swarm in a fresh session. The plan is a file — it survives session boundaries. This trades one extra session start for lower context death risk.

## Metrics

| Metric | Value |
|--------|-------|
| Swarm agents | 12 (1 manual worktree fix) |
| Files produced | 62 |
| Lines of code | ~3800 |
| Merge conflicts | 0 (inter-agent), 4 (ghost-file cleanup) |
| Smoke tests | 21/22 PASS (fixed to 22/22 by P1-1 fix) |
| Review findings | 6 (2 P1, 3 P2, 1 P3) |
| All P1s fixed | Yes |
| All P2s fixed | Yes |
| New FC variants | 1 (FC6: Python 3.14 autocommit+BEGIN data loss) |
