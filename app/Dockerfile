# BirdLense Hub — один контейнер: UI + API + processor
# Подключается к внешним: Go2RTC (Frigate), MQTT (BirdNET, Frigate)

# Stage 1: UI (использует pre-built dist если есть — обход ETIMEDOUT на сервере)
FROM node:22-alpine AS ui
WORKDIR /ui
COPY app/ui/ ./
# Если dist уже собран локально — пропускаем npm (сервер может не достать registry)
RUN test -f dist/index.html && echo "Using pre-built UI" || (npm install --legacy-peer-deps && npm run build)

# Stage 2: всё в одном
# Базовый образ держим на 8.4.21: сборка ngx_brotli под nginx из образа проверена в CI.
# Версию Python-пакета ultralytics задаём в processor/requirements.txt (pip ниже).
FROM ultralytics/ultralytics:8.4.21
# Intel VA-API: драйвер, vainfo, intel_gpu_top (метрики как во Frigate NVR).
# OpenCL ICD — пользовательский стек для OpenVINO «GPU» внутри контейнера при пробросе /dev/dri
# (docker-compose.override.yml от docker-compose-intel-override-gen.sh). Без ICD Ultralytics часто падает на CPU.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg nginx curl unzip gosu \
    intel-media-va-driver-non-free vainfo intel-gpu-tools \
    ocl-icd-libopencl1 intel-opencl-icd clinfo \
    libbrotli1 \
    && apt-get clean && rm -rf /var/cache/apt /var/lib/apt/lists/*
# Brotli: в Ubuntu 22.04 нет пакета libnginx-mod-http-brotli — собираем ngx_brotli как динамический модуль к версии nginx из образа
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpcre3-dev zlib1g-dev libssl-dev libbrotli-dev git ca-certificates curl \
    && NGINX_VER="$(nginx -v 2>&1 | sed -n 's/.*nginx\///p' | awk '{print $1}')" \
    && cd /tmp \
    && curl -fsSL "http://nginx.org/download/nginx-${NGINX_VER}.tar.gz" | tar xz \
    && git clone --depth 1 https://github.com/google/ngx_brotli.git \
    && cd ngx_brotli && git submodule update --init \
    && cd "/tmp/nginx-${NGINX_VER}" \
    && ./configure --with-compat --add-dynamic-module=/tmp/ngx_brotli \
    && make -j"$(nproc)" modules \
    && cp objs/ngx_http_brotli_filter_module.so objs/ngx_http_brotli_static_module.so /usr/lib/nginx/modules/ \
    && printf '%s\n%s\n' \
        'load_module modules/ngx_http_brotli_filter_module.so;' \
        'load_module modules/ngx_http_brotli_static_module.so;' \
        > /etc/nginx/modules-enabled/99-brotli-birdlense.conf \
    && cd / && rm -rf /tmp/nginx-${NGINX_VER} /tmp/ngx_brotli \
    && apt-get purge -y build-essential libpcre3-dev zlib1g-dev libssl-dev libbrotli-dev git \
    && apt-get autoremove -y \
    && apt-get clean && rm -rf /var/cache/apt /var/lib/apt/lists/*

WORKDIR /app

# Статические изображения каталога (корм и т.д.) — копируются в volume при старте из entrypoint
COPY app/data/images /app/_bundled_data/images

# Web + processor + scripts + shared eBird helpers (processor imports without services.*)
COPY app/ebird_region_core.py ./
COPY app/web/ ./web/
COPY app/shared/ ./shared/
COPY app/processor/ ./processor/
COPY app/app_config/ ./app_config/
COPY app/scripts/ ./scripts/
# Скрипты из корня репо (контекст сборки — родитель app/).
# Список обязательных путей дублируется в web/services/fusion_training_service.py:
# REQUIRED_SHIPPED_SCRIPT_RELPATHS — при добавлении subprocess-скрипта расширьте оба места.
COPY scripts/export_fusion_training_data.py ./scripts/
COPY scripts/train_fusion.py ./scripts/
COPY scripts/diag_video_detect.py ./scripts/
COPY scripts/diag_coco_bird_frames.py ./scripts/
COPY scripts/benchmark-track-regen.py ./scripts/
COPY scripts/compare_detector_bboxes.py ./scripts/
COPY scripts/debug_ov_conversion.py ./scripts/
COPY scripts/validate_ov_parity.py ./scripts/
COPY scripts/patch_prod_nuclear_user_config.py ./scripts/
COPY scripts/benchmark_regen_labels.py ./scripts/
COPY scripts/catalog_deep_polish.py ./scripts/
COPY scripts/reid/run_daily_ssl_cycle.py ./scripts/reid/
# SHA256 EU-классификатора — синхронизировать с CHECKSUMS (.../classification/weights/best.pt) и fetch-processor-weights.sh.
ARG CLASSIFIER_SHA256=9e99b6d1b0b7697f671a728bfa887f2f45d574ec932e8a745855e9818aadd46e
# Детекторные веса больше не вшиваются в образ: используются артефакты из volume
# ``processor/models/detection/weights`` (TrapperAI production detector).
RUN mkdir -p processor/models/detection/weights processor/models/classification/weights \
    && if [ ! -s processor/models/classification/weights/best.pt ]; then \
         curl -fsSL --retry 3 --retry-connrefused --retry-delay 5 \
           -o processor/models/classification/weights/best.pt.tmp \
           "https://huggingface.co/gfermoto/birdlense-birds-eu/resolve/c6af5aa595cbb1198a61bcf2f3f9c2adc3772dc9/best.pt" \
         && echo "${CLASSIFIER_SHA256}  processor/models/classification/weights/best.pt.tmp" | sha256sum -c - \
         && mv processor/models/classification/weights/best.pt.tmp processor/models/classification/weights/best.pt; \
       fi
RUN pip install --no-cache-dir -r web/requirements.txt \
    && pip install --no-cache-dir -r processor/requirements.txt \
    && pip install --no-cache-dir 'openvino>=2024.0'

# OpenVINO runtime нужен для dual-mode (processor.inference_backend=auto/openvino).

# UI + nginx (template, подставляется при старте)
COPY --from=ui /ui/dist /usr/share/nginx/html
COPY app/nginx/standalone.conf.template /etc/nginx/conf.d/default.conf.template
COPY app/nginx/docker-nginx-main.conf /app/nginx/docker-nginx-main.conf

# Процессы nginx / gunicorn / processor — от birdlense (uid 1000); entrypoint при старте от root делает chown volume (#277).
RUN groupadd -r birdlense -g 1000 \
    && useradd -r -u 1000 -g birdlense -d /app -s /bin/bash birdlense \
    && (usermod -aG video,render birdlense 2>/dev/null || true) \
    && mkdir -p /var/log/nginx \
    && chown -R birdlense:birdlense /app /usr/share/nginx/html /etc/nginx/conf.d /var/log/nginx

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -sf http://127.0.0.1:8000/api/ui/health > /dev/null || exit 1

EXPOSE 8080

ENV API_URL_BASE=http://127.0.0.1:8000/api/processor
ENV DATA_DIR=/app/data
# Ultralytics: writable settings dir (avoids /app/.config not owned by birdlense) — #385
ENV YOLO_CONFIG_DIR=/app/data/.ultralytics
# Меньше шума libav/h264 от OpenCV VideoCapture (RTSP) в docker logs
ENV OPENCV_LOG_LEVEL=ERROR
ENV OPENCV_FFMPEG_LOGLEVEL=quiet

CMD ["/bin/bash", "/app/scripts/entrypoint.sh"]
