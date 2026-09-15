"""On-device Needle 2 tool-calling agent tests.

Hermetic where possible; the model-loading tests skip cleanly when the needle
runtime is not installed (opt-in dependency). A real-execution test is gated by
AUTOFLOW_NEEDLE_LIVE=1 so CI without the runtime stays green.
"""

from __future__ import annotations

import importlib.util

import pytest

from autoflow_ai.needle_agent import BUNDLED_WEIGHTS, available, default_weights
from autoflow_ai.needle_agent.tools import build_tools

_HAS_NEEDLE = importlib.util.find_spec("needle") is not None
needs_needle = pytest.mark.skipif(not _HAS_NEEDLE, reason="cactus-needle not installed (opt-in)")


# -- availability + packaging (no runtime needed) ---------------------------

def test_ne_01_bundled_weights_present():
    # the fine-tuned ~14MB weights ship with the package
    assert BUNDLED_WEIGHTS.name == "my_agent.cact"
    assert BUNDLED_WEIGHTS.exists()
    assert BUNDLED_WEIGHTS.stat().st_size > 10_000_000  # ~13.7MB


def test_ne_02_default_weights_prefers_bundled(monkeypatch):
    monkeypatch.delenv("AUTOFLOW_NEEDLE_WEIGHTS", raising=False)
    assert default_weights() == str(BUNDLED_WEIGHTS)


def test_ne_03_env_override_weights(monkeypatch):
    monkeypatch.setenv("AUTOFLOW_NEEDLE_WEIGHTS", "/custom/path.cact")
    assert default_weights() == "/custom/path.cact"


def test_ne_04_available_reports_status():
    a = available()
    assert "available" in a
    if not _HAS_NEEDLE:
        assert a["available"] is False and "reason" in a


# -- tool set (needs the needle.tool decorator) -----------------------------

@needs_needle
def test_ne_05_builds_26_tools():
    tools = build_tools(execute=False)
    # 26 named in the manifest + open_file/open_folder wired
    # + search_kaggle_datasets + write_notepad.
    assert len(tools) == 30


@needs_needle
def test_ne_06_dry_run_tools_have_no_side_effects(tmp_path):
    # In safe mode create_note returns a planned action WITHOUT writing a file.
    tools = {t.__name__: t for t in build_tools(execute=False, output_dir=str(tmp_path))}
    res = tools["create_note"]("hello world")
    assert res["executed"] is False
    assert res["status"] == "planned"
    assert not list(tmp_path.iterdir())  # nothing written


@needs_needle
def test_ne_07_execute_note_writes_real_file(tmp_path):
    tools = {t.__name__: t for t in build_tools(execute=True, output_dir=str(tmp_path))}
    res = tools["create_note"]("buy milk")
    assert res["executed"] is True
    note = tmp_path / "note.txt"
    assert note.exists()
    assert "buy milk" in note.read_text(encoding="utf-8")


# -- real on-device model run (gated) ---------------------------------------

@pytest.mark.skipif(not _HAS_NEEDLE, reason="cactus-needle not installed")
@pytest.mark.skipif(
    __import__("os").environ.get("AUTOFLOW_NEEDLE_LIVE") != "1",
    reason="on-device model run disabled (set AUTOFLOW_NEEDLE_LIVE=1 to run)",
)
def test_ne_08_live_model_selects_and_executes(tmp_path):
    from autoflow_ai.needle_agent import NeedleAgent

    agent = NeedleAgent(execute=True, output_dir=str(tmp_path))
    try:
        result = agent.run("make a note that says buy milk and eggs")
    finally:
        agent.close()
    assert result.success is True
    # the model selected a tool and it executed on-device with a real result
    assert result.results, "model produced no tool result"
    executed = [r for r in result.results if isinstance(r, dict) and r.get("executed")]
    assert executed, f"no tool executed a real action: {result.results}"
    # the real side effect landed on disk within the confined output dir
    note = tmp_path / "note.txt"
    assert note.exists()
    assert "buy milk and eggs" in note.read_text(encoding="utf-8")
