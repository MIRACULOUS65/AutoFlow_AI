"""Agent error types."""

from __future__ import annotations


class AgentError(Exception):
    """Base class for agent errors."""


class UnsupportedCapability(AgentError):
    """The agent cannot perform the requested capability yet (honest stub)."""
