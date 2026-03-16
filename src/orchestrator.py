"""OrchestratorAgent — coordinates the full daily pipeline run."""

import json
import logging
import uuid
from datetime import datetime, timezone

import boto3

from src.config import load_config
from src.metrics import emit_metrics
from src.models import PipelineResult, PublishResult, ChannelResult
from src.registry import SCRAPER_REGISTRY, PUBLISHER_REGISTRY
from src.relevance_filter import RelevanceFilter
from src.summarizer import SummarizerAgent

# Import scrapers and publishers to trigger self-registration
import src.scrapers  # noqa: F401
import src.publishers  # noqa: F401

logger = logging.getLogger(__name__)

RUN_HISTORY_TABLE = "early-newsletter-runs"


class OrchestratorAgent:
    """Coordinates the daily scrape → filter → summarize → publish pipeline."""

    def run_pipeline(self, aws_region: str = "eu-west-1") -> PipelineResult:
        run_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        logger.info(f"Pipeline run {run_id} started")

        try:
            config = load_config(aws_region)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            end_time = datetime.now(timezone.utc)
            return PipelineResult(
                run_id=run_id, start_time=start_time, end_time=end_time,
                items_scraped=0, items_after_filter=0, items_in_digest=0,
                scraper_results={}, error=str(e),
            )

        # 1. Scrape
        all_items, scraper_results = self._run_scrapers(config)

        # 2. All scrapers failed — alert and abort
        if not all_items:
            logger.error("All scrapers failed — no items to process")
            self._alert_slack(config, "⚠️ All scrapers failed. No digest generated.")
            end_time = datetime.now(timezone.utc)
            result = PipelineResult(
                run_id=run_id, start_time=start_time, end_time=end_time,
                items_scraped=0, items_after_filter=0, items_in_digest=0,
                scraper_results=scraper_results, error="All scrapers failed",
            )
            self._record_run(result, config)
            return result

        # 3. Filter and rank
        try:
            rf = RelevanceFilter(config)
            filtered = rf.filter_and_rank(
                all_items,
                similarity_threshold=config.get("similarity_threshold", 0.85),
                max_items=config.get("max_items", 30),
            )
        except Exception as e:
            logger.error(f"RelevanceFilter failed: {e}")
            end_time = datetime.now(timezone.utc)
            result = PipelineResult(
                run_id=run_id, start_time=start_time, end_time=end_time,
                items_scraped=len(all_items), items_after_filter=0, items_in_digest=0,
                scraper_results=scraper_results, error=str(e),
            )
            self._record_run(result, config)
            return result

        # 4. Summarize
        try:
            digest = SummarizerAgent().summarize(filtered, config)
        except Exception as e:
            logger.error(f"SummarizerAgent failed: {e}")
            end_time = datetime.now(timezone.utc)
            result = PipelineResult(
                run_id=run_id, start_time=start_time, end_time=end_time,
                items_scraped=len(all_items), items_after_filter=len(filtered), items_in_digest=0,
                scraper_results=scraper_results, error=str(e),
            )
            self._record_run(result, config)
            return result

        # 5. Publish
        publish_result = self._publish(digest, config)

        end_time = datetime.now(timezone.utc)
        result = PipelineResult(
            run_id=run_id, start_time=start_time, end_time=end_time,
            items_scraped=len(all_items), items_after_filter=len(filtered),
            items_in_digest=digest.item_count,
            scraper_results=scraper_results, publish_result=publish_result,
        )

        # 6. Record metrics and run history
        try:
            emit_metrics(result, aws_region)
        except Exception as e:
            logger.warning(f"Failed to emit metrics: {e}")

        self._record_run(result, config)
        logger.info(f"Pipeline run {run_id} complete — {digest.item_count} items published")
        return result

    def _run_scrapers(self, config: dict) -> tuple:
        """Run all registered scrapers, skip failures. Returns (items, scraper_results)."""
        all_items = []
        scraper_results = {}
        enabled = config.get("enabled_sources", list(SCRAPER_REGISTRY.keys()))

        for source_type, scraper_cls in SCRAPER_REGISTRY.items():
            if source_type not in enabled:
                continue
            try:
                items = scraper_cls().scrape(config)
                all_items.extend(items)
                scraper_results[source_type] = {"success": True, "count": len(items)}
                logger.info(f"Scraper {source_type}: {len(items)} items")
            except Exception as e:
                logger.error(f"Scraper {source_type} failed: {e}")
                scraper_results[source_type] = {"success": False, "count": 0, "error": str(e)}

        return all_items, scraper_results

    def _publish(self, digest, config: dict) -> PublishResult:
        """Deliver digest to all registered publisher channels."""
        channel_results = []
        for channel_name, publisher_cls in PUBLISHER_REGISTRY.items():
            try:
                success = publisher_cls().deliver(digest, config)
                channel_results.append(ChannelResult(channel=channel_name, success=success))
            except Exception as e:
                logger.error(f"Publisher {channel_name} failed: {e}")
                channel_results.append(ChannelResult(channel=channel_name, success=False, error=str(e)))
        return PublishResult(channel_results=channel_results)

    def _alert_slack(self, config: dict, message: str) -> None:
        """Send a plain alert to Slack (best-effort, no retry)."""
        token = config.get("slack_token", "")
        channel = config.get("slack_channel", "#general")
        if not token:
            return
        try:
            import requests
            requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"channel": channel, "text": message},
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Alert to Slack failed: {e}")

    def _record_run(self, result: PipelineResult, config: dict) -> None:
        """Write run history to DynamoDB (best-effort)."""
        aws_region = config.get("aws_region", "eu-west-1")
        try:
            ddb = boto3.client("dynamodb", region_name=aws_region)
            duration = (result.end_time - result.start_time).total_seconds()
            status = "failed" if result.error else ("success" if result.publish_result and result.publish_result.all_success else "partial")
            item = {
                "run_date": {"S": result.start_time.date().isoformat()},
                "run_id": {"S": result.run_id},
                "status": {"S": status},
                "duration_seconds": {"N": str(duration)},
                "items_scraped": {"N": str(result.items_scraped)},
                "items_published": {"N": str(result.items_in_digest)},
                "scraper_results": {"S": json.dumps(result.scraper_results)},
            }
            if result.error:
                item["error"] = {"S": result.error}
            ddb.put_item(TableName=RUN_HISTORY_TABLE, Item=item)
        except Exception as e:
            logger.warning(f"Failed to record run history: {e}")
