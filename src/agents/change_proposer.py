from src.config import llm
from src.models.change_proposal import changeProposal
from src.models.runbook_review import runbookReview
from src.retrieval.retriever import format_chunks, retrieve_for_queries


def create_change_proposal( runbook_review: runbookReview) -> changeProposal:
    queries = [
        issue.issue
        for issue in runbook_review.issues
    ]

    relevant_runbook = format_chunks(
        retrieve_for_queries(queries, limit=3)
    )

    prompt = f"""
You are the Change Proposal agent.

Create precise proposed edits to the CURRENT runbooks based
ONLY on the findings from the final Runbook Review and the
retrieved runbook sections.

For every change provide:

- runbook: the exact file name shown in the [Runbook: ...]
  label of the retrieved content being changed
- affected section: the section heading the text sits under,
  as shown in the [Section: ...] label
- current text: copied verbatim from a single paragraph or
  table cell of the retrieved content
  Table rows appear in the retrieved content flattened as
  "<row label>, **<column>** = <cell value>. ...". For table
  content, current text and proposed text must be ONLY the
  <cell value> being changed, never the flattened row.
  Make one change per paragraph or table cell.
- proposed replacement text
- reason for the change

Rules:

1. Only propose changes identified in the Runbook Review.
2. Use the retrieved runbook content to determine the
   exact current text that needs to change.
3. Do not invent information.
4. Do not modify unrelated content.
5. Do not implement the changes.
6. Preserve the existing terminology and structure.
7. If a finding cannot be supported by the retrieved
   runbook content, do not propose a change for it.

====================
FINAL RUNBOOK REVIEW
====================
{runbook_review.model_dump_json(indent=2)}

====================
RELEVANT CURRENT RUNBOOK SECTIONS
====================
{relevant_runbook}

====================
PROPOSED CHANGES
====================

Create the ChangeProposal.
"""

    structured_llm = llm.with_structured_output(changeProposal)

    return structured_llm.invoke(prompt)