#!/usr/bin/env python3
"""Generate path fragments and splice them into app/web/openapi.yaml before components:."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

_VIDEO_DELETE_ANCHOR = """        "404":
          description: Video not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
  /videos/{video_id}/detection-frames:"""

_VIDEO_DELETE_INSERT = """        "404":
          description: Video not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
    delete:
      summary: Delete recording
      description: |
        Admin: delete video row and associated artifacts per server rules.
      parameters:
        - in: path
          name: video_id
          required: true
          schema:
            type: integer
      responses:
        "200":
          description: Result
          content:
            application/json:
              schema:
                type: object
                additionalProperties: true
        "403":
          description: Access denied
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
        "404":
          description: Video not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Error"
  /videos/{video_id}/detection-frames:"""


def _add_video_delete(path: Path) -> None:
    t = path.read_text(encoding="utf-8")
    if "    delete:\n      summary: Delete recording" in t:
        return
    if _VIDEO_DELETE_ANCHOR not in t:
        raise SystemExit("video delete anchor not found")
    path.write_text(t.replace(_VIDEO_DELETE_ANCHOR, _VIDEO_DELETE_INSERT, 1), encoding="utf-8")
OPENAPI = ROOT / "app" / "web" / "openapi.yaml"
FRAG_UI = ROOT / "app" / "web" / "_openapi_paths_remaining.yaml"
FRAG_PR = ROOT / "app" / "web" / "_openapi_processor_paths.yaml"
GEN = ROOT / "scripts" / "generate_openapi_remaining_paths.py"


def main() -> None:
    subprocess.run([sys.executable, str(GEN)], check=True)
    text = OPENAPI.read_text(encoding="utf-8")
    marker = "\ncomponents:\n"
    if marker not in text:
        raise SystemExit("components: marker not found")
    head, tail = text.split(marker, 1)
    # Do not use strip() — it removes leading indentation from the first path key.
    ui = FRAG_UI.read_text(encoding="utf-8").rstrip("\n")
    pr = FRAG_PR.read_text(encoding="utf-8").rstrip("\n")
    merged = head.rstrip() + "\n" + ui + "\n" + pr + "\n" + marker + tail
    # Second server for processor paths
    merged = merged.replace(
        "servers:\n  - url: http://birdlense.local/api/ui\n",
        "servers:\n"
        "  - url: http://birdlense.local/api/ui\n"
        "    description: Hub UI API (browser and MCP)\n"
        "  - url: http://birdlense.local/api/processor\n"
        "    description: Processor ingest (requires X-Processor-Token when configured)\n",
        1,
    )
    OPENAPI.write_text(merged, encoding="utf-8")
    _add_video_delete(OPENAPI)
    yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    FRAG_UI.unlink(missing_ok=True)
    FRAG_PR.unlink(missing_ok=True)
    print("Merged fragments into", OPENAPI)


if __name__ == "__main__":
    main()
