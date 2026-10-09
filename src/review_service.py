"""Programmatic backend entrypoint: the existing indexer, graph and DOCX writer.

Transport adapters supply code, not document text. No agent prompts, search
ranking, parser or editing rules are implemented here.
"""
import hashlib
import os
from pathlib import Path

from src.agents.implementor import _resolve_runbook_path, prepare_document, implementor
from src.graph.state import make_initial_state
from src.graph.workflow import build_workflow
from src.models.change_proposal import changeProposal
from src.retrieval.runtime import retrieval_scope


def digest(content):
    return hashlib.sha256(content).hexdigest()


def prepare_review(code, paths, folder, retrieval_location, embedded=True):
    folder = Path(folder)
    documents = []
    for source in paths:
        source = Path(source)
        content = source.read_bytes()
        snapshot = folder / "sources" / source.name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        temporary = snapshot.with_suffix(".tmp")
        temporary.write_bytes(content)
        os.replace(temporary, snapshot)
        documents.append({"name": source.name, "source_path": str(source), "snapshot_path": str(snapshot),
                          "revision_sha256": digest(content)})
    state = make_initial_state(code, [doc["snapshot_path"] for doc in documents], folder / "outputs")
    state["review_only"] = True
    return {"format": 2, "documents": documents, "state": state,
            "retrieval": {"location": str(retrieval_location), "embedded": embedded,
                          "collection": "api_review_" + folder.name.replace("-", "_")}}


def verify_review(execution, live=False, names=None):
    for document in execution["documents"]:
        if names is not None and document["name"] not in names:
            continue
        if digest(Path(document["snapshot_path"]).read_bytes()) != document["revision_sha256"]:
            raise ValueError("The saved runbook snapshot changed: " + document["name"])
        if live and digest(Path(document["source_path"]).read_bytes()) != document["revision_sha256"]:
            raise ValueError("The reviewed runbook changed: " + document["name"])


class RetrievalUnavailable(Exception):
    pass


def analyze_review(execution):
    verify_review(execution)
    from src.retrieval.vector_store import get_qdrant_client, collection_name
    scope = execution["retrieval"]
    try:
        from src.retrieval.index_runbooks import index_runbooks
        with retrieval_scope(scope["location"], scope["embedded"], scope["collection"]):
            index_runbooks(execution["state"]["runbook_paths"])
            if get_qdrant_client().count(collection_name=collection_name(), exact=True).count == 0:
                raise ValueError("The retrieval index contains no readable sections")
    except Exception as error:
        raise RetrievalUnavailable("Backend runbook indexing failed. Check retrieval dependencies, model downloads, and storage; then retry analysis.") from error
    with retrieval_scope(scope["location"], scope["embedded"], scope["collection"]):
        return build_workflow().invoke(execution["state"], {"recursion_limit": 50})


def split_changes(execution, proposal):
    paths = [doc["snapshot_path"] for doc in execution["documents"]]
    grouped = {}
    for change in proposal.changes:
        path = _resolve_runbook_path(change.runbook, paths)
        if path is None:
            raise ValueError("Unknown or ambiguous runbook: " + repr(change.runbook))
        name = Path(path).name
        grouped.setdefault(name, []).append(change.model_copy(update={"runbook": name}))
    return grouped


def validate_review(execution, proposal):
    verify_review(execution)
    documents = {doc["name"]: doc for doc in execution["documents"]}
    for name, changes in split_changes(execution, proposal).items():
        prepare_document(documents[name]["snapshot_path"], changeProposal(changes=changes, readable_feedback=proposal.readable_feedback), runbook_name=name)


def apply_document(execution, name, changes):
    verify_review(execution, live=True, names={name})
    document = next(doc for doc in execution["documents"] if doc["name"] == name)
    proposal = changeProposal(changes=changes, readable_feedback="Human-approved document changes")
    output = Path(execution["state"]["output_dir"]) / name
    return implementor(document["snapshot_path"], proposal, str(output), runbook_name=name)
