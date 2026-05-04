"""Приём от процессора: лог ingest, детекции, SSRF webhook, исходящий POST."""

from __future__ import annotations

import ipaddress
import json
import secrets
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

from models import ActivityLog, db


def log_ingest_activity(type_name: str, payload: dict) -> None:
    """Persist ActivityLog row; rollback on failure."""
    try:
        db.session.add(ActivityLog(type=type_name, data=json.dumps(payload)))
        db.session.commit()
    except Exception:
        db.session.rollback()


def processor_detection_payload(raw: dict) -> dict:
    """Strip unknown keys but keep explicit eligibility flags for VisitProcessor."""
    if not isinstance(raw, dict):
        return {}
    allowed = {
        "species_name",
        "species",
        "confidence",
        "start_time",
        "end_time",
        "source",
        "track_id",
        "frames",
        "detection_provider",
        "visit_eligible",
        "notification_eligible",
        "arbitration_reason",
        "decision_reason_before_arbitration",
        "decision_reason",
        "decision_kind",
        "outcome_bucket",
        "evidence_state",
        "trust_band",
        "detector_confidence",
        "classifier_confidence",
        "classifier_entropy",
        "classifier_top1_top2_margin",
        "classifier_needs_review",
        "review_reason",
        "individual_nickname",
        "reid_model",
        "reid_dim",
        "reid_embedding",
        "reid_crop_key",
        "reid_similarity",
    }
    return {k: raw[k] for k in allowed if k in raw}


def is_public_ip(ip: str) -> bool:
    """True if address is global (not private/loopback/etc.)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not any(
        (
            addr.is_private,
            addr.is_loopback,
            addr.is_link_local,
            addr.is_multicast,
            addr.is_reserved,
            addr.is_unspecified,
        )
    )


def is_safe_webhook_url(url: str) -> bool:
    """http(s) only; host resolves to public IPs only (SSRF guard)."""
    raw = (url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").strip()
    if not host:
        return False
    if host.lower() == "localhost":
        return False
    try:
        infos = socket.getaddrinfo(host, parsed.port or None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        addr = info[4][0]
        if not is_public_ip(addr):
            return False
    return True


def fire_webhook(url: str, species_list: list, start_time: datetime, logger) -> None:
    """POST each detection to webhook URL. Runs in thread, logs errors."""
    for sp in species_list:
        try:
            species_name = sp.get("species_name") or sp.get("species") or sp.get("name") or "unknown"
            confidence = float(sp.get("confidence") or 0)
            det_start = float(sp.get("start_time") or 0)
            detection_time = start_time + timedelta(seconds=det_start)
            if detection_time.tzinfo is None:
                detection_time = detection_time.replace(tzinfo=timezone.utc)
            payload = {
                "species": species_name,
                "confidence": round(confidence, 4),
                "time": detection_time.isoformat(),
                "source": sp.get("source", "video"),
            }
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.warning("Webhook POST failed: %s", e)


def check_processor_secret_token(*, request_token: str, env_secret: str, is_prod: bool) -> bool:
    """Accept request if token matches secret, or dev with empty secret."""
    secret = (env_secret or "").strip()
    token = request_token or ""
    if not secret:
        return not is_prod
    return secrets.compare_digest(token, secret)
