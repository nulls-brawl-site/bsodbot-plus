"""Session metadata helpers for executable task plans."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, MutableMapping

PLAN_STATE_KEY = "task_plan"
PLAN_MODE_KEY = "plan_mode"
_VALID_STEP_STATUSES = {"pending", "in_progress", "completed"}
_MAX_RUNTIME_LINES = 40
_MAX_STEP_CHARS = 240
_MAX_OBJECTIVE_CHARS = 1000


def _now_iso() -> str:
    return datetime.now().isoformat()


def normalize_plan_steps(steps: Any) -> list[dict[str, str]]:
    """Normalize user/tool supplied plan steps into serializable records."""
    if not isinstance(steps, list):
        return []
    out: list[dict[str, str]] = []
    in_progress_seen = False
    for item in steps[:50]:
        if isinstance(item, str):
            step = item.strip()
            status = "pending"
        elif isinstance(item, Mapping):
            step = str(item.get("step") or item.get("text") or "").strip()
            status = str(item.get("status") or "pending").strip().lower()
        else:
            continue
        if not step:
            continue
        if status not in _VALID_STEP_STATUSES:
            status = "pending"
        if status == "in_progress":
            if in_progress_seen:
                status = "pending"
            else:
                in_progress_seen = True
        out.append({"step": step[:_MAX_STEP_CHARS], "status": status})
    return out


def current_plan(metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    plan = metadata.get(PLAN_STATE_KEY)
    return plan if isinstance(plan, dict) else None


def plan_mode_enabled(metadata: Mapping[str, Any] | None) -> bool:
    if not metadata:
        return False
    return bool(metadata.get(PLAN_MODE_KEY))


def set_plan_mode(metadata: MutableMapping[str, Any], enabled: bool) -> None:
    if enabled:
        metadata[PLAN_MODE_KEY] = True
    else:
        metadata.pop(PLAN_MODE_KEY, None)


def set_plan_state(
    metadata: MutableMapping[str, Any],
    *,
    objective: str | None,
    steps: list[dict[str, str]],
    note: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    status = status if status in {"active", "completed"} else "active"
    previous = current_plan(metadata) or {}
    now = _now_iso()
    plan = {
        "status": status,
        "objective": (objective or previous.get("objective") or "").strip()[:_MAX_OBJECTIVE_CHARS],
        "steps": steps,
        "updated_at": now,
        "created_at": previous.get("created_at") or now,
    }
    if note:
        plan["note"] = note.strip()[:1000]
    metadata[PLAN_STATE_KEY] = plan
    if status == "active":
        metadata[PLAN_MODE_KEY] = True
    else:
        metadata.pop(PLAN_MODE_KEY, None)
    return plan


def clear_plan_state(metadata: MutableMapping[str, Any]) -> None:
    metadata.pop(PLAN_STATE_KEY, None)
    metadata.pop(PLAN_MODE_KEY, None)


def plan_state_runtime_lines(metadata: Mapping[str, Any] | None) -> list[str]:
    if not plan_mode_enabled(metadata):
        return []
    plan = current_plan(metadata)
    lines = [
        "Plan mode: active executable plan.",
        "Maintain a short task plan, update it when progress changes, and continue executing the current in-progress/pending step with tools.",
        "Do not stop after merely writing a plan unless the user explicitly asks for plan-only output.",
    ]
    if not plan:
        lines.append("Current plan: none yet; create one with update_plan, then execute it.")
        return lines
    objective = str(plan.get("objective") or "").strip()
    if objective:
        lines.append(f"Plan objective: {objective[:_MAX_OBJECTIVE_CHARS]}")
    steps = normalize_plan_steps(plan.get("steps"))
    if not steps:
        lines.append("Current plan steps: none; create concise steps with update_plan.")
    else:
        lines.append("Current plan steps:")
        for index, item in enumerate(steps[:_MAX_RUNTIME_LINES], start=1):
            lines.append(f"{index}. [{item['status']}] {item['step']}")
        if len(steps) > _MAX_RUNTIME_LINES:
            lines.append(f"... {len(steps) - _MAX_RUNTIME_LINES} more step(s) omitted")
    note = str(plan.get("note") or "").strip()
    if note:
        lines.append(f"Plan note: {note[:1000]}")
    return lines
