"""Unit tests for processor ingest payload canonicalization."""

from routes import processor_routes


def test_species_payload_hash_ignores_non_persisted_flags():
    base = [
        {
            "species_name": "Great Tit",
            "source": "video",
            "detection_provider": "yolo",
            "track_id": 12,
            "start_time": 0.0,
            "end_time": 2.0,
            "confidence": 0.91,
            "visit_eligible": True,
            "notification_eligible": True,
            "decision_kind": "accepted_species",
            "classifier_confidence": 0.91,
            "frames": [],
        }
    ]
    changed = [
        {
            **base[0],
            "visit_eligible": False,
            "notification_eligible": False,
            "decision_kind": "review_only_generic",
            "classifier_confidence": 0.01,
        }
    ]
    assert processor_routes._build_species_payload_hash(species_list=base) == processor_routes._build_species_payload_hash(
        species_list=changed
    )


def test_species_payload_hash_stable_for_numeric_and_track_normalization():
    a = [
        {
            "species_name": "Blue Tit",
            "source": "video",
            "detection_provider": "yolo",
            "track_id": "7",
            "start_time": "1.2345674",
            "end_time": 3.4567894,
            "confidence": 0.333333333,
            "frames": [],
        }
    ]
    b = [
        {
            "species_name": "Blue Tit",
            "source": "video",
            "detection_provider": "yolo",
            "track_id": 7,
            "start_time": 1.23456739,
            "end_time": "3.45678939",
            "confidence": "0.3333333334",
            "frames": [],
        }
    ]
    assert processor_routes._build_species_payload_hash(species_list=a) == processor_routes._build_species_payload_hash(
        species_list=b
    )
