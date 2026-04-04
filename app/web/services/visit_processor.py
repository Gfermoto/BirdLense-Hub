from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
import json

from app_config.app_config import app_config
from models import Video, Species, VideoSpecies, SpeciesVisit
from services.species_catalog_allowlist_service import (
    load_catalog_allowlist_norm_keys,
    species_matches_allowlist,
)
from services.species_registry_service import resolve_species_name
from species_constants import GENERIC_BIRD_SPECIES
from util import (
    get_parent_name_for_species,
    load_species_canonical_mapping,
    update_species_info_from_wiki,
)


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC). SQLite returns naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class VisitProcessor:
    def __init__(self, db, logger, visit_timeout: int = 60):
        self.db = db
        self.logger = logger
        self.visit_timeout = visit_timeout

    def process_video_detection(self, species: Species, video: Video,
                                detection_start: float, detection_end: float,
                                confidence: float, track_id: Optional[int] = None,
                                frames: Optional[List[Dict]] = None,
                                detection_provider: Optional[str] = None
                                ) -> Tuple[SpeciesVisit, VideoSpecies]:
        """
        Process a video detection and create/update associated visit.
        Returns the visit and video_species record.
        """
        video_start = _ensure_utc(video.start_time)
        detection_time = video_start + timedelta(seconds=detection_start)
        visit, _ = self._get_or_create_visit(species, detection_time)

        # Extend visit duration
        visit.end_time = max(
            visit.end_time,
            video_start + timedelta(seconds=detection_end)
        )
        video_species = VideoSpecies(
            species_id=species.id,
            start_time=detection_start,
            end_time=detection_end,
            confidence=confidence,
            source='video',
            detection_provider=detection_provider,
            track_id=track_id,
            created_at=detection_time,
            species_visit=visit,
            video=video,
            frames=json.dumps(frames) if frames else None
        )
        self.db.session.add(video_species)

        return visit, video_species

    def process_audio_detection(self, species: Species, video: Video,
                                detection_start: float, detection_end: float,
                                confidence: float,
                                detection_provider: Optional[str] = None
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
            source='audio',
            detection_provider=detection_provider or 'birdnet_mqtt',
            created_at=detection_time,
            species_visit=visit,
            video=video
        )
        self.db.session.add(video_species)

        return video_species

    def process_detections(self, video: Video, detections: List[Dict]) -> List[VideoSpecies]:
        """Обработка детекций видео, создание визитов и VideoSpecies."""
        video_species_records = []
        visits_to_update = {}  # Map (species_id, start_time) to visit data

        # First pass: Process all detections
        for det in detections:
            species = self._get_or_create_species(det['species_name'])
            if not species:
                self.logger.warning(f'Could not create species "{det["species_name"]}"')
                continue

            # Update species info from Wikipedia
            update_species_info_from_wiki(species)

            if det['source'] == 'video':
                visit, video_species = self.process_video_detection(
                    species=species,
                    video=video,
                    detection_start=det['start_time'],
                    detection_end=det['end_time'],
                    confidence=det['confidence'],
                    track_id=det.get('track_id'),
                    frames=det.get('frames'),
                    detection_provider=det.get('detection_provider')
                )
                visit_key = (visit.species_id, visit.start_time)
                if visit_key not in visits_to_update:
                    visits_to_update[visit_key] = {
                        'visit': visit,
                        'detections': []
                    }
                visits_to_update[visit_key]['detections'].append(video_species)
                video_species_records.append(video_species)
            else:  # audio
                video_species = self.process_audio_detection(
                    species=species,
                    video=video,
                    detection_start=det['start_time'],
                    detection_end=det['end_time'],
                    confidence=det['confidence'],
                    detection_provider=det.get('detection_provider')
                )
                if video_species:
                    video_species_records.append(video_species)

        # Second pass: Update simultaneous counts for affected visits
        for visit_data in visits_to_update.values():
            self._update_simultaneous_count(
                visit_data['visit'], visit_data['detections'])

        return video_species_records

    def _get_or_create_visit(self, species: Species, detection_time: datetime) -> Tuple[SpeciesVisit, bool]:
        """
        Gets existing or creates new visit for a species.
        Always creates visits at the detection species level.
        Returns tuple of (visit, was_created).
        """
        # Look for existing visit that ended recently or is still ongoing
        cutoff_time = detection_time - timedelta(seconds=self.visit_timeout)
        future_tolerance = detection_time + timedelta(seconds=self.visit_timeout)
        recent_visit = (SpeciesVisit.query
                        .filter(
                            SpeciesVisit.species_id == species.id,
                            SpeciesVisit.end_time >= cutoff_time,
                            SpeciesVisit.start_time <= future_tolerance,
                        )
                        .order_by(SpeciesVisit.end_time.desc())
                        .first())

        if recent_visit:
            recent_visit.start_time = recent_visit.start_time.replace(
                tzinfo=timezone.utc)
            recent_visit.end_time = recent_visit.end_time.replace(
                tzinfo=timezone.utc)
            recent_visit.created_at = recent_visit.created_at.replace(
                tzinfo=timezone.utc)
            if detection_time < recent_visit.start_time:
                recent_visit.start_time = detection_time
            return recent_visit, False

        visit = SpeciesVisit(
            species_id=species.id,
            start_time=detection_time,
            end_time=detection_time,
            max_simultaneous=1
        )
        self.db.session.add(visit)
        return visit, True

    def _get_or_create_unknown_species(self) -> Optional[Species]:
        """Перенос мусора / вне allowlist — одна строка «Unknown»."""
        existing = Species.query.filter_by(name='Unknown').first()
        if existing:
            return existing
        birds = Species.query.filter_by(name='Birds').first()
        parent_id = birds.id if birds else None
        row = Species(name='Unknown', parent_id=parent_id, active=False)
        self.db.session.add(row)
        self.db.session.flush()
        self.logger.info('Created species "Unknown" for blocked/off-allowlist ingest')
        return row

    def _ingest_blocked(
        self,
        display_name: str,
        raw_normalized: str,
        taxon_common_name: str | None,
    ) -> bool:
        """Строгий allowlist: если задан и включён — имена вне списка → Unknown."""
        canonical_candidates = {
            str(display_name or '').strip().lower(),
            str(raw_normalized or '').strip().lower(),
            str(taxon_common_name or '').strip().lower(),
        }
        if GENERIC_BIRD_SPECIES.strip().lower() in canonical_candidates:
            return False
        if not bool(app_config.get('species.catalog_strict_ingest')):
            return False
        allow = load_catalog_allowlist_norm_keys(app_config.get)
        if allow is None:
            self.logger.warning(
                'Strict catalog ingest is enabled but allowlist is unavailable; '
                'blocking species "%s" until allowlist is restored.',
                display_name or raw_normalized or taxon_common_name or 'unknown',
            )
            return True
        mapping = load_species_canonical_mapping()
        ok_display = species_matches_allowlist(display_name or '', allow, mapping)
        ok_raw = species_matches_allowlist(raw_normalized or '', allow, mapping)
        return not (ok_display or ok_raw)

    def _get_or_create_species(self, name: str) -> Optional[Species]:
        """Вид по имени или создание (Frigate/YOLO/BirdNET). bird → Bird."""
        if not name or not isinstance(name, str):
            return None
        normalized = name.strip()
        if not normalized:
            return None
        if normalized.lower() in {'bird', 'unknown'}:
            normalized = GENERIC_BIRD_SPECIES
        resolution = resolve_species_name(normalized, source="ingest")
        taxon = resolution.taxon if resolution.found else None
        taxon_common = taxon.common_name if taxon else None
        canonical_name = taxon_common if taxon else normalized

        species = Species.query.filter_by(name=canonical_name).first()
        if species:
            tx = species.taxon
            cmn = tx.common_name if tx else None
            if self._ingest_blocked(species.name or '', normalized, cmn):
                return self._get_or_create_unknown_species()
            if resolution.found and taxon and species.taxon_id != taxon.id:
                species.taxon_id = taxon.id
            return species

        if self._ingest_blocked(canonical_name, normalized, taxon_common):
            return self._get_or_create_unknown_species()

        birds = Species.query.filter_by(name='Birds').first()
        parent_id = birds.id if birds else None
        parent_name = get_parent_name_for_species(canonical_name)
        if parent_name:
            parent_species = Species.query.filter_by(name=parent_name).first()
            if parent_species:
                parent_id = parent_species.id
        species = Species(
            name=canonical_name,
            parent_id=parent_id,
            active=False,
            taxon_id=taxon.id if taxon else None,
        )
        self.db.session.add(species)
        self.db.session.flush()
        self.logger.info(
            'Created species "%s" (parent_id=%s, resolver_method=%s)',
            canonical_name,
            parent_id,
            resolution.method,
        )
        return species

    def _find_active_visit_for_audio(self, audio_species: Species, detection_time: datetime) -> Optional[SpeciesVisit]:
        """Активный визит для аудио: вид или его дочерние."""
        cutoff_time = detection_time - timedelta(seconds=self.visit_timeout)
        future_tolerance = detection_time + timedelta(seconds=self.visit_timeout)

        child_species = Species.query.filter_by(
            parent_id=audio_species.id).all()
        species_ids = [audio_species.id] + [s.id for s in child_species]

        return (SpeciesVisit.query
                .filter(
                    SpeciesVisit.species_id.in_(species_ids),
                    SpeciesVisit.end_time >= cutoff_time,
                    SpeciesVisit.start_time <= future_tolerance,
                )
                .order_by(SpeciesVisit.end_time.desc())
                .first())

    def _update_simultaneous_count(self, visit: SpeciesVisit, current_detections: List[VideoSpecies]) -> None:
        """max_simultaneous по перекрывающимся детекциям в текущем видео."""
        video_detections = [
            vs for vs in current_detections if vs.source == 'video']
        if not video_detections:
            return
        sorted_detections = sorted(
            video_detections, key=lambda x: x.start_time)
        max_concurrent = 1
        for i, curr in enumerate(sorted_detections):
            concurrent = 1
            for other in sorted_detections[i+1:]:
                if curr.end_time >= other.start_time:
                    concurrent += 1
                else:
                    break
            max_concurrent = max(max_concurrent, concurrent)
        visit.max_simultaneous = max(visit.max_simultaneous, max_concurrent)
