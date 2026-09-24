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


def test_audio_queue_and_insights_fallback():
    with TestClient(app) as client:
        meeting = client.post("/api/meetings", json={"title": "Kiểm thử âm thanh"}).json()
        queued = client.post(
            f"/api/meetings/{meeting['id']}/audio",
            data={"speaker": "Minh"},
            files={"file": ("sample.webm", b"fake-audio", "audio/webm")},
        )
        assert queued.status_code == 202
        assert queued.json()["status"] == "saved"

        segment = {
            "meeting_id": meeting["id"], "speaker": "Minh", "original": "Xin chào",
            "translation": "", "language": "vi", "confidence": 0.91, "offset_ms": 0,
        }
        created = client.post(f"/api/meetings/{meeting['id']}/segments", json=segment)
        assert created.status_code == 201
        assert created.json()["translation"] == "Xin chào"
        insight = client.get(f"/api/meetings/{meeting['id']}/insights")
        assert insight.status_code == 200
        assert "Xin chào" in insight.json()["summary"]


def test_rejects_non_audio_upload():
    with TestClient(app) as client:
        meeting = client.post("/api/meetings", json={"title": "Kiểm thử file"}).json()
        response = client.post(
            f"/api/meetings/{meeting['id']}/audio",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 415
