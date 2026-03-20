# BirdLense Hub — один контейнер: UI + API + processor
# Подключается к внешним: Go2RTC (Frigate), MQTT (BirdNET, Frigate)

# Stage 1: UI (использует pre-built dist если есть — обход ETIMEDOUT на сервере)
FROM node:25-alpine AS ui
WORKDIR /ui
COPY ui/ ./
# Если dist уже собран локально — пропускаем npm (сервер может не достать registry)
RUN test -f dist/index.html && echo "Using pre-built UI" || (npm install --legacy-peer-deps && npm run build)

# Stage 2: всё в одном
FROM ultralytics/ultralytics:8.4.21
# Intel VA-API: драйвер, vainfo, intel_gpu_top (метрики как во Frigate NVR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg nginx curl \
    intel-media-va-driver-non-free vainfo intel-gpu-tools \
    && apt-get clean && rm -rf /var/cache/apt /var/lib/apt/lists/*

WORKDIR /app

# Web + processor + scripts
COPY web/ ./web/
COPY processor/ ./processor/
COPY app_config/ ./app_config/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir -r web/requirements.txt \
    && pip install --no-cache-dir -r processor/requirements.txt

# UI + nginx (template, подставляется при старте)
COPY --from=ui /ui/dist /usr/share/nginx/html
COPY nginx/standalone.conf.template /etc/nginx/conf.d/default.conf.template

EXPOSE 8080

ENV API_URL_BASE=http://127.0.0.1:8000/api/processor
ENV DATA_DIR=/app/data

CMD ["/bin/bash", "/app/scripts/entrypoint.sh"]

