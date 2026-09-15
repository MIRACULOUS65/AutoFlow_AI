"""On-device tool-calling agent built on Cactus Needle 2.

Wraps the fine-tuned Needle 2 model (``my_agent.cact``, ~14 MB, bundled in this
package) behind a small, honest interface. The model turns a natural-language
instruction into one or more tool calls and executes them. It runs fully on the
CPU on-device (no cloud, no API key) and is OPT-IN: nothing here imports the
``needle`` runtime until :meth:`NeedleAgent.run` (or :func:`available`) is called,
so the base package + test suite stay unaffected when it is not used.

Honesty:
* If the ``needle`` runtime is not installed, methods raise a clear error /
  :func:`available` returns a reason — never a fake result.
* Default is safe (``execute=False``): tools return their structured action
  without touching the machine. Real Windows side effects require ``execute=True``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
BUNDLED_WEIGHTS = _PKG_DIR / "weights" / "my_agent.cact"

_SYSTEM = (
    "You are AutoFlow's on-device operator. Turn the user instruction into the "
    "correct tool call(s). Only call tools that match the intent; do not invent "
    "arguments you were not given."
)


def default_weights() -> str | None:
    """Resolve the weights path: env override, bundled fine-tuned, else base model."""

    env = os.environ.get("AUTOFLOW_NEEDLE_WEIGHTS")
    if env:
        return env
    if BUNDLED_WEIGHTS.exists():
        return str(BUNDLED_WEIGHTS)
    return None  # let Needle fetch the open base model from HF


def available() -> dict:
    """Report whether the on-device agent can run, without side effects."""

    try:
        import needle  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"needle runtime not installed: {type(exc).__name__}",
                "install": "uv pip install cactus-needle"}
    w = default_weights()
    return {
        "available": True,
        "weights": w or "base (fetched from HuggingFace)",
        "bundled_weights_present": BUNDLED_WEIGHTS.exists(),
    }


@dataclass
class NeedleResult:
    instruction: str
    success: bool
    executed: bool
    tool_calls: list = field(default_factory=list)
    results: list = field(default_factory=list)
    reasoning: str | None = None
    metrics: dict = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "instruction": self.instruction, "success": self.success,
            "executed": self.executed, "tool_calls": self.tool_calls,
            "results": self.results, "reasoning": self.reasoning,
            "metrics": self.metrics, "error": self.error,
        }


class NeedleAgent:
    """A thin, honest wrapper around ``needle.Needle`` with the AutoFlow tool set."""

    def __init__(self, *, execute: bool = False, weights: str | None = None,
                 output_dir: str | None = None) -> None:
        self.execute = execute
        self.weights = weights if weights is not None else default_weights()
        self.output_dir = output_dir
        self._agent = None  # lazy

    def _build(self):
        if self._agent is not None:
            return self._agent
        import warnings

        import needle

        from .tools import build_tools

        tools = build_tools(execute=self.execute, output_dir=self.output_dir)
        with warnings.catch_warnings():
            # the tuned-weights confidence-head warning is expected and benign
            warnings.simplefilter("ignore")
            self._agent = needle.Needle(tools=tools, system=_SYSTEM, weights=self.weights)
        return self._agent

    def run(self, instruction: str) -> NeedleResult:
        """Run one instruction: model selects + executes tool(s). Fails honestly."""

        try:
            agent = self._build()
        except ImportError as exc:
            return NeedleResult(instruction, success=False, executed=self.execute,
                                error=f"needle runtime not installed: {exc}")
        try:
            out = agent.run(instruction)
        except Exception as exc:  # noqa: BLE001
            return NeedleResult(instruction, success=False, executed=self.execute,
                                error=f"{type(exc).__name__}: {exc}")

        return NeedleResult(
            instruction=instruction,
            success=bool(out.get("success")),
            executed=self.execute,
            tool_calls=out.get("function_calls") or [],
            results=out.get("results") or [],
            reasoning=out.get("reasoning"),
            metrics={
                "prefill_tps": out.get("prefill_tps"),
                "decode_tps": out.get("decode_tps"),
                "peak_ram_mb": out.get("peak_ram_mb"),
                "confidence": out.get("confidence"),
            },
        )

    def close(self) -> None:
        if self._agent is not None:
            try:
                self._agent.close()
            except Exception:  # noqa: BLE001
                pass
            self._agent = None
