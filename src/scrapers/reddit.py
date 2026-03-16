"""RedditAgent — fetches recent posts from subreddits via public JSON API (no auth required)."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List

import requests

from src.models import SignalItem
from src.registry import ScraperAgent, register_scraper
from src.retry import with_retry

logger = logging.getLogger(__name__)

DEFAULT_SUBREDDITS = ["MachineLearning", "LocalLLaMA", "aws"]
LOOKBACK_HOURS = 48
DEFAULT_VELOCITY_THRESHOLD = 1.0  # comments per hour
FETCH_LIMIT = 100

HEADERS = {"User-Agent": "early-ai-newsletter/1.0 (no-auth public API)"}


def compute_velocity(created_utc: float, num_comments: int) -> float:
    """Compute comment velocity in comments per hour since post creation."""
    age_hours = max(
        (datetime.now(timezone.utc) - datetime.fromtimestamp(created_utc, tz=timezone.utc)).total_seconds() / 3600,
        0.1,
    )
    return num_comments / age_hours


@register_scraper("reddit")
class RedditAgent(ScraperAgent):
    """Scraper for Reddit posts via public JSON API — no credentials required."""

    def source_type(self) -> str:
        return "reddit"

    def scrape(self, config: dict) -> List[SignalItem]:
        subreddits = config.get("reddit_subreddits", DEFAULT_SUBREDDITS)
        velocity_threshold = config.get("reddit_velocity_threshold", DEFAULT_VELOCITY_THRESHOLD)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

        all_posts = []
        for subreddit_name in subreddits:
            try:
                posts = self._fetch_posts(subreddit_name, cutoff)
                all_posts.extend(posts)
            except Exception as e:
                logger.error(f"RedditAgent failed for r/{subreddit_name}: {e}")

        filtered = [
            (post, compute_velocity(post["created_utc"], post["num_comments"]))
            for post in all_posts
            if compute_velocity(post["created_utc"], post["num_comments"]) >= velocity_threshold
        ]
        filtered.sort(key=lambda x: x[1], reverse=True)

        items = [self._normalize(post, velocity) for post, velocity in filtered]
        logger.info(f"RedditAgent scraped {len(items)} items above velocity threshold {velocity_threshold}")
        return items

    @with_retry(max_retries=3)
    def _fetch_posts(self, subreddit_name: str, cutoff: datetime) -> list:
        """Fetch new posts from a subreddit using the public .json endpoint."""
        url = f"https://www.reddit.com/r/{subreddit_name}/new.json"
        params = {"limit": FETCH_LIMIT}
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()

        posts = []
        for child in response.json().get("data", {}).get("children", []):
            post = child.get("data", {})
            created = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc)
            if created < cutoff:
                break
            posts.append(post)
        return posts

    def _normalize(self, post: dict, velocity: float) -> SignalItem:
        """Normalize a Reddit post dict into a SignalItem."""
        created = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc)
        selftext = post.get("selftext", "")
        summary = selftext[:500] if selftext else post.get("url", "")
        permalink = f"https://www.reddit.com{post.get('permalink', '')}"

        return SignalItem(
            source_type="reddit",
            title=post.get("title", ""),
            summary=summary,
            url=permalink,
            timestamp=created,
            raw_metadata={
                "subreddit": post.get("subreddit", ""),
                "comment_count": post.get("num_comments", 0),
                "velocity_score": round(velocity, 4),
                "post_id": post.get("id", ""),
            },
        )
