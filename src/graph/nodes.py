from src.agents.code_reviewer import code_reviewer
from src.agents.implementor import implementor
from src.agents.runbook_analyzer1 import runbook_analyzer1
from src.agents.runbook_analyzer2 import runbook_analyzer2
from src.agents.runbook_decision_reviewer import runbook_decision_reviewer
from src.agents.change_proposer import create_change_proposal
from src.agents.orchestrator import orchestrator_review
from src.models.workflow import workflowState


def orchestrator_start_node(state: workflowState):
    print("ORCHESTRATOR: starting code/runbook review")
    return {}

def orchestrator_review_node(state: workflowState):
    decision = orchestrator_review( code_review=state["code_review"], runbook_review=state["runbook_review"])
    return { "orchestrator_decision": decision,"orchestrator_feedback": decision.feedback}

def code_reviewer_node(state: workflowState):
    review = code_reviewer(old_code=state["old_code"], code_diff=state["code_diff"])
    return {"code_review": review}

def runbook_analyzer1_node(state: workflowState):
    feedback = state.get("orchestrator_feedback", "")
    review = runbook_analyzer1(code_review=state["code_review"], feedback=feedback)
    return { "runbook_review1": review}

def runbook_analyzer2_node(state: workflowState):
    feedback = state.get("orchestrator_feedback","")
    review = runbook_analyzer2(code_review=state["code_review"], feedback=feedback)
    return { "runbook_review2": review}

def runbook_decision_reviewer_node(state: workflowState):
    final_review = runbook_decision_reviewer(code_review=state["code_review"],runbook_analysis1=state["runbook_review1"], runbook_analysis2=state["runbook_review2"])
    return {"runbook_review": final_review}

def change_proposal_node(state: workflowState):
    proposal = create_change_proposal(runbook_review=state["runbook_review"])
    return { "change_proposal": proposal }

def human_approval_node(state: workflowState):

    proposal = state["change_proposal"]

    print("=" * 60)
    print("RUNBOOK CHANGE PROPOSAL")
    print("=" * 60)

    print(proposal.readable_feedback)

    for i, change in enumerate(proposal.changes, 1):
        print(f"\nCHANGE {i}")
        print(f"Runbook: {change.runbook}")
        print(f"Section: {change.section}")
        print("\nCURRENT:")
        print(change.current_text)
        print("\nPROPOSED:")
        print(change.proposed_text)
        print("\nREASON:")
        print(change.reason)

    print("\n" + "=" * 60)

    decision = input(
        "Approve these changes? (yes/no): "
    ).strip().lower()

    if decision == "yes":
        return {"approved_changes": proposal}

    return {"approved_changes": None}

def implementor_node(state: workflowState):

    updated_paths = implementor(
        runbook_paths=state["runbook_paths"],
        approved_changes=state["approved_changes"],
        output_dir="test_data/output",
    )

    return {
        "updated_runbook_paths": updated_paths
    }