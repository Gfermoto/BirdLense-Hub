"""eBird Record Format export for BirdLense species visits."""
import csv
import io
import re
from datetime import datetime, timezone
from app_config.app_config import app_config


def _common_name_from_species(name: str) -> str:
    """Extract common name from 'Scientific (Common)' or return as-is."""
    if not name or not isinstance(name, str):
        return ""
    name = name.strip()
    match = re.search(r"\(([^)]+)\)\s*$", name)
    if match:
        return match.group(1).strip()
    return name


def build_ebird_csv(
    rows: list[dict],
    start_dt: datetime,
    end_dt: datetime,
) -> str:
    """Build CSV in eBird Record Format.
    Each row = one unique species per day. Count = X (present).
    Columns per eBird import: Common Name, Count, Date, Time, Country, State,
    Location, Latitude, Longitude, Protocol, Duration, All Obs.
    No header row (eBird requires first row = data).
    """
    country = (app_config.get("ebird.country") or "").strip() or "US"
    state = (app_config.get("ebird.state") or "").strip() or ""
    location = (app_config.get("ebird.location_name") or "").strip() or "BirdLense Feeder"
    lat = app_config.get("secrets.latitude") or ""
    lon = app_config.get("secrets.longitude") or ""
    protocol = (app_config.get("ebird.protocol") or "Stationary").strip()

    # Use first visit time for the "checklist" time
    first_date = start_dt.strftime("%m/%d/%Y")
    first_time = start_dt.strftime("%H:%M")

    # Duration in minutes (full day = 1440 for Stationary)
    duration_min = int((end_dt - start_dt).total_seconds() / 60) if end_dt > start_dt else 1440

    output = io.StringIO()
    w = csv.writer(output, lineterminator="\n")

    for r in rows:
        common_name = _common_name_from_species(r.get("species_name", ""))
        if not common_name:
            continue
        # eBird: no quotes in data, Count = X for present
        # Column order: Common Name, Scientific (optional), Count, Date, Time,
        # Country, State, Location, Lat, Lon, Protocol, Duration, All Obs
        w.writerow([
            common_name,
            "",  # Scientific name optional
            "X",  # Present, not counted
            first_date,
            first_time,
            country[:2] if len(country) >= 2 else country,
            state[:3] if state else "",
            location,
            str(lat).replace(",", ".") if lat else "",
            str(lon).replace(",", ".") if lon else "",
            protocol,
            str(duration_min),
            "Y",  # All observations reported
        ])

    return output.getvalue()
