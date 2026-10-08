from src.models.workflow import workflowState


def route_after_orchestrator(state: workflowState):
    if not state["runbook_review"].update_required:
        return "no_update"
    if state["orchestrator_decision"].proceed:
        return "proceed"
    if state.get("analysis_attempts", 0) >= state.get("max_analysis_attempts", 3):
        return "failed"
    return "rework"


def route_after_proposal(state: workflowState):
    proposal = state.get("change_proposal")
    return "review" if proposal and proposal.changes else "no_update"


def route_after_human(state: workflowState):
    if state.get("workflow_status") == "awaiting_decision":
        return "waiting"
    if state["approved_changes"] is not None:
        return "approved"
    if state.get("workflow_status") == "rework":
        if state.get("analysis_attempts", 0) >= state.get("max_analysis_attempts", 3):
            return "failed"
        return "rework"
    return "rejected"
