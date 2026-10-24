
import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from ollama import Client
from pydantic import BaseModel, Field, field_validator


# 1. Application setup and logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("incident_agent")

app = FastAPI(
    title="Production Incident Resolution Agent",
    description="AI-powered investigation of data pipeline failures",
    version="0.5.0",
)

ollama_client = Client(host="http://localhost:11434")


# 2. Request and response models
class IncidentRequest(BaseModel):
    incident_id: str = Field(min_length=1, max_length=100)
    pipeline_name: str = Field(min_length=1, max_length=200)
    logs: list[str] = Field(min_length=1, max_length=50)

    @field_validator("incident_id", "pipeline_name")
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be blank.")

        return value

    @field_validator("logs")
    @classmethod
    def validate_logs(cls, logs: list[str]) -> list[str]:
        cleaned_logs = [log.strip() for log in logs]

        if any(not log for log in cleaned_logs):
            raise ValueError("Log entries cannot be blank.")

        if any(len(log) > 5000 for log in cleaned_logs):
            raise ValueError(
                "Each log entry must be 5000 characters or fewer."
            )

        return cleaned_logs


class IncidentAnalysis(BaseModel):
    root_cause: str
    evidence: list[str]
    recommended_actions: list[str]
    severity: Literal["low", "medium", "high", "unknown"]
    confidence: float = Field(ge=0, le=1)
    requires_human_approval: bool


# 3. Rule-based investigation tools
def investigate_logs(logs: list[str]) -> dict:
    """Select an investigation tool based on the supplied logs."""

    text = " ".join(logs).lower()

    if "schema mismatch" in text or "delta_schema_mismatch" in text:
        tool_name = "schema_investigation"
        result = {
            "category": "schema_mismatch",
            "evidence": [
                log for log in logs if "schema" in log.lower()
            ],
            "findings": (
                "The logs indicate a possible source-target schema mismatch."
            ),
            "next_check": (
                "Compare incoming and target schemas, including "
                "column names and data types."
            ),
        }

    elif any(
        term in text
        for term in (
            "access denied",
            "accessdenied",
            "permission denied",
        )
    ):
        tool_name = "permission_investigation"
        result = {
            "category": "permission_error",
            "evidence": [
                log for log in logs
                if any(
                    term in log.lower()
                    for term in (
                        "access denied",
                        "accessdenied",
                        "permission denied",
                    )
                )
            ],
            "findings": (
                "The logs indicate a possible access or permission failure."
            ),
            "next_check": (
                "Check the execution identity, IAM policies, bucket "
                "policy, and required permissions."
            ),
        }

    elif (
        "outofmemoryerror" in text
        or "java heap space" in text
    ):
        tool_name = "memory_investigation"
        result = {
            "category": "memory_error",
            "evidence": [
                log for log in logs
                if (
                    "outofmemoryerror" in log.lower()
                    or "java heap space" in log.lower()
                )
            ],
            "findings": (
                "The logs indicate a possible Spark memory failure."
            ),
            "next_check": (
                "Inspect Spark stages, executor memory, partition "
                "sizes, and data skew."
            ),
        }

    else:
        tool_name = "general_investigation"
        result = {
            "category": "unknown",
            "evidence": logs,
            "findings": (
                "The available logs do not match a recognized failure pattern."
            ),
            "next_check": (
                "Collect additional logs and inspect the failed job details."
            ),
        }

    return {
        "selected_tool": tool_name,
        **result,
    }


# 4. Basic API endpoints
@app.get("/")
def home():
    return {
        "message": "Production Incident Resolution Agent is running!"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# 5. AI-powered incident investigation
@app.post("/incidents/investigate")
def investigate_incident(incident: IncidentRequest):
    logger.info("Incident received: %s", incident.incident_id)

    # Step 1: Select the investigation tool
    tool_result = investigate_logs(incident.logs)

    logger.info(
        "Investigation tool selected: %s",
        tool_result["selected_tool"],
    )

    # Step 2: Prepare the LLM prompt
    prompt = f"""
You are a production data engineering incident investigation agent.

Incident ID: {incident.incident_id}
Pipeline: {incident.pipeline_name}

Selected investigation tool and findings:
{tool_result}

Original logs:
{chr(10).join(incident.logs)}

Instructions:
- Treat tool findings as a hypothesis, not absolute proof.
- Cite evidence from the original logs.
- Do not invent facts or claim a fix was applied.
- Recommend investigation steps before recovery.
- Set confidence from 0 to 1 based on the evidence.
- Set requires_human_approval to true.
- Use severity low, medium, high, or unknown.
- Do not execute any fixes.
- Return structured JSON matching the requested schema.
"""

    try:
        # Step 3: Call the local LLM
        response = ollama_client.chat(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": prompt}],
            format=IncidentAnalysis.model_json_schema(),
            options={"temperature": 0},
        )

        analysis = IncidentAnalysis.model_validate_json(
            response.message.content
        )

        # Step 4: Enforce deterministic root-cause classification
        category = tool_result["category"]

        if category == "schema_mismatch":
            analysis.root_cause = (
                "Possible source-target schema mismatch"
            )

        elif category == "permission_error":
            analysis.root_cause = (
                "Possible access or permission failure"
            )

        elif category == "memory_error":
            analysis.root_cause = (
                "Possible Spark memory failure"
            )

        else:
            analysis.root_cause = (
                "Root cause not identified; "
                "further investigation required"
            )
            analysis.confidence = min(analysis.confidence, 0.2)

        # Step 5: Use the investigation tool's recommended next step
        analysis.recommended_actions = [tool_result["next_check"]]

        # Step 6: Require human review; never apply automatic fixes
        analysis.requires_human_approval = True

    except Exception:
        logger.exception(
            "AI investigation failed for incident: %s",
            incident.incident_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "AI investigation failed. Check that Ollama is running, "
                "the model is available, and the response is valid."
            ),
        )

    logger.info(
        "Investigation completed for incident: %s",
        incident.incident_id,
    )

    return {
        "incident_id": incident.incident_id,
        "pipeline_name": incident.pipeline_name,
        "tool_result": tool_result,
        "analysis": analysis.model_dump(),
        "automatic_fix": False,
    }

