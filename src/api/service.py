import fcntl
import hashlib
import json
import logging
import re
import threading
import uuid
from pathlib import Path
from openai import APITimeoutError

from src.api.pipeline import Pipeline, digest
from src.api.store import Store, dumps
from src.models.change_proposal import changeProposal
from src.review_service import RetrievalUnavailable

logger = logging.getLogger(__name__)


def pipeline_error(error):
    """Expose a safe, actionable cause; keep raw exceptions in server logs."""
    if isinstance(error, RetrievalUnavailable):
        return {"code": "RETRIEVAL_FAILED", "message": str(error)}
    if isinstance(error, APITimeoutError):
        steps = {"code_reviewer": "reviewing the merged code", "runbook_analyzer1": "analyzing the runbook",
                 "runbook_analyzer2": "analyzing the runbook", "runbook_decision_reviewer": "checking the runbook analysis",
                 "orchestrator_review": "reviewing the analysis", "change_proposal": "generating proposed runbook changes"}
        step = "analyzing the change"
        for note in getattr(error, "__notes__", []):
            match = re.search(r"During task with name '([^']+)'", note)
            if match and match[1] in steps:
                step = steps[match[1]]
        return {"code": "MODEL_TIMEOUT", "message": f"The AI request timed out while {step}. Retry analysis; if it happens again, increase the backend model timeout before retrying."}
    return {"code": "PIPELINE_FAILED", "message": "The runbook pipeline failed. Check backend logs and retry analysis."}


def preview_budget(snapshot):
    """Conservative bound for Markdown escaping, fences, and rendered output."""
    def escaped_size(text):
        return len(text.encode()) + len(re.findall(r"[\\`*_{}\[\]()<>#|!]", text))

    def fenced_size(text):
        fence = max([3] + [len(match[0]) + 1 for match in re.finditer(r"`+", text)])
        return len(text.encode()) + 2 * fence + 8

    size = 2048 + escaped_size(snapshot["summary"])
    for proposal in snapshot["proposals"]:
        size += 512 + sum(escaped_size(proposal[field]) for field in ("title", "reason"))
        size += escaped_size(proposal["target"]["path"])
        for change in proposal["changes"]:
            size += 256 + sum(escaped_size(change[field]) for field in ("section", "reason"))
            size += sum(fenced_size(change[field]) for field in ("current_text", "proposed_text"))
    return size


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class Service:
    def __init__(self, settings, pipeline=None):
        self.settings = settings
        self.store = Store(settings.data_dir / "state.sqlite3")
        self.pipeline = pipeline or Pipeline(settings)
        self.wakeup = threading.Event()
        self.stopping = threading.Event()
        self.running_job = threading.Lock()
        self.thread = None
        self.worker_lock = None

    @staticmethod
    def replay(db, scope, key, body):
        row = db.execute("SELECT * FROM receipts WHERE scope=? AND key=?", (scope, key)).fetchone()
        if row:
            if row["body"] != dumps(body):
                raise ApiError(409, "Idempotency key was already used with a different request")
            return row["status"], json.loads(row["response"])

    @staticmethod
    def receipt(db, scope, key, body, status, response):
        db.execute("INSERT INTO receipts(scope,key,body,status,response) VALUES (?,?,?,?,?)",
                   (scope, key, dumps(body), status, dumps(response)))
        return status, response

    def start_analysis(self, body, key):
        if body["source"]["repository"].lower() != self.settings.repository.lower():
            raise ApiError(403, "This repository is not enabled")
        with self.store.transaction() as db:
            replay = self.replay(db, "start", key, body)
            if replay:
                return replay
            if db.execute("SELECT id FROM analyses WHERE json_extract(request,'$.request_id')=? AND json_extract(request,'$.attempt')=?",
                          (body["request_id"], body["attempt"])).fetchone():
                raise ApiError(409, "This request and attempt already exist; reuse the original idempotency key")
            analysis_id = str(uuid.uuid4())
            source = body["source"]
            snapshot = {"analysis_id": analysis_id, "source_head_sha": source["head_sha"],
                        "source_merge_commit_sha": source["merge_commit_sha"], "status": "queued",
                        "summary": "Queued for analysis of the merged PR and configured runbook.",
                        "proposal_version": None, "proposals": [], "allowed_decisions": []}
            db.execute("INSERT INTO analyses(id,request,snapshot,work) VALUES (?,?,?,?)",
                       (analysis_id, dumps(body), dumps(snapshot), "analyze"))
            response = self.receipt(db, "start", key, body, 202, snapshot)
        self.wakeup.set()
        return response

    def get_analysis(self, analysis_id):
        job = self.store.get(analysis_id)
        if job is None:
            raise ApiError(404, "Unknown analysis")
        return job["snapshot"]

    def decide(self, analysis_id, body, key):
        scope = f"decision:{analysis_id}"
        with self.store.transaction() as db:
            replay = self.replay(db, scope, key, body)
            if replay:
                return replay
            job = self.store.read(db, analysis_id)
            if job is None:
                raise ApiError(404, "Unknown analysis")
            snapshot = job["snapshot"]
            if snapshot.get("decision_scope") == "document" and snapshot["proposals"]:
                raise ApiError(422, "Choose a proposal and use its document decision endpoint")
            if job["decision"] is not None:
                raise ApiError(409, "A decision has already been accepted")
            if body["head_sha"] != snapshot["source_head_sha"] or body["merge_commit_sha"] != snapshot["source_merge_commit_sha"] or body["proposal_version"] != snapshot["proposal_version"]:
                raise ApiError(409, "The source or proposal version does not match the reviewed result")
            if snapshot["status"] not in ("awaiting_decision", "no_update_needed"):
                raise ApiError(409, "This analysis is not awaiting a decision")
            if body["decision"] not in snapshot["allowed_decisions"]:
                raise ApiError(422, "This decision is not supported for this result")
            execution = job["execution"]
            try:
                if execution.get("format") == 2:
                    self.pipeline.verify_live(execution)
                    changed = False
                else:
                    changed = digest(Path(execution["source_path"]).read_bytes()) != execution["revision_sha256"]
                    self.pipeline.verify_snapshot(execution)
            except (OSError, ValueError):
                changed = True
            if changed:
                snapshot.update(status="stale", summary="The reviewed runbook has changed. Retry analysis.", allowed_decisions=[])
                self.store.save(db, job)
                # Commit the stale status, then return 409 without accepting the decision.
                response = (409, {"error": {"code": "CONFLICT", "message": snapshot["summary"]}})
            else:
                job["decision"] = body
                action = body["decision"]
                snapshot["allowed_decisions"] = []
                if action == "approve":
                    snapshot.update(status="applying", summary="Approval accepted. Applying the saved runbook changes to a local output copy.")
                    job["work"] = "apply"
                elif action == "deny":
                    snapshot.update(status="rejected", summary="The runbook update was denied.")
                else:
                    snapshot.update(status="no_update_needed", summary="The no-update result was acknowledged.", allowed_decisions=["acknowledge"])
                self.store.save(db, job)
                response = self.receipt(db, scope, key, body, 202 if action == "approve" else 200,
                                        {"accepted": True, "analysis": snapshot})
        self.wakeup.set()
        return response

    def run_once(self):
        """One durable job step; also used by tests without starting a daemon."""
        with self.running_job:
            job = self.store.next_job()
            if job is None:
                return False
            try:
                if job["work"] == "analyze":
                    job["snapshot"].update(status="analyzing", summary="Running the backend indexing, retrieval, and AI workflow.")
                    with self.store.transaction() as db:
                        self.store.save(db, job)
                    if job["execution"] is None:
                        job["execution"] = self.pipeline.prepare(job["request"], self.settings.data_dir / job["id"])
                        with self.store.transaction() as db:
                            self.store.save(db, job)
                    state = self.pipeline.analyze(job["execution"])
                    # Persist JSON, never pickle models or executable objects.
                    job["execution"]["state"] = json.loads(dumps(state))
                    self.review_result(job, state)
                elif job["execution"].get("format") == 2:
                    self.apply_documents(job)
                else:
                    if not job["decision"] or job["decision"]["decision"] != "approve":
                        raise ValueError("Application requires a saved approval")
                    output = self.pipeline.apply(job["execution"])
                    job["snapshot"].update(status="applied", summary=f"Approved changes saved to local output {job['id']}/updated.docx. GitHub publication is not configured.")
                    job["execution"]["updated_runbook_path"] = str(output)
                job["work"] = None
            except Exception as error:
                logger.exception("Workflow job %s failed", job["id"])
                if job["work"] == "analyze":
                    job["snapshot"].update(proposals=[], proposal_version=None)
                job["work"] = None
                failure = pipeline_error(error)
                job["snapshot"].update(status="failed", summary=failure["message"], allowed_decisions=[], error=failure)
            with self.store.transaction() as db:
                self.store.save(db, job)
            return True

    def review_result(self, job, state):
        status = state["workflow_status"]
        if status not in ("awaiting_decision", "no_update_needed"):
            raise ValueError(state.get("error") or "Analysis did not reach a reviewable result")
        snapshot = job["snapshot"]
        if job["execution"].get("format") == 2:
            return self.document_review_result(job, state)
        if status == "awaiting_decision":
            proposal = changeProposal.model_validate(state["change_proposal"])
            self.pipeline.validate(job["execution"], proposal)
            changes = [change.model_dump(exclude={"runbook"}) for change in proposal.changes]
            if any(not change[field].strip() for change in changes for field in ("section", "current_text", "proposed_text", "reason")):
                raise ValueError("The proposal contains an empty required field")
            snapshot.update(summary=proposal.readable_feedback or "The configured runbook needs an update.",
                            proposals=[{"id": f"{job['id']}:1", "title": "Update the configured runbook",
                                        "operation": "update", "reason": "This is the explicitly configured document; retrieval is disabled.",
                                        "target": {"kind": "local", "path": Path(job["execution"]["source_path"]).name,
                                                   "revision_sha256": job["execution"]["revision_sha256"]}, "changes": changes}],
                            allowed_decisions=["approve", "deny"])
        else:
            snapshot.update(summary="No update is needed for the configured runbook. Please acknowledge this result.",
                            proposals=[], allowed_decisions=["acknowledge"])
        # Include the source and document even when the result has no edits.
        version_data = [job["request"], job["execution"]["source_path"], job["execution"]["revision_sha256"], snapshot["proposals"]]
        snapshot.update(status=status, proposal_version=hashlib.sha256(dumps(version_data).encode()).hexdigest())
        if len(snapshot["summary"].encode()) > 4_000 or len(dumps(snapshot).encode()) > 32_000 or preview_budget(snapshot) > 48_000:
            raise ValueError("Proposal is too large for a complete GitHub preview")

    def document_review_result(self, job, state):
        snapshot, execution = job["snapshot"], job["execution"]
        snapshot["decision_scope"] = "document"
        proposal = changeProposal.model_validate(state["change_proposal"]) if state["workflow_status"] == "awaiting_decision" else None
        proposals = []
        if proposal:
            self.pipeline.validate(execution, proposal)
            grouped = self.pipeline.split_changes(execution, proposal)
            documents = {document["name"]: document for document in execution["documents"]}
            for name in sorted(grouped):
                changes = [change.model_dump(exclude={"runbook"}) for change in grouped[name]]
                if any(not change[field].strip() for change in changes for field in ("section", "current_text", "proposed_text", "reason")):
                    raise ValueError("The proposal contains an empty required field")
                proposals.append({"id": hashlib.sha256(name.encode()).hexdigest()[:24],
                    "title": "Update " + name, "operation": "update",
                    "reason": "Selected by the backend agents using retrieved runbook sections.",
                    "target": {"kind": "local", "path": name, "revision_sha256": documents[name]["revision_sha256"]},
                    "changes": changes, "review_status": "pending", "save_status": "not_started"})
        snapshot.update(proposals=proposals, status="awaiting_decision" if proposals else "no_update_needed",
                        summary=proposal.readable_feedback if proposals and proposal.readable_feedback else
                            ("Review the proposed document changes individually." if proposals else "No changes were proposed from the indexed runbooks. Please acknowledge this result."),
                        allowed_decisions=["approve", "deny"] if proposals else ["acknowledge"])
        version = [job["request"], execution["documents"], [{key: value for key, value in item.items()
                   if key not in ("review_status", "save_status")} for item in proposals]]
        snapshot["proposal_version"] = hashlib.sha256(dumps(version).encode()).hexdigest()
        # Individual comments contain the complete passages; no aggregate 32k
        # limit should silently remove a second document's review.
        if len(snapshot["summary"].encode()) > 4_000 or len(dumps(snapshot).encode()) > 1_000_000:
            raise ValueError("Analysis is too large for the integration")
        for item in proposals:
            if preview_budget({"summary": "", "proposals": [item]}) > 48_000:
                raise ValueError("Document proposal is too large for a complete GitHub review: " + item["target"]["path"])

    def decide_document(self, analysis_id, proposal_id, body, key):
        scope = f"decision:{analysis_id}:{proposal_id}"
        with self.store.transaction() as db:
            replay = self.replay(db, scope, key, body)
            if replay:
                return replay
            job = self.store.read(db, analysis_id)
            if not job:
                raise ApiError(404, "Unknown analysis")
            snapshot = job["snapshot"]
            if snapshot.get("decision_scope") != "document":
                raise ApiError(422, "This analysis uses the legacy decision endpoint")
            item = next((item for item in snapshot["proposals"] if item["id"] == proposal_id), None)
            if not item:
                raise ApiError(404, "Unknown document proposal")
            if (body["proposal_version"] != snapshot["proposal_version"] or body["head_sha"] != snapshot["source_head_sha"]
                    or body["merge_commit_sha"] != snapshot["source_merge_commit_sha"]):
                raise ApiError(409, "The source or reviewed proposal version does not match")
            if body["decision"] not in ("approve", "deny"):
                raise ApiError(422, "Choose approve or deny for this document")
            if snapshot["status"] != "awaiting_decision" or item["review_status"] != "pending":
                raise ApiError(409, "This document is not awaiting a decision")
            if body["decision"] == "approve":
                try:
                    self.pipeline.verify_live(job["execution"], {item["target"]["path"]})
                except (OSError, ValueError):
                    snapshot.update(status="stale", allowed_decisions=[], summary="The reviewed document changed. Retry analysis.")
                    self.store.save(db, job)
                    return 409, {"error": {"code": "CONFLICT", "message": snapshot["summary"]}}
            job["decision"] = job["decision"] or {}
            job["decision"][proposal_id] = body
            item.update(review_status="approved" if body["decision"] == "approve" else "denied",
                        decision={"action": body["decision"], "actor": body["actor"]})
            pending = sum(item["review_status"] == "pending" for item in snapshot["proposals"])
            approved = sum(item["review_status"] == "approved" for item in snapshot["proposals"])
            snapshot["summary"] = f"{approved} document(s) approved; {pending} awaiting a decision. Saving waits for all decisions."
            if not pending:
                snapshot["allowed_decisions"] = []
                if approved:
                    snapshot.update(status="applying", summary=f"All documents reviewed. Saving {approved} approved local copies.")
                    job["work"] = "apply"
                else:
                    snapshot.update(status="rejected", summary="All proposed document updates were denied. No copies were saved.")
            self.store.save(db, job)
            response = self.receipt(db, scope, key, body, 202, {"accepted": True, "analysis": snapshot})
        self.wakeup.set()
        return response

    def apply_documents(self, job):
        snapshot, execution = job["snapshot"], job["execution"]
        approved = [item for item in snapshot["proposals"] if item["review_status"] == "approved"]
        if any(item["review_status"] == "pending" for item in snapshot["proposals"]) or not approved:
            raise ValueError("Every document needs a saved decision before applying")
        if any((job["decision"] or {}).get(item["id"], {}).get("decision") != "approve" for item in approved):
            raise ValueError("Application requires a saved approval for each document")
        try:
            self.pipeline.verify_live(execution, {item["target"]["path"] for item in approved if item["save_status"] != "saved"})
        except (OSError, ValueError):
            snapshot.update(status="stale", allowed_decisions=[], summary="An approved runbook changed before saving. Retry analysis; approvals remain recorded.")
            return
        for item in approved:
            if item["save_status"] == "saved":
                continue
            try:
                changes = [dict(change, runbook=item["target"]["path"]) for change in item["changes"]]
                item["save_status"] = "saving"
                output = self.pipeline.apply_document(execution, item["target"]["path"],
                    changeProposal.model_validate({"changes": changes, "readable_feedback": "Approved"}).changes)
                item.update(save_status="saved", result={"output_path": str(output)})
            except Exception as error:
                logger.exception("Document save failed for %s", item["id"])
                item.update(save_status="failed", error=pipeline_error(error))
            with self.store.transaction() as db:
                self.store.save(db, job)
        failures = [item for item in approved if item["save_status"] != "saved"]
        if failures:
            snapshot.update(status="failed", summary=f"Saved {len(approved) - len(failures)} of {len(approved)} approved copies; see the document save receipts.",
                            error={"code": "DOCUMENT_SAVE_FAILED", "message": "Some approved documents could not be saved. Existing successful copies remain available."})
        else:
            snapshot.update(status="applied", summary=f"Saved {len(approved)} approved local runbook copies. GitHub publication is not configured.")

    def start_worker(self):
        lock = (self.settings.data_dir / "worker.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            raise RuntimeError("A backend worker already uses this data directory; run one uvicorn worker")
        self.worker_lock = lock
        self.thread = threading.Thread(target=self._loop, name="runbook-worker", daemon=True)
        self.thread.start()

    def _loop(self):
        try:
            while not self.stopping.is_set():
                self.wakeup.clear()
                try:
                    has_work = self.run_once()
                except Exception:
                    logger.exception("Worker could not persist a job; saved work will be retried")
                    has_work = False
                if not has_work:
                    self.wakeup.wait(1)
        finally:
            self.worker_lock.close()

    def stop_worker(self):
        self.stopping.set()
        self.wakeup.set()
        if self.thread:
            self.thread.join(timeout=5)
