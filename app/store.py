from collections import defaultdict
from typing import Protocol

import asyncpg

from app.models import Meeting, MeetingCreate, MeetingStatus, TranscriptSegment


class Store(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def create_meeting(self, payload: MeetingCreate) -> Meeting: ...
    async def list_meetings(self) -> list[Meeting]: ...
    async def get_meeting(self, meeting_id: str) -> Meeting | None: ...
    async def set_status(self, meeting_id: str, status: MeetingStatus) -> Meeting | None: ...
    async def add_segment(self, segment: TranscriptSegment) -> None: ...
    async def get_transcript(self, meeting_id: str) -> list[TranscriptSegment]: ...


class MemoryStore:
    def __init__(self) -> None:
        self.meetings: dict[str, Meeting] = {}
        self.transcripts: dict[str, list[TranscriptSegment]] = defaultdict(list)

    async def connect(self) -> None: pass
    async def close(self) -> None: pass

    async def create_meeting(self, payload: MeetingCreate) -> Meeting:
        meeting = Meeting(**payload.model_dump())
        self.meetings[meeting.id] = meeting
        return meeting

    async def list_meetings(self) -> list[Meeting]:
        return sorted(self.meetings.values(), key=lambda item: item.created_at, reverse=True)

    async def get_meeting(self, meeting_id: str) -> Meeting | None:
        return self.meetings.get(meeting_id)

    async def set_status(self, meeting_id: str, status: MeetingStatus) -> Meeting | None:
        meeting = self.meetings.get(meeting_id)
        if meeting:
            meeting.status = status
        return meeting

    async def add_segment(self, segment: TranscriptSegment) -> None:
        self.transcripts[segment.meeting_id].append(segment)

    async def get_transcript(self, meeting_id: str) -> list[TranscriptSegment]:
        return self.transcripts[meeting_id]


class PostgresStore:
    """Kho dữ liệu PostgreSQL tối giản, không cần migration tool cho bản demo."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.database_url)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS meetings (
                    id VARCHAR(36) PRIMARY KEY, title VARCHAR(120) NOT NULL,
                    source_language VARCHAR(16) NOT NULL, target_language VARCHAR(16) NOT NULL,
                    status VARCHAR(16) NOT NULL, created_at TIMESTAMPTZ NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transcript_segments (
                    id VARCHAR(36) PRIMARY KEY, meeting_id VARCHAR(36) NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
                    speaker VARCHAR(120) NOT NULL, original TEXT NOT NULL, translation TEXT NOT NULL,
                    language VARCHAR(16) NOT NULL, confidence DOUBLE PRECISION NOT NULL,
                    offset_ms INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_segments_meeting_offset
                ON transcript_segments(meeting_id, offset_ms);
            """)

    async def close(self) -> None:
        if self.pool: await self.pool.close()

    def _meeting(self, row: asyncpg.Record | None) -> Meeting | None:
        return Meeting(**dict(row)) if row else None

    async def create_meeting(self, payload: MeetingCreate) -> Meeting:
        meeting = Meeting(**payload.model_dump())
        assert self.pool
        await self.pool.execute("INSERT INTO meetings VALUES($1,$2,$3,$4,$5,$6)", meeting.id, meeting.title,
            meeting.source_language, meeting.target_language, meeting.status.value, meeting.created_at)
        return meeting

    async def list_meetings(self) -> list[Meeting]:
        assert self.pool
        rows = await self.pool.fetch("SELECT * FROM meetings ORDER BY created_at DESC")
        return [Meeting(**dict(row)) for row in rows]

    async def get_meeting(self, meeting_id: str) -> Meeting | None:
        assert self.pool
        return self._meeting(await self.pool.fetchrow("SELECT * FROM meetings WHERE id=$1", meeting_id))

    async def set_status(self, meeting_id: str, status: MeetingStatus) -> Meeting | None:
        assert self.pool
        row = await self.pool.fetchrow("UPDATE meetings SET status=$2 WHERE id=$1 RETURNING *", meeting_id, status.value)
        return self._meeting(row)

    async def add_segment(self, segment: TranscriptSegment) -> None:
        assert self.pool
        await self.pool.execute("INSERT INTO transcript_segments VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",
            segment.id, segment.meeting_id, segment.speaker, segment.original, segment.translation,
            segment.language, segment.confidence, segment.offset_ms, segment.created_at)

    async def get_transcript(self, meeting_id: str) -> list[TranscriptSegment]:
        assert self.pool
        rows = await self.pool.fetch("SELECT * FROM transcript_segments WHERE meeting_id=$1 ORDER BY offset_ms", meeting_id)
        return [TranscriptSegment(**dict(row)) for row in rows]
