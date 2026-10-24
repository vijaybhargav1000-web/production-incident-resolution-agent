
from fastapi.testclient import TestClient

from main import app, investigate_logs

client = TestClient(app)


def test_home_endpoint():
    response = client.get("/")
    assert response.status_code == 200


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_schema_mismatch_selects_schema_tool():
    result = investigate_logs([
        "DELTA_SCHEMA_MISMATCH: incoming schema differs from target"
    ])
    assert result["selected_tool"] == "schema_investigation"
    assert result["category"] == "schema_mismatch"


def test_permission_error_selects_permission_tool():
    result = investigate_logs([
        "AccessDenied: User is not authorized to access the S3 bucket"
    ])
    assert result["selected_tool"] == "permission_investigation"
    assert result["category"] == "permission_error"


def test_memory_error_selects_memory_tool():
    result = investigate_logs([
        "java.lang.OutOfMemoryError: Java heap space"
    ])
    assert result["selected_tool"] == "memory_investigation"
    assert result["category"] == "memory_error"


def test_unknown_error_selects_general_tool():
    result = investigate_logs([
        "Unexpected failure while processing batch 4821"
    ])
    assert result["selected_tool"] == "general_investigation"
    assert result["category"] == "unknown"


def test_blank_incident_id_is_rejected():
    response = client.post(
        "/incidents/investigate",
        json={
            "incident_id": "   ",
            "pipeline_name": "customer_etl",
            "logs": ["Some error"],
        },
    )
    assert response.status_code == 422


def test_blank_log_is_rejected():
    response = client.post(
        "/incidents/investigate",
        json={
            "incident_id": "INC-TEST",
            "pipeline_name": "customer_etl",
            "logs": [""],
        },
    )
    assert response.status_code == 422


def test_oversized_log_is_rejected():
    response = client.post(
        "/incidents/investigate",
        json={
            "incident_id": "INC-TEST",
            "pipeline_name": "customer_etl",
            "logs": ["a" * 5001],
        },
    )
    assert response.status_code == 422
