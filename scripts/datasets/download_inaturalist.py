#!/usr/bin/env python3
"""
Скачать птиц Европы с iNaturalist API в формат YOLO classification.

Формат выхода: output_dir/train/Scientific_Common/img.jpg
Имена классов: "Scientific_name (Common Name)" — совпадает с Frigate, BirdNET.

Использование:
    pip install requests tqdm Pillow
    python download_inaturalist.py --output inaturalist_europe_cls --max-obs 5000
    python download_inaturalist.py --taxon-id <ID_вида> --no-place-filter --max-obs 500 \\
        --output inaturalist_one_species   # ID в URL страницы вида на inaturalist.org
"""

import argparse
import time
from pathlib import Path

import requests
from tqdm import tqdm

from species_format import format_scientific_common

# Europe place_id (incl. Canary, Svalbard)
EUROPE_PLACE_ID = 96372
AVES_TAXON_ID = 3
API = "https://api.inaturalist.org/v1/observations"
RATE_LIMIT = 1.1  # сек между запросами (60/мин)


def fetch_observations(
    page: int = 1,
    per_page: int = 200,
    *,
    taxon_id: int,
    place_id: int | None,
) -> dict:
    """Research-grade наблюдения; place_id=None — без фильтра региона (глобально)."""
    params: dict = {
        'taxon_id': taxon_id,
        'quality_grade': 'research',
        'per_page': per_page,
        'page': page,
    }
    if place_id is not None:
        params['place_id'] = place_id
    r = requests.get(API, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='inaturalist_europe_cls',
                        help='Output directory')
    parser.add_argument('--max-obs', type=int, default=5000,
                        help='Max observations to fetch')
    parser.add_argument('--val-ratio', type=float, default=0.2)
    parser.add_argument('--photo-size', default='medium',
                        choices=['thumb', 'small', 'medium', 'large'],
                        help='Photo size from API')
    parser.add_argument(
        '--taxon-id',
        type=int,
        default=None,
        metavar='ID',
        help='Таксон вида на iNaturalist (со страницы вида). По умолчанию все птицы (Aves) в Европе.',
    )
    parser.add_argument(
        '--no-place-filter',
        action='store_true',
        help='Не передавать place_id (добор по всему миру для узкого taxon-id).',
    )
    args = parser.parse_args()

    taxon = args.taxon_id if args.taxon_id is not None else AVES_TAXON_ID
    place = None if args.no_place_filter else EUROPE_PLACE_ID

    output = Path(args.output).resolve()
    (output / 'train').mkdir(parents=True, exist_ok=True)
    (output / 'val').mkdir(parents=True, exist_ok=True)

    import random
    random.seed(42)
    seen_species = set()
    img_count = 0
    obs_count = 0
    page = 1
    per_page = 200

    pbar = tqdm(total=args.max_obs, desc='Observations', unit='obs')

    while obs_count < args.max_obs:
        time.sleep(RATE_LIMIT)
        data = fetch_observations(page=page, per_page=per_page, taxon_id=taxon, place_id=place)
        results = data.get('results', [])
        if not results:
            break

        for obs in results:
            if obs_count >= args.max_obs:
                break
            taxon = obs.get('taxon')
            if not taxon:
                continue
            scientific = taxon.get('name') or obs.get('species_guess', '')
            common = taxon.get('preferred_common_name') or taxon.get('english_common_name') or ''
            photos = obs.get('photos', [])
            if not photos:
                continue

            # Формат "Scientific (Common)" — совпадает с Frigate
            species_display = format_scientific_common(scientific, common or scientific)
            class_name = species_display  # папка = полное имя (Linux допускает пробелы и скобки)
            seen_species.add(class_name)
            split = 'val' if random.random() < args.val_ratio else 'train'
            out_dir = output / split / class_name
            out_dir.mkdir(parents=True, exist_ok=True)

            for i, photo in enumerate(photos):
                url = photo.get('url', '')
                for sz in ('/square.', '/thumb.', '/small.'):
                    if sz in url:
                        url = url.replace(sz, f'/{args.photo_size}.')
                        break
                if not url or ('inaturalist' not in url and 'amazonaws' not in url):
                    continue
                try:
                    time.sleep(RATE_LIMIT * 0.5)
                    r = requests.get(url, timeout=15)
                    r.raise_for_status()
                    ext = '.jpg' if 'jpeg' in r.headers.get('content-type', '') else '.jpg'
                    fname = f"{obs['id']}_{i}{ext}"
                    out_path = out_dir / fname
                    if not out_path.exists():
                        out_path.write_bytes(r.content)
                    img_count += 1
                except Exception:
                    pass

            obs_count += 1
            pbar.update(1)

        page += 1
        if len(results) < per_page:
            break

    pbar.close()
    print(f'Saved {img_count} images, {len(seen_species)} species to {output}')


if __name__ == '__main__':
    main()
