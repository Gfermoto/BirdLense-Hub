#!/usr/bin/env python3
"""Тестовая галерея для приёма загрузок BirdLense Hub.

Принимает POST multipart/form-data на /api/upload (формат см. docs/CONFIGURATION.md — Gallery).
Сохраняет кадры и показывает простую галерею.
"""
import json
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, request, render_template_string, send_from_directory

app = Flask(__name__)
UPLOAD_DIR = Path(os.environ.get("GALLERY_DATA", "/data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
METADATA_FILE = UPLOAD_DIR / "uploads.json"


def _load_uploads():
    if METADATA_FILE.exists():
        try:
            with open(METADATA_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_uploads(entries):
    with open(METADATA_FILE, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


@app.route("/api/upload", methods=["POST"])
def upload():
    """Приём загрузок от BirdLense Hub (multipart/form-data)."""
    image = request.files.get("image")
    if not image or not image.filename:
        return {"ok": False, "error": "No image file"}, 400

    species = request.form.get("species", "Unknown")
    confidence = request.form.get("confidence", "")
    timestamp = request.form.get("timestamp", "")
    detection_id = request.form.get("detection_id", "")
    video_id = request.form.get("video_id", "")
    latitude = request.form.get("latitude", "")
    longitude = request.form.get("longitude", "")

    ext = Path(image.filename).suffix or ".jpg"
    safe_name = f"{detection_id or 'img'}_{video_id or 'v'}{ext}".replace("/", "_")
    filepath = UPLOAD_DIR / safe_name

    try:
        image.save(str(filepath))
    except OSError as e:
        return {"ok": False, "error": str(e)}, 500

    entry = {
        "filename": safe_name,
        "species": species,
        "confidence": confidence,
        "timestamp": timestamp,
        "detection_id": detection_id,
        "video_id": video_id,
        "latitude": latitude,
        "longitude": longitude,
        "uploaded_at": datetime.utcnow().isoformat() + "Z",
    }

    entries = _load_uploads()
    entries.insert(0, entry)
    _save_uploads(entries[:500])  # limit

    return {"ok": True, "filename": safe_name}, 200


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/")
def index():
    entries = _load_uploads()
    return render_template_string(GALLERY_HTML, entries=entries)


GALLERY_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BirdLense Gallery Test</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; background: #1a1a2e; color: #eee; }
    h1 { font-size: 1.5rem; margin-bottom: 1rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }
    .card { background: #16213e; border-radius: 8px; overflow: hidden; }
    .card img { width: 100%; aspect-ratio: 1; object-fit: cover; display: block; }
    .card .meta { padding: 0.5rem; font-size: 0.85rem; }
    .card .species { font-weight: 600; color: #e94560; }
    .card .meta span { color: #888; }
    .empty { color: #666; padding: 2rem; }
    .api { font-size: 0.8rem; color: #4a9; margin-top: 1rem; }
  </style>
</head>
<body>
  <h1>🦜 BirdLense Gallery Test</h1>
  <p class="api">API: POST /api/upload (multipart: image, species, confidence, timestamp, latitude, longitude)</p>
  {% if entries %}
  <div class="grid">
    {% for e in entries %}
    <div class="card">
      <img src="/uploads/{{ e.filename }}" alt="{{ e.species }}" loading="lazy">
      <div class="meta">
        <span class="species">{{ e.species }}</span><br>
        <span>confidence: {{ e.confidence }}</span><br>
        <span>{{ e.timestamp[:19] if e.timestamp else '' }}</span>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <p class="empty">Пока пусто. Включите «Публичная галерея» в BirdLense и укажите URL: <code>{{ request.url_root }}api/upload</code></p>
  {% endif %}
</body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
