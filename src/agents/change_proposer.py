from src.config import llm
from src.models.change_proposal import changeProposal
from src.models.runbook_review import runbookReview


def create_change_proposal(runbook: str,runbook_review: runbookReview) -> changeProposal:

    prompt = f"""You are the Change Proposal agent. Create precise proposed edits to the runbook based ONLY on the findings from the Runbook Analyzer.
For every change provide:

- affected section
- current text
- proposed replacement text
- reason for the change

Do not implement the changes.
Do not modify unrelated content.

====================
RUNBOOK
====================
{runbook}

====================
RUNBOOK REVIEW
====================
{runbook_review.model_dump_json(indent=2)}
"""
    structured_llm = llm.with_structured_output(changeProposal)
    
    return structured_llm.invoke(prompt)