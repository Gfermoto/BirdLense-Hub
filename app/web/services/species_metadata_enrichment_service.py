"""Explicit metadata enrichment entrypoints for species cards/admin jobs."""

from __future__ import annotations

from species_metadata import update_species_info_from_wiki


def enrich_species_metadata(species):
    """Populate external metadata for a species card."""
    return update_species_info_from_wiki(species)
