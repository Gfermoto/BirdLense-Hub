"""RC4 protocol surfaces — Frigate/Hub as optional priors, not product SoT.

Structural typing only (like ``interfaces.DetectionStrategyProtocol``).
Install code may satisfy these without inheriting.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class TriggerSource(Protocol):
    """Motion / event trigger that starts a recording session."""

    name: str

    def poll(self) -> Mapping[str, Any] | None:
        """Return trigger event dict or None when idle."""
        ...


@runtime_checkable
class BoxProvider(Protocol):
    """Bounding-box evidence for a time window (Hub YOLO or external)."""

    name: str

    def boxes_for_window(
        self,
        *,
        start_time: Any,
        end_time: Any,
        camera_id: str | None = None,
    ) -> list[Mapping[str, Any]]: ...


@runtime_checkable
class SpeciesHint(Protocol):
    """Non-authoritative species prior (MQTT/Frigate/BirdNET). Never a go-metric alone."""

    name: str

    def hints_for_window(
        self,
        *,
        start_time: Any,
        end_time: Any,
        camera_id: str | None = None,
    ) -> list[Mapping[str, Any]]: ...


@runtime_checkable
class SpeciesAuthority(Protocol):
    """Optional named-species authority. Hub classifier is the default authority."""

    name: str

    def may_accept_named(self, row: Mapping[str, Any]) -> bool: ...


def hub_is_species_authority(app_config: Any) -> bool:
    """Product default: Hub taxonomy wins; Frigate authority is opt-in."""
    try:
        from visit_contract import frigate_species_authority

        return not bool(frigate_species_authority(app_config))
    except Exception:
        return True
