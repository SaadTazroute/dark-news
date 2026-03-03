"""
Local pipeline smoke test — runs each scraper independently, then the full pipeline.
No AWS credentials needed for scrapers. Bedrock required for full pipeline.

Usage:
    source .venv/bin/activate
    python tests/test_local_pipeline.py
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from src.scrapers.arxiv import ArxivAgent
from src.scrapers.aws_changelog import AWSChangelogAgent
from src.scrapers.github_signal import GitHubSignalAgent
from src.scrapers.huggingface import HuggingFaceAgent
from src.scrapers.reddit import RedditAgent

SCRAPERS = [ArxivAgent, AWSChangelogAgent, GitHubSignalAgent, HuggingFaceAgent, RedditAgent]


def test_scrapers():
    print("\n=== Scraper smoke test ===")
    config = {}
    total = 0
    for cls in SCRAPERS:
        items = cls().scrape(config)
        status = "✓" if len(items) >= 0 else "✗"
        print(f"  {status} {cls.__name__}: {len(items)} items")
        total += len(items)
    print(f"\n  Total: {total} items scraped")
    return total


def test_full_pipeline():
    print("\n=== Full pipeline test (requires Bedrock access) ===")
    try:
        from src.config import load_config
        from src.orchestrator import OrchestratorAgent

        config = load_config()
        result = OrchestratorAgent().run_pipeline(aws_region=config.get("aws_region", "us-east-1"))

        print(f"  run_id:           {result.run_id}")
        print(f"  items_scraped:    {result.items_scraped}")
        print(f"  items_filtered:   {result.items_after_filter}")
        print(f"  items_in_digest:  {result.items_in_digest}")
        print(f"  error:            {result.error or 'none'}")

        if result.publish_result:
            for ch in result.publish_result.channel_results:
                icon = "✓" if ch.success else "✗"
                print(f"  {icon} publisher [{ch.channel}]: {'ok' if ch.success else ch.error}")

        return result.error is None
    except Exception as e:
        print(f"  ✗ Pipeline failed: {e}")
        return False


if __name__ == "__main__":
    scraper_total = test_scrapers()

    run_full = "--full" in sys.argv
    if run_full:
        ok = test_full_pipeline()
        sys.exit(0 if ok else 1)
    else:
        print("\nTip: run with --full to also test Bedrock summarization + publishing")
        sys.exit(0 if scraper_total > 0 else 1)
