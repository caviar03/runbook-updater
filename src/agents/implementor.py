from docx import Document

from src.models.change_proposal import changeProposal


def implementor(
    runbook_path: str,
    approved_changes: changeProposal,
    output_path: str,
) -> str:

    document = Document(runbook_path)

    for change in approved_changes.changes:

        current_text = change.current_text
        proposed_text = change.proposed_text

        for paragraph in document.paragraphs:

            if current_text.strip() in paragraph.text:

                for run in paragraph.runs:
                    run.text = ""

                paragraph.runs[0].text = paragraph.text.replace(
                    current_text,
                    proposed_text
                )

                break

    document.save(output_path)

    return output_path