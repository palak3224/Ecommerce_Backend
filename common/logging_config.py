"""
Central logging setup for the Flask app (Tier 1 — structured, no new dependencies).

Environment:
  LOG_LEVEL   DEBUG, INFO, WARNING, ERROR (default: INFO)
  LOG_FORMAT  text | json  (default: text; json = one JSON object per line)
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """One JSON object per log line for log aggregators."""

    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _parse_level(name: str) -> int:
    return getattr(logging, name.upper(), logging.INFO)


def configure_app_logging(app) -> None:
    """Attach a single stream handler with consistent formatting; idempotent per app instance."""
    level = _parse_level(os.getenv("LOG_LEVEL", "INFO"))
    use_json = os.getenv("LOG_FORMAT", "text").strip().lower() == "json"

    app.logger.setLevel(level)
    for h in list(app.logger.handlers):
        app.logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    if use_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    app.logger.addHandler(handler)
    app.logger.propagate = False
