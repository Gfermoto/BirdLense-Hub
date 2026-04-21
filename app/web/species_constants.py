"""Общие константы каталога видов (#222)."""

# Вид «Bird» / «bird» — птица без определённого вида (отдельная запись Species, не родитель каталога)
GENERIC_BIRD_SPECIES = "Bird"

# Родительская категория в дереве каталога — не класс YOLO
CATALOG_BIRDS_GROUP_SPECIES = "Birds"

# Имена, которые не сравниваем с головой классификатора: родитель каталога + служебные.
# «Bird» (GENERIC_BIRD_SPECIES) сюда не входит — при отсутствии класса в .pt отчёт покажет рассогласование.
ALIGNMENT_IGNORE_SPECIES_NAMES: frozenset[str] = frozenset(
    {
        CATALOG_BIRDS_GROUP_SPECIES.strip().lower(),
        "unknown",
        "rodent",
    }
)
