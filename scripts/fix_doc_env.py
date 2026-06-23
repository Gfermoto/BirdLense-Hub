#!/usr/bin/env python3
"""Fix env line in the doc (binary-safe)."""
path = "docs/strategy/jetson-nano-edge-setup-and-migration.md"
with open(path, "rb") as f:
    data = f.read()

old_env = b"**Env (`app/.env` + `docker-compose.jetson.yml`):** `BIRDLENSE_PLATFORM=jetson_nano`, `BIRDLENSE_INFERENCE_BACKEND=tensorrt`, `BIRDLENSE_CLASSIFIER_ENGINE=chriamue`, `BIRDLENSE_OPENVINO_BINARY_ENABLED=0`, `LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1`."

new_env = b"**Env (`app/.env` + `docker-compose.jetson.yml`):** `BIRDLENSE_PLATFORM=jetson_nano`, `BIRDLENSE_INFERENCE_BACKEND=tensorrt`, `BIRDLENSE_BINARY_TENSORRT_PATH=models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.engine`, `BIRDLENSE_CLASSIFIER_ENGINE=chriamue`, `BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND=onnxruntime`, `BIRDLENSE_ENCODING=jetson`, `BIRDLENSE_CAPTURE_BACKEND=ffmpeg_nvmpi`, `BIRDLENSE_OPENVINO_BINARY_ENABLED=0`, `LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1`."

if old_env in data:
    data = data.replace(old_env, new_env)
    with open(path, "wb") as f:
        f.write(data)
    print("OK: replaced env line")
else:
    print("FAIL: env line not found")
    idx = data.find(b"BIRDLENSE_PLATFORM=jetson_nano")
    if idx >= 0:
        chunk = data[idx-30:idx+300]
        print(repr(chunk))