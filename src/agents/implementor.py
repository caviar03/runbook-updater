from src.config import llm
from src.models.change_proposal import changeProposal


def implementor(runbook: str, approved_changes: changeProposal) -> str:
    prompt = f"""
You are the Runbook Implementor.

Apply ONLY the human-approved changes to the
current runbook.

Rules:
- Do not invent information.
- Do not make additional changes.
- Do not modify unrelated sections.
- Preserve the existing formatting.
- Return the complete updated runbook.
- The approved changes are authoritative.

====================
CURRENT RUNBOOK
====================
{runbook}

====================
HUMAN-APPROVED CHANGES
====================
{approved_changes.model_dump_json(indent=2)}
"""
    response = llm.invoke(prompt)

    return response.content