from src.graph.workflow import build_workflow
from src.github.merge import get_merge_code
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

    initial_state = {
        "old_code": code_data["old_code"],
        "current_code": code_data["current_code"],
        "code_diff": code_data["diff"],

        "runbook_path": (
            "test_data/input/"
            "Kartly Order Tracking Service_System Admin Operating Manual "
            "(Runbook)_v1.0.docx"
        ),

        "code_review": None,

        "runbook_review1": None,
        "runbook_review2": None,
        "runbook_review": None,

        "orchestrator_decision": None,
        "orchestrator_feedback": "",

        "change_proposal": None,
        "approved_changes": None,

        "updated_runbook_path": "",

        "analysis_attempts": 0,
    }

    result = app.invoke(initial_state)

    print("\nWORKFLOW COMPLETE")
    print(result)


if __name__ == "__main__":
    main()