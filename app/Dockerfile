# BirdLense Hub — один контейнер: UI + API + processor
# Подключается к внешним: Go2RTC (Frigate), MQTT (BirdNET, Frigate)

# Stage 1: UI (использует pre-built dist если есть — обход ETIMEDOUT на сервере)
FROM node:22-alpine AS ui
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

