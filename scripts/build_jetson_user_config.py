#!/usr/bin/env python3
"""Build Jetson user_config: default + operational template + overlay, strip Intel."""

import argparse
import copy
import re
from pathlib import Path
from typing import Any, Dict

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "app/app_config/default_config.yaml"
OPERATIONAL = ROOT / "app/app_config/user_config.jetson-operational.example.yaml"
PROD = ROOT / "app/app_config/.user_config_prod_drift.yaml"
OVERLAY = ROOT / "deploy/profiles/jetson-nano/config.overlay.yaml"
OUT = ROOT / "app/app_config/user_config.yaml"
EXAMPLE_OUT = ROOT / "app/app_config/user_config.jetson.example.yaml"

_INTEL_KEY_RE = re.compile(
    r"^(openvino_|.*_openvino$|.*openvino.*|inference_device$|binary_openvino|"
    r"classifier_openvino|classifier_birder|birder_eu|efficientnet_b2_onnx$)",
    re.I,
)

_INTEL_MODEL_KEYS = frozenset(
    {
        "binary_openvino",
        "classifier_openvino",
        "classifier_birder_eu",
        "classifier_birder_eu_openvino",
        "classifier_efficientnet_b2_onnx",
        "behavior_openvino",
    },
)

_SECRET_PATHS = (
    ("mqtt", "password"),
    ("video", "go2rtc_password"),
    ("general", "settings_password"),
    ("general", "contributor_password"),
    ("homeassistant", "token"),
    ("notifications", "telegram_bot_token"),
    ("mcp", "token"),
    ("secrets", "ebird_api_key"),
    ("secrets", "openweather_api_key"),
)


def deep_merge(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base)
    for key, val in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_site_env(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    out = {}  # type: Dict[str, str]
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def _strip_intel(node: Any, parent_key: str = "") -> Any:
    if isinstance(node, dict):
        cleaned = {}  # type: Dict[str, Any]
        for k, v in node.items():
            if k in _INTEL_MODEL_KEYS:
                continue
            if parent_key == "processor" and _INTEL_KEY_RE.match(k):
                continue
            if parent_key == "models" and k.endswith("_openvino"):
                continue
            if k == "openvino" and isinstance(v, dict):
                continue
            cleaned[k] = _strip_intel(v, k)
        return cleaned
    if isinstance(node, list):
        return [_strip_intel(x, parent_key) for x in node]
    if parent_key == "encoding" and str(node).strip().lower() == "intel":
        return "cpu"
    return node


def _apply_site(cfg: dict, site: Dict[str, str]) -> None:
    mqtt = cfg.setdefault("mqtt", {})
    if site.get("MQTT_BROKER"):
        mqtt["broker"] = site["MQTT_BROKER"]
    mqtt["port"] = int(site.get("MQTT_PORT") or mqtt.get("port") or 1883)
    if site.get("MQTT_USERNAME"):
        mqtt["username"] = site["MQTT_USERNAME"]
    if site.get("MQTT_PASSWORD"):
        mqtt["password"] = site["MQTT_PASSWORD"]

    video = cfg.setdefault("video", {})
    video.update(
        {
            "encoding": "cpu",
            "capture_backend": "opencv",
            "record_with_vaapi": False,
        }
    )
    if site.get("GO2RTC_URL"):
        video["go2rtc_url"] = site["GO2RTC_URL"]
    if site.get("GO2RTC_USERNAME"):
        video["go2rtc_username"] = site["GO2RTC_USERNAME"]
    if site.get("GO2RTC_PASSWORD"):
        video["go2rtc_password"] = site["GO2RTC_PASSWORD"]

    if site.get("HA_URL"):
        cfg.setdefault("homeassistant", {})["url"] = site["HA_URL"]
    if site.get("UI_BASE_URL"):
        cfg.setdefault("notifications", {})["base_url"] = site["UI_BASE_URL"]

    general = cfg.setdefault("general", {})
    if site.get("SETTINGS_PASSWORD"):
        general["settings_password"] = site["SETTINGS_PASSWORD"]
    if site.get("CONTRIBUTOR_PASSWORD"):
        general["contributor_password"] = site["CONTRIBUTOR_PASSWORD"]


def _apply_jetson_inference(cfg: dict, *, bootstrap_torch: bool) -> None:
    proc = cfg.setdefault("processor", {})
    proc["openvino_binary_enabled"] = False
    proc.pop("openvino", None)
    proc["classifier_engine"] = "chriamue"
    proc["binary_imgsz"] = 704
    proc["inference_lores_wh"] = [704, 576]

    models = proc.setdefault("models", {})
    base = "models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024"
    models.update(
        {
            "binary": f"{base}.pt",
            "binary_onnx": f"{base}.onnx",
            "binary_tensorrt": f"{base}.engine",
            "classifier": "models/classification/chriamue_bird_species_classifier",
            "classifier_chriamue": "models/classification/chriamue_bird_species_classifier",
            "classifier_efficientnet_b2": "models/classification/chriamue_bird_species_classifier",
            "welfare_embedder": "models/welfare/ornimetrics/embedder.onnx",
            "welfare_scorer": "models/welfare/ornimetrics/welfare_scorer.npz",
            "reid_embedder": "models/reid/ornimetrics/reid_embedder.onnx",
        }
    )

    br = proc.setdefault("behavior_recognition", {})
    br.update(
        {
            "engine": "meta",
            "inference_backend": "logistic_json",
            "openvino_fallback_logistic": False,
        }
    )
    reid = proc.setdefault("reid", {})
    reid.update({"inference_backend": "onnxruntime", "device": "cuda", "runtime_enabled": True})

    if bootstrap_torch:
        proc["inference_backend"] = "torch"
        proc["inference_device"] = "cpu"
        proc["classifier_inference_backend"] = "torch"
        proc["classifier_inference_device"] = "cpu"
        reid["inference_backend"] = "torch"
        reid["device"] = "cpu"
    else:
        proc["inference_backend"] = "tensorrt"
        proc.pop("inference_device", None)
        proc["classifier_inference_backend"] = "onnxruntime"
        proc["classifier_inference_device"] = "cuda"


def _sanitize(cfg: dict) -> None:
    for section, key in _SECRET_PATHS:
        sec = cfg.get(section)
        if isinstance(sec, dict) and key in sec:
            sec[key] = "CHANGE_ME"
    notif = cfg.get("notifications")
    if isinstance(notif, dict):
        for k in list(notif.keys()):
            if "token" in k or "secret" in k or "password" in k:
                notif[k] = "CHANGE_ME"


def _build_base(use_prod: bool) -> dict:
    cfg = _load_yaml(DEFAULT)
    cfg = deep_merge(cfg, _load_yaml(OPERATIONAL))
    if use_prod and PROD.is_file():
        cfg = deep_merge(cfg, _load_yaml(PROD))
    cfg = deep_merge(cfg, _load_yaml(OVERLAY))
    return cfg


def _dump_yaml(cfg: dict) -> str:
    try:
        return yaml.safe_dump(
            cfg, sort_keys=False, allow_unicode=True, default_flow_style=False
        )
    except TypeError:
        return yaml.safe_dump(cfg, allow_unicode=True, default_flow_style=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-torch", action="store_true")
    parser.add_argument("--use-prod-drift", action="store_true", help="merge .user_config_prod_drift.yaml if present")
    parser.add_argument(
        "--site-env",
        type=Path,
        default=ROOT / "deploy/profiles/jetson-nano/site.env",
    )
    parser.add_argument("-o", "--output", type=Path, default=OUT)
    parser.add_argument("--example", action="store_true", help="write sanitized user_config.jetson.example.yaml")
    args = parser.parse_args()

    cfg = _build_base(use_prod=args.use_prod_drift)
    cfg = _strip_intel(cfg)
    site = _load_site_env(args.site_env)
    if not site and args.site_env.with_name("site.example.env").is_file():
        site = _load_site_env(args.site_env.with_name("site.example.env"))
    _apply_site(cfg, site)
    _apply_jetson_inference(cfg, bootstrap_torch=args.bootstrap_torch)
    cfg["_meta"] = {"schema_version": 7, "platform": "jetson_nano"}

    out = EXAMPLE_OUT if args.example else args.output
    if args.example:
        _sanitize(cfg)

    out.write_text(_dump_yaml(cfg), encoding="utf-8")
    mode = "bootstrap-torch" if args.bootstrap_torch else "production-trt"
    print(f"Wrote {out} ({len(cfg)} keys, mode={mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
