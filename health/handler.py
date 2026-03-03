"""Lambda handler for the /health endpoint."""

import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

RUN_HISTORY_TABLE = os.environ.get("RUN_HISTORY_TABLE", "dark-web-newsletter-runs")
AWS_REGION = os.environ.get("APP_REGION", "us-east-1")


def handler(event, context):
    """Return the status of the last pipeline run."""
    try:
        last_run = _get_last_run()
        status_code = 200
        body = last_run if last_run else {"status": "no_runs", "message": "No pipeline runs recorded yet"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        status_code = 500
        body = {"status": "error", "message": str(e)}

    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _get_last_run() -> dict:
    """Query DynamoDB for the most recent pipeline run."""
    ddb = boto3.client("dynamodb", region_name=AWS_REGION)
    try:
        # Scan and sort by run_date descending to get the latest
        response = ddb.scan(
            TableName=RUN_HISTORY_TABLE,
            Limit=10,
            ProjectionExpression="run_date, run_id, #s, duration_seconds, items_scraped, items_published, #e",
            ExpressionAttributeNames={"#s": "status", "#e": "error"},
        )
        items = response.get("Items", [])
        if not items:
            return None

        # Sort by run_date descending, pick the latest
        items.sort(key=lambda x: x.get("run_date", {}).get("S", ""), reverse=True)
        latest = items[0]

        return {
            "status": latest.get("status", {}).get("S", "unknown"),
            "run_date": latest.get("run_date", {}).get("S", ""),
            "run_id": latest.get("run_id", {}).get("S", ""),
            "duration_seconds": float(latest.get("duration_seconds", {}).get("N", 0)),
            "items_scraped": int(latest.get("items_scraped", {}).get("N", 0)),
            "items_published": int(latest.get("items_published", {}).get("N", 0)),
            "error": latest.get("error", {}).get("S", None),
        }
    except ClientError as e:
        raise RuntimeError(f"DynamoDB query failed: {e}") from e
