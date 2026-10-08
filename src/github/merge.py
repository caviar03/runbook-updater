def get_merge_code(
    owner: str,
    repo: str,
    merge_commit_sha: str,
):
    merge_commit = get_commit(owner, repo, merge_commit_sha)

    old_commit_sha = merge_commit["parents"][0]["sha"]

    comparison = get_compare(
        owner,
        repo,
        old_commit_sha,
        merge_commit_sha,
    )

    changed_files = []

    for file in comparison.get("files", []):
        file_path = file["filename"]

        changed_files.append({
            "file_path": file_path,
            "status": file["status"],
            "old_code": get_file_at_commit(
                owner,
                repo,
                file_path,
                old_commit_sha,
            ),
            "current_code": get_file_at_commit(
                owner,
                repo,
                file_path,
                merge_commit_sha,
            ),
            "diff": file.get("patch", ""),
        })

    return {
        "old_commit": old_commit_sha,
        "current_commit": merge_commit_sha,
        "changed_files": changed_files,
    }