"""Dataset export/clean, detection crop/confirm/PATCH, corrections log (#198)."""

from flask import Response, current_app, request

from auth import contributor_or_admin_access
from models import db
from services.corrections_activity_service import fetch_recent_species_corrections
from services.dataset_export_request_service import (
    dataset_export_zip_filename,
    parse_dataset_export_query_args,
)
from services.dataset_export_service import build_dataset_zip, clean_dataset
from services.api_json_validation import parse_request_json_object_allow_empty
from services.detection_crop_api_service import get_detection_crop_jpeg_and_filename
from services.detection_species_correction_service import (
    apply_detection_nickname_patch,
    apply_detection_species_patch,
    delete_detection_with_feedback,
    run_confirm_detection,
)
from services.bird_profile_service import (
    assign_profile_to_detection,
    clear_profile_from_detection,
    create_bird_profile,
    delete_bird_profile,
    list_bird_profiles,
    merge_bird_profiles,
    set_detection_semantic_review,
    update_bird_profile,
)
from services.reid_auto_link_service import record_link_feedback, suggest_profile_links


def register_ui_corrections_dataset_routes(app):
    @app.route("/api/ui/bird-profiles", methods=["GET"])
    def get_bird_profiles():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        query = request.args.get("query")
        species_id = request.args.get("species_id", type=int)
        limit = request.args.get("limit", 20, type=int)
        return {"items": list_bird_profiles(query=query, species_id=species_id, limit=limit)}, 200

    @app.route("/api/ui/bird-profiles", methods=["POST"])
    def post_bird_profile():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        try:
            payload = create_bird_profile(
                display_name=str(data.get("display_name") or ""),
                species_id=data.get("species_id"),
                avatar_url=data.get("avatar_url"),
                status=data.get("status"),
            )
            return payload, 201
        except ValueError as exc:
            return {"error": str(exc)}, 400

    @app.route("/api/ui/bird-profiles/<int:profile_id>", methods=["PATCH"])
    def patch_bird_profile(profile_id: int):
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        try:
            payload = update_bird_profile(
                profile_id=profile_id,
                display_name=data.get("display_name"),
                avatar_url=data.get("avatar_url"),
                status=data.get("status"),
            )
            return payload, 200
        except ValueError as exc:
            return {"error": str(exc)}, 400
        except LookupError:
            return {"error": "profile not found"}, 404

    @app.route("/api/ui/bird-profiles/<int:profile_id>", methods=["DELETE"])
    def delete_bird_profile_route(profile_id: int):
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        try:
            payload = delete_bird_profile(profile_id=profile_id)
            return payload, 200
        except LookupError:
            return {"error": "profile not found"}, 404

    @app.route("/api/ui/bird-profiles/<int:profile_id>/suggest-links", methods=["POST"])
    def post_bird_profile_suggest_links(profile_id: int):
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        try:
            payload = suggest_profile_links(
                profile_id=int(profile_id) if int(profile_id) > 0 else None,
                video_species_id=data.get("video_species_id"),
                species_id=data.get("species_id"),
                limit=data.get("limit", 8),
            )
            return payload, 200
        except LookupError:
            return {"error": "detection not found"}, 404

    @app.route("/api/ui/bird-profiles/suggest-links", methods=["POST"])
    def post_bird_profile_suggest_links_new():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        try:
            payload = suggest_profile_links(
                profile_id=data.get("profile_id"),
                video_species_id=data.get("video_species_id"),
                species_id=data.get("species_id"),
                limit=data.get("limit", 8),
            )
            return payload, 200
        except LookupError:
            return {"error": "detection not found"}, 404

    @app.route("/api/ui/bird-profiles/link-feedback", methods=["POST"])
    def post_bird_profile_link_feedback():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        try:
            payload = record_link_feedback(
                action=str(data.get("action") or ""),
                candidate_profile_id=int(data.get("candidate_profile_id")),
                anchor_profile_id=data.get("anchor_profile_id"),
                video_species_id=data.get("video_species_id"),
                similarity=data.get("similarity"),
                source=str(data.get("source") or "auto_link_ui"),
            )
            return payload, 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    @app.route("/api/ui/bird-profiles/<int:target_profile_id>/merge", methods=["POST"])
    def post_bird_profile_merge(target_profile_id: int):
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        source_id = data.get("source_profile_id")
        if source_id is None:
            return {"error": "source_profile_id is required"}, 400
        try:
            payload = merge_bird_profiles(
                target_profile_id=int(target_profile_id),
                source_profile_id=int(source_id),
            )
            return payload, 200
        except ValueError as exc:
            return {"error": str(exc)}, 400
        except LookupError:
            return {"error": "profile not found"}, 404

    @app.route("/api/ui/detections/<int:detection_id>/crop", methods=["GET"])
    def get_detection_crop(detection_id):
        """Extract a frame from video for iNaturalist export. Returns JPEG."""
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        jpeg, filename, err = get_detection_crop_jpeg_and_filename(db.session, detection_id)
        if err:
            msg = err.get("error", "")
            if msg in ("Detection not found", "Video not found"):
                return err, 404
            if msg == "Failed to extract frame":
                return err, 500
            return err, 400
        return Response(
            jpeg,
            mimetype="image/jpeg",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.route("/api/ui/dataset/export", methods=["GET"])
    def export_dataset():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        params = parse_dataset_export_query_args(request.args)
        zip_bytes, err = build_dataset_zip(**params)
        if err:
            return {"error": err}, 404
        filename = dataset_export_zip_filename()
        return Response(
            zip_bytes,
            mimetype="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.route("/api/ui/dataset/retro-export", methods=["POST"])
    def retro_export_dataset():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        from services.dataset_export_service import retro_export_all_video_detections

        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        min_conf = float(data.get("min_confidence", 0))
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        only_manually_corrected = bool(data.get("only_manually_corrected", False))
        rebuild = bool(data.get("rebuild", False))
        if rebuild and (not start_date or not end_date):
            return {"error": "rebuild requires start_date and end_date"}, 400
        result = retro_export_all_video_detections(
            min_confidence=min_conf,
            start_date=start_date,
            end_date=end_date,
            only_manually_corrected=only_manually_corrected,
            rebuild=rebuild,
        )
        return result, 200

    @app.route("/api/ui/dataset/clean", methods=["POST"])
    def clean_dataset_route():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        dry_run = bool(data.get("dry_run", False))
        remove_fullframe = data.get("remove_fullframe", True)
        remove_orphaned = data.get("remove_orphaned", False)
        result = clean_dataset(
            dry_run=dry_run,
            remove_fullframe=remove_fullframe,
            remove_orphaned=remove_orphaned,
        )
        return result, 200

    @app.route("/api/ui/detections/<int:detection_id>/confirm", methods=["POST"])
    def confirm_detection(detection_id):
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        err, ok = run_confirm_detection(db.session, detection_id, data)
        if err:
            return err, 404
        return ok, 200

    @app.route("/api/ui/corrections/recent", methods=["GET"])
    def recent_corrections():
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        limit = request.args.get("limit", 10, type=int)
        out = fetch_recent_species_corrections(db.session, limit)
        return out, 200

    @app.route("/api/ui/detections/<int:detection_id>", methods=["PATCH"])
    def update_detection_species(detection_id):
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        app_obj = current_app._get_current_object()
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        if "species_id" in data:
            err, ok = apply_detection_species_patch(
                db.session,
                app.logger,
                detection_id,
                data,
                app_obj_for_thread=app_obj,
            )
        elif "bird_profile_id" in data:
            raw_profile_id = data.get("bird_profile_id")
            if raw_profile_id is None:
                try:
                    payload = clear_profile_from_detection(detection_id=detection_id)
                    return payload, 200
                except LookupError as exc:
                    return {"error": str(exc)}, 404
            try:
                payload = assign_profile_to_detection(
                    detection_id=detection_id,
                    bird_profile_id=int(raw_profile_id),
                )
                return payload, 200
            except (TypeError, ValueError):
                return {"error": "bird_profile_id must be an integer or null"}, 400
            except LookupError as exc:
                return {"error": str(exc)}, 404
        elif "semantic_review_required" in data:
            try:
                payload = set_detection_semantic_review(
                    detection_id=detection_id,
                    required=bool(data.get("semantic_review_required")),
                    note=(str(data.get("semantic_review_note") or "").strip() or None),
                    source=str(data.get("source") or "video_details"),
                )
                return payload, 200
            except LookupError:
                return {"error": "detection not found"}, 404
        elif "individual_nickname" in data:
            err, ok = apply_detection_nickname_patch(
                db.session,
                detection_id,
                data,
            )
        else:
            return {
                "error": (
                    "species_id, individual_nickname, bird_profile_id or semantic_review_required is required"
                )
            }, 400
        if err:
            code = 404
            if err.get("error") in (
                "species_id is required",
                "species_id must be an integer",
                "individual_nickname is required",
                "individual_nickname must be a string or null",
                "individual_nickname is too long (max 64)",
            ):
                code = 400
            return err, code
        return ok, 200

    @app.route("/api/ui/detections/<int:detection_id>", methods=["DELETE"])
    def delete_detection(detection_id):
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        err, ok = delete_detection_with_feedback(
            db.session,
            app.logger,
            detection_id,
            data,
        )
        if err:
            return err, 404
        return ok, 200
