"""
Deep Researcher — Managed Agents

Reuses the Console-created agent and environment. Sends a research query,
polls for completion, and prints the synthesized report.

Usage:
  python3 deep_researcher.py "your research question here"
  python3 deep_researcher.py --new "query"   # create fresh agent+env
  python3 deep_researcher.py --list          # list agents and sessions
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

API_KEY = os.environ["ANTHROPIC_API_KEY"]
BASE = "https://api.anthropic.com/v1"
HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY,
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "managed-agents-2026-04-01",
}

# Console-created resources (reuse instead of creating new ones each run)
DEFAULT_AGENT = "agent_011CZs2Cedr6QuQxu33GUadg"
DEFAULT_ENV = "env_01QM2ZuSpyXaefaAFxaFNen4"

SYSTEM_PROMPT = """You are a research agent. Given a question or topic:

1. Decompose it into 3-5 concrete sub-questions that, answered together, cover the topic.
2. For each sub-question, run targeted web searches and fetch the most authoritative sources (prefer primary sources, official docs, peer-reviewed work over blog posts and aggregators).
3. Read the sources in full. Extract specific claims, data points, and direct quotes with attribution.
4. Synthesize a report that answers the original question. Structure it by sub-question, cite every non-obvious claim inline, and close with a "confidence & gaps" section noting where sources disagreed or where you couldn't find good coverage.

Be skeptical. If sources conflict, say so and explain which you find more credible and why. Don't paper over uncertainty with confident-sounding prose."""


def api(method, path, payload=None):
    """Make an API call and return the JSON response."""
    fn = requests.post if method == "POST" else requests.get
    kwargs = {"headers": HEADERS}
    if payload:
        kwargs["json"] = payload
    resp = fn(f"{BASE}{path}", **kwargs)
    if not resp.ok:
        print(f"  API error {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    return resp.json()


# --- Resource management ---

def create_agent():
    print("Creating new agent...")
    agent = api("POST", "/agents", {
        "name": "Deep researcher",
        "description": "Multi-step web research with source synthesis and citations.",
        "model": "claude-sonnet-4-6",
        "system": SYSTEM_PROMPT,
        "tools": [{"type": "agent_toolset_20260401"}],
    })
    print(f"  Agent: {agent['id']}")
    return agent["id"]


def create_environment():
    print("Creating new environment...")
    env = api("POST", "/environments", {
        "name": "research-env",
        "description": "Unrestricted internet access for web research.",
    })
    print(f"  Environment: {env['id']}")
    return env["id"]


def list_resources():
    print("=== Agents ===")
    agents = api("GET", "/agents").get("data", [])
    for a in agents:
        model = a.get("model", {}).get("id", "?")
        print(f"  {a['id']}  {a['name']:<25} model={model}")

    print("\n=== Environments ===")
    envs = api("GET", "/environments").get("data", [])
    for e in envs:
        net = e.get("config", {}).get("networking", {}).get("type", "?")
        print(f"  {e['id']}  {e['name']:<25} net={net}")

    print("\n=== Recent Sessions ===")
    sessions = api("GET", "/sessions").get("data", [])
    for s in sessions[:10]:
        usage = s.get("usage", {})
        out = usage.get("output_tokens", 0)
        status = s.get("status", "?")
        title = s.get("title") or "(untitled)"
        print(f"  {s['id']}  {status:<10} {out:>6} tokens  {title[:50]}")


# --- Session lifecycle ---

def start_session(agent_id, env_id, query):
    print(f"Starting session...")
    session = api("POST", "/sessions", {
        "environment_id": env_id,
        "agent": {"type": "agent", "id": agent_id},
    })
    sid = session["id"]
    print(f"  Session: {sid}")

    print(f"  Query: {query[:80]}...")
    api("POST", f"/sessions/{sid}/events", {
        "events": [{
            "type": "user.message",
            "content": [{"type": "text", "text": query}],
        }],
    })
    print("  Sent. Agent is researching...\n")
    return sid


def poll_session(sid):
    start = time.time()

    while True:
        session = api("GET", f"/sessions/{sid}")
        status = session.get("status", "unknown")
        usage = session.get("usage", {})
        out_tokens = usage.get("output_tokens", 0)
        elapsed = time.time() - start

        print(f"  [{elapsed:>5.0f}s] {status:<10} | {out_tokens:>6} output tokens")

        if status == "idle" and out_tokens > 0:
            return session
        if status in ("failed", "cancelled", "error"):
            print(f"\n  Session {status}: {session.get('error', 'unknown')}")
            return session

        time.sleep(5)


def get_report(sid):
    """Extract the agent's final message from session events."""
    data = api("GET", f"/sessions/{sid}/events")
    events = data.get("data", data) if isinstance(data, dict) else data

    report_parts = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "agent.message":
            for block in ev.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    report_parts.append(block["text"])

    return "\n".join(report_parts) if report_parts else None


def print_results(session, sid):
    report = get_report(sid)

    print("\n" + "=" * 60)
    print("RESEARCH REPORT")
    print("=" * 60 + "\n")

    if report:
        print(report)
    else:
        print("(Could not extract report. Raw session data:)")
        print(json.dumps(session, indent=2)[:3000])

    usage = session.get("usage", {})
    stats = session.get("stats", {})
    cache = usage.get("cache_creation", {})

    print("\n" + "-" * 60)
    print(f"Active time:    {stats.get('active_seconds', 0):.1f}s")
    print(f"Total time:     {stats.get('duration_seconds', 0):.1f}s")
    print(f"Input tokens:   {usage.get('input_tokens', 0):,}")
    print(f"Output tokens:  {usage.get('output_tokens', 0):,}")
    print(f"Cache read:     {usage.get('cache_read_input_tokens', 0):,}")
    print(f"Cache written:  {cache.get('ephemeral_5m_input_tokens', 0):,}")
    print("-" * 60)


# --- Main ---

def main():
    args = sys.argv[1:]

    if "--list" in args:
        list_resources()
        return

    new_mode = "--new" in args
    if new_mode:
        args.remove("--new")

    if args:
        query = " ".join(args)
    else:
        query = "What are the key differences between Claude's Agent SDK and the new Managed Agents API? When should you use each?"
        print(f"Using default query:\n  {query}\n")

    if new_mode:
        agent_id = create_agent()
        env_id = create_environment()
    else:
        agent_id = DEFAULT_AGENT
        env_id = DEFAULT_ENV
        print(f"Reusing Console agent: {agent_id}")
        print(f"Reusing Console env:   {env_id}\n")

    sid = start_session(agent_id, env_id, query)
    session = poll_session(sid)
    print_results(session, sid)


if __name__ == "__main__":
    main()
