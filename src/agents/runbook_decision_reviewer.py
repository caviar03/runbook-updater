from src.config import llm
from src.models.runbook_review import runbookReview


def runbook_decision_reviewer(
    code_review,
    runbook_analysis1: runbookReview,
    runbook_analysis2: runbookReview,
) -> runbookReview:

    prompt = f"""
You are the Runbook Review Judge.

Two independent agents analyzed the code changes and the
relevant sections of the CURRENT runbook retrieved from
the runbook search index.

Your task is to evaluate their findings and produce the
most accurate possible final RunbookReview.

You must:

1. Compare the findings from both analyzers.

2. Verify that each finding is supported by the CODE REVIEW.

3. Verify that each finding is based on evidence from the
   CURRENT RUNBOOK sections that the analyzers retrieved.

4. Remove unsupported, speculative, or hallucinated findings.

5. Resolve disagreements between the analyzers.

6. Prefer findings with specific evidence and clear
   operational impact.

7. Do NOT invent new runbook issues.

8. Do NOT assume that a code change requires a runbook
   change unless the evidence supports it.

9. Ensure every recommended change is directly justified
   by the code change and the documented runbook content.

10. Preserve the section identified by the analyzer when
    the finding is valid.

The final output must be a single RunbookReview.

====================
CODE REVIEW
====================
{code_review.model_dump_json(indent=2)}

====================
ANALYZER 1 REVIEW
====================
{runbook_analysis1.model_dump_json(indent=2)}

====================
ANALYZER 2 REVIEW
====================
{runbook_analysis2.model_dump_json(indent=2)}

====================
FINAL DECISION
====================

Select and reconcile the strongest evidence from the two
analyses.

Do not add findings that are not supported by the provided
evidence.

Produce the final RunbookReview.
"""

    structured_llm = llm.with_structured_output(runbookReview)

    return structured_llm.invoke(prompt)