import importlib.util
from pathlib import Path


def load_recommendations_module(monkeypatch):
    monkeypatch.setenv("RECOMMENDATIONS_MODE", "smoke")
    app_path = Path(__file__).resolve().parents[3] / "phase_7" / "recommendations" / "app.py"
    spec = importlib.util.spec_from_file_location("phase7_recommendations_app", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_text_handles_empty_values(monkeypatch):
    module = load_recommendations_module(monkeypatch)
    assert module.safe_text(None) == ""
    assert module.safe_text("UNKNOWN") == ""
    assert module.safe_text("  Action  ") == "Action"


def test_anime_to_text(monkeypatch):
    module = load_recommendations_module(monkeypatch)
    text = module.anime_to_text(("Naruto", "Action", "Pierrot"))
    assert "Title: Naruto" in text
    assert "Genres: Action" in text
    assert "Studios: Pierrot" in text
