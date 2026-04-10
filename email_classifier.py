"""
Email Classifier — Advisor Strategy (Custom Tool Proxy)

Classifies emails using Haiku as executor with a custom consult_advisor tool
that routes to Opus when Haiku decides it needs help. Tests executor-driven
self-escalation behavior.

Usage:
  python3 email_classifier.py              # classify 20 sample emails
  python3 email_classifier.py --verbose     # show each classification as it runs

See: docs/plans/2026-04-09-feat-advisor-email-classifier-plan.md
"""

import json
import os
import sys
import time
from dataclasses import dataclass
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
}

RESULTS_FILE = Path(__file__).parent / "email_classifier_results.jsonl"

# --- Config ---


@dataclass(frozen=True)
class EmailClassifierConfig:
    executor_model: str = "claude-haiku-4-5-20251001"
    advisor_model: str = "claude-opus-4-6"
    max_tokens: int = 1024
    advisor_max_tokens: int = 512


CONFIG = EmailClassifierConfig()

# --- Tool definition ---

ADVISOR_TOOL = {
    "name": "consult_advisor",
    "description": (
        "Consult a senior advisor for a second opinion on email "
        "classification. Use this when you are uncertain about whether "
        "an email is a genuine lead or sophisticated marketing/spam."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email_summary": {
                "type": "string",
                "description": "Brief summary of the email and sender",
            },
            "preliminary_classification": {
                "type": "string",
                "description": "Your initial classification category",
            },
            "confidence": {
                "type": "number",
                "description": "Your confidence 0-1",
            },
            "uncertainty_reason": {
                "type": "string",
                "description": "What specifically makes you uncertain",
            },
        },
        "required": [
            "email_summary",
            "preliminary_classification",
            "confidence",
            "uncertainty_reason",
        ],
    },
}

# --- System prompts ---

EXECUTOR_SYSTEM_PROMPT = """You are an email classifier for a freelance music composer named Alex. Classify each email into one of these categories:

HIGH-STAKES (must surface):
- gig_inquiry: music/sound work availability, rates, projects
- business_opportunity: workshop bookings, consulting, partnerships
- genuine_networking: industry contacts, collaborators, real people

LOW-PRIORITY (safe to defer):
- subscription: newsletters, digests
- marketing: promotional emails
- notification: GitHub, services, receipts
- social_digest: social media notifications

Before classifying any email as low-priority, consider whether it could be a real lead. If there is ANY chance the email is from a real person seeking work, business, or connection, use the consult_advisor tool before making your final decision.

Return your classification as JSON (no markdown fencing): {"category": "...", "confidence": 0.0-1.0, "reasoning": "..."}"""

ADVISOR_SYSTEM_PROMPT = """You are a senior email classification advisor. A junior classifier is uncertain about an email. Review their preliminary assessment and the email details. Return JSON (no markdown fencing): {"category": "...", "confidence": 0.0-1.0, "reasoning": "..."}

Focus on whether this could be a real lead that should not be missed. When in doubt, classify as high-stakes."""

# --- Haiku pricing per 1M tokens (April 2026) ---
HAIKU_INPUT_COST = 0.80  # per 1M input tokens
HAIKU_OUTPUT_COST = 4.00  # per 1M output tokens
OPUS_INPUT_COST = 15.00  # per 1M input tokens
OPUS_OUTPUT_COST = 75.00  # per 1M output tokens


# --- API helper ---


def api(method, path, payload):
    """Make an API call and return the JSON response."""
    fn = requests.post if method == "POST" else requests.get
    resp = fn(f"{BASE}{path}", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()


# --- Advisor routing ---


def call_advisor(tool_input, config=CONFIG):
    """Route a consult_advisor tool call to Opus and return guidance."""
    advisor_query = (
        f"A junior email classifier needs your help.\n\n"
        f"Email summary: {tool_input['email_summary']}\n"
        f"Preliminary classification: {tool_input['preliminary_classification']}\n"
        f"Confidence: {tool_input['confidence']}\n"
        f"Uncertainty reason: {tool_input['uncertainty_reason']}\n\n"
        f"Review their assessment and return your recommendation."
    )

    resp = api("POST", "/messages", {
        "model": config.advisor_model,
        "max_tokens": config.advisor_max_tokens,
        "system": ADVISOR_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": advisor_query}],
    })

    text = "".join(
        b.get("text", "") for b in resp.get("content", []) if b["type"] == "text"
    )
    usage = resp.get("usage", {})
    return text, usage


# --- Classification ---


def classify_email(email, config=CONFIG):
    """Classify a single email using the multi-turn advisor flow.

    Returns a dict with classification result and metrics.
    """
    email_text = (
        f"From: {email['sender']}\n"
        f"Subject: {email['subject']}\n\n"
        f"{email['body']}"
    )

    t0 = time.time()

    # Step 1: Send to Haiku with tool
    resp1 = api("POST", "/messages", {
        "model": config.executor_model,
        "max_tokens": config.max_tokens,
        "tools": [ADVISOR_TOOL],
        "system": EXECUTOR_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": f"Classify this email:\n\n{email_text}"}],
    })

    usage1 = resp1.get("usage", {})
    api_calls = 1
    escalated = resp1.get("stop_reason") == "tool_use"
    advisor_usage = {}
    advisor_text = ""
    tool_input = {}
    haiku_preliminary = None
    haiku_confidence = None
    haiku_uncertainty_reason = None

    if escalated:
        # Extract tool call
        tool_use = next(
            b for b in resp1["content"] if b["type"] == "tool_use"
        )
        tool_input = tool_use["input"]
        tool_id = tool_use["id"]
        haiku_preliminary = tool_input.get("preliminary_classification")
        haiku_confidence = tool_input.get("confidence")
        haiku_uncertainty_reason = tool_input.get("uncertainty_reason")

        # Step 2: Route to Opus
        advisor_text, advisor_usage = call_advisor(tool_input, config)
        api_calls += 1

        # Step 3: Return guidance to Haiku
        resp3 = api("POST", "/messages", {
            "model": config.executor_model,
            "max_tokens": config.max_tokens,
            "tools": [ADVISOR_TOOL],
            "system": EXECUTOR_SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": f"Classify this email:\n\n{email_text}"},
                {"role": "assistant", "content": resp1["content"]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": advisor_text,
                        }
                    ],
                },
            ],
        })
        api_calls += 1
        final_content = resp3.get("content", [])
        usage3 = resp3.get("usage", {})
    else:
        final_content = resp1.get("content", [])
        usage3 = {}

    latency_ms = int((time.time() - t0) * 1000)

    # Parse final classification JSON
    final_text = "".join(
        b.get("text", "") for b in final_content if b["type"] == "text"
    )
    classification = parse_classification(final_text)

    # Parse advisor recommendation if escalated
    advisor_recommendation = None
    advisor_reasoning = None
    if escalated and advisor_text:
        advisor_parsed = parse_classification(advisor_text)
        advisor_recommendation = advisor_parsed.get("category")
        advisor_reasoning = advisor_parsed.get("reasoning")

    # Compute costs
    executor_in = usage1.get("input_tokens", 0) + usage3.get("input_tokens", 0)
    executor_out = usage1.get("output_tokens", 0) + usage3.get("output_tokens", 0)
    advisor_in = advisor_usage.get("input_tokens", 0)
    advisor_out = advisor_usage.get("output_tokens", 0)
    total_cost = (
        executor_in * HAIKU_INPUT_COST / 1_000_000
        + executor_out * HAIKU_OUTPUT_COST / 1_000_000
        + advisor_in * OPUS_INPUT_COST / 1_000_000
        + advisor_out * OPUS_OUTPUT_COST / 1_000_000
    )

    final_category = classification.get("category", "unknown")
    advisor_changed = (
        escalated
        and haiku_preliminary is not None
        and haiku_preliminary != final_category
    )

    return {
        "email_id": email["id"],
        "sender": email["sender"],
        "subject": email["subject"],
        "ground_truth": email["ground_truth"],
        "should_escalate": email["should_escalate"],
        "haiku_preliminary": haiku_preliminary,
        "haiku_confidence": haiku_confidence,
        "haiku_uncertainty_reason": haiku_uncertainty_reason,
        "escalated": escalated,
        "advisor_recommendation": advisor_recommendation,
        "advisor_reasoning": advisor_reasoning,
        "advisor_changed_answer": advisor_changed,
        "final_decision": final_category,
        "final_confidence": classification.get("confidence"),
        "final_reasoning": classification.get("reasoning"),
        "executor_input_tokens": executor_in,
        "executor_output_tokens": executor_out,
        "advisor_input_tokens": advisor_in,
        "advisor_output_tokens": advisor_out,
        "total_cost_usd": round(total_cost, 6),
        "latency_ms": latency_ms,
        "api_calls": api_calls,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def parse_classification(text):
    """Extract JSON classification from model response text."""
    cleaned = text.strip()
    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass
        return {"category": "parse_error", "confidence": 0, "reasoning": cleaned[:200]}


# --- Logging ---


def log_result(result):
    """Append a classification result as one JSON line."""
    with open(RESULTS_FILE, "a") as f:
        f.write(json.dumps(result) + "\n")


# --- Summary ---

HIGH_STAKES = {"gig_inquiry", "business_opportunity", "genuine_networking"}


def print_summary(results):
    """Print the classification summary report."""
    total = len(results)
    errors = [r for r in results if r.get("error")]
    classified = [r for r in results if not r.get("error")]

    correct = sum(
        1 for r in classified if r["final_decision"] == r["ground_truth"]
    )

    # Lead safety
    high_stakes_emails = [
        r for r in classified if r["ground_truth"] in HIGH_STAKES
    ]
    high_stakes_correct = sum(
        1 for r in high_stakes_emails
        if r["final_decision"] in HIGH_STAKES
    )

    # Escalation confusion matrix
    tp = sum(1 for r in classified if r["should_escalate"] and r["escalated"])
    fn = sum(1 for r in classified if r["should_escalate"] and not r["escalated"])
    fp = sum(1 for r in classified if not r["should_escalate"] and r["escalated"])
    tn = sum(1 for r in classified if not r["should_escalate"] and not r["escalated"])

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0

    escalated_count = sum(1 for r in classified if r["escalated"])
    advisor_changed = sum(1 for r in classified if r["advisor_changed_answer"])

    total_cost = sum(r["total_cost_usd"] for r in classified)
    total_calls = sum(r["api_calls"] for r in classified)

    print(f"\n{'=' * 50}")
    print(f"  Email Classifier Results")
    print(f"{'=' * 50}")
    print(f"Total emails: {total}")
    if errors:
        print(f"Errors: {len(errors)}")
    print(f"Correct classifications: {correct}/{len(classified)} ({correct/len(classified)*100:.0f}%)")

    hs_total = len(high_stakes_emails)
    print(f"\nLead safety (HARD CONSTRAINT):")
    print(f"  High-stakes emails: {hs_total}")
    print(f"  Correctly identified: {high_stakes_correct}/{hs_total}"
          f" ({high_stakes_correct/hs_total*100:.0f}%)"
          f" {'✓ PASS' if high_stakes_correct == hs_total else '✗ FAIL'}")

    should_esc = tp + fn
    print(f"\nEscalation accuracy (sandbox targets, n={should_esc} ambiguous):")
    print(f"  Should have escalated: {should_esc}")
    print(f"  Actually escalated: {tp}  (TP={tp}, FN={fn})")
    print(f"  Unnecessary escalations: {fp}  (FP={fp})")
    print(f"  Escalation recall: {recall:.2f} ({tp}/{should_esc}) -- target >= 0.83")
    print(f"  Escalation precision: {precision:.2f} ({tp}/{tp+fp}) -- target >= 0.50")
    print(f"  Advisor changed answer: {advisor_changed}/{escalated_count} escalations")

    print(f"\nCost:")
    print(f"  Total API calls: {total_calls}")
    print(f"  Total: ${total_cost:.4f}")
    if len(classified) > 0:
        print(f"  Per email: ${total_cost/len(classified):.6f}")
    advisor_cost = sum(
        r["advisor_input_tokens"] * OPUS_INPUT_COST / 1_000_000
        + r["advisor_output_tokens"] * OPUS_OUTPUT_COST / 1_000_000
        for r in classified
    )
    print(f"  Advisor overhead: ${advisor_cost:.4f}"
          f" ({advisor_cost/total_cost*100:.0f}% of total)" if total_cost > 0 else "")
    print()


# --- Sample emails ---


def load_sample_emails():
    """Return 20 labeled test emails for the classifier experiment."""
    return [
        # --- Clear high-stakes (1-7) ---
        {
            "id": "sample_01",
            "sender": "Mike Torres <mike@sunsetfilms.com>",
            "subject": "Composer needed for short film",
            "body": "Hi Alex, I'm directing a 15-minute short film shooting in October and I'm looking for a composer. Budget is $2,500 for the score. The film is a drama set in 1970s San Diego. Would you be interested? I can send the script.",
            "ground_truth": "gig_inquiry",
            "should_escalate": False,
        },
        {
            "id": "sample_02",
            "sender": "Lisa Park <lisa@parkproductions.tv>",
            "subject": "Music for our podcast intro",
            "body": "Hey Alex, we produce a tech podcast with 50K monthly listeners and need a custom intro/outro theme. 30 seconds each, modern electronic feel. What's your rate for something like this? We'd need it by end of month.",
            "ground_truth": "gig_inquiry",
            "should_escalate": False,
        },
        {
            "id": "sample_03",
            "sender": "David Kim <david@indiegamedev.co>",
            "subject": "Game soundtrack opportunity",
            "body": "Alex, I found your work through a colleague's recommendation. We're developing an indie RPG and need 45 minutes of original orchestral music. Development timeline is 8 months. Can we schedule a call to discuss scope and budget?",
            "ground_truth": "gig_inquiry",
            "should_escalate": False,
        },
        {
            "id": "sample_04",
            "sender": "Rachel Wong <rachel@sdtechweek.org>",
            "subject": "Workshop speaker invitation - AI in Music",
            "body": "Hi Alex, I'm organizing SD Tech Week 2026 and we'd love to have you lead a workshop on AI tools in music production. The event is June 15, honorarium is $500 plus travel. 90-minute session, 40 attendees expected. Interested?",
            "ground_truth": "business_opportunity",
            "should_escalate": False,
        },
        {
            "id": "sample_05",
            "sender": "James Okafor <james@amplifypartners.vc>",
            "subject": "Partnership discussion - AI music tools",
            "body": "Alex, I lead the creative tools practice at Amplify Partners. We've been following your work at the intersection of AI and music composition. Would love to explore potential consulting engagement. Are you available for a 30-minute intro call next week?",
            "ground_truth": "business_opportunity",
            "should_escalate": False,
        },
        {
            "id": "sample_06",
            "sender": "Carlos Mendez <carlos@sounddesigners.org>",
            "subject": "Connecting at AES Convention",
            "body": "Hi Alex, we met briefly at the AES convention in October. I really enjoyed your panel on generative music. I'm a sound designer at Ubisoft and would love to keep the conversation going. Coffee sometime?",
            "ground_truth": "genuine_networking",
            "should_escalate": False,
        },
        {
            "id": "sample_07",
            "sender": "Nina Patel <nina@berklee.edu>",
            "subject": "Alumni connect - composition program",
            "body": "Hey Alex, I'm a fellow Berklee alum (2018, film scoring). Just moved to San Diego and trying to build my local network. Saw your name come up in a few industry circles. Would love to grab lunch and swap notes on the local scene.",
            "ground_truth": "genuine_networking",
            "should_escalate": False,
        },
        # --- Clear low-priority (8-14) ---
        {
            "id": "sample_08",
            "sender": "Splice <newsletters@splice.com>",
            "subject": "New samples: Analog Synth Collection",
            "body": "This week on Splice: 500 new analog synth samples from our latest pack. Plus, hear how producer deadmau5 uses granular synthesis in his workflow. Browse the collection at splice.com/sounds.\n\nUnsubscribe | Update preferences",
            "ground_truth": "subscription",
            "should_escalate": False,
        },
        {
            "id": "sample_09",
            "sender": "Music Business Worldwide <digest@musicbusinessworldwide.com>",
            "subject": "Weekly digest: Streaming revenue hits new high",
            "body": "This week's top stories: Global streaming revenue surpasses $50B. Universal Music explores AI licensing framework. Sony acquires indie label catalog.\n\nYou're receiving this because you subscribed to MBW Weekly.\nUnsubscribe here.",
            "ground_truth": "subscription",
            "should_escalate": False,
        },
        {
            "id": "sample_10",
            "sender": "Film Score Monthly <news@filmscoremonthly.com>",
            "subject": "FSM Newsletter #412",
            "body": "In this issue: Interview with Hans Zimmer on his latest score. Review of the new John Williams box set. Upcoming film music concerts.\n\nManage subscription | Unsubscribe",
            "ground_truth": "subscription",
            "should_escalate": False,
        },
        {
            "id": "sample_11",
            "sender": "BandLab <promos@bandlab.com>",
            "subject": "🎵 50% off BandLab Pro - Limited time!",
            "body": "Upgrade to BandLab Pro and get unlimited cloud storage, advanced mastering, and premium sounds. Use code SPRING50 at checkout. Offer ends Friday!\n\nThis is a promotional email. Unsubscribe.",
            "ground_truth": "marketing",
            "should_escalate": False,
        },
        {
            "id": "sample_12",
            "sender": "iZotope <offers@izotope.com>",
            "subject": "Everything Bundle - Save $800 this week only",
            "body": "The Everything Bundle includes Ozone, RX, Neutron, and all our creative tools. Originally $2,499, now $1,699. This is our biggest sale of the year.\n\nUnsubscribe from promotional emails.",
            "ground_truth": "marketing",
            "should_escalate": False,
        },
        {
            "id": "sample_13",
            "sender": "GitHub <notifications@github.com>",
            "subject": "[sandbox] Issue #42: Fix test runner timeout",
            "body": "dependabot opened a new issue in alejandroguillen/sandbox:\n\nThe test runner is timing out on CI when running the full suite. Suggest increasing timeout from 120s to 300s.\n\nView issue: https://github.com/alejandroguillen/sandbox/issues/42",
            "ground_truth": "notification",
            "should_escalate": False,
        },
        {
            "id": "sample_14",
            "sender": "Railway <notifications@railway.app>",
            "subject": "Deploy succeeded: pf-intel-api",
            "body": "Your deployment to pf-intel-api completed successfully.\n\nCommit: fix(api): handle empty query params\nBranch: main\nDuration: 45s\n\nView deployment: https://railway.app/project/abc123",
            "ground_truth": "notification",
            "should_escalate": False,
        },
        # --- Ambiguous (15-20) ---
        {
            "id": "sample_15",
            "sender": "Sarah Chen <sarah@creativeagency.io>",
            "subject": "Hey Alex, quick question about your availability",
            "body": "Hey Alex,\n\nHope you're doing well! I came across your portfolio and was really impressed with your recent documentary work. We're putting together a creative project and I'd love to chat about potential collaboration.\n\nWould you have 15 minutes this week for a quick call?\n\nBest,\nSarah\n\n---\nCreative Agency | Connecting talent with opportunity\nUnsubscribe from this list",
            "ground_truth": "marketing",
            "should_escalate": True,
        },
        {
            "id": "sample_16",
            "sender": "Jordan Taylor <jordan@talentsync.com>",
            "subject": "Your profile caught my eye",
            "body": "Hi Alex,\n\nI'm Jordan, and I've been following your journey in AI-assisted composition. Really cool stuff. We help creative professionals find their next opportunity and I think you'd be a great fit for some projects we're sourcing.\n\nNo pressure - just wanted to reach out personally.\n\nJordan\n\nTalentSync | Unsubscribe",
            "ground_truth": "marketing",
            "should_escalate": True,
        },
        {
            "id": "sample_17",
            "sender": "Carlos Mendez <carlos@sounddesigners.org>",
            "subject": "Sound Design Guild - March roundup",
            "body": "Hey Alex,\n\nHere's what the guild has been up to this month:\n- New mentorship program launching (apply by April 15)\n- Member spotlight: Sarah Kim's work on the latest Pixar film\n- Upcoming webinar: Spatial audio for VR experiences\n\nHope to see you at the next meetup!\n\nCarlos\nSound Design Guild Newsletter | Unsubscribe",
            "ground_truth": "subscription",
            "should_escalate": True,
        },
        {
            "id": "sample_18",
            "sender": "Nina Patel <nina@berklee.edu>",
            "subject": "Berklee Alumni Monthly",
            "body": "Hi Alex,\n\nThis month's alumni spotlight features your classmate Dave Chen, who just scored his first Netflix series! Also: summer reunion details and a call for mentors in the new composition program.\n\nAs always, reply to this email if you want to be featured or have news to share.\n\nNina\nBerklee Alumni Relations | Unsubscribe",
            "ground_truth": "subscription",
            "should_escalate": True,
        },
        {
            "id": "sample_19",
            "sender": "Mark Sullivan <mark.sullivan@gmail.com>",
            "subject": "Music for my wedding?",
            "body": "Hey Alex,\n\nFound your info online. My fiancee and I are getting married in La Jolla in September and we're looking for someone to compose a custom piece for the ceremony. Nothing too long, maybe 3-4 minutes. Is this something you do?\n\nThanks,\nMark",
            "ground_truth": "gig_inquiry",
            "should_escalate": True,
        },
        {
            "id": "sample_20",
            "sender": "events@sdinnovate.org",
            "subject": "You're invited: SD Innovate Creator Mixer",
            "body": "Alex,\n\nYou've been selected to attend our exclusive Creator Mixer on April 22. Connect with 50 San Diego creatives, filmmakers, and tech founders over drinks and demos.\n\nRSVP by April 18. Space is limited to 50 attendees.\n\nSD Innovate | Unsubscribe",
            "ground_truth": "genuine_networking",
            "should_escalate": True,
        },
    ]


# --- Main ---


def main():
    verbose = "--verbose" in sys.argv

    print("Email Classifier — Advisor Strategy (Custom Tool Proxy)")
    print(f"Executor: {CONFIG.executor_model}")
    print(f"Advisor: {CONFIG.advisor_model}")
    print()

    emails = load_sample_emails()
    print(f"Classifying {len(emails)} emails...\n")

    # Clear previous results
    if RESULTS_FILE.exists():
        RESULTS_FILE.unlink()

    results = []
    for i, email in enumerate(emails, 1):
        label = f"[{i}/{len(emails)}] {email['id']}: {email['subject'][:40]}"
        print(f"{label}...", end=" ", flush=True)

        try:
            result = classify_email(email)
            log_result(result)
            results.append(result)

            status = "✓" if result["final_decision"] == email["ground_truth"] else "✗"
            esc = " [escalated]" if result["escalated"] else ""
            print(f"{status} {result['final_decision']}{esc} ({result['latency_ms']}ms)")

            if verbose and result["escalated"]:
                print(f"    Haiku preliminary: {result['haiku_preliminary']} "
                      f"(conf={result['haiku_confidence']})")
                print(f"    Advisor recommendation: {result['advisor_recommendation']}")
                print(f"    Advisor changed answer: {result['advisor_changed_answer']}")

        except Exception as e:
            error_result = {
                "email_id": email["id"],
                "error": str(e),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            log_result(error_result)
            results.append(error_result)
            print(f"ERROR: {e}")

    print_summary(results)


if __name__ == "__main__":
    main()
