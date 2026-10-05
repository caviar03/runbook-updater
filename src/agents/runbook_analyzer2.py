from src.config import llm
from src.models.runbook_review import runbookReview
from src.models.code_review import CodeChangeReview

def runbook_analyzer2(runbook: str, code_review: CodeChangeReview) -> runbookReview:
    prompt = f"""
You are a Runbook Analysis Agent.

Your task is to determine whether the current runbook
accurately reflects the behavior identified by the
Code Review Agent.

Identify discrepancies between the code behavior and
the runbook.

Rules:
- Only use evidence provided by the Code Review.
- Do not invent code behavior.
- Identify the specific runbook section affected.
- Explain what is missing or incorrect.
- Recommend the required documentation change.
- Do not write the final runbook.
- Focus only on documentation discrepancies.

====================
RUNBOOK
====================
{runbook}

====================
CODE REVIEW
====================
{code_review.model_dump_json(indent=2)}
"""
    
    structured_llm = llm.with_structured_output(runbookReview)
    return structured_llm.invoke(prompt)

