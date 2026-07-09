"""SOTA-13: ReID track clustering unit tests."""

from __future__ import annotations

import math

from services.reid_track_cluster_service import (
    TrackEmbeddingRow,
    cluster_track_embeddings,
    cosine_similarity,
)


def _unit_vec(axis: int, dim: int = 8) -> list[float]:
    v = [0.0] * dim
    v[axis % dim] = 1.0
    return v


def test_cosine_identical_is_one():
    v = _unit_vec(0)
    assert math.isclose(cosine_similarity(v, v), 1.0, rel_tol=1e-5)


def test_cosine_orthogonal_is_zero():
    assert math.isclose(cosine_similarity(_unit_vec(0), _unit_vec(1)), 0.0, abs_tol=1e-5)


def test_cluster_merges_similar_embeddings():
    rows = [
        TrackEmbeddingRow(1, 10, 5, "Bird", 1, 2.0, _unit_vec(0)),
        TrackEmbeddingRow(2, 10, 5, "Bird", 2, 2.0, [0.99, 0.01] + [0.0] * 6),
        TrackEmbeddingRow(3, 11, 5, "Bird", 3, 2.0, _unit_vec(2)),
    ]
    clusters = cluster_track_embeddings(rows)
    assert len(clusters) == 2
    sizes = sorted(len(c.member_video_species_ids) for c in clusters)
    assert sizes == [1, 2]


def test_cluster_separates_species():
    rows = [
        TrackEmbeddingRow(1, 10, 1, "A", 1, 1.0, _unit_vec(0)),
        TrackEmbeddingRow(2, 10, 2, "B", 2, 1.0, _unit_vec(1)),
    ]
    clusters = cluster_track_embeddings(rows)
    assert len(clusters) == 2
