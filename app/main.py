from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import Health, Meeting, MeetingCreate, MeetingStatus, TranscriptSegment
from app.store import MemoryStore

VERSION = "0.1.0"
store = MemoryStore()


class Connections:
    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, meeting_id: str, socket: WebSocket) -> None:
        await socket.accept()
        self.rooms.setdefault(meeting_id, set()).add(socket)

    def disconnect(self, meeting_id: str, socket: WebSocket) -> None:
        self.rooms.get(meeting_id, set()).discard(socket)

    async def publish(self, meeting_id: str, payload: dict) -> None:
        stale = []
        for socket in self.rooms.get(meeting_id, set()).copy():
            try:
                await socket.send_json(payload)
            except RuntimeError:
                stale.append(socket)
        for socket in stale:
            self.disconnect(meeting_id, socket)


connections = Connections()


@asynccontextmanager
async def lifespan(_: FastAPI):
    demo = await store.create_meeting(MeetingCreate(title="Product Sync — APAC", target_language="vi"))
    await store.set_status(demo.id, MeetingStatus.live)
    yield


app = FastAPI(title="ScribeAI", version=VERSION, lifespan=lifespan)


@app.get("/api/health", response_model=Health)
async def health() -> Health:
    return Health(status="healthy", version=VERSION, event_bus="redis-streams" if os.getenv("REDIS_URL") else "memory")


@app.get("/api/meetings", response_model=list[Meeting])
async def list_meetings() -> list[Meeting]:
    return await store.list_meetings()


@app.post("/api/meetings", response_model=Meeting, status_code=201)
async def create_meeting(payload: MeetingCreate) -> Meeting:
    return await store.create_meeting(payload)


@app.post("/api/meetings/{meeting_id}/status/{status}", response_model=Meeting)
async def change_status(meeting_id: str, status: MeetingStatus) -> Meeting:
    meeting = await store.set_status(meeting_id, status)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    await connections.publish(meeting_id, {"type": "status", "data": meeting.model_dump(mode="json")})
    return meeting


@app.get("/api/meetings/{meeting_id}/transcript", response_model=list[TranscriptSegment])
async def transcript(meeting_id: str) -> list[TranscriptSegment]:
    if not await store.get_meeting(meeting_id):
        raise HTTPException(404, "Meeting not found")
    return await store.get_transcript(meeting_id)


@app.post("/api/meetings/{meeting_id}/segments", response_model=TranscriptSegment, status_code=201)
async def ingest_segment(meeting_id: str, segment: TranscriptSegment) -> TranscriptSegment:
    if meeting_id != segment.meeting_id or not await store.get_meeting(meeting_id):
        raise HTTPException(404, "Meeting not found")
    await store.add_segment(segment)
    await connections.publish(meeting_id, {"type": "segment", "data": segment.model_dump(mode="json")})
    return segment


@app.websocket("/ws/meetings/{meeting_id}")
async def meeting_stream(socket: WebSocket, meeting_id: str) -> None:
    await connections.connect(meeting_id, socket)
    try:
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        connections.disconnect(meeting_id, socket)


web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(web_dir / "index.html")
