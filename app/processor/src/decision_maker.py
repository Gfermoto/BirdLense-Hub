import logging
import time
from collections import Counter
import re

logger = logging.getLogger(__name__)

# Default min confidence; can be overridden via app_config processor.min_confidence_to_process
DEFAULT_MIN_CONFIDENCE = 0.03


def _normalized_species_keys(species_name):
    raw = str(species_name or '').strip()
    if not raw:
        return []

    def _normalize_key(value):
        return ' '.join(
            str(value or '')
            .replace('_', ' ')
            .replace('-', ' ')
            .strip()
            .lower()
            .split()
        )

    keys = []
    raw_key = _normalize_key(raw)
    if raw_key:
        keys.append(raw_key)

    match = re.match(r'^.+?\s*\(([^)]+)\)\s*$', raw)
    if match:
        common_key = _normalize_key(match.group(1))
        if common_key and common_key not in keys:
            keys.append(common_key)

    return keys


class DecisionMaker():
    def __init__(
        self,
        max_record_seconds=60,
        max_inactive_seconds=10,
        min_track_duration=2,
        min_confidence_to_process=None,
        species_confidence_overrides=None,
        post_record_seconds=0,
    ):
        self.max_record_seconds = max_record_seconds
        self.max_inactive_seconds = max_inactive_seconds
        try:
            pr = float(post_record_seconds or 0)
        except (TypeError, ValueError):
            pr = 0.0
        # post-roll: extend «no detection» tail after last activity (#157)
        self._effective_max_inactive = float(max_inactive_seconds or 0) + max(0.0, min(pr, 120.0))
        self.min_track_duration = min_track_duration
        self.min_confidence_to_process = (
            min_confidence_to_process
            if min_confidence_to_process is not None
            else DEFAULT_MIN_CONFIDENCE
        )
        self.species_confidence_overrides = species_confidence_overrides or {}
        self._species_confidence_override_keys = {
            key: value
            for name, value in self.species_confidence_overrides.items()
            for key in _normalized_species_keys(name)
        }
        self.reset()

    def _get_threshold_for_species(self, species_name):
        """Return min confidence threshold for species. Override or default."""
        direct = self.species_confidence_overrides.get(species_name)
        if direct is not None:
            return direct
        for key in _normalized_species_keys(species_name):
            mapped = self._species_confidence_override_keys.get(key)
            if mapped is not None:
                return mapped
        return self.min_confidence_to_process

    def reset(self):
        self.stop_recording_decided = False
        self.species_decided = False
        self.start_time = time.time()
        self.inactive_start_time = None

    def update_has_detections(self, has_detections):
        if not has_detections:
            if self.inactive_start_time is None:
                self.inactive_start_time = time.time()
        else:
            self.inactive_start_time = None

    def decide_stop_recording(self):
        if self.stop_recording_decided:
            # already decided once
            return False
        reached_max_record_seconds = (
            time.time() - self.start_time) >= self.max_record_seconds
        reached_max_inactive_seconds = self.inactive_start_time and (
            time.time() - self.inactive_start_time) >= self._effective_max_inactive
        decision = reached_max_inactive_seconds or reached_max_record_seconds
        self.stop_recording_decided = decision
        return decision

    def decide_species(self, tracks):
        if self.species_decided:
            return None
        results = self.get_results(tracks)
        if len(results) > 0:
            self.species_decided = True
            return results[0]['species_name']
        return None

    def get_first_species_result(self, tracks):
        """Return first result dict (species_name, best_frame, ...) or None."""
        if self.species_decided:
            return None
        results = self.get_results(tracks)
        if len(results) > 0:
            self.species_decided = True
            return results[0]
        return None

    def get_results(self, tracks):
        result = []
        for track_id, track in tracks.items():
            # Skip tracks with no predictions yet
            if not track['preds']:
                continue
            # Find most common prediction for each track
            # preds is a list of (species_name, confidence)
            species_only = [p[0] for p in track['preds']]
            pred_counts = Counter(species_only)
            species_name, count = pred_counts.most_common(1)[0]
            
            voting_confidence = count / len(track['preds'])
            
            # Calculate average classifier confidence for the winning species
            relevant_confs = [p[1] for p in track['preds'] if p[0] == species_name]
            avg_classifier_conf = sum(relevant_confs) / len(relevant_confs)
            
            # Combine confidences
            confidence = voting_confidence * avg_classifier_conf
            
            # Skip tracks with very low confidence - likely false positives
            threshold = self._get_threshold_for_species(species_name)
            if confidence < threshold:
                logger.debug(
                    f"Skipping track {track_id} ({species_name}): confidence={confidence:.2%} < {threshold}")
                continue

            dur = track['end_time'] - track['start_time']
            # Only consider species with at least min_track_duration
            if dur < self.min_track_duration:
                logger.debug(
                    f"Skipping track {track_id} ({species_name}): duration={dur:.2f}s < {self.min_track_duration}s")
                continue
            result.append({
                'track_id': track_id,
                'species_name': species_name,
                'start_time': track['start_time'],
                'end_time': track['end_time'],
                'confidence': confidence,
                'best_frame': track.get('best_frame'),
                'source': 'video',
                'frames': track.get('frames', [])  # Per-frame bounding box data
            })

        result.sort(
            key=lambda item: (
                -float(item.get('confidence') or 0.0),
                int(item.get('track_id') or 0),
            )
        )
        return result
