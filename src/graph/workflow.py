from langgraph.graph import StateGraph, START, END

from src.models.workflow import workflowState
from src.graph.nodes import (
    analysis_start_node, change_proposal_node, code_reviewer_node, failed_node,
    human_approval_node, implementor_node, no_update_node,
    orchestrator_review_node, orchestrator_start_node,
    runbook_analyzer1_node, runbook_analyzer2_node, runbook_decision_reviewer_node,
)
from src.graph.routing import route_after_human, route_after_orchestrator, route_after_proposal


def build_workflow():
    workflow = StateGraph(workflowState)
    for name, node in {
        "orchestrator_start": orchestrator_start_node,
        "code_reviewer": code_reviewer_node,
        "analysis_start": analysis_start_node,
        "runbook_analyzer1": runbook_analyzer1_node,
        "runbook_analyzer2": runbook_analyzer2_node,
        "runbook_decision_reviewer": runbook_decision_reviewer_node,
        "orchestrator_review": orchestrator_review_node,
        "change_proposal": change_proposal_node,
        "human_approval": human_approval_node,
        "implementor": implementor_node,
        "no_update": no_update_node,
        "failed": failed_node,
    }.items():
        workflow.add_node(name, node)
    workflow.add_edge(START, "orchestrator_start")
    workflow.add_edge("orchestrator_start", "code_reviewer")
    workflow.add_edge("code_reviewer", "analysis_start")
    workflow.add_edge("analysis_start", "runbook_analyzer1")
    workflow.add_edge("analysis_start", "runbook_analyzer2")
    workflow.add_edge(["runbook_analyzer1", "runbook_analyzer2"], "runbook_decision_reviewer")
    workflow.add_edge("runbook_decision_reviewer", "orchestrator_review")
    workflow.add_conditional_edges("orchestrator_review", route_after_orchestrator, {
        "proceed": "change_proposal", "rework": "analysis_start", "no_update": "no_update", "failed": "failed",
    })
    workflow.add_conditional_edges("change_proposal", route_after_proposal, {"review": "human_approval", "no_update": "no_update"})
    workflow.add_conditional_edges("human_approval", route_after_human, {
        "waiting": END, "approved": "implementor", "rejected": END, "rework": "analysis_start", "failed": "failed",
    })
    for name in ["implementor", "no_update", "failed"]:
        workflow.add_edge(name, END)
    return workflow.compile()
