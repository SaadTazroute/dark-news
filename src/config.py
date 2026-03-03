"""Configuration loading — Secrets Manager for credentials, DynamoDB for settings."""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Secrets Manager secret name (set via env var or default)
SECRET_NAME = os.environ.get("NEWSLETTER_SECRET_NAME", "dark-web-newsletter/credentials")
CONFIG_TABLE = os.environ.get("NEWSLETTER_CONFIG_TABLE", "dark-web-newsletter-config")


def _load_secrets(aws_region: str) -> dict:
    """Load sensitive credentials from Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=aws_region)
    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
        return json.loads(response["SecretString"])
    except ClientError as e:
        logger.error(f"Failed to load secrets from Secrets Manager: {e}")
        raise


def _load_dynamo_config(aws_region: str) -> dict:
    """Load non-sensitive config from DynamoDB config table."""
    client = boto3.client("dynamodb", region_name=aws_region)
    config = {}
    try:
        response = client.scan(TableName=CONFIG_TABLE)
        for item in response.get("Items", []):
            key = item["config_key"]["S"]
            # config_value can be a string (S) or a JSON map (S containing JSON)
            raw = item.get("config_value", {})
            if "S" in raw:
                try:
                    config[key] = json.loads(raw["S"])
                except (json.JSONDecodeError, TypeError):
                    config[key] = raw["S"]
    except ClientError as e:
        logger.warning(f"Failed to load config from DynamoDB (using defaults): {e}")
    return config


def load_config(aws_region: str = "us-east-1") -> dict:
    """Load and merge all configuration for a pipeline run.

    Secrets Manager credentials take precedence over DynamoDB config.
    Returns a single merged dict ready for use by all agents.
    """
    config = {"aws_region": aws_region}

    # Non-sensitive config from DynamoDB (best-effort — failures use defaults)
    dynamo_config = _load_dynamo_config(aws_region)
    config.update(dynamo_config)

    # Sensitive credentials from Secrets Manager (required — raises on failure)
    secrets = _load_secrets(aws_region)
    config.update(secrets)

    return config
