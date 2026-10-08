import pytest

from src.github.snapshot import code_from_snapshot


def file(status="modified", patch="@@ -1 +1 @@\n-old\n+new\n", original="new\n", current="new\n", additions=1, deletions=1):
    return {"file_path": "worker.py", "previous_file_path": "before.py", "status": status,
            "patch": patch, "pr_head_content": original, "merged_content": current,
            "additions": additions, "deletions": deletions}


@pytest.mark.parametrize("entry,old", [
    (file(current="new\n# merge/rebase context\n"), "old\n"),
    (file(status="added", patch="@@ -0,0 +1 @@\n+new\n", deletions=0), ""),
    (file(status="removed", patch="@@ -1 +0,0 @@\n-old\n", original="", current="", additions=0), "old\n"),
    (file(status="renamed", patch="", additions=0, deletions=0), "new\n"),
    (file(patch="@@ -1 +1 @@\n-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file", original="new", current="new"), "old"),
    (file(original=None, current=None, patch="", additions=0, deletions=0), None),
    (file(status="removed", original=None, current="", patch="", additions=0, deletions=0), None),
])
def test_offline_snapshot_recovers_complete_saved_pr_changes(entry, old):
    result = code_from_snapshot({"files": [entry]})
    change = result["changed_files"][0]
    assert change["old_code"] == old and change["current_code"] == entry["merged_content"]
    assert change["previous_file_path"] == "before.py"
    assert change["is_binary"] is (old is None)


@pytest.mark.parametrize("entry", [
    file(patch=""), file(original="does not match\n"),
    file(patch="@@ -1 +1 @@\n-old\n"),
    file(status="removed", original=None, current="", patch="", additions=0),
    file(status="added"),
])
def test_offline_snapshot_refuses_incomplete_or_inconsistent_evidence(entry):
    with pytest.raises(ValueError):
        code_from_snapshot({"files": [entry]})
