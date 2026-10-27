"""Load a gosom/google-maps-scraper export into public.fire_stations.

Keeps only real fire stations (not extinguisher shops, safety consultants, …)
located in Gujarat, de-duplicates on Google place id, and upserts — so re-running
after a fresh scrape updates existing rows instead of duplicating them.

    # from backend/
    python scripts/fire_stations/import_fire_stations.py <export.csv> --dry-run
    python scripts/fire_stations/import_fire_stations.py <export.csv>

where <export.csv> is scripts/fire_stations/output/gujarat_fire_stations.csv.

--dry-run writes output/cleaned_fire_stations.csv for review and touches nothing.
Accepts the scraper's CSV or JSON (-json, one object per line) output.
"""

import argparse
import asyncio
import csv
import difflib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

# Loose box around Gujarat; the address must also say Gujarat.
GUJARAT_LAT = (20.0, 24.8)
GUJARAT_LNG = (68.0, 74.6)

_STATION_WORDS = ("fire station", "fire brigade", "fire department", "fire service", "agnishaman")
_STATION_NAME_WORDS = _STATION_WORDS + ("fire headquarter", "fire force", "fire & emergency")
# Categories that mention "fire" but are businesses, not stations.
_NOT_STATION_WORDS = (
    "supplier", "equipment", "extinguisher", "protection", "safety", "contractor",
    "consultant", "training", "store", "shop", "dealer", "manufacturer", "service provider",
    "alarm", "hydrant", "sprinkler", "fireworks", "fire pit", "restaurant",
)
# Google often files real stations under "Government office", "Building", etc., so a
# clear station name is trusted, unless the category says it's something else...
_NAMED_STATION_BAD_CATEGORIES = (
    "supplier", "equipment", "extinguisher", "contractor", "consultant", "training",
    "academy", "store", "shop", "dealer", "manufacturer", "fireworks", "restaurant",
    "bus ", "bus stop", "bus station", "train", "transportation", "home stay", "hotel",
    "condominium", "housing society", "garden", "park", "auto repair", "school",
)
# ...or the name is a landmark named after a station.
_LANDMARK_NAME_WORDS = (
    "circle", "chowk", "garden", "near ", "nr.", "nr ", "opp.", "proposed", "ni same",
    "bus stop", "academy", "training",
)
# Even under a "Fire station" category, the name must look like one: Google users
# mis-tag cremation grounds, factories, offices. Gujarat calls some stations
# "Emergency Response Centre"; ફાયર / અગ્નિ = fire in Gujarati.
_STATION_NAME_HINTS = ("fire", "brigade", "agnishaman", "emergency response", "ફાયર", "અગ્નિ")
# Two listings closer than this, with similar or generic names, are one station
# listed twice. Distinct stations can sit this close, so names must agree too.
_DUPLICATE_RADIUS_KM = 0.15
_GENERIC_NAMES = {"fire station", "fire brigade", "main fire station", "fire station office"}


def read_rows(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    stripped = text.lstrip()
    if stripped.startswith("[") or stripped.startswith("{"):
        if stripped.startswith("["):
            return json.loads(stripped)
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    csv.field_size_limit(sys.maxsize)
    return list(csv.DictReader(text.splitlines()))


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _categories(row: Dict[str, Any]) -> str:
    cats = row.get("categories")
    if isinstance(cats, list):
        cats = ", ".join(str(c) for c in cats)
    return f"{row.get('category') or ''} {cats or ''}".lower()


def is_fire_station(row: Dict[str, Any]) -> bool:
    cats = _categories(row)
    title = (row.get("title") or "").lower()
    if not any(w in title for w in _STATION_NAME_HINTS):
        return False
    if any(w in cats for w in _STATION_WORDS) and not any(w in cats for w in _NOT_STATION_WORDS):
        return True
    return (
        any(w in title for w in _STATION_NAME_WORDS)
        and not any(w in title for w in _LANDMARK_NAME_WORDS)
        and not any(w in cats for w in _NAMED_STATION_BAD_CATEGORIES)
    )


def is_in_gujarat(row: Dict[str, Any], lat: float, lng: float) -> bool:
    if not (GUJARAT_LAT[0] <= lat <= GUJARAT_LAT[1] and GUJARAT_LNG[0] <= lng <= GUJARAT_LNG[1]):
        return False
    state = (_as_dict(row.get("complete_address")).get("state") or "").lower()
    if state:
        return "gujarat" in state
    return "gujarat" in (row.get("address") or "").lower()


def to_station(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one scraper row to a fire_stations row, or None if it doesn't belong."""
    name = _clean(row.get("title"))
    lat = _as_float(row.get("latitude"))
    # older gosom versions spell it "longtitude"
    lng = _as_float(row.get("longitude", row.get("longtitude")))
    if not name or lat is None or lng is None:
        return None
    # "Closed" alone means closed right now (opening hours); only skip shut-down places.
    status = (row.get("status") or "").lower()
    if "permanently" in status or "temporarily" in status:
        return None
    if not is_fire_station(row) or not is_in_gujarat(row, lat, lng):
        return None

    addr = _as_dict(row.get("complete_address"))
    place_id = (
        _clean(row.get("place_id"))
        or _clean(row.get("data_id"))
        or _clean(row.get("cid"))
        or f"{name.lower()}@{lat:.4f},{lng:.4f}"
    )
    return {
        "place_id": place_id,
        "name": name[:200],
        "address": _clean(row.get("address")),
        "city": _clean(addr.get("city")),
        "postal_code": _clean(addr.get("postal_code")),
        "state": "Gujarat",
        "phone": _clean(row.get("phone")),
        "latitude": lat,
        "longitude": lng,
        "google_maps_url": _clean(row.get("link")),
        "source": "google_maps",
    }


def _distance_km(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a["latitude"], a["longitude"], b["latitude"], b["longitude"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _is_duplicate(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    if a["place_id"] == b["place_id"]:
        return True
    if _distance_km(a, b) >= _DUPLICATE_RADIUS_KM:
        return False
    name_a, name_b = a["name"].lower().strip(), b["name"].lower().strip()
    if name_a in _GENERIC_NAMES or name_b in _GENERIC_NAMES:
        return True
    return difflib.SequenceMatcher(None, name_a, name_b).ratio() >= 0.6


def _filled(station: Dict[str, Any]) -> int:
    return sum(v is not None for v in station.values())


def clean_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for row in rows:
        station = to_station(row)
        if station is None:
            continue
        # Same place from several queries, or listed twice on Maps: keep the
        # copy with the most filled fields.
        dup = next((i for i, k in enumerate(kept) if _is_duplicate(k, station)), None)
        if dup is None:
            kept.append(station)
        elif _filled(station) > _filled(kept[dup]):
            kept[dup] = station
    return sorted(kept, key=lambda s: (s["city"] or "", s["name"]))


async def upsert(stations: List[Dict[str, Any]]) -> int:
    os.chdir(BACKEND_DIR)  # config.json is read relative to cwd
    from app.data_layer.database_manager import DatabaseManager
    from app.data_layer.supabase_credentials import resolve_supabase_url

    key, is_service_role = DatabaseManager.resolve_server_supabase_key()
    if not is_service_role:
        print("WARNING: no service-role key configured; RLS will likely block the insert.")
    await DatabaseManager.initialize(resolve_supabase_url("database"), key)
    manager = DatabaseManager.get_instance()
    try:
        assert manager.fire_stations is not None
        return await manager.fire_stations.upsert_by_place_id(stations)
    finally:
        await manager.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("export", type=Path, help="CSV or JSON file from google-maps-scraper")
    parser.add_argument("--dry-run", action="store_true", help="only write the cleaned CSV")
    args = parser.parse_args()

    rows = read_rows(args.export)
    stations = clean_rows(rows)
    print(f"{len(rows)} scraped rows -> {len(stations)} Gujarat fire stations")

    out = Path(__file__).parent / "output" / "cleaned_fire_stations.csv"
    out.parent.mkdir(exist_ok=True)
    if stations:
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(stations[0].keys()))
            writer.writeheader()
            writer.writerows(stations)
        print(f"Cleaned list: {out}")

    if args.dry_run or not stations:
        return
    written = asyncio.run(upsert(stations))
    print(f"Upserted {written} rows into fire_stations")


if __name__ == "__main__":
    main()
