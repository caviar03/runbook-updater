import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from docx import Document
from docx.oxml.ns import qn
from docx.text.run import Run
from docx.text.paragraph import Paragraph

from src.models.change_proposal import changeProposal


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


def _iter_paragraphs_with_sections(container, inherited=()):
    """Document order and heading context, including nested tables."""
    headings = list(inherited)
    seen_cells = set()
    for item in container.iter_inner_content():
        if isinstance(item, Paragraph):
            level = _heading_level(item)
            if level is not None:
                headings = [heading for heading in headings if heading[0] < level]
                headings.append((level, item.text))
            yield item, [heading[1] for heading in headings]
        else:
            for row in item.rows:
                for cell in row.cells:
                    if cell._tc in seen_cells:
                        continue
                    seen_cells.add(cell._tc)
                    yield from _iter_paragraphs_with_sections(cell, headings)


def _paragraphs(container):
    for paragraph in container.paragraphs:
        yield paragraph
    visited_cells = set()
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                # Merged cells may appear more than once in the row/column grid.
                if cell._tc in visited_cells:
                    continue
                visited_cells.add(cell._tc)
                yield from _paragraphs(cell)


def _runs(paragraph):
    for item in paragraph.iter_inner_content():
        if isinstance(item, Run):
            yield item
        else:
            yield from item.runs


def _replace(paragraph, current_text, proposed_text):
    runs = list(_runs(paragraph))
    text = "".join(run.text for run in runs)
    if text != paragraph.text:
        raise ValueError("This paragraph contains unsupported text structures")
    start = text.index(current_text)
    end = start + len(current_text)
    positions = []
    cursor = 0
    for i, run in enumerate(runs):
        positions.append((i, cursor, cursor + len(run.text)))
        cursor += len(run.text)
    first, first_start, _ = next(item for item in positions if item[1] <= start < item[2])
    last, last_start, _ = next(item for item in positions if item[1] < end <= item[2])
    supported = {qn(f"w:{tag}") for tag in ["rPr", "t", "tab", "br", "cr"]}
    for run in runs[first:last + 1]:
        if any(element.tag not in supported for element in run._r):
            raise ValueError("Approved text overlaps an image, field, or unsupported run content")
    prefix = runs[first].text[:start - first_start]
    suffix = runs[last].text[end - last_start:]
    if first == last:
        runs[first].text = prefix + proposed_text + suffix
    else:
        runs[first].text = prefix + proposed_text
        for i in range(first + 1, last):
            runs[i].text = ""
        runs[last].text = suffix


def prepare_document(runbook_path: str, approved_changes: changeProposal, runbook_name=None):
    if not approved_changes or not approved_changes.changes:
        raise ValueError("Nonempty human-approved changes are required")
    document = Document(runbook_path)
    paragraphs = list(_iter_paragraphs_with_sections(document))
    name = runbook_name or runbook_path
    for change in approved_changes.changes:
        if change.runbook and _resolve_runbook_path(change.runbook, [name]) is None:
            raise ValueError(f"Proposal identifies a different runbook: {change.runbook!r}")
        if not change.current_text or not change.current_text.strip():
            raise ValueError("An update must identify exact nonempty current text")
        edits = [(change.current_text, change.proposed_text)]
        if not any(change.current_text in paragraph.text for paragraph, _ in paragraphs):
            # Support the upstream Docling table representation while requiring
            # every changed cell to match. Never save a partially applied edit.
            edits = _table_cell_edits(change.current_text, change.proposed_text) or edits
        for current_text, proposed_text in edits:
            matches = [(paragraph, headings) for paragraph, headings in paragraphs if current_text in paragraph.text]
            if sum(paragraph.text.count(current_text) for paragraph, _ in matches) > 1:
                matches = [(paragraph, headings) for paragraph, headings in matches if _in_section(change.section, headings)]
            occurrences = sum(paragraph.text.count(current_text) for paragraph, _ in matches)
            if occurrences != 1:
                raise ValueError(f"Approved text for {change.section!r} must match exactly once; found {occurrences}")
            _replace(matches[0][0], current_text, proposed_text)
    return document


def read_runbook_text(runbook_path: str, runbook_name=None) -> str:
    document = Document(runbook_path)
    if runbook_name:
        return "\n\n".join(
            f"[Runbook: {runbook_name}]\n[Section: {' > '.join(headings)}]\n{paragraph.text}"
            for paragraph, headings in _iter_paragraphs_with_sections(document)
        )
    return "\n\n".join(paragraph.text for paragraph in _paragraphs(document))


def _save_document(document, output_path):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only after every approved edit succeeds; failures leave existing files intact.
    temporary = None
    try:
        with NamedTemporaryFile(dir=output.parent, suffix=".docx", delete=False) as file:
            temporary = Path(file.name)
        document.save(temporary)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return str(output)


def implementor(runbook_path=None, approved_changes=None, output_path=None, *,
                runbook_paths=None, output_dir=None, runbook_name=None):
    if runbook_paths is None and isinstance(runbook_path, (list, tuple)):
        runbook_paths, output_dir = runbook_path, output_path
    if runbook_paths is None:
        document = prepare_document(runbook_path, approved_changes, runbook_name=runbook_name)
        return _save_document(document, output_path)
    if not approved_changes or not approved_changes.changes:
        raise ValueError("Nonempty human-approved changes are required")
    names = [_normalize(Path(path).name) for path in runbook_paths]
    if len(set(names)) != len(names):
        raise ValueError("Runbook file names must be unique for multi-document updates")
    changes_by_path = {}
    for change in approved_changes.changes:
        path = _resolve_runbook_path(change.runbook, runbook_paths)
        if path is None:
            raise ValueError(f"Unknown or ambiguous runbook: {change.runbook!r}")
        changes_by_path.setdefault(path, []).append(change)
    # Validate all documents before writing any output copies.
    prepared = []
    for path, changes in changes_by_path.items():
        proposal = changeProposal(changes=changes, readable_feedback=approved_changes.readable_feedback)
        prepared.append((prepare_document(path, proposal), Path(output_dir) / Path(path).name))
    return [_save_document(document, output) for document, output in prepared]
