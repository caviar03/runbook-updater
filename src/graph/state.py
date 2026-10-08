"""Construct workflow inputs for CLI and offline HTTP jobs."""

from pathlib import Path


def make_initial_state(code_data, runbook_path, output_path=None):
    path = Path(runbook_path)
    return {
        "old_code": code_data["old_code"],
        "current_code": code_data["current_code"],
        "code_diff": code_data["code_diff"],
        "changed_files": code_data["changed_files"],
        "runbook_path": str(path),
        "output_path": str(output_path or path.with_name(f"{path.stem}.updated{path.suffix}")),
        "code_review": None, "runbook_review1": None, "runbook_review2": None,
        "runbook_review": None, "orchestrator_decision": None, "orchestrator_feedback": "",
        "change_proposal": None, "approved_changes": None, "human_feedback": "",
        "updated_runbook_path": "", "analysis_attempts": 0, "max_analysis_attempts": 3,
        "workflow_status": "analyzing", "error": "",
    }


