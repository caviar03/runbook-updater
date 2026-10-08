import logging

from src.agents.code_reviewer import code_reviewer
from src.agents.implementor import implementor
from src.agents.runbook_analyzer1 import runbook_analyzer1
from src.agents.runbook_analyzer2 import runbook_analyzer2
from src.agents.runbook_decision_reviewer import runbook_decision_reviewer
from src.agents.change_proposer import create_change_proposal
from src.agents.orchestrator import orchestrator_review
from src.agents.necessity_scorer import score_issues
from src.models.orchestrator_decision import orchestratorDecision
from src.models.workflow import workflowState

logger = logging.getLogger(__name__)


def orchestrator_start_node(state: workflowState):
    print("ORCHESTRATOR: starting code/runbook review")
    return {"workflow_status": "analyzing", "approved_changes": None, "updated_runbook_path": ""}


def analysis_start_node(state: workflowState):
    return {"analysis_attempts": state.get("analysis_attempts", 0) + 1}


def code_reviewer_node(state: workflowState):
    review = code_reviewer(old_code=state["old_code"], code_diff=state["code_diff"])
    return {"code_review": review}


def runbook_analyzer1_node(state: workflowState):
    direct = {"runbook_text": state["runbook_text"]} if "runbook_text" in state else {}
    review = runbook_analyzer1(code_review=state["code_review"], feedback=state.get("orchestrator_feedback", ""), **direct)
    return {"runbook_review1": review}


def runbook_analyzer2_node(state: workflowState):
    direct = {"runbook_text": state["runbook_text"]} if "runbook_text" in state else {}
    review = runbook_analyzer2(code_review=state["code_review"], feedback=state.get("orchestrator_feedback", ""), **direct)
    return {"runbook_review2": review}


def runbook_decision_reviewer_node(state: workflowState):
    review = runbook_decision_reviewer(
        code_review=state["code_review"], runbook_analysis1=state["runbook_review1"],
        runbook_analysis2=state["runbook_review2"],
    )
    return {"runbook_review": review}


def orchestrator_review_node(state: workflowState):
    if not state["runbook_review"].update_required:
        decision = orchestratorDecision(proceed=True, reasoning="No runbook update is required.", feedback="")
    else:
        decision = orchestrator_review(code_review=state["code_review"], runbook_review=state["runbook_review"])
    return {"orchestrator_decision": decision, "orchestrator_feedback": decision.feedback}


def necessity_scorer_node(state: workflowState):
    issues = state["runbook_review"].issues
    try:
        scores = score_issues(issues)
    except Exception:
        # Scores are only shown to the reviewer, so a missing model or package must not fail the run.
        logger.exception("Necessity scoring failed; continuing without scores")
        return {"issue_scores": []}
    issue_scores = [{"section": issue.section, "issue": issue.issue, "score": score} for issue, score in zip(issues, scores)]
    # Scores are informational for the reviewer; every issue still goes to change proposal.
    return {"issue_scores": issue_scores}


def change_proposal_node(state: workflowState):
    direct = {"runbook_text": state["runbook_text"]} if "runbook_text" in state else {}
    return {"change_proposal": create_change_proposal(runbook_review=state["runbook_review"], **direct)}


def no_update_node(state: workflowState):
    return {"workflow_status": "no_update_needed", "approved_changes": None}


def failed_node(state: workflowState):
    error = "Analysis did not converge within the attempt limit."
    if state.get("orchestrator_feedback"):
        error += f" Last feedback: {state['orchestrator_feedback']}"
    return {"workflow_status": "failed", "approved_changes": None, "error": error}


def human_approval_node(state: workflowState):
    proposal = state["change_proposal"]
    if state.get("review_only"):
        return {"approved_changes": None, "workflow_status": "awaiting_decision"}
    print("RUNBOOK CHANGE PROPOSAL")
    print(proposal.readable_feedback)
    print(f"Documents: {state.get('runbook_paths') or [state.get('runbook_path')]}")
    if state.get("issue_scores"):
        print("\nIssue necessity scores:")
        for entry in state["issue_scores"]:
            print(f"  {entry['score']:.2f} [{entry['section']}] {entry['issue']}")
    for i, change in enumerate(proposal.changes, 1):
        print(f"\nCHANGE {i}\nRunbook: {change.runbook}\nSection: {change.section}\nCURRENT:\n{change.current_text}\nPROPOSED:\n{change.proposed_text}\nREASON:\n{change.reason}")
    while True:
        decision = input("Approve these changes? (yes/no/edit): ").strip().lower()
        if decision == "yes":
            return {"approved_changes": proposal, "human_feedback": "Approved", "workflow_status": "approved"}
        if decision == "no":
            return {"approved_changes": None, "human_feedback": "Rejected", "workflow_status": "rejected"}
        if decision == "edit":
            feedback = input("Enter your feedback: ").strip()
            if feedback:
                return {"approved_changes": None, "human_feedback": feedback, "orchestrator_feedback": feedback, "workflow_status": "rework"}
        print("Enter yes, no, or edit (with nonempty feedback).")


def implementor_node(state: workflowState):
    if state.get("runbook_paths"):
        updated_paths = implementor(
            runbook_paths=state["runbook_paths"], approved_changes=state["approved_changes"],
            output_dir=state.get("output_dir", "test_data/output"),
        )
        return {"updated_runbook_paths": updated_paths, "workflow_status": "applied"}
    updated_path = implementor(
        runbook_path=state["runbook_path"], approved_changes=state["approved_changes"],
        output_path=state["output_path"],
    )
    return {"updated_runbook_path": updated_path, "workflow_status": "applied"}
