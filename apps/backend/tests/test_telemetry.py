from fastapi.testclient import TestClient

from firesight_backend.main import create_app


def test_heartbeat_returns_warmup_command() -> None:
    response = TestClient(create_app()).post(
        "/api/telemetry",
        headers={"X-API-Key": "dev-only-change-me"},
        json={
            "device_id": "node_1",
            "mq2": 900,
            "temp_c": 28,
            "hum_pct": 55,
            "warmup_done": False,
            "uptime_s": 15,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"buzzer": False, "state": "WARMUP"}


def test_heartbeat_rejects_an_invalid_key() -> None:
    response = TestClient(create_app()).post(
        "/api/telemetry",
        headers={"X-API-Key": "invalid"},
        json={
            "device_id": "node_1",
            "mq2": 900,
            "warmup_done": True,
            "uptime_s": 15,
        },
    )

    assert response.status_code == 401
