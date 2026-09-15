"""Agent society: real sub-agent collaboration on top of the Phase 1-7 substrate.

This package adds the *agent society* that the base multi-agent runtime lacked:
a message protocol + bus, a shared trust-classed blackboard with context
isolation, per-agent internal observe->decide->act->verify loops, an independent
critic that can REJECT work, and a MissionSupervisor that dynamically delegates,
reassigns, and only declares completion after independent verification.

It never bypasses the existing authority chain: agents PROPOSE, the
ToolCallingController executes, and the VerificationEngine decides success.
"""

from __future__ import annotations

from .messages import AgentMessage, MessageType, MessageBus
from .blackboard import Blackboard, BlackboardEntry, TrustClass, HandoffContext
from .roles import AGENT_ROLES, AgentRole, DecisionSummary
from .agent import CollaborativeAgent, AgentPhase
from .critic import CriticAgent, CriticVerdict
from .supervisor import MissionSupervisor, MissionReport, MissionLimits
from .autonomous import (
    AutonomousComputerAgent,
    GoalSpec,
    AutonomousResult,
    LoopOutcome,
)
from .metrics import (
    AgenticityMetrics,
    AgentScore,
    compute_metrics,
    AgenticityVerdict,
    evaluate_agenticity,
)
from .grounding import MissionGrounding, GroundingResult, GroundingStatus
from .evidence_broker import (
    EvidenceBroker,
    EvidenceBundle,
    EvidenceItem,
    EvidenceSource,
    validate_search_relevance,
    reformulate_query,
    relevance_score,
)
from .persistence import MissionStore, MissionState, MissionCheckpoint
from .reasoning import ReasoningPolicy, ReasoningSpecialist, ModelDecision
from .websearch import (
    AutonomousWebSearchAgent,
    WebSearchResult,
    SearchOutcome,
    SEARCH_ENGINES,
)
from .research import (
    WebResearchAgent,
    ResearchReport,
    ResearchFact,
    ResearchOutcome,
    EpistemicLabel,
)
from .gmail_workflow import (
    GmailComposeWorkflow,
    EmailSpec,
    GmailResult,
    GmailOutcome,
)
from .flagship import FlagshipWorkflow, FlagshipResult, FlagshipOutcome
from .simulation import (
    MissionTracer,
    TraceStage,
    SimulationResult,
    simulate_mission,
    compare_sim_vs_live,
)

__all__ = [
    "AgentMessage",
    "MessageType",
    "MessageBus",
    "Blackboard",
    "BlackboardEntry",
    "TrustClass",
    "HandoffContext",
    "AGENT_ROLES",
    "AgentRole",
    "DecisionSummary",
    "CollaborativeAgent",
    "AgentPhase",
    "CriticAgent",
    "CriticVerdict",
    "MissionSupervisor",
    "MissionReport",
    "MissionLimits",
    "AutonomousComputerAgent",
    "GoalSpec",
    "AutonomousResult",
    "LoopOutcome",
    "AgenticityMetrics",
    "AgentScore",
    "compute_metrics",
    "AgenticityVerdict",
    "evaluate_agenticity",
    "MissionGrounding",
    "GroundingResult",
    "GroundingStatus",
    "MissionStore",
    "MissionState",
    "MissionCheckpoint",
    "EvidenceBroker",
    "EvidenceBundle",
    "EvidenceItem",
    "EvidenceSource",
    "validate_search_relevance",
    "reformulate_query",
    "relevance_score",
    "ReasoningPolicy",
    "ReasoningSpecialist",
    "ModelDecision",
    "AutonomousWebSearchAgent",
    "WebSearchResult",
    "SearchOutcome",
    "SEARCH_ENGINES",
    "WebResearchAgent",
    "ResearchReport",
    "ResearchFact",
    "ResearchOutcome",
    "EpistemicLabel",
    "GmailComposeWorkflow",
    "EmailSpec",
    "GmailResult",
    "GmailOutcome",
    "FlagshipWorkflow",
    "FlagshipResult",
    "FlagshipOutcome",
    "MissionTracer",
    "TraceStage",
    "SimulationResult",
    "simulate_mission",
    "compare_sim_vs_live",
]
