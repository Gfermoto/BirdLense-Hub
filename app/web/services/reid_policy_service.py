"""Re-ID suggestion policy (#390) — conservative defaults, config-driven thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app_config.app_config import app_config

from services.reid_contract import EMBEDDING_SCHEMA_V1, embedding_age_hours


@dataclass(frozen=True)
class ReidPolicyDecision:
    decision: str  # suggest_same_individual | inconclusive | suppressed
    reasons: list[str]
    effective_threshold: float | None = None
    mode: str | None = None


def _as_bool(val: Any, default: bool) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        s = val.strip().lower()
        if s in {"1", "true", "yes", "on"}:
            return True
        if s in {"0", "false", "no", "off"}:
            return False
    return default


def _as_float(val: Any, default: float) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except Exception:
        return default


def load_reid_policy_config() -> dict[str, Any]:
    """Normalize nested dict from YAML into a flat, typed policy view."""
    enabled = _as_bool(app_config.get("processor.reid_suggestions_enabled"), True)
    kill = _as_bool(app_config.get("processor.reid_kill_switch"), False)
    shadow = _as_bool(app_config.get("processor.reid_shadow_mode"), False)
    mode = str(app_config.get("processor.reid_embedding_pipeline_mode") or "offline_batch")

    default_tau = _as_float(app_config.get("processor.reid_default_similarity_threshold"), 0.86)
    diff_tau = _as_float(app_config.get("processor.reid_different_similarity_threshold"), 0.35)
    cross_boost = _as_float(app_config.get("processor.reid_cross_camera_threshold_boost"), 0.04)
    max_age = app_config.get("processor.reid_max_embedding_age_hours")
    try:
        max_age_f = float(max_age) if max_age is not None else None
    except Exception:
        max_age_f = None

    species_map = app_config.get("processor.reid_species_similarity_thresholds") or {}
    if not isinstance(species_map, dict):
        species_map = {}

    return {
        "enabled": enabled and not kill,
        "kill_switch": kill,
        "shadow_mode": shadow,
        "mode": mode,
        "expected_schema": EMBEDDING_SCHEMA_V1,
        "default_similarity_threshold": default_tau,
        "different_similarity_threshold": diff_tau,
        "cross_camera_threshold_boost": cross_boost,
        "max_embedding_age_hours": max_age_f,
        "species_thresholds": {str(k): _as_float(v, default_tau) for k, v in species_map.items()},
    }


def policy_snapshot() -> dict[str, Any]:
    cfg = load_reid_policy_config()
    return {
        "schema": "reid_policy@v1",
        "enabled": bool(cfg["enabled"]),
        "kill_switch": bool(cfg["kill_switch"]),
        "shadow_mode": bool(cfg["shadow_mode"]),
        "mode": str(cfg["mode"]),
        "expected_schema": str(cfg["expected_schema"]),
        "thresholds": {
            "default_similarity": float(cfg["default_similarity_threshold"]),
            "different_similarity": float(cfg["different_similarity_threshold"]),
            "cross_camera_boost": float(cfg["cross_camera_threshold_boost"]),
            "max_embedding_age_hours": cfg["max_embedding_age_hours"],
            "species_overrides_count": len(cfg["species_thresholds"]),
        },
    }


def species_threshold(species_name: str | None, cfg: dict[str, Any]) -> float:
    base = float(cfg["default_similarity_threshold"])
    if not species_name:
        return base
    over = cfg["species_thresholds"].get(str(species_name))
    if over is None:
        return base
    try:
        return float(over)
    except Exception:
        return base


def _embedding_contract_ok(
    *,
    schema: str | None,
    model_id: str | None,
    model_sha16: str | None,
    crop_fp: str | None,
    created_at: str | None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not schema or str(schema).strip() != EMBEDDING_SCHEMA_V1:
        reasons.append("bad_or_missing_embedding_schema")
    if not model_id or not str(model_id).strip():
        reasons.append("missing_embedding_model_id")
    if not model_sha16 or not str(model_sha16).strip():
        reasons.append("missing_embedding_model_sha16")
    if not crop_fp or not str(crop_fp).strip():
        reasons.append("missing_crop_fingerprint_sha16")
    if not created_at or not str(created_at).strip():
        reasons.append("missing_jsonl_created_at_utc")
    return (len(reasons) == 0), reasons


def evaluate_reid_candidate(
    *,
    cfg: dict[str, Any],
    species_name: str | None,
    similarity: float,
    anchor_video_path: str | None,
    candidate_video_path: str | None,
    anchor_created_at: str | None,
    candidate_created_at: str | None,
    anchor_schema: str | None,
    cand_schema: str | None,
    anchor_model_id: str | None,
    cand_model_id: str | None,
    anchor_dim: int | None,
    cand_dim: int | None,
    anchor_model_sha16: str | None,
    cand_model_sha16: str | None,
    anchor_crop_fp: str | None,
    cand_crop_fp: str | None,
    hours_apart: float | None,
) -> ReidPolicyDecision:
    if not cfg["enabled"]:
        return ReidPolicyDecision(decision="suppressed", reasons=["reid_disabled"], mode=str(cfg["mode"]))

    ok_a, reasons_a = _embedding_contract_ok(
        schema=anchor_schema,
        model_id=anchor_model_id,
        model_sha16=anchor_model_sha16,
        crop_fp=anchor_crop_fp,
        created_at=anchor_created_at,
    )
    ok_c, reasons_c = _embedding_contract_ok(
        schema=cand_schema,
        model_id=cand_model_id,
        model_sha16=cand_model_sha16,
        crop_fp=cand_crop_fp,
        created_at=candidate_created_at,
    )
    if not ok_a:
        return ReidPolicyDecision(
            decision="suppressed",
            reasons=["anchor_contract_incomplete"] + reasons_a,
            mode=str(cfg["mode"]),
        )
    if not ok_c:
        return ReidPolicyDecision(
            decision="suppressed",
            reasons=["candidate_contract_incomplete"] + reasons_c,
            mode=str(cfg["mode"]),
        )

    if anchor_schema != cand_schema:
        return ReidPolicyDecision(decision="suppressed", reasons=["schema_mismatch"], mode=str(cfg["mode"]))
    if anchor_model_id != cand_model_id:
        return ReidPolicyDecision(decision="suppressed", reasons=["embedding_model_id_mismatch"], mode=str(cfg["mode"]))
    if anchor_dim is not None and cand_dim is not None and int(anchor_dim) != int(cand_dim):
        return ReidPolicyDecision(decision="suppressed", reasons=["embedding_dim_mismatch"], mode=str(cfg["mode"]))
    if anchor_model_sha16 and cand_model_sha16 and str(anchor_model_sha16) != str(cand_model_sha16):
        return ReidPolicyDecision(
            decision="suppressed", reasons=["embedding_model_sha_mismatch"], mode=str(cfg["mode"])
        )

    max_age = cfg["max_embedding_age_hours"]
    if max_age is not None:
        aa = embedding_age_hours(anchor_created_at)
        ca = embedding_age_hours(candidate_created_at)
        if aa is None or ca is None:
            return ReidPolicyDecision(
                decision="suppressed", reasons=["embedding_freshness_unknown"], mode=str(cfg["mode"])
            )
        if aa > float(max_age) or ca > float(max_age):
            return ReidPolicyDecision(decision="suppressed", reasons=["embedding_stale"], mode=str(cfg["mode"]))

    cross_camera = False
    if anchor_video_path and candidate_video_path:
        a = str(anchor_video_path).replace("\\", "/")
        b = str(candidate_video_path).replace("\\", "/")
        cross_camera = a.rsplit("/", 1)[0] != b.rsplit("/", 1)[0]

    tau0 = species_threshold(species_name, cfg)
    tau = tau0 + (float(cfg["cross_camera_threshold_boost"]) if cross_camera else 0.0)
    tau = min(0.999, max(0.0, tau))

    if similarity < float(cfg["different_similarity_threshold"]):
        return ReidPolicyDecision(
            decision="inconclusive",
            reasons=["below_different_threshold"],
            effective_threshold=tau,
            mode=str(cfg["mode"]),
        )

    if similarity >= tau:
        if cfg["shadow_mode"]:
            return ReidPolicyDecision(
                decision="suppressed",
                reasons=["shadow_mode"],
                effective_threshold=tau,
                mode=str(cfg["mode"]),
            )
        reasons = []
        if cross_camera:
            reasons.append("cross_camera_stricter_threshold")
        if hours_apart is not None and hours_apart > 24 * 120:
            reasons.append("large_time_gap")
        return ReidPolicyDecision(
            decision="suggest_same_individual",
            reasons=reasons,
            effective_threshold=tau,
            mode=str(cfg["mode"]),
        )

    return ReidPolicyDecision(
        decision="inconclusive",
        reasons=["below_species_threshold"],
        effective_threshold=tau,
        mode=str(cfg["mode"]),
    )
