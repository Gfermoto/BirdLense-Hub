#!/usr/bin/env python3
"""Verify hard negatives manifest structure and file integrity (#394)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_KINDS = {'image_level', 'object_crop'}
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp'}


def _resolve_item_path(
    *,
    relative_path: str,
    manifest_path: Path,
    dataset_root: Path | None,
) -> Path | None:
    rel = Path(relative_path)
    if rel.is_absolute():
        return None
    if '..' in rel.parts:
        return None

    manifest_rel = (manifest_path.parent / rel).resolve()
    if manifest_rel.exists():
        return manifest_rel

    if dataset_root is not None:
        dataset_rel = (dataset_root / rel).resolve()
        if dataset_rel.exists():
            return dataset_rel

    return None


def verify_manifest(
    payload: dict[str, Any],
    *,
    manifest_path: Path,
    dataset_root: Path | None = None,
    require_existing_files: bool = False,
) -> tuple[bool, dict[str, Any]]:
    """Validate schema-like fields and optional on-disk file integrity."""
    errors: list[str] = []
    items = payload.get('items')
    if payload.get('schema') != 'hard_negatives_manifest@v1':
        errors.append('schema_mismatch:expected hard_negatives_manifest@v1')
    if not isinstance(items, list):
        errors.append('items_missing_or_not_array')
        return False, {'ok': False, 'errors': errors}
    if not items:
        errors.append('items_empty')

    seen: set[str] = set()
    valid_items = 0
    missing_files = 0
    for idx, row in enumerate(items):
        if not isinstance(row, dict):
            errors.append(f'item_not_object:{idx}')
            continue
        rel = row.get('relative_path')
        kind = row.get('kind')
        if not isinstance(rel, str) or not rel.strip():
            errors.append(f'item_relative_path_invalid:{idx}')
            continue
        rel = rel.strip()
        if rel in seen:
            errors.append(f'duplicate_relative_path:{rel}')
            continue
        seen.add(rel)

        if kind not in ALLOWED_KINDS:
            errors.append(f'item_kind_invalid:{idx}:{kind}')

        suffix = Path(rel).suffix.lower()
        if suffix and suffix not in IMAGE_EXT:
            errors.append(f'item_extension_unexpected:{idx}:{suffix}')

        if require_existing_files:
            resolved = _resolve_item_path(
                relative_path=rel,
                manifest_path=manifest_path,
                dataset_root=dataset_root,
            )
            if resolved is None:
                missing_files += 1
                errors.append(f'item_file_missing:{rel}')
        valid_items += 1

    summary = {
        'ok': len(errors) == 0,
        'errors': errors,
        'total_items': len(items),
        'unique_items': len(seen),
        'valid_items': valid_items,
        'missing_files': missing_files,
        'manifest_path': str(manifest_path),
        'dataset_root': str(dataset_root) if dataset_root else None,
        'require_existing_files': require_existing_files,
    }
    return summary['ok'], summary


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--manifest',
        required=True,
        help='Path to manifest JSON',
    )
    parser.add_argument(
        '--dataset-root',
        default='',
        help='Optional dataset root for resolving relative paths',
    )
    parser.add_argument(
        '--require-existing-files',
        action='store_true',
        help='Fail if listed files are not found',
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    payload = json.loads(manifest_path.read_text(encoding='utf-8'))
    dataset_root = (
        Path(args.dataset_root).resolve()
        if args.dataset_root
        else None
    )
    ok, summary = verify_manifest(
        payload,
        manifest_path=manifest_path,
        dataset_root=dataset_root,
        require_existing_files=bool(args.require_existing_files),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
