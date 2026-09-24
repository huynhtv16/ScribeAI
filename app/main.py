from contextlib import asynccontextmanager
from pathlib import Path
import shutil

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.event_bus import EventBus
from app.models import AudioJob, Health, Meeting, MeetingCreate, MeetingInsights, MeetingStatus, TranscriptSegment
from app.services import TranslationService
from app.store import MemoryStore, PostgresStore, Store

VERSION = "0.2.0"
settings = get_settings()
store: Store = PostgresStore(settings.database_url) if settings.database_url else MemoryStore()
event_bus = EventBus(settings.redis_url)
translator = TranslationService(settings)


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
            try: await socket.send_json(payload)
            except RuntimeError: stale.append(socket)
        for socket in stale: self.disconnect(meeting_id, socket)


connections = Connections()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await store.connect()
    await event_bus.connect()
    if not await store.list_meetings():
        demo = await store.create_meeting(MeetingCreate(title="Đồng bộ sản phẩm — APAC", target_language="vi"))
        await store.set_status(demo.id, MeetingStatus.live)
    yield
    await event_bus.close()
    await store.close()


app = FastAPI(title="ScribeAI", description="Trợ lý cuộc họp AI đa ngôn ngữ", version=VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health", response_model=Health)
async def health() -> Health:
    return Health(status="healthy", version=VERSION, event_bus="redis-streams" if event_bus.redis else "memory")


@app.get("/api/meetings", response_model=list[Meeting])
async def list_meetings() -> list[Meeting]: return await store.list_meetings()


@app.post("/api/meetings", response_model=Meeting, status_code=201)
async def create_meeting(payload: MeetingCreate) -> Meeting: return await store.create_meeting(payload)


@app.get("/api/meetings/{meeting_id}", response_model=Meeting)
async def get_meeting(meeting_id: str) -> Meeting:
    meeting = await store.get_meeting(meeting_id)
    if not meeting: raise HTTPException(404, "Không tìm thấy cuộc họp")
    return meeting


@app.post("/api/meetings/{meeting_id}/status/{status}", response_model=Meeting)
async def change_status(meeting_id: str, status: MeetingStatus) -> Meeting:
    meeting = await store.set_status(meeting_id, status)
    if not meeting: raise HTTPException(404, "Không tìm thấy cuộc họp")
    data = meeting.model_dump(mode="json")
    await event_bus.publish(f"scribe:meeting:{meeting_id}", {"type": "status", "data": data})
    await connections.publish(meeting_id, {"type": "status", "data": data})
    return meeting


@app.get("/api/meetings/{meeting_id}/transcript", response_model=list[TranscriptSegment])
async def transcript(meeting_id: str) -> list[TranscriptSegment]:
    if not await store.get_meeting(meeting_id): raise HTTPException(404, "Không tìm thấy cuộc họp")
    return await store.get_transcript(meeting_id)


@app.post("/api/meetings/{meeting_id}/segments", response_model=TranscriptSegment, status_code=201)
async def ingest_segment(meeting_id: str, segment: TranscriptSegment) -> TranscriptSegment:
    if meeting_id != segment.meeting_id or not await store.get_meeting(meeting_id):
        raise HTTPException(404, "Không tìm thấy cuộc họp")
    if not segment.translation:
        segment.translation = await translator.translate(segment.original, (await store.get_meeting(meeting_id)).target_language)  # type: ignore[union-attr]
    await store.add_segment(segment)
    data = segment.model_dump(mode="json")
    await event_bus.publish(f"scribe:meeting:{meeting_id}", {"type": "segment", "data": data})
    await connections.publish(meeting_id, {"type": "segment", "data": data})
    return segment


@app.post("/api/meetings/{meeting_id}/audio", response_model=AudioJob, status_code=202)
async def upload_audio(meeting_id: str, file: UploadFile = File(...), speaker: str = Form("Người tham gia")) -> AudioJob:
    meeting = await store.get_meeting(meeting_id)
    if not meeting: raise HTTPException(404, "Không tìm thấy cuộc họp")
    if not file.content_type or not (file.content_type.startswith("audio/") or file.content_type == "video/webm"):
        raise HTTPException(415, "Chỉ chấp nhận tệp âm thanh hoặc WebM")
    upload_dir = Path("data/uploads") / meeting_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "audio.webm").name
    target = upload_dir / safe_name
    with target.open("wb") as output: shutil.copyfileobj(file.file, output)
    job = AudioJob(meeting_id=meeting_id, speaker=speaker, audio_path=str(target), target_language=meeting.target_language)
    if not await event_bus.queue_audio(job.model_dump(mode="json")):
        job.status = "saved"
    return job


@app.get("/api/meetings/{meeting_id}/insights", response_model=MeetingInsights)
async def insights(meeting_id: str) -> MeetingInsights:
    if not await store.get_meeting(meeting_id): raise HTTPException(404, "Không tìm thấy cuộc họp")
    return await translator.insights(await store.get_transcript(meeting_id))


@app.websocket("/ws/meetings/{meeting_id}")
async def meeting_stream(socket: WebSocket, meeting_id: str) -> None:
    if not await store.get_meeting(meeting_id):
        await socket.close(code=4404)
        return
    await connections.connect(meeting_id, socket)
    try:
        while True: await socket.receive_text()
    except WebSocketDisconnect: connections.disconnect(meeting_id, socket)


web_dir = Path(__file__).parent.parent / "web"
app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse: return FileResponse(web_dir / "index.html")
