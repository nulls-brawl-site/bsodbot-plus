"""Tests for run_tools batch wrapper."""

from __future__ import annotations

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.batch import RunToolsTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.schema import StringSchema, tool_parameters_schema


@tool_parameters(tool_parameters_schema(value=StringSchema("value"), required=["value"]))
class EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "echo"

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, value: str, **kwargs):
        return f"echo:{value}"


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(RunToolsTool(registry))
    return registry


async def test_run_tools_executes_multiple_calls():
    registry = _registry()
    tool = registry.get("run_tools")

    out = await tool.execute(calls=[
        {"tool": "echo", "arguments": {"value": "one"}},
        {"tool": "echo", "arguments": {"value": "two"}},
    ])

    assert "## 1. echo" in out
    assert "echo:one" in out
    assert "## 2. echo" in out
    assert "echo:two" in out


async def test_run_tools_rejects_self_call():
    registry = _registry()
    tool = registry.get("run_tools")

    out = await tool.execute(calls=[{"tool": "run_tools", "arguments": {"calls": []}}])

    assert "cannot call itself" in out
