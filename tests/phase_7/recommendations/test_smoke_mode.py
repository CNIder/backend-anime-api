import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient


def load_recommendations_module(monkeypatch):
    monkeypatch.setenv("RECOMMENDATIONS_MODE", "smoke")
    app_path = Path(__file__).resolve().parents[3] / "phase_7" / "recommendations" / "app.py"
    spec = importlib.util.spec_from_file_location("phase7_recommendations_app_smoke", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recommendations_health_smoke_mode(monkeypatch):
    module = load_recommendations_module(monkeypatch)
    client = TestClient(module.app)

    response = client.get("/recommendations/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] == "smoke"


def test_recommendations_post_smoke_mode(monkeypatch):
    module = load_recommendations_module(monkeypatch)
    monkeypatch.setattr(module, "get_user_choice", lambda anime_name: {"user_choice_score": 0.75})
    client = TestClient(module.app)

    response = client.post("/recommendations", json={"anime_name": "Naruto"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "smoke"
    assert body["input_anime"]["anime"] == "Naruto"
    assert body["input_anime"]["user_choice_score"] == 0.75
