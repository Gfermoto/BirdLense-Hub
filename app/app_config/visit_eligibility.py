"""Visit stats eligibility — generic bird labels must not inflate dashboard counters."""

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


def is_generic_bird_species_name(
    name: str | None,
    *,
    birder_unknown_label: str | None = None,
) -> bool:
    """True when species label is generic bird (no named taxon for visit stats)."""
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


def visit_eligible_for_named_species(
    *,
    species_name: str | None,
    visit_eligible: bool,
    birder_unknown_label: str | None = None,
) -> bool:
    """Persist overlay may stay accepted; SpeciesVisit only for named taxa."""
    if not visit_eligible:
        return False
    return not is_generic_bird_species_name(
        species_name,
        birder_unknown_label=birder_unknown_label,
    )
