"""Monthly PDF report generation. Branded, professional layout."""
from datetime import datetime, timezone, timedelta
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart

# Brand colors (match app theme)
BRAND_PRIMARY = colors.HexColor('#10B981')   # Emerald
BRAND_SECONDARY = colors.HexColor('#0EA5E9')  # Sky
BRAND_DARK = colors.HexColor('#0F172A')      # Slate 900
BRAND_PAPER = colors.HexColor('#1E293B')     # Slate 800
TEXT_PRIMARY = colors.HexColor('#0F172A')
TEXT_SECONDARY = colors.HexColor('#64748B')  # Slate 500
BG_ALT = colors.HexColor('#F8FAFC')           # Slate 50
WHITE = colors.white

def _build_header_footer(canv, doc, month_label, is_first_page=False):
    """Draw branded header and footer on each page."""
    page_width = A4[0]
    page_height = A4[1]
    margin = 2 * cm

    # Header: brand bar
    canv.setFillColor(BRAND_DARK)
    canv.rect(0, page_height - 28 * mm, page_width, 28 * mm, fill=1, stroke=0)

    canv.setFillColor(WHITE)
    canv.setFont('Helvetica-Bold', 16)
    canv.drawString(margin, page_height - 20 * mm, 'BirdLense Hub')

    canv.setFont('Helvetica', 10)
    canv.setFillColor(colors.HexColor('#94A3B8'))
    canv.drawString(margin, page_height - 25 * mm, month_label)

    # Accent line
    canv.setFillColor(BRAND_PRIMARY)
    canv.rect(margin, page_height - 28 * mm, 40 * mm, 2 * mm, fill=1, stroke=0)

    # Footer
    canv.setFillColor(TEXT_SECONDARY)
    canv.setFont('Helvetica', 8)
    footer_y = 15 * mm
    canv.drawString(margin, footer_y, f'Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}')
    canv.drawRightString(page_width - margin, footer_y, f'Page {doc.page}')
    canv.drawCentredString(page_width / 2, footer_y, 'BirdLense Hub')


def build_monthly_report(start_dt, end_dt, top_species, stats, month_label):
    """Build PDF report for a month. Returns bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=3.2 * cm,
        bottomMargin=2.2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=22,
        spaceAfter=6,
        textColor=TEXT_PRIMARY,
        fontName='Helvetica-Bold',
    )
    subtitle_style = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=16,
        textColor=TEXT_SECONDARY,
    )
    heading_style = ParagraphStyle(
        'ReportHeading',
        parent=styles['Heading2'],
        fontSize=13,
        spaceAfter=10,
        spaceBefore=14,
        textColor=TEXT_PRIMARY,
        fontName='Helvetica-Bold',
        borderPadding=(0, 0, 4, 0),
        borderColor=BRAND_PRIMARY,
        borderWidth=0,
        leftIndent=0,
    )
    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontSize=10,
        textColor=TEXT_PRIMARY,
        spaceAfter=6,
    )

    story = []

    # Title block
    story.append(Paragraph(month_label, title_style))
    story.append(Paragraph(
        'Monthly Activity Report — Bird detection statistics from your feeder',
        subtitle_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    # Executive summary card
    story.append(Paragraph('Executive Summary', heading_style))
    summary_data = [
        ['Metric', 'Value'],
        ['Unique species', str(stats.get('uniqueSpecies', 0))],
        ['Total visits', str(stats.get('totalDetections', 0))],
        ['Recording time (video)', _format_seconds(stats.get('videoDuration', 0))],
        ['Recording time (audio)', _format_seconds(stats.get('audioDuration', 0))],
        ['Avg visit duration', _format_seconds(stats.get('avgVisitDuration', 0))],
    ]
    t = Table(summary_data, colWidths=[8 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), WHITE),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, BG_ALT]),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 1 * cm))

    # Top species
    story.append(Paragraph('Top Species', heading_style))
    if top_species:
        species_data = [['#', 'Species', 'Visits']]
        for i, sp in enumerate(top_species[:5], 1):
            total = sum(sp.get('detections', []) or [0])
            species_data.append([str(i), sp.get('name', '—'), str(total)])
        t2 = Table(species_data, colWidths=[1.5 * cm, 10 * cm, 3 * cm])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_SECONDARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), WHITE),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, BG_ALT]),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        story.append(t2)
        story.append(Spacer(1, 0.8 * cm))

        # Bar chart
        if len(top_species) >= 1:
            drawing = Drawing(400, 200)
            bc = VerticalBarChart()
            bc.x = 60
            bc.y = 40
            bc.height = 140
            bc.width = 320
            bc.data = [[sum(sp.get('detections', []) or [0]) for sp in top_species[:5]]]
            bc.strokeColor = BRAND_PRIMARY
            bc.fillColor = BRAND_PRIMARY
            bc.valueAxis.valueMin = 0
            max_val = max((sum(sp.get('detections', []) or [0]) for sp in top_species[:5]))
            bc.valueAxis.valueMax = max_val * 1.15 if max_val > 0 else 1
            bc.categoryAxis.labels.boxAnchor = 'ne'
            bc.categoryAxis.labels.dx = 8
            bc.categoryAxis.labels.dy = -2
            bc.categoryAxis.labels.angle = 30
            bc.categoryAxis.labels.fontSize = 9
            bc.categoryAxis.categoryNames = [
                (sp.get('name', '')[:18] + '…') if len(sp.get('name', '')) > 18 else sp.get('name', '')
                for sp in top_species[:5]
            ]
            drawing.add(bc)
            story.append(drawing)
    else:
        story.append(Paragraph(
            'No species detected in this period.',
            ParagraphStyle('Empty', parent=body_style, textColor=TEXT_SECONDARY),
        ))

    story.append(Spacer(1, 1 * cm))

    # Methodology
    story.append(Paragraph('About this report', heading_style))
    story.append(Paragraph(
        'This report is generated automatically by BirdLense Hub. Data is based on bird detections '
        'from your feeder cameras using YOLO classification, optionally combined with Frigate and BirdNET. '
        'Events are grouped into species visits; charts count visits (sessions), not raw detection segments. '
        'Recording time reflects video and audio duration associated with detected visits.',
        ParagraphStyle('Method', parent=body_style, fontSize=9, textColor=TEXT_SECONDARY),
    ))

    def on_first_page(canv, doc):
        _build_header_footer(canv, doc, month_label, is_first_page=True)

    def on_later_pages(canv, doc):
        _build_header_footer(canv, doc, month_label, is_first_page=False)

    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
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
    from util import GENERIC_BIRD_SPECIES

    exclude_bird = Species.name != GENERIC_BIRD_SPECIES

    # Top species by visit count in period; hourly bars = visits starting in that hour (UTC hour of DB timestamp).
    top_query = (
        session.query(
            Species.id.label('id'),
            Species.name.label('name'),
            *[
                func.sum(
                    case(
                        (func.strftime('%H', SpeciesVisit.start_time) == str(h).zfill(2),
                         1),
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
            exclude_bird,
        )
        .group_by(Species.id, Species.name)
        .order_by(func.count(SpeciesVisit.id).desc())
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

    # Stats (visit rows, same semantics as Overview)
    stats_row = (
        session.query(
            func.count(distinct(SpeciesVisit.species_id)).label('uniqueSpecies'),
            func.count(SpeciesVisit.id).label('totalDetections'),
            func.avg(
                func.strftime('%s', SpeciesVisit.end_time) -
                func.strftime('%s', SpeciesVisit.start_time)
            ).label('avgVisitDuration'),
        )
        .join(Species, SpeciesVisit.species_id == Species.id)
        .filter(
            SpeciesVisit.start_time >= start_dt,
            SpeciesVisit.start_time <= end_dt,
            exclude_bird,
        )
        .first()
    )

    # Recording time: сумма длительностей видеофайлов за период (как в Overview)
    video_dur_expr = (
        func.strftime('%s', Video.end_time) - func.strftime('%s', Video.start_time)
    )
    recording_sec = (
        session.query(func.sum(video_dur_expr).label('total'))
        .filter(
            Video.start_time >= start_dt,
            Video.start_time <= end_dt,
        )
        .scalar()
    ) or 0

    # Audio detection time (VideoSpecies)
    dur_expr = case(
        (VideoSpecies.end_time >= VideoSpecies.start_time,
         VideoSpecies.end_time - VideoSpecies.start_time),
        else_=0
    )
    audio_duration = (
        session.query(func.sum(case((VideoSpecies.source == 'audio', dur_expr), else_=0)))
        .join(SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id)
        .filter(
            SpeciesVisit.start_time >= start_dt,
            SpeciesVisit.start_time <= end_dt,
        )
        .scalar()
    ) or 0

    stats = {
        'uniqueSpecies': stats_row.uniqueSpecies or 0,
        'totalDetections': stats_row.totalDetections or 0,
        'avgVisitDuration': round(stats_row.avgVisitDuration or 0),
        'videoDuration': round(recording_sec),
        'audioDuration': round(audio_duration),
    }

    return top_species, stats
