"""Core data models for the Dark Web AI Newsletter pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


REQUIRED_SIGNAL_FIELDS = ("source_type", "title", "summary", "url", "timestamp")


@dataclass
class SignalItem:
    """A normalized data record representing a single piece of intelligence."""

    source_type: str  # "arxiv" | "github" | "huggingface" | "reddit" | "aws_changelog"
    title: str
    summary: str
    url: str
    timestamp: datetime
    raw_metadata: dict = field(default_factory=dict)
    relevance_score: Optional[float] = None
    embedding: Optional[list] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage/transport."""
        return {
            "source_type": self.source_type,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "timestamp": self.timestamp.isoformat(),
            "raw_metadata": self.raw_metadata,
            "relevance_score": self.relevance_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SignalItem":
        """Deserialize from dictionary."""
        return cls(
            source_type=data["source_type"],
            title=data["title"],
            summary=data["summary"],
            url=data["url"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            raw_metadata=data.get("raw_metadata", {}),
            relevance_score=data.get("relevance_score"),
        )


@dataclass
class Digest:
    """The final formatted output for a given day."""

    date: str  # ISO date string
    plain_text: str  # Plain-text version for Slack
    html: str  # HTML version for email
    item_count: int
    sources_summary: dict  # {"arxiv": 5, "github": 3, ...}


@dataclass
class ChannelResult:
    """Result of delivering a digest to a single channel."""

    channel: str  # "slack", "email", etc.
    success: bool
    error: Optional[str] = None


@dataclass
class PublishResult:
    """Aggregated result of delivering a digest to all channels."""

    channel_results: List[ChannelResult]

    @property
    def all_success(self) -> bool:
        return all(r.success for r in self.channel_results)

    def get(self, channel: str) -> Optional[ChannelResult]:
        return next((r for r in self.channel_results if r.channel == channel), None)


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""

    run_id: str
    start_time: datetime
    end_time: datetime
    items_scraped: int
    items_after_filter: int
    items_in_digest: int
    scraper_results: dict  # {"arxiv": {"success": True, "count": 5}, ...}
    publish_result: Optional[PublishResult] = None
    error: Optional[str] = None


def validate_signal_item(data: dict) -> bool:
    """Validate that a dict has all required Signal_Item fields and they are non-empty.

    Returns True if all required fields are present and non-empty, False otherwise.
    """
    for field_name in REQUIRED_SIGNAL_FIELDS:
        value = data.get(field_name)
        if value is None or value == "":
            return False
    return True
