from typing import Optional
from typing_extensions import TypedDict

from .code_review import CodeChangeReview
from .runbook_review import runbookReview
from .change_proposal import changeProposal
from .orchestrator_decision import orchestratorDecision


class workflowState(TypedDict, total=False):
    old_code: str
    current_code: str
    code_diff: str
    changed_files: list[dict]
    runbook_text: str
    review_only: bool
    runbook_paths: list[str]
    output_dir: str
    updated_runbook_paths: list[str]
    runbook_path: str
    output_path: str
    code_review: Optional[CodeChangeReview]
    runbook_review: Optional[runbookReview]
    runbook_review1: Optional[runbookReview]
    runbook_review2: Optional[runbookReview]
    orchestrator_decision: Optional[orchestratorDecision]
    orchestrator_feedback: str
    issue_scores: list[dict]
    change_proposal: Optional[changeProposal]
    approved_changes: Optional[changeProposal]
    human_feedback: str
    updated_runbook_path: str
    analysis_attempts: int
    max_analysis_attempts: int
    workflow_status: str
    error: str
