"""Pure functions for extracting contact info from HTML pages. No I/O."""

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


@dataclass
class ParsedContactInfo:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)


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
            if not candidate.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
                if candidate not in info.emails:
                    info.emails.append(candidate)

    return info
