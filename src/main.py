import os
import json
from pathlib import Path

from dotenv import load_dotenv

from src.github.merge import get_merge_code
from src.graph.workflow import build_workflow
from src.graph.state import make_initial_state


def main():
    load_dotenv()
    merge_sha = os.environ.get("GITHUB_MERGE_COMMIT_SHA", "")
    if not merge_sha or merge_sha == "YOUR_MERGE_COMMIT_SHA":
        raise ValueError("Set GITHUB_MERGE_COMMIT_SHA to a real merged commit")
    number = os.environ.get("GITHUB_PR_NUMBER")
    if not number or not number.isdigit() or int(number) < 1:
        raise ValueError("Set GITHUB_PR_NUMBER to the merged PR number")
    code_data = get_merge_code(os.environ["GITHUB_OWNER"], os.environ["GITHUB_REPO"], merge_sha, pull_request_number=int(number))
    configured = os.environ.get("RUNBOOK_PATHS")
    runbook_paths = json.loads(configured) if configured else [str(path) for path in sorted(Path("test_data/input").glob("*.docx"))]
    if not isinstance(runbook_paths, list) or not runbook_paths or any(not isinstance(path, str) or not Path(path).is_file() for path in runbook_paths):
        raise ValueError("RUNBOOK_PATHS must be a JSON array of existing runbook files")
    # The multi-runbook CLI indexes current documents; HTTP jobs bypass retrieval.
    from src.retrieval.index_runbooks import index_runbooks
    index_runbooks(runbook_paths)
    initial_state = make_initial_state(code_data, runbook_paths, os.environ.get("RUNBOOK_OUTPUT_DIR"))
    result = build_workflow().invoke(initial_state, {"recursion_limit": 50})
    print("\nWORKFLOW COMPLETE")
    print(result)


if __name__ == "__main__":
    main()
