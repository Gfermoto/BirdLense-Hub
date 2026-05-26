"""ReID gallery + expert review queue API (SOTA-13)."""

from __future__ import annotations

from flask import request

from auth import contributor_or_admin_access
from services.api_json_validation import parse_request_json_object_allow_empty
from services.expert_review_queue_service import (
    expert_queue_enabled,
    export_expert_verified_dataset,
    list_expert_queue,
    resolve_expert_task,
)
from services.reid_track_cluster_service import (
    build_gallery_payload,
    reid_gallery_enabled,
    reid_track_clustering_enabled,
)


def register_ui_expert_reid_routes(app):
    @app.route("/api/ui/expert/queue", methods=["GET"])
    @app.route("/api/expert/queue", methods=["GET"])
    def get_expert_queue():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        status = request.args.get("status", "pending")
        limit = request.args.get("limit", 50, type=int)
        sync = request.args.get("sync", "1").strip().lower() not in ("0", "false", "no")
        return list_expert_queue(status=status, limit=limit, sync=sync), 200

    @app.route("/api/ui/expert/resolve", methods=["POST"])
    @app.route("/api/expert/resolve", methods=["POST"])
    def post_expert_resolve():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        task_id = data.get("task_id")
        if task_id is None:
            return {"error": "task_id is required"}, 400
        try:
            payload = resolve_expert_task(
                task_id=int(task_id),
                action=str(data.get("action") or ""),
                species_id=data.get("species_id"),
                target_profile_id=data.get("target_profile_id"),
                source_profile_id=data.get("source_profile_id"),
                note=data.get("note"),
            )
            return payload, 200
        except LookupError:
            return {"error": "task not found"}, 404
        except ValueError as exc:
            return {"error": str(exc)}, 400

    @app.route("/api/ui/reid/gallery", methods=["GET"])
    def get_reid_gallery():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        video_id = request.args.get("video_id", type=int)
        species_id = request.args.get("species_id", type=int)
        limit = request.args.get("limit", 500, type=int)
        return build_gallery_payload(video_id=video_id, species_id=species_id, limit=limit), 200

    @app.route("/api/ui/reid/gallery/status", methods=["GET"])
    def get_reid_gallery_status():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        return {
            "reid_gallery_enabled": reid_gallery_enabled(),
            "reid_track_clustering_enabled": reid_track_clustering_enabled(),
            "reid_expert_queue_enabled": expert_queue_enabled(),
        }, 200

    @app.route("/api/ui/expert/export-verified", methods=["POST"])
    def post_expert_export_verified():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        limit = request.args.get("limit", 500, type=int)
        try:
            return export_expert_verified_dataset(limit=limit), 200
        except OSError as exc:
            return {"error": str(exc)}, 500
