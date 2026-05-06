#!/usr/bin/env python3
"""
Скачать птиц с iNaturalist API в формат YOLO classification.

Формат выхода: output_dir/train/Scientific (Common)/img.jpg
Имена классов: "Scientific_name (Common Name)" — совпадает с Frigate, BirdNET.

Использование:
    pip install requests tqdm Pillow
    python download_inaturalist.py --output inaturalist_europe_cls --max-obs 5000
    python download_inaturalist.py --taxon-id <ID_вида> --no-place-filter --max-obs 500 \\
        --output inaturalist_one_species   # ID в URL страницы вида на inaturalist.org
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

import requests
from requests.exceptions import RequestException
from tqdm import tqdm

from species_format import format_scientific_common

# Europe place_id (incl. Canary, Svalbard)
EUROPE_PLACE_ID = 96372
AVES_TAXON_ID = 3
API = "https://api.inaturalist.org/v1/observations"
RATE_LIMIT = 1.1  # сек между запросами (~60/мин)


def fetch_observations(
    page: int = 1,
    per_page: int = 200,
    *,
    query_taxon_id: int,
    place_id: int | None,
    timeout: tuple[float, float] = (45.0, 180.0),
    max_retries: int = 6,
) -> dict:
    """Research-grade наблюдения; place_id=None — без фильтра региона (глобально)."""
    params: dict = {
        "taxon_id": query_taxon_id,
        "quality_grade": "research",
        "per_page": per_page,
        "page": page,
    }
    if place_id is not None:
        params["place_id"] = place_id
    delay = 4.0
    for attempt in range(max_retries):
        try:
            r = requests.get(API, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (RequestException, TimeoutError, OSError) as e:
            if attempt + 1 >= max_retries:
                raise RuntimeError(
                    f"iNat API page={page} failed after {max_retries} attempts: {e}"
                ) from e
            time.sleep(delay)
            delay = min(delay * 1.6, 90.0)


def download_inaturalist_cls_layer(
    output: Path,
    *,
    query_taxon_id: int,
    place_id: int | None,
    max_observations: int,
    val_ratio: float = 0.2,
    photo_size: str = "medium",
    seed: int = 42,
    rate_limit: float = RATE_LIMIT,
) -> dict[str, int]:
    """
    Скачать до max_observations наблюдений для одного query_taxon_id (вид или Aves).
    Не очищает output — дописывает в train/ и val/.
    """
    output = output.resolve()
    (output / "train").mkdir(parents=True, exist_ok=True)
    (output / "val").mkdir(parents=True, exist_ok=True)

    rnd = random.Random(seed)
    img_count = 0
    obs_count = 0
    page = 1
    per_page = 200
    species_seen: set[str] = set()

    pbar = tqdm(total=max_observations, desc=f"iNat taxon={query_taxon_id}", unit="obs")

    while obs_count < max_observations:
        time.sleep(rate_limit)
        data = fetch_observations(
            page=page,
            per_page=per_page,
            query_taxon_id=query_taxon_id,
            place_id=place_id,
        )
        results = data.get("results", [])
        if not results:
            break

        for obs in results:
            if obs_count >= max_observations:
                break
            obs_taxon = obs.get("taxon")
            if not obs_taxon:
                continue
            scientific = obs_taxon.get("name") or obs.get("species_guess", "")
            common = obs_taxon.get("preferred_common_name") or obs_taxon.get("english_common_name") or ""
            photos = obs.get("photos", [])
            if not photos:
                continue

            species_display = format_scientific_common(scientific, common or scientific)
            species_seen.add(species_display)
            split = "val" if rnd.random() < val_ratio else "train"
            out_dir = output / split / species_display
            out_dir.mkdir(parents=True, exist_ok=True)

            for i, photo in enumerate(photos):
                url = photo.get("url", "")
                for sz in ("/square.", "/thumb.", "/small."):
                    if sz in url:
                        url = url.replace(sz, f"/{photo_size}.")
                        break
                if not url or ("inaturalist" not in url and "amazonaws" not in url):
                    continue
                fname = f"{obs['id']}_{i}.jpg"
                out_path = out_dir / fname
                if out_path.exists():
                    continue
                try:
                    time.sleep(rate_limit * 0.5)
                    r = requests.get(url, timeout=(20.0, 90.0))
                    r.raise_for_status()
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
    return {
        "observations": obs_count,
        "images_written": img_count,
        "distinct_labels": len(species_seen),
        "output": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="inaturalist_europe_cls", help="Output directory")
    parser.add_argument("--max-obs", type=int, default=5000, help="Max observations to fetch")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument(
        "--photo-size",
        default="medium",
        choices=["thumb", "small", "medium", "large"],
        help="Photo size from API",
    )
    parser.add_argument(
        "--taxon-id",
        type=int,
        default=None,
        metavar="ID",
        help="Таксон вида на iNaturalist. По умолчанию все птицы (Aves) в Европе.",
    )
    parser.add_argument(
        "--no-place-filter",
        action="store_true",
        help="Не передавать place_id (глобально для узкого taxon-id).",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    qtax = args.taxon_id if args.taxon_id is not None else AVES_TAXON_ID
    place = None if args.no_place_filter else EUROPE_PLACE_ID

    stats = download_inaturalist_cls_layer(
        Path(args.output),
        query_taxon_id=qtax,
        place_id=place,
        max_observations=args.max_obs,
        val_ratio=args.val_ratio,
        photo_size=args.photo_size,
        seed=args.seed,
    )
    print(
        f"Saved {stats['images_written']} images, {stats['distinct_labels']} labels -> {stats['output']}"
    )


if __name__ == "__main__":
    main()
