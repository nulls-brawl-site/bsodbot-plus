"""Tests for executable task plan tool."""

from __future__ import annotations

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.context import RequestContext
from nanobot.agent.tools.plan import UpdatePlanTool
from nanobot.bus.queue import MessageBus
from nanobot.session.manager import SessionManager
from nanobot.session.plan_state import PLAN_MODE_KEY, PLAN_STATE_KEY, plan_state_runtime_lines


def _tool(sm: SessionManager) -> UpdatePlanTool:
    tool = UpdatePlanTool(sm)
    tool.set_context(RequestContext(channel="cli", chat_id="direct", session_key="cli:direct"))
    return tool


@pytest.mark.asyncio
async def test_update_plan_records_steps_and_runtime_lines(tmp_path):
    sm = SessionManager(tmp_path)
    tool = _tool(sm)

    out = await tool.execute(
        objective="Fix context",
        steps=[
            {"step": "Inspect context code", "status": "completed"},
            {"step": "Patch plan handling", "status": "in_progress"},
            {"step": "Run tests", "status": "pending"},
        ],
        note="working",
    )

    assert "Plan active" in out
    sess = sm.get_or_create("cli:direct")
    assert sess.metadata[PLAN_MODE_KEY] is True
    plan = sess.metadata[PLAN_STATE_KEY]
    assert plan["objective"] == "Fix context"
    assert plan["steps"][1]["status"] == "in_progress"
    lines = "\n".join(plan_state_runtime_lines(sess.metadata))
    assert "Plan mode: active executable plan" in lines
    assert "Patch plan handling" in lines


@pytest.mark.asyncio
async def test_update_plan_clear_removes_metadata(tmp_path):
    sm = SessionManager(tmp_path)
    tool = _tool(sm)
    await tool.execute(objective="X", steps=[{"step": "one", "status": "in_progress"}])

    out = await tool.execute(status="clear")

    assert out == "Plan cleared."
    sess = sm.get_or_create("cli:direct")
    assert PLAN_STATE_KEY not in sess.metadata
    assert PLAN_MODE_KEY not in sess.metadata


@pytest.mark.asyncio
async def test_update_plan_completed_turns_plan_mode_off(tmp_path):
    sm = SessionManager(tmp_path)
    tool = _tool(sm)
    await tool.execute(objective="X", steps=[{"step": "one", "status": "completed"}])

    out = await tool.execute(status="completed")

    assert "Plan completed" in out
    sess = sm.get_or_create("cli:direct")
    assert sess.metadata[PLAN_STATE_KEY]["status"] == "completed"
    assert PLAN_MODE_KEY not in sess.metadata


def test_update_plan_registered(tmp_path):
    from unittest.mock import MagicMock

    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    loop = AgentLoop(bus=MessageBus(), provider=provider, workspace=tmp_path, model="test-model")
    tool = loop.tools.get("update_plan")
    assert tool is not None
    assert tool.name == "update_plan"
