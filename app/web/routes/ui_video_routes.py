"""Маршруты видео: детали, соседи, кадры треков, удаление, скачивание, стрим, merge (#198)."""

import os
import shutil
import json
from datetime import timedelta

from flask import request, send_file
from sqlalchemy.orm import joinedload

from app_config.app_config import app_config
from auth import contributor_or_admin_access, ui_sensitive_export_access
from models import ActiveLearningCase, Species, SpeciesVisit, Video, VideoSpecies, db
from services.api_json_validation import parse_request_json_dict
from services.cache import cache_get, cache_set
from services.dataset_export_service import (
    extract_and_save_crop_for_detection,
    move_crop_on_species_correction,
)
from services.detection_crop_service import VIDEO_PATH_SAFE_RE
from services.favorites_catalog_service import build_favorites_by_species_payload
from services.http_response_cache import bust_all_api_caches
from services.video_neighbors_service import (
    VideoNeighborsParamError,
    build_video_neighbors_payload,
    parse_video_neighbors_request_args,
)
from services.fusion_trace_service import build_fusion_trace_api_payload
from services.video_payload_service import (
    build_video_detail_dict,
    build_video_detection_frames_dict,
)
from services.visit_processor import VisitProcessor
import util as util_mod
from util import ensure_utc

from routes.ui_route_constants import CACHE_DETECTION_FRAMES_SEC, CACHE_FAVORITES_CATALOG_SEC


def register_ui_video_routes(app):
    @app.route("/api/ui/favorites/by-species", methods=["GET"])
    def get_favorites_by_species():
        """Каталог избранных роликов без календаря: группы по виду + нераспознанные."""
        ck = "favorites:by-species:v1"
        hit, cached = cache_get(ck)
        if hit:
            return cached, 200
        body = build_favorites_by_species_payload(db.session)
        cache_set(ck, body, CACHE_FAVORITES_CATALOG_SEC)
        return body, 200

    @app.route("/api/ui/videos/<int:video_id>", methods=["GET"])
    def get_video_details(video_id):
        video = (
            db.session.query(Video)
            .options(
                joinedload(Video.video_species).joinedload(VideoSpecies.species),
                joinedload(Video.video_species).joinedload(VideoSpecies.bird_profile),
                joinedload(Video.food),
            )
            .filter(Video.id == video_id)
            .first()
        )

        if not video:
            return {"error": "Video not found"}, 404
        payload = build_video_detail_dict(video)
        detection_ids = [row.get("id") for row in payload.get("species", []) if row.get("id") is not None]
        if detection_ids:
            rows = (
                db.session.query(ActiveLearningCase)
                .filter(
                    ActiveLearningCase.video_id == video_id,
                    ActiveLearningCase.video_species_id.in_(detection_ids),
                )
                .order_by(ActiveLearningCase.updated_at.desc())
                .all()
            )
            history_map = {}
            for case in rows:
                try:
                    p = json.loads(case.payload_json or "{}")
                except Exception:
                    p = {}
                hist = p.get("semantic_review_history")
                if not isinstance(hist, list):
                    continue
                history_map[int(case.video_species_id)] = hist[-10:]
            for row in payload.get("species", []):
                did = row.get("id")
                if did is None:
                    continue
                row["semantic_review_history"] = history_map.get(int(did), [])
                row["semantic_conflict"] = bool(row.get("classifier_needs_review")) or bool(
                    row.get("review_reason") == "semantic_review_required"
                )
        return payload, 200

    @app.route("/api/ui/videos/<int:video_id>", methods=["PATCH"])
    def patch_video(video_id):
        """Избранное и/или ручная правка поведения (#416). Только contributor/admin."""
        if not contributor_or_admin_access():
            return {"error": "Access denied"}, 403
        data, v_err = parse_request_json_dict(request)
        if v_err is not None:
            return v_err, 400
        allowed_keys = {"favorite", "behavior_label", "behavior_confidence"}
        if not data or any(k not in allowed_keys for k in data):
            return {"error": "Invalid body"}, 400
        video = db.session.get(Video, video_id)
        if not video:
            return {"error": "Video not found"}, 404
        if video.deleted_at is not None:
            return {"error": "Video deleted"}, 410

        if "favorite" in data:
            fav = data["favorite"]
            if not isinstance(fav, bool):
                return {"error": "favorite must be a boolean"}, 400
            video.favorite = fav

        if "behavior_label" in data:
            raw = data["behavior_label"]
            if raw is None or raw == "":
                video.behavior_label = None
                video.behavior_confidence = None
            elif isinstance(raw, str):
                lab = raw.strip().lower()[:32]
                if not lab:
                    video.behavior_label = None
                else:
                    video.behavior_label = lab
            else:
                return {"error": "behavior_label must be a string or null"}, 400

        if "behavior_confidence" in data:
            rawc = data["behavior_confidence"]
            if rawc is None:
                video.behavior_confidence = None
            else:
                try:
                    cf = float(rawc)
                except (TypeError, ValueError):
                    return {"error": "behavior_confidence must be a number or null"}, 400
                if cf < 0 or cf > 1:
                    return {"error": "behavior_confidence must be between 0 and 1"}, 400
                video.behavior_confidence = cf

        db.session.commit()
        bust_all_api_caches()
        video = (
            db.session.query(Video)
            .options(
                joinedload(Video.video_species).joinedload(VideoSpecies.species),
                joinedload(Video.video_species).joinedload(VideoSpecies.bird_profile),
                joinedload(Video.food),
            )
            .filter(Video.id == video_id)
            .first()
        )
        return build_video_detail_dict(video), 200

    @app.route("/api/ui/videos/<int:video_id>/neighbors", methods=["GET"])
    def get_video_neighbors(video_id):
        """Соседние ролики для страницы видео.

        По умолчанию границы дня считаются в UTC (совместимо с прежним контрактом).
        Опции:
        - day_scope=local: использовать локальный день оператора (tz_offset_minutes)
        - cross_day=true: если в пределах дня соседей нет, вернуть ближайший из соседних суток
        """
        video = db.session.get(Video, video_id)
        if not video:
            return {"error": "Video not found"}, 404
        try:
            nparams = parse_video_neighbors_request_args(request.args)
        except VideoNeighborsParamError as exc:
            return {"error": str(exc)}, 400
        scope, cross_day, neighbor_mode, visit_id, tz_offset_minutes = nparams
        payload = build_video_neighbors_payload(
            db.session,
            video,
            video_id,
            scope=scope,
            cross_day=cross_day,
            neighbor_mode=neighbor_mode,
            visit_id=visit_id,
            tz_offset_minutes=tz_offset_minutes,
        )
        return payload, 200

    @app.route("/api/ui/videos/<int:video_id>/detection-frames", methods=["GET"])
    def get_video_detection_frames(video_id):
        """Покадровые bbox для оверлея треков. Тяжёлый JSON — не смешиваем с GET /videos/:id."""
        ck = f"detection_frames:{video_id}"
        hit, cached = cache_get(ck)
        if hit:
            return cached, 200
        video = db.session.query(Video).options(joinedload(Video.video_species)).filter(Video.id == video_id).first()
        if not video:
            return {"error": "Video not found"}, 404
        body = build_video_detection_frames_dict(video)
        cache_set(ck, body, CACHE_DETECTION_FRAMES_SEC)
        return body, 200

    @app.route("/api/ui/videos/<int:video_id>/fusion-trace", methods=["GET"])
    def get_video_fusion_trace(video_id):
        """Трассировка fusion (ActivityLog decision_trace) для ролика (#272).

        Как export/download: contributor/admin, MCP Bearer или UI API key; не для гостей.
        """
        if not ui_sensitive_export_access():
            return {"error": "Access denied"}, 403
        body, code = build_fusion_trace_api_payload(video_id)
        return body, code

    @app.route("/api/ui/videos/<int:video_id>", methods=["DELETE"])
    def delete_video(video_id):
        """Удалить запись (видео, файл, связанные данные). Только для админа и помощника."""
        if not contributor_or_admin_access():
            return {"error": "Access denied"}, 403
        video = db.session.get(Video, video_id)
        if not video:
            return {"error": "Video not found"}, 404
        try:
            recording_dir = None
            if video.video_path and VIDEO_PATH_SAFE_RE.match(video.video_path):
                d = util_mod.full_path_for_video(os.path.dirname(video.video_path))
                if d and os.path.isdir(d):
                    recording_dir = d

            visit_ids = {vs.species_visit_id for vs in video.video_species if vs.species_visit_id}
            visits_to_delete = []
            for vid in visit_ids:
                other = VideoSpecies.query.filter(
                    VideoSpecies.species_visit_id == vid,
                    VideoSpecies.video_id != video_id,
                ).first()
                if not other:
                    visits_to_delete.append(vid)
            for vs in list(video.video_species):
                db.session.delete(vs)
            for vid in visits_to_delete:
                visit = db.session.get(SpeciesVisit, vid)
                if visit:
                    db.session.delete(visit)

            db.session.delete(video)
            db.session.commit()
            bust_all_api_caches()

            if recording_dir:
                try:
                    shutil.rmtree(recording_dir)
                    app.logger.info(f"Deleted recording dir: {recording_dir}")
                except OSError as e:
                    app.logger.warning(f"Could not delete dir {recording_dir}: {e}")

            return {"message": "Video deleted"}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception(f"Delete video {video_id} failed: {e}")
            return {"error": str(e)}, 500

    @app.route("/api/ui/videos/<int:video_id>/download", methods=["GET"])
    def download_video(video_id):
        """Скачать видео. Только для админа и помощника (contributor_or_admin_access)."""
        if not contributor_or_admin_access():
            return {"error": "Access denied"}, 403
        video = db.session.get(Video, video_id)
        if not video or not video.video_path:
            return {"error": "Video not found"}, 404
        if not VIDEO_PATH_SAFE_RE.match(video.video_path):
            return {"error": "Invalid video path"}, 400
        full_path = util_mod.full_path_for_video(video.video_path)
        if not full_path or not os.path.isfile(full_path):
            return {"error": "Video file not found"}, 404
        ts = video.start_time.strftime("%Y-%m-%d_%H%M%S") if video.start_time else "video"
        filename = f"birdlense_{ts}.mp4"
        return send_file(
            full_path,
            as_attachment=True,
            download_name=filename,
            mimetype="video/mp4",
        )

    @app.route("/api/ui/videos/<int:video_id>/stream", methods=["GET"])
    def stream_video(video_id):
        """Стриминг видео для плеера (Range, video/mp4).

        По умолчанию доступен гостям (Viewer), как GET /videos/:id — см. ACCESS_CONTROL.
        Опционально: general.require_auth_for_video_stream=true — только Contributor/Admin.
        """
        if bool(app_config.get("general.require_auth_for_video_stream")):
            if not contributor_or_admin_access():
                return {"error": "Password required"}, 403
        video = db.session.get(Video, video_id)
        if not video or not video.video_path:
            return {"error": "Video not found"}, 404
        if not VIDEO_PATH_SAFE_RE.match(video.video_path):
            return {"error": "Invalid video path"}, 400
        full_path = util_mod.full_path_for_video(video.video_path)
        if not full_path or not os.path.isfile(full_path):
            return {"error": "Video file not found"}, 404
        return send_file(
            full_path,
            mimetype="video/mp4",
            conditional=True,
        )

    @app.route("/api/ui/videos/<int:video_id>/merge-species", methods=["POST"])
    def merge_video_species(video_id):
        """Объединить все детекции в видео в один вид."""
        if not contributor_or_admin_access():
            return {"error": "Password required"}, 403

        video = db.session.get(Video, video_id)
        if not video:
            return {"error": "Video not found"}, 404

        data, v_err = parse_request_json_dict(request)
        if v_err is not None:
            return v_err, 400
        species_id = data.get("species_id")
        if species_id is None:
            return {"error": "species_id is required"}, 400
        try:
            species_id = int(species_id)
        except (TypeError, ValueError):
            return {"error": "species_id must be an integer"}, 400

        species = db.session.get(Species, species_id)
        if not species:
            return {"error": "Species not found"}, 404

        to_update = [vs for vs in video.video_species]
        if not to_update:
            return {"message": "No detections to merge", "updated_count": 0}, 200

        if all(vs.species_id == species_id for vs in to_update):
            return {"message": "All detections already this species", "updated_count": 0}, 200

        old_visits = {vs.species_visit for vs in to_update if vs.species_visit}
        visit_timeout = int(app_config.get("detection.dedup_window_seconds") or 60)
        vp = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)
        video_start = ensure_utc(video.start_time)

        first_start = min(vs.start_time for vs in to_update)
        detection_time = video_start + timedelta(seconds=first_start)
        new_visit, _ = vp.get_or_create_visit(species, detection_time)

        for vs in to_update:
            old_species_name = vs.species.name
            vs.species_id = species_id
            vs.species_visit_id = new_visit.id
            vs.species_visit = new_visit
            vs.manually_corrected = True
            v_start = video_start + timedelta(seconds=vs.start_time)
            v_end = video_start + timedelta(seconds=vs.end_time)
            new_visit.end_time = max(new_visit.end_time, v_end)
            new_visit.start_time = min(new_visit.start_time, v_start)
            if vs.source == "video":
                moved = move_crop_on_species_correction(
                    video_id=vs.video_id,
                    track_id=vs.track_id,
                    old_species_name=old_species_name,
                    new_species_name=species.name,
                )
                if not moved:
                    extract_and_save_crop_for_detection(vs, species.name)

        db.session.flush()
        for ov in old_visits:
            if ov and ov.id != new_visit.id:
                remaining = [x for x in ov.video_species if x not in to_update]
                if not remaining:
                    db.session.delete(ov)

        new_video_detections = [v for v in new_visit.video_species if v.source == "video"]
        if new_video_detections:
            vp.update_simultaneous_count(new_visit, new_video_detections)

        db.session.commit()
        bust_all_api_caches()
        updated_count = len(to_update)
        return {
            "message": f"All {updated_count} detections merged to {species.name}",
            "species_id": species_id,
            "updated_count": updated_count,
        }, 200
