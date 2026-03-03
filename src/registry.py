"""Scraper and publisher registries with self-registration decorators."""

from abc import ABC, abstractmethod
from typing import List

from src.models import SignalItem, Digest

SCRAPER_REGISTRY: dict[str, type] = {}
PUBLISHER_REGISTRY: dict[str, type] = {}


class ScraperAgent(ABC):
    """Interface for all scraper agents."""

    @abstractmethod
    def scrape(self, config: dict) -> List[SignalItem]:
        """Fetch and normalize items from the source. Returns empty list on failure."""
        pass

    @abstractmethod
    def source_type(self) -> str:
        """Return the source type identifier (e.g., 'arxiv', 'github')."""
        pass


class PublisherChannel(ABC):
    """Interface for all publisher channels."""

    @abstractmethod
    def deliver(self, digest: Digest, config: dict) -> bool:
        """Deliver digest to this channel. Returns True on success."""
        pass

    @abstractmethod
    def channel_name(self) -> str:
        """Return the channel identifier (e.g., 'slack', 'email')."""
        pass


def register_scraper(source_type: str):
    """Decorator to register a scraper agent in the global registry."""
    def decorator(cls):
        SCRAPER_REGISTRY[source_type] = cls
        return cls
    return decorator


def register_publisher(channel_name: str):
    """Decorator to register a publisher channel in the global registry."""
    def decorator(cls):
        PUBLISHER_REGISTRY[channel_name] = cls
        return cls
    return decorator
