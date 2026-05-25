"""Calibrate Monte Carlo relevance weights from actual build history.

Parses the Update Log in agent-pitfalls.md and self-audit reports to compute
empirical FC occurrence rates per agent.
"""

import re
import json
from pathlib import Path

# --- Build history extracted from agent-pitfalls.md Update Log ---
# Format: (name, agent_count, fc_ids_observed)
# agent_count: number of swarm agents (1 for solo/manual builds)
# fc_ids_observed: FCs that had findings in this build

BUILDS = [
    # Pre-doc builds (referenced in FC descriptions as "Builds hit")
    ("Health Journal", 3, ["fc1"]),
    ("Bookmark Manager", 3, ["fc1", "fc4"]),
    ("Project Tracker", 3, ["fc2", "fc4", "fc5"]),
    ("Notes API", 3, ["fc4", "fc7"]),
    ("Personal Finance Tracker", 3, ["fc7"]),
    ("Flask Acid Test", 3, ["fc2"]),
    ("Task Tracker", 3, ["fc2"]),
    ("Ethics Toolkit (13-agent)", 13, ["fc1", "fc5", "fc6", "fc16", "fc17", "fc18", "fc19", "fc20", "fc22"]),
    ("Lead-Scraper (May 5-9)", 1, ["fc13", "fc14", "fc21"]),
    ("WRC Build #7 (13 agents)", 13, ["fc1", "fc2", "fc4", "fc5", "fc9", "fc10", "fc27"]),

    # Post-doc builds from Update Log
    ("Venue Scraper Cycle 2", 1, []),  # FC11, FC12 are orchestrator-level, not agent
    ("Tunestamp Power Features", 6, ["fc15", "fc22", "fc23"]),
    ("Lead-Scraper Reliability", 1, ["fc21"]),
    ("WRC Screenplay Ingestion", 1, ["fc24", "fc25", "fc26", "fc27"]),
    ("Workshop Registration Hub", 8, ["fc28", "fc29", "fc30", "fc31"]),
    ("WRC Auth Refactor", 1, ["fc32"]),
    ("WRC Voice Override (run 043)", 1, ["fc24"]),
    ("Feedback Board (run 045)", 1, []),  # P1s were init_db pattern, not FC-classified
    ("Invoice & CRM (run 046)", 15, ["fc9", "fc33", "fc34"]),
    ("Solopreneur Command Center (run 047)", 16, ["fc4"]),
    ("Client Music Planner (run 048)", 20, ["fc4", "fc31"]),
    ("VenueConnect (run 049)", 25, ["fc4", "fc35", "fc36", "fc37"]),
    ("GigSheet (run 050)", 31, ["fc3", "fc10", "fc26", "fc29", "fc35", "fc38", "fc39", "fc40"]),
    ("Lead-Scraper Cross-Pollination", 1, ["fc4", "fc5", "fc41", "fc42"]),
    ("RestaurantOps (run 052)", 29, ["fc1", "fc4", "fc29"]),
    ("CoWorkFlow (run 055)", 22, ["fc1"]),
    ("CoWorkFlow Deferred (run 056)", 1, ["fc43", "fc44"]),
    ("BrewOps (run 057)", 21, ["fc5", "fc35", "fc45", "fc46"]),
    ("Gig Lead Responder P3", 1, []),
    ("Client Intake Dashboard (run 058)", 15, ["fc1", "fc4", "fc10", "fc43", "fc47"]),
    ("Bookmark Tagger", 1, []),
    ("Habit Tracker Web (run 059)", 1, ["fc4"]),
]

# Only include swarm builds (agent_count >= 3) for relevance calculation
# Solo builds test different things (single agent, no coordination)
SWARM_THRESHOLD = 3


def compute_relevance() -> dict[str, dict]:
    """Compute empirical relevance for each FC from build history.

    relevance = P(at least one agent encounters this FC in a build)

    For swarm builds: relevance ≈ occurrences / applicable_builds
    Per-agent relevance ≈ occurrences / total_agent_runs
    """
    swarm_builds = [(name, agents, fcs) for name, agents, fcs in BUILDS
                    if agents >= SWARM_THRESHOLD]

    total_swarm_builds = len(swarm_builds)
    total_agent_runs = sum(agents for _, agents, _ in swarm_builds)

    # Count how many swarm builds each FC appeared in
    fc_build_count: dict[str, int] = {}
    fc_total_agents_exposed: dict[str, int] = {}

    for name, agents, fcs in swarm_builds:
        for fc_id in fcs:
            fc_build_count[fc_id] = fc_build_count.get(fc_id, 0) + 1
            fc_total_agents_exposed[fc_id] = fc_total_agents_exposed.get(fc_id, 0) + agents

    # Compute relevance two ways:
    # 1. Build-level: what fraction of builds had this FC?
    # 2. Agent-level: approximate per-agent probability
    results = {}
    all_fcs = set()
    for _, _, fcs in BUILDS:
        all_fcs.update(fcs)

    for fc_id in sorted(all_fcs):
        builds_hit = fc_build_count.get(fc_id, 0)
        agents_exposed = fc_total_agents_exposed.get(fc_id, 0)

        # Build-level relevance: fraction of swarm builds where this FC appeared
        build_relevance = builds_hit / total_swarm_builds if total_swarm_builds > 0 else 0

        # Per-agent relevance estimate:
        # If FC hit B builds totaling A agents, and each occurrence is typically
        # 1-2 agents, then per-agent rate ≈ occurrences / A
        # We assume ~1 agent per FC occurrence (conservative)
        per_agent = builds_hit / total_agent_runs if total_agent_runs > 0 else 0

        # Scale up: per-agent relevance should be higher than raw occurrence/agents
        # because the FC could have appeared more times but was caught by review.
        # Use build_relevance as a floor, per_agent as supplementary signal.
        # Heuristic: blend of build frequency and agent density
        relevance = min(build_relevance * 0.8, 1.0)  # cap at 1.0

        results[fc_id] = {
            "builds_hit": builds_hit,
            "total_swarm_builds": total_swarm_builds,
            "build_relevance": round(build_relevance, 3),
            "per_agent_rate": round(per_agent, 4),
            "calibrated_relevance": round(relevance, 3),
        }

    return results


def generate_relevance_dict(results: dict[str, dict]) -> dict[str, float]:
    """Generate the FLASK_SWARM_RELEVANCE dict for mc_simulator.py."""
    return {fc_id: data["calibrated_relevance"] for fc_id, data in results.items()}


def main():
    swarm_builds = [(name, agents, fcs) for name, agents, fcs in BUILDS
                    if agents >= SWARM_THRESHOLD]

    print(f"Total builds: {len(BUILDS)}")
    print(f"Swarm builds (>= {SWARM_THRESHOLD} agents): {len(swarm_builds)}")
    print(f"Total agent-runs in swarm builds: {sum(a for _, a, _ in swarm_builds)}")

    print(f"\n{'FC':<8} {'Builds':<8} {'Build%':<8} {'Per-Agent':<10} {'Calibrated'}")
    print(f"{'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*10}")

    results = compute_relevance()
    for fc_id in sorted(results.keys(), key=lambda x: results[x]["calibrated_relevance"], reverse=True):
        data = results[fc_id]
        print(f"{fc_id:<8} {data['builds_hit']:<8} {data['build_relevance']:<8.0%} "
              f"{data['per_agent_rate']:<10.4f} {data['calibrated_relevance']:.3f}")

    # Print as Python dict for mc_simulator.py
    print("\n\n# --- Paste into mc_simulator.py as FLASK_SWARM_RELEVANCE ---")
    print("CALIBRATED_RELEVANCE = {")
    rel = generate_relevance_dict(results)
    for fc_id in sorted(rel.keys()):
        print(f'    "{fc_id}": {rel[fc_id]},')
    print("}")

    # Also save as JSON
    out_path = Path("calibration/relevance-weights.json")
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({
            "metadata": {
                "total_builds": len(BUILDS),
                "swarm_builds": len(swarm_builds),
                "total_agent_runs": sum(a for _, a, _ in swarm_builds),
                "swarm_threshold": SWARM_THRESHOLD,
            },
            "fc_details": results,
            "calibrated_relevance": rel,
        }, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
