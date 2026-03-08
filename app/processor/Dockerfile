# x86/amd64 image for Go2RTC + YOLO (no RPi hardware)
FROM ultralytics/ultralytics:8.3.231

# Install ffmpeg for RTSP recording (no picamera2, no ALSA)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["python", "src/main.py"]
