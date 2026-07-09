"""Visit eligibility — placeholder taxa (Bird/Rodent) are full catalog species."""

from __future__ import annotations

GENERIC_BIRD_SPECIES = "Bird"

GENERIC_BIRD_NAME_KEYS: frozenset[str] = frozenset(
    {
        "bird",
        "unknown",
        "unknown bird",
        "generic bird",
    }
)

# Raw labels that must not become SpeciesVisit rows (map to Bird/Rodent first).
VISIT_STATS_EXCLUDE_NAME_KEYS: frozenset[str] = frozenset({"unknown"})


def is_generic_bird_species_name(
    name: str | None,
    *,
    birder_unknown_label: str | None = None,
) -> bool:
    """True when species label is generic bird (detector / classifier placeholder)."""
    n = str(name or "").strip().lower()
    if not n:
        return False
    if n in GENERIC_BIRD_NAME_KEYS:
        return True
    if birder_unknown_label:
        unk = str(birder_unknown_label).strip().lower()
        if unk and n == unk:
            return True
    return False


GENERIC_RODENT_SPECIES = "Rodent"

GENERIC_RODENT_NAME_KEYS: frozenset[str] = frozenset(
    {
        "rodent",
        "squirrel",
        "mouse",
        "rat",
        "vole",
    }
)


def is_generic_rodent_species_name(name: str | None) -> bool:
    n = str(name or "").strip().lower()
    if not n:
        return False
    if n in GENERIC_RODENT_NAME_KEYS:
        return True
    return n == GENERIC_RODENT_SPECIES.strip().lower()


def is_unidentified_activity_species_name(
    name: str | None,
    *,
    birder_unknown_label: str | None = None,
) -> bool:
    return is_generic_bird_species_name(name, birder_unknown_label=birder_unknown_label) or is_generic_rodent_species_name(
        name
    )


def is_catalog_placeholder_species_name(name: str | None) -> bool:
    """Canonical Bird/Rodent rows — visits, dashboard, and catalog."""
    n = str(name or "").strip()
    if not n:
        return False
    return n == GENERIC_BIRD_SPECIES or n == GENERIC_RODENT_SPECIES


def visit_eligible_for_named_species(
    *,
    species_name: str | None,
    visit_eligible: bool,
    birder_unknown_label: str | None = None,
) -> bool:
    """SpeciesVisit for named taxa and catalog placeholders Bird/Rodent."""
    if not visit_eligible:
        return False
    n = str(species_name or "").strip().lower()
    if n in VISIT_STATS_EXCLUDE_NAME_KEYS:
        return False
    if is_catalog_placeholder_species_name(species_name):
        return True
    if is_generic_bird_species_name(species_name, birder_unknown_label=birder_unknown_label):
        return True
    if is_generic_rodent_species_name(species_name):
        return True
    return True
