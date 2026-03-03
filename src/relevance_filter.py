"""Relevance filtering: Bedrock embeddings, deduplication, and ranking."""

import json
import math
import logging
from typing import List

import boto3

from src.models import SignalItem

logger = logging.getLogger(__name__)

# Source type weights for relevance scoring when no score is pre-assigned
SOURCE_WEIGHTS = {
    "arxiv": 1.0,
    "github": 0.9,
    "huggingface": 0.8,
    "reddit": 0.7,
    "aws_changelog": 0.85,
}


def _cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class RelevanceFilter:
    """Deduplicates and ranks SignalItems using Bedrock Titan Embeddings."""

    def __init__(self, config: dict = None):
        config = config or {}
        region = config.get("aws_region", "us-east-1")
        self._bedrock = boto3.client("bedrock-runtime", region_name=region)

    def compute_embeddings(self, items: List[SignalItem]) -> List[list]:
        """Call Bedrock Titan Embeddings for each SignalItem.

        Uses title + summary as the input text. Raises on API failure so the
        orchestrator can handle it (Requirement 7.4).
        """
        embeddings = []
        for item in items:
            text = f"{item.title}. {item.summary}"
            response = self._bedrock.invoke_model(
                modelId="amazon.titan-embed-text-v1",
                body=json.dumps({"inputText": text}),
                contentType="application/json",
                accept="application/json",
            )
            embedding = json.loads(response["body"].read())["embedding"]
            item.embedding = embedding
            embeddings.append(embedding)
        return embeddings

    def deduplicate(
        self, items: List[SignalItem], embeddings: List[list], threshold: float
    ) -> List[SignalItem]:
        """Remove near-duplicate items using cosine similarity.

        Iterates items in order (highest relevance_score first if pre-sorted).
        Keeps the first item in each near-duplicate group; discards any subsequent
        item whose similarity to an already-kept item is >= threshold.
        """
        kept: List[SignalItem] = []
        kept_embeddings: List[list] = []

        for item, emb in zip(items, embeddings):
            is_duplicate = any(
                _cosine_similarity(emb, kept_emb) >= threshold
                for kept_emb in kept_embeddings
            )
            if not is_duplicate:
                kept.append(item)
                kept_embeddings.append(emb)

        return kept

    def rank(self, items: List[SignalItem]) -> List[SignalItem]:
        """Assign relevance scores (if missing) and sort descending by score."""
        for item in items:
            if item.relevance_score is None:
                item.relevance_score = SOURCE_WEIGHTS.get(item.source_type, 0.5)
        return sorted(items, key=lambda i: i.relevance_score, reverse=True)

    def filter_and_rank(
        self,
        items: List[SignalItem],
        similarity_threshold: float = 0.85,
        max_items: int = 30,
    ) -> List[SignalItem]:
        """Full pipeline: embed → dedup → rank → cap.

        1. Assign relevance scores so dedup starts with highest-value items first.
        2. Compute Bedrock embeddings (raises on failure — Requirement 7.4).
        3. Deduplicate by cosine similarity.
        4. Re-rank and cap at max_items.
        """
        if not items:
            return []

        # Score first so we can sort before dedup (keeps best item per cluster)
        for item in items:
            if item.relevance_score is None:
                item.relevance_score = SOURCE_WEIGHTS.get(item.source_type, 0.5)
        pre_sorted = sorted(items, key=lambda i: i.relevance_score, reverse=True)

        embeddings = self.compute_embeddings(pre_sorted)
        unique = self.deduplicate(pre_sorted, embeddings, similarity_threshold)
        ranked = self.rank(unique)
        return ranked[:max_items]
