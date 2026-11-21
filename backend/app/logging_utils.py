import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

_request_id = contextvars.ContextVar("request_id", default="unknown")
_logger = logging.getLogger("craftnest")
_logger.setLevel(logging.INFO)
_logger.propagate = False

if not _logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id or "unknown")


def log_event(level, event_type, details):
    """Emit one JSON object per line for CloudWatch Logs and Metric Filters."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": str(level).upper(),
        "event_type": event_type,
        "request_id": _request_id.get(),
        "details": details if isinstance(details, dict) else {"message": str(details)},
    }
    line = json.dumps(record, separators=(",", ":"), default=str)
    numeric_level = getattr(logging, str(level).upper(), logging.INFO)
    _logger.log(numeric_level, line)
