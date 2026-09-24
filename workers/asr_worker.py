import json
import os
import time

import httpx
from faster_whisper import WhisperModel
from redis import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
API_URL = os.getenv("API_URL", "http://api:8000")
MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8" if DEVICE == "cpu" else "float16")
GROUP = "asr-workers"
CONSUMER = os.getenv("HOSTNAME", "asr-1")


def ensure_group(redis: Redis) -> None:
    try: redis.xgroup_create("scribe:audio", GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc): raise


def process_job(redis: Redis, model: WhisperModel, message_id: str, fields: dict) -> None:
    try:
        job = json.loads(fields["payload"])
        segments, info = model.transcribe(job["audio_path"], vad_filter=True, beam_size=5)
        for segment in segments:
            text = segment.text.strip()
            if not text: continue
            payload = {"meeting_id": job["meeting_id"], "speaker": job["speaker"],
                "original": text, "translation": "", "language": info.language,
                "confidence": max(0.0, min(1.0, 1.0 - segment.no_speech_prob)),
                "offset_ms": int(segment.start * 1000)}
            response = httpx.post(f"{API_URL}/api/meetings/{job['meeting_id']}/segments", json=payload, timeout=60)
            response.raise_for_status()
        redis.xack("scribe:audio", GROUP, message_id)
        print(f"[ASR] Đã xử lý job {message_id}", flush=True)
    except Exception as exc:
        print(f"[ASR] Lỗi job {message_id}: {exc}", flush=True)
        redis.xadd("scribe:audio:failed", {"source_id": message_id, "error": str(exc), "payload": fields.get("payload", "")}, maxlen=1000)
        redis.xack("scribe:audio", GROUP, message_id)
        time.sleep(1)


def main() -> None:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    ensure_group(redis)
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print(f"[ASR] Sẵn sàng: model={MODEL_SIZE}, device={DEVICE}", flush=True)
    # Nhận lại tác vụ bị bỏ dở nếu worker cũ bị restart giữa chừng.
    _, abandoned, *_ = redis.xautoclaim("scribe:audio", GROUP, CONSUMER, min_idle_time=0, start_id="0-0", count=100)
    for message_id, fields in abandoned:
        process_job(redis, model, message_id, fields)
    while True:
        messages = redis.xreadgroup(GROUP, CONSUMER, {"scribe:audio": ">"}, count=1, block=5000)
        if not messages: continue
        for _, entries in messages:
            for message_id, fields in entries:
                process_job(redis, model, message_id, fields)


if __name__ == "__main__": main()
