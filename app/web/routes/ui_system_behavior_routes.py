"""Переобучение behavior baseline из меток в хабе (только админ / пароль настроек, #416)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import jsonify

from routes.http_guards import require_ui_settings_password
from services.api_json_validation import parse_request_json_object_allow_empty
from services.behavior_baseline_retrain_service import run_behavior_baseline_retrain_from_hub

if TYPE_CHECKING:
    from flask import Flask

_log = logging.getLogger(__name__)


def register_ui_system_behavior_routes(app: Flask) -> None:
    @app.route("/api/ui/system/behavior-baseline/retrain", methods=["POST"])
    @require_ui_settings_password
    def behavior_baseline_retrain_from_hub():
        from flask import request as req

        payload, v_err = parse_request_json_object_allow_empty(req)
        if v_err is not None:
            return v_err, 400
        max_iter = 500
        seed = 42
        max_videos = 2000
        if isinstance(payload, dict):
            try:
                if "max_iter" in payload and payload["max_iter"] is not None:
                    max_iter = int(payload["max_iter"])
                if "seed" in payload and payload["seed"] is not None:
                    seed = int(payload["seed"])
                if "max_videos" in payload and payload["max_videos"] is not None:
                    max_videos = int(payload["max_videos"])
            except (TypeError, ValueError):
                return {"error": "invalid_numeric_parameter"}, 400
        if max_iter < 50 or max_iter > 5000:
            return {"error": "max_iter_out_of_range"}, 400
        if max_videos < 4 or max_videos > 10_000:
            return {"error": "max_videos_out_of_range"}, 400
        try:
            body = run_behavior_baseline_retrain_from_hub(
                max_iter=max_iter,
                seed=seed,
                max_videos=max_videos,
            )
        except ValueError as e:
            _log.warning("behavior retrain validation: %s", e)
            return {"error": str(e)}, 400
        except RuntimeError as e:
            if "scikit-learn" in str(e).lower():
                return {"error": "scikit_learn_not_installed"}, 501
            _log.exception("behavior retrain failed")
            return {"error": str(e)}, 500
        except Exception:
            _log.exception("behavior retrain failed")
            return {"error": "behavior_retrain_failed"}, 500
        return jsonify(body), 200
