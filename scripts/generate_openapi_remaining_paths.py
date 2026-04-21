#!/usr/bin/env python3
"""Write app/web/_openapi_paths_remaining.yaml — path entries to merge into openapi.yaml (before components:)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _desc(*lines: str) -> str:
    """Single-line description so yaml.dump does not break OpenAPI structure."""
    return " ".join(lines)


def _err() -> dict[str, Any]:
    return {
        "description": "Error",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"},
            },
        },
    }


def _json_ok() -> dict[str, Any]:
    return {
        "description": "OK",
        "content": {
            "application/json": {
                "schema": {"type": "object", "additionalProperties": True},
            },
        },
    }


def _path_int(name: str) -> list[dict[str, Any]]:
    return [
        {
            "in": "path",
            "name": name,
            "required": True,
            "schema": {"type": "integer"},
        },
    ]


def _get(
    summary: str,
    description: str,
    *,
    params: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    op: dict[str, Any] = {
        "summary": summary,
        "description": _desc(description),
        "responses": {"200": _json_ok(), "403": _err()},
    }
    if params:
        op["parameters"] = params
    if extra:
        op["responses"].update(extra)
    return {"get": op}


def _post(
    summary: str,
    description: str,
    *,
    body: bool = True,
    params: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    op: dict[str, Any] = {
        "summary": summary,
        "description": _desc(description),
        "responses": {"200": _json_ok(), "400": _err(), "403": _err()},
    }
    if params:
        op["parameters"] = params
    if body:
        op["requestBody"] = {
            "required": False,
            "content": {
                "application/json": {
                    "schema": {"type": "object", "additionalProperties": True},
                },
            },
        }
    return {"post": op}


def _post_nb(summary: str, description: str, *, params: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    op: dict[str, Any] = {
        "summary": summary,
        "description": _desc(description),
        "responses": {"200": _json_ok(), "403": _err()},
    }
    if params:
        op["parameters"] = params
    return {"post": op}


def _patch(summary: str, description: str, *, params: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "patch": {
            "summary": summary,
            "description": _desc(description),
            "parameters": params,
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"type": "object", "additionalProperties": True},
                    },
                },
            },
            "responses": {"200": _json_ok(), "400": _err(), "403": _err()},
        },
    }


def _get_mixed_binary(summary: str, description: str, *, params: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    op: dict[str, Any] = {
        "summary": summary,
        "description": _desc(description),
        "responses": {
            "200": {
                "description": "Payload or file",
                "content": {
                    "application/json": {
                        "schema": {"type": "object", "additionalProperties": True},
                    },
                    "application/octet-stream": {
                        "schema": {"type": "string", "format": "binary"},
                    },
                },
            },
            "403": _err(),
            "404": _err(),
        },
    }
    if params:
        op["parameters"] = params
    return {"get": op}


PATHS: dict[str, dict[str, Any]] = {
    "/cameras": _get("List cameras", "Configured video cameras from settings.", extra={"500": _err()}),
    "/dataset/clean": _post("Clean dataset artifacts", "Remove stale export files per server rules."),
    "/dataset/export": _get_mixed_binary(
        "Dataset ZIP export",
        "Contributor plus: ZIP stream of dataset crops (query params per UI).",
    ),
    "/dataset/retro-export": _post("Retro dataset export job", "Start async retro export."),
    "/detections/{detection_id}": _patch(
        "Correct detection species",
        "PATCH JSON species_id etc. Contributor plus.",
        params=_path_int("detection_id"),
    ),
    "/detections/{detection_id}/confirm": _post(
        "Confirm detection",
        "Confirm low-confidence row after review.",
        params=_path_int("detection_id"),
    ),
    "/detections/{detection_id}/crop": _get_mixed_binary(
        "Detection crop JPEG",
        "JPEG crop for iNaturalist flow.",
        params=_path_int("detection_id"),
    ),
    "/feed/dispense": _post_nb("Dispense feeder", "Admin: trigger a feed dispense cycle."),
    "/feed/info": _get("Feeder / scale snapshot", "Overview card payload for feeder and scale state."),
    "/feed/scale-tare": _post_nb("Tare feeder scale", "Admin: publish tare command on MQTT or ESPHome per configuration."),
    "/migration-calendar": _get(
        "Migration calendar",
        "Species visits aggregated by calendar month (heatmap). catalog selects rows: observed = species with activity in range; dataset = class folders under data/dataset; full_eu = EU allowlist catalog. Legacy aliases: active -> observed; full -> full_eu. evidence is accepted for compatibility but ignored.",
        params=[
            {
                "in": "query",
                "name": "catalog",
                "required": False,
                "schema": {
                    "type": "string",
                    "default": "observed",
                    "enum": ["observed", "dataset", "full_eu", "active", "full"],
                },
                "description": "Catalog mode; active and full are legacy aliases.",
            },
            {
                "in": "query",
                "name": "start_year",
                "required": False,
                "schema": {"type": "integer"},
                "description": "Inclusive filter on visit year (optional).",
            },
            {
                "in": "query",
                "name": "end_year",
                "required": False,
                "schema": {"type": "integer"},
                "description": "Inclusive filter on visit year (optional).",
            },
            {
                "in": "query",
                "name": "start_date",
                "required": False,
                "schema": {"type": "string", "format": "date"},
                "description": "Inclusive UTC start date YYYY-MM-DD (optional).",
            },
            {
                "in": "query",
                "name": "end_date",
                "required": False,
                "schema": {"type": "string", "format": "date"},
                "description": "Inclusive UTC end date YYYY-MM-DD (optional).",
            },
            {
                "in": "query",
                "name": "evidence",
                "required": False,
                "schema": {"type": "string"},
                "description": "Ignored; reserved for backward compatibility.",
            },
        ],
        extra={"400": _err()},
    ),
    "/notify/test": _post_nb("Send test notification", "Admin: trigger test Telegram or configured channel."),
    "/push/subscribe": _post("Subscribe to Web Push", "Register push subscription JSON from the browser."),
    "/push/vapid-public": {
        "get": {
            "summary": "Web Push VAPID public key",
            "description": _desc("Public key for browser push subscription."),
            "responses": {"200": _json_ok()},
        },
    },
    "/region-comparison": _get("Regional eBird comparison", "Overview compare-to-region payload."),
    "/report/pdf": _get_mixed_binary(
        "Monthly PDF report",
        "PDF bytes for requested month or range (query params).",
    ),
    "/restart-processor": _post_nb(
        "Restart processor",
        "Admin: set processor restart flag for next processor cycle.",
    ),
    "/settings/check-access": {
        "get": {
            "summary": "Session unlock probe",
            "description": _desc("Returns unlock state without failing when locked."),
            "responses": {"200": _json_ok()},
        },
    },
    "/settings/logout": _post_nb("Logout settings session", "Clears settings unlock cookie or session."),
    "/settings/requires-password": {
        "get": {
            "summary": "Whether settings password is configured",
            "description": _desc("Always 200; boolean flags for UI."),
            "responses": {"200": _json_ok()},
        },
    },
    "/settings/verify-password": _post("Unlock settings session", "POST JSON with password; returns role admin or contributor.", body=True),
    "/settings/yaml-export": _get("Export settings YAML", "Download merged settings as YAML. Requires settings access."),
    "/settings/yaml-import": _post("Import settings YAML", "Replace or merge settings from uploaded YAML."),
    "/species-image": _get(
        "Species image proxy",
        "Cached species image bytes or redirect; query parameters per server.",
    ),
    "/species/observed": _get("Observed species list", "Species observed in a time window (query params per server)."),
    "/species/tuning-targets": _get("List tuning targets", "Species ids marked as tuning targets."),
    "/species/track-regen-options": _get("Track regeneration options", "Options payload for track regen UI."),
    "/species/{species_id}/refresh-metadata": _post_nb(
        "Refresh species metadata",
        "Contributor or admin: queue metadata refresh for catalog row.",
        params=_path_int("species_id"),
    ),
    "/species/{species_id}/tuning-target": _post(
        "Toggle tuning target",
        "Mark or unmark species for training export.",
        params=_path_int("species_id"),
    ),
    "/species/{species_id}/xeno-canto": _get(
        "Xeno-canto clips",
        "Audio clip metadata for a species.",
        params=_path_int("species_id"),
    ),
    "/status/debug": _get(
        "Debug status (admin)",
        "Detailed status for operators. Requires settings access.",
        extra={"500": _err()},
    ),
    "/storage/nearest-recording-day": _get(
        "Nearest day with recordings",
        "Library calendar helper: date of nearest recordings bucket.",
    ),
    "/system/clean-orphaned-visits": _post("Clean orphaned visits", "Admin: DB maintenance for orphan visits."),
    "/system/db/backup": _get_mixed_binary("Download SQLite backup", "Admin: streaming DB backup file."),
    "/system/db/restore": _post("Restore SQLite from upload", "Admin: restore database from client upload."),
    "/system/diagnostics/birdnet-fifo": _get(
        "BirdNET FIFO diagnostics",
        "Named pipe or FIFO status for BirdNET path.",
    ),
    "/system/diagnostics/broken-videos": _get("List broken video files", "Diagnostics: files failing probe."),
    "/system/diagnostics/broken-videos/delete": _post(
        "Delete broken videos",
        "Admin: remove broken files from list.",
    ),
    "/system/diagnostics/broken-videos/delete-preview": _post(
        "Preview delete broken videos",
        "Admin: preview cleanup.",
    ),
    "/system/diagnostics/broken-videos/purge": _post(
        "Purge broken videos",
        "Admin: delete files from disk per payload.",
    ),
    "/system/diagnostics/no-species-videos/purge": _post(
        "Purge videos without species",
        "Admin: destructive cleanup.",
    ),
    "/system/diagnostics/review-only-noise-candidates": _get(
        "Review-only noise candidates",
        "Diagnostics list for operator triage.",
    ),
    "/system/domain-health": _get(
        "Domain health check",
        "External domain reachability; may require UI API key in strict mode.",
    ),
    "/system/fusion/eval": _post("Start fusion calibration eval", "Admin: run eval job on traces."),
    "/system/fusion/eval/download": _get_mixed_binary("Download fusion eval artifact", "Download eval output when ready."),
    "/system/fusion/eval/status": _get("Fusion eval job status", "Poll fusion eval job."),
    "/system/fusion/export": _post("Start fusion trace export", "Admin: export fusion training CSV job."),
    "/system/fusion/export/download": _get_mixed_binary("Download fusion export", "CSV download when job complete."),
    "/system/fusion/export/status": _get("Fusion export job status", "Poll fusion export job."),
    "/system/merge-duplicate-species": _post("Merge duplicate species", "Admin: merge catalog duplicates."),
    "/system/observability": _get("Observability snapshot", "Combined observability JSON for System page."),
    "/system/realign-visit-times": _post("Realign visit times", "Admin: adjust visit timestamps per rules."),
    "/system/recordings/scan": _post("Scan and import recordings", "Admin: scan recordings directory and import metadata."),
    "/system/regenerate-spectrograms": _post("Bulk regenerate spectrograms", "Admin: start batch spectrogram job."),
    "/system/regenerate-spectrograms/status": _get("Spectrogram batch status", "Poll batch spectrogram job."),
    "/system/regenerate-tracks/status": _get("Track batch status", "Poll batch track regeneration job."),
    "/system/retention": _post("Run retention policy", "Admin: apply configured retention rules."),
    "/system/review-queue/delete": _post("Execute review-queue delete", "Admin: apply bulk delete."),
    "/system/review-queue/delete-preview": _post("Preview review-queue delete", "Admin: preview bulk delete in review queue."),
    "/system/species-catalog/reconcile": _post("Reconcile species catalog", "Admin: reconcile catalog vs classifier."),
    "/system/split-large-gap-visits": _post(
        "Split visits on large gaps",
        "Admin: split visits when gap exceeds threshold.",
    ),
    "/system/telegram-proxy/refresh": _post_nb("Refresh Telegram SOCKS proxy", "Admin: run proxy selection now."),
    "/system/telegram-proxy/refresh/status": _get("Telegram proxy refresh status", "Poll async proxy refresh."),
    "/system/visitors/track": _post("Record visitor heartbeat", "Optional client analytics ping."),
    "/timeline/export": _get(
        "Export timeline",
        "CSV, JSON, or eBird export for timeline range (query format and times).",
    ),
    "/videos/{video_id}/download": _get_mixed_binary(
        "Download recording",
        "Binary video download or redirect. Admin or contributor when gated.",
        params=_path_int("video_id"),
    ),
    "/videos/{video_id}/merge-species": _post(
        "Merge species on recording",
        "Admin: merge duplicate species rows for a video.",
        params=_path_int("video_id"),
    ),
    "/videos/{video_id}/regenerate-spectrogram": _post_nb(
        "Regenerate spectrogram",
        "Admin: queue spectrogram regeneration for one recording.",
        params=_path_int("video_id"),
    ),
    "/videos/{video_id}/regenerate-tracks": _post_nb(
        "Regenerate tracks",
        "Admin: queue track regeneration for one recording.",
        params=_path_int("video_id"),
    ),
    "/videos/{video_id}/stream": {
        "get": {
            "summary": "Stream recording",
            "description": _desc(
                "Video stream for playback; may require contributor when require_auth_for_video_stream is set.",
            ),
            "parameters": _path_int("video_id"),
            "responses": {
                "200": {
                    "description": "Video stream",
                    "content": {"video/mp4": {"schema": {"type": "string", "format": "binary"}}},
                },
                "403": _err(),
                "404": _err(),
            },
        },
    },
}

# Second server base URL in openapi.yaml: /api/processor — paths here are relative to that base.
PROCESSOR_PATHS: dict[str, dict[str, Any]] = {
    "/activity_log": _post("Processor activity log", "Heartbeat and status from processor container."),
    "/notify/detections": _post("Notify detections", "Processor to web: detection notification pipeline."),
    "/notify/motion": _post("Notify motion", "Processor to web: motion notification."),
    "/species/active": {
        "put": {
            "summary": "Active species snapshot",
            "description": _desc("Processor publishes active species list for web and UI."),
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"type": "object", "additionalProperties": True},
                    },
                },
            },
            "responses": {
                "200": _json_ok(),
                "400": _err(),
                "403": _err(),
            },
        },
    },
    "/videos": _post("Upsert video and detections", "Processor ingest: recording path, detections, metadata."),
}


def _dump_fragment(data: dict[str, Any], out_path: Path) -> None:
    dumped = yaml.dump(data, sort_keys=True, allow_unicode=True, default_flow_style=False, width=120)
    out_lines = ["  " + ln for ln in dumped.splitlines() if ln.strip()]
    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    _dump_fragment(PATHS, root / "app" / "web" / "_openapi_paths_remaining.yaml")
    _dump_fragment(PROCESSOR_PATHS, root / "app" / "web" / "_openapi_processor_paths.yaml")
    print("Wrote UI fragment and processor fragment under app/web/")


if __name__ == "__main__":
    main()
