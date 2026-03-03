"""Structured JSON log formatter for CloudWatch Logs."""

import json
import logging
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """Formats log records as structured JSON with agent context fields."""

    def format(self, record):
        log_entry = {
            "level": record.levelname,
            "agent_name": getattr(record, "agent_name", "unknown"),
            "error_type": getattr(record, "error_type", ""),
            "error_message": record.getMessage(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if hasattr(record, "run_id"):
            log_entry["run_id"] = record.run_id
        if hasattr(record, "context"):
            log_entry["context"] = record.context
        return json.dumps(log_entry)


def format_error_log(agent_name: str, error_type: str, error_message: str) -> dict:
    """Build a structured error log dict with required fields.

    Args:
        agent_name: Name of the agent that encountered the error.
        error_type: Type/class of the error.
        error_message: Human-readable error description.

    Returns:
        Dict containing agent_name, error_type, error_message, and timestamp.
    """
    return {
        "agent_name": agent_name,
        "error_type": error_type,
        "error_message": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
