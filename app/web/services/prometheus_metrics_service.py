"""Текстовый exposition для Prometheus (#265)."""
from __future__ import annotations

from sqlalchemy import func

from models import Video, VideoSpecies, db

from services.activity_notify_insights_service import (
    notify_delivery_24h,
    notify_fallback_by_reason_24h,
    notify_preview_by_source_24h,
    notify_preview_generated_by_source_24h,
)
from services.system_live_metrics_service import collect_live_system_metrics


def prometheus_metrics_body(app) -> str:
    sys_m = collect_live_system_metrics(app)
    detections = db.session.query(func.count(VideoSpecies.id)).scalar() or 0
    species_count = db.session.query(VideoSpecies.species_id).distinct().count()
    videos_count = db.session.query(func.count(Video.id)).scalar() or 0
    preview_by_source = notify_preview_by_source_24h()
    preview_generated_by_source = notify_preview_generated_by_source_24h()
    fallback_by_reason = notify_fallback_by_reason_24h()
    delivery_counts = notify_delivery_24h()
    lines = [
        '# HELP birdlense_cpu_usage_percent CPU usage',
        '# TYPE birdlense_cpu_usage_percent gauge',
        f'birdlense_cpu_usage_percent {sys_m["cpu"]["percent"]}',
        '# HELP birdlense_memory_used_percent Memory usage percent',
        '# TYPE birdlense_memory_used_percent gauge',
        f'birdlense_memory_used_percent {sys_m["memory"]["percent"]}',
        '# HELP birdlense_memory_total_bytes Memory total in bytes',
        '# TYPE birdlense_memory_total_bytes gauge',
        f'birdlense_memory_total_bytes {sys_m["memory"]["total_bytes"]}',
        '# HELP birdlense_memory_used_bytes Memory used in bytes',
        '# TYPE birdlense_memory_used_bytes gauge',
        f'birdlense_memory_used_bytes {sys_m["memory"]["used_bytes"]}',
        '# HELP birdlense_disk_used_percent Disk usage percent',
        '# TYPE birdlense_disk_used_percent gauge',
        f'birdlense_disk_used_percent {sys_m["disk"]["percent"]}',
        '# HELP birdlense_detections_total Total number of bird detections',
        '# TYPE birdlense_detections_total counter',
        f'birdlense_detections_total {detections}',
        '# HELP birdlense_species_count Number of unique species detected',
        '# TYPE birdlense_species_count gauge',
        f'birdlense_species_count {species_count}',
        '# HELP birdlense_videos_total Total number of recorded videos',
        '# TYPE birdlense_videos_total counter',
        f'birdlense_videos_total {videos_count}',
        '# HELP birdlense_notify_preview_24h '
        'Notification preview source counts for last 24h',
        '# TYPE birdlense_notify_preview_24h gauge',
    ]
    for src, count in preview_by_source.items():
        lines.append(f'birdlense_notify_preview_24h{{source="{src}"}} {count}')
    lines.extend([
        '# HELP birdlense_notify_preview_generated_24h '
        'Notification preview generation counts for last 24h',
        '# TYPE birdlense_notify_preview_generated_24h gauge',
    ])
    for src, count in preview_generated_by_source.items():
        lines.append(
            f'birdlense_notify_preview_generated_24h{{source="{src}"}} {count}',
        )
    lines.extend([
        '# HELP birdlense_notify_fallback_24h '
        'Notification fallback reason counts for last 24h',
        '# TYPE birdlense_notify_fallback_24h gauge',
    ])
    for reason, count in fallback_by_reason.items():
        lines.append(
            f'birdlense_notify_fallback_24h{{reason="{reason}"}} {count}',
        )
    lines.extend([
        '# HELP birdlense_notify_delivery_24h '
        'Notification delivery outcome counts for last 24h',
        '# TYPE birdlense_notify_delivery_24h gauge',
    ])
    for delivery, count in delivery_counts.items():
        lines.append(
            f'birdlense_notify_delivery_24h{{delivery="{delivery}"}} {count}',
        )
    if sys_m['gpu_percent'] is not None:
        lines.extend([
            '# HELP birdlense_gpu_usage_percent GPU usage',
            '# TYPE birdlense_gpu_usage_percent gauge',
            f'birdlense_gpu_usage_percent {sys_m["gpu_percent"]}',
        ])
    return '\n'.join(lines) + '\n'
