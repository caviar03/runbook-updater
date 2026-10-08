import difflib
from src.github.patch import _restore_old_code

from src.github.repo import (
    get_commit, get_compare, get_file_at_commit,
    get_pull_request, get_pull_request_files,
)


def get_merge_code(owner: str, repo: str, merge_commit_sha: str, pull_request_number: int | None = None):
    merge_commit = get_commit(owner, repo, merge_commit_sha)
    parents = merge_commit.get("parents", [])
    if not parents:
        raise ValueError("The merged commit has no previous commit to compare")
    old_commit_sha = parents[0]["sha"]
    source_head = None
    if pull_request_number is not None:
        pr = get_pull_request(owner, repo, pull_request_number)
        if not pr.get("merged") or pr.get("merge_commit_sha") != merge_commit_sha:
            raise ValueError("PR is not merged at the supplied merge commit")
        if pr.get("changed_files", 0) > 3000:
            raise ValueError("PR exceeds GitHub's complete file-list limit")
        source_head = pr["head"]["sha"]
        files = get_pull_request_files(owner, repo, pull_request_number)
    else:
        files = get_compare(owner, repo, old_commit_sha, merge_commit_sha).get("files", [])

    changed_files = []
    for file in files:
        path = file["filename"]
        status = file["status"]
        old_path = file.get("previous_filename", path)
        current = "" if status == "removed" else get_file_at_commit(owner, repo, path, merge_commit_sha)
        patch = file.get("patch", "")
        if source_head:
            original = "" if status == "removed" else get_file_at_commit(owner, repo, path, source_head)
            if status == "added":
                old = ""
            elif original is None:
                old = None
            elif not patch and status == "renamed" and not file.get("changes", 0):
                old = original
            else:
                if not patch:
                    raise ValueError(f"No complete saved PR text patch for {path}")
                edits = sum(line.startswith(("+", "-")) for line in patch.splitlines())
                if "additions" in file and "deletions" in file and edits != file["additions"] + file["deletions"]:
                    raise ValueError(f"Truncated saved PR patch for {path}")
                old = _restore_old_code(original, patch)
        else:
            old = "" if status == "added" else get_file_at_commit(owner, repo, old_path, old_commit_sha)
        binary = old is None or current is None
        if binary:
            patch = "[Binary/non-UTF-8 change: contents are not available as code text.]"
        elif not patch and old != current:
            patch = "".join(difflib.unified_diff(old.splitlines(keepends=True), current.splitlines(keepends=True), fromfile=old_path, tofile=path))
        changed_files.append({"file_path": path, "previous_file_path": old_path, "status": status, "old_code": old, "current_code": current, "diff": patch, "is_binary": binary})

    def combine(key):
        return "\n\n".join(f"FILE: {file['file_path']} ({file['status']})\n{file[key] if file[key] is not None else '[Binary/non-UTF-8 file]'}" for file in changed_files)

    return {
        "old_commit": old_commit_sha, "current_commit": merge_commit_sha,
        "changed_files": changed_files, "old_code": combine("old_code"),
        "current_code": combine("current_code"), "code_diff": combine("diff"),
    }
