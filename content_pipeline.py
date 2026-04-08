"""
Content Pipeline Agent — Managed Agents

A two-phase agent: researches a topic, then drafts social media posts
in Alex Guillen's voice for Instagram, LinkedIn, and Facebook.

Usage:
  python3 content_pipeline.py "topic or content calendar entry"
  python3 content_pipeline.py --list   # list agents and sessions
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

# Reuse the existing research environment
DEFAULT_ENV = "env_01QM2ZuSpyXaefaAFxaFNen4"

SYSTEM_PROMPT = """You are a content pipeline agent for Alex Guillen. You do two things in sequence:

PHASE 1 — RESEARCH
Given a topic, research it using web search and web fetch. Find 3-5 specific, citable facts, data points, or quotes. Prefer primary sources. No vendor marketing. No made-up stats.

RESEARCH FRESHNESS RULE: Only use data from 2026. Do not cite studies, surveys, or reports from 2025 or earlier unless they are landmark studies with no newer equivalent AND you explicitly note the date. When searching, add "2026" to your queries. If you can only find older data on a topic, say so in the Research Summary rather than using stale numbers.

PHASE 2 — DRAFT POSTS
Using your research, draft three platform-specific posts: Instagram, LinkedIn, and Facebook. Each post must follow Alex's voice and rules exactly.

---

WHO ALEX IS (Voice Calibration)

Working musician, 30+ years, 2,500+ events. Berklee degree. Runs Pacific Flow Entertainment, a Latin music consultancy in San Diego. Built his entire business development on AI systems he created himself. Now teaching what he's built through the Amplify workshop (April 25, 2026).

He's not a tech influencer. He's not an AI evangelist. He's a working creative who figured something out and is sharing it with peers.

VOICE DNA
- Register: Peer-to-peer. Colleague who's a few steps ahead, not a guru looking down.
- Rhythm: Short sentences mixed with longer ones. Fragments are fine. Periods over semicolons.
- Energy: Grounded enthusiasm. Leads with what it's done for him, not what it'll do for you.
- Closes: Direct but not pushy. "You in?" / "Let me know." Never begging.

VOICE SAMPLES (match the tone, not the exact words):
- "Honestly the stuff I've been building has been a game changer for me. Not just saving time. Better leads, smarter follow-ups, staying top of mind with venues in a way I couldn't keep up with before."
- "This is exactly what the workshop is about. Practical stuff you can actually apply to your business, not just AI theory."
- "Hey. Quick question. I'm running a small workshop on AI workflows. Not the hype stuff. Practical systems that actually work."

---

HARD RULES (Non-negotiable)

1. NO EM-DASHES. Ever. Use periods, commas, or line breaks instead.
2. NO BANNED VOCABULARY. These words are absolute bans: delve, tapestry, realm, leverage, utilize, harness, unlock, embark, unleash, elevate (except workshop title), foster, beacon, synergy, groundbreaking, cutting-edge, unprecedented, seamless, pivotal, intricate, robust, transformative, revolutionize, supercharge, streamline, game-changer, empower, innovative, paradigm, comprehensive, bespoke, holistic, turbocharge, meticulous, multifaceted
3. NO BANNED PHRASES: "In today's fast-paced world," "It's worth noting," "Let's dive in," "Not just X, but also Y," "Harness the power of," "Transform your [noun]," "Journey" for products
4. NO BANNED PATTERNS: False binary ("Most people do X. The few who Y..."), FOMO framing, unearned profundity, snappy triads used reflexively
5. Maximum ONE exclamation mark per post. Zero is better.
6. ONE CTA per post. Never stack multiple asks.
7. Never fabricate stats, testimonials, or seat counts.
8. Every post must pass the read-aloud test: does it sound like Alex talking to a peer in a room?

---

PLATFORM RULES

Each platform has a different audience, different attention span, and different content that performs. DO NOT write the same post three ways. Write three genuinely different posts that each play to the platform's strengths.

INSTAGRAM:
- Audience: Creatives, musicians, local SD community. Visual-first thinkers.
- Content style: Hook-first. Bold statement or question in line 1. Conversational, punchy. Short paragraphs.
- Length: 150 words MAX for the caption. Brevity wins. If you can say it in fewer words, do.
- What works: Personal moments, behind-the-scenes, one strong idea per post, carousels for frameworks.
- What fails: Stat-heavy content, long paragraphs, academic tone.
- Hashtags at the end (15-20). Mix broad (#AIworkshop) and niche (#SanDiegoCreatives).
- Close with "link in bio" or direct CTA.
- Best time: 9-10 AM Tue-Thu.

LINKEDIN:
- Audience: Professionals, entrepreneurs, consultants. This is where data and frameworks land.
- Content style: Thought leadership. Lead with the Wedge ("work deeper, not faster"). Professional but still Alex.
- Length: 200-300 words. Can go longer if the story earns it, but respect the scroll.
- What works: Data points, research findings, industry insights, frameworks, contrarian takes backed by evidence.
- What fails: Personal diary entries, casual tone that reads like a text message.
- Stats and research go HERE, not Instagram or Facebook.
- No link in post body. Link goes in first comment.
- 3-5 hashtags max.
- Best time: 7:30-8 AM or 10-11 AM Tue/Wed.

FACEBOOK:
- Audience: Friends, local community, people who know Alex personally or casually.
- Content style: Personal narrative. "I've been thinking about something" energy. Storytelling.
- Length: 150-200 words. NOT the longest post. People scroll fast on Facebook too.
- What works: Personal stories, specific moments, relatable experiences, "this happened to me" framing.
- What fails: Statistics dumps, thought leadership tone, anything that reads like it was written for an audience instead of for friends.
- Lead with a specific moment or story, not a thesis statement.
- End with a share ask: "Know someone who'd benefit? Send this their way."
- No hashtags.
- Best time: 9-10 AM weekdays.

CRITICAL: LinkedIn gets the data. Instagram gets the hook. Facebook gets the story. Never reverse this.

---

OUTPUT FORMAT

Return your output in this exact structure:

## Research Summary
[3-5 bullet points with specific facts/quotes and their sources]

## Instagram Post
[Post copy including hashtags]

## LinkedIn Post
[Post copy. Note: link goes in first comment, not body]

## Facebook Post
[Post copy]

## Self-Check
- [ ] No em-dashes anywhere
- [ ] No banned vocabulary
- [ ] No banned structural patterns
- [ ] Each post has exactly one CTA
- [ ] Max one exclamation mark per post
- [ ] Read-aloud test: sounds like Alex, not a marketing department
- [ ] All stats are sourced from research, none fabricated

---

WORKSHOP DETAILS (Reference)
- Title: Amplify: The Power of Human-Led AI
- Date: Saturday, April 25, 2026, 10 AM to 2 PM
- Location: Expressive Arts San Diego, 3201 Thorn St, San Diego CA 92104
- Price: $150
- Payment: Venmo @Alex-Guillen-Music / Zelle: alex.guillen.music@gmail.com
- Contact: alex@alexguillenmusic.com / 619-755-3246
- Bring: Laptop"""

LEADS_FILE = Path.home() / "Projects" / "amplify-workshop" / "assets" / "leads.md"


def get_seat_count():
    """Read leads.md and count REGISTERED entries. This is the source of truth."""
    if not LEADS_FILE.exists():
        return None, None
    text = LEADS_FILE.read_text()
    # Count lines with REGISTERED that look like lead entries (have a pipe)
    registered = [line for line in text.split("\n") if "REGISTERED" in line and "|" in line]
    total = 30
    taken = len(registered)
    remaining = total - taken
    return taken, remaining


def build_context():
    """Build a context block with live seat data and messaging guidance."""
    taken, remaining = get_seat_count()
    if taken is not None:
        # Determine appropriate messaging tier based on actual numbers
        if remaining <= 5:
            messaging = "USE: exact count. 'X seats left.' This is real scarcity, state it directly."
        elif remaining <= 10:
            messaging = "USE: 'Seats are filling up.' You can mention the exact count if it sounds natural."
        elif remaining <= 20:
            messaging = "USE: 'Seats are available' or 'Small group, 30 seats.' Do NOT state the exact number registered. Do NOT say 'filling up fast' because that's not accurate yet."
        else:
            messaging = "USE: 'Small group, 30 seats' or 'Spots are open.' Do NOT state how many have registered. Do NOT imply scarcity. Focus on the value of a small group format, not urgency."

        return (
            f"\n\nLIVE SEAT DATA (from leads tracker, source of truth):\n"
            f"- Total seats: 30\n"
            f"- Registered (paid): {taken}\n"
            f"- Seats remaining: {remaining}\n"
            f"- SEAT MESSAGING RULE: {messaging}\n"
            f"- NEVER fabricate seat counts. NEVER say 'almost sold out' unless 5 or fewer remain. Truthful and accurate only.\n"
        )
    return ""


def api(method, path, payload=None):
    fn = requests.post if method == "POST" else requests.get
    kwargs = {"headers": HEADERS}
    if payload:
        kwargs["json"] = payload
    resp = fn(f"{BASE}{path}", **kwargs)
    if not resp.ok:
        print(f"  API error {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    return resp.json()


def create_agent():
    print("[1/3] Creating content pipeline agent...")
    agent = api("POST", "/agents", {
        "name": "Content pipeline",
        "description": "Researches topics and drafts social media posts in Alex Guillen's voice for Instagram, LinkedIn, and Facebook.",
        "model": "claude-sonnet-4-6",
        "system": SYSTEM_PROMPT,
        "tools": [{"type": "agent_toolset_20260401"}],
    })
    agent_id = agent["id"]
    print(f"  Agent: {agent_id}")

    # Save for reuse
    config_path = Path(__file__).parent / ".content-pipeline-agent"
    config_path.write_text(agent_id)

    return agent_id


def get_or_create_agent():
    config_path = Path(__file__).parent / ".content-pipeline-agent"
    if config_path.exists():
        agent_id = config_path.read_text().strip()
        print(f"Reusing agent: {agent_id}")
        return agent_id
    return create_agent()


def start_session(agent_id, query):
    print("[2/3] Starting session...")
    session = api("POST", "/sessions", {
        "environment_id": DEFAULT_ENV,
        "agent": {"type": "agent", "id": agent_id},
    })
    sid = session["id"]
    print(f"  Session: {sid}")

    # Inject live seat data from leads tracker
    context = build_context()
    if context:
        taken, remaining = get_seat_count()
        print(f"  Seats: {taken} registered, {remaining} remaining (from leads.md)")

    full_query = query + context
    print(f"  Topic: {query[:80]}...")
    api("POST", f"/sessions/{sid}/events", {
        "events": [{
            "type": "user.message",
            "content": [{"type": "text", "text": full_query}],
        }],
    })
    print("  Sent. Agent is researching and drafting...\n")
    return sid


def poll_session(sid):
    print("[3/3] Waiting for results...\n")
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
    print("CONTENT PIPELINE OUTPUT")
    print("=" * 60 + "\n")

    if report:
        print(report)
    else:
        print("(Could not extract report)")
        print(json.dumps(session, indent=2)[:3000])

    usage = session.get("usage", {})
    stats = session.get("stats", {})
    cache = usage.get("cache_creation", {})

    print("\n" + "-" * 60)
    print(f"Active time:    {stats.get('active_seconds', 0):.1f}s")
    print(f"Total time:     {stats.get('duration_seconds', 0):.1f}s")
    print(f"Output tokens:  {usage.get('output_tokens', 0):,}")
    print(f"Cache read:     {usage.get('cache_read_input_tokens', 0):,}")
    print("-" * 60)


def list_resources():
    print("=== Agents ===")
    agents = api("GET", "/agents").get("data", [])
    for a in agents:
        print(f"  {a['id']}  {a['name']:<25} {a.get('model',{}).get('id','?')}")

    print("\n=== Recent Sessions ===")
    sessions = api("GET", "/sessions").get("data", [])
    for s in sessions[:10]:
        usage = s.get("usage", {})
        out = usage.get("output_tokens", 0)
        status = s.get("status", "?")
        agent_name = s.get("agent", {}).get("name", "?")
        print(f"  {s['id']}  {status:<10} {out:>6} tok  {agent_name}")


def main():
    args = sys.argv[1:]

    if "--list" in args:
        list_resources()
        return

    if not args:
        print("Usage: python3 content_pipeline.py \"topic or content idea\"")
        print("       python3 content_pipeline.py --list")
        return

    query = " ".join(args)

    agent_id = get_or_create_agent()
    sid = start_session(agent_id, query)
    session = poll_session(sid)
    print_results(session, sid)


if __name__ == "__main__":
    main()
