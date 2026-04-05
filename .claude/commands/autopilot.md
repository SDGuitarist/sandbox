---
name: autopilot
description: Full autonomous compound engineering loop with Feed-Forward, learnings, and handoffs
argument-hint: "[feature description]"
disable-model-invocation: true
---

Run these steps in order. Do not do anything else. Do not stop between steps — complete every step through to the end. This is an unattended automation run.

1. `/ralph-loop:ralph-loop "finish all slash commands" --completion-promise "DONE"`
2. `/compound-start $ARGUMENTS`
3. `/workflows:brainstorm $ARGUMENTS`
4. `/workflows:plan $ARGUMENTS`
5. `/compound-engineering:deepen-plan`
6. `/workflows:work`
7. `/workflows:review`
8. `/compound-engineering:resolve_todo_parallel`
9. `/workflows:compound`
10. `/update-learnings`
11. Output `<promise>DONE</promise>` — all phases complete

Start with step 1 now.
