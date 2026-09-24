.PHONY: dev test demo docker-up
dev:
	.venv/bin/uvicorn app.main:app --reload
test:
	.venv/bin/pytest -q
demo:
	.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
docker-up:
	docker compose up --build
