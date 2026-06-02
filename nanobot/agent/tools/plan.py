"""Executable task plan tool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.context import ContextAware, RequestContext
from nanobot.agent.tools.schema import (
    ArraySchema,
    ObjectSchema,
    StringSchema,
    tool_parameters_schema,
)
from nanobot.session.plan_state import clear_plan_state, normalize_plan_steps, set_plan_state

if TYPE_CHECKING:
    from nanobot.session.manager import SessionManager


@tool_parameters(
    tool_parameters_schema(
        objective=StringSchema(
            "Current objective this plan serves. Required when creating a new plan; can be omitted for progress-only updates.",
            max_length=1000,
            nullable=True,
        ),
        steps=ArraySchema(
            items=ObjectSchema(
                step=StringSchema("Concrete step text.", max_length=240),
                status=StringSchema(
                    "Step status. Use exactly one in_progress step when work is active.",
                    enum=["pending", "in_progress", "completed"],
                ),
                required=["step", "status"],
            ),
            description="Full current plan. Include completed, in_progress, and pending steps in order.",
            min_items=1,
            max_items=50,
            nullable=True,
        ),
        note=StringSchema(
            "Optional short status note, blocker, or next action.",
            max_length=1000,
            nullable=True,
        ),
        status=StringSchema(
            "Plan lifecycle status.",
            enum=["active", "completed", "clear"],
            nullable=True,
        ),
        required=[],
    )
)
class UpdatePlanTool(Tool, ContextAware):
    """Create, update, complete, or clear the executable plan for this session."""
    _scopes = {"core"}

    def __init__(self, sessions: SessionManager) -> None:
        self._sessions = sessions
        self._request_ctx: RequestContext | None = None

    @classmethod
    def create(cls, ctx: Any) -> Tool:
        sess = getattr(ctx, "sessions", None)
        assert sess is not None
        return cls(sessions=sess)

    @classmethod
    def enabled(cls, ctx: Any) -> bool:
        return getattr(ctx, "sessions", None) is not None

    def set_context(self, ctx: RequestContext) -> None:
        self._request_ctx = ctx

    @property
    def name(self) -> str:
        return "update_plan"

    @property
    def description(self) -> str:
        return (
            "Create or update the active executable plan for this chat. Use this for multi-step work: "
            "write a short plan, mark exactly one current step in_progress, update completed steps as you work, "
            "and keep using normal tools to execute the plan. This is not a plan-only mode; it is bookkeeping that "
            "keeps the plan visible in context across turns and compaction. Use status=completed when all steps are done, "
            "or status=clear when the plan is obsolete."
        )

    def _session(self):
        if self._request_ctx is None or not self._request_ctx.session_key:
            return None
        return self._sessions.get_or_create(self._request_ctx.session_key)

    async def execute(
        self,
        objective: str | None = None,
        steps: list[dict[str, Any]] | None = None,
        note: str | None = None,
        status: str | None = None,
        **kwargs: Any,
    ) -> str:
        sess = self._session()
        if sess is None:
            return "Error: update_plan requires an active chat session."

        lifecycle = (status or "active").strip().lower()
        if lifecycle == "clear":
            clear_plan_state(sess.metadata)
            self._sessions.save(sess)
            return "Plan cleared."

        normalized_steps = normalize_plan_steps(steps)
        if not normalized_steps:
            current = sess.metadata.get("task_plan")
            if isinstance(current, dict):
                normalized_steps = normalize_plan_steps(current.get("steps"))
        if not normalized_steps:
            return "Error: update_plan needs at least one step when creating a plan."

        plan = set_plan_state(
            sess.metadata,
            objective=objective,
            steps=normalized_steps,
            note=note,
            status="completed" if lifecycle == "completed" else "active",
        )
        self._sessions.save(sess)
        counts = {"pending": 0, "in_progress": 0, "completed": 0}
        for item in normalized_steps:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return (
            f"Plan {plan['status']}: {len(normalized_steps)} step(s) "
            f"({counts['completed']} completed, {counts['in_progress']} in progress, {counts['pending']} pending)."
        )
