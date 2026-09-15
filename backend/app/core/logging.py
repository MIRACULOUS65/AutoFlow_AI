"""Structured logging.

Uses structlog to emit key/value logs carrying correlation ids. Never log
secrets or hidden chain-of-thought — only operational metadata.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings

_SENSITIVE_KEYS = {
    "authorization",
    "password",
    "token",
    "api_key",
    "secret",
    "private_key",
    "reasoning",
    "chain_of_thought",
}


def _redact(_logger, _method, event_dict):
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact,
    ]
    if settings.is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "autoflow") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
