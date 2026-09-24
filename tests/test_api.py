from fastapi.testclient import TestClient

from app.main import app


def test_health_and_meeting_flow():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        created = client.post("/api/meetings", json={"title": "Design Review", "target_language": "en"})
        assert created.status_code == 201
        meeting = created.json()

        started = client.post(f"/api/meetings/{meeting['id']}/status/live")
        assert started.json()["status"] == "live"

        segment = {
            "meeting_id": meeting["id"], "speaker": "Linh", "original": "Chào mọi người",
            "translation": "Hello everyone", "language": "vi", "confidence": 0.97, "offset_ms": 1200,
        }
        assert client.post(f"/api/meetings/{meeting['id']}/segments", json=segment).status_code == 201
        transcript = client.get(f"/api/meetings/{meeting['id']}/transcript").json()
        assert transcript[0]["translation"] == "Hello everyone"


def test_missing_meeting_returns_404():
    with TestClient(app) as client:
        assert client.get("/api/meetings/missing/transcript").status_code == 404

