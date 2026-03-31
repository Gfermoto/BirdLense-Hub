#!/usr/bin/env python3
"""Automated catalog card audit for BirdLense Hub.

Checks full_eu catalog cards via public API:
1) species summary is reachable
2) description is non-empty
3) image_url is non-empty and reachable (HTTP 2xx/3xx)

Exit code:
- 0: no issues
- 1: at least one issue found
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import sys
from dataclasses import dataclass, asdict

import requests


@dataclass
class CardIssue:
    species_id: int
    species_name: str
    issue: str
    details: str


def _ok_image_status(code: int) -> bool:
    return 200 <= code < 400


def _needs_proxy(image_url: str) -> bool:
    return 'inaturalist' in (image_url or '').lower()


def _check_species(base_url: str, species_id: int, timeout: float) -> list[CardIssue]:
    out: list[CardIssue] = []
    try:
        r = requests.get(f'{base_url}/api/ui/species/{species_id}/summary', timeout=timeout)
    except Exception as exc:  # pragma: no cover - network failures are reported
        return [CardIssue(species_id, '', 'summary_request_failed', str(exc))]
    if r.status_code != 200:
        return [CardIssue(species_id, '', 'summary_http_error', f'status={r.status_code}')]

    body = r.json() or {}
    sp = body.get('species') or {}
    name = str(sp.get('name') or '')
    desc = str(sp.get('description') or '').strip()
    image_url = str(sp.get('image_url') or '').strip()

    if not desc:
        out.append(CardIssue(species_id, name, 'empty_description', 'description is blank'))
    if not image_url:
        out.append(CardIssue(species_id, name, 'empty_image_url', 'image_url is blank'))
        return out

    # Validate via the same route as UI:
    # - iNaturalist URLs go through hub proxy
    # - Wikimedia/other image hosts are loaded directly by the browser
    try:
        if _needs_proxy(image_url):
            h = requests.get(
                f'{base_url}/api/ui/species-image',
                params={'url': image_url},
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
            issue_prefix = 'image_proxy'
        else:
            h = requests.get(
                image_url,
                timeout=timeout,
                allow_redirects=True,
                stream=True,
                headers={
                    'User-Agent': 'BirdLense-Hub-Audit/1.0',
                    'Accept': 'image/*,*/*;q=0.8',
                },
            )
            issue_prefix = 'image_direct'
        status = h.status_code
        ctype = (h.headers.get('Content-Type') or '').lower()
        h.close()
        if not _ok_image_status(status):
            out.append(CardIssue(species_id, name, f'{issue_prefix}_unreachable', f'status={status} url={image_url}'))
        elif ctype and not ctype.startswith('image/'):
            out.append(CardIssue(species_id, name, f'{issue_prefix}_not_image', f'ctype={ctype} url={image_url}'))
    except Exception as exc:  # pragma: no cover
        out.append(CardIssue(species_id, name, 'image_check_failed', f'{exc} url={image_url}'))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description='Audit full_eu species cards.')
    p.add_argument('--base-url', default='https://birdlense.eyera.info')
    p.add_argument('--timeout', type=float, default=20.0)
    p.add_argument('--workers', type=int, default=12)
    p.add_argument('--limit', type=int, default=0, help='check only first N species (0 = all)')
    p.add_argument('--report-path', default='', help='optional JSON report output path')
    args = p.parse_args()

    base = args.base_url.rstrip('/')
    r = requests.get(f'{base}/api/ui/migration-calendar', params={'catalog': 'full_eu'}, timeout=args.timeout)
    r.raise_for_status()
    species = r.json().get('species') or []

    ids = [int(s['id']) for s in species if isinstance(s.get('id'), int) and int(s['id']) > 0]
    if args.limit and args.limit > 0:
        ids = ids[: args.limit]

    issues: list[CardIssue] = []
    with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = [pool.submit(_check_species, base, sid, args.timeout) for sid in ids]
        for fut in cf.as_completed(futs):
            issues.extend(fut.result())

    report = {
        'base_url': base,
        'checked_species': len(ids),
        'issue_count': len(issues),
        'issues': [asdict(x) for x in sorted(issues, key=lambda z: (z.issue, z.species_id))],
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.report_path:
        out_dir = os.path.dirname(args.report_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.report_path, 'w', encoding='utf-8') as f:
            f.write(payload + '\n')
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())

