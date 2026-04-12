"""Анонимная статистика браузеров и прореживание рядов (#265)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from models import SiteVisitor, db


def downsample_evenly(items, max_n: int):
    """Равномерно проредить список до max_n элементов (сохраняем концы)."""
    n = len(items)
    if n <= max_n or max_n < 2:
        return items
    out = []
    for i in range(max_n):
        idx = int(round(i * (n - 1) / (max_n - 1)))
        out.append(items[idx])
    return out


def collect_visitor_stats(visitors_days: int = 7) -> dict:
    """Анонимные счётчики по SiteVisitor."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    days = max(1, min(int(visitors_days or 7), 365))
    start_utc = now_utc - timedelta(days=days)
    browser_count = (
        db.session.query(
            func.count(func.distinct(SiteVisitor.browser_hash)),
        )
        .filter(
            SiteVisitor.last_seen_at >= start_utc,
        )
        .scalar()
        or 0
    )
    unique_visits = (
        db.session.query(
            func.count(SiteVisitor.id),
        )
        .filter(
            SiteVisitor.last_seen_at >= start_utc,
        )
        .scalar()
        or 0
    )
    active_days = (
        db.session.query(
            func.count(func.distinct(SiteVisitor.seen_day)),
        )
        .filter(
            SiteVisitor.last_seen_at >= start_utc,
        )
        .scalar()
        or 0
    )
    raw_breakdown = (
        db.session.query(
            SiteVisitor.device_class,
            func.count(func.distinct(SiteVisitor.browser_hash)),
        )
        .filter(
            SiteVisitor.last_seen_at >= start_utc,
        )
        .group_by(SiteVisitor.device_class)
        .all()
    )
    breakdown = {"desktop": 0, "mobile": 0, "tablet": 0, "unknown": 0}
    for device_class, count in raw_breakdown:
        key = str(device_class or "unknown").strip().lower()
        if key not in breakdown:
            key = "unknown"
        breakdown[key] = int(count or 0)
    return {
        "period_days": days,
        "browser_count": int(browser_count),
        "unique_visits": int(unique_visits),
        "active_days": int(active_days),
        "device_breakdown": breakdown,
        "method": "anonymous_browser_id",
    }


def device_class_from_user_agent(user_agent: str) -> str:
    ua = (user_agent or "").strip().lower()
    if not ua:
        return "unknown"
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "android" in ua and "mobile" not in ua:
        return "tablet"
    if "iphone" in ua or "mobile" in ua or "android" in ua or "windows phone" in ua:
        return "mobile"
    return "desktop"


def browser_hash(raw_browser_id: str) -> str:
    return hashlib.sha256(raw_browser_id.encode("utf-8")).hexdigest()
