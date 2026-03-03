"""Scraper agents — one per source, self-registering via registry."""

from src.scrapers import arxiv  # noqa: F401
from src.scrapers import github_signal  # noqa: F401
from src.scrapers import huggingface  # noqa: F401
from src.scrapers import reddit  # noqa: F401
from src.scrapers import aws_changelog  # noqa: F401
