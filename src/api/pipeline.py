import hashlib
import os
from pathlib import Path

from src.agents.implementor import implementor, prepare_document, read_runbook_text
from src.github.snapshot import code_from_snapshot
from src.graph.workflow import build_workflow
from src.graph.state import make_initial_state
from src.models.change_proposal import changeProposal


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Pipeline:
    """Use one explicitly configured document; no retrieval or runbook discovery."""

    def __init__(self, settings):
        self.settings = settings

    def prepare(self, request, folder: Path):
        code = code_from_snapshot(request["code_snapshot"])
        content = self.settings.runbook_path.read_bytes()
        folder.mkdir(parents=True, exist_ok=True)
        snapshot_path = folder / "source.docx"
        temporary = folder / "source.tmp"
        temporary.write_bytes(content)
        os.replace(temporary, snapshot_path)
        state = make_initial_state(code, snapshot_path, folder / "updated.docx")
        state.update(review_only=True, runbook_text=read_runbook_text(str(snapshot_path), runbook_name=self.settings.runbook_path.name))
        return {"state": state, "source_path": str(self.settings.runbook_path),
                "revision_sha256": digest(content)}

    def analyze(self, execution):
        self.verify_snapshot(execution)
        return build_workflow().invoke(execution["state"], {"recursion_limit": 50})

    @staticmethod
    def verify_snapshot(execution):
        if digest(Path(execution["state"]["runbook_path"]).read_bytes()) != execution["revision_sha256"]:
            raise ValueError("The saved runbook snapshot changed")

    def validate(self, execution, proposal):
        self.verify_snapshot(execution)
        prepare_document(execution["state"]["runbook_path"], proposal, runbook_name=Path(execution["source_path"]).name)

    def apply(self, execution):
        self.verify_snapshot(execution)
        state = execution["state"]
        # Always start from the immutable source, including after an interrupted write.
        # Repeating a recovered job replaces its own output; it never edits twice.
        return implementor(state["runbook_path"], changeProposal.model_validate(state["change_proposal"]), state["output_path"], runbook_name=Path(execution["source_path"]).name)
