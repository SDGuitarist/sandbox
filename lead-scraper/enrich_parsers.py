"""Pure functions for extracting contact info from HTML pages. No I/O."""

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)

# Social handle patterns -- keyword-prefix required, no bare @handle matching.
_SOCIAL_PATTERNS = [
    ("instagram", re.compile(
        r"\b(?:IG|instagram|insta)[:\s|]+@?([a-zA-Z0-9_.]{3,30})\b", re.IGNORECASE
    )),
    ("twitter", re.compile(
        r"(?:twitter\.com|x\.com)[/]*@?([a-zA-Z0-9_]{1,15})", re.IGNORECASE
    )),
    ("linkedin", re.compile(
        r"linkedin\.com/(in/[a-zA-Z0-9\-]+)", re.IGNORECASE
    )),
    ("tiktok", re.compile(
        r"(?:tiktok|tik\s*tok)[:\s|]*@?([a-zA-Z0-9_.]{2,24})", re.IGNORECASE
    )),
    ("youtube", re.compile(
        r"(?:youtube\.com|youtu\.be)/(?:@|channel/|c/)([a-zA-Z0-9_\-]+)",
        re.IGNORECASE,
    )),
]

_IMAGE_SUFFIXES = (".png", ".jpg", ".gif", ".svg", ".webp")


@dataclass
class ParsedContactInfo:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_handles: list[str] = field(default_factory=list)


def parse_profile_page(html: str) -> ParsedContactInfo:
    """Extract emails and phones from HTML. Pure function, no I/O."""
    info = ParsedContactInfo()
    soup = BeautifulSoup(html, "lxml")

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        # mailto: links
        if href.lower().startswith("mailto:"):
            raw = href[7:].split("?")[0].strip().lower()
            if EMAIL_RE.fullmatch(raw):
                info.emails.append(raw)

        # tel: links
        elif href.lower().startswith("tel:"):
            raw = href[4:].strip()
            digits = re.sub(r"[^\d+]", "", raw)
            if 7 <= len(digits) <= 16:
                info.phones.append(digits)

    # Fallback: regex scan visible text for emails not in mailto: links
    for text_node in soup.find_all(string=True):
        if text_node.parent.name in ("script", "style", "noscript"):
            continue
        for match in EMAIL_RE.finditer(str(text_node)):
            candidate = match.group().lower()
            if not candidate.endswith(_IMAGE_SUFFIXES):
                if candidate not in info.emails:
                    info.emails.append(candidate)

    return info


def parse_bio(text: str) -> ParsedContactInfo:
    """Extract emails, phones, and social handles from bio text. Pure function."""
    info = ParsedContactInfo()
    if not text:
        return info

    text = text[:10_000]  # Cap input length to prevent ReDoS on crafted bios

    # Emails
    for match in EMAIL_RE.finditer(text):
        candidate = match.group().lower()
        if not candidate.endswith(_IMAGE_SUFFIXES):
            if candidate not in info.emails:
                info.emails.append(candidate)

    # Phones
    for match in PHONE_RE.finditer(text):
        digits = re.sub(r"[^\d]", "", match.group())
        if digits not in info.phones:
            info.phones.append(digits)

    # Social handles (keyword-prefix required)
    for platform, pattern in _SOCIAL_PATTERNS:
        for match in pattern.finditer(text):
            handle = match.group(1).strip().rstrip(".")
            if not handle:
                continue
            entry = f"{platform}:{handle}"
            if entry not in info.social_handles:
                info.social_handles.append(entry)

    return info
