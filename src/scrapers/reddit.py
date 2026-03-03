"""RedditAgent — fetches and normalizes recent posts from configured subreddits."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List

import praw
import praw.exceptions

from src.models import SignalItem
from src.registry import ScraperAgent, register_scraper
from src.retry import with_retry

logger = logging.getLogger(__name__)

DEFAULT_SUBREDDITS = ["MachineLearning", "LocalLLaMA", "aws"]
LOOKBACK_HOURS = 48
DEFAULT_VELOCITY_THRESHOLD = 1.0  # comments per hour
FETCH_LIMIT = 100


def compute_velocity(post) -> float:
    """Compute comment velocity in comments per hour since post creation."""
    age_hours = max(
        (datetime.now(timezone.utc) - datetime.fromtimestamp(post.created_utc, tz=timezone.utc)).total_seconds() / 3600,
        0.1,
    )
    return post.num_comments / age_hours


@register_scraper("reddit")
class RedditAgent(ScraperAgent):
    """Scraper for Reddit posts filtered by comment velocity."""

    def source_type(self) -> str:
        return "reddit"

    def scrape(self, config: dict) -> List[SignalItem]:
        subreddits = config.get("reddit_subreddits", DEFAULT_SUBREDDITS)
        velocity_threshold = config.get("reddit_velocity_threshold", DEFAULT_VELOCITY_THRESHOLD)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

        reddit = praw.Reddit(
            client_id=config.get("reddit_client_id", ""),
            client_secret=config.get("reddit_client_secret", ""),
            user_agent=config.get("reddit_user_agent", "dark-web-ai-newsletter/1.0"),
            read_only=True,
        )

        all_posts = []
        for subreddit_name in subreddits:
            try:
                posts = self._fetch_posts(reddit, subreddit_name, cutoff)
                all_posts.extend(posts)
            except praw.exceptions.PRAWException as e:
                logger.error(f"RedditAgent auth/API error for r/{subreddit_name}: {e}")
                return []
            except Exception as e:
                logger.error(f"RedditAgent failed for r/{subreddit_name}: {e}")

        # Filter by velocity threshold, then sort descending
        filtered = [
            (post, compute_velocity(post))
            for post in all_posts
            if compute_velocity(post) >= velocity_threshold
        ]
        filtered.sort(key=lambda x: x[1], reverse=True)

        items = [self._normalize(post, velocity) for post, velocity in filtered]
        logger.info(f"RedditAgent scraped {len(items)} items above velocity threshold {velocity_threshold}")
        return items

    @with_retry(max_retries=3)
    def _fetch_posts(self, reddit: praw.Reddit, subreddit_name: str, cutoff: datetime) -> list:
        """Fetch new posts from a subreddit published after cutoff."""
        subreddit = reddit.subreddit(subreddit_name)
        posts = []
        for post in subreddit.new(limit=FETCH_LIMIT):
            created = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
            if created < cutoff:
                break
            posts.append(post)
        return posts

    def _normalize(self, post, velocity: float) -> SignalItem:
        """Normalize a PRAW submission into a SignalItem."""
        created = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        summary = post.selftext[:500] if post.selftext else post.url
        permalink = f"https://www.reddit.com{post.permalink}"

        return SignalItem(
            source_type="reddit",
            title=post.title,
            summary=summary,
            url=permalink,
            timestamp=created,
            raw_metadata={
                "subreddit": post.subreddit.display_name,
                "comment_count": post.num_comments,
                "velocity_score": round(velocity, 4),
                "post_id": post.id,
            },
        )
