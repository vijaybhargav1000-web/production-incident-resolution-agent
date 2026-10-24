


from typing import Literal

from fastapi import FastAPI, HTTPException
from ollama import Client
from pydantic import BaseModel, Field


# --------------------------------------------------
# 1. Application setup
# --------------------------------------------------

app = FastAPI(
    title="Production Incident Resolution Agent",
    description="AI-powered investigation of data pipeline failures",
    version="0.4.0",
)

ollama_client = Client(host="http://localhost:11434")


# --------------------------------------------------
# 2. Request and response models
# --------------------------------------------------

class IncidentRequest(BaseModel):
    incident_id: str = Field(min_length=1)
    pipeline_name: str = Field(min_length=1)
    logs: list[str] = Field(min_length=1)


class IncidentAnalysis(BaseModel):
    root_cause: str
    evidence: list[str]
    recommended_actions: list[str]
    severity: Literal["low", "medium", "high", "unknown"]
    confidence: float = Field(ge=0, le=1)
    requires_human_approval: bool


# --------------------------------------------------
# 3. Investigation tool
# --------------------------------------------------

def investigate_logs(logs: list[str]) -> dict:
    """Identify a likely failure category using log patterns."""

    text = " ".join(logs).lower()

    if (
        "schema mismatch" in text
        or "delta_schema_mismatch" in text
    ):
        return {
            "category": "schema_mismatch",
            "evidence": [
                log for log in logs
                if "schema" in log.lower()
            ],
            "next_check": (
                "Compare the incoming schema with the target schema."
            ),
        }

    if (
        "access denied" in text
        or "accessdenied" in text
        or "permission denied" in text
    ):
        return {
            "category": "permission_error",
            "evidence": [
                log for log in logs
                if any(
                    term in log.lower()
                    for term in [
                        "access denied",
                        "accessdenied",
                        "permission denied",
                    ]
                )
            ],
            "next_check": (
                "Review the identity, resource policy, "
                "and required permissions."
            ),
        }

    if (
        "outofmemoryerror" in text
        or "java heap space" in text
    ):
        return {
            "category": "memory_error",
            "evidence": [
                log for log in logs
                if (
                    "outofmemoryerror" in log.lower()
                    or "java heap space" in log.lower()
                )
            ],
            "next_check": (
                "Inspect Spark stages, executor memory, "
                "and possible data skew."
            ),
        }

    return {
        "category": "unknown",
        "evidence": [],
        "next_check": (
            "Collect more logs and inspect the failed job details."
        ),
    }


# --------------------------------------------------
# 4. Basic endpoints
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Production Incident Resolution Agent is running!"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# --------------------------------------------------
# 5. AI-powered incident investigation
# --------------------------------------------------

@app.post("/incidents/investigate")
def investigate_incident(incident: IncidentRequest):

    # Step 1: Run the investigation tool
    tool_result = investigate_logs(incident.logs)

    # Step 2: Prepare the prompt using tool findings
   
    prompt = f"""
You are a production data engineering incident investigation agent.

Analyze the incident using the logs and preliminary tool findings.

Incident ID: {incident.incident_id}
Pipeline: {incident.pipeline_name}
Tool findings: {tool_result}
Logs:
{chr(10).join(incident.logs)}

Instructions:
- Use the tool category as the initial hypothesis when it matches the logs.
- For schema_mismatch, identify a possible source-target schema mismatch.
- Do not claim the exact column or data type is known unless logs show it.
- Include the actual log line in evidence.
- Use the tool's next_check as a recommended action.
- If a failure category is recognized, do not label it unknown merely
  because the exact underlying cause is not yet confirmed.
- Use severity "unknown" if business impact is not available.
- Set confidence between 0 and 1 to reflect the evidence.
- This is an estimate, not a calibrated probability.
- Set requires_human_approval to true.
- Do not execute fixes.

Return the required structured JSON.
"""


    # Step 3: Ask the local LLM for structured analysis
    try:
        response = ollama_client.chat(
            model="llama3.2:3b",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format=IncidentAnalysis.model_json_schema(),
            options={"temperature": 0},
        )

        analysis = IncidentAnalysis.model_validate_json(
            response.message.content
        )

        # Enforce approval for any future recovery workflow
        analysis.requires_human_approval = True

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "AI analysis failed. Check that Ollama is running "
                f"and the model is available. Details: {exc}"
            ),
        )

    # Enforce the deterministic finding when the tool recognizes a category
    category = tool_result["category"]

    if category == "schema_mismatch":
        analysis.root_cause = (
            "Possible source-target schema mismatch"
        )
        analysis.recommended_actions = [
            tool_result["next_check"]
        ]

    elif category == "permission_error":
        analysis.root_cause = (
            "Possible access or permission failure"
        )
        analysis.recommended_actions = [
            tool_result["next_check"]
        ]

    elif category == "memory_error":
        analysis.root_cause = (
            "Possible Spark memory failure"
        )
        analysis.recommended_actions = [
            tool_result["next_check"]
        ]

    else:
        analysis.root_cause = (
            "Root cause not identified; further investigation required"
        )
        analysis.confidence = min(analysis.confidence, 0.2)
    
    # Step 4: Return both tool findings and AI analysis
    return {
        "incident_id": incident.incident_id,
        "pipeline_name": incident.pipeline_name,
        "tool_result": tool_result,
        "analysis": analysis.model_dump(),
        "automatic_fix": False,
    }
