"""Канонический реестр видов: taxon, алиасы, резолв имён, бэкфилл и обогащение метаданными."""
import re
import time
import requests
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, or_

from models import db, Species, SpeciesAlias, SpeciesTaxon, SpeciesUnresolvedName
from services.species_catalog_allowlist_service import (
    load_catalog_allowlist_names,
    species_name_match_norm_keys,
)
from util import load_species_canonical_mapping
from util import (
    update_species_info_from_wiki,
    _extract_wiki_search_title,
    infer_metadata_source_fields,
    get_inaturalist_image_and_description,
    _host_is_wikipedia_family,
    _url_hostname_lower,
)


def _norm_key(name: str) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def _slug(name: str) -> str:
    s = _norm_key(name)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _has_metadata_text(value: str | None) -> bool:
    return bool((value or '').strip())


def _next_unique_taxon_key(base_name: str, fallback_suffix: str = '') -> str:
    base = _slug(base_name) or 'taxon'
    if fallback_suffix:
        fallback_suffix = _slug(fallback_suffix)
    candidate = base
    idx = 2
    while SpeciesTaxon.query.filter_by(taxon_key=candidate).first():
        if fallback_suffix:
            candidate = f'{base}-{fallback_suffix}-{idx}'
        else:
            candidate = f'{base}-{idx}'
        idx += 1
    return candidate


def _parse_scientific_and_common(name: str) -> tuple[str | None, str]:
    m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", (name or "").strip())
    if not m:
        return None, (name or "").strip()
    scientific = m.group(1).strip() or None
    common = m.group(2).strip() or (name or "").strip()
    return scientific, common


@dataclass
class SpeciesResolution:
    """Результат сопоставления строки с ``SpeciesTaxon`` (метод и уверенность)."""
    found: bool
    taxon: SpeciesTaxon | None
    method: str
    confidence: float
    normalized_key: str


def _resolve_without_logging(name: str) -> SpeciesResolution:
    key = _norm_key(name)
    if not key:
        return SpeciesResolution(False, None, 'empty', 0.0, key)

    alias = SpeciesAlias.query.filter_by(alias_key=key).first()
    if alias and alias.taxon:
        return SpeciesResolution(True, alias.taxon, 'alias_key', 1.0, key)

    stripped = (name or '').strip()
    taxon = SpeciesTaxon.query.filter_by(common_name=stripped).first()
    if taxon:
        return SpeciesResolution(True, taxon, 'common_name_exact', 1.0, key)

    for candidate in SpeciesTaxon.query.all():
        if _norm_key(candidate.common_name) == key:
            return SpeciesResolution(True, candidate, 'common_name_normalized', 0.95, key)
    return SpeciesResolution(False, None, 'unresolved', 0.0, key)


def ensure_species_registry_seeded() -> dict:
    """
    Seed canonical taxa and aliases from species_canonical_mapping.txt.
    Safe for repeated runs.
    """
    taxa_created = 0
    aliases_created = 0
    linked_existing = 0

    mapping = load_species_canonical_mapping() or {}

    for variant, canonical in mapping.items():
        canonical = (canonical or "").strip()
        if not canonical:
            continue
        taxon = SpeciesTaxon.query.filter_by(common_name=canonical).first()
        if not taxon:
            scientific, _ = _parse_scientific_and_common(variant)
            if not scientific:
                scientific, _ = _parse_scientific_and_common(canonical)
            taxon = SpeciesTaxon(
                taxon_key=_next_unique_taxon_key(canonical),
                scientific_name=scientific,
                common_name=canonical,
                wiki_title=canonical,
                status="active",
            )
            db.session.add(taxon)
            db.session.flush()
            taxa_created += 1

        for alias in {variant.strip(), canonical}:
            if not alias:
                continue
            alias_row = SpeciesAlias.query.filter_by(alias=alias).first()
            if alias_row:
                if alias_row.taxon_id != taxon.id:
                    alias_row.taxon_id = taxon.id
                    alias_row.alias_key = _norm_key(alias)
                continue
            db.session.add(
                SpeciesAlias(
                    alias=alias,
                    alias_key=_norm_key(alias),
                    taxon_id=taxon.id,
                )
            )
            aliases_created += 1

    # Baseline coverage for the whole DB:
    # every existing Species name should have a canonical taxon,
    # even if not yet present in mapping file.
    for sp in Species.query.order_by(Species.id.asc()).all():
        existing_taxon = SpeciesTaxon.query.filter_by(common_name=sp.name).first()
        if not existing_taxon:
            scientific, common = _parse_scientific_and_common(sp.name)
            canonical = common or sp.name
            existing_taxon = SpeciesTaxon.query.filter_by(common_name=canonical).first()
            if not existing_taxon:
                existing_taxon = SpeciesTaxon(
                    taxon_key=_next_unique_taxon_key(canonical or sp.name or 'taxon', fallback_suffix=str(sp.id)),
                    scientific_name=scientific,
                    common_name=canonical,
                    wiki_title=canonical,
                    status='active',
                )
                db.session.add(existing_taxon)
                db.session.flush()
                taxa_created += 1

        alias_row = SpeciesAlias.query.filter_by(alias=sp.name).first()
        if not alias_row:
            db.session.add(
                SpeciesAlias(
                    alias=sp.name,
                    alias_key=_norm_key(sp.name),
                    taxon_id=existing_taxon.id,
                )
            )
            aliases_created += 1
        elif alias_row.taxon_id != existing_taxon.id:
            alias_row.taxon_id = existing_taxon.id
            alias_row.alias_key = _norm_key(sp.name)

        if sp.taxon_id != existing_taxon.id:
            sp.taxon_id = existing_taxon.id
            linked_existing += 1

    db.session.commit()
    return {
        "taxa_created": taxa_created,
        "aliases_created": aliases_created,
        "linked_existing_species": linked_existing,
    }


def resolve_species_name(name: str, source: str | None = None) -> SpeciesResolution:
    """Найти taxon по алиасу или common name; при неудаче залогировать в SpeciesUnresolvedName."""
    resolution = _resolve_without_logging(name)
    if not resolution.found:
        _log_unresolved_name(name, resolution.normalized_key, source=source, reason='no_match')
    return resolution


def _log_unresolved_name(raw_name: str, normalized_key: str, source: str | None, reason: str) -> None:
    now = datetime.now(timezone.utc)
    row = SpeciesUnresolvedName.query.filter_by(normalized_key=normalized_key).first()
    if row:
        row.last_seen_at = now
        row.seen_count = int(row.seen_count or 0) + 1
        if source and not row.source:
            row.source = source
        if reason and not row.reason:
            row.reason = reason
    else:
        db.session.add(
            SpeciesUnresolvedName(
                raw_name=(raw_name or "").strip(),
                normalized_key=normalized_key,
                source=source,
                reason=reason,
                seen_count=1,
            )
        )
    db.session.flush()


def backfill_species_taxa(dry_run: bool = True, limit: int | None = None) -> dict:
    """Проставить ``Species.taxon_id`` по реестру; при ``dry_run`` откат без commit."""
    ensure_species_registry_seeded()
    q = Species.query.order_by(Species.id.asc())
    if limit:
        q = q.limit(limit)

    processed = 0
    matched = 0
    unresolved = 0

    candidates = q.all()
    # Process base names before variants in parentheses, so cache reuse is maximal.
    candidates.sort(key=lambda s: (1 if '(' in (s.name or '') else 0, (s.name or '')))
    for sp in candidates:
        processed += 1
        if sp.taxon_id:
            matched += 1
            continue
        r = resolve_species_name(sp.name, source="species_backfill")
        if r.found and r.taxon:
            matched += 1
            if not dry_run:
                sp.taxon_id = r.taxon.id
        else:
            unresolved += 1

    # Cleanup unresolved rows that are now resolvable with current registry.
    cleaned_unresolved = 0
    for row in SpeciesUnresolvedName.query.all():
        rr = _resolve_without_logging(row.raw_name)
        if rr.found:
            db.session.delete(row)
            cleaned_unresolved += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {
        "processed": processed,
        "matched": matched,
        "unresolved": unresolved,
        "cleaned_unresolved": cleaned_unresolved,
        "dry_run": dry_run,
    }


def unresolved_species_report(limit: int = 100) -> list[dict]:
    """Топ неразрешённых имён по счётчику для админки и triage."""
    rows = (SpeciesUnresolvedName.query
            .order_by(SpeciesUnresolvedName.seen_count.desc(), SpeciesUnresolvedName.last_seen_at.desc())
            .limit(max(1, min(limit, 1000)))
            .all())
    return [{
        "id": r.id,
        "raw_name": r.raw_name,
        "normalized_key": r.normalized_key,
        "source": r.source,
        "reason": r.reason,
        "seen_count": int(r.seen_count or 0),
        "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
        "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
    } for r in rows]


def enrich_species_metadata(limit: int = 100, dry_run: bool = True) -> dict:
    """
    Populate missing species image/description from external sources.
    """
    q = Species.query.filter(
        or_(
            Species.image_url.is_(None),
            func.trim(func.coalesce(Species.image_url, '')) == '',
            Species.description.is_(None),
            func.trim(func.coalesce(Species.description, '')) == '',
        )
    ).order_by(Species.id.asc()).limit(max(1, min(limit, 5000)))

    processed = 0
    updated = 0
    failed = 0
    for sp in q.all():
        processed += 1
        try:
            before_img = _has_metadata_text(sp.image_url)
            before_desc = _has_metadata_text(sp.description)
            changed = update_species_info_from_wiki(sp)
            if changed and (not before_img or not before_desc):
                updated += 1
        except Exception:
            failed += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
        if updated > 0:
            _invalidate_species_catalog_http_caches()

    return {
        "processed": processed,
        "updated": updated,
        "failed": failed,
        "dry_run": dry_run,
    }


def repair_recently_reset_species_metadata(
    limit: int = 500,
    dry_run: bool = True,
) -> dict:
    """
    Restore images for rows that lost them during a bad cleanup pass.
    Targets only species that still have a description but no image.
    """
    q = Species.query.filter(
        Species.image_url.is_(None),
        Species.description.isnot(None),
    ).order_by(Species.id.asc()).limit(max(1, min(limit, 5000)))

    processed = 0
    repaired = 0
    failed = 0
    for sp in q.all():
        processed += 1
        try:
            before_img = bool(sp.image_url)
            update_species_info_from_wiki(sp)
            if sp.image_url and not before_img:
                repaired += 1
        except Exception:
            failed += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
        if repaired > 0:
            _invalidate_species_catalog_http_caches()

    return {
        "processed": processed,
        "repaired": repaired,
        "failed": failed,
        "dry_run": dry_run,
    }


def enrich_species_metadata_with_status(
    limit: int = 100,
    dry_run: bool = True,
    retry_failed_only: bool = False,
) -> dict:
    """
    Metadata enrichment with per-species status tracking.
    """
    q = Species.query
    if retry_failed_only:
        q = q.filter(Species.metadata_status == 'error')
    else:
        q = q.filter(
            or_(
                Species.image_url.is_(None),
                func.trim(func.coalesce(Species.image_url, '')) == '',
                Species.description.is_(None),
                func.trim(func.coalesce(Species.description, '')) == '',
            )
        )

    q = q.order_by(Species.id.asc()).limit(max(1, min(limit, 5000)))

    processed = 0
    updated = 0
    failed = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    base_meta_cache: dict[str, tuple[str | None, str | None]] = {}

    for sp in q.all():
        # Keep source provenance consistent even for already enriched rows.
        src, src_url = infer_metadata_source_fields(
            sp.name,
            sp.image_url,
            sp.metadata_source_url,
        )
        if src and not sp.metadata_source:
            sp.metadata_source = src
        if src_url and not sp.metadata_source_url:
            sp.metadata_source_url = src_url
        if (
            _has_metadata_text(sp.image_url)
            and _has_metadata_text(sp.description)
            and not retry_failed_only
        ):
            skipped += 1
            if not dry_run:
                db.session.commit()
            continue
        processed += 1
        sp.metadata_attempts = int(sp.metadata_attempts or 0) + 1
        try:
            base_title = (_extract_wiki_search_title(sp.name) or '').strip()
            cached = base_meta_cache.get(base_title.lower()) if base_title else None
            if cached and (
                not _has_metadata_text(sp.image_url)
                or not _has_metadata_text(sp.description)
            ):
                img_c, desc_c = cached
                if _has_metadata_text(img_c) and not _has_metadata_text(sp.image_url):
                    sp.image_url = img_c
                if _has_metadata_text(desc_c) and not _has_metadata_text(sp.description):
                    sp.description = desc_c

            changed = update_species_info_from_wiki(sp)
            sp.metadata_updated_at = now
            if _has_metadata_text(sp.image_url) and _has_metadata_text(sp.description):
                sp.metadata_status = 'ok'
                sp.metadata_error = None
                if base_title:
                    base_meta_cache[base_title.lower()] = (sp.image_url, sp.description)
                if changed:
                    updated += 1
            else:
                sp.metadata_status = 'not_found'
                sp.metadata_error = 'metadata_not_found'
        except Exception as e:
            failed += 1
            sp.metadata_status = 'error'
            sp.metadata_error = str(e)[:255]
            sp.metadata_updated_at = now
        finally:
            if not dry_run:
                # Commit per species to avoid long SQLite write lock windows.
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    failed += 1
            # Throttle external API calls to reduce 429 bursts.
            time.sleep(0.6)

    if dry_run:
        db.session.rollback()
    elif updated > 0:
        _invalidate_species_catalog_http_caches()

    return {
        'processed': processed,
        'updated': updated,
        'failed': failed,
        'skipped': skipped,
        'dry_run': dry_run,
        'retry_failed_only': retry_failed_only,
    }


def species_registry_health() -> dict:
    """Quality snapshot for registry rollout and CI gates."""
    species_total = Species.query.count()
    species_with_taxon = Species.query.filter(Species.taxon_id.isnot(None)).count()
    unresolved_total = SpeciesUnresolvedName.query.count()
    aliases_total = SpeciesAlias.query.count()
    taxa_total = SpeciesTaxon.query.count()
    coverage = round((species_with_taxon / species_total) * 100, 2) if species_total else 100.0
    metadata_ok = Species.query.filter(Species.metadata_status == 'ok').count()
    metadata_error = Species.query.filter(Species.metadata_status == 'error').count()
    metadata_not_found = Species.query.filter(Species.metadata_status == 'not_found').count()
    metadata_pending = Species.query.filter(Species.metadata_status == 'pending').count()
    return {
        "species_total": species_total,
        "species_with_taxon": species_with_taxon,
        "coverage_percent": coverage,
        "unresolved_total": unresolved_total,
        "aliases_total": aliases_total,
        "taxa_total": taxa_total,
        "metadata_ok": metadata_ok,
        "metadata_error": metadata_error,
        "metadata_not_found": metadata_not_found,
        "metadata_pending": metadata_pending,
    }


def ensure_allowlist_species_materialized(
    app_config_get,
    *,
    fill_metadata: bool = True,
    dry_run: bool = True,
    limit: int = 5000,
) -> dict:
    """Ensure every allowlist class has a Species row and metadata."""
    allowlist_names = list(load_catalog_allowlist_names(app_config_get) or ())
    if not allowlist_names:
        return {
            'allowlist_total': 0,
            'created': 0,
            'matched_existing': 0,
            'metadata_updated': 0,
            'missing_after': 0,
            'dry_run': dry_run,
        }

    existing_rows = Species.query.order_by(Species.id.asc()).all()
    by_norm: dict[str, Species] = {}
    for sp in existing_rows:
        for k in species_name_match_norm_keys(sp.name or ''):
            by_norm.setdefault(k, sp)

    created = 0
    matched_existing = 0
    metadata_updated = 0
    touched: list[Species] = []
    sci_common = re.compile(r'^(.+?)\s*\(([^)]+)\)\s*$')
    cap = max(1, min(int(limit or 5000), 20000))
    for raw in allowlist_names[:cap]:
        target = None
        for k in species_name_match_norm_keys(raw):
            target = by_norm.get(k)
            if target:
                break
        if target:
            matched_existing += 1
        else:
            m = sci_common.match((raw or '').strip())
            common_name = (m.group(2).strip() if m else (raw or '').strip()) or (raw or '').strip()
            target = Species(name=common_name)
            db.session.add(target)
            db.session.flush()
            created += 1
            for k in species_name_match_norm_keys(raw):
                by_norm.setdefault(k, target)
            for k in species_name_match_norm_keys(target.name):
                by_norm.setdefault(k, target)
        touched.append(target)

    if fill_metadata:
        for sp in touched:
            if sp.image_url and sp.description:
                continue
            try:
                if update_species_info_from_wiki(sp):
                    metadata_updated += 1
            except Exception:
                continue

    missing_after = sum(1 for sp in touched if not sp.image_url or not sp.description)

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {
        'allowlist_total': len(allowlist_names),
        'created': created,
        'matched_existing': matched_existing,
        'metadata_updated': metadata_updated,
        'missing_after': missing_after,
        'dry_run': dry_run,
    }


def _invalidate_species_catalog_http_caches() -> None:
    """После массового обновления Species — сброс Redis/in-memory JSON-кэшей API (иначе UI видит старые image_url)."""
    try:
        from services.http_response_cache import bust_response_caches
        from util import bust_feeder_species_filter_cache

        bust_response_caches()
        bust_feeder_species_filter_cache()
    except Exception:
        pass


def realign_species_images_from_allowlist_science(
    targets: list,
    app_config_get,
    *,
    limit: int = 500,
) -> int:
    """Перезаписать image_url с Wikipedia по биному из allowlist (без кэша), если URL изменился.

    Ограничение limit на прогон — чтобы не упереться в rate limit Wikipedia при больших каталогах.
    """
    from species_metadata import get_wikipedia_image_and_description
    from services.species_catalog_allowlist_service import (
        allowlist_scientific_name_for_display_name,
    )

    cap = max(1, int(limit))
    n = 0
    for sp in targets:
        if n >= cap:
            break
        sci = allowlist_scientific_name_for_display_name(sp.name or '', app_config_get)
        if not sci:
            continue
        img, desc = get_wikipedia_image_and_description(sci, use_cache=False)
        if not img:
            continue
        if (sp.image_url or '').strip() == img.strip():
            continue
        sp.image_url = img
        if desc and not (sp.description or '').strip():
            sp.description = desc
        inf_src, inf_url = infer_metadata_source_fields(
            getattr(sp, 'name', None), img, None
        )
        if inf_src:
            sp.metadata_source = inf_src
        if inf_url:
            sp.metadata_source_url = inf_url
        n += 1
    return n


def repair_catalog_cards(app_config_get, *, dry_run: bool = True, limit: int = 6000) -> dict:
    """Auto-heal full catalog cards: missing metadata and blocked Wikimedia images."""
    # Ensure full catalog materialization first, otherwise repair runs only on
    # already-existing rows and misses allowlist species absent in DB.
    materialize = ensure_allowlist_species_materialized(
        app_config_get,
        fill_metadata=True,
        dry_run=dry_run,
        limit=limit,
    )

    allowlist_names = list(load_catalog_allowlist_names(app_config_get) or ())
    if not allowlist_names:
        return {
            'checked': 0,
            'metadata_fixed': 0,
            'images_replaced_from_inat': 0,
            'images_realigned_allowlist_science': 0,
            'still_missing': 0,
            'dry_run': dry_run,
        }

    species_rows = Species.query.order_by(Species.id.asc()).all()
    by_norm: dict[str, Species] = {}
    for sp in species_rows:
        for k in species_name_match_norm_keys(sp.name or ''):
            by_norm.setdefault(k, sp)

    targets: list[Species] = []
    for aname in allowlist_names:
        match = None
        for k in species_name_match_norm_keys(aname):
            match = by_norm.get(k)
            if match:
                break
        if match:
            targets.append(match)
    # unique by ID, keep order
    uniq: dict[int, Species] = {}
    for sp in targets[: max(1, min(limit, 20000))]:
        uniq.setdefault(int(sp.id), sp)
    targets = list(uniq.values())

    metadata_fixed = 0
    images_replaced_from_inat = 0

    for sp in targets:
        before_img = bool((sp.image_url or '').strip())
        before_desc = bool((sp.description or '').strip())

        if not before_img or not before_desc:
            try:
                changed = update_species_info_from_wiki(sp)
                if changed and (not before_img or not before_desc):
                    metadata_fixed += 1
            except Exception:
                pass

        # Wikimedia links are often blocked by anti-abuse; replace only failing ones.
        current_img = (sp.image_url or '').strip()
        host = _url_hostname_lower(current_img)
        if current_img and _host_is_wikipedia_family(host):
            blocked = False
            try:
                resp = requests.get(
                    current_img,
                    timeout=8,
                    allow_redirects=True,
                    headers={
                        'User-Agent': 'BirdLense-Hub/1.0',
                        'Accept': 'image/*,*/*;q=0.8',
                    },
                    stream=True,
                )
                blocked = resp.status_code >= 400
                resp.close()
            except Exception:
                blocked = True

            if blocked:
                title = _extract_wiki_search_title(sp.name) or sp.name
                img2, desc2, src2 = get_inaturalist_image_and_description(title)
                if img2:
                    sp.image_url = img2
                    if desc2 and not (sp.description or '').strip():
                        sp.description = desc2
                    sp.metadata_source = 'inaturalist'
                    if src2:
                        sp.metadata_source_url = src2
                    images_replaced_from_inat += 1

    realigned_sci = 0
    if not dry_run:
        realigned_sci = realign_species_images_from_allowlist_science(
            targets,
            app_config_get,
            limit=min(500, max(1, int(limit or 6000))),
        )
        metadata_fixed += realigned_sci

    still_missing = sum(
        1
        for sp in targets
        if not (sp.image_url or '').strip() or not (sp.description or '').strip()
    )
    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
        _invalidate_species_catalog_http_caches()

    return {
        'checked': len(targets),
        'metadata_fixed': metadata_fixed,
        'images_replaced_from_inat': images_replaced_from_inat,
        'images_realigned_allowlist_science': realigned_sci,
        'still_missing': still_missing,
        'materialized_created': int(materialize.get('created') or 0),
        'materialized_missing_after': int(materialize.get('missing_after') or 0),
        'dry_run': dry_run,
    }


def catalog_cards_coverage_snapshot(app_config_get) -> dict:
    """Coverage snapshot for allowlist-backed catalog cards."""
    allowlist_names = list(load_catalog_allowlist_names(app_config_get) or ())
    if not allowlist_names:
        return {
            'allowlist_total': 0,
            'species_matched': 0,
            'with_image': 0,
            'with_description': 0,
            'complete_cards': 0,
            'completion_percent': 100.0,
        }

    species_rows = Species.query.order_by(Species.id.asc()).all()
    by_norm: dict[str, Species] = {}
    for sp in species_rows:
        for k in species_name_match_norm_keys(sp.name or ''):
            by_norm.setdefault(k, sp)

    matched: list[Species] = []
    for raw in allowlist_names:
        target = None
        for k in species_name_match_norm_keys(raw):
            target = by_norm.get(k)
            if target:
                break
        if target:
            matched.append(target)

    uniq: dict[int, Species] = {}
    for sp in matched:
        uniq.setdefault(int(sp.id), sp)
    matched = list(uniq.values())

    with_image = sum(1 for sp in matched if (sp.image_url or '').strip())
    with_description = sum(1 for sp in matched if (sp.description or '').strip())
    complete_cards = sum(
        1 for sp in matched if (sp.image_url or '').strip() and (sp.description or '').strip()
    )
    completion_percent = round((complete_cards / max(1, len(allowlist_names))) * 100.0, 2)
    return {
        'allowlist_total': len(allowlist_names),
        'species_matched': len(matched),
        'with_image': with_image,
        'with_description': with_description,
        'complete_cards': complete_cards,
        'completion_percent': completion_percent,
    }

