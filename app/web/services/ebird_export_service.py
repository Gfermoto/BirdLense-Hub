"""eBird Record Format export for BirdLense species visits.

Порядок колонок по официальному шаблону eBird (support.ebird.org):
1 Common Name, 2 Genus, 3 Species, 4 Number, 5 Species Comments,
6 Location Name, 7 Latitude, 8 Longitude, 9 Date, 10 Start Time,
11 State/Province, 12 Country Code, 13 Protocol, 14 Number of Observers,
15 Duration, 16 All observations reported?, 17 Effort Distance Miles,
18 Effort area acres, 19 Submission Comments
"""
import csv
import io
from datetime import datetime

from app_config.app_config import app_config

from services.ebird_util import REGION_NAME_TO_CODE, common_name_from_species


def build_ebird_csv(
    rows: list[dict],
    start_dt: datetime,
    end_dt: datetime,
) -> str:
    """Build CSV in eBird Record Format. Порядок колонок — по официальному шаблону."""
    country = (app_config.get("ebird.country") or "").strip().upper() or "US"
    state_raw = (app_config.get("ebird.state") or "").strip()
    state = REGION_NAME_TO_CODE.get(state_raw.lower()) or (state_raw.upper()[:3] if state_raw else "")
    location = (app_config.get("ebird.location_name") or "").strip() or "BirdLense Feeder"
    lat = app_config.get("secrets.latitude") or ""
    lon = app_config.get("secrets.longitude") or ""
    protocol_raw = (app_config.get("ebird.protocol") or "Stationary").strip()
    protocol = protocol_raw.lower() if protocol_raw else "stationary"

    first_date = start_dt.strftime("%m/%d/%Y")
    hour = start_dt.hour % 12 or 12
    am_pm = "AM" if start_dt.hour < 12 else "PM"
    first_time = f"{hour}:{start_dt.strftime('%M')} {am_pm}"

    duration_min = int((end_dt - start_dt).total_seconds() / 60) if end_dt > start_dt else 1440

    def _lat_lon(val) -> str:
        s = str(val).replace(",", ".").strip()
        return s if s else ""

    output = io.StringIO()
    w = csv.writer(output, lineterminator="\n")

    for r in rows:
        common_name = common_name_from_species(r.get("species_name", ""))
        if not common_name:
            continue
        w.writerow([
            common_name,       # 1 Common Name
            "",               # 2 Genus
            "",               # 3 Species
            "X",              # 4 Number (present)
            "",               # 5 Species Comments
            location,         # 6 Location Name
            _lat_lon(lat),     # 7 Latitude
            _lat_lon(lon),     # 8 Longitude
            first_date,        # 9 Date (MM/DD/YYYY)
            first_time,        # 10 Start Time (8:00 AM or 14:50)
            state,             # 11 State/Province
            country[:2],       # 12 Country Code
            protocol,          # 13 Protocol
            1,                 # 14 Number of Observers
            duration_min,      # 15 Duration (minutes)
            "Y",               # 16 All observations reported?
            "",               # 17 Effort Distance Miles (stationary = empty)
            "",               # 18 Effort area acres
            "",               # 19 Submission Comments
        ])

    return output.getvalue()
