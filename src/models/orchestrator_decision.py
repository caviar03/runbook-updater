from pydantic import BaseModel, Field

class orchestratorDecision(BaseModel):
    proceed: bool = Field(description="Whether the workflow should proceed to creating a runbook change proposal")
    reasoning: str = Field(description="Why the orchestrator made this decision")
    feedback: str = Field(description="Feedback for the Runbook Analyzer if rework is required" )