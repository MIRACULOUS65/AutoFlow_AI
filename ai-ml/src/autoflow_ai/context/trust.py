"""Trust model for context.

Trust classes are explicit and ordered. The model must never confuse DATA with
INSTRUCTION: only high-trust sources (SYSTEM, and trusted application/user
state) may act as instructions. Retrieved knowledge, tool output and external
content are DATA — even if their text says "ignore previous instructions".
"""

from __future__ import annotations

from ..schemas.enums import StrEnum


class TrustLevel(StrEnum):
    """Ordered trust classes (highest to lowest authority)."""

    SYSTEM = "system"
    TRUSTED_APPLICATION_STATE = "trusted_application_state"
    AUTHORIZED_USER_INPUT = "authorized_user_input"
    AUTHORIZED_MEMORY = "authorized_memory"
    AUTHORIZED_KNOWLEDGE = "authorized_knowledge"
    TOOL_OUTPUT = "tool_output"
    EXTERNAL_CONTENT = "external_content"
    UNTRUSTED_CONTENT = "untrusted_content"


# Higher number = more authority. Used for ranking tie-breaks and to decide
# whether an item may be treated as an instruction.
TRUST_ORDER: dict[TrustLevel, int] = {
    TrustLevel.SYSTEM: 100,
    TrustLevel.TRUSTED_APPLICATION_STATE: 80,
    TrustLevel.AUTHORIZED_USER_INPUT: 70,
    TrustLevel.AUTHORIZED_MEMORY: 60,
    TrustLevel.AUTHORIZED_KNOWLEDGE: 50,
    TrustLevel.TOOL_OUTPUT: 30,
    TrustLevel.EXTERNAL_CONTENT: 20,
    TrustLevel.UNTRUSTED_CONTENT: 10,
}

# Only these trust levels may be rendered as authoritative instructions.
_INSTRUCTION_TRUST = frozenset(
    {
        TrustLevel.SYSTEM,
        TrustLevel.AUTHORIZED_USER_INPUT,
        TrustLevel.TRUSTED_APPLICATION_STATE,
    }
)

# Everything at or below this authority must be clearly framed as data.
DATA_TRUST = frozenset(
    {
        TrustLevel.AUTHORIZED_MEMORY,
        TrustLevel.AUTHORIZED_KNOWLEDGE,
        TrustLevel.TOOL_OUTPUT,
        TrustLevel.EXTERNAL_CONTENT,
        TrustLevel.UNTRUSTED_CONTENT,
    }
)


def is_trusted_instruction_source(level: TrustLevel) -> bool:
    """Whether content at ``level`` may act as an instruction (not just data)."""

    return level in _INSTRUCTION_TRUST
