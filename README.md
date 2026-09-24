# ScribeAI

Trợ lý cuộc họp AI phân tán, hỗ trợ phiên âm và dịch đa ngôn ngữ theo thời gian thực. Hệ thống gồm bot tham gia Google Meet, hàng đợi Redis Streams, worker Faster-Whisper, API FastAPI/WebSocket, PostgreSQL và bảng điều khiển trực tiếp.

![Bảng điều khiển trực tiếp của ScribeAI](screenshots/dashboard.png)

## Tính năng hiện có

- Tạo và quản lý phiên họp trực tiếp thông qua REST API có kiểu dữ liệu rõ ràng.
- Tiếp nhận các đoạn phiên âm theo từng người nói và phát trực tiếp qua WebSocket.
- Theo dõi bản ghi đa ngôn ngữ cùng bản dịch, độ tin cậy, tóm tắt, việc cần làm, chủ đề và sắc thái cuộc họp.
- Khởi chạy bot Google Meet bằng TypeScript và Playwright; bot cần được chủ phòng chấp nhận cho tham gia.
- Tải âm thanh lên hàng đợi Redis để worker Faster-Whisper phiên âm bằng CPU hoặc CUDA.
- Dịch và tạo nội dung tổng hợp bằng API tương thích OpenAI; vẫn chạy được khi chưa có API key.
- Chạy toàn bộ hệ thống FastAPI, Redis và PostgreSQL bằng Docker Compose.

## Khởi động nhanh

Yêu cầu Python 3.11 trở lên.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Mở [http://localhost:8000](http://localhost:8000). Tài liệu API nằm tại `/docs`, trạng thái hệ thống nằm tại `/api/health`.

Chạy kiểm thử:

```bash
.venv/bin/pytest -q
```

Hoặc khởi chạy API, Redis và PostgreSQL:

```bash
docker compose up --build
```

Khởi chạy thêm worker phiên âm Faster-Whisper:

```bash
docker compose --profile asr up --build
```

Lần đầu chạy, Faster-Whisper sẽ tải model. Mặc định dự án dùng `small` trên CPU. Máy có NVIDIA CUDA có thể đặt `WHISPER_DEVICE=cuda` và `WHISPER_COMPUTE_TYPE=float16`.

## Cấu hình API AI

Sao chép tệp môi trường mẫu:

```bash
cp .env.example .env
```

Điền khóa API của bạn vào dòng sau:

```dotenv
TRANSLATION_API_KEY=sk-...
```

Mặc định dự án gọi OpenAI với model `gpt-4o-mini`. Có thể dùng nhà cung cấp tương thích OpenAI bằng cách đổi `TRANSLATION_API_URL` và `TRANSLATION_MODEL`. Khi chưa có key, pipeline phiên âm vẫn hoạt động và phần dịch sẽ trả lại nguyên văn thay vì gây lỗi hệ thống.

## Bot tham gia cuộc họp

```bash
cd bot-agent
npm install
npx playwright install chromium
MEETING_URL="https://meet.google.com/..." npm start
```

Bot sẽ tham gia ở trạng thái tắt tiếng với tên `ScribeAI Notes`. Để bot tự thu và gửi âm thanh, cần cài `ffmpeg` và cấu hình thêm `API_URL`, `MEETING_ID`, `AUDIO_SOURCE`. Trên Linux, tìm nguồn monitor bằng `pactl list short sources`. Bot cắt âm thanh thành đoạn WebM 10 giây rồi tải lên hàng đợi phiên âm. Giao diện và bộ chọn phần tử của Google Meet có thể thay đổi, vì vậy hãy kiểm tra bot theo chính sách Google Workspace của bạn trước khi dùng trong môi trường thực tế.

## Kiến trúc

```text
Cuộc họp ──> Bot Playwright ──> Bộ xử lý âm thanh/đoạn hội thoại
                                        │
                                        ▼
Bảng điều khiển <── WebSocket/API <── Redis Streams
                         │
                         └──────────> PostgreSQL
```

Khi chạy trực tiếp không có biến môi trường, ứng dụng dùng kho dữ liệu trong bộ nhớ để phát triển nhanh. Khi chạy Docker Compose, dữ liệu được lưu thật trong PostgreSQL, file âm thanh được ghi vào volume dùng chung và tác vụ được phát qua Redis Streams. Worker Faster-Whisper nhận tác vụ theo consumer group, phiên âm rồi gửi `TranscriptSegment` về API. API dịch nội dung, lưu dữ liệu và phát realtime tới dashboard qua WebSocket.

## API chính

| Phương thức | Đường dẫn | Chức năng |
| --- | --- | --- |
| `GET` | `/api/health` | Kiểm tra trạng thái dịch vụ |
| `POST` | `/api/meetings` | Tạo cuộc họp |
| `GET` | `/api/meetings` | Danh sách cuộc họp |
| `POST` | `/api/meetings/{id}/audio` | Tải audio/WebM và xếp hàng phiên âm |
| `POST` | `/api/meetings/{id}/segments` | Gửi một đoạn phiên âm |
| `GET` | `/api/meetings/{id}/transcript` | Lấy toàn bộ bản ghi |
| `GET` | `/api/meetings/{id}/insights` | Tóm tắt, việc cần làm và chủ đề |
| `WS` | `/ws/meetings/{id}` | Nhận sự kiện realtime |

## Ví dụ gọi API

```bash
curl -X POST http://localhost:8000/api/meetings \
  -H 'content-type: application/json' \
  -d '{"title":"Họp đồng bộ hằng tuần","source_language":"auto","target_language":"vi"}'
```

## Lộ trình phát triển

- Worker Faster-Whisper sử dụng GPU và tính năng phát hiện giọng nói.
- Redis consumer group bền vững và kho dữ liệu PostgreSQL.
- Bộ kết nối cuộc họp Zoom và Microsoft Teams.
- Xác thực, phân tách dữ liệu theo tổ chức và mã hóa bản ghi.

Dự án sử dụng giấy phép MIT. Xem [LICENSE](LICENSE).
