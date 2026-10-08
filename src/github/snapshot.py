"""Offline code comparison from the App's authenticated immutable snapshot."""

from src.github.patch import _restore_old_code


def code_from_snapshot(snapshot):
    changed_files = []
    for file in snapshot["files"]:
        path, status = file["file_path"], file["status"]
        original, current, patch = file["pr_head_content"], file["merged_content"], file["patch"]
        binary = original is None or current is None
        if status == "removed" and not patch and file["deletions"]:
            raise ValueError(f"Missing saved deletion patch for {path}")
        if binary:
            old = None
            patch = "[Binary/non-UTF-8 change: contents are not available as code text.]"
        elif not patch and file["additions"] + file["deletions"] == 0:
            old = "" if status == "added" else original
        else:
            if not patch:
                raise ValueError(f"Missing saved PR patch for {path}")
            edits = sum(line.startswith(("+", "-")) for line in patch.splitlines())
            if edits != file["additions"] + file["deletions"]:
                raise ValueError(f"Truncated saved PR patch for {path}")
            old = _restore_old_code(original, patch)
            if status == "added" and old:
                raise ValueError(f"Added file has nonempty previous content: {path}")
        changed_files.append({"file_path": path, "previous_file_path": file["previous_file_path"],
                              "status": status, "old_code": old, "current_code": current,
                              "diff": patch, "is_binary": binary})

    def combine(key):
        return "\n\n".join(f"FILE: {file['file_path']} ({file['status']})\n{file[key] if file[key] is not None else '[Binary/non-UTF-8 file]'}" for file in changed_files)

    return {"changed_files": changed_files, "old_code": combine("old_code"),
            "current_code": combine("current_code"), "code_diff": combine("diff")}
