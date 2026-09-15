"""Runtime component registry.

Resolves the configured mode (mock/real) into concrete implementations of each
external interface. This is the single place where mock -> real is flipped; no
API, service, or database code changes when the real implementations arrive.
"""

from __future__ import annotations

from functools import lru_cache

from app.agents.interfaces import AgentRuntime
from app.agents.mock_agent_runtime import MockAgentRuntime
from app.core.config import settings
from app.intelligence.interfaces import IntelligenceRuntime
from app.orchestration.interfaces import Orchestrator
from app.orchestration.mock_orchestrator import MockOrchestrator
from app.policy.interfaces import PolicyEngine
from app.policy.mock_policy_engine import MockPolicyEngine
from app.recovery.interfaces import RecoveryManager
from app.recovery.mock_recovery_manager import MockRecoveryManager
from app.tools.interfaces import ToolRuntime
from app.tools.mock_tool_runtime import MockToolRuntime
from app.verification.interfaces import Verifier
from app.verification.mock_verifier import MockVerifier


@lru_cache
def get_orchestrator() -> Orchestrator:
    if settings.orchestrator_mode == "real":
        raise NotImplementedError("Real orchestrator not wired yet.")
    return MockOrchestrator()


@lru_cache
def get_agent_runtime() -> AgentRuntime:
    if settings.agent_runtime_mode == "real":
        raise NotImplementedError("Real agent runtime not wired yet.")
    return MockAgentRuntime()


@lru_cache
def get_tool_runtime() -> ToolRuntime:
    if settings.tool_runtime_mode == "real":
        raise NotImplementedError("Real tool runtime not wired yet.")
    return MockToolRuntime()


@lru_cache
def get_verifier() -> Verifier:
    if settings.verifier_mode == "real":
        raise NotImplementedError("Real verifier not wired yet.")
    return MockVerifier()


@lru_cache
def get_recovery_manager() -> RecoveryManager:
    if settings.recovery_mode == "real":
        raise NotImplementedError("Real recovery manager not wired yet.")
    return MockRecoveryManager()


@lru_cache
def get_policy_engine() -> PolicyEngine:
    if settings.policy_mode == "real":
        raise NotImplementedError("Real policy engine not wired yet.")
    return MockPolicyEngine()


@lru_cache
def get_intelligence_runtime() -> IntelligenceRuntime:
    """The coarse mission-level intelligence seam.

    Returns the real AI/ML runtime (out-of-process, HTTP) when integration is
    enabled, otherwise the built-in mock. This is the single flip point for the
    mock -> real intelligence convergence.
    """
    if settings.use_real_intelligence:
        from app.intelligence.ai_ml_runtime import RealAiMlRuntime

        return RealAiMlRuntime()
    from app.intelligence.mock_runtime import MockIntelligenceRuntime

    return MockIntelligenceRuntime()
