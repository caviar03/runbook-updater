from src.config import llm
from src.models.runbook_review import runbookReview
from src.models.code_review import CodeChangeReview
def retrieve_for_queries(*args, **kwargs):
    from src.retrieval.retriever import retrieve_for_queries as retrieve
    return retrieve(*args, **kwargs)


def format_chunks(chunks):
    from src.retrieval.retriever import format_chunks as format_content
    return format_content(chunks)


# Analyzer 2 checks operational procedures: whether the steps an
# operator would follow still work given the changed behavior.

def runbook_analyzer2(code_review: CodeChangeReview, feedback: str = "", runbook_text: str | None = None) -> runbookReview:
    queries = [
        change.operational_impact
        for change in code_review.code_changes
    ] + [
        discrepancy.explanation
        for discrepancy in code_review.existing_discrepancies
    ]

    if not queries and runbook_text is None:
        return runbookReview(update_required=False, issues=[])

    relevant_runbook = runbook_text if runbook_text is not None else format_chunks(
        retrieve_for_queries(queries, limit=5)
    )

    prompt = f"""
You are a Runbook Analysis Agent focused on OPERATIONAL PROCEDURES.

Your task is to determine whether the procedures in the current
runbooks still work correctly given the code behavior identified
by the Code Review Agent.

Check the retrieved runbook content for:
- troubleshooting steps and error descriptions an operator
  would see
- rollback, maintenance and configuration procedures
- verification steps and expected outcomes
- monitoring, alerting or escalation guidance

Rules:
- Only use evidence provided by the Code Review.
- Do not invent code behavior.
- Only report a discrepancy if following the retrieved runbook
  content would now mislead an operator, or if a procedure is
  missing a step that the changed behavior makes necessary.
- For each issue, set "runbook" to the exact file name from the
  [Runbook: ...] label and "section" to the heading from the
  [Section: ...] label of the content you are citing.
- Quote the outdated runbook statement in "issue".
- Explain what is missing or incorrect.
- Recommend the required documentation change.
- Do not write the final runbook.
- If no retrieved content is affected, return
  update_required = false with no issues.

====================
CODE REVIEW
====================
{code_review.model_dump_json(indent=2)}

====================
ORCHESTRATOR FEEDBACK FROM PREVIOUS ATTEMPT
====================
{feedback or "None"}

====================
CURRENT RUNBOOK SECTIONS
====================
{relevant_runbook}

====================
RUNBOOK REVIEW
====================

Produce a RunbookReview.
"""

    structured_llm = llm.with_structured_output(runbookReview)
    return structured_llm.invoke(prompt)
