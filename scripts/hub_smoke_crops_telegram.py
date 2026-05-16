#!/usr/bin/env python3
"""
Смоук детектора на хабе (контейнер birdlense, APP_ROOT=/app):

- Берёт до N роликов из SQLite за «сегодня» (локальный день БД).
- Прогоняет **весь ролик** (последовательно, с лимитом по кадрам/сек), YOLO OpenVINO.
- Рисует **рамки и подписи классов** через ``Results.plot()`` — не кропы.
- Пишет ``annotated_{id}.mp4`` + ``contact_{id}.jpg`` (3 кадра с рамками в одной полосе).
- Опционально шлёт в Telegram: ``sendVideo`` (если файл не слишком большой) или превью-фото.

Пример:

    python3 scripts/hub_smoke_crops_telegram.py

    python3 scripts/hub_smoke_crops_telegram.py --no-telegram \\
        --max-seconds 20 --frame-step 1 --limit-videos 3
"""

from __future__ import annotations

import argparse
import io
import os
import sqlite3
import sys
from pathlib import Path

import cv2
import requests
import yaml
from ultralytics import YOLO

APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))


def _load_notify(cfg_path: Path) -> tuple[str, str, dict]:
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    n = raw.get("notifications") or {}
    token = str(n.get("telegram_bot_token") or "").strip()
    chat = str(n.get("telegram_chat_id") or "").strip()
    return token, chat, n


def _telegram_session(n: dict) -> tuple[str, dict | None, int]:
    api_base = (n.get("telegram_api_base") or "").strip().rstrip("/") or "https://api.telegram.org"
    proxy_url = (n.get("telegram_proxy_url") or "").strip()
    proxies = {"https": proxy_url, "http": proxy_url} if proxy_url else None
    timeout = int(n.get("telegram_timeout") or 300)
    return api_base, proxies, timeout


def _predict_device(ov: YOLO, frame, *, dev: str, conf: float, imgsz: int):
    try:
        return ov.predict(frame, device=dev, conf=conf, imgsz=imgsz, verbose=False)[0]
    except Exception:
        return ov.predict(frame, device="intel:cpu", conf=conf, imgsz=imgsz, verbose=False)[0]


def _annotate_video(
    ov: YOLO,
    vp: Path,
    out_mp4: Path,
    *,
    predict_device: str,
    conf: float,
    imgsz: int,
    frame_step: int,
    max_frames: int,
) -> tuple[int, int]:
    """
    Возвращает (записано_кадров, всего_обработано_кадров).
    """
    cap = cv2.VideoCapture(str(vp))
    if not cap.isOpened():
        return 0, 0
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_in = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    out_fps = fps / max(1, frame_step)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_mp4), fourcc, out_fps, (w, h))
    written = 0
    processed = 0
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        if processed >= max_frames:
            break
        if idx % frame_step != 0:
            idx += 1
            continue
        r = _predict_device(ov, frame, dev=predict_device, conf=conf, imgsz=imgsz)
        plotted = r.plot()
        if plotted.shape[1] != w or plotted.shape[0] != h:
            plotted = cv2.resize(plotted, (w, h))
        if plotted.ndim == 2:
            plotted = cv2.cvtColor(plotted, cv2.COLOR_GRAY2BGR)
        writer.write(plotted)
        written += 1
        processed += 1
        idx += 1

    cap.release()
    writer.release()
    return written, min(processed, total_in or processed)


def _contact_sheet(ov: YOLO, vp: Path, out_jpg: Path, *, dev: str, conf: float, imgsz: int) -> bool:
    """Три кадра (начало / середина / конец) с рамками в одном JPEG."""
    cap = cv2.VideoCapture(str(vp))
    if not cap.isOpened():
        return False
    nfr = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    idxs = [0]
    if nfr > 2:
        idxs.append(nfr // 2)
        idxs.append(max(0, nfr - 1))
    elif nfr == 2:
        idxs.append(1)
    imgs = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, fr = cap.read()
        if not ret or fr is None:
            continue
        r = _predict_device(ov, fr, dev=dev, conf=conf, imgsz=imgsz)
        imgs.append(r.plot())
    cap.release()
    if not imgs:
        return False
    h = max(x.shape[0] for x in imgs)
    w = max(x.shape[1] for x in imgs)
    norm = [cv2.resize(x, (w, h)) if x.shape[:2] != (h, w) else x for x in imgs]
    row = cv2.hconcat(norm) if len(norm) <= 3 else cv2.hconcat(norm[:3])
    return bool(cv2.imwrite(str(out_jpg), row))


def main() -> int:
    ap = argparse.ArgumentParser(description="Смоук OpenVINO: аннотированное видео + опционально TG")
    ap.add_argument("--limit-videos", type=int, default=5)
    ap.add_argument("--frame-step", type=int, default=1, help="обрабатывать каждый N-й кадр (ускорение)")
    ap.add_argument("--max-frames", type=int, default=600, help="макс. кадров с инференсом на ролик")
    ap.add_argument("--max-seconds", type=float, default=0, help="если >0, лимит по длительности (при известном fps)")
    ap.add_argument("--conf", type=float, default=0.2)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", type=str, default="intel:gpu")
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()

    cfg_path = APP_ROOT / "app_config/user_config.yaml"
    if not cfg_path.is_file():
        print("ERR: no user_config.yaml", file=sys.stderr)
        return 1
    token, chat_id, n = _load_notify(cfg_path)
    if not args.no_telegram:
        if not token or not chat_id:
            print("ERR: telegram not configured; use --no-telegram", file=sys.stderr)
            return 1
        api_base, proxies, timeout = _telegram_session(n)
    else:
        api_base, proxies, timeout = "", None, 60

    model_path = APP_ROOT / "processor/models/detection/weights/best_openvino_model"
    ov = YOLO(str(model_path))

    con = sqlite3.connect(str(APP_ROOT / "data/db/birdlense.db"))
    lim = max(1, min(50, int(args.limit_videos)))
    rows = con.execute(
        """
        SELECT id, video_path, start_time
        FROM video
        WHERE deleted_at IS NULL
          AND date(start_time) = date('now', 'localtime')
        ORDER BY id DESC
        LIMIT ?
        """,
        (lim,),
    ).fetchall()
    if len(rows) < lim:
        rows = con.execute(
            """
            SELECT id, video_path, start_time
            FROM video
            WHERE deleted_at IS NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (lim,),
        ).fetchall()

    out_dir = APP_ROOT / "data/tmp_smoke_annotated"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.no_telegram:
        url_photo = f"{api_base}/bot{token}/sendPhoto"
        url_video = f"{api_base}/bot{token}/sendVideo"

    ok_any = 0
    for vid, rel, st in rows:
        vp = APP_ROOT / rel
        if not vp.is_file():
            print(f"skip missing id={vid}")
            continue

        cap = cv2.VideoCapture(str(vp))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        cap.release()
        max_f = args.max_frames
        if args.max_seconds > 0 and fps > 0:
            max_f = min(max_f, int(args.max_seconds * fps))

        out_mp4 = out_dir / f"annotated_{vid}.mp4"
        wn, proc = _annotate_video(
            ov,
            vp,
            out_mp4,
            predict_device=args.device,
            conf=args.conf,
            imgsz=args.imgsz,
            frame_step=max(1, args.frame_step),
            max_frames=max_f,
        )
        print(f"video id={vid} wrote_frames={wn} infer_cap={max_f} path={out_mp4.name}")
        cj = out_dir / f"contact_{vid}.jpg"
        if _contact_sheet(ov, vp, cj, dev=args.device, conf=args.conf, imgsz=args.imgsz):
            print(f"  contact_sheet {cj.name}")

        if args.no_telegram:
            ok_any += 1
            continue

        caption = f"annotated id={vid} dt={st} frames={wn} {rel}"[:1024]
        sent = False
        sz = out_mp4.stat().st_size if out_mp4.is_file() else 0
        if out_mp4.is_file() and sz > 0 and sz < 48 * 1024 * 1024:
            with open(out_mp4, "rb") as fh:
                files = {"video": ("clip.mp4", fh, "video/mp4")}
                data = {"chat_id": chat_id, "caption": caption, "supports_streaming": "true"}
                r = requests.post(url_video, data=data, files=files, proxies=proxies, timeout=timeout)
            if r.ok:
                sent = True
                print(f"  tg sendVideo ok id={vid} bytes={sz}")
            else:
                print(f"  tg sendVideo fail http={r.status_code} {r.text[:300]}")

        if not sent:
            pj = out_dir / f"contact_{vid}.jpg"
            if not pj.is_file() and _contact_sheet(ov, vp, pj, dev=args.device, conf=args.conf, imgsz=args.imgsz):
                pass
            if pj.is_file():
                img_bytes = pj.read_bytes()
                files = {"photo": ("sheet.jpg", io.BytesIO(img_bytes), "image/jpeg")}
                data = {"chat_id": chat_id, "caption": caption[:1024]}
                r = requests.post(url_photo, data=data, files=files, proxies=proxies, timeout=timeout)
                if r.ok:
                    sent = True
                    print(f"  tg sendPhoto fallback {pj.name}")
        if sent or wn > 0:
            ok_any += 1

    print(f"done ok_segments={ok_any}/{len(rows)} out_dir={out_dir}")
    return 0 if ok_any else 1


if __name__ == "__main__":
    raise SystemExit(main())
