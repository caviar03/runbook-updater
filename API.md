# GitHub App API

The backend accepts a confirmed code merge, analyzes the App-supplied saved PR diff against
one configured local DOCX, and waits for a separate document decision. Retrieval
is bypassed: no Qdrant, embeddings, Docling, indexing, or runbook discovery is
used by the API. Both analyzers and the proposer receive the document text,
including table-cell paragraphs, directly. Direct content now carries runbook
filename and section labels shared with the upstream multi-runbook agents.
The API still selects one configured file; the CLI can index and update several.
Legacy saved proposals without a runbook identifier remain readable and applicable;
a new proposal that identifies a different file is rejected before review.

## Start locally

Run from `runbook-updater` using Python 3.12 or later on macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-api.txt
cp .env.example .env
```

Fill these fields in `.env`:

| Setting | Value |
| --- | --- |
| `BACKEND_TOKEN` | A random service token of at least 24 characters; use the same value in the GitHub App. Generate one with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`. |
| `SOURCE_REPOSITORY` | `sriram-senthilkr/mock-website`, or the single selected code repository. |
| `OPENAI_API_KEY` | Model credential. Required when a job starts analysis, not for API startup/health. |
| `RUNBOOK_PATH` | Existing DOCX file to analyze. Choose a document relevant to your test code. |
| `BACKEND_DATA_DIR` | Durable local directory, default `.data`. Keep it across restarts. |

Start the service:

```sh
.venv/bin/python -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

`GET http://127.0.0.1:8000/health` reports that the endpoint is reachable.
Interactive API documentation is at `http://127.0.0.1:8000/docs`.
All `/v1` calls need `Authorization: Bearer <BACKEND_TOKEN>`; both POST calls
also need a nonempty `Idempotency-Key` header. Do not run multiple workers
against the same directory; a process lock prevents duplicate execution.

In `github-app/.env`, use `BACKEND_URL=http://127.0.0.1:8000` and the same
`BACKEND_TOKEN`, with `RELEASE_ON=approval` and `NO_UPDATE_POLICY=acknowledge`.
Keep the App credentials, webhook secret, and selected repository configured.
Run the App with `npm start` (live mode), rather than `npm run smoke`.
Cloudflare exposes the App's port 3000 webhook, not the backend's port 8000.
The existing running smoke service is not automatically switched by this change.

## Endpoints

The request/response contract is in
[`../github-app/BACKEND_API.md`](../github-app/BACKEND_API.md) and
[`../github-app/backend.openapi.json`](../github-app/backend.openapi.json).

| Endpoint | Result |
| --- | --- |
| `POST /v1/analyses` | `202` queued snapshot, before model work. Requires the original PR head and immutable merged commit, a merged timestamp, PR URL/number, and trigger `pull_request_merged`. A complete `code_snapshot` is required. Other repositories return `403`. |
| `GET /v1/analyses/{id}` | `200` current snapshot with full changes and allowed decisions. Unknown IDs return `404`. |
| `POST /v1/analyses/{id}/decisions` | `202` accepted approval in `applying`, or `200` accepted denial/acknowledgment. Requires the exact proposal version, original head SHA, merged SHA, and GitHub actor. |

Source SHAs must be full lowercase 40-character Git SHA-1 values. The App verifies GitHub reports the PR as merged, reads the complete saved PR
file list, and fetches contents at the original PR head and merged commit using
its installation authentication. It sends these as `code_snapshot`, bound to
the same source SHAs. The backend trusts the bearer-authenticated App as its
source provider and checks that the snapshot identity matches the request. It
reconstructs the old text from the saved PR patches locally; it makes no GitHub
requests and requires no `GITHUB_TOKEN`. Installation tokens and private keys
are never included in the payload. The actor comes from the App's verified
webhook; the backend adds no approver role restriction. Invalid requests/actions return `422`; authentication failures
return `401`; stale or competing decisions return `409` without acceptance.

At review, `allowed_decisions` is `["approve", "deny"]`. No-update results have
a version and require `["acknowledge"]`; acknowledgment is stored with its actor.
Creation is not implemented, so the API does not advertise `create`. A fresh
retry uses `POST /v1/analyses` with an incremented attempt and a new key.

The local target variant is explicit:

```json
{
  "kind": "local",
  "path": "selected-runbook.docx",
  "revision_sha256": "<64-character hash of the reviewed DOCX bytes>"
}
```

The GitHub preview labels this as a configured local file. It does not claim a
GitHub repository, branch, URL, or Git blob identity. Repository targets remain
supported by the frontend for future integration.

## Source snapshot

`POST /v1/analyses` now requires a `code_snapshot` object in addition to the
existing source metadata. This is contract version 1.3. Metadata-only starts
return `422`; update the App and backend together.

```json
{
  "head_sha": "<original PR head SHA>",
  "merge_commit_sha": "<immutable merged SHA>",
  "files": [{
    "file_path": "worker.py",
    "previous_file_path": "worker.py",
    "status": "modified",
    "additions": 1,
    "deletions": 1,
    "patch": "@@ -1 +1 @@\n-timeout = 30\n+timeout = 60\n",
    "pr_head_content": "timeout = 60\n",
    "merged_content": "timeout = 60\n"
  }]
}
```

Contents and patches preserve whitespace. `null` contents explicitly identify
binary/non-UTF-8 data. Removed files have empty merged content; deleted text is
reconstructed from the complete saved deletion patch against an empty PR-head
file. Renames carry the previous path. The collector refuses incomplete lists,
missing or truncated text patches, unsupported contents, and snapshots above
10 MiB instead of silently omitting files. The backend validates matching SHAs,
duplicate paths, the file limit, size, and patch consistency.

The App needs Contents read access along with its existing Checks and Pull
requests permissions. Its existing installation credentials fetch source;
no additional personal access token is needed. Source is never fetched from a
moving branch tip. The persisted snapshot is reused across connection retries,
process restarts, and later analysis attempts for the same merge.

Previously prepared, reviewable, or approved backend jobs still use their saved
state. Legacy queued jobs without source data cannot fetch it under this flow:
they fail and need a fresh analysis retry from the updated App.

## Saved state and approval

SQLite (`.data/state.sqlite3`, with WAL and full synchronous writes) stores
requests, prepared code/document inputs, model results, versioned proposals,
decisions with actor, output paths, and exact accepted HTTP response receipts.
Every decision and receipt is committed in the same transaction as the next
workflow step. Repeating a successful POST with the same key/body replays the
original response, even after progress or a restart. A different body for that
key returns `409`. Only one decision can win.

The App saves the complete source snapshot in its SQLite run state before the
first backend POST. Backend requests and their supplied source are persisted
at acceptance. The worker prepares the code context and saves an immutable
`source.docx` before agent execution. An interrupted analysis restarts the agent graph from those
saved inputs; intermediate model calls may be repeated. A completed proposal
awaiting review survives restart without regeneration or terminal `input()`.
Queued jobs and approved application jobs resume automatically on startup.

Proposal versions bind the source identity, document revision, destination,
and full changes. The backend validates exact paragraph replacements before
showing a proposal, and checks the source DOCX and saved snapshot hashes before
accepting the decision. Changed or missing documents become `stale`, requiring
a fresh analysis. Oversized previews fail instead of being silently truncated.

Approval is accepted immediately; the worker then writes
`.data/<analysis_id>/updated.docx` atomically from the immutable snapshot.
The configured original is preserved. If the process exits after writing but
before recording completion, recovery regenerates that job's same output from
the original snapshot, so edits cannot be applied twice. Denial and
acknowledgment perform no update write. Failures are durable and visible as
`failed`; detailed diagnostics stay in backend logs.

Keep the entire data directory for recovery, including DOCX snapshots and
outputs. Do not edit saved snapshots. This implementation does not commit,
push, open a runbook PR, or publish/download the output through GitHub. The
updated file is available locally at the path above; publication is a later
integration step. The code PR is already merged and this check cannot block it.

## Verify

```sh
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
```

Tests exercise HTTP requests, real graph execution and DOCX writes, restart
recovery, accepted receipt replay, competing decisions, stale versions, and
retrieval bypass. Live GitHub/model network calls are blocked in tests.
