# ScribeAI

Trợ lý cuộc họp AI phân tán, hỗ trợ phiên âm và dịch đa ngôn ngữ theo thời gian thực. Phiên bản MVP hiện có API tiếp nhận dữ liệu bằng FastAPI/WebSocket, bảng điều khiển cuộc họp trực tiếp và bộ khung bot tham gia cuộc họp bằng Playwright chạy ẩn.

![Bảng điều khiển trực tiếp của ScribeAI](screenshots/dashboard.png)

## Tính năng hiện có

- Tạo và quản lý phiên họp trực tiếp thông qua REST API có kiểu dữ liệu rõ ràng.
- Tiếp nhận các đoạn phiên âm theo từng người nói và phát trực tiếp qua WebSocket.
- Theo dõi bản ghi đa ngôn ngữ cùng bản dịch, độ tin cậy, tóm tắt, việc cần làm, chủ đề và sắc thái cuộc họp.
- Khởi chạy bot Google Meet bằng TypeScript và Playwright; bot cần được chủ phòng chấp nhận cho tham gia.
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

Hoặc khởi chạy toàn bộ hạ tầng:

```bash
docker compose up --build
```

## Bot tham gia cuộc họp

```bash
cd bot-agent
npm install
npx playwright install chromium
MEETING_URL="https://meet.google.com/..." npm start
```

Bot sẽ tham gia ở trạng thái tắt tiếng với tên `ScribeAI Notes`. Giao diện và bộ chọn phần tử của Google Meet có thể thay đổi, vì vậy hãy kiểm tra bot theo chính sách Google Workspace của bạn trước khi dùng trong môi trường thực tế.

## Kiến trúc

```text
Cuộc họp ──> Bot Playwright ──> Bộ xử lý âm thanh/đoạn hội thoại
                                        │
                                        ▼
Bảng điều khiển <── WebSocket/API <── Redis Streams
                         │
                         └──────────> PostgreSQL
```

MVP sử dụng kho dữ liệu trong bộ nhớ để có thể chạy demo ngay mà không cần cấu hình. `docker-compose.yml` cung cấp Redis Streams và PostgreSQL làm ranh giới tích hợp cho môi trường triển khai. Các worker Faster-Whisper/CUDA có thể gửi sự kiện `TranscriptSegment` đã chuẩn hóa tới `POST /api/meetings/{id}/segments`; API sẽ phát các sự kiện này tới những máy khách đang kết nối.

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
