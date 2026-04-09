"""Wikipedia / iNaturalist metadata, taxonomy seed files, and species-image URL allowlist.

Moved from util.py (tech debt #222)."""

import logging
import os
import re
from urllib.parse import urlparse

import requests

from app_config.app_config import app_config
from models import Species, db

_wiki_meta_cache = {}
_wiki_title_overrides = {
    'cardinals, grosbeaks, and allies': 'Cardinalidae',
    'frigatebirds, boobies, cormorants, darters, and allies': 'Suliformes',
    'grouse, quail, and allies': 'Galliformes',
    'gulls, terns, and allies': 'Laridae',
    'mockingbirds, thrashers, and allies': 'Mimidae',
    'new world sparrows and allies': 'Passerellidae',
    'old world warblers': 'Sylviidae',
    'pelicans, herons, ibises, and allies': 'Pelecaniformes',
    'skuas and alcids': 'Alcidae',
    'swifts and hummingbirds': 'Apodiformes',
    'jacobin pigeon': 'Jacobin (pigeon)',
    'jacobin pigeon ': 'Jacobin (pigeon)',
    'grey headed fish eagle': 'Grey-headed fish eagle',
}

# Редкие случаи, когда Wikipedia-заголовок не даёт стабильное превью (не раздувать список).
_manual_image_overrides = {
    'jacobin pigeon': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/A_Jacobin_Pigeon.JPG/330px-A_Jacobin_Pigeon.JPG',
}


def _allowlist_scientific_for_species_name(name: str) -> str | None:
    try:
        from services.species_catalog_allowlist_service import (
            allowlist_scientific_name_for_display_name,
        )

        return allowlist_scientific_name_for_display_name(name, app_config.get)
    except Exception:
        return None


def _url_hostname_lower(url: str) -> str | None:
    """Разбор hostname без небезопасной подстроковой проверки URL (CodeQL py/incomplete-url-substring-sanitization)."""
    u = (url or '').strip()
    if not u:
        return None
    try:
        parsed = urlparse(u if '://' in u else f'//{u}', allow_fragments=True)
        h = (parsed.hostname or '').lower()
        return h or None
    except ValueError:
        return None


def _host_is_wikipedia_family(hostname: str | None) -> bool:
    """True if hostname is wikipedia.org / wikimedia.org (incl. subdomains)."""
    if not hostname:
        return False
    return hostname == 'wikipedia.org' or hostname.endswith(
        '.wikipedia.org'
    ) or hostname == 'wikimedia.org' or hostname.endswith('.wikimedia.org')


def _host_is_inaturalist(hostname: str | None) -> bool:
    """True if hostname is inaturalist.org (incl. subdomains)."""
    if not hostname:
        return False
    return hostname == 'inaturalist.org' or hostname.endswith('.inaturalist.org')


def _host_is_inaturalist_open_data_asset(hostname: str | None) -> bool:
    """Публичный S3-бакет iNaturalist open data (только hostname, без эвристик по query/path — SSRF)."""
    if not hostname:
        return False
    hn = hostname.lower().rstrip('.')
    if hn == 'inaturalist-open-data.s3.amazonaws.com':
        return True
    parts = hn.split('.')
    if (
        len(parts) >= 5
        and parts[0] == 'inaturalist-open-data'
        and parts[1] == 's3'
        and parts[-2] == 'amazonaws'
        and parts[-1] == 'com'
    ):
        return True
    return False


def _url_suggests_inaturalist_asset(url: str) -> bool:
    """iNaturalist сайт или open-data S3 — только по hostname."""
    h = _url_hostname_lower(url)
    if not h:
        return False
    return _host_is_inaturalist(h) or _host_is_inaturalist_open_data_asset(h)


def infer_metadata_source_fields(
    species_name: str | None,
    image_url: str | None,
    source_url: str | None,
) -> tuple[str | None, str | None]:
    """
    Infer canonical metadata source and source URL from known URL patterns.
    """
    img = (image_url or '').strip()
    src = (source_url or '').strip()
    title = ((species_name or '').strip() or 'bird').replace(' ', '_')

    img_host = _url_hostname_lower(img)
    src_host = _url_hostname_lower(src)

    if _host_is_wikipedia_family(img_host) or _host_is_wikipedia_family(src_host):
        return 'wikipedia', (src or f'https://en.wikipedia.org/wiki/{title}')
    if _host_is_inaturalist(src_host) or _host_is_inaturalist(img_host):
        return 'inaturalist', (src or img)
    if _url_suggests_inaturalist_asset(img) or _url_suggests_inaturalist_asset(src):
        return 'inaturalist', None
    return None, source_url


def _extract_common_for_hierarchy(species_name: str) -> str:
    """
    Извлечь common name для поиска в иерархии.
    "Cardinalis cardinalis (Northern Cardinal)" -> "Northern Cardinal"
    "Northern Cardinal" -> "Northern Cardinal"
    """
    if not species_name or not isinstance(species_name, str):
        return species_name or ""
    s = species_name.strip()
    if len(s) > 512:
        s = s[:512]
    if not s.endswith(')'):
        return s
    open_idx = s.rfind('(')
    if open_idx <= 0:
        return s
    inner = s[open_idx + 1 : -1].strip()
    return inner if inner else s


def _extract_wiki_search_title(species_name: str) -> str:
    """
    Choose best-effort Wikipedia title.

    - "Corvus cornix (Hooded Crow)" -> "Hooded Crow"
    - "Bald Eagle (Adult, subadult)" -> "Bald Eagle"
    """
    if not species_name or not isinstance(species_name, str):
        return species_name or ""
    s = species_name.strip()
    key = s.lower().strip()
    if key in _wiki_title_overrides:
        return _wiki_title_overrides[key]
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", s)
    if not m:
        return s
    left = (m.group(1) or "").strip()
    right = (m.group(2) or "").strip()
    # Scientific binomial (Genus species) on the left -> use right common name.
    if re.match(r"^[A-Z][a-z]+ [a-z][a-z-]+$", left):
        return right or left or s
    # Otherwise parentheses are usually morph/age/sex; use base species name.
    return left or right or s


def _load_hierarchy_parent_map():
    """Загрузить маппинг child -> parent из hierarchy_names.txt."""
    path = os.path.join(os.path.dirname(__file__), "seed", "hierarchy_names.txt")
    result = {}
    if not os.path.isfile(path):
        logging.warning('Hierarchy file not found: %s', path)
        return result
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "|" in line:
                child, parent = line.split("|", 1)
                result[child.strip()] = parent.strip()
    return result


def load_species_canonical_mapping():
    """
    Загрузить маппинг variant -> canonical из species_canonical_mapping.txt.
    Возвращает dict: variant_name -> canonical_name (Common).
    """
    path = os.path.join(os.path.dirname(__file__), "seed", "species_canonical_mapping.txt")
    result = {}
    if not os.path.isfile(path):
        return result
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            variant, canonical = line.split("|", 1)
            result[variant.strip()] = canonical.strip()
    return result


def normalize_species_to_canonical(name: str, mapping: dict | None = None) -> str:
    """
    Нормализовать имя вида в каноническое (Common name).
    mapping: variant -> canonical. Если None — загружается из seed.
    """
    mapping = mapping or load_species_canonical_mapping()
    return mapping.get(name, name)


_hierarchy_parent_map = None

_feeder_taxonomy_cache: tuple | None = None
_feeder_included_names_cache: dict[frozenset, tuple] = {}


def bust_feeder_species_filter_cache() -> None:
    """Сбросить кэши filter_feeder_species (тесты или после массовых правок Species)."""
    global _feeder_taxonomy_cache
    _feeder_taxonomy_cache = None
    _feeder_included_names_cache.clear()


def _species_catalog_signature() -> tuple[int, int, int, int, int]:
    """Отпечаток каталога Species: счётчики, суммы id/parent и сумма длин имён (переименования)."""
    from sqlalchemy import func

    row = db.session.query(
        func.count(Species.id),
        func.max(Species.id),
        func.sum(Species.id),
        func.sum(func.coalesce(Species.parent_id, 0)),
        func.sum(func.length(Species.name)),
    ).one()
    return tuple(int(x or 0) for x in row)


def _get_feeder_taxonomy_context():
    """Словари parent→children и name→Species; кэш по _species_catalog_signature."""
    global _feeder_taxonomy_cache
    sig = _species_catalog_signature()
    if _feeder_taxonomy_cache is not None and _feeder_taxonomy_cache[0] == sig:
        return _feeder_taxonomy_cache[1]
    children_by_parent: dict = {}
    name_to_species: dict = {}
    for species in Species.query.all():
        children_by_parent.setdefault(
            species.parent_id, set(),
        ).add(species.name)
        name_to_species[species.name] = species
    birds_category = name_to_species.get('Birds')
    data = (children_by_parent, name_to_species, birds_category)
    _feeder_taxonomy_cache = (sig, data)
    _feeder_included_names_cache.clear()
    return data


def get_parent_name_for_species(species_name: str) -> str | None:
    """Родительская категория для вида по иерархии (Frigate/BirdNET/YOLO)."""
    global _hierarchy_parent_map
    if _hierarchy_parent_map is None:
        _hierarchy_parent_map = _load_hierarchy_parent_map()
    key = _extract_common_for_hierarchy(species_name)
    return _hierarchy_parent_map.get(key) or _hierarchy_parent_map.get(species_name)


def build_hierarchy_tree():
    """Построить вложенный dict дерева таксоновии из seed/hierarchy_names.txt."""
    species_dict = _load_hierarchy_parent_map()

    children_map = {}
    for child, parent in species_dict.items():
        children_map.setdefault(parent, []).append(child)

    def build_tree_from_parent(parent):
        if parent not in children_map:
            return {}
        return {child: build_tree_from_parent(child) for child in children_map[parent]}

    root_nodes = set(species_dict.values()) - set(species_dict.keys())
    return {root: build_tree_from_parent(root) for root in root_nodes}


def get_wikipedia_image_and_description(title, *, use_cache: bool = True):
    """Fetch image and description from Wikipedia. Returns (None, None) on any error."""
    cache_key = (title or "").strip().lower()
    if use_cache and cache_key in _wiki_meta_cache:
        return _wiki_meta_cache[cache_key]
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "prop": "pageimages|pageprops|extracts",
            "format": "json",
            "piprop": "thumbnail",
            "titles": title,
            "pithumbsize": 300,
            "redirects": 1,
            "exintro": 1,
        }
        headers = {'User-Agent': 'BirdLense-Hub/1.0 (Bird feeder monitoring app)'}
        response = requests.get(url, params=params, timeout=10, headers=headers)
        response.raise_for_status()
        if 'json' not in (response.headers.get('Content-Type') or '').lower():
            logging.warning("Wikipedia API non-JSON response for '%s' (content-type=%s)",
                            title, response.headers.get('Content-Type'))
            result = (None, None)
            if use_cache:
                _wiki_meta_cache[cache_key] = result
            return result
        data = response.json()
        pages_dict = (data.get("query") or {}).get("pages") or {}
        pages = list(pages_dict.values())
        if not pages:
            result = (None, None)
            if use_cache:
                _wiki_meta_cache[cache_key] = result
            return result
        page = pages[0]
        image_url = page.get("thumbnail", {}).get("source")
        description = re.sub(r'<[^>]*>', '', page.get("extract", "")).strip() or None
        result = (image_url, description)
        if use_cache:
            _wiki_meta_cache[cache_key] = result
        return result
    except requests.RequestException as e:
        logging.warning("Wikipedia API HTTP failed for '%s': %s", title, e)
        result = (None, None)
        if use_cache:
            _wiki_meta_cache[cache_key] = result
        return result
    except ValueError as e:
        logging.warning("Wikipedia API decode failed for '%s': %s", title, e)
        result = (None, None)
        if use_cache:
            _wiki_meta_cache[cache_key] = result
        return result
    except Exception as e:
        logging.warning("Wikipedia API failed for '%s': %s", title, e)
        result = (None, None)
        if use_cache:
            _wiki_meta_cache[cache_key] = result
        return result


def get_inaturalist_image_and_description(title):
    """
    Fallback metadata source via iNaturalist taxa API.
    Returns (image_url, description, source_url) or (None, None, None).
    """
    try:
        query = (title or "").strip()
        if not query:
            return None, None, None
        url = "https://api.inaturalist.org/v1/taxa"
        params = {
            "q": query,
            "per_page": 3,
            "locale": "en",
            "is_active": "true",
            "iconic_taxa": "Aves",
        }
        headers = {'User-Agent': 'BirdLense-Hub/1.0 (Bird feeder monitoring app)'}
        response = requests.get(url, params=params, timeout=10, headers=headers)
        response.raise_for_status()
        data = response.json() or {}
        results = data.get("results") or []
        if not results:
            return None, None, None
        top = next(
            (row for row in results if (row.get("iconic_taxon_name") or "") == "Aves"),
            None,
        )
        if not top:
            return None, None, None
        image_url = ((top.get("default_photo") or {}).get("medium_url")
                     or (top.get("default_photo") or {}).get("square_url"))
        description = (top.get("wikipedia_summary")
                       or (top.get("taxon_schemes_count") and top.get("name"))
                       or None)
        if description and isinstance(description, str):
            description = description.strip() or None
        taxon_id = top.get("id")
        source_url = f"https://www.inaturalist.org/taxa/{taxon_id}" if taxon_id else None
        return image_url, description, source_url
    except Exception as e:
        logging.warning("iNaturalist API failed for '%s': %s", title, e)
        return None, None, None


def _wikipedia_query_titles_for_species(sp) -> list[str]:
    """Порядок заголовков для Wikipedia/iNaturalist: таксон → allowlist binomial → имя в БД."""
    titles: list[str] = []
    taxon = getattr(sp, 'taxon', None)
    wt = (getattr(taxon, 'wiki_title', None) or '').strip()
    if wt:
        t = _extract_wiki_search_title(wt) or wt
        if t:
            titles.append(t)

    sci_allow = _allowlist_scientific_for_species_name(sp.name or '')
    if sci_allow:
        titles.append(sci_allow)

    extracted = _extract_wiki_search_title(sp.name) or ''
    if extracted:
        titles.append(extracted)
    raw = (sp.name or '').strip()
    if raw and raw not in titles:
        titles.append(raw)

    scientific = re.sub(r'\(.*\)', '', sp.name or '').strip()
    if scientific and scientific not in titles:
        titles.append(scientific)

    probe = ((extracted or raw or '').strip().lower())
    if probe == 'hooded crow' and 'Corvus cornix' not in titles:
        titles.append('Corvus cornix')
    if probe == 'corvus cornix' and 'Hooded Crow' not in titles:
        titles.append('Hooded Crow')
    if 'jacobin pigeon' in ' '.join(titles).lower():
        for extra in ('Columba livia domestica', 'Rock Dove'):
            if extra not in titles:
                titles.append(extra)

    seen: set[str] = set()
    out: list[str] = []
    for t in titles:
        tl = (t or '').strip()
        if not tl:
            continue
        k = tl.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(tl)
    return out


def update_species_info_from_wiki(sp):
    """Подтянуть пустые image_url/description из Wikipedia / iNaturalist.

    Для видов из allowlist «Scientific (Common)» сначала ищем по **научному имени** из файла,
    чтобы не привязать карточку к чужой статье общего имени.
    """
    updated = False
    key = (sp.name or '').strip().lower()
    forced_url = _manual_image_overrides.get(key)
    if forced_url and (sp.image_url or '').strip() != forced_url:
        sp.image_url = forced_url
        inf_src, inf_url = infer_metadata_source_fields(
            getattr(sp, 'name', None), forced_url, None
        )
        if inf_src and not getattr(sp, 'metadata_source', None):
            sp.metadata_source = inf_src
        if inf_url and not getattr(sp, 'metadata_source_url', None):
            sp.metadata_source_url = inf_url
        updated = True

    if sp.image_url and sp.description:
        return updated

    metadata_source = None
    metadata_source_url = None
    image_url = None
    description = None

    wiki_titles = _wikipedia_query_titles_for_species(sp)
    for alt in wiki_titles:
        if image_url and description:
            break
        img2, desc2 = get_wikipedia_image_and_description(alt)
        if img2 and not image_url:
            image_url = img2
            metadata_source = metadata_source or 'wikipedia'
            metadata_source_url = (
                metadata_source_url
                or f"https://en.wikipedia.org/wiki/{alt.replace(' ', '_')}"
            )
        if desc2 and not description:
            description = desc2
            metadata_source = metadata_source or 'wikipedia'
            metadata_source_url = (
                metadata_source_url
                or f"https://en.wikipedia.org/wiki/{alt.replace(' ', '_')}"
            )

    if not image_url or not description:
        for alt in wiki_titles:
            if image_url and description:
                break
            img3, desc3, src3 = get_inaturalist_image_and_description(alt)
            if img3 and not image_url:
                image_url = img3
                metadata_source = metadata_source or 'inaturalist'
                metadata_source_url = metadata_source_url or src3
            if desc3 and not description:
                description = desc3
                metadata_source = metadata_source or 'inaturalist'
                metadata_source_url = metadata_source_url or src3

    if not description:
        title = _extract_wiki_search_title(sp.name) or sp.name
        if 'and allies' in (sp.name or '').lower():
            description = (
                f"{title} is a higher-level taxonomic bird group used in the BirdLense "
                'hierarchy for organizing related species.'
            )
        elif '(' in (sp.name or '') and ')' in (sp.name or ''):
            base = (sp.name or '').split('(', 1)[0].strip() or title
            description = (
                f"{sp.name} is a morphology/age/sex variant entry for {base} in the "
                'BirdLense species taxonomy.'
            )
        else:
            description = f'{title} is a bird taxon represented in the BirdLense registry.'

    if not image_url:
        image_url = _manual_image_overrides.get(key) or image_url
    if image_url and not sp.image_url:
        sp.image_url = image_url
    if description and not sp.description:
        sp.description = description
    inferred_source, inferred_url = infer_metadata_source_fields(
        getattr(sp, 'name', None),
        image_url or getattr(sp, 'image_url', None),
        metadata_source_url or getattr(sp, 'metadata_source_url', None),
    )
    if (metadata_source or inferred_source) and not getattr(sp, 'metadata_source', None):
        sp.metadata_source = metadata_source or inferred_source
    if (metadata_source_url or inferred_url) and not getattr(
        sp, 'metadata_source_url', None
    ):
        sp.metadata_source_url = metadata_source_url or inferred_url
    return updated or bool(image_url or description)


def filter_feeder_species(species_names):
    """Фильтр по семействам из processor.included_bird_families."""
    included_families = app_config.get('processor.included_bird_families', [])
    if not included_families:
        return species_names

    sig = _species_catalog_signature()
    children_by_parent, name_to_species, birds_category = _get_feeder_taxonomy_context()
    if not birds_category:
        return species_names

    fkey = frozenset(included_families)
    hit = _feeder_included_names_cache.get(fkey)
    if hit is not None and hit[0] == sig:
        included_species = hit[1]
    else:
        included_species = set()

        def add_descendants(parent_name):
            species = name_to_species.get(parent_name)
            if not species:
                return
            children = children_by_parent.get(species.id, set())
            included_species.update(children)
            for child in children:
                add_descendants(child)

        for family in included_families:
            if family in children_by_parent.get(birds_category.id, set()):
                add_descendants(family)
                included_species.add(family)
        _feeder_included_names_cache[fkey] = (sig, included_species)

    return [name for name in species_names if name in included_species]
