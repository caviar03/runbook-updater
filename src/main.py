from src.graph import workflow
from test_data.input.old_code import old_code
from test_data.input.current_code import current_code
from test_data.input.runbook_text import runbook
from src.graph.workflow import build_workflow


def main():

    app = build_workflow()

    initial_state = {
    "old_code": old_code,
    "current_code": current_code,
    "runbook": runbook,
    "code_review": None,
    "runbook_review": None,
    "orchestrator_decision": None,
    "change_proposal": None,
    "orchestrator_feedback": "",
    "analysis_attempts": 0,
    }

    result = app.invoke(initial_state)

    print("\nWORKFLOW COMPLETE")
    print(result)


if __name__ == "__main__":
    main()