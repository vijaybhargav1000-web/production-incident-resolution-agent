
# Production Incident Resolution Agent

An AI-assisted incident investigation API for data engineering pipelines. It classifies common failures, gathers relevant log evidence, and uses a local LLM to generate structured investigation results.

## Features

- FastAPI REST API
- Rule-based investigation tool selection
- Local LLM analysis using Ollama and Llama 3.2
- Pydantic input and output validation
- Structured application logging
- Human approval required for remediation
- No automatic fixes are executed
- Automated tests using pytest

## Architecture

```text
Client / Swagger UI
        |
        v
FastAPI REST API
        |
        v
Pydantic Input Validation
        |
        v
Rule-Based Investigation
        |
        +--> Schema Investigation
        +--> Permission Investigation
        +--> Memory Investigation
        +--> General Investigation
        |
        v
Local Ollama LLM
        |
        v
Structured Incident Analysis
        |
        v
Human Review Required
```

## Technology Stack

- Python
- FastAPI
- Pydantic
- Ollama
- Llama 3.2 (3B)
- pytest
- HTTPX / FastAPI TestClient

## Prerequisites

- Python installed
- Git installed
- Ollama installed
- The `llama3.2:3b` model downloaded in Ollama

## Setup

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install fastapi "uvicorn[standard]" ollama pytest httpx
```

Download the model if it is not already installed:

```powershell
ollama pull llama3.2:3b
```

Start the API:

```powershell
python -m uvicorn main:app --reload
```

Open Swagger UI:

http://127.0.0.1:8000/docs

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Application welcome message |
| GET | `/health` | Basic API health response |
| POST | `/incidents/investigate` | Investigate an incident |

## Example Request

```json
{
  "incident_id": "INC-101",
  "pipeline_name": "customer_etl",
  "logs": [
    "DELTA_SCHEMA_MISMATCH: incoming schema differs from target"
  ]
}
```

## Investigation Scenarios

| Scenario | Selected tool |
|---|---|
| Schema mismatch | `schema_investigation` |
| Access or permission failure | `permission_investigation` |
| Spark memory error | `memory_investigation` |
| Unrecognized failure | `general_investigation` |

## Run Automated Tests

```powershell
python -m pytest -v
```

The current test suite covers the API welcome and health endpoints, all four rule-based classifications, and invalid input cases.

## Safety

- The agent does not apply automatic fixes.
- Human approval is required.
- The root-cause classification is a hypothesis, not proof.
- Unknown incidents are marked for further investigation.
- Input validation limits incident identifiers, pipeline names, log count, and individual log size.

## Current Limitations

This is a production-oriented portfolio prototype, not a fully deployed production incident management platform.

- Investigation tools classify supplied logs using rules; they do not query live AWS or Databricks resources.
- The LLM runs locally through Ollama.
- Severity and confidence require further calibration and evaluation.
- Authentication, authorization, persistent incident storage, and deployment infrastructure are not implemented.
- The health endpoint checks API responsiveness, not Ollama availability.

## Future Improvements

- Integrate with real AWS and Databricks monitoring APIs.
- Add structured incident storage and audit history.
- Add authentication and authorization.
- Add LLM evaluation, metrics, and alerting.
- Add deployment and CI/CD automation.
