"""Fetch new public fraud alerts on a schedule (the "cron job" side of continuous learning).

Code, not the model, fetches from a fixed allowlist: the FBI Internet Crime
Complaint Center (IC3) public service announcements RSS feed and the PSA pages
it links to. IC3 PSAs are U.S. Government works (public domain), so their text
may be stored in full. Fetched text is untrusted data like any advisory: the
agent still has no network tools, and quotes are verified against the stored
text. Requests are bounded (timeout, size, item count) and only fraud-related
alerts are kept.
"""

from __future__ import annotations

import html
import re
import ssl
import threading
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

import certifi

from pydantic import BaseModel

from app.intel.advisories import MAX_ADVISORY_CHARS, Advisory
from app.storage import DocumentBackend

FETCHED = "fetched_advisories"
FEED_STATE = "feed_state"
IC3_FEED = "https://www.ic3.gov/PSA/RSS"
IC3_PAGE_PREFIX = "https://www.ic3.gov/PSA/"
MAX_BYTES = 600_000
TIMEOUT_SECONDS = 15
MAX_NEW_PER_REFRESH = 5
MIN_TEXT_CHARS = 200
USER_AGENT = "RulePilot-AI/1.0 (fraud-rule research prototype)"
# Kept only if the title or text mentions a financial-fraud technique.
FRAUD_TERMS = re.compile(
    r"\b(fraud|scam|scammer|card|account takeover|sim swap|payment|bank|wire|money|crypto|"
    r"cryptocurrency|investment|impersonat\w*|phishing|identity theft|extortion|romance)\b",
    re.IGNORECASE,
)

Fetcher = Callable[[str], bytes]


class FeedItem(BaseModel):
    guid: str
    title: str
    link: str
    published: str | None


class RefreshResult(BaseModel):
    checked_at: datetime
    feed_items: int
    new_advisories: list[str]
    skipped_not_fraud: list[str]
    errors: list[str]


def http_fetch(url: str) -> bytes:
    """GET an allowlisted IC3 URL with a timeout and a size cap."""
    if not (url == IC3_FEED or url.startswith(IC3_PAGE_PREFIX)):
        raise ValueError(f"URL not on the allowlist: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # certifi's CA bundle: some Python builds ship without system certificates. Verification stays on.
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:  # noqa: S310 (allowlisted https)
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError(f"response from {url} is larger than {MAX_BYTES} bytes")
    return body


def parse_feed(xml_bytes: bytes) -> list[FeedItem]:
    root = ET.fromstring(xml_bytes)
    items = []
    for node in root.iter("item"):
        link = (node.findtext("link") or "").strip()
        guid = (node.findtext("guid") or link).strip()
        title = html.unescape((node.findtext("title") or "").strip())
        if not link.startswith(IC3_PAGE_PREFIX) or not title:
            continue
        published = None
        if node.findtext("pubDate"):
            try:
                published = parsedate_to_datetime(node.findtext("pubDate")).date().isoformat()
            except (TypeError, ValueError):
                published = None
        items.append(FeedItem(guid=guid, title=title[:200], link=link, published=published))
    return items


def page_text(html_bytes: bytes) -> str:
    """Readable text of a PSA page's <main> element (scripts, navigation, and markup removed)."""
    source = html_bytes.decode("utf-8", errors="replace")
    match = re.search(r"<main.*?</main>", source, re.S | re.I) or re.search(r"<body.*?</body>", source, re.S | re.I)
    if not match:
        return ""
    text = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", match.group(0), flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()[:MAX_ADVISORY_CHARS]


def advisory_id_for(item: FeedItem) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", item.guid.lower()).strip("-")[:50] or "item"
    return f"ic3-{slug}"


class FeedStore:
    """Fetched advisories and the last refresh result, kept with the governance backend."""

    def __init__(self, backend: DocumentBackend) -> None:
        self.backend = backend
        self._lock = threading.Lock()

    def advisories(self) -> dict[str, Advisory]:
        found = {}
        for document in self.backend.all(FETCHED):
            try:
                advisory = Advisory.model_validate_json(document["payload"])
            except (KeyError, ValueError):
                continue
            found[advisory.advisory_id] = advisory
        return dict(sorted(found.items(), key=lambda kv: kv[1].published_date or "", reverse=True))

    def last_refresh(self) -> RefreshResult | None:
        document = self.backend.get(FEED_STATE, "ic3")
        return RefreshResult.model_validate_json(document["payload"]) if document else None

    def refresh(self, fetch: Fetcher = http_fetch) -> RefreshResult:
        """Fetch the IC3 feed and store up to MAX_NEW_PER_REFRESH new fraud-related PSAs."""
        with self._lock:
            known = set(self.advisories())
            new, skipped, errors = [], [], []
            items: list[FeedItem] = []
            try:
                items = parse_feed(fetch(IC3_FEED))
            except Exception as error:  # network, XML, or size errors are reported, never raised
                errors.append(f"feed: {type(error).__name__}: {error}"[:300])
            for item in items:
                advisory_id = advisory_id_for(item)
                if advisory_id in known or len(new) >= MAX_NEW_PER_REFRESH:
                    continue
                try:
                    text = page_text(fetch(item.link))
                except Exception as error:
                    errors.append(f"{item.link}: {type(error).__name__}: {error}"[:300])
                    continue
                if len(text) < MIN_TEXT_CHARS or not FRAUD_TERMS.search(f"{item.title} {text}"):
                    skipped.append(item.title)
                    continue
                advisory = Advisory(
                    advisory_id=advisory_id,
                    title=item.title,
                    publisher="FBI Internet Crime Complaint Center (IC3)",
                    source_url=item.link,
                    published_date=item.published,
                    retrieved_at=date.today().isoformat(),
                    source_type="government_psa",
                    rights_note="U.S. Government public service announcement (public domain); fetched automatically by the scheduled job.",
                    excerpt=text,
                )
                self.backend.put(FETCHED, advisory_id, {"payload": advisory.model_dump_json()})
                new.append(advisory_id)
            result = RefreshResult(
                checked_at=datetime.now(timezone.utc), feed_items=len(items),
                new_advisories=new, skipped_not_fraud=skipped, errors=errors,
            )
            self.backend.put(FEED_STATE, "ic3", {"payload": result.model_dump_json()})
            return result


_stores: dict[int, FeedStore] = {}


def feed_store(backend: DocumentBackend) -> FeedStore:
    if id(backend) not in _stores:
        _stores[id(backend)] = FeedStore(backend)
    return _stores[id(backend)]
