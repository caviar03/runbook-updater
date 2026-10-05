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
