"""SlackPublisher — delivers the digest to a Slack channel via Block Kit."""

import json
import logging

import requests

from src.models import Digest
from src.registry import PublisherChannel, register_publisher
from src.retry import with_retry

logger = logging.getLogger(__name__)

SLACK_API_URL = "https://slack.com/api/chat.postMessage"


def build_blocks(digest: Digest) -> list:
    """Build Slack Block Kit blocks from a Digest."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🧠 48H Ahead — {digest.date}", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{digest.item_count} signals* from {len(digest.sources_summary)} sources"},
        },
        {"type": "divider"},
    ]

    # One section block per source group summary
    for source_type, count in digest.sources_summary.items():
        label = source_type.replace("_", " ").title()
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{label}* — {count} item{'s' if count != 1 else ''}"},
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": digest.plain_text[:2900]},  # Slack block text limit
    })

    return blocks


@register_publisher("slack")
class SlackPublisher(PublisherChannel):
    """Delivers the digest to a Slack channel using the Slack Web API."""

    def channel_name(self) -> str:
        return "slack"

    def deliver(self, digest: Digest, config: dict) -> bool:
        token = config.get("slack_token", "")
        channel = config.get("slack_channel", "#general")

        if not token:
            logger.error("SlackPublisher: slack_token not configured")
            return False

        try:
            return self._post(token, channel, digest)
        except Exception as e:
            logger.error(f"SlackPublisher: delivery failed: {e}")
            return False

    @with_retry(max_retries=3)
    def _post(self, token: str, channel: str, digest: Digest) -> bool:
        """Post the digest to Slack with Block Kit formatting."""
        blocks = build_blocks(digest)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "channel": channel,
            "blocks": blocks,
            "text": f"48H Ahead digest — {digest.date}",  # fallback text
        }
        response = requests.post(SLACK_API_URL, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise RuntimeError(f"Slack API error: {result.get('error', 'unknown')}")
        logger.info(f"SlackPublisher: posted to {channel}")
        return True
