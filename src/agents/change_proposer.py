from src.config import llm
from src.models.change_proposal import changeProposal
from src.models.runbook_review import runbookReview
def retrieve_chunks(*args, **kwargs):
    from src.retrieval.retriever import retrieve_chunks as retrieve
    return retrieve(*args, **kwargs)



def create_change_proposal( runbook_review: runbookReview, runbook_text: str | None = None) -> changeProposal:
    if runbook_text is not None:
        relevant_runbook = runbook_text
    else:
        chunks = []
        for issue in runbook_review.issues:
            chunks.extend(retrieve_chunks(issue.issue, limit=3))
        relevant_runbook = "\n\n".join(dict.fromkeys(chunk.payload["text"] for chunk in chunks))

    prompt = f"""
You are the Change Proposal agent.

Create precise proposed edits to the CURRENT runbook based
ONLY on the findings from the final Runbook Review and the
retrieved runbook sections.

For every change provide:

- affected section
- current text
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
8. Each current_text must be an exact, nonempty, contiguous
   passage within one paragraph (including a table-cell paragraph).
   Split edits to multiple paragraphs into separate changes.

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
