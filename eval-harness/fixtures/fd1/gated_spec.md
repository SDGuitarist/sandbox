# Demo Spec (gated / CONVERGED copy)

This stands in for the spec the pre-swarm gates actually validated on the
orchestrator's FEATURE branch — the converged version. The runner commits this on
the feature branch.

Because this differs from the worktree-base copy, the shipped FC52 detector
(`tools/check_spec_provenance.py`, the SAME one SKILL Step 9w.9.5 now calls) must
report PROVENANCE_DRIFT before any worker spawns. A positive control in the runner
also commits this identical copy on BOTH branches and asserts PROVENANCE_OK — so
the fixture proves the detector discriminates, not that it always cries drift.
