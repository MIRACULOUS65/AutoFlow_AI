"""Specialist agent runtime (Phase 6).

Agents PROPOSE structured actions; they never execute side effects directly.
The MultiAgentRuntime validates every proposal against the tool registry,
policy and permissions before the deterministic tool runtime performs it.
"""

from __future__ import annotations

from .errors import AgentError, UnsupportedCapability
from .models import (
    AgentActionProposal,
    AgentContext,
    AgentResult,
    AgentStatus,
)
from .base import SpecialistAgent
from .registry import AgentRegistry, build_default_registry

__all__ = [
    "AgentError",
    "UnsupportedCapability",
    "AgentActionProposal",
    "AgentContext",
    "AgentResult",
    "AgentStatus",
    "SpecialistAgent",
    "AgentRegistry",
    "build_default_registry",
]
