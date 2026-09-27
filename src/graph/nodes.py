from src.agents.code_reviewer import code_reviewer
from src.agents.implementor import implementor
from src.agents.runbook_analyzer import runbook_analyzer
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
    review = code_reviewer(old_code=state["old_code"], current_code=state["current_code"], runbook=state["runbook"])
    return {"code_review": review}

def runbook_analyzer_node(state: workflowState):
    feedback = state.get("orchestrator_feedback", "")
    review = runbook_analyzer(code_review=state["code_review"],runbook=state["runbook"])
    return { "runbook_review": review}

def change_proposal_node(state: workflowState):
    proposal = create_change_proposal(runbook=state["runbook"], runbook_review=state["runbook_review"])
    return { "change_proposal": proposal }

def human_approval_node(state: workflowState):

    proposal = state["change_proposal"]

    print("=" * 60)
    print("RUNBOOK CHANGE PROPOSAL")
    print("=" * 60)

    print(proposal.readable_feedback)

    for i, change in enumerate(proposal.changes, 1):
        print(f"\nCHANGE {i}")
        print(f"Section: {change.section}")
        print("\nCURRENT:")
        print(change.current_text)
        print("\nPROPOSED:")
        print(change.proposed_text)
        print("\nREASON:")
        print(change.reason)

    print("\n" + "=" * 60)

    decision = input(
        "Approve these changes? (yes/no/edit): "
    ).strip().lower()

    if decision == "yes":
        return {
            "approved_changes": proposal,
            "human_feedback": "Approved"
        }

    if decision == "no":
        return {
            "approved_changes": None,
            "human_feedback": "Rejected"
        }

    feedback = input("Enter your feedback: ")

    return {
        "approved_changes": None,
        "human_feedback": feedback
    }

def implementor_node(state: workflowState):
    updated_runbook = implementor(
        runbook=state["runbook"],
        approved_changes=state["approved_changes"]
    )
    return {
        "updated_runbook": updated_runbook
    }