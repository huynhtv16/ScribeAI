from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MeetingStatus(str, Enum):
    scheduled = "scheduled"
    live = "live"
    ended = "ended"


class MeetingCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    source_language: str = "auto"
    target_language: str = "vi"


class Meeting(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    source_language: str
    target_language: str
    status: MeetingStatus = MeetingStatus.scheduled
    created_at: datetime = Field(default_factory=utc_now)


class TranscriptSegment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    meeting_id: str
    speaker: str
    original: str
    translation: str
    language: str
    confidence: float = Field(ge=0, le=1)
    offset_ms: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class Health(BaseModel):
    status: str
    version: str
    event_bus: str


class AudioJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    meeting_id: str
    speaker: str = "Người tham gia"
    audio_path: str
    target_language: str = "vi"
    status: str = "queued"


class MeetingInsights(BaseModel):
    summary: str
    action_items: list[str]
    topics: list[str]
