from src.config import llm
from src.models.runbook_review import runbookReview
from src.models.code_review import CodeChangeReview
def retrieve_for_queries(*args, **kwargs):
    from src.retrieval.retriever import retrieve_for_queries as retrieve
    return retrieve(*args, **kwargs)


def format_chunks(chunks):
    from src.retrieval.retriever import format_chunks as format_content
    return format_content(chunks)


# Analyzer 1 checks factual accuracy: names, values, behavior and
# errors that the runbook states about the changed code.

def runbook_analyzer1(code_review: CodeChangeReview, feedback: str = "", runbook_text: str | None = None) -> runbookReview:
    queries = [
        f"{change.description} {' '.join(change.affected_components)}"
        for change in code_review.code_changes
    ] + [
        discrepancy.runbook_claim
        for discrepancy in code_review.existing_discrepancies
    ]

    if not queries and runbook_text is None:
        return runbookReview(update_required=False, issues=[])

    relevant_runbook = runbook_text if runbook_text is not None else format_chunks(
        retrieve_for_queries(queries, limit=5)
    )

    prompt = f"""
You are a Runbook Analysis Agent focused on FACTUAL ACCURACY.

Your task is to determine whether the current runbooks
accurately describe the code behavior identified by the
Code Review Agent.

Check every statement in the retrieved runbook content about:
- constant, variable, function, class and error names
- configuration values and defaults
- described behavior (e.g. how retries, timeouts or
  calculations work)
- errors or exceptions that are thrown and when

Rules:
- Only use evidence provided by the Code Review.
- Do not invent code behavior.
- Only report a discrepancy if the retrieved runbook content
  contains a statement that is now incorrect, or is missing
  information that the changed behavior makes necessary.
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
