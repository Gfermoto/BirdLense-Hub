#!/usr/bin/env python3
"""
Эмбеддинг кропов через DINOv2 (torch.hub) — офлайн-прототип для Re-ID (#383 / #374).

Пример::

    python3 scripts/reid/embed_dinov2_crop.py --image crop.jpg
    python3 scripts/reid/embed_dinov2_crop.py --glob 'exports/crops/*.jpg' --output embed.jsonl

Зависимости (не в базовом образе процессора): torch, torchvision, Pillow.
Первый запуск может скачать веса через torch.hub (нужен доступ в интернет).
"""

from __future__ import annotations

import argparse
import glob as glob_mod
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _pick_cls_embedding(features: Any) -> Any:
    """Из выхода forward_features достаём вектор [B, D]."""
    import torch

    if isinstance(features, torch.Tensor):
        if features.dim() == 3:
            return features[:, 0, :]
        if features.dim() == 2:
            return features
        raise RuntimeError(f"Unexpected tensor shape {tuple(features.shape)}")
    if isinstance(features, dict):
        for key in ("x_norm_clstoken", "x_prenorm_clstoken", "cls_token"):
            t = features.get(key)
            if torch.is_tensor(t):
                return t.squeeze(1) if t.dim() == 3 else t
        for _k, v in features.items():
            if torch.is_tensor(v) and v.dim() in (2, 3):
                return v.squeeze(1) if v.dim() == 3 else v
    raise RuntimeError("Cannot interpret forward_features output")


def _infer_side(model: Any) -> int:
    pe = getattr(model, "patch_embed", None)
    if pe is None:
        return 518
    img_size = getattr(pe, "img_size", None)
    if isinstance(img_size, tuple) and len(img_size) >= 1:
        return int(img_size[0])
    if isinstance(img_size, int):
        return img_size
    return 518


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", help="Один файл изображения (jpeg/png)")
    ap.add_argument("--glob", dest="glob_pat", help="Шаблон glob для нескольких файлов")
    ap.add_argument(
        "--model",
        default="dinov2_vits14",
        help="Имя модели в hub facebookresearch/dinov2 (dinov2_vits14, dinov2_vitb14, …)",
    )
    ap.add_argument("--output", "-o", help="Писать JSON Lines в файл (иначе stdout)")
    ap.add_argument(
        "--device", default=None, help="cuda | cpu (по умолчанию: cuda если доступен)"
    )
    args = ap.parse_args()

    if not args.image and not args.glob_pat:
        ap.error("Укажите --image или --glob")

    try:
        import torch
        import torch.nn.functional as F
        from PIL import Image
        from torchvision import transforms
    except ImportError as e:
        print(
            "Requires torch, torchvision, Pillow (offline GPU/CPU env).\n"
            "Example: pip install torch torchvision pillow",
            file=sys.stderr,
        )
        print(str(e), file=sys.stderr)
        return 2

    paths: list[Path] = []
    if args.image:
        paths.append(Path(args.image))
    if args.glob_pat:
        paths.extend(sorted(Path(p) for p in glob_mod.glob(args.glob_pat)))

    if not paths:
        print("Нет файлов по заданным путям.", file=sys.stderr)
        return 2

    device_s = args.device or (
        "cuda" if __import__("torch").cuda.is_available() else "cpu"
    )
    device = torch.device(device_s)

    print(f"Loading {args.model} from torch.hub on {device_s} …", file=sys.stderr)
    model = torch.hub.load("facebookresearch/dinov2", args.model)
    model.eval()
    model.to(device)

    side = _infer_side(model)
    tfm = transforms.Compose(
        [
            transforms.Resize(side, interpolation=transforms.InterpolationMode.BICUBIC),
            transforms.CenterCrop(side),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )

    # RFC (#389): embedding contract metadata for safe downstream imports/queries.
    try:
        from app.web.services.reid_contract import (
            EMBEDDING_SCHEMA_V1,
            stable_sha16_from_bytes,
            stable_sha16_from_state_dict,
        )
    except Exception:
        # scripts may run without web package on PYTHONPATH — keep minimal inline fallbacks
        EMBEDDING_SCHEMA_V1 = "embedding_schema@v1"

        def stable_sha16_from_bytes(data: bytes) -> str:  # type: ignore
            import hashlib

            return hashlib.sha256(data).hexdigest()[:16]

        def stable_sha16_from_state_dict(state_dict: dict[str, Any]) -> str:  # type: ignore
            import hashlib

            h = hashlib.sha256()
            for k in sorted(state_dict.keys()):
                h.update(str(k).encode("utf-8"))
                h.update(b":")
                v = state_dict[k]
                try:
                    import torch as _torch

                    if _torch.is_tensor(v):
                        vv = v.detach().cpu().contiguous().view(-1)[:4096]
                        h.update(vv.numpy().tobytes())
                        h.update(str(tuple(v.shape)).encode("utf-8"))
                        h.update(str(v.dtype).encode("utf-8"))
                        continue
                except Exception:
                    pass
                h.update(str(type(v)).encode("utf-8"))
                h.update(b";")
            return h.hexdigest()[:16]

    embedding_model_id = f"torchhub:facebookresearch/dinov2:{args.model}"
    model_sha16 = stable_sha16_from_state_dict(dict(model.state_dict()))

    out_lines: list[str] = []

    with torch.inference_mode():
        for p in paths:
            if not p.is_file():
                print(f"Skip missing: {p}", file=sys.stderr)
                continue
            crop_bytes = p.read_bytes()
            crop_fp = stable_sha16_from_bytes(crop_bytes)
            img = Image.open(p).convert("RGB")
            batch = tfm(img).unsqueeze(0).to(device)
            feats = model.forward_features(batch)
            vec = _pick_cls_embedding(feats)
            vec = F.normalize(vec.float(), dim=-1).squeeze(0)
            emb = vec.cpu().numpy().astype("float64")
            created_at = (
                datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
            row = {
                "path": str(p.resolve()),
                "model": args.model,
                "dim": int(emb.shape[0]),
                "embedding": emb.tolist(),
                # Contract fields (#389)
                "embedding_schema": EMBEDDING_SCHEMA_V1,
                "embedding_model_id": embedding_model_id,
                "embedding_model_sha16": model_sha16,
                "crop_fingerprint_sha16": crop_fp,
                "created_at_utc": created_at,
            }
            out_lines.append(json.dumps(row, ensure_ascii=False))

    text = "\n".join(out_lines) + ("\n" if out_lines else "")
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Wrote {len(out_lines)} rows → {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
