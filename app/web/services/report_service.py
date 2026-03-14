"""Monthly PDF report generation."""
from datetime import datetime, timezone, timedelta
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart


def _ensure_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def build_monthly_report(start_dt, end_dt, top_species, stats, month_label):
    """Build PDF report for a month. Returns bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        'ReportHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=8,
    )
    body_style = styles['Normal']

    story = []

    # Title
    story.append(Paragraph(f"BirdLense Hub — {month_label}", title_style))
    story.append(Spacer(1, 0.5 * cm))

    # Summary
    story.append(Paragraph("Summary", heading_style))
    summary_data = [
        ["Metric", "Value"],
        ["Unique species", str(stats.get('uniqueSpecies', 0))],
        ["Total detections", str(stats.get('totalDetections', 0))],
        ["Recording time (video)", _format_seconds(stats.get('videoDuration', 0))],
        ["Recording time (audio)", _format_seconds(stats.get('audioDuration', 0))],
        ["Avg visit duration", f"{stats.get('avgVisitDuration', 0)} sec"],
    ]
    t = Table(summary_data, colWidths=[8 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10B981')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(t)
    story.append(Spacer(1, 1 * cm))

    # Top species
    story.append(Paragraph("Top 5 Species", heading_style))
    if top_species:
        species_data = [["#", "Species", "Detections"]]
        for i, sp in enumerate(top_species[:5], 1):
            total = sum(sp.get('detections', []) or [0])
            species_data.append([str(i), sp.get('name', '—'), str(total)])
        t2 = Table(species_data, colWidths=[1.5 * cm, 10 * cm, 3 * cm])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0EA5E9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        story.append(t2)
        story.append(Spacer(1, 0.5 * cm))

        # Simple bar chart
        if len(top_species) >= 1:
            drawing = Drawing(400, 180)
            bc = VerticalBarChart()
            bc.x = 50
            bc.y = 30
            bc.height = 130
            bc.width = 320
            bc.data = [[sum(sp.get('detections', []) or [0]) for sp in top_species[:5]]]
            bc.strokeColor = colors.HexColor('#10B981')
            bc.fillColor = colors.HexColor('#10B981')
            bc.valueAxis.valueMin = 0
            max_val = max((sum(sp.get('detections', []) or [0]) for sp in top_species[:5]))
            bc.valueAxis.valueMax = max_val * 1.1 if max_val > 0 else 1
            bc.categoryAxis.labels.boxAnchor = 'ne'
            bc.categoryAxis.labels.dx = 8
            bc.categoryAxis.labels.dy = -2
            bc.categoryAxis.labels.angle = 30
            bc.categoryAxis.categoryNames = [
                (sp.get('name', '')[:20] + '…') if len(sp.get('name', '')) > 20 else sp.get('name', '')
                for sp in top_species[:5]
            ]
            drawing.add(bc)
            story.append(drawing)
    else:
        story.append(Paragraph("No species detected in this period.", body_style))

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f"Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        ParagraphStyle('Footer', parent=body_style, fontSize=8, textColor=colors.grey)
    ))

    doc.build(story)
    return buffer.getvalue()


def _format_seconds(sec):
    if sec < 60:
        return f"{int(sec)} sec"
    if sec < 3600:
        return f"{int(sec / 60)} min"
    return f"{sec / 3600:.1f} hrs"


def get_monthly_report_data(session, start_dt, end_dt):
    """Query DB for monthly stats. Returns (top_species, stats)."""
    from models import Species, SpeciesVisit, VideoSpecies, Video
    from sqlalchemy import func, case, distinct

    # Top species (by total detections in period)
    top_query = (
        session.query(
            Species.id.label('id'),
            Species.name.label('name'),
            *[
                func.sum(
                    case(
                        (func.strftime('%H', SpeciesVisit.start_time) == str(h).zfill(2),
                         SpeciesVisit.max_simultaneous),
                        else_=0
                    )
                ).label(f'detection_hour_{h}')
                for h in range(24)
            ]
        )
        .join(SpeciesVisit, SpeciesVisit.species_id == Species.id)
        .filter(
            SpeciesVisit.start_time >= start_dt,
            SpeciesVisit.start_time <= end_dt,
        )
        .group_by(Species.id, Species.name)
        .order_by(func.sum(SpeciesVisit.max_simultaneous).desc())
        .limit(10)
        .all()
    )
    top_species = [
        {
            'id': row.id,
            'name': row.name,
            'detections': [getattr(row, f'detection_hour_{h}', 0) or 0 for h in range(24)],
        }
        for row in top_query
    ]

    # Stats
    stats_row = (
        session.query(
            func.count(distinct(SpeciesVisit.species_id)).label('uniqueSpecies'),
            func.sum(SpeciesVisit.max_simultaneous).label('totalDetections'),
            func.avg(
                func.strftime('%s', SpeciesVisit.end_time) -
                func.strftime('%s', SpeciesVisit.start_time)
            ).label('avgVisitDuration'),
        )
        .filter(
            SpeciesVisit.start_time >= start_dt,
            SpeciesVisit.start_time <= end_dt,
        )
        .first()
    )

    source_duration = (
        session.query(
            func.sum(
                case(
                    (VideoSpecies.source == 'video',
                     VideoSpecies.end_time - VideoSpecies.start_time),
                    else_=0
                )
            ).label('video_duration'),
            func.sum(
                case(
                    (VideoSpecies.source == 'audio',
                     VideoSpecies.end_time - VideoSpecies.start_time),
                    else_=0
                )
            ).label('audio_duration'),
        )
        .join(SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id)
        .filter(
            SpeciesVisit.start_time >= start_dt,
            SpeciesVisit.start_time <= end_dt,
        )
        .first()
    )

    stats = {
        'uniqueSpecies': stats_row.uniqueSpecies or 0,
        'totalDetections': stats_row.totalDetections or 0,
        'avgVisitDuration': round(stats_row.avgVisitDuration or 0),
        'videoDuration': round(source_duration.video_duration or 0),
        'audioDuration': round(source_duration.audio_duration or 0),
    }

    return top_species, stats
