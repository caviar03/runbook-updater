from src.models.workflow import workflowState


def route_after_human(state: workflowState):
    if state["approved_changes"] is not None:
        return "approved"
    return "rejected"

def route_after_orchestrator(state: workflowState):
    decision = state["orchestrator_decision"]

    if decision.proceed:
        return "proceed"
    return "rework"