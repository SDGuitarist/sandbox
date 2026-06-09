"""Orchestration-hardening negative-test fixtures.

Each fixture sets up a deliberately broken input and asserts the corresponding
SHIPPED guard catches it. Fixtures EXERCISE the guards read-only; they never edit
or reimplement gate logic.

The cardinal rule (Feed-Forward risk of the plan): never test a *copy* of a
guard. A fixture that passes against a Python reimplementation proves nothing
about the artifact the autopilot pipeline actually runs -- that is the FC52/M1
gate/use drift the hardening exists to kill, reborn inside the validator. So the
fidelity label of any fixture whose "guard" is a Python mirror is `MIRRORED`,
never `EXERCISED`.
"""
