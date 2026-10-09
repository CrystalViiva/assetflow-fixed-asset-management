"""Structured log records, without exception payloads or request bodies."""

import json
import logging
import re


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Exception messages can contain raw provider responses, passwords or SQL values.
        message = "Operation failed" if record.exc_info else record.getMessage()
        message = re.sub(
            r"(?i)(postgres(?:ql)?://|redis://|smtp://)[^\s]+", "[REDACTED_URL]", message
        )
        message = re.sub(
            r"(?i)(bearer\s+|password[=:]\s*|token[=:]\s*)[^\s]+", r"\1[REDACTED]", message
        )
        result = {
            "level": record.levelname,
            "time": self.formatTime(record),
            "request_id": getattr(record, "request_id", "-"),
            "logger": record.name,
            "message": message,
        }
        if record.exc_info:
            result["error_type"] = record.exc_info[0].__name__
        return json.dumps(result)
