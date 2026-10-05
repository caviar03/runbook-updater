from src.config import llm
from src.agents.runbook_analyzer1 import runbook_analyzer1
from src.agents.runbook_analyzer2 import runbook_analyzer2
from src.models.runbook_review import runbookReview
from src.models.code_review import CodeChangeReview

def runbook_decision_reviewer(
    runbook: str,
    code_review,
    runbook_analysis1: runbookReview,
    runbook_analysis2: runbookReview,
    ) -> runbookReview:

    prompt = f"""
You are the Runbook Review Judge.

Two independent agents analyzed the same code and runbook.

Your task is to evaluate their findings and produce the BEST
possible final RunbookReview.

You must:

1. Compare the findings from both analyzers.
2. Identify findings that are supported by the code.
3. Remove unsupported or speculative findings.
4. Resolve disagreements between the analyzers.
5. Prefer precise findings with strong evidence.
6. Avoid introducing new findings that neither analyzer identified
   unless they are clearly supported by the provided evidence.
7. Ensure every recommended change is actually justified by the
   code and the current runbook.

The final output must be a single RunbookReview.

====================
CODE REVIEW
====================
{code_review.model_dump_json(indent=2)}

====================
CURRENT RUNBOOK
====================
{runbook}

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

Produce the most accurate RunbookReview based on the evidence.
"""
    structured_llm = llm.with_structured_output(runbookReview)
    return structured_llm.invoke(prompt)
