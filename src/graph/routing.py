from src.models.workflow import workflowState


def route_after_proposal(state: workflowState):
    proposal = state["change_proposal"]

    if proposal is None or not proposal.changes:
        print("CHANGE PROPOSAL: no runbook changes required")
        return "no_changes"
    return "has_changes"

def route_after_human(state: workflowState):
    if state["approved_changes"] is not None:
        return "approved"
    return "rejected"

def route_after_orchestrator(state: workflowState):
    decision = state["orchestrator_decision"]

    if decision.proceed:
        return "proceed"
    return "rework"