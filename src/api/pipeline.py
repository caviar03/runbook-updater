import hashlib
from pathlib import Path

from src.agents.implementor import implementor, prepare_document
from src import review_service
from src.github.snapshot import code_from_snapshot
from src.graph.workflow import build_workflow
from src.models.change_proposal import changeProposal


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Pipeline:
    """Transport adapter to the backend review service; no document selection or AI logic."""

    def __init__(self, settings):
        self.settings = settings

    def prepare(self, request, folder: Path):
        return review_service.prepare_review(code_from_snapshot(request["code_snapshot"]),
                                             self.settings.paths, folder, self.settings.retrieval_location,
                                             self.settings.retrieval_embedded)

    def analyze(self, execution):
        if execution.get("format") == 2:
            return review_service.analyze_review(execution)
        self.verify_snapshot(execution)
        return build_workflow().invoke(execution["state"], {"recursion_limit": 50})

    @staticmethod
    def verify_snapshot(execution):
        if execution.get("format") == 2:
            return review_service.verify_review(execution)
        if digest(Path(execution["state"]["runbook_path"]).read_bytes()) != execution["revision_sha256"]:
            raise ValueError("The saved runbook snapshot changed")

    def validate(self, execution, proposal):
        if execution.get("format") == 2:
            return review_service.validate_review(execution, proposal)
        self.verify_snapshot(execution)
        prepare_document(execution["state"]["runbook_path"], proposal, runbook_name=Path(execution["source_path"]).name)

    def apply(self, execution):
        self.verify_snapshot(execution)
        state = execution["state"]
        # Always start from the immutable source, including after an interrupted write.
        # Repeating a recovered job replaces its own output; it never edits twice.
        return implementor(state["runbook_path"], changeProposal.model_validate(state["change_proposal"]), state["output_path"], runbook_name=Path(execution["source_path"]).name)

    def split_changes(self, execution, proposal):
        return review_service.split_changes(execution, proposal)

    def verify_live(self, execution, names=None):
        return review_service.verify_review(execution, live=True, names=names)

    def apply_document(self, execution, name, changes):
        return review_service.apply_document(execution, name, changes)
