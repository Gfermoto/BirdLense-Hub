import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from models import db, Species, SpeciesAlias, SpeciesTaxon, SpeciesUnresolvedName
from util import load_species_canonical_mapping
from util import (
    update_species_info_from_wiki,
    _extract_wiki_search_title,
    infer_metadata_source_fields,
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
        (Species.image_url.is_(None)) | (Species.description.is_(None))
    ).order_by(Species.id.asc()).limit(max(1, min(limit, 5000)))

    processed = 0
    updated = 0
    failed = 0
    for sp in q.all():
        processed += 1
        try:
            before_img = bool(sp.image_url)
            before_desc = bool(sp.description)
            changed = update_species_info_from_wiki(sp)
            if changed and (not before_img or not before_desc):
                updated += 1
        except Exception:
            failed += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

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
            (Species.image_url.is_(None)) | (Species.description.is_(None))
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
        if sp.image_url and sp.description and not retry_failed_only:
            skipped += 1
            if not dry_run:
                db.session.commit()
            continue
        processed += 1
        sp.metadata_attempts = int(sp.metadata_attempts or 0) + 1
        try:
            base_title = (_extract_wiki_search_title(sp.name) or '').strip()
            cached = base_meta_cache.get(base_title.lower()) if base_title else None
            if cached and (not sp.image_url or not sp.description):
                img_c, desc_c = cached
                if img_c and not sp.image_url:
                    sp.image_url = img_c
                if desc_c and not sp.description:
                    sp.description = desc_c

            changed = update_species_info_from_wiki(sp)
            sp.metadata_updated_at = now
            if sp.image_url and sp.description:
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

