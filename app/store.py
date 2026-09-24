from collections import defaultdict

from app.models import Meeting, MeetingCreate, MeetingStatus, TranscriptSegment


class MemoryStore:
    """Small async repository; Redis adapter can replace it without changing routes."""

    def __init__(self) -> None:
        self.meetings: dict[str, Meeting] = {}
        self.transcripts: dict[str, list[TranscriptSegment]] = defaultdict(list)

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

