from langgraph.graph import StateGraph, START, END

from src.graph.nodes import change_proposal_node, code_reviewer_node, human_approval_node, implementor_node, orchestrator_review_node, orchestrator_start_node, runbook_analyzer1_node, runbook_analyzer2_node, runbook_decision_reviewer_node
from src.graph.routing import route_after_human, route_after_orchestrator, route_after_proposal
from src.models.workflow import workflowState


def build_workflow():

    workflow = StateGraph(workflowState)

    workflow.add_node("orchestrator_start", orchestrator_start_node)

    workflow.add_node("code_reviewer", code_reviewer_node)

    workflow.add_node("runbook_analyzer1", runbook_analyzer1_node)

    workflow.add_node("runbook_analyzer2", runbook_analyzer2_node)

    workflow.add_node("runbook_decision_reviewer", runbook_decision_reviewer_node)

    workflow.add_node("orchestrator_review",orchestrator_review_node)

    workflow.add_node("change_proposal", change_proposal_node)

    workflow.add_node("human_approval", human_approval_node)

    workflow.add_node("implementor", implementor_node)

    workflow.add_edge(START, "orchestrator_start")

    workflow.add_edge("orchestrator_start", "code_reviewer")

    workflow.add_edge("code_reviewer", "runbook_analyzer1")

    workflow.add_edge("code_reviewer", "runbook_analyzer2")  

    workflow.add_edge("runbook_analyzer1","runbook_decision_reviewer") 

    workflow.add_edge("runbook_analyzer2","runbook_decision_reviewer") 

    workflow.add_edge("runbook_decision_reviewer", "orchestrator_review")

    workflow.add_conditional_edges( "orchestrator_review",route_after_orchestrator,
       {
        "proceed": "change_proposal",
        "rework": "runbook_analyzer1" #just a temp routing
       }
      )

    workflow.add_conditional_edges("change_proposal", route_after_proposal,
      {
        "has_changes": "human_approval",
        "no_changes": END
      }
     )

    workflow.add_conditional_edges("human_approval", route_after_human,
      {
        "approved": "implementor",
        "rejected": END
      }
     )

    workflow.add_edge("implementor", END)
    return workflow.compile()