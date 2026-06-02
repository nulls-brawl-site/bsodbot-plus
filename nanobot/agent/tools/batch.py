"""Batch tool wrapper for multiple tool calls in one model action."""

from __future__ import annotations

import asyncio
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.schema import (
    ArraySchema,
    ObjectSchema,
    StringSchema,
    tool_parameters_schema,
)
from nanobot.utils.helpers import truncate_text


@tool_parameters(
    tool_parameters_schema(
        calls=ArraySchema(
            items=ObjectSchema(
                tool=StringSchema("Tool name to call."),
                arguments=ObjectSchema(
                    description="Arguments object for that tool.",
                    additional_properties=True,
                ),
                required=["tool", "arguments"],
            ),
            description="Tool calls to execute. Independent read-only calls run in parallel; mutating calls run in order.",
            min_items=1,
            max_items=8,
        ),
        required=["calls"],
    )
)
class RunToolsTool(Tool):
    """Execute several existing nanobot tools from one model tool call."""

    _plugin_discoverable = False

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    @property
    def name(self) -> str:
        return "run_tools"

    @property
    def description(self) -> str:
        return (
            "Execute up to 8 existing tools in one call. Use for independent reads/searches or small grouped edits "
            "to avoid many separate assistant tool-call turns. Each item has tool and arguments. Read-only calls are "
            "run concurrently; mutating/exclusive calls are run sequentially in the listed order. Do not call run_tools "
            "from inside run_tools."
        )

    @property
    def exclusive(self) -> bool:
        return True

    async def execute(self, calls: list[dict[str, Any]], **kwargs: Any) -> str:
        if not isinstance(calls, list) or not calls:
            return "Error: calls must be a non-empty list."
        if len(calls) > 8:
            return "Error: run_tools supports at most 8 calls."

        prepared: list[tuple[int, str, Any, Any, str | None]] = []
        for index, call in enumerate(calls, start=1):
            if not isinstance(call, dict):
                return f"Error: calls[{index}] must be an object."
            name = str(call.get("tool") or "").strip()
            if not name:
                return f"Error: calls[{index}].tool is required."
            if name == self.name:
                return "Error: run_tools cannot call itself."
            args = call.get("arguments")
            if not isinstance(args, dict):
                return f"Error: calls[{index}].arguments must be an object."
            tool, params, error = self._registry.prepare_call(name, args)
            prepared.append((index, name, tool, params, error))

        results: list[tuple[int, str, Any]] = []

        async def _run_one(index: int, name: str, tool: Any, params: dict[str, Any], error: str | None):
            if error:
                return index, name, error
            try:
                return index, name, await tool.execute(**params)
            except Exception as exc:
                return index, name, f"Error executing {name}: {exc}"

        read_batch: list[tuple[int, str, Any, dict[str, Any], str | None]] = []

        async def _flush_reads() -> None:
            if not read_batch:
                return
            batch = list(read_batch)
            read_batch.clear()
            results.extend(await asyncio.gather(*(_run_one(*item) for item in batch)))

        for index, name, tool, params, error in prepared:
            read_only = bool(tool is not None and tool.concurrency_safe and not error)
            if read_only:
                read_batch.append((index, name, tool, params, error))
                continue
            await _flush_reads()
            results.append(await _run_one(index, name, tool, params, error))
        await _flush_reads()

        results.sort(key=lambda item: item[0])
        parts: list[str] = []
        for index, name, result in results:
            text = result if isinstance(result, str) else str(result)
            parts.append(f"## {index}. {name}\n{truncate_text(text, 8_000)}")
        return "\n\n".join(parts)
