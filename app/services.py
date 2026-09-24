import json

import httpx

from app.config import Settings
from app.models import MeetingInsights, TranscriptSegment


class TranslationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def translate(self, text: str, target_language: str) -> str:
        if not self.settings.translation_api_key:
            return text
        payload = {
            "model": self.settings.translation_model,
            "messages": [{"role": "system", "content": f"Dịch chính xác sang ngôn ngữ {target_language}. Chỉ trả về bản dịch."},
                         {"role": "user", "content": text}],
            "temperature": 0.1,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.settings.translation_api_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.translation_api_key}"}, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()

    async def insights(self, segments: list[TranscriptSegment]) -> MeetingInsights:
        if not segments:
            return MeetingInsights(summary="Cuộc họp chưa có nội dung.", action_items=[], topics=[])
        if not self.settings.translation_api_key:
            return MeetingInsights(summary=" ".join(s.translation for s in segments[-3:]), action_items=[], topics=[])
        transcript = "\n".join(f"{s.speaker}: {s.translation}" for s in segments)
        payload = {"model": self.settings.translation_model, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": "Trả JSON tiếng Việt gồm summary (chuỗi), action_items (mảng chuỗi), topics (mảng chuỗi)."},
                         {"role": "user", "content": transcript}], "temperature": 0.2}
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(f"{self.settings.translation_api_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.translation_api_key}"}, json=payload)
            response.raise_for_status()
            return MeetingInsights(**json.loads(response.json()["choices"][0]["message"]["content"]))
