from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root():
    response = client.get("/")

    assert response.status_code == 204
    assert response.json() == {"status": "ok"}
