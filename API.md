# GitHub App API

The API is a transport and persistence adapter to the existing backend indexer,
retrieval agents, LangGraph workflow, and DOCX writer. The GitHub App sends the
complete merged code snapshot; it never opens, chooses, indexes, or edits runbooks.
New analyses do not supply full document text to the agents. The backend parses
its runbooks with Docling, embeds their chunks, searches Qdrant, and generates
proposals using its existing workflow. Agent prompts, ranking, and editing rules
are unchanged.

## Start locally

Run from the backend root:

```sh
.venv/bin/python -m pip install -r requirements-api.txt
.venv/bin/python -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Keep `BACKEND_TOKEN`, `SOURCE_REPOSITORY`, `OPENAI_API_KEY`, `OPENAI_MODEL`,
`OPENAI_TIMEOUT_SECONDS`, and `BACKEND_DATA_DIR` in `.env`. The App uses the same
shared token; the backend needs no GitHub credential. Model credentials are
required for analysis, not endpoint startup.

Use `RUNBOOK_PATHS` as a JSON array of DOCX paths. If absent, `RUNBOOK_PATH`
selects a single document; with neither set, all `test_data/input/*.docx` files
are selected. Names must be unique. Configure only backend-owned runbooks.

API retrieval defaults to embedded Qdrant at `BACKEND_DATA_DIR/qdrant`, so no
Docker service is required. `QDRANT_URL` instead selects a Qdrant server. The
existing CLI retains its server defaults. First analysis may download the
backend tokenizer/embedding model. Index failures are reported as
`RETRIEVAL_FAILED`; there is no direct-document fallback.

Run one backend process/worker. The process lock prevents competing workers.
The embedded client is shared across the parallel analyzer threads with locked
access. `GET /health` reports retrieval enabled; `/docs` exposes the contract.
Cloudflare exposes the GitHub App on port 3000, not the backend on port 8000.

## Endpoints and document decisions

All `/v1` calls require `Authorization: Bearer <BACKEND_TOKEN>`. Every POST
requires `Idempotency-Key`. Schema version 1.4 is in `openapi.json` and the
identical App contract `../github-app/backend.openapi.json`.

| Endpoint | Behavior |
| --- | --- |
| `POST /v1/analyses` | Queue analysis using the App's saved source snapshot. |
| `GET /v1/analyses/{id}` | Return analysis progress and all document proposals. |
| `POST /v1/analyses/{id}/proposals/{proposal_id}/decisions` | Approve or deny one document. |
| `POST /v1/analyses/{id}/decisions` | Acknowledge an overall no-update result, or decide a saved legacy single-document job. |

Source requests retain the v1.3 complete `code_snapshot`, source head/merge SHAs,
PR metadata, and merged trigger. Code whitespace and complete PR patches are
preserved. Snapshot limits remain 10 MiB and 3000 files. No installation tokens
or private keys are forwarded. The backend trusts the authenticated App as its
source provider and reconstructs old source locally.

New results include `decision_scope: "document"`. Every affected document has
one proposal with its ID, local target/revision, and complete current/proposed
passages. Extra fields are:

- `review_status`: `pending`, `approved`, or `denied`.
- `save_status`: `not_started`, `saving`, `saved`, or `failed`.
- `decision`: accepted `action` and `actor`, after a decision.
- `result.output_path`: exact local output after saving.
- `error`: document-specific save failure when applicable.

Document decision bodies use the existing fields: `decision` (`approve` or
`deny`), `proposal_version`, `head_sha`, `merge_commit_sha`, and `actor`.
A success returns `202` with `{accepted: true, analysis: ...}`. Each decision
has its own idempotent receipt. A duplicate key/body replays that original
response; changed bodies or conflicting decisions return `409`.

One approval does not start writing. The overall status remains
`awaiting_decision` until every affected document is approved or denied. Then
it becomes `applying` if any were approved, or `rejected` if all were denied.
Only approved documents are written. Mixed approvals and denials are supported.
No proposals means `no_update_needed` with `acknowledge`, and no output writes.
Whole-analysis approval is rejected for new document-scoped proposals.

The proposal version binds the source, saved document revisions, and edits.
Decision changes do not change that version. Original documents and snapshots
are checked before approval; approved documents are checked again before the
batch save. Changed originals become `stale` and require new analysis/approval.
Invalid auth returns `401`, wrong repository `403`, unknown analysis/proposal
`404`, and unsupported input/actions `422`.

## State, outputs, and recovery

SQLite stores source, document manifests, analysis results, individual decisions,
and exact HTTP receipts. Each analysis saves original-named documents under
`.data/<id>/sources/` and indexes those copies into its own persistent Qdrant
collection. Later analyses cannot replace that evidence. Interrupted indexing
can rebuild from saved copies. Reviewable analyses are not regenerated on restart.

The worker validates every approved document before writing. Outputs are
`.data/<id>/outputs/<original-name>.docx`; the input documents stay untouched.
The existing writer atomically replaces each output file. A save receipt is
persisted per document; restart skips completed saves. Recovery from an exit
between file publication and receipt persistence recreates the same output from
the original snapshot, without editing an already edited input.

A failed save records its document error and preserves other successful copies.
The analysis never claims all outputs were saved when some failed. Retry analysis
creates a fresh attempt and requires fresh decisions; old outputs remain available.
Legacy stored analyses preserve their single-document decisions and
`.data/<id>/updated.docx` outputs. No state migration or automatic reanalysis occurs.

Reviews are limited per document to fit complete GitHub comments. Oversized
content fails explicitly rather than truncating passages. The aggregate response
has a 1 MiB limit. Keep the entire data directory, including the vector store,
snapshots, and outputs, for recovery. No GitHub publication is performed.

## Verification

```sh
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
```

Tests cover legacy jobs, retrieval delegation/isolation, document decisions,
partial approvals, waits before writing, restart recovery, stale documents,
HTTP receipts, and failures. External services are mocked in the regression suite;
the separate local smoke test exercises real parsing, embeddings, and retrieval.
