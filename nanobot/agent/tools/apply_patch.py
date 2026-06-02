"""Apply file edits by providing structured edit instructions."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import tool_parameters
from nanobot.agent.tools.filesystem import _FsTool
from nanobot.agent.tools.schema import (
    ArraySchema,
    BooleanSchema,
    IntegerSchema,
    ObjectSchema,
    StringSchema,
    tool_parameters_schema,
)


@dataclass(slots=True)
class _PatchSummary:
    action: str
    path: str
    added: int = 0
    deleted: int = 0


class _PatchError(ValueError):
    pass


_ABSOLUTE_WINDOWS_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _validate_relative_path(path: str) -> str:
    normalized = path.strip()
    if not normalized:
        raise _PatchError("patch path cannot be empty")
    if "\0" in normalized:
        raise _PatchError(f"patch path contains a null byte: {path!r}")
    if normalized.startswith(("~", "/", "\\")) or _ABSOLUTE_WINDOWS_RE.match(normalized):
        raise _PatchError(f"patch path must be relative: {path}")
    if any(part == ".." for part in re.split(r"[\\/]+", normalized)):
        raise _PatchError(f"patch path must not contain '..': {path}")
    return normalized


def _lines_to_text(lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _text_line_count(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def _line_diff_stats(before: str, after: str) -> tuple[int, int]:
    before_lines = before.replace("\r\n", "\n").splitlines()
    after_lines = after.replace("\r\n", "\n").splitlines()
    added = 0
    deleted = 0
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("replace", "delete"):
            deleted += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return added, deleted


def _format_summary(summary: _PatchSummary) -> str:
    stats = ""
    if summary.added or summary.deleted:
        stats = f" (+{summary.added}/-{summary.deleted})"
    return f"- {summary.action} {summary.path}{stats}"


def _read_existing_text(source: Path, path: str, writes: dict[Path, str]) -> tuple[str, bool]:
    pending = writes.get(source)
    if pending is not None:
        return pending, True
    if not source.exists():
        raise _PatchError(f"file to update does not exist: {path}")
    if not source.is_file():
        raise _PatchError(f"path to update is not a file: {path}")
    raw = source.read_bytes()
    try:
        return raw.decode("utf-8"), False
    except UnicodeDecodeError:
        raise _PatchError(f"file is not UTF-8 text: {path}")


def _require_line_number(value: Any, field: str, path: str) -> int:
    if type(value) is not int:
        raise _PatchError(f"{field} required for line edit: {path}")
    if value < 1:
        raise _PatchError(f"{field} must be >= 1 for line edit: {path}")
    return value


def _line_block(text: str) -> str:
    block = text.replace("\r\n", "\n")
    if block and not block.endswith("\n"):
        block += "\n"
    return block


def _line_pieces(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _expected_text_matches(actual: str, expected: str) -> bool:
    actual_norm = actual.replace("\r\n", "\n")
    expected_norm = expected.replace("\r\n", "\n")
    return actual_norm == expected_norm or actual_norm.rstrip("\n") == expected_norm.rstrip("\n")


def _ensure_final_newline(text: str) -> str:
    if text and not text.endswith("\n"):
        return text + "\n"
    return text


@tool_parameters(
    tool_parameters_schema(
        edits=ArraySchema(
            items=ObjectSchema(
                path=StringSchema("Relative path to the file to edit."),
                action=StringSchema(
                    "Operation type: replace/add/delete for text blocks, or replace_lines/insert_lines/delete_lines for 1-based line edits.",
                    enum=[
                        "replace",
                        "add",
                        "delete",
                        "replace_lines",
                        "insert_lines",
                        "delete_lines",
                    ],
                ),
                old_text=StringSchema(
                    "Exact text to search for in the file. Required for replace and delete. Optional guard for line edits.",
                    nullable=True,
                ),
                new_text=StringSchema(
                    "Text to replace with, insert, or append. Required for replace, add, replace_lines, and insert_lines.",
                    nullable=True,
                ),
                start_line=IntegerSchema(
                    description="1-based start line for replace_lines, insert_lines, or delete_lines.",
                    minimum=1,
                    nullable=True,
                ),
                end_line=IntegerSchema(
                    description="1-based inclusive end line for replace_lines or delete_lines. Defaults to start_line.",
                    minimum=1,
                    nullable=True,
                ),
                position=StringSchema(
                    "For insert_lines, insert before or after start_line. Defaults to before.",
                    enum=["before", "after"],
                    nullable=True,
                ),
                expected_old_text=StringSchema(
                    "Optional exact text guard for the selected line range before replacing or deleting.",
                    nullable=True,
                ),
                required=["path", "action"],
            ),
            description="List of edits to apply. Each edit specifies a file and the change to make.",
            min_items=1,
            max_items=20,
        ),
        dry_run=BooleanSchema(
            description="Validate and summarize the patch without writing files.",
            default=False,
        ),
        required=["edits"],
    )
)
class ApplyPatchTool(_FsTool):
    """Apply file edits by providing structured edit instructions."""
    _scopes = {"core", "subagent"}

    @property
    def name(self) -> str:
        return "apply_patch"

    @property
    def description(self) -> str:
        return (
            "Default tool for code edits. Supports multi-file changes in a single call. "
            "Provide a list of structured edits, each specifying a file path, action, and the text or line range to change. "
            "Use replace_lines, insert_lines, or delete_lines with start_line/end_line for surgical line-based edits. "
            "Paths must be relative. Set dry_run=true to validate and preview without writing files. "
            "Use edit_file only for small exact replacements on a single file."
        )

    async def execute(
        self,
        edits: list[dict] | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> str:
        try:
            if not edits:
                raise _PatchError("must provide edits")

            writes: dict[Path, str] = {}
            deletes: set[Path] = set()
            summaries: list[_PatchSummary] = []

            for edit in edits:
                if not isinstance(edit, dict):
                    raise _PatchError("each edit must be an object")
                raw_path = edit.get("path")
                if not isinstance(raw_path, str):
                    raise _PatchError("path required for edit")
                path = _validate_relative_path(raw_path)
                action = edit.get("action")
                if not isinstance(action, str):
                    raise _PatchError(f"action required for edit: {path}")
                source = self._resolve(path)

                if action == "add":
                    new_text = edit.get("new_text")
                    if new_text is None:
                        raise _PatchError(f"new_text required for add: {path}")

                    pending = writes.get(source)
                    if pending is not None:
                        content = pending
                        exists = True
                    elif source.exists():
                        raw = source.read_bytes()
                        try:
                            content = raw.decode("utf-8")
                        except UnicodeDecodeError:
                            raise _PatchError(f"file is not UTF-8 text: {path}")
                        exists = True
                    else:
                        content = ""
                        exists = False

                    if exists:
                        uses_crlf = "\r\n" in content
                        new_norm = content.replace("\r\n", "\n") + new_text.replace("\r\n", "\n")
                        if new_norm and not new_norm.endswith("\n"):
                            new_norm += "\n"
                        if uses_crlf:
                            new_norm = new_norm.replace("\n", "\r\n")
                        writes[source] = new_norm
                        deletes.discard(source)
                        added, deleted = _line_diff_stats(content, new_norm)
                        action_name = "update"
                    else:
                        new_norm = new_text.replace("\r\n", "\n")
                        if new_norm and not new_norm.endswith("\n"):
                            new_norm += "\n"
                        writes[source] = new_norm
                        deletes.discard(source)
                        added = _text_line_count(new_norm)
                        deleted = 0
                        action_name = "add"

                    summaries.append(
                        _PatchSummary(
                            action=action_name, path=path, added=added, deleted=deleted
                        )
                    )

                elif action == "replace":
                    old_text = edit.get("old_text") or ""
                    if not old_text:
                        raise _PatchError(f"old_text required for replace: {path}")
                    new_text = edit.get("new_text")
                    if new_text is None:
                        raise _PatchError(f"new_text required for replace: {path}")

                    pending = writes.get(source)
                    if pending is not None:
                        content = pending
                    elif source.exists():
                        raw = source.read_bytes()
                        try:
                            content = raw.decode("utf-8")
                        except UnicodeDecodeError:
                            raise _PatchError(f"file is not UTF-8 text: {path}")
                    else:
                        raise _PatchError(f"file to update does not exist: {path}")

                    if pending is None and not source.is_file():
                        raise _PatchError(f"path to update is not a file: {path}")

                    uses_crlf = "\r\n" in content
                    norm_content = content.replace("\r\n", "\n")
                    norm_old = old_text.replace("\r\n", "\n")

                    pos = norm_content.find(norm_old)
                    if pos < 0:
                        raise _PatchError(f"old_text not found in {path}")
                    if norm_content.find(norm_old, pos + 1) >= 0:
                        raise _PatchError(f"old_text appears multiple times in {path}")

                    new_norm = (
                        norm_content[:pos]
                        + new_text.replace("\r\n", "\n")
                        + norm_content[pos + len(norm_old) :]
                    )
                    if new_norm and not new_norm.endswith("\n"):
                        new_norm += "\n"
                    if uses_crlf:
                        new_norm = new_norm.replace("\n", "\r\n")

                    writes[source] = new_norm
                    deletes.discard(source)
                    added, deleted = _line_diff_stats(content, new_norm)
                    summaries.append(
                        _PatchSummary(
                            action="update", path=path, added=added, deleted=deleted
                        )
                    )

                elif action == "delete":
                    old_text = edit.get("old_text") or ""
                    if not old_text:
                        raise _PatchError(f"old_text required for delete: {path}")

                    pending = writes.get(source)
                    if pending is not None:
                        content = pending
                    elif source.exists():
                        raw = source.read_bytes()
                        try:
                            content = raw.decode("utf-8")
                        except UnicodeDecodeError:
                            raise _PatchError(f"file is not UTF-8 text: {path}")
                    else:
                        raise _PatchError(f"file to update does not exist: {path}")

                    if pending is None and not source.is_file():
                        raise _PatchError(f"path to update is not a file: {path}")

                    uses_crlf = "\r\n" in content
                    norm_content = content.replace("\r\n", "\n")
                    norm_old = old_text.replace("\r\n", "\n")

                    pos = norm_content.find(norm_old)
                    if pos < 0:
                        raise _PatchError(f"old_text not found in {path}")
                    if norm_content.find(norm_old, pos + 1) >= 0:
                        raise _PatchError(f"old_text appears multiple times in {path}")

                    if norm_old == norm_content:
                        deletes.add(source)
                        writes.pop(source, None)
                        added, deleted = 0, _text_line_count(content)
                        summaries.append(
                            _PatchSummary(
                                action="delete", path=path, added=added, deleted=deleted
                            )
                        )
                    else:
                        new_norm = (
                            norm_content[:pos] + norm_content[pos + len(norm_old) :]
                        )
                        if new_norm and not new_norm.endswith("\n"):
                            new_norm += "\n"
                        if uses_crlf:
                            new_norm = new_norm.replace("\n", "\r\n")
                        writes[source] = new_norm
                        deletes.discard(source)
                        added, deleted = _line_diff_stats(content, new_norm)
                        summaries.append(
                            _PatchSummary(
                                action="update", path=path, added=added, deleted=deleted
                            )
                        )

                elif action in {"replace_lines", "insert_lines", "delete_lines"}:
                    content, _ = _read_existing_text(source, path, writes)
                    uses_crlf = "\r\n" in content
                    norm_content = content.replace("\r\n", "\n")
                    lines = _line_pieces(norm_content)
                    line_count = len(lines)
                    start_line = _require_line_number(edit.get("start_line"), "start_line", path)

                    if action == "insert_lines":
                        new_text = edit.get("new_text")
                        if new_text is None:
                            raise _PatchError(f"new_text required for insert_lines: {path}")
                        block = _line_block(new_text)
                        if not block:
                            raise _PatchError(f"new_text cannot be empty for insert_lines: {path}")
                        position = edit.get("position") or "before"
                        if position not in {"before", "after"}:
                            raise _PatchError(f"position must be before or after for insert_lines: {path}")

                        if line_count == 0:
                            if start_line != 1:
                                raise _PatchError(
                                    f"start_line {start_line} is out of range for empty file: {path}"
                                )
                            lines = _line_pieces(block)
                        else:
                            if start_line > line_count:
                                raise _PatchError(
                                    f"start_line {start_line} is out of range; {path} has {line_count} lines"
                                )
                            index = start_line - 1 if position == "before" else start_line
                            if position == "after" and not lines[start_line - 1].endswith("\n"):
                                lines[start_line - 1] += "\n"
                            lines[index:index] = _line_pieces(block)
                    else:
                        if line_count == 0:
                            raise _PatchError(f"cannot {action} in empty file: {path}")
                        end_value = edit.get("end_line")
                        end_line = (
                            start_line
                            if end_value is None
                            else _require_line_number(end_value, "end_line", path)
                        )
                        if end_line < start_line:
                            raise _PatchError(f"end_line must be >= start_line for line edit: {path}")
                        if end_line > line_count:
                            raise _PatchError(
                                f"end_line {end_line} is out of range; {path} has {line_count} lines"
                            )

                        selected = "".join(lines[start_line - 1 : end_line])
                        expected_old_text = edit.get("expected_old_text")
                        if expected_old_text is None:
                            expected_old_text = edit.get("old_text")
                        if expected_old_text is not None:
                            if not isinstance(expected_old_text, str):
                                raise _PatchError(f"expected_old_text must be text for line edit: {path}")
                            if not _expected_text_matches(selected, expected_old_text):
                                raise _PatchError(
                                    f"selected lines {start_line}-{end_line} did not match expected_old_text in {path}"
                                )

                        if action == "replace_lines":
                            new_text = edit.get("new_text")
                            if new_text is None:
                                raise _PatchError(f"new_text required for replace_lines: {path}")
                            lines[start_line - 1 : end_line] = _line_pieces(_line_block(new_text))
                        else:
                            lines[start_line - 1 : end_line] = []

                    new_norm = _ensure_final_newline("".join(lines))
                    if uses_crlf:
                        new_norm = new_norm.replace("\n", "\r\n")
                    writes[source] = new_norm
                    deletes.discard(source)
                    added, deleted = _line_diff_stats(content, new_norm)
                    summaries.append(
                        _PatchSummary(
                            action="update", path=path, added=added, deleted=deleted
                        )
                    )

                else:
                    raise _PatchError(f"unknown action: {action}")

            if dry_run:
                return "Patch dry-run succeeded:\n" + "\n".join(
                    _format_summary(summary) for summary in summaries
                )

            backups: dict[Path, bytes | None] = {}
            for path in set(writes) | deletes:
                backups[path] = path.read_bytes() if path.exists() else None

            try:
                for path in deletes:
                    if path.exists():
                        path.unlink()
                for path, content in writes.items():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8", newline="")
            except Exception:
                for path, data in backups.items():
                    if data is None:
                        if path.exists():
                            path.unlink()
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                raise

            for path in set(writes) | deletes:
                self._file_states.record_write(path)
            return "Patch applied:\n" + "\n".join(
                _format_summary(summary) for summary in summaries
            )
        except PermissionError as exc:
            return f"Error: {exc}"
        except _PatchError as exc:
            return f"Error applying patch: {exc}"
        except Exception as exc:
            return f"Error applying patch: {exc}"
