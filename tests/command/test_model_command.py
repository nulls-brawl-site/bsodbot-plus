from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.command.builtin import (
    build_help_text,
    builtin_command_palette,
    cmd_goal,
    cmd_model,
    cmd_plan,
    register_builtin_commands,
)
from nanobot.command.router import CommandContext, CommandRouter
from nanobot.config.schema import ModelPresetConfig


def _provider(default_model: str, max_tokens: int = 123) -> MagicMock:
    provider = MagicMock()
    provider.get_default_model.return_value = default_model
    provider.generation = SimpleNamespace(
        max_tokens=max_tokens,
        temperature=0.1,
        reasoning_effort=None,
    )
    return provider


def _make_loop(tmp_path) -> AgentLoop:
    return AgentLoop(
        bus=MessageBus(),
        provider=_provider("base-model", max_tokens=123),
        workspace=tmp_path,
        model="base-model",
        context_window_tokens=1000,
        model_presets={
            "default": ModelPresetConfig(
                model="base-model",
                max_tokens=123,
                context_window_tokens=1000,
            ),
            "fast": ModelPresetConfig(
                model="openai/gpt-4.1",
                max_tokens=4096,
                context_window_tokens=32_768,
            ),
        },
    )


def _ctx(loop: AgentLoop, raw: str, args: str = "") -> CommandContext:
    msg = InboundMessage(channel="cli", sender_id="user", chat_id="direct", content=raw)
    return CommandContext(msg=msg, session=None, key=msg.session_key, raw=raw, args=args, loop=loop)


def _ctx_session(loop: AgentLoop, raw: str, args: str = "") -> CommandContext:
    msg = InboundMessage(channel="cli", sender_id="user", chat_id="direct", content=raw)
    return CommandContext(
        msg=msg, session=MagicMock(), key=msg.session_key, raw=raw, args=args, loop=loop,
    )


@pytest.mark.asyncio
async def test_model_command_lists_current_and_available_presets(tmp_path) -> None:
    loop = _make_loop(tmp_path)

    out = await cmd_model(_ctx(loop, "/model"))

    assert "Current model: `base-model`" in out.content
    assert "Current preset: `default`" in out.content
    assert "Available presets" not in out.content
    assert "## Presets (2)" in out.content
    assert "`default` (active): model `base-model`" in out.content
    assert "`fast`: model `openai/gpt-4.1`" in out.content
    assert "provider `auto`" in out.content
    assert "`fast`" in out.content
    assert out.metadata == {"render_as": "text"}


@pytest.mark.asyncio
async def test_model_command_switches_preset(tmp_path) -> None:
    loop = _make_loop(tmp_path)

    out = await cmd_model(_ctx(loop, "/model fast", args="fast"))

    assert "Switched model preset to `fast`." in out.content
    assert "Model: `openai/gpt-4.1`" in out.content
    assert loop.model_preset == "fast"
    assert loop.model == "openai/gpt-4.1"
    assert loop.subagents.model == "openai/gpt-4.1"
    assert loop.consolidator.model == "openai/gpt-4.1"
    assert loop.dream.model == "openai/gpt-4.1"


@pytest.mark.asyncio
async def test_model_command_switches_back_to_default(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    loop.set_model_preset("fast")

    out = await cmd_model(_ctx(loop, "/model default", args="default"))

    assert "Switched model preset to `default`." in out.content
    assert loop.model_preset == "default"
    assert loop.model == "base-model"
    assert loop.context_window_tokens == 1000


@pytest.mark.asyncio
async def test_model_command_unknown_preset_keeps_old_state(tmp_path) -> None:
    loop = _make_loop(tmp_path)

    out = await cmd_model(_ctx(loop, "/model missing", args="missing"))

    assert "Could not switch model preset" in out.content
    assert "\"model_preset" not in out.content
    assert "Available presets: `default`, `fast`" in out.content
    assert loop.model_preset is None
    assert loop.model == "base-model"


@pytest.mark.asyncio
async def test_model_command_does_not_depend_on_my_allow_set(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    assert loop.tools_config.my.allow_set is False

    await cmd_model(_ctx(loop, "/model fast", args="fast"))

    assert loop.model_preset == "fast"


@pytest.mark.asyncio
async def test_model_command_provider_error_does_not_dump_every_preset(tmp_path, monkeypatch) -> None:
    loop = _make_loop(tmp_path)

    def fail_set_model_preset(_name: str) -> None:
        raise ValueError("No API key configured for provider 'openai'.")

    monkeypatch.setattr(loop, "set_model_preset", fail_set_model_preset)

    out = await cmd_model(_ctx(loop, "/model fast", args="fast"))

    assert "Could not switch model preset" in out.content
    assert "No API key configured" in out.content
    assert "Available presets" not in out.content
    assert "Use `/models`" in out.content


@pytest.mark.asyncio
async def test_model_command_registered_as_exact_and_prefix(tmp_path) -> None:
    router = CommandRouter()
    register_builtin_commands(router)
    loop = _make_loop(tmp_path)

    out = await router.dispatch(_ctx(loop, "/model fast"))

    assert out is not None
    assert "Switched model preset" in out.content
    assert loop.model_preset == "fast"


@pytest.mark.asyncio
async def test_models_command_browses_providers_and_models(tmp_path) -> None:
    router = CommandRouter()
    register_builtin_commands(router)
    loop = _make_loop(tmp_path)

    listed = await router.dispatch(_ctx(loop, "/models"))
    provider = await router.dispatch(_ctx(loop, "/models provider auto"))
    switched = await router.dispatch(_ctx(loop, "/model fast"))

    assert listed is not None
    assert "Choose provider" in listed.content
    assert listed.buttons == [["Auto (2) ✓"]]
    assert listed.button_values == [["/models provider auto"]]
    assert provider is not None
    assert "Choose model" in provider.content
    assert provider.button_values == [["/models"], ["/model default"], ["/model fast"]]
    assert switched is not None and "Switched model preset" in switched.content
    assert loop.model_preset == "fast"


@pytest.mark.asyncio
async def test_models_command_is_not_model_alias(tmp_path) -> None:
    router = CommandRouter()
    register_builtin_commands(router)
    loop = _make_loop(tmp_path)

    out = await router.dispatch(_ctx(loop, "/models fast"))

    assert out is not None
    assert "Unknown model provider `fast`" in out.content
    assert loop.model_preset is None


def test_model_command_in_help_and_palette() -> None:
    palette = builtin_command_palette()

    assert any(item["command"] == "/model" and item["arg_hint"] == "[preset]" for item in palette)
    assert any(item["command"] == "/models" and item["arg_hint"] == "[provider]" for item in palette)
    assert "/model [preset]" in build_help_text()
    assert "/models [provider]" in build_help_text()


@pytest.mark.asyncio
async def test_plan_command_shows_empty_status(tmp_path) -> None:
    loop = _make_loop(tmp_path)

    out = await cmd_plan(_ctx(loop, "/plan"))

    assert out is not None
    assert "Plan mode: off" in out.content
    assert "Current plan: none" in out.content


@pytest.mark.asyncio
async def test_plan_command_on_and_clear(tmp_path) -> None:
    loop = _make_loop(tmp_path)

    on = await cmd_plan(_ctx(loop, "/plan on", args="on"))
    clear = await cmd_plan(_ctx(loop, "/plan clear", args="clear"))

    session = loop.sessions.get_or_create("cli:direct")
    assert on is not None and "enabled" in on.content
    assert clear is not None and "cleared" in clear.content.lower()
    assert session.metadata == {}


@pytest.mark.asyncio
async def test_plan_command_off_disables_without_clearing_current_plan(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    session = loop.sessions.get_or_create("cli:direct")
    session.metadata = {
        "plan_mode": True,
        "task_plan": {
            "status": "active",
            "objective": "Fix context",
            "steps": [{"step": "Check Telegram commands", "status": "in_progress"}],
        },
    }
    loop.sessions.save(session)

    off = await cmd_plan(_ctx(loop, "/plan off", args="off"))
    status = await cmd_plan(_ctx(loop, "/plan"))

    session = loop.sessions.get_or_create("cli:direct")
    assert off is not None and "disabled" in off.content.lower()
    assert "plan_mode" not in session.metadata
    assert session.metadata["task_plan"]["objective"] == "Fix context"
    assert status is not None
    assert "Plan mode: off" in status.content
    assert "Fix context" in status.content


@pytest.mark.asyncio
async def test_plan_command_rewrites_objective_to_agent_prompt(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    ctx = _ctx_session(loop, "/plan fix the bot", args="fix the bot")

    out = await cmd_plan(ctx)

    assert out is None
    assert "fix the bot" in ctx.msg.content
    assert "update_plan" in ctx.msg.content
    assert ctx.msg.metadata.get("original_command") == "/plan"


@pytest.mark.asyncio
async def test_goal_command_shows_usage_without_args(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    out = await cmd_goal(_ctx(loop, "/goal"))
    assert out is not None
    assert "Usage: /goal" in out.content


@pytest.mark.asyncio
async def test_goal_command_rejects_mid_turn_without_session(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    out = await cmd_goal(_ctx(loop, "/goal do work", args="do work"))
    assert out is not None
    assert "/stop" in out.content


@pytest.mark.asyncio
async def test_goal_command_rewrites_to_agent_prompt(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    ctx = _ctx_session(loop, "/goal audit the repo", args="audit the repo")
    out = await cmd_goal(ctx)
    assert out is None
    assert "audit the repo" in ctx.msg.content
    assert "long_task" in ctx.msg.content
    assert ctx.msg.metadata.get("original_command") == "/goal"
    assert ctx.msg.metadata.get("original_content") == "/goal audit the repo"
    assert isinstance(ctx.msg.metadata.get("goal_started_at"), int | float)


@pytest.mark.asyncio
async def test_goal_command_registered_on_router(tmp_path) -> None:
    router = CommandRouter()
    register_builtin_commands(router)
    loop = _make_loop(tmp_path)
    ctx = _ctx_session(loop, "/goal ship it", args="ship it")
    out = await router.dispatch(ctx)
    assert out is None
    assert "ship it" in ctx.msg.content


def test_goal_command_in_help_and_palette() -> None:
    palette = builtin_command_palette()
    assert any(item["command"] == "/goal" and item["arg_hint"] == "<goal>" for item in palette)
    assert "/goal <goal>" in build_help_text()
