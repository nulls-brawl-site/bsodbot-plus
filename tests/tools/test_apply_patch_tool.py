from __future__ import annotations

import asyncio

from nanobot.agent.tools.apply_patch import ApplyPatchTool


def test_apply_patch_edits_replace(tmp_path):
    target = tmp_path / "calc.py"
    target.write_text("def add(a, b):\n    return a + b\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "calc.py",
                    "action": "replace",
                    "old_text": "    return a + b",
                    "new_text": "    return a - b",
                }
            ]
        )
    )

    assert "update calc.py" in result
    assert target.read_text() == "def add(a, b):\n    return a - b\n"


def test_apply_patch_edits_add_new_file(tmp_path):
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "config.py",
                    "action": "add",
                    "new_text": "DEBUG = True",
                }
            ]
        )
    )

    assert "add config.py" in result
    assert (tmp_path / "config.py").read_text() == "DEBUG = True\n"


def test_apply_patch_edits_preserves_new_file_trailing_blank_lines(tmp_path):
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "notes.txt",
                    "action": "add",
                    "new_text": "one\n\n",
                }
            ]
        )
    )

    assert "add notes.txt" in result
    assert (tmp_path / "notes.txt").read_text() == "one\n\n"


def test_apply_patch_edits_add_to_existing_file(tmp_path):
    target = tmp_path / "log.py"
    target.write_text("import logging\n\nlogger = logging.getLogger(__name__)\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "log.py",
                    "action": "add",
                    "new_text": "def debug(msg):\n    logger.debug(msg)",
                }
            ]
        )
    )

    assert "update log.py" in result
    assert (
        target.read_text()
        == "import logging\n\nlogger = logging.getLogger(__name__)\ndef debug(msg):\n    logger.debug(msg)\n"
    )


def test_apply_patch_edits_delete(tmp_path):
    target = tmp_path / "utils.py"
    target.write_text("def unused():\n    pass\ndef used():\n    return 1\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "utils.py",
                    "action": "delete",
                    "old_text": "def unused():\n    pass\n",
                }
            ]
        )
    )

    assert "update utils.py" in result
    assert target.read_text() == "def used():\n    return 1\n"


def test_apply_patch_edits_delete_entire_file(tmp_path):
    target = tmp_path / "obsolete.txt"
    target.write_text("remove me\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "obsolete.txt",
                    "action": "delete",
                    "old_text": "remove me\n",
                }
            ]
        )
    )

    assert "delete obsolete.txt" in result
    assert not target.exists()


def test_apply_patch_edits_delete_substring_with_surrounding_whitespace(tmp_path):
    target = tmp_path / "keep_whitespace.txt"
    target.write_text("  token  \n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "keep_whitespace.txt",
                    "action": "delete",
                    "old_text": "token",
                }
            ]
        )
    )

    assert "update keep_whitespace.txt" in result
    assert target.exists()
    assert target.read_text() == "    \n"


def test_apply_patch_edits_batch_multiple_files(tmp_path):
    a = tmp_path / "a.py"
    a.write_text("X = 1\n")
    b = tmp_path / "b.py"
    b.write_text("from a import X\nprint(X)\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "a.py",
                    "action": "replace",
                    "old_text": "X = 1",
                    "new_text": "Y = 1",
                },
                {
                    "path": "b.py",
                    "action": "replace",
                    "old_text": "from a import X",
                    "new_text": "from a import Y",
                },
            ]
        )
    )

    assert "update a.py" in result
    assert "update b.py" in result
    assert a.read_text() == "Y = 1\n"
    assert b.read_text() == "from a import Y\nprint(X)\n"


def test_apply_patch_edits_rejects_ambiguous_old_text(tmp_path):
    target = tmp_path / "repeated.txt"
    target.write_text("target\nmiddle\ntarget\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "repeated.txt",
                    "action": "replace",
                    "old_text": "target",
                    "new_text": "changed",
                }
            ]
        )
    )

    assert "old_text appears multiple times" in result
    assert target.read_text() == "target\nmiddle\ntarget\n"


def test_apply_patch_edits_dry_run_validates_without_writing(tmp_path):
    target = tmp_path / "dry.txt"
    target.write_text("before\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "dry.txt",
                    "action": "replace",
                    "old_text": "before",
                    "new_text": "after",
                },
                {
                    "path": "added.txt",
                    "action": "add",
                    "new_text": "new",
                },
            ],
            dry_run=True,
        )
    )

    assert "Patch dry-run succeeded" in result
    assert target.read_text() == "before\n"
    assert not (tmp_path / "added.txt").exists()


def test_apply_patch_edits_rejects_absolute_and_parent_paths(tmp_path):
    tool = ApplyPatchTool(workspace=tmp_path)

    absolute = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "/tmp/owned.txt",
                    "action": "add",
                    "new_text": "nope",
                }
            ]
        )
    )
    parent = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "../owned.txt",
                    "action": "add",
                    "new_text": "nope",
                }
            ]
        )
    )
    windows_absolute = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": r"C:\owned.txt",
                    "action": "add",
                    "new_text": "nope",
                }
            ]
        )
    )
    windows_parent = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": r"..\owned.txt",
                    "action": "add",
                    "new_text": "nope",
                }
            ]
        )
    )

    assert "must be relative" in absolute
    assert "must not contain '..'" in parent
    assert "must be relative" in windows_absolute
    assert "must not contain '..'" in windows_parent
    assert not (tmp_path.parent / "owned.txt").exists()


def test_apply_patch_edits_reports_invalid_edit_shapes(tmp_path):
    tool = ApplyPatchTool(workspace=tmp_path)

    missing_path = asyncio.run(tool.execute(edits=[{"action": "add", "new_text": "x"}]))
    missing_action = asyncio.run(tool.execute(edits=[{"path": "x.txt", "new_text": "x"}]))
    non_object = asyncio.run(tool.execute(edits=["not an object"]))  # type: ignore[list-item]

    assert "path required for edit" in missing_path
    assert "action required for edit: x.txt" in missing_action
    assert "each edit must be an object" in non_object


def test_apply_patch_edits_rolls_back_when_late_operation_fails(tmp_path):
    first = tmp_path / "first.txt"
    first.write_text("before\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "first.txt",
                    "action": "replace",
                    "old_text": "before",
                    "new_text": "after",
                },
                {
                    "path": "missing.txt",
                    "action": "delete",
                    "old_text": "remove me",
                },
            ]
        )
    )

    assert "file to update does not exist: missing.txt" in result
    assert first.read_text() == "before\n"


def test_apply_patch_replace_lines_single_line(tmp_path):
    target = tmp_path / "calc.py"
    target.write_text("def calc():\n    value = 1\n    return value\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "calc.py",
                    "action": "replace_lines",
                    "start_line": 2,
                    "new_text": "    value = 2",
                    "expected_old_text": "    value = 1",
                }
            ]
        )
    )

    assert "update calc.py" in result
    assert target.read_text() == "def calc():\n    value = 2\n    return value\n"


def test_apply_patch_replace_lines_range_with_multiple_new_lines(tmp_path):
    target = tmp_path / "service.py"
    target.write_text("def run():\n    old = True\n    return old\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "service.py",
                    "action": "replace_lines",
                    "start_line": 2,
                    "end_line": 3,
                    "new_text": "    value = compute()\n    return value",
                    "old_text": "    old = True\n    return old",
                }
            ]
        )
    )

    assert "update service.py" in result
    assert target.read_text() == "def run():\n    value = compute()\n    return value\n"


def test_apply_patch_insert_lines_before_and_after(tmp_path):
    target = tmp_path / "items.txt"
    target.write_text("one\ntwo")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "items.txt",
                    "action": "insert_lines",
                    "start_line": 1,
                    "position": "before",
                    "new_text": "zero",
                },
                {
                    "path": "items.txt",
                    "action": "insert_lines",
                    "start_line": 3,
                    "position": "after",
                    "new_text": "three",
                },
            ]
        )
    )

    assert "update items.txt" in result
    assert target.read_text() == "zero\none\ntwo\nthree\n"


def test_apply_patch_insert_lines_into_empty_file(tmp_path):
    target = tmp_path / "empty.txt"
    target.write_text("")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "empty.txt",
                    "action": "insert_lines",
                    "start_line": 1,
                    "new_text": "first",
                }
            ]
        )
    )

    assert "update empty.txt" in result
    assert target.read_text() == "first\n"


def test_apply_patch_delete_lines_with_guard(tmp_path):
    target = tmp_path / "cleanup.py"
    target.write_text("keep = 1\nremove = 2\nalso_remove = 3\nkeep = 4\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "cleanup.py",
                    "action": "delete_lines",
                    "start_line": 2,
                    "end_line": 3,
                    "expected_old_text": "remove = 2\nalso_remove = 3",
                }
            ]
        )
    )

    assert "update cleanup.py" in result
    assert target.read_text() == "keep = 1\nkeep = 4\n"


def test_apply_patch_line_edit_guard_prevents_wrong_line_change(tmp_path):
    target = tmp_path / "guard.py"
    target.write_text("alpha\nbeta\ngamma\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "guard.py",
                    "action": "replace_lines",
                    "start_line": 2,
                    "new_text": "changed",
                    "expected_old_text": "gamma",
                }
            ]
        )
    )

    assert "did not match expected_old_text" in result
    assert target.read_text() == "alpha\nbeta\ngamma\n"


def test_apply_patch_line_edits_preserve_crlf(tmp_path):
    target = tmp_path / "windows.txt"
    target.write_bytes(b"one\r\ntwo\r\nthree\r\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "windows.txt",
                    "action": "replace_lines",
                    "start_line": 2,
                    "new_text": "TWO",
                }
            ]
        )
    )

    assert "update windows.txt" in result
    assert target.read_bytes() == b"one\r\nTWO\r\nthree\r\n"


def test_apply_patch_line_edits_dry_run_without_writing(tmp_path):
    target = tmp_path / "dry_lines.txt"
    target.write_text("before\n")
    tool = ApplyPatchTool(workspace=tmp_path)

    result = asyncio.run(
        tool.execute(
            edits=[
                {
                    "path": "dry_lines.txt",
                    "action": "replace_lines",
                    "start_line": 1,
                    "new_text": "after",
                }
            ],
            dry_run=True,
        )
    )

    assert "Patch dry-run succeeded" in result
    assert target.read_text() == "before\n"
