"""CloudWatch metrics builder — emits pipeline run metrics."""

import logging
from datetime import datetime, timezone

import boto3

from src.models import PipelineResult

logger = logging.getLogger(__name__)

NAMESPACE = "DarkWebAINewsletter"


def emit_metrics(result: PipelineResult, aws_region: str = "us-east-1") -> None:
    """Emit CloudWatch metrics from a PipelineResult.

    Metrics emitted:
    - PipelineDuration (seconds)
    - ItemsScraped per source (Count)
    - ItemsAfterFilter (Count)
    - DeliverySuccess / DeliveryFailure (Count)
    """
    cw = boto3.client("cloudwatch", region_name=aws_region)
    now = datetime.now(timezone.utc)

    metric_data = build_metric_data(result, now)

    # CloudWatch accepts max 20 metrics per call
    for i in range(0, len(metric_data), 20):
        try:
            cw.put_metric_data(Namespace=NAMESPACE, MetricData=metric_data[i:i + 20])
        except Exception as e:
            logger.error(f"Failed to emit CloudWatch metrics: {e}")


def build_metric_data(result: PipelineResult, timestamp: datetime) -> list:
    """Build CloudWatch metric data list from a PipelineResult."""
    duration = (result.end_time - result.start_time).total_seconds()

    metrics = [
        _metric("PipelineDuration", duration, "Seconds", timestamp),
        _metric("ItemsAfterFilter", result.items_after_filter, "Count", timestamp),
        _metric("ItemsInDigest", result.items_in_digest, "Count", timestamp),
    ]

    # Per-source items scraped
    for source, info in result.scraper_results.items():
        count = info.get("count", 0) if isinstance(info, dict) else 0
        metrics.append(_metric("ItemsScraped", count, "Count", timestamp, dimension=("Source", source)))

    # Delivery success/failure
    if result.publish_result:
        for channel_result in result.publish_result.channel_results:
            metric_name = "DeliverySuccess" if channel_result.success else "DeliveryFailure"
            metrics.append(_metric(metric_name, 1, "Count", timestamp, dimension=("Channel", channel_result.channel)))

    return metrics


def _metric(name: str, value: float, unit: str, timestamp: datetime, dimension: tuple = None) -> dict:
    """Build a single CloudWatch metric datum."""
    datum = {
        "MetricName": name,
        "Value": value,
        "Unit": unit,
        "Timestamp": timestamp,
    }
    if dimension:
        datum["Dimensions"] = [{"Name": dimension[0], "Value": dimension[1]}]
    return datum
