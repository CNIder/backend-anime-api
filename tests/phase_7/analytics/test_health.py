import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient


def load_analytics_module(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("BQ_DATASET", "test_dataset")
    monkeypatch.setenv("BQ_TABLE", "test_table")
    app_path = Path(__file__).resolve().parents[3] / "phase_7" / "analytics" / "app.py"
    spec = importlib.util.spec_from_file_location("phase7_analytics_app", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analytics_health(monkeypatch):
    module = load_analytics_module(monkeypatch)
    client = TestClient(module.app)

    response = client.get("/analytics/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["table"] == "test-project.test_dataset.test_table"
