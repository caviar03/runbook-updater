import fcntl
import hashlib
import json
import logging
import re
import threading
import uuid
from pathlib import Path

from src.api.pipeline import Pipeline, digest
from src.api.store import Store, dumps
from src.models.change_proposal import changeProposal

logger = logging.getLogger(__name__)


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
                    job["snapshot"].update(status="analyzing", summary="Reviewing the merged code and configured runbook.")
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
                else:
                    if not job["decision"] or job["decision"]["decision"] != "approve":
                        raise ValueError("Application requires a saved approval")
                    output = self.pipeline.apply(job["execution"])
                    job["snapshot"].update(status="applied", summary=f"Approved changes saved to local output {job['id']}/updated.docx. GitHub publication is not configured.")
                    job["execution"]["updated_runbook_path"] = str(output)
                job["work"] = None
            except Exception:
                logger.exception("Workflow job %s failed", job["id"])
                if job["work"] == "analyze":
                    job["snapshot"].update(proposals=[], proposal_version=None)
                job["work"] = None
                job["snapshot"].update(status="failed", summary="The runbook pipeline failed. Check backend logs and retry analysis.",
                                       allowed_decisions=[], error={"code": "PIPELINE_FAILED", "message": "The runbook pipeline failed. Check backend logs and retry analysis."})
            with self.store.transaction() as db:
                self.store.save(db, job)
            return True

    def review_result(self, job, state):
        status = state["workflow_status"]
        if status not in ("awaiting_decision", "no_update_needed"):
            raise ValueError(state.get("error") or "Analysis did not reach a reviewable result")
        snapshot = job["snapshot"]
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
