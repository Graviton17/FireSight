from fastapi.testclient import TestClient

from firesight_backend.main import create_app


def test_health_endpoint_is_live() -> None:
    response = TestClient(create_app()).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
