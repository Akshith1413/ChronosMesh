"""
ChronosMesh Structured JSON Logger.

Outputs production logs in structured JSON format with distributed trace context,
event IDs, cloud region, service names, and execution latency.
Automatically masks credentials, tokens, and passwords.
"""

import json
import logging
import sys
import time
from typing import Any, Dict, Optional


SENSITIVE_KEYS = {"password", "secret", "token", "jwt", "authorization", "key", "access_token"}


def mask_sensitive(data: Any) -> Any:
    """Recursively mask sensitive values in dicts/lists."""
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                masked[k] = "[REDACTED]"
            else:
                masked[k] = mask_sensitive(v)
        return masked
    elif isinstance(data, list):
        return [mask_sensitive(item) for item in data]
    return data


class StructuredJsonFormatter(logging.Formatter):
    """Custom logging formatter that renders records as compact JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom contextual attributes if present
        for attr in ("service", "trace_id", "event_id", "event_type", "region", "processing_time_ms", "status_code"):
            if hasattr(record, attr):
                log_obj[attr] = getattr(record, attr)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(mask_sensitive(log_obj))


def setup_structured_logging(level: int = logging.INFO):
    """Configure root logger to use JSON formatting."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = StructuredJsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Remove existing handlers to prevent duplicate lines
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
