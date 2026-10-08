from src.config import llm
from src.models.runbook_review import runbookReview
from src.models.code_review import CodeChangeReview
from src.retrieval.retriever import retrieve_chunks

def runbook_analyzer1(code_review: CodeChangeReview) -> runbookReview:
    query = f"""
    Identify the runbook sections relevant to these code changes
    and discrepancies:

    {code_review.model_dump_json(indent=2)}
    """

    retrieved_chunks = retrieve_chunks(query, limit=5)

    relevant_runbook = "\n\n".join(
        chunk.payload["text"]
        for chunk in retrieved_chunks
    )

    prompt = f"""
    You are a Runbook Analysis Agent.

    Your task is to determine whether the current runbook
    accurately reflects the behavior identified by the
    Code Review Agent.

    Identify discrepancies between the code behavior and
    the runbook.

    Rules:
    - Only use evidence provided by the Code Review.
    - Do not invent code behavior.
    - Identify the specific runbook section affected.
    - Explain what is missing or incorrect.
    - Recommend the required documentation change.
    - Do not write the final runbook.
    - Focus only on documentation discrepancies.
    """
    
    structured_llm = llm.with_structured_output(runbookReview)
    return structured_llm.invoke(prompt)

