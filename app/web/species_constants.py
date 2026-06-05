"""Общие константы каталога видов (#222)."""

from app_config.visit_eligibility import (  # noqa: F401
    GENERIC_BIRD_NAME_KEYS,
    GENERIC_BIRD_SPECIES,
    GENERIC_RODENT_NAME_KEYS,
    GENERIC_RODENT_SPECIES,
    is_generic_bird_species_name,
    is_generic_rodent_species_name,
    is_unidentified_activity_species_name,
    visit_eligible_for_named_species,
)

# Родительская категория в дереве каталога — не класс YOLO
CATALOG_BIRDS_GROUP_SPECIES = "Birds"

# Вид каталога для грызунов (Trapper squirrel → без классификатора EfficientNet).
CATALOG_RODENT_SPECIES = "Rodent"

# Имена, которые не сравниваем с головой классификатора: родитель каталога + служебные.
# «Bird» (GENERIC_BIRD_SPECIES) сюда не входит — при отсутствии класса в .pt отчёт покажет рассогласование.
ALIGNMENT_IGNORE_SPECIES_NAMES: frozenset[str] = frozenset(
    {
        CATALOG_BIRDS_GROUP_SPECIES.strip().lower(),
        "unknown",
        CATALOG_RODENT_SPECIES.strip().lower(),
    }
)
