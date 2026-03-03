"""ArxivAgent — fetches and normalizes recent preprints from arxiv."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List

import arxiv

from src.models import SignalItem
from src.registry import ScraperAgent, register_scraper
from src.retry import with_retry

logger = logging.getLogger(__name__)

CATEGORIES = ["cs.AI", "cs.LG", "cs.CR"]
LOOKBACK_HOURS = 72


@register_scraper("arxiv")
class ArxivAgent(ScraperAgent):
    """Scraper for arxiv preprints in cs.AI, cs.LG, and cs.CR categories."""

    def source_type(self) -> str:
        return "arxiv"

    def scrape(self, config: dict) -> List[SignalItem]:
        categories = config.get("arxiv_categories", CATEGORIES)
        hours = config.get("arxiv_lookback_hours", LOOKBACK_HOURS)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        items = []
        for category in categories:
            try:
                raw = self._fetch_preprints(category, cutoff)
                for paper in raw:
                    item = self._normalize(paper)
                    if item:
                        items.append(item)
            except Exception as e:
                logger.error(f"ArxivAgent failed for category {category}: {e}")

        logger.info(f"ArxivAgent scraped {len(items)} items")
        return items

    @with_retry(max_retries=3)
    def _fetch_preprints(self, category: str, cutoff: datetime) -> list:
        """Fetch preprints for a single category submitted after cutoff."""
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=100,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        results = []
        for paper in arxiv.Client().results(search):
            published = paper.published
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published < cutoff:
                break
            results.append(paper)
        return results

    def _normalize(self, paper) -> SignalItem:
        """Normalize an arxiv paper into a SignalItem."""
        published = paper.published
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        return SignalItem(
            source_type="arxiv",
            title=paper.title,
            summary=paper.summary,
            url=paper.entry_id,
            timestamp=published,
            raw_metadata={
                "authors": [a.name for a in paper.authors],
                "categories": paper.categories,
                "arxiv_id": paper.get_short_id(),
            },
        )
