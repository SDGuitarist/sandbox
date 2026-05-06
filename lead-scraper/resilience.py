"""Resilience helpers for the enrichment pipeline.

Exports:
    parse_retry_after() -- safely parse Retry-After headers with a cap
    YELLOW, RED, GREEN, RESET -- ANSI color constants (empty when piped)
"""

import sys


# ---------------------------------------------------------------------------
# Retry-After header parsing (security hardened)
# ---------------------------------------------------------------------------

MAX_RETRY_WAIT: int = 120


def parse_retry_after(header_value: str | None, fallback: float = 10.0) -> float:
    """Parse Retry-After header with a 120s safety cap.

    Handles integer seconds. Returns fallback on missing, non-integer,
    or negative values. Caps at 120s to prevent hangs from misconfigured
    servers (e.g. Retry-After: 999999 would sleep 11 days).
    """
    if header_value is None:
        return fallback
    try:
        wait = int(header_value)
    except (ValueError, TypeError):
        return fallback
    return float(min(max(0, wait), MAX_RETRY_WAIT))


# ---------------------------------------------------------------------------
# ANSI color constants -- empty strings when stdout is not a terminal
# ---------------------------------------------------------------------------

_IS_TTY = sys.stdout.isatty()

YELLOW = "\033[33m" if _IS_TTY else ""
RED = "\033[31m" if _IS_TTY else ""
GREEN = "\033[32m" if _IS_TTY else ""
RESET = "\033[0m" if _IS_TTY else ""
