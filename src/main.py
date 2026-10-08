from src.graph.workflow import build_workflow
from src.github.merge import get_merge_code
from src.retrieval.index_runbooks import index_runbooks
import os


def main():

    app = build_workflow()

    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]

    # For now, supply the merge commit SHA manually.
    # Later, GitHub will provide this automatically after a merge.
    merge_commit_sha = "YOUR_MERGE_COMMIT_SHA"

    code_data = get_merge_code(
        owner=owner,
        repo=repo,
        merge_commit_sha=merge_commit_sha,
    )

    changed_files = code_data["changed_files"]

    old_code = "\n\n".join(
        f"# File: {file['file_path']}\n{file['old_code']}"
        for file in changed_files
    )

    code_diff = "\n\n".join(
        f"# File: {file['file_path']} ({file['status']})\n{file['diff']}"
        for file in changed_files
    )

    runbook_paths = [
        "test_data/input/Kartly Order Tracking Service_System Admin Operating Manual (Runbook)_v1.0.docx",
        "test_data/input/Kartly Payments Service_System Admin Operating Manual (Runbook)_v1.0.docx",
        "test_data/input/Kartly Search & Discovery Service_System Admin Operating Manual (Runbook)_v1.0.docx",
    ]

    # The agents only see runbook content through Qdrant retrieval,
    # so index the current runbooks before the workflow starts.
    index_runbooks(runbook_paths)

    initial_state = {
        "old_code": old_code,
        "code_diff": code_diff,
        "runbook_paths": runbook_paths,
    }

    result = app.invoke(initial_state)

    print("\nWORKFLOW COMPLETE")
    print(result)


if __name__ == "__main__":
    main()