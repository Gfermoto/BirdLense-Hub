"""Runtime profile selection for low-light / night detection tuning."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class RuntimeProfileConfigOverlay(Mapping):
    """Read-only app_config overlay with profile-specific processor overrides."""

    def __init__(self, app_config, overrides: Mapping[str, Any] | None = None):
        """Store base app_config and per-profile processor override values."""
        self._app_config = app_config
        self._overrides = dict(overrides or {})

    def __getitem__(self, key):
        """Resolve a value or raise KeyError if nothing is set."""
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __iter__(self):
        """Iterate like an empty mapping; only .get() is used in practice."""
        yield from ()

    def __len__(self):
        """Return zero because overlay is get-oriented, not key-enumerated."""
        return 0

    def get(self, key, default=None):
        """Resolve `processor.*` key from overrides first, then fallback."""
        short = str(key or "")
        if short.startswith("processor."):
            short = short.split(".", 1)[1]
        if short in self._overrides:
            return self._overrides[short]
        return self._app_config.get(key, default)

    def resolve_strategy_field(self, full_key: str, strategy: Any, attr: str, default: Any) -> Any:
        """Порядок: overrides профиля → атрибут стратегии (как при __init__ / в тестах) → app_config."""
        fk = str(full_key or "").strip()
        if fk and not fk.startswith("processor.") and fk.count(".") == 0:
            fk = f"processor.{fk}"
        short = fk.split(".", 1)[1] if fk.startswith("processor.") else fk
        if short in self._overrides:
            return self._overrides[short]
        if hasattr(strategy, attr):
            return getattr(strategy, attr)
        lookup = fk if fk.startswith("processor.") else f"processor.{short}"
        return self._app_config.get(lookup, default)


def resolve_runtime_profile(
    app_config,
    *,
    brightness: float | None,
    contrast: float | None,
) -> tuple[str | None, dict]:
    """Return active runtime profile name and processor overrides for this frame."""
    if not bool(app_config.get("processor.adaptive_profiles.enabled", False)):
        return None, {}
    try:
        b = None if brightness is None else float(brightness)
        c = None if contrast is None else float(contrast)
    except (TypeError, ValueError):
        return None, {}
    night_below = app_config.get("processor.adaptive_profiles.night.max_brightness")
    night_contrast = app_config.get("processor.adaptive_profiles.night.max_contrast")
    try:
        night_below = float(night_below) if night_below is not None else None
        night_contrast = float(night_contrast) if night_contrast is not None else None
    except (TypeError, ValueError):
        return None, {}
    brightness_ok = night_below is not None and b is not None and b <= night_below
    contrast_ok = night_contrast is not None and c is not None and c <= night_contrast
    if brightness_ok or contrast_ok:
        overrides = app_config.get("processor.adaptive_profiles.night.overrides") or {}
        return "night", dict(overrides) if isinstance(overrides, Mapping) else {}
    return None, {}


def light_gate_allows_frame(
    *,
    brightness: float | None,
    contrast: float | None,
    base_has_sufficient_light: bool,
    profile_overrides: Mapping[str, Any] | None = None,
) -> bool:
    """Evaluate frame light with optional lower thresholds from active profile."""
    if base_has_sufficient_light:
        return True
    overrides = dict(profile_overrides or {})
    try:
        min_brightness = float(overrides["light_gate_min_brightness"])
        min_contrast = float(overrides["light_gate_min_contrast"])
    except (KeyError, TypeError, ValueError):
        return False
    try:
        b = float(brightness) if brightness is not None else None
        c = float(contrast) if contrast is not None else None
    except (TypeError, ValueError):
        return False
    if b is None or c is None:
        return False
    return b >= min_brightness and c >= min_contrast


def resolve_openvino_tuning(
    app_config,
    *,
    profile_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Resolve OpenVINO tuning with optional profile-time overrides.

    Keys:
    - profile: latency|throughput
    - num_requests: 0(auto) or >=1
    - model_cache_enabled: bool
    """
    overrides = dict(profile_overrides or {})
    profile = str(overrides.get("openvino_profile") or app_config.get("processor.openvino.profile") or "latency")
    profile = profile.strip().lower()
    if profile not in {"latency", "throughput"}:
        profile = "latency"
    raw_nr = overrides.get("openvino_num_requests")
    if raw_nr is None:
        raw_nr = app_config.get("processor.openvino.num_requests")
    try:
        num_requests = max(0, int(raw_nr or 0))
    except (TypeError, ValueError):
        num_requests = 0
    raw_cache = overrides.get("openvino_model_cache_enabled")
    if raw_cache is None:
        raw_cache = app_config.get("processor.openvino.model_cache_enabled", True)
    model_cache_enabled = bool(raw_cache)
    return {
        "profile": profile,
        "num_requests": num_requests,
        "model_cache_enabled": model_cache_enabled,
    }
