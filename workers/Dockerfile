FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY workers/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY workers workers
CMD ["python3", "-m", "workers.asr_worker"]
