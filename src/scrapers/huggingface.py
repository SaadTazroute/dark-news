"""HuggingFaceAgent — fetches and normalizes recent model uploads from HuggingFace Hub."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from huggingface_hub import list_models

from src.models import SignalItem
from src.registry import ScraperAgent, register_scraper
from src.retry import with_retry

logger = logging.getLogger(__name__)

LOOKBACK_HOURS = 48
FETCH_LIMIT = 100


@register_scraper("huggingface")
class HuggingFaceAgent(ScraperAgent):
    """Scraper for new model uploads on HuggingFace Hub within the last 48 hours."""

    def source_type(self) -> str:
        return "huggingface"

    def scrape(self, config: dict) -> List[SignalItem]:
        token: Optional[str] = config.get("huggingface_token")
        hours = config.get("huggingface_lookback_hours", LOOKBACK_HOURS)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            models = self._fetch_models(token)
        except Exception as e:
            logger.error(f"HuggingFaceAgent failed to fetch models: {e}")
            return []

        items = []
        for model in models:
            created_at = model.created_at
            if created_at is None:
                continue
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at < cutoff:
                break  # Results are sorted by createdAt descending, so we can stop early
            item = self._normalize(model, created_at)
            if item:
                items.append(item)

        logger.info(f"HuggingFaceAgent scraped {len(items)} items")
        return items

    @with_retry(max_retries=3)
    def _fetch_models(self, token: Optional[str]) -> list:
        """Fetch recent models from HuggingFace Hub sorted by creation date descending."""
        kwargs = {"sort": "createdAt", "direction": -1, "limit": FETCH_LIMIT}
        if token:
            kwargs["token"] = token
        return list(list_models(**kwargs))

    def _normalize(self, model, created_at: datetime) -> Optional[SignalItem]:
        """Normalize a HuggingFace ModelInfo into a SignalItem."""
        model_id = model.id or ""
        if not model_id:
            return None

        pipeline_tag = model.pipeline_tag or ""
        url = f"https://huggingface.co/{model_id}"

        # Extract model size from safetensors info if available
        model_size: Optional[int] = None
        if hasattr(model, "safetensors") and model.safetensors:
            model_size = getattr(model.safetensors, "total", None)

        return SignalItem(
            source_type="huggingface",
            title=model_id,
            summary=pipeline_tag if pipeline_tag else "New model upload",
            url=url,
            timestamp=created_at,
            raw_metadata={
                "model_id": model_id,
                "author": model.author or "",
                "pipeline_tag": pipeline_tag,
                "model_size": model_size,
            },
        )
