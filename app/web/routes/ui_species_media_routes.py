"""Xeno-canto, summary, прокси species-image, tuning targets (#198)."""

import hashlib
import os
import time
from urllib.parse import quote, urljoin, urlparse, urlunparse

import ipaddress
import requests
from flask import Response, request
from sqlalchemy import func

from app_config.app_config import app_config
from auth import contributor_or_admin_access
from models import Species, SpeciesVisit, db
from services.cache import cache_delete, cache_delete_prefix, cache_get, cache_set
from services.dataset_export_service import _sanitize_dirname
from services.http_response_cache import bust_response_caches
from services.species_summary_service import build_species_summary
from services.xeno_canto_service import fetch_recordings, _search_term_from_species_name
from species_metadata import refresh_species_metadata_from_sources
from util import (
    data_dir,
    settings_check_access,
    _host_is_inaturalist,
    _host_is_inaturalist_open_data_asset,
    _host_is_wikipedia_family,
)


_SPECIES_PROXY_MAX_REDIRECTS = 5


def _species_proxy_allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return False
    try:
        host = (parsed.hostname or '').lower()
    except ValueError:
        return False
    return bool(
        _host_is_wikipedia_family(host)
        or _host_is_inaturalist(host)
        or _host_is_inaturalist_open_data_asset(host)
    )


def _species_proxy_sanitized_fetch_url(url: str) -> str | None:
    try:
        p = urlparse(url)
    except ValueError:
        return None
    if p.scheme not in ('http', 'https') or p.username or p.password:
        return None
    try:
        host = (p.hostname or '').lower()
        hn = p.hostname
        port = p.port
    except ValueError:
        return None
    if not host or not hn:
        return None
    if not (
        _host_is_wikipedia_family(host)
        or _host_is_inaturalist(host)
        or _host_is_inaturalist_open_data_asset(host)
    ):
        return None
    try:
        addr = ipaddress.ip_address(hn)
        host_netloc = f'[{hn}]' if addr.version == 6 else hn
    except ValueError:
        host_netloc = hn
    netloc = f'{host_netloc}:{port}' if port is not None else host_netloc
    return urlunparse((p.scheme, netloc, p.path or '', p.params, p.query, p.fragment))


def _species_proxy_client_error_message(last_err: str | None) -> str:
    if not last_err:
        return 'image proxy failed'
    if last_err.startswith('upstream status='):
        return last_err
    if last_err == 'upstream is not image content':
        return last_err
    return 'image proxy failed'


def _fetch_species_proxy_upstream(start_url: str):
    current = start_url
    for _ in range(_SPECIES_PROXY_MAX_REDIRECTS + 1):
        if not _species_proxy_allowed_url(current):
            return None, 'image proxy: redirect to disallowed host'
        fetch_url = _species_proxy_sanitized_fetch_url(current)
        if not fetch_url:
            return None, 'image proxy: invalid URL'
        try:
            r = requests.get(
                fetch_url,
                timeout=8,
                headers={
                    'User-Agent': 'BirdLense-Hub/1.0',
                    'Accept': 'image/*,*/*;q=0.8',
                },
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException:
            return None, 'image proxy: upstream request failed'
        if 300 <= r.status_code < 400:
            loc = (r.headers.get('Location') or '').strip()
            next_url = urljoin(r.url, loc) if loc else ''
            r.close()
            if not next_url:
                return None, 'image proxy: redirect without Location'
            current = next_url
            continue
        return r, None
    return None, 'image proxy: too many redirects'


def _get_tuning_target_ids() -> list[int]:
    raw = app_config.get('species.tuning_target_species_ids') or []
    out: list[int] = []
    if isinstance(raw, list):
        for x in raw:
            try:
                v = int(x)
            except (TypeError, ValueError):
                continue
            if v > 0:
                out.append(v)
    return sorted(set(out))


def _save_tuning_target_ids(ids: list[int]) -> None:
    species_cfg = app_config.config.get('species') or {}
    species_cfg['tuning_target_species_ids'] = sorted(set(int(x) for x in ids if int(x) > 0))
    app_config.config['species'] = species_cfg
    app_config.save()


def _dataset_class_folders() -> set[str]:
    web_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.abspath(os.path.join(web_root, '..', '..'))
    candidates = [
        os.path.join(data_dir(), 'dataset'),
        os.path.join(repo_root, 'datasets', 'merged_cls'),
    ]
    out: set[str] = set()
    for base in candidates:
        for split in ('train', 'val'):
            root = os.path.join(base, split)
            if not os.path.isdir(root):
                continue
            try:
                for entry in os.listdir(root):
                    if os.path.isdir(os.path.join(root, entry)):
                        out.add(entry)
            except OSError:
                continue
    return out


def register_ui_species_media_routes(app):
    @app.route('/api/ui/species/<int:species_id>/xeno-canto', methods=['GET'])
    def get_species_xeno_canto(species_id):
        xck = f"xeno_canto:{species_id}"
        hit, xc = cache_get(xck)
        if hit:
            return xc, 200
        species = db.session.get(Species, species_id)
        if not species:
            return {'error': 'Species not found'}, 404
        recordings = fetch_recordings(species.name, limit=5)
        term = _search_term_from_species_name(species.name) or species.name
        search_url = f"https://xeno-canto.org/explore?query={quote(term)}" if term else None
        body = {
            'recordings': recordings,
            'species_name': species.name,
            'xeno_canto_search_url': search_url,
        }
        cache_set(xck, body, 600)
        return body, 200

    @app.route('/api/ui/species/<int:species_id>/summary', methods=['GET'])
    def get_species_summary(species_id):
        sck = f"species_summary:{species_id}"
        hit, sc = cache_get(sck)
        if hit:
            return sc
        species = db.session.get(Species, species_id)
        if not species:
            return {'error': 'Species not found'}, 404

        children = Species.query.filter_by(parent_id=species_id).all()
        all_species_ids = [species.id] + [c.id for c in children]

        out = build_species_summary(db.session, species, children, all_species_ids)
        cache_set(sck, out, 30)
        return out

    @app.route('/api/ui/species/<int:species_id>/refresh-metadata', methods=['POST'])
    def refresh_species_card_metadata(species_id):
        """Перезапрос фото/описания/источника для одной карточки (Wikipedia → iNaturalist)."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        species = db.session.get(Species, species_id)
        if not species:
            return {'error': 'Species not found'}, 404
        try:
            refresh_species_metadata_from_sources(species)
            db.session.commit()
            cache_delete(f'species_summary:{species_id}')
            cache_delete_prefix('species_list:v3:')
            bust_response_caches()
            return {
                'ok': True,
                'species_id': species_id,
                'name': species.name,
                'image_url': species.image_url,
                'description': species.description,
                'metadata_source': species.metadata_source,
                'metadata_source_url': species.metadata_source_url,
            }, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('refresh_species_card_metadata failed: %s', e)
            return {'error': 'Failed to refresh species metadata'}, 500

    @app.route('/api/ui/species-image', methods=['GET'])
    def proxy_species_image():
        raw = (request.args.get('url') or '').strip()
        if not raw:
            return {'error': 'url is required'}, 400
        try:
            parsed = urlparse(raw)
        except ValueError:
            return {'error': 'only absolute http/https URLs are allowed'}, 400
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            return {'error': 'only absolute http/https URLs are allowed'}, 400
        try:
            host = (parsed.hostname or '').lower()
        except ValueError:
            return {'error': 'invalid URL for proxy'}, 400
        if not (
            _host_is_wikipedia_family(host)
            or _host_is_inaturalist(host)
            or _host_is_inaturalist_open_data_asset(host)
        ):
            return {'error': 'host is not allowed for proxy'}, 400
        if _species_proxy_sanitized_fetch_url(raw) is None:
            return {'error': 'invalid URL for image proxy'}, 400

        key = hashlib.sha1(raw.encode('utf-8')).hexdigest()
        cache_dir = os.path.join(data_dir(), 'cache', 'species_proxy')
        body_path = os.path.join(cache_dir, f'{key}.bin')
        ctype_path = os.path.join(cache_dir, f'{key}.ctype')
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except OSError:
            pass

        if os.path.isfile(body_path):
            try:
                with open(body_path, 'rb') as fh:
                    body = fh.read()
                ctype = 'image/jpeg'
                if os.path.isfile(ctype_path):
                    with open(ctype_path, 'r', encoding='utf-8') as fh:
                        ctype = (fh.read().strip() or ctype)
                return Response(
                    body,
                    status=200,
                    mimetype=ctype,
                    headers={'Cache-Control': 'public, max-age=86400'},
                )
            except OSError:
                pass

        last_err = None
        for attempt in range(2):
            upstream = None
            try:
                upstream, fetch_err = _fetch_species_proxy_upstream(raw)
                if fetch_err:
                    last_err = fetch_err
                    if attempt == 0:
                        time.sleep(0.35)
                        continue
                    break
                if upstream.status_code >= 400:
                    last_err = f'upstream status={upstream.status_code}'
                    if attempt == 0:
                        time.sleep(0.35)
                        continue
                    break
                ctype = (upstream.headers.get('Content-Type') or '').lower()
                if ctype and not ctype.startswith('image/'):
                    last_err = 'upstream is not image content'
                    break
                body = upstream.content
                try:
                    with open(body_path, 'wb') as fh:
                        fh.write(body)
                    with open(ctype_path, 'w', encoding='utf-8') as fh:
                        fh.write(ctype or 'image/jpeg')
                except OSError:
                    pass
                headers = {'Cache-Control': 'public, max-age=86400'}
                return Response(body, status=200, mimetype=ctype or 'image/jpeg', headers=headers)
            finally:
                if upstream is not None:
                    upstream.close()

        app.logger.warning(
            'Species image proxy failed url=%s detail=%s',
            (raw[:512] + '…') if len(raw) > 512 else raw,
            last_err,
        )
        return {'error': _species_proxy_client_error_message(last_err)}, 502

    @app.route('/api/ui/species/tuning-targets', methods=['GET'])
    def get_tuning_targets():
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        ids = _get_tuning_target_ids()
        if not ids:
            return {'ids': [], 'targets': []}, 200
        species_rows = Species.query.filter(Species.id.in_(ids)).all()
        by_id = {s.id: s for s in species_rows}

        observed_rows = (
            db.session.query(SpeciesVisit.species_id, func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0))
            .filter(SpeciesVisit.species_id.in_(ids))
            .group_by(SpeciesVisit.species_id)
            .all()
        )
        observed = {int(sid): int(cnt or 0) for sid, cnt in observed_rows if sid is not None}

        dataset_folders = _dataset_class_folders()

        targets = []
        for sid in ids:
            sp = by_id.get(sid)
            if not sp:
                continue
            in_dataset = _sanitize_dirname(sp.name or '') in dataset_folders
            targets.append({
                'id': sid,
                'name': sp.name,
                'observed_count': observed.get(sid, 0),
                'in_dataset': bool(in_dataset),
                'in_full_catalog': True,
            })
        return {'ids': ids, 'targets': targets}, 200

    @app.route('/api/ui/species/<int:species_id>/tuning-target', methods=['POST'])
    def set_species_tuning_target(species_id: int):
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        sp = db.session.get(Species, species_id)
        if not sp:
            return {'error': 'Species not found'}, 404
        payload = request.json or {}
        enabled = bool(payload.get('enabled'))
        ids = _get_tuning_target_ids()
        id_set = set(ids)
        if enabled:
            id_set.add(species_id)
        else:
            id_set.discard(species_id)
        _save_tuning_target_ids(sorted(id_set))
        bust_response_caches()
        return {
            'ok': True,
            'species_id': species_id,
            'enabled': enabled,
            'tuning_target_species_ids': sorted(id_set),
        }, 200
