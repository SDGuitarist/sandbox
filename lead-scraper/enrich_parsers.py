"""Pure functions for extracting contact info from HTML pages. No I/O."""

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup, SoupStrainer

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "tiktok.com": "tiktok",
}

# Skip generic share/intent URLs
_SHARE_PATTERNS = ("/sharer", "/intent/", "/share", "/dialog/", "/hashtag/")


@dataclass
class ParsedContactInfo:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_urls: dict[str, str] = field(default_factory=dict)


def parse_profile_page(html: str) -> ParsedContactInfo:
    """Extract contact info from HTML. Pure function, no I/O."""
    info = ParsedContactInfo()

    # Parse only <a> and <script> tags for efficiency
    link_strainer = SoupStrainer("a")
    soup = BeautifulSoup(html, "lxml", parse_only=link_strainer)

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

        # Social media links
        else:
            try:
                parsed = urlparse(href)
                domain = (parsed.netloc or "").lower().removeprefix("www.")
            except Exception:
                continue

            path = parsed.path.lower()
            if any(p in path for p in _SHARE_PATTERNS):
                continue

            for social_domain, platform in SOCIAL_DOMAINS.items():
                if domain.endswith(social_domain) and platform not in info.social_urls:
                    info.social_urls[platform] = href
                    break

    # Fallback: regex scan visible text for emails not in mailto: links
    full_soup = BeautifulSoup(html, "lxml")
    for text_node in full_soup.find_all(string=True):
        if text_node.parent.name in ("script", "style", "noscript"):
            continue
        for match in EMAIL_RE.finditer(str(text_node)):
            candidate = match.group().lower()
            # Skip image filenames that look like emails
            if not candidate.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
                if candidate not in info.emails:
                    info.emails.append(candidate)

    # Schema.org JSON-LD sameAs (for social links)
    if '"@type"' in html:
        script_strainer = SoupStrainer("script", type="application/ld+json")
        script_soup = BeautifulSoup(html, "lxml", parse_only=script_strainer)
        for script in script_soup.find_all("script"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            items = data.get("@graph", [data]) if isinstance(data, dict) else data
            for item in items:
                if not isinstance(item, dict):
                    continue
                same_as = item.get("sameAs", [])
                if isinstance(same_as, str):
                    same_as = [same_as]
                for url in same_as:
                    if not isinstance(url, str):
                        continue
                    try:
                        domain = urlparse(url).netloc.lower().removeprefix("www.")
                    except Exception:
                        continue
                    for social_domain, platform in SOCIAL_DOMAINS.items():
                        if domain.endswith(social_domain) and platform not in info.social_urls:
                            info.social_urls[platform] = url
                            break

    return info
