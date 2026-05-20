import pytest

from app.services.model_service import ModelService


def test_load_raises_when_model_file_missing(tmp_path) -> None:
    missing_path = tmp_path / "does-not-exist.joblib"
    service = ModelService(model_path=str(missing_path), model_version="v0.2.0")

    with pytest.raises(FileNotFoundError) as excinfo:
        service.load()

    assert str(missing_path) in str(excinfo.value)


def test_load_raises_on_corrupt_model_file(tmp_path) -> None:
    bad_path = tmp_path / "bad.joblib"
    bad_path.write_bytes(b"this is not a valid joblib payload")
    service = ModelService(model_path=str(bad_path), model_version="v0.2.0")

    with pytest.raises(Exception):
        service.load()


def test_predict_before_load_raises() -> None:
    from app.schemas.prediction import RiskScoreRequest

    service = ModelService(model_path="any", model_version="v0.2.0")
    req = RiskScoreRequest(income=1000, age=30, debt=100, employment_years=1)

    with pytest.raises(RuntimeError):
        service.predict(req)
