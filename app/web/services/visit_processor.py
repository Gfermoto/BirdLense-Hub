"""Сборка ``SpeciesVisit`` и ``VideoSpecies`` из детекций процессора (видео/аудио)."""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
import json

from models import Video, Species, VideoSpecies, SpeciesVisit
from sqlalchemy import text
from services.species_identity_service import SpeciesIdentityService


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC). SQLite returns naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _review_reason_from_detection(det: dict) -> str | None:
    """Normalize optional review reason fields from processor payload."""
    reason = (det.get("review_reason") or "").strip()
    if reason:
        return reason
    if bool(det.get("classifier_needs_review")):
        return "classifier_uncertainty"
    return None


class VisitProcessor:
    """Правила склейки визитов по таймауту и привязки детекций к видео."""

    def __init__(
        self,
        db,
        logger,
        visit_timeout: int = 60,
        *,
        update_species_metadata: bool = True,
        species_identity_service: SpeciesIdentityService | None = None,
    ):
        self.db = db
        self.logger = logger
        self.visit_timeout = visit_timeout
        # Kept for backward compatibility. Hot-path metadata enrichment is disabled.
        self.update_species_metadata = bool(update_species_metadata)
        self.species_identity = species_identity_service or SpeciesIdentityService(db, logger)

    def process_video_detection(
        self,
        species: Species,
        video: Video,
        detection_start: float,
        detection_end: float,
        confidence: float,
        track_id: Optional[int] = None,
        frames: Optional[List[Dict]] = None,
        detection_provider: Optional[str] = None,
        classifier_entropy: float | None = None,
        classifier_top1_top2_margin: float | None = None,
        classifier_needs_review: bool = False,
        review_reason: str | None = None,
        individual_nickname: str | None = None,
    ) -> Tuple[SpeciesVisit, VideoSpecies]:
        """
        Process a video detection and create/update associated visit.
        Returns the visit and video_species record.
        """
        video_start = _ensure_utc(video.start_time)
        detection_time = video_start + timedelta(seconds=detection_start)
        visit, _ = self.get_or_create_visit(species, detection_time)

        # Extend visit duration
        visit.end_time = max(visit.end_time, video_start + timedelta(seconds=detection_end))
        video_species = VideoSpecies(
            species_id=species.id,
            start_time=detection_start,
            end_time=detection_end,
            confidence=confidence,
            source="video",
            detection_provider=detection_provider,
            track_id=track_id,
            classifier_entropy=classifier_entropy,
            classifier_top1_top2_margin=classifier_top1_top2_margin,
            classifier_needs_review=bool(classifier_needs_review),
            review_reason=review_reason,
            individual_nickname=individual_nickname,
            created_at=detection_time,
            species_visit=visit,
            video=video,
            frames=json.dumps(frames) if frames else None,
        )
        self.db.session.add(video_species)

        return visit, video_species

    def process_video_detection_review_only(
        self,
        species: Species,
        video: Video,
        detection_start: float,
        detection_end: float,
        confidence: float,
        *,
        track_id: Optional[int] = None,
        frames: Optional[List[Dict]] = None,
        detection_provider: Optional[str] = None,
        classifier_entropy: float | None = None,
        classifier_top1_top2_margin: float | None = None,
        classifier_needs_review: bool = False,
        review_reason: str | None = None,
        individual_nickname: str | None = None,
    ) -> VideoSpecies:
        """Persist a video detection without creating/extending a SpeciesVisit."""
        video_start = _ensure_utc(video.start_time)
        detection_time = video_start + timedelta(seconds=detection_start)
        video_species = VideoSpecies(
            species_id=species.id,
            start_time=detection_start,
            end_time=detection_end,
            confidence=confidence,
            source="video",
            detection_provider=detection_provider,
            track_id=track_id,
            classifier_entropy=classifier_entropy,
            classifier_top1_top2_margin=classifier_top1_top2_margin,
            classifier_needs_review=bool(classifier_needs_review),
            review_reason=review_reason,
            individual_nickname=individual_nickname,
            created_at=detection_time,
            species_visit_id=None,
            video=video,
            frames=json.dumps(frames) if frames else None,
        )
        self.db.session.add(video_species)
        return video_species

    def _upsert_reid_embedding_from_detection(
        self,
        *,
        video_species: VideoSpecies,
        detection_row: Dict,
    ) -> None:
        self.db.session.flush()
        emb = detection_row.get("reid_embedding")
        if not isinstance(emb, list) or not emb:
            return
        vals: list[float] = []
        for v in emb:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                return
        dim = int(detection_row.get("reid_dim") or len(vals))
        if dim <= 0 or dim != len(vals):
            return
        model = str(detection_row.get("reid_model") or "dinov2_vits14").strip()
        if not model:
            model = "dinov2_vits14"
        crop_key = str(detection_row.get("reid_crop_key") or "").strip()
        if not crop_key:
            crop_key = f"runtime://video/{video_species.video_id}/vs/{video_species.id}"

        self.db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS reid_embedding (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_species_id INTEGER,
                    video_id INTEGER,
                    species_id INTEGER,
                    track_id INTEGER,
                    crop_path TEXT NOT NULL UNIQUE,
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    species_name TEXT,
                    individual_label TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        self.db.session.execute(
            text(
                """
                INSERT INTO reid_embedding (
                    video_species_id, video_id, species_id, track_id,
                    crop_path, model, dim, embedding_json,
                    species_name, individual_label
                ) VALUES (
                    :video_species_id, :video_id, :species_id, :track_id,
                    :crop_path, :model, :dim, :embedding_json,
                    :species_name, :individual_label
                )
                ON CONFLICT(crop_path) DO UPDATE SET
                    video_species_id=excluded.video_species_id,
                    video_id=excluded.video_id,
                    species_id=excluded.species_id,
                    track_id=excluded.track_id,
                    model=excluded.model,
                    dim=excluded.dim,
                    embedding_json=excluded.embedding_json,
                    species_name=excluded.species_name,
                    individual_label=excluded.individual_label
                """
            ),
            {
                "video_species_id": int(video_species.id),
                "video_id": int(video_species.video_id),
                "species_id": int(video_species.species_id),
                "track_id": video_species.track_id,
                "crop_path": crop_key,
                "model": model,
                "dim": int(dim),
                "embedding_json": json.dumps(vals, separators=(",", ":")),
                "species_name": str(video_species.species.name),
                "individual_label": (video_species.individual_nickname or None),
            },
        )

    def process_audio_detection(
        self,
        species: Species,
        video: Video,
        detection_start: float,
        detection_end: float,
        confidence: float,
        detection_provider: Optional[str] = None,
    ) -> Optional[VideoSpecies]:
        """Аудио-детекция → привязка к активному визиту."""
        video_start = _ensure_utc(video.start_time)
        detection_time = video_start + timedelta(seconds=detection_start)
        visit = self._find_active_visit_for_audio(species, detection_time)

        if not visit:
            return None
        if detection_time < _ensure_utc(visit.start_time):
            visit.start_time = detection_time

        video_species = VideoSpecies(
            species_id=species.id,
            start_time=detection_start,
            end_time=detection_end,
            confidence=confidence,
            source="audio",
            detection_provider=detection_provider or "birdnet_mqtt",
            created_at=detection_time,
            species_visit=visit,
            video=video,
        )
        self.db.session.add(video_species)

        return video_species

    def process_detections(self, video: Video, detections: List[Dict]) -> List[VideoSpecies]:
        """Обработка детекций видео, создание визитов и VideoSpecies."""
        video_species_records = []
        visits_to_update = {}  # Map (species_id, start_time) to visit data
        deduped_detections = self._deduplicate_detections(detections)

        # First pass: Process all detections
        for det in deduped_detections:
            visit_eligible = bool(det.get("visit_eligible", True))
            provider = str(det.get("detection_provider") or det.get("source") or "ingest").strip().lower()
            raw_aliases = [
                *(det.get("source_aliases") or []),
                det.get("species_name_raw"),
                det.get("species"),
            ]
            scientific_aliases = list(det.get("source_scientific_names") or [])
            species = self.species_identity.resolve_or_create_species(
                det["species_name"],
                source=f"ingest:{provider}" if provider else "ingest",
                audit_aliases=[str(x).strip() for x in raw_aliases if str(x or "").strip()],
                audit_scientific_names=[str(x).strip() for x in scientific_aliases if str(x or "").strip()],
            )
            if not species:
                self.logger.warning(f'Could not create species "{det["species_name"]}"')
                continue

            if det["source"] == "video":
                if visit_eligible:
                    visit, video_species = self.process_video_detection(
                        species=species,
                        video=video,
                        detection_start=det["start_time"],
                        detection_end=det["end_time"],
                        confidence=det["confidence"],
                        track_id=det.get("track_id"),
                        frames=det.get("frames"),
                        detection_provider=det.get("detection_provider"),
                        classifier_entropy=det.get("classifier_entropy"),
                        classifier_top1_top2_margin=det.get("classifier_top1_top2_margin"),
                        classifier_needs_review=bool(det.get("classifier_needs_review")),
                        review_reason=_review_reason_from_detection(det),
                        individual_nickname=(det.get("individual_nickname") or None),
                    )
                    self._upsert_reid_embedding_from_detection(
                        video_species=video_species,
                        detection_row=det,
                    )
                    visit_key = (visit.species_id, visit.start_time)
                    if visit_key not in visits_to_update:
                        visits_to_update[visit_key] = {"visit": visit, "detections": []}
                    visits_to_update[visit_key]["detections"].append(video_species)
                    video_species_records.append(video_species)
                else:
                    video_species = self.process_video_detection_review_only(
                        species=species,
                        video=video,
                        detection_start=det["start_time"],
                        detection_end=det["end_time"],
                        confidence=det["confidence"],
                        track_id=det.get("track_id"),
                        frames=det.get("frames"),
                        detection_provider=det.get("detection_provider"),
                        classifier_entropy=det.get("classifier_entropy"),
                        classifier_top1_top2_margin=det.get("classifier_top1_top2_margin"),
                        classifier_needs_review=bool(det.get("classifier_needs_review")),
                        review_reason=_review_reason_from_detection(det),
                        individual_nickname=(det.get("individual_nickname") or None),
                    )
                    self._upsert_reid_embedding_from_detection(
                        video_species=video_species,
                        detection_row=det,
                    )
                    video_species_records.append(video_species)
            else:  # audio
                video_species = self.process_audio_detection(
                    species=species,
                    video=video,
                    detection_start=det["start_time"],
                    detection_end=det["end_time"],
                    confidence=det["confidence"],
                    detection_provider=det.get("detection_provider"),
                )
                if video_species:
                    video_species_records.append(video_species)

        # Second pass: Update simultaneous counts for affected visits
        for visit_data in visits_to_update.values():
            self.update_simultaneous_count(visit_data["visit"], visit_data["detections"])

        return video_species_records

    @staticmethod
    def _dedup_detection_key(det: Dict) -> tuple:
        def _round_num(v, ndigits):
            try:
                return round(float(v), ndigits)
            except (TypeError, ValueError):
                return None

        track_id = det.get("track_id")
        try:
            track_id = int(track_id) if track_id is not None else None
        except (TypeError, ValueError):
            track_id = None
        return (
            str(det.get("source") or "").strip().lower(),
            str(det.get("species_name") or "").strip().lower(),
            _round_num(det.get("start_time"), 3),
            _round_num(det.get("end_time"), 3),
            _round_num(det.get("confidence"), 4),
            track_id,
            str(det.get("detection_provider") or "").strip().lower(),
            bool(det.get("visit_eligible", True)),
        )

    def _deduplicate_detections(self, detections: List[Dict]) -> List[Dict]:
        if not detections:
            return []
        out: List[Dict] = []
        seen: set[tuple] = set()
        for det in detections:
            key = self._dedup_detection_key(det)
            if key in seen:
                continue
            seen.add(key)
            out.append(det)
        removed = len(detections) - len(out)
        if removed > 0:
            self.logger.info("VisitProcessor: dropped %d duplicate detections", removed)
        return out

    def get_or_create_visit(self, species: Species, detection_time: datetime) -> Tuple[SpeciesVisit, bool]:
        """
        Gets existing or creates new visit for a species.
        Always creates visits at the detection species level.
        Returns tuple of (visit, was_created).
        """
        # Look for existing visit that ended recently or is still ongoing
        cutoff_time = detection_time - timedelta(seconds=self.visit_timeout)
        future_tolerance = detection_time + timedelta(seconds=self.visit_timeout)
        recent_visit = (
            SpeciesVisit.query.filter(
                SpeciesVisit.species_id == species.id,
                SpeciesVisit.end_time >= cutoff_time,
                SpeciesVisit.start_time <= future_tolerance,
            )
            .order_by(SpeciesVisit.end_time.desc())
            .first()
        )

        if recent_visit:
            recent_visit.start_time = recent_visit.start_time.replace(tzinfo=timezone.utc)
            recent_visit.end_time = recent_visit.end_time.replace(tzinfo=timezone.utc)
            recent_visit.created_at = recent_visit.created_at.replace(tzinfo=timezone.utc)
            if detection_time < recent_visit.start_time:
                recent_visit.start_time = detection_time
            return recent_visit, False

        visit = SpeciesVisit(
            species_id=species.id, start_time=detection_time, end_time=detection_time, max_simultaneous=1
        )
        self.db.session.add(visit)
        return visit, True

    def get_or_create_species(self, name: str) -> Optional[Species]:
        """Resolve or create a catalog species via the dedicated identity service."""
        return self.species_identity.resolve_or_create_species(name, source="ingest")

    def _find_active_visit_for_audio(self, audio_species: Species, detection_time: datetime) -> Optional[SpeciesVisit]:
        """Активный визит для аудио: вид или его дочерние."""
        cutoff_time = detection_time - timedelta(seconds=self.visit_timeout)
        future_tolerance = detection_time + timedelta(seconds=self.visit_timeout)

        child_species = Species.query.filter_by(parent_id=audio_species.id).all()
        species_ids = [audio_species.id] + [s.id for s in child_species]

        return (
            SpeciesVisit.query.filter(
                SpeciesVisit.species_id.in_(species_ids),
                SpeciesVisit.end_time >= cutoff_time,
                SpeciesVisit.start_time <= future_tolerance,
            )
            .order_by(SpeciesVisit.end_time.desc())
            .first()
        )

    def update_simultaneous_count(self, visit: SpeciesVisit, current_detections: List[VideoSpecies]) -> None:
        """max_simultaneous по перекрывающимся детекциям в текущем видео."""
        video_detections = [vs for vs in current_detections if vs.source == "video"]
        if not video_detections:
            return
        sorted_detections = sorted(video_detections, key=lambda x: x.start_time)
        max_concurrent = 1
        for i, curr in enumerate(sorted_detections):
            concurrent = 1
            for other in sorted_detections[i + 1 :]:
                if curr.end_time >= other.start_time:
                    concurrent += 1
                else:
                    break
            max_concurrent = max(max_concurrent, concurrent)
        visit.max_simultaneous = max(visit.max_simultaneous, max_concurrent)

    def _get_or_create_visit(self, species: Species, detection_time: datetime) -> Tuple[SpeciesVisit, bool]:
        return self.get_or_create_visit(species, detection_time)

    def _get_or_create_species(self, name: str) -> Optional[Species]:
        return self.get_or_create_species(name)

    def _update_simultaneous_count(self, visit: SpeciesVisit, current_detections: List[VideoSpecies]) -> None:
        self.update_simultaneous_count(visit, current_detections)
