from functools import lru_cache

from src.config import NECESSITY_MODEL
from src.models.runbook_review import runbookIssue

# The v2.0 zero-shot models are binary entailment classifiers, so a single
# hypothesis returns one probability that the issue is relevant to the change.
# Treat it as a rough signal: phrasings like "the runbook is outdated" scored
# valid issues near 0, and this one still scored a valid issue at 0.48.
NECESSITY_HYPOTHESIS = "The code change affects what the runbook statement describes."


@lru_cache(maxsize=1)
def _classifier():
    # Import and load on first use so API startup and tests never pull the model.
    from transformers import pipeline
    return pipeline("zero-shot-classification", model=NECESSITY_MODEL)


def _premise(issue: runbookIssue) -> str:
    # recommended_change is left out so the model judges the evidence,
    # not the analyzer's own conclusion.
    return (
        f"Runbook section: {issue.section}\n"
        f"Runbook statement: {issue.issue}\n"
        f"Code change: {issue.evidence_from_code}"
    )


def score_issues(issues: list[runbookIssue]) -> list[float]:
    if not issues:
        return []
    results = _classifier()(
        [_premise(issue) for issue in issues],
        candidate_labels=[NECESSITY_HYPOTHESIS],
        hypothesis_template="{}",
        multi_label=True,
    )
    if isinstance(results, dict):
        results = [results]
    return [float(result["scores"][0]) for result in results]
