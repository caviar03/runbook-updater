old_code = get_file_at_commit(
    owner="caviar03",
    repo="your-repo",
    path="src/lib/tracking.ts",
    commit_sha="OLD_COMMIT_SHA",
)

current_code = get_file_at_commit(
    owner="caviar03",
    repo="your-repo",
    path="src/lib/tracking.ts",
    commit_sha="NEW_COMMIT_SHA",
)