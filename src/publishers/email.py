"""EmailPublisher — delivers the digest via Amazon SES."""

import logging

import boto3

from src.models import Digest
from src.registry import PublisherChannel, register_publisher
from src.retry import with_retry

logger = logging.getLogger(__name__)


@register_publisher("email")
class EmailPublisher(PublisherChannel):
    """Delivers the HTML digest via Amazon SES."""

    def channel_name(self) -> str:
        return "email"

    def deliver(self, digest: Digest, config: dict) -> bool:
        sender = config.get("email_sender", "")
        recipient = config.get("email_recipient", "")
        aws_region = config.get("aws_region", "us-east-1")

        if not sender or not recipient:
            logger.error("EmailPublisher: email_sender or email_recipient not configured")
            return False

        try:
            return self._send(sender, recipient, digest, aws_region)
        except Exception as e:
            logger.error(f"EmailPublisher: delivery failed: {e}")
            return False

    @with_retry(max_retries=3)
    def _send(self, sender: str, recipient: str, digest: Digest, aws_region: str) -> bool:
        """Send the digest via SES."""
        ses = boto3.client("ses", region_name=aws_region)
        subject = f"48H Ahead of the Curve — {digest.date}"

        ses.send_email(
            Source=sender,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": digest.plain_text, "Charset": "UTF-8"},
                    "Html": {"Data": digest.html, "Charset": "UTF-8"},
                },
            },
        )
        logger.info(f"EmailPublisher: sent to {recipient}")
        return True
