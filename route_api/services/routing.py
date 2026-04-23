import requests
from functools import lru_cache

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "http://router.project-osrm.org/route/v1/driving"
HEADERS = {"User-Agent": "FuelRouteOptimizer/1.0 (fuel-route-api)"}


@lru_cache(maxsize=512)
def geocode(location: str) -> tuple:
    """Returns (lat, lon, display_name). Cached to avoid repeated lookups."""
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": location, "format": "json", "limit": 1, "countrycodes": "us"},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"Location not found within the USA: '{location}'")
    item = data[0]
    return float(item['lat']), float(item['lon']), item['display_name']


def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict:
    """
    Single OSRM call returning route geometry (list of [lon, lat]),
    distance in meters, and duration in seconds.
    """
    coords = f"{start_lon},{start_lat};{end_lon},{end_lat}"
    resp = requests.get(
        f"{OSRM_URL}/{coords}",
        params={"overview": "full", "geometries": "geojson", "steps": "false"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get('code') != 'Ok':
        raise ValueError(f"Routing error: {data.get('message', 'Unknown OSRM error')}")

    route = data['routes'][0]
    return {
        'distance_meters': route['distance'],
        'duration_seconds': route['duration'],
        'geometry': route['geometry']['coordinates'],  # [[lon, lat], ...]
    }
