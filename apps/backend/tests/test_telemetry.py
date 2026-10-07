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


def test_heartbeat_accepts_the_budget_firmware_payload() -> None:
    response = TestClient(create_app()).post(
        "/api/telemetry",
        headers={"X-API-Key": "dev-only-change-me"},
        json={
            "device_id": "node_1",
            "mq2": 812,
            "temp_c": 27.4,
            "hum_pct": None,
            "warmup_done": True,
            "local_alarm": False,
            "uptime_s": 240,
            "rssi": -58,
            "fw": "0.2.0",
            "flame_ir": False,
            "flame_ir_raw": 3900,
            "silenced": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"buzzer": False, "state": "NORMAL"}


def test_heartbeat_local_alarm_is_adopted() -> None:
    response = TestClient(create_app()).post(
        "/api/telemetry",
        headers={"X-API-Key": "dev-only-change-me"},
        json={
            "device_id": "node_1",
            "mq2": 3500,
            "temp_c": None,
            "warmup_done": True,
            "local_alarm": True,
            "uptime_s": 600,
            "fw": "0.2.0",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"buzzer": True, "state": "ALARM"}
