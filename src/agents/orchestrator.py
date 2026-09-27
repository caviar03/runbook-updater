from pydantic import BaseModel

from src.config import llm
from src.models.code_review import CodeChangeReview
from src.models.runbook_review import runbookReview


class orchestratorDecision(BaseModel):
    proceed: bool
    reasoning: str
    feedback: str


def orchestrator_review(code_review: CodeChangeReview, runbook_review: runbookReview) -> orchestratorDecision:

    prompt = f"""
You are the Orchestrator Agent.

Review the Code Review and Runbook Review.

Your responsibilities:
- Determine whether the findings are sufficiently
  supported by the code and runbook.
- Determine whether the proposed documentation work
  should proceed.
- Identify problems that require the analyzers to
  rework their analysis.
- Do not write the final runbook.
- Do not invent information.

If the analysis is sufficiently supported:
proceed = true

If the analysis requires rework:
proceed = false

====================
CODE REVIEW
====================
{code_review.model_dump_json(indent=2)}

====================
RUNBOOK REVIEW
====================
{runbook_review.model_dump_json(indent=2)}
"""

    structured_llm = llm.with_structured_output(
        orchestratorDecision
    )

    return structured_llm.invoke(prompt)