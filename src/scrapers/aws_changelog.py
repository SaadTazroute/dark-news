"""AWSChangelogAgent — fetches and normalizes recent AWS changelog entries."""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import List

import feedparser

from src.models import SignalItem
from src.registry import ScraperAgent, register_scraper
from src.retry import with_retry

logger = logging.getLogger(__name__)

RSS_URL = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
LOOKBACK_HOURS = 48
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags and truncate to 500 chars."""
    return _TAG_RE.sub("", text or "")[:500].strip()


def _extract_service(title: str) -> str:
    """Extract service name from the entry title (text before '–', '-', or first word)."""
    for sep in ("–", "-"):
        if sep in title:
            return title.split(sep)[0].strip()
    return title.split()[0] if title else "AWS"


@register_scraper("aws_changelog")
class AWSChangelogAgent(ScraperAgent):
    """Scraper for AWS What's New RSS feed."""

    def source_type(self) -> str:
        return "aws_changelog"

    def scrape(self, config: dict) -> List[SignalItem]:
        hours = config.get("aws_changelog_lookback_hours", LOOKBACK_HOURS)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            entries = self._fetch_feed()
        except Exception as e:
            logger.error(f"AWSChangelogAgent failed to fetch feed: {e}")
            return []

        items = []
        for entry in entries:
            if not entry.get("published_parsed"):
                continue
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published < cutoff:
                continue
            items.append(self._normalize(entry, published))

        logger.info(f"AWSChangelogAgent scraped {len(items)} items")
        return items

    @with_retry(max_retries=3)
    def _fetch_feed(self) -> list:
        """Fetch and parse the AWS changelog RSS feed."""
        feed = feedparser.parse(RSS_URL)
        return feed.entries

    def _normalize(self, entry, published: datetime) -> SignalItem:
        """Normalize a feed entry into a SignalItem."""
        title = entry.get("title", "")
        return SignalItem(
            source_type="aws_changelog",
            title=title,
            summary=_strip_html(entry.get("summary", "")),
            url=entry.get("link", ""),
            timestamp=published,
            raw_metadata={
                "service_name": _extract_service(title),
                "entry_id": entry.get("id", ""),
            },
        )
