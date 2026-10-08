import base64
from unittest.mock import Mock

import pytest

from src.github import merge, repo


def setup_merge(monkeypatch, files, contents):
    monkeypatch.setattr(merge, "get_commit", lambda *args: {"parents": [{"sha": "before"}]})
    monkeypatch.setattr(merge, "get_compare", lambda *args: {"files": files})
    reads = []
    def read(owner, repository, path, sha):
        reads.append((path, sha))
        return contents[(path, sha)]
    monkeypatch.setattr(merge, "get_file_at_commit", read)
    return reads


def test_imports_and_multi_file_output_match_workflow_inputs(monkeypatch):
    setup_merge(monkeypatch, [{"filename": "a.py", "status": "modified"}, {"filename": "b.py", "status": "modified"}], {
        ("a.py", "before"): "a = 1\n", ("a.py", "merged"): "a = 2\n",
        ("b.py", "before"): "b = 3\n", ("b.py", "merged"): "b = 4\n",
    })
    result = merge.get_merge_code("owner", "repo", "merged")
    assert len(result["changed_files"]) == 2
    assert "a = 1" in result["old_code"] and "b = 3" in result["old_code"]
    assert "a = 2" in result["current_code"] and "b = 4" in result["current_code"]
    assert "-a = 1" in result["code_diff"] and "+b = 4" in result["code_diff"]


def test_added_removed_renamed_and_binary_files_use_existing_revisions(monkeypatch):
    reads = setup_merge(monkeypatch, [
        {"filename": "new.py", "status": "added"},
        {"filename": "gone.py", "status": "removed"},
        {"filename": "after.py", "previous_filename": "before.py", "status": "renamed"},
        {"filename": "image.png", "status": "modified"},
    ], {
        ("new.py", "merged"): "new\n", ("gone.py", "before"): "gone\n",
        ("before.py", "before"): "same\n", ("after.py", "merged"): "same\n",
        ("image.png", "before"): None, ("image.png", "merged"): None,
    })
    result = merge.get_merge_code("owner", "repo", "merged")
    assert ("new.py", "before") not in reads
    assert ("gone.py", "merged") not in reads
    assert ("before.py", "before") in reads
    assert result["changed_files"][-1]["is_binary"] is True


@pytest.mark.parametrize("current,patch,expected", [
    ("a\nnew\nz\n", "@@ -1,3 +1,3 @@\n a\n-old\n+new\n z", "a\nold\nz\n"),
    ("first\nkeep\nlast\n", "@@ -1 +1 @@\n-before\n+first\n@@ -3 +3 @@\n-after\n+last", "before\nkeep\nafter\n"),
    ("", "@@ -1,2 +0,0 @@\n-one\n-two", "one\ntwo\n"),
    ("new", "@@ -1 +1 @@\n-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file", "old"),
])
def test_saved_patch_restores_original_code_across_hunks(current, patch, expected):
    assert merge._restore_old_code(current, patch) == expected


def test_saved_pr_diff_covers_all_changes_in_a_rebase_merge(monkeypatch):
    files = [
        {"filename": "first.py", "status": "modified", "additions": 1, "deletions": 1, "patch": "@@ -1 +1 @@\n-old first\n+new first"},
        {"filename": "last.py", "status": "modified", "additions": 1, "deletions": 1, "patch": "@@ -1 +1 @@\n-old last\n+new last"},
    ]
    reads = setup_merge(monkeypatch, [], {
        ("first.py", "original-head"): "new first\n", ("first.py", "merged"): "new first\n",
        ("last.py", "original-head"): "new last\n", ("last.py", "merged"): "new last\n",
    })
    monkeypatch.setattr(merge, "get_pull_request", lambda *args: {"merged": True, "merge_commit_sha": "merged", "head": {"sha": "original-head"}})
    monkeypatch.setattr(merge, "get_pull_request_files", lambda *args: files)
    result = merge.get_merge_code("owner", "repo", "merged", pull_request_number=42)
    assert "old first" in result["old_code"] and "old last" in result["old_code"]
    assert not any(sha == "before" for _, sha in reads)


def test_unmerged_or_mismatched_pr_is_rejected(monkeypatch):
    setup_merge(monkeypatch, [], {})
    monkeypatch.setattr(merge, "get_pull_request", lambda *args: {"merged": False})
    with pytest.raises(ValueError, match="not merged"):
        merge.get_merge_code("owner", "repo", "merged", pull_request_number=42)


@pytest.mark.parametrize("patch", ["", "@@ -1,2 +1,2 @@\n-old\n+new", "@@ -1 +1 @@\n-old\n+different"])
def test_incomplete_patch_cannot_supply_misleading_old_code(patch):
    with pytest.raises(ValueError):
        merge._restore_old_code("new\n", patch)


def test_file_reader_encodes_paths_sets_timeout_and_marks_binary(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-only")
    response = Mock()
    response.json.return_value = {"encoding": "base64", "content": base64.b64encode(b"\xff\x00").decode()}
    request = Mock(return_value=response)
    monkeypatch.setattr(repo.requests, "get", request)
    assert repo.get_file_at_commit("owner", "repo", "a #b/file.py", "sha") is None
    assert request.call_args.args[0].endswith("/contents/a%20%23b/file.py")
    assert request.call_args.kwargs["timeout"] == 30
    assert request.call_args.kwargs["params"] == {"ref": "sha"}


def test_pr_file_reader_paginates(monkeypatch):
    batches = iter([[{"filename": str(i)} for i in range(100)], [{"filename": "last"}]])
    read = Mock(side_effect=lambda *args, **kwargs: next(batches))
    monkeypatch.setattr(repo, "_get", read)
    assert len(repo.get_pull_request_files("owner", "repo", 42)) == 101
    assert read.call_args_list[1].kwargs["params"]["page"] == 2

