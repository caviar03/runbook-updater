import os
import re

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from src.models.change_proposal import changeProposal, proposedChange


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _resolve_runbook_path(runbook: str, runbook_paths: list[str]) -> str | None:
    # The LLM may return the full file name, the name without
    # extension, or a shortened service name.
    target = _normalize(os.path.splitext(os.path.basename(runbook))[0])

    for path in runbook_paths:
        name = _normalize(os.path.splitext(os.path.basename(path))[0])
        if name == target:
            return path

    candidates = [
        path for path in runbook_paths
        if target and target in _normalize(os.path.basename(path))
    ]

    if len(candidates) == 1:
        return candidates[0]

    return None


def _heading_level(paragraph: Paragraph) -> int | None:
    style = paragraph.style.name if paragraph.style is not None else ""
    match = re.match(r"Heading (\d+)", style)
    return int(match.group(1)) if match else None


def _iter_paragraphs_with_sections(document):
    """Yield (paragraph, heading_stack) in document order, including table cells."""
    heading_stack: list[tuple[int, str]] = []

    for child in document.element.body.iterchildren():

        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, document)
            level = _heading_level(paragraph)

            if level is not None:
                heading_stack = [h for h in heading_stack if h[0] < level]
                heading_stack.append((level, paragraph.text))
                continue

            yield paragraph, [h[1] for h in heading_stack]

        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            seen_cells = set()

            for row in table.rows:
                for cell in row.cells:
                    # Merged cells appear once per spanned column.
                    # Store the elements themselves (not id()) so they stay
                    # alive and identity comparisons remain valid.
                    if cell._tc in seen_cells:
                        continue
                    seen_cells.add(cell._tc)

                    for paragraph in cell.paragraphs:
                        yield paragraph, [h[1] for h in heading_stack]


def _in_section(section: str, headings: list[str]) -> bool:
    target = _normalize(section)

    # Allow "5.3 Execution Steps", "Execution Steps" or
    # "Deployment & Configuration > Execution Steps". For a heading
    # path, only the most specific (last) heading has to match.
    parts = [p for p in re.split(r"\s*>\s*", target) if p]

    if not parts:
        return False

    return any(parts[-1] in _normalize(heading) for heading in headings)


# Docling flattens table rows in chunk text as
# "<row label>, **<column>** = <cell value>. <row label>, **<column>** = ..."
# The LLM sometimes drops the repeated row label, so it is optional.
_TABLE_CELL_VALUE = re.compile(
    r"\*\*[^*]+\*\* = (.+?)(?=\.\s+(?:[^.]*?, )?\*\*[^*]+\*\* = |\.?\s*$)",
    re.DOTALL,
)


def _table_cell_edits(current_text: str, proposed_text: str) -> list[tuple[str, str]]:
    # Turn a change quoted as flattened table rows back into
    # per-cell (current, proposed) edits.
    current_values = _TABLE_CELL_VALUE.findall(current_text)
    proposed_values = _TABLE_CELL_VALUE.findall(proposed_text)

    if not current_values or len(current_values) != len(proposed_values):
        return []

    return [
        (old.strip(), new.strip())
        for old, new in zip(current_values, proposed_values)
        if old.strip() != new.strip()
    ]


def _replace_in_paragraph(paragraph: Paragraph, current_text: str, proposed_text: str) -> bool:
    # Prefer replacing inside a single run so formatting is preserved.
    for run in paragraph.runs:
        if current_text in run.text:
            run.text = run.text.replace(current_text, proposed_text, 1)
            return True

    if current_text not in paragraph.text or not paragraph.runs:
        return False

    new_text = paragraph.text.replace(current_text, proposed_text, 1)

    for run in paragraph.runs:
        run.text = ""

    paragraph.runs[0].text = new_text
    return True


def _apply_text_edit(document, section: str, current_text: str, proposed_text: str) -> bool:
    if not current_text:
        return False

    for paragraph, headings in _iter_paragraphs_with_sections(document):
        if not _in_section(section, headings):
            continue

        if _replace_in_paragraph(paragraph, current_text, proposed_text):
            return True

    return False


def _apply_change(document, change: proposedChange) -> bool:
    current_text = change.current_text.strip()
    proposed_text = change.proposed_text.strip()

    if _apply_text_edit(document, change.section, current_text, proposed_text):
        return True

    # Fall back to per-cell edits when the change quotes flattened table rows.
    cell_edits = _table_cell_edits(current_text, proposed_text)

    if not cell_edits:
        return False

    results = [
        _apply_text_edit(document, change.section, old, new)
        for old, new in cell_edits
    ]

    return any(results)

    return False


def implementor(
    runbook_paths: list[str],
    approved_changes: changeProposal,
    output_dir: str,
) -> list[str]:

    changes_by_path: dict[str, list[proposedChange]] = {}

    for change in approved_changes.changes:
        path = _resolve_runbook_path(change.runbook, runbook_paths)

        if path is None:
            print(f"IMPLEMENTOR: skipped change, unknown runbook '{change.runbook}'")
            continue

        changes_by_path.setdefault(path, []).append(change)

    os.makedirs(output_dir, exist_ok=True)

    updated_paths = []

    for path, changes in changes_by_path.items():
        document = Document(path)
        applied = 0

        for change in changes:
            if _apply_change(document, change):
                applied += 1
            else:
                print(
                    f"IMPLEMENTOR: could not find text in section "
                    f"'{change.section}' of {os.path.basename(path)}: "
                    f"{change.current_text[:80]!r}"
                )

        if applied == 0:
            continue

        output_path = os.path.join(output_dir, os.path.basename(path))
        document.save(output_path)
        updated_paths.append(output_path)

        print(f"IMPLEMENTOR: applied {applied}/{len(changes)} changes to {output_path}")

    return updated_paths
