from app import scoring


def test_model_status_explicitly_reports_fallback(monkeypatch):
    monkeypatch.setattr(scoring, "MODEL_PATH", "missing-model.pkl")
    monkeypatch.setattr(scoring, "_trained_model", None)
    monkeypatch.setattr(scoring, "_trained_model_load_attempted", False)
    monkeypatch.setattr(scoring, "_trained_model_metadata", None)

    status = scoring.model_status()

    assert status["mode"] == "heuristic"
    assert status["model_version"] == "landslide_heuristic_v0"
