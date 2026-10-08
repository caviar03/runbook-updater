import os

from dotenv import load_dotenv

from src.github.merge import get_merge_code
from src.graph.workflow import build_workflow
from src.graph.state import make_initial_state


DEFAULT_RUNBOOK = "test_data/input/Kartly Order Tracking Service_System Admin Operating Manual (Runbook)_v1.0.docx"


def main():
    load_dotenv()
    merge_sha = os.environ.get("GITHUB_MERGE_COMMIT_SHA", "")
    if not merge_sha or merge_sha == "YOUR_MERGE_COMMIT_SHA":
        raise ValueError("Set GITHUB_MERGE_COMMIT_SHA to a real merged commit")
    number = os.environ.get("GITHUB_PR_NUMBER")
    if not number or not number.isdigit() or int(number) < 1:
        raise ValueError("Set GITHUB_PR_NUMBER to the merged PR number")
    code_data = get_merge_code(os.environ["GITHUB_OWNER"], os.environ["GITHUB_REPO"], merge_sha, pull_request_number=int(number))
    initial_state = make_initial_state(code_data, os.environ.get("RUNBOOK_PATH", DEFAULT_RUNBOOK), os.environ.get("RUNBOOK_OUTPUT_PATH"))
    result = build_workflow().invoke(initial_state, {"recursion_limit": 50})
    print("\nWORKFLOW COMPLETE")
    print(result)


if __name__ == "__main__":
    main()
