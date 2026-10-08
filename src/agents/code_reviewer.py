from src.config import llm
from src.models.code_review import CodeChangeReview


def code_reviewer(
    old_code: str,
    code_diff: str
) -> CodeChangeReview:

    prompt = f"""
You are a Code Review Agent.

Your job is to analyze a code change and identify meaningful
changes that may have an operational impact or require a
runbook update.

You must:

1. Use the OLD CODE to understand the previous behavior.
2. Use the GITHUB DIFF to identify exactly what changed.
3. Identify meaningful behavioral or configuration changes.
4. Identify existing behavior that may now differ from the
   previous implementation.
5. Do not invent behavior that is not supported by the
   provided code or diff.
6. Do not assume that every code change requires a runbook
   update.
7. For each change, explain its operational impact and whether
   it is potentially relevant to the runbook.

====================
OLD CODE
====================
{old_code}

====================
GITHUB DIFF
====================
{code_diff}

====================
CODE REVIEW
====================

Produce a CodeChangeReview.
"""

    structured_llm = llm.with_structured_output(CodeChangeReview)

    return structured_llm.invoke(prompt)