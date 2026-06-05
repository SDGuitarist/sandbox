"""Monte Carlo simulator for swarm build failure prediction.

Uses eval harness pass rates to model: "Given these injected rules and
this many agents, what's the probability of a clean build?"
"""

import json
import sys
from pathlib import Path

import numpy as np

# --- Load eval harness data ---

def load_fc_rates(report_json: Path) -> dict[str, dict]:
    """Load per-FC pass rates from eval harness report JSON."""
    with open(report_json) as f:
        data = json.load(f)

    rates = {}
    for fc in data["fc_scores"]:
        rates[fc["fc_id"]] = {
            "with_rule": fc["pass_rate_with_rule"],
            "without_rule": fc["pass_rate_without_rule"] or 0.0,
            "delta": fc["delta"] or 0.0,
        }
    return rates


# --- Build profiles ---
# Relevance = probability that a given agent in this build type encounters this FC.
# Estimated from 18 build histories. 0.0 = never relevant, 1.0 = every agent hits it.

# Calibrated from 20 swarm builds, 255 total agent-runs
# Source: calibrate_relevance.py -> calibration/relevance-weights.json
FLASK_SWARM_RELEVANCE = {
    "fc1": 0.28,   # naming divergence -- 7/20 builds
    "fc2": 0.16,   # wrong usage inferred -- 4/20 builds
    "fc4": 0.36,   # validation gap -- 9/20 builds (most common)
    "fc5": 0.16,   # swarm consistency -- 4/20 builds
    "fc7": 0.08,   # route prefix doubling -- 2/20 builds
    "fc9": 0.08,   # mock mismatch -- 2/20 builds
    "fc10": 0.12,  # fail-open -- 3/20 builds
    "fc15": 0.04,  # window.location -- 1/20 builds
    "fc16": 0.04,  # non-idempotent DDL -- 1/20 builds
    "fc17": 0.04,  # duplicate boilerplate -- 1/20 builds
    "fc19": 0.04,  # unsigned tokens -- 1/20 builds
    "fc20": 0.04,  # cron concurrency -- 1/20 builds
    "fc23": 0.04,  # anon RLS -- 1/20 builds
    "fc24": 0.0,   # XML sandbox escape -- 0 swarm builds (solo only)
    "fc25": 0.0,   # zip bomb -- 0 swarm builds (solo only)
    "fc26": 0.04,  # comment not code -- 1/20 builds
    "fc27": 0.04,  # neighbor pattern skip -- 1/20 builds
    "fc28": 0.04,  # proxy path stripping -- 1/20 builds
    "fc29": 0.12,  # no transaction boundary -- 3/20 builds
    "fc33": 0.04,  # transitive deps -- 1/20 builds
    "fc35": 0.12,  # IDOR -- 3/20 builds
    "fc36": 0.04,  # FTS5 injection -- 1/20 builds
    "fc39": 0.04,  # app per job -- 1/20 builds
    "fc41": 0.0,   # cost cap -- 0 swarm builds (solo only)
    "fc46": 0.04,  # phantom FK -- 1/20 builds
    "fc47": 0.04,  # Markup XSS -- 1/20 builds
}


def simulate_build(
    n_agents: int,
    fc_rates: dict[str, dict],
    injected_rules: set[str],
    relevance: dict[str, float],
    rng: np.random.Generator,
) -> bool:
    """Simulate one swarm build. Returns True if clean (no failures)."""
    for agent_idx in range(n_agents):
        for fc_id, rel in relevance.items():
            if fc_id not in fc_rates:
                continue

            # Does this agent encounter this FC?
            if rng.random() > rel:
                continue  # FC not relevant to this agent

            # What's the pass rate?
            if fc_id in injected_rules:
                p_pass = fc_rates[fc_id]["with_rule"]
            else:
                p_pass = fc_rates[fc_id]["without_rule"]

            # Did the agent pass?
            if rng.random() > p_pass:
                return False  # Build failed

    return True


def run_mc(
    n_agents: int,
    fc_rates: dict[str, dict],
    injected_rules: set[str],
    relevance: dict[str, float],
    n_trials: int = 10_000,
    seed: int = 42,
) -> dict:
    """Run Monte Carlo simulation and return results."""
    rng = np.random.default_rng(seed)

    clean_builds = 0
    for _ in range(n_trials):
        if simulate_build(n_agents, fc_rates, injected_rules, relevance, rng):
            clean_builds += 1

    p_clean = clean_builds / n_trials
    return {
        "n_agents": n_agents,
        "n_trials": n_trials,
        "n_rules_injected": len(injected_rules),
        "p_clean_build": p_clean,
        "p_failure": 1 - p_clean,
        "injected": sorted(injected_rules),
        "skipped": sorted(set(fc_rates.keys()) - injected_rules),
    }


def find_minimum_injection_set(
    n_agents: int,
    fc_rates: dict[str, dict],
    relevance: dict[str, float],
    target_p_clean: float = 0.95,
    n_trials: int = 10_000,
    seed: int = 42,
) -> list[dict]:
    """Find the minimum set of rules to inject to hit target clean build probability.

    Strategy: start with zero rules, greedily add the highest-delta rule
    until target is met. Returns the progression.
    """
    # Sort FCs by delta (highest impact first)
    ranked = sorted(
        fc_rates.items(),
        key=lambda x: x[1]["delta"],
        reverse=True,
    )

    injected = set()
    progression = []

    # Baseline: no rules
    result = run_mc(n_agents, fc_rates, injected, relevance, n_trials, seed)
    progression.append({
        "step": 0,
        "added": "(none)",
        "delta": 0,
        "n_injected": 0,
        "p_clean": result["p_clean_build"],
    })

    for fc_id, rates in ranked:
        if rates["delta"] <= 0:
            continue  # Skip zero/negative delta rules

        injected.add(fc_id)
        result = run_mc(n_agents, fc_rates, injected, relevance, n_trials, seed)
        progression.append({
            "step": len(progression),
            "added": fc_id,
            "delta": rates["delta"],
            "n_injected": len(injected),
            "p_clean": result["p_clean_build"],
        })

        if result["p_clean_build"] >= target_p_clean:
            break

    return progression


def main():
    report_path = Path("reports/2026-05-24-1336.json")
    if not report_path.exists():
        print(f"Report not found: {report_path}")
        sys.exit(1)

    fc_rates = load_fc_rates(report_path)

    print("=" * 70)
    print("MONTE CARLO BUILD FAILURE SIMULATOR")
    print("=" * 70)

    # --- Scenario 1: All rules injected ---
    all_rules = set(fc_rates.keys())
    for n_agents in [10, 15, 20, 25, 31]:
        result = run_mc(n_agents, fc_rates, all_rules, FLASK_SWARM_RELEVANCE)
        print(f"\n  {n_agents} agents, ALL {len(all_rules)} rules injected:")
        print(f"    P(clean build) = {result['p_clean_build']:.1%}")

    # --- Scenario 2: No rules injected ---
    print("\n" + "-" * 70)
    no_rules: set[str] = set()
    for n_agents in [10, 15, 20, 25, 31]:
        result = run_mc(n_agents, fc_rates, no_rules, FLASK_SWARM_RELEVANCE)
        print(f"\n  {n_agents} agents, NO rules injected:")
        print(f"    P(clean build) = {result['p_clean_build']:.1%}")

    # --- Scenario 3: Only load-bearing rules ---
    print("\n" + "-" * 70)
    load_bearing = {fc_id for fc_id, r in fc_rates.items() if r["delta"] > 0}
    for n_agents in [10, 15, 20, 25, 31]:
        result = run_mc(n_agents, fc_rates, load_bearing, FLASK_SWARM_RELEVANCE)
        print(f"\n  {n_agents} agents, {len(load_bearing)} load-bearing rules only:")
        print(f"    P(clean build) = {result['p_clean_build']:.1%}")
        print(f"    Skipped: {sorted(all_rules - load_bearing)}")

    # --- Scenario 4: Minimum injection set for 95% clean at 25 agents ---
    print("\n" + "=" * 70)
    print("MINIMUM INJECTION SET (target: 95% clean build, 25 agents)")
    print("=" * 70)

    progression = find_minimum_injection_set(
        n_agents=25,
        fc_rates=fc_rates,
        relevance=FLASK_SWARM_RELEVANCE,
        target_p_clean=0.95,
    )

    print(f"\n  {'Step':<5} {'Added':<8} {'Delta':<8} {'Rules':<7} {'P(clean)'}")
    print(f"  {'-'*5} {'-'*8} {'-'*8} {'-'*7} {'-'*10}")
    for step in progression:
        print(
            f"  {step['step']:<5} {step['added']:<8} "
            f"{step['delta']:<8.0%} {step['n_injected']:<7} "
            f"{step['p_clean']:.1%}"
        )

    final = progression[-1]
    print(f"\n  Result: {final['n_injected']} rules needed for "
          f"{final['p_clean']:.1%} clean build rate")
    print(f"  Saved: {len(all_rules) - final['n_injected']} rules removed from briefs")

    # --- Scenario 5: What if we fix the ambiguous rules? ---
    print("\n" + "=" * 70)
    print("WHAT-IF: FIX AMBIGUOUS RULES TO 100% WITH_RULE PASS RATE")
    print("=" * 70)

    fc_rates_fixed = {k: dict(v) for k, v in fc_rates.items()}
    for fc_id in ["fc10", "fc14", "fc41"]:
        if fc_id in fc_rates_fixed:
            fc_rates_fixed[fc_id]["with_rule"] = 1.0

    for n_agents in [10, 15, 20, 25, 31]:
        result_before = run_mc(n_agents, fc_rates, all_rules, FLASK_SWARM_RELEVANCE)
        result_after = run_mc(n_agents, fc_rates_fixed, all_rules, FLASK_SWARM_RELEVANCE)
        improvement = result_after["p_clean_build"] - result_before["p_clean_build"]
        print(f"\n  {n_agents} agents: {result_before['p_clean_build']:.1%} -> "
              f"{result_after['p_clean_build']:.1%} (+{improvement:.1%})")

    # --- Scenario 6: Fixed rules + load-bearing only ---
    print("\n" + "-" * 70)
    print("FIXED RULES + LOAD-BEARING ONLY (optimal strategy)")
    print("-" * 70)

    progression_fixed = find_minimum_injection_set(
        n_agents=25,
        fc_rates=fc_rates_fixed,
        relevance=FLASK_SWARM_RELEVANCE,
        target_p_clean=0.95,
    )

    print(f"\n  {'Step':<5} {'Added':<8} {'Delta':<8} {'Rules':<7} {'P(clean)'}")
    print(f"  {'-'*5} {'-'*8} {'-'*8} {'-'*7} {'-'*10}")
    for step in progression_fixed:
        print(
            f"  {step['step']:<5} {step['added']:<8} "
            f"{step['delta']:<8.0%} {step['n_injected']:<7} "
            f"{step['p_clean']:.1%}"
        )

    final_fixed = progression_fixed[-1]
    if final_fixed["p_clean"] >= 0.95:
        print(f"\n  TARGET HIT: {final_fixed['n_injected']} rules for "
              f"{final_fixed['p_clean']:.1%} clean build rate")
    else:
        print(f"\n  Target not reached: {final_fixed['p_clean']:.1%} with "
              f"{final_fixed['n_injected']} rules")


if __name__ == "__main__":
    main()
