"""GitHubSignalAgent — fetches and normalizes recent commits from key AI repositories."""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import List

import requests

from src.models import SignalItem
from src.registry import ScraperAgent, register_scraper

logger = logging.getLogger(__name__)

LOOKBACK_HOURS = 48

DEFAULT_REPOS = [
    "aws/amazon-bedrock-samples",
    "anthropics/anthropic-sdk-python",
    "openai/openai-python",
    "huggingface/transformers",
    "vllm-project/vllm",
]

# Prefixes and substrings that mark a commit as trivial
_TRIVIAL_PREFIXES = ("bump", "chore", "ci:", "docs:", "style:", "test:", "merge")
_TRIVIAL_SUBSTRINGS = ("dependency", "dependabot", "typo", "whitespace", "formatting")

GITHUB_API = "https://api.github.com"


def is_trivial(commit_msg: str) -> bool:
    """Return True if the commit message represents a trivial change.

    Trivial commits include dependency bumps, typo fixes, CI config changes,
    merge commits, and pure style/formatting/docs/test changes.
    """
    lower = commit_msg.strip().lower()
    first_line = lower.splitlines()[0] if lower else ""

    for prefix in _TRIVIAL_PREFIXES:
        if first_line.startswith(prefix):
            return True

    for substring in _TRIVIAL_SUBSTRINGS:
        if substring in lower:
            return True

    return False


@register_scraper("github")
class GitHubSignalAgent(ScraperAgent):
    """Scraper for significant commits on key AI/ML repositories."""

    def source_type(self) -> str:
        return "github"

    def scrape(self, config: dict) -> List[SignalItem]:
        token = config.get("github_token")
        repos = config.get("github_repos", DEFAULT_REPOS)
        hours = config.get("github_lookback_hours", LOOKBACK_HOURS)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        items = []
        for repo in repos:
            try:
                commits = self._fetch_commits(repo, cutoff, headers)
                for commit in commits:
                    msg = commit.get("commit", {}).get("message", "")
                    if is_trivial(msg):
                        continue
                    item = self._normalize(repo, commit)
                    if item:
                        items.append(item)
            except Exception as e:
                logger.error(f"GitHubSignalAgent failed for repo {repo}: {e}")

        logger.info(f"GitHubSignalAgent scraped {len(items)} significant commits")
        return items

    def _fetch_commits(self, repo: str, cutoff: datetime, headers: dict) -> list:
        """Fetch commits for a repo since cutoff, respecting rate limits."""
        since = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{GITHUB_API}/repos/{repo}/commits"
        params = {"since": since, "per_page": 100}

        commits = []
        while url:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            self._handle_rate_limit(response)
            response.raise_for_status()

            page = response.json()
            commits.extend(page)

            # Follow pagination via Link header
            url = self._next_page_url(response.headers.get("Link", ""))
            params = {}  # params are encoded in the next URL

        return commits

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Pause if the GitHub rate limit is exhausted."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) == 0:
            reset_ts = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
            sleep_secs = max(reset_ts - int(time.time()), 1)
            logger.warning(f"GitHub rate limit reached, sleeping {sleep_secs}s until reset")
            time.sleep(sleep_secs)

    def _next_page_url(self, link_header: str) -> str:
        """Parse the 'next' URL from a GitHub Link header, or return empty string."""
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                # Format: <https://...>; rel="next"
                url_part = part.split(";")[0].strip()
                return url_part.strip("<>")
        return ""

    def _normalize(self, repo: str, commit: dict) -> SignalItem:
        """Normalize a GitHub commit API response into a SignalItem."""
        commit_data = commit.get("commit", {})
        message = commit_data.get("message", "").strip()
        first_line = message.splitlines()[0] if message else ""

        author_info = commit_data.get("author", {})
        author = author_info.get("name", "unknown")

        date_str = author_info.get("date", "")
        try:
            timestamp = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now(timezone.utc)

        sha = commit.get("sha", "")
        short_sha = sha[:7] if sha else ""
        html_url = commit.get("html_url", f"https://github.com/{repo}/commit/{sha}")

        return SignalItem(
            source_type="github",
            title=f"{repo}: {first_line}",
            summary=message,
            url=html_url,
            timestamp=timestamp,
            raw_metadata={
                "repo": repo,
                "author": author,
                "sha": short_sha,
            },
        )
