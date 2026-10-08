The GitHub App API is implemented with durable SQLite state and direct DOCX input.
The App supplies the complete merged source snapshot using its existing App
credentials; the HTTP backend does not need `GITHUB_TOKEN` or fetch GitHub itself.
The CLI instructions below describe a separate legacy entry point.
See [API.md](API.md) for configuration, endpoints, and restart behavior.
Use `requirements-api.txt` to run this path without retrieval dependencies.

Local Development Setup

Follow the steps below to run the project locally.

Prerequisites

Before setting up the project, make sure you have the following installed:

Python 3.12 or later
Git
An OpenAI API key

You can verify your Python installation with:

python3 --version

You should see Python 3.12 or later.

Verify Git with:

git --version

1. Clone the Repository

Clone the repository:

git clone https://github.com/caviar03/runbook-updator.git

Navigate into the project directory:

cd runbook-updator

2. Create a Python Virtual Environment

Creating a virtual environment keeps the project's dependencies isolated from other Python projects on your machine.

Run:

python3 -m venv .venv

This creates a .venv directory inside the project.

macOS / Linux

Activate the virtual environment:

source .venv/bin/activate
Windows

If using Command Prompt:

.venv\Scripts\activate

If using PowerShell:

.venv\Scripts\Activate.ps1

After activation, your terminal should show something similar to:

(.venv) user@computer runbook-updator %

Verify that Python is using the virtual environment:

which python

On Windows:

where python

The path should point to the project's .venv directory.

3. Upgrade pip

With the virtual environment activated, upgrade pip:

python -m pip install --upgrade pip 4. Install Project Dependencies

Install all required Python packages from requirements.txt:

pip install -r requirements.txt

This installs the dependencies required by the project, including:

LangChain
LangGraph
LangChain OpenAI integration
Pydantic
Python dotenv
Python DOCX

5. Configure Your OpenAI API Key

Create a .env file in the project root:

Copy `.env.example` to `.env` and fill `OPENAI_API_KEY`, `GITHUB_TOKEN`,
`GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_PR_NUMBER`, and
`GITHUB_MERGE_COMMIT_SHA`. The PR must already be merged at the supplied
commit. The saved PR file patches supply the complete change across normal,
squash, and rebase merges; the old source context is reconstructed against
the original PR head.

The CLI now indexes and analyzes all `test_data/input/*.docx` runbooks before
starting its workflow. Set `RUNBOOK_PATHS` to a JSON array to select different
files, and `RUNBOOK_OUTPUT_DIR` for approved copies (default `test_data/output`).
The CLI requires the full retrieval dependencies and a running Qdrant service.

The HTTP API remains separate: `RUNBOOK_PATH` selects one local DOCX and the
App supplies the merged code snapshot. It bypasses retrieval and writes approved
copies under `.data/<analysis_id>/updated.docx`. See [API.md](API.md). Repository
publication is not implemented yet.

6. Run the Application

Make sure you are in the project root directory:

runbook-updator/

Make sure the virtual environment is activated:

(.venv)

Then run:

python -m src.main

The application will execute the LangGraph workflow.

The workflow will:

Start the orchestrator.
Review the code changes.
Analyze the runbook.
Review the analysis.
Generate proposed runbook changes.
Ask for human approval.
Apply the approved changes.
Produce the updated runbook.

Both analyzers receive the code review, labelled runbook evidence, and
rework feedback. The first checks factual accuracy; the second checks operational
procedures. Proposals identify the target runbook and section for each change. A no-update result exits without prompting or writing.
Both analyzers rerun on rework, with a default limit of three analysis
attempts. The CLI's `edit` response supplies feedback for a new analysis;
`no` performs no document write. Approval uses the configured document
and output paths.

Approved DOCX edits must each match exactly once within a paragraph or
table-cell paragraph, using the proposed section to distinguish repeated text.
Multi-document changes route to the named runbook, and every document is validated
before output copies are saved. Flattened table changes require every changed
cell to match. The writer preserves surrounding runs and their
formatting and refuses missing/ambiguous text or edits overlapping fields
or images. It saves atomically after all edits succeed. Split changes to
multiple paragraphs into separate proposal entries.

Workflow regression tests

```sh
python -m pip install -r requirements-test.txt
python -m pytest -q
```

Tests use real LangGraph execution and DOCX files with mocked model,
retrieval, and GitHub responses. They block network requests and do not
require live API credentials or an embedding model download. The smaller
test requirements do not install Docling or FastEmbed; install the full
`requirements.txt` to run live parsing/retrieval.
