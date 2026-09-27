from src.config import llm
from src.models.code_review import CodeChangeReview


def code_reviewer(old_code: str, current_code: str, runbook: str) -> CodeChangeReview:

    prompt = f"""
You are a Code Review Agent.

Your job is to:

1. Compare the old and current code.
2. Identify meaningful code changes.
3. Review the FULL current code for pre-existing
   discrepancies with the runbook.
4. Identify anything in the code that the runbook
   does not accurately document.
5. Identify anything the runbook claims that the
   code does not support.
6. Determine which findings are relevant to the runbook.

Do not invent behavior that is not supported by the code.

====================
OLD CODE
====================
{old_code}

====================
CURRENT CODE
====================
{current_code}

====================
RUNBOOK
====================
{runbook}
"""

    structured_llm = llm.with_structured_output(CodeChangeReview)

    return structured_llm.invoke(prompt)