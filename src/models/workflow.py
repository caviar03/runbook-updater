from typing import Optional
from typing_extensions import TypedDict

from .code_review import CodeChangeReview
from .runbook_review import runbookReview
from .change_proposal import changeProposal
from .orchestrator_decision import orchestratorDecision

class workflowState(TypedDict):

    old_code: str
    diff: str
    runbook_path: str


    code_review: Optional[CodeChangeReview]
    runbook_review: Optional[runbookReview]
    runbook_review1: Optional[runbookReview]
    runbook_review2: Optional[runbookReview]

    orchestrator_decision: Optional[orchestratorDecision]
    orchestrator_feedback: str

    change_proposal: Optional[changeProposal]
    approved_changes: Optional[changeProposal]

    updated_runbook: str

    analysis_attempts: int