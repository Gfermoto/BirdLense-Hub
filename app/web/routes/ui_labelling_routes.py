"""Active Learning and labelling MVP endpoints."""

from __future__ import annotations

from flask import request

from auth import contributor_or_admin_access
from services.active_learning_service import (
    apply_case_feedback,
    export_cases,
    list_cases,
    mine_hard_examples,
    patch_case,
)
from services.api_json_validation import parse_request_json_dict


def register_ui_labelling_routes(app):
    @app.route("/api/ui/labelling/cases/mine", methods=["POST"])
    def post_labelling_cases_mine():
        if not contributor_or_admin_access():
            return {"error": "Access denied"}, 403
        body, err = parse_request_json_dict(request)
        if err is not None:
            return err, 400
        body = body or {}
        res = mine_hard_examples(
            lookback_hours=int(body.get("lookback_hours", 72)),
            max_rows=int(body.get("max_rows", 400)),
            blind_score_threshold=float(body.get("blind_score_threshold", 0.5)),
            fallback_ratio_threshold=float(body.get("fallback_ratio_threshold", 0.35)),
            conf_min=float(body.get("conf_min", 0.20)),
            conf_max=float(body.get("conf_max", 0.35)),
        )
        return {"ok": True, **res}, 200

    @app.route("/api/ui/labelling/cases", methods=["GET"])
    def get_labelling_cases():
        if not contributor_or_admin_access():
            return {"error": "Access denied"}, 403
        status = request.args.get("status")
        try:
            limit = int(request.args.get("limit", "100"))
        except ValueError:
            return {"error": "invalid limit"}, 400
        return list_cases(status=status, limit=limit), 200

    @app.route("/api/ui/labelling/cases/<int:case_id>", methods=["PATCH"])
    def patch_labelling_case(case_id: int):
        if not contributor_or_admin_access():
            return {"error": "Access denied"}, 403
        body, err = parse_request_json_dict(request)
        if err is not None:
            return err, 400
        body = body or {}
        try:
            status = str(body.get("status") or "").strip().lower()
            note = body.get("note")
            return patch_case(case_id=case_id, status=status, reason_note=note), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400
        except LookupError:
            return {"error": "case not found"}, 404

    @app.route("/api/ui/labelling/export", methods=["POST"])
    def post_labelling_export():
        if not contributor_or_admin_access():
            return {"error": "Access denied"}, 403
        body, err = parse_request_json_dict(request)
        if err is not None:
            return err, 400
        body = body or {}
        fmt = str(body.get("format", "yolo"))
        status = str(body.get("status", "approved"))
        version = body.get("version")
        try:
            payload = export_cases(fmt=fmt, status=status, version=version)
            return payload, 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    @app.route("/api/ui/labelling/cases/<int:case_id>/feedback", methods=["POST"])
    def post_labelling_feedback(case_id: int):
        if not contributor_or_admin_access():
            return {"error": "Access denied"}, 403
        body, err = parse_request_json_dict(request)
        if err is not None:
            return err, 400
        body = body or {}
        try:
            return (
                apply_case_feedback(
                    case_id=case_id,
                    action=str(body.get("action") or ""),
                    behavior_tag=body.get("behavior_tag"),
                    species_tag=body.get("species_tag"),
                ),
                200,
            )
        except ValueError as exc:
            return {"error": str(exc)}, 400
        except LookupError:
            return {"error": "case not found"}, 404
