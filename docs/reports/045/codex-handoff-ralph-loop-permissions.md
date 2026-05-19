# Codex Handoff: Ralph Loop Permission Fix Risk Assessment

## Context

Read these files first:
- `CLAUDE.md` (sandbox operating contract, especially "Bash Command Rules" and "Forbidden Actions")
- `.claude/settings.local.json` (current project permissions)
- `~/.claude/settings.json` (global permissions -- look at `permissions.allow` array)

## Problem Statement

Ralph Loop is a session iteration plugin used during autopilot builds. Its setup
script (`setup-ralph-loop.sh`) fails with a permission error even though
`dangerouslySkipPermissions: true` is set in `.claude/settings.local.json`.

**Exact error:**
```
Shell command permission check failed for pattern
"/Users/alejandroguillen/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/scripts/setup-ralph-loop.sh"
finish all slash commands --completion-promise DONE
: This command requires approval
```

## Diagnosis

Claude Code has a three-layer permission model:

| Layer | Scope | `dangerouslySkipPermissions` covers it? |
|-------|-------|----------------------------------------|
| 1. Global allow list (`~/.claude/settings.json`) | Direct Bash tool calls | Yes |
| 2. Project override (`.claude/settings.local.json`) | Direct Bash tool calls | Yes |
| 3. Plugin command scope (`allowed-tools` in command .md) | Shell scripts via plugin commands | **No** |

The Ralph Loop command definition at
`~/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/commands/ralph-loop.md`
declares:
```yaml
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/setup-ralph-loop.sh:*)"]
```

This Layer 3 permission is evaluated separately from `dangerouslySkipPermissions`.
The security heuristic also sees the unquoted multi-word arguments
(`finish all slash commands --completion-promise DONE`) as suspicious.

## Proposed Fix

Add explicit Bash permission patterns for both Ralph Loop scripts to the
project settings:

```json
{
  "permissions": {
    "dangerouslySkipPermissions": true,
    "allow": [
      "Bash(/Users/alejandroguillen/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/scripts/setup-ralph-loop.sh *)",
      "Bash(/Users/alejandroguillen/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/hooks/stop-hook.sh *)"
    ]
  }
}
```

## Questions for Codex to Assess

### 1. Security Risk of the Allow Pattern

The `*` wildcard at the end of each pattern permits ANY arguments to these
two scripts. Is this safe?

- `setup-ralph-loop.sh` accepts: a prompt string, `--max-iterations N`,
  `--completion-promise "TEXT"`. It writes a YAML state file to
  `.claude/ralph-loop.local.md`. It does NOT execute the prompt, access
  the network, or modify code.
- `stop-hook.sh` reads the state file, reads the transcript, checks for
  a completion promise, and either feeds the prompt back or ends the loop.
  It does NOT modify code or access the network.

**Risk question:** Could a malicious or hallucinated argument to either
script cause harm? (e.g., path traversal in the state file location,
command injection via the prompt string, etc.)

### 2. Version Pinning Fragility

The paths contain `1.0.0` (the plugin version). If the plugin updates to
`1.1.0`, the allow patterns break and Ralph Loop fails silently again.

**Options to assess:**
- **A. Hardcode `1.0.0`** -- breaks on update, requires manual fix
- **B. Use glob `*/scripts/*`** -- does `.claude/settings.local.json` support
  glob patterns in `allow` entries? If so, is `ralph-loop/*/scripts/*` safe?
- **C. Use `${CLAUDE_PLUGIN_ROOT}` variable** -- does the settings parser
  expand environment variables? If so, this would be version-independent.
- **D. Move to global settings** -- add the pattern to `~/.claude/settings.json`
  so it applies to all projects. Risk: broader scope than needed.

### 3. Scope of `dangerouslySkipPermissions`

Our diagnosis says `dangerouslySkipPermissions` only covers Layers 1-2
(direct Bash calls), not Layer 3 (plugin command scopes). Is this accurate?

If so, is this a Claude Code bug/limitation that should be reported, or is
it intentional design (plugins should manage their own permissions)?

### 4. Alternative: Skip Ralph Loop in Autopilot

Ralph Loop provides iteration safety (re-checks if promise isn't met).
The autopilot skill already has its own completion flow (the `<promise>DONE</promise>`
tag). Is Ralph Loop actually load-bearing for autopilot, or is it redundant?

If redundant, the simplest fix is to remove the Ralph Loop step from the
autopilot skill entirely, avoiding the permission problem altogether.

### 5. Stop Hook Permissions

The stop hook (`stop-hook.sh`) runs on the `Stop` event via `hooks.json`.
Even if the setup script is fixed, will the stop hook also fail? Does the
hook execution path go through the same three-layer permission model, or
do hooks have a separate permission mechanism?

## What I Need Back

1. **GO/NO-GO** on the proposed settings.local.json change
2. **Recommended approach** for version pinning (A, B, C, or D)
3. **Assessment** of whether Ralph Loop is load-bearing or redundant for autopilot
4. **Risk rating** (P1/P2/P3) for each concern raised
5. If the proposed fix is rejected, an **alternative approach**

## Files to Read for Full Context

| File | Why |
|------|-----|
| `~/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/scripts/setup-ralph-loop.sh` | The blocked script (257 lines) |
| `~/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/hooks/stop-hook.sh` | The stop hook (192 lines) |
| `~/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/hooks/hooks.json` | Hook registration |
| `~/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/commands/ralph-loop.md` | Command definition with `allowed-tools` |
| `~/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/plugin.json` | Plugin metadata |
| `.claude/settings.local.json` | Current project permissions |
| `~/.claude/settings.json` | Global permissions (the `allow` array format) |
| `.claude/skills/autopilot/SKILL.md` | Where Ralph Loop is invoked (Step 1) |
