"""Shared retry decorator with exponential backoff and jitter."""

import time
import random
import logging

logger = logging.getLogger(__name__)


def with_retry(max_retries=3, base_wait=1, max_wait=30):
    """Decorator that retries a function with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retry attempts.
        base_wait: Base wait time in seconds.
        max_wait: Maximum wait time in seconds.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    wait = min(base_wait * (2 ** attempt) + random.random(), max_wait)
                    logger.warning(f"{func.__name__} attempt {attempt+1} failed, retrying in {wait:.1f}s: {e}")
                    time.sleep(wait)
        return wrapper
    return decorator
