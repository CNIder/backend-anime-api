import importlib.util
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient


def load_analytics_module(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("BQ_DATASET", "test_dataset")
    monkeypatch.setenv("BQ_TABLE", "test_table")
    app_path = Path(__file__).resolve().parents[3] / "phase_7" / "analytics" / "app.py"
    spec = importlib.util.spec_from_file_location("phase7_analytics_app_user_choice", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeQueryJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeBigQueryClient:
    def __init__(self, rows):
        self._rows = rows

    def query(self, query, job_config=None):
        return FakeQueryJob(self._rows)


def test_user_choice_score_not_found(monkeypatch):
    module = load_analytics_module(monkeypatch)
    monkeypatch.setattr(module, "get_bigquery_client", lambda: FakeBigQueryClient([]))
    client = TestClient(module.app)

    response = client.post("/analytics/anime/user-choice-score", json={"anime_name": "Missing"})

    assert response.status_code == 404


def test_user_choice_score_success(monkeypatch):
    module = load_analytics_module(monkeypatch)
    fake_row = SimpleNamespace(
        name="Naruto",
        score=8.0,
        popularity=20,
        members=100000,
        score_normalized=0.8,
        popularity_normalized=0.9,
        members_normalized=0.7,
    )
    monkeypatch.setattr(module, "get_bigquery_client", lambda: FakeBigQueryClient([fake_row]))
    client = TestClient(module.app)

    response = client.post("/analytics/anime/user-choice-score", json={"anime_name": "Naruto"})

    assert response.status_code == 200
    body = response.json()
    assert body["anime_name"] == "Naruto"
    assert body["user_choice_score"] == 0.81
    assert body["user_choice_label"] == "high"
