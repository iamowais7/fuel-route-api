import csv
import json
import os
import time
import requests
from pathlib import Path

US_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
    'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
    'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
    'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
    'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY',
}

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
PROCESSED_CSV = DATA_DIR / 'fuel_prices_processed.csv'
GEOCODE_CACHE_FILE = DATA_DIR / 'geocode_cache.json'
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "FuelRouteOptimizer/1.0"}

_stations: list = []
_geocode_cache: dict = {}


def preload_stations() -> None:
    global _stations
    raw_csv = os.environ.get('FUEL_PRICES_CSV', str(DATA_DIR / 'fuel_prices.csv'))

    if PROCESSED_CSV.exists():
        _stations = _load_processed_csv(str(PROCESSED_CSV))
        print(f"[stations] Loaded {len(_stations)} stations from pre-processed CSV.")
    elif Path(raw_csv).exists():
        raw = _load_opis_csv(raw_csv)
        print(f"[stations] Loaded {len(raw)} raw stations. Geocode cache will be used at request time.")
        _stations = raw  # no coords yet; fuel_optimizer will geocode on demand
    else:
        print(f"[stations] WARNING: No fuel prices CSV found at {raw_csv}")


def get_stations() -> list:
    if not _stations:
        preload_stations()
    return _stations


def _load_processed_csv(path: str) -> list:
    stations = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                stations.append({
                    'id': row['id'],
                    'name': row['name'],
                    'address': row.get('address', ''),
                    'city': row['city'],
                    'state': row['state'],
                    'lat': float(row['lat']),
                    'lon': float(row['lon']),
                    'price': float(row['price']),
                })
            except (ValueError, KeyError):
                continue
    return stations


def _load_opis_csv(path: str) -> list:
    """Load OPIS-format CSV (no lat/lon). Deduplicate by station ID keeping min price."""
    station_min: dict = {}

    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                state = row.get('State', '').strip()
                if state not in US_STATES:
                    continue

                station_id = row.get('OPIS Truckstop ID', '').strip()
                price = float(row.get('Retail Price', '0').strip())
                if not station_id or price <= 0:
                    continue

                city = row.get('City', '').strip()

                if station_id not in station_min or price < station_min[station_id]['price']:
                    station_min[station_id] = {
                        'id': station_id,
                        'name': row.get('Truckstop Name', 'Fuel Stop').strip(),
                        'address': row.get('Address', '').strip(),
                        'city': city,
                        'state': state,
                        'price': price,
                    }
            except (ValueError, KeyError):
                continue

    return list(station_min.values())


# --- Geocoding helpers (used at request time for OPIS-only CSV) ---

def _load_geocode_cache() -> dict:
    global _geocode_cache
    if not _geocode_cache and GEOCODE_CACHE_FILE.exists():
        with open(GEOCODE_CACHE_FILE) as f:
            _geocode_cache = json.load(f)
    return _geocode_cache


def _save_geocode_cache() -> None:
    with open(GEOCODE_CACHE_FILE, 'w') as f:
        json.dump(_geocode_cache, f)


def geocode_city_state(city: str, state: str) -> tuple | None:
    cache = _load_geocode_cache()
    key = f"{city.strip()}, {state.strip()}"

    if key in cache:
        v = cache[key]
        return tuple(v) if v else None

    time.sleep(1.1)  # Nominatim: max 1 req/s
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": f"{city}, {state}, USA", "format": "json", "limit": 1, "countrycodes": "us"},
            headers=HEADERS,
            timeout=10,
        )
        data = resp.json()
        if data:
            result = [float(data[0]['lat']), float(data[0]['lon'])]
            cache[key] = result
            _save_geocode_cache()
            return tuple(result)
    except Exception:
        pass

    cache[key] = None
    _save_geocode_cache()
    return None


def attach_coords_for_states(stations: list, states: set) -> list:
    """
    For raw OPIS stations (no lat/lon), geocode unique city/state pairs
    for the given set of states and return stations that got coordinates.
    """
    # Only process relevant states
    relevant = [s for s in stations if s.get('state') in states]

    result = []
    for s in relevant:
        if 'lat' in s and 'lon' in s:
            result.append(s)
            continue
        coords = geocode_city_state(s['city'], s['state'])
        if coords:
            result.append({**s, 'lat': coords[0], 'lon': coords[1]})

    return result
