"""
Fuel route optimizer.

Algorithm: greedy one-pass with look-ahead.
  - Start with a full tank (500-mile range).
  - At each candidate station (sorted by dist_from_start):
      * If we can reach the destination on current fuel → skip.
      * Else find the next cheaper station within tank range:
          - If found → fill just enough to reach it.
          - If not found → fill up completely (no point saving for costlier fuel ahead).
"""

from django.conf import settings

from .routing import geocode, get_route
from .geo_utils import compute_cumulative_distances, find_stations_near_route
from .station_loader import get_stations, attach_coords_for_states
from .map_generator import generate_map_html

METERS_TO_MILES = 0.000621371

# Approximate bounding boxes (min_lat, max_lat, min_lon, max_lon) per state.
# Used to determine which states a route passes through when stations lack coords.
_STATE_BOUNDS = {
    'AL': (30.14, 35.01, -88.47, -84.89), 'AZ': (31.33, 37.00, -114.82, -109.04),
    'AR': (33.00, 36.50, -94.62, -89.64), 'CA': (32.53, 42.01, -124.41, -114.13),
    'CO': (36.99, 41.00, -109.06, -102.04), 'CT': (40.95, 42.05, -73.73, -71.79),
    'DE': (38.45, 39.84, -75.79, -75.05), 'FL': (24.52, 31.00, -87.63, -80.03),
    'GA': (30.36, 35.00, -85.61, -80.84), 'HI': (18.91, 22.24, -160.25, -154.81),
    'ID': (41.99, 49.00, -117.24, -111.04), 'IL': (36.97, 42.51, -91.51, -87.02),
    'IN': (37.77, 41.76, -88.10, -84.78), 'IA': (40.38, 43.50, -96.64, -90.14),
    'KS': (36.99, 40.00, -102.05, -94.59), 'KY': (36.50, 39.15, -89.57, -81.96),
    'LA': (28.92, 33.02, -94.04, -88.82), 'ME': (43.06, 47.46, -71.08, -66.95),
    'MD': (37.89, 39.72, -79.49, -75.05), 'MA': (41.24, 42.89, -73.51, -69.93),
    'MI': (41.70, 48.30, -90.42, -82.42), 'MN': (43.50, 49.38, -97.24, -89.49),
    'MS': (30.17, 35.01, -91.65, -88.10), 'MO': (35.99, 40.61, -95.77, -89.10),
    'MT': (44.36, 49.00, -116.05, -104.04), 'NE': (39.99, 43.00, -104.06, -95.31),
    'NV': (35.00, 42.00, -120.01, -114.04), 'NH': (42.70, 45.31, -72.56, -70.61),
    'NJ': (38.93, 41.36, -75.56, -73.90), 'NM': (31.33, 37.00, -109.05, -103.00),
    'NY': (40.50, 45.02, -79.76, -71.86), 'NC': (33.84, 36.59, -84.32, -75.46),
    'ND': (45.94, 49.00, -104.05, -96.56), 'OH': (38.40, 42.33, -84.82, -80.52),
    'OK': (33.62, 37.00, -103.00, -94.43), 'OR': (41.99, 46.26, -124.57, -116.46),
    'PA': (39.72, 42.27, -80.52, -74.69), 'RI': (41.15, 42.02, -71.91, -71.12),
    'SC': (32.04, 35.22, -83.35, -78.54), 'SD': (42.50, 45.94, -104.06, -96.44),
    'TN': (34.98, 36.68, -90.31, -81.65), 'TX': (25.84, 36.50, -106.65, -93.51),
    'UT': (36.99, 42.00, -114.05, -109.04), 'VT': (42.73, 45.02, -73.44, -71.50),
    'VA': (36.54, 39.47, -83.68, -75.24), 'WA': (45.54, 49.00, -124.73, -116.92),
    'WV': (37.20, 40.64, -82.64, -77.72), 'WI': (42.49, 47.08, -92.89, -86.25),
    'WY': (40.99, 45.01, -111.06, -104.05),
}


def optimize_route(start_location: str, finish_location: str) -> dict:
    tank = getattr(settings, 'TANK_CAPACITY_MILES', 500.0)
    mpg = getattr(settings, 'VEHICLE_MPG', 10.0)
    max_detour = getattr(settings, 'MAX_OFF_ROUTE_MILES', 5.0)

    # --- Geocode (2 Nominatim calls, cached after first request) ---
    start_lat, start_lon, start_display = geocode(start_location)
    finish_lat, finish_lon, finish_display = geocode(finish_location)

    # --- Single routing call (OSRM) ---
    route_data = get_route(start_lat, start_lon, finish_lat, finish_lon)

    coords = route_data['geometry']
    total_miles = route_data['distance_meters'] * METERS_TO_MILES
    total_hours = route_data['duration_seconds'] / 3600.0

    cum_dists = compute_cumulative_distances(coords)
    all_stations = get_stations()

    # If stations lack coordinates (raw OPIS CSV), geocode only route-relevant states.
    if all_stations and 'lat' not in all_stations[0]:
        route_states = _states_along_route(coords)
        all_stations = attach_coords_for_states(all_stations, route_states)

    # --- Find stations near the route ---
    nearby = find_stations_near_route(coords, cum_dists, all_stations, max_detour)

    # --- Optimize fuel stops ---
    fuel_stops, total_cost = _find_optimal_stops(nearby, total_miles, tank, mpg)

    # --- Build response ---
    total_gallons = sum(s['gallons'] for s in fuel_stops)
    avg_price = total_cost / total_gallons if total_gallons else 0.0

    map_html = generate_map_html(
        coords=coords,
        fuel_stops=fuel_stops,
        start=(start_lat, start_lon, start_location),
        finish=(finish_lat, finish_lon, finish_location),
    )

    return {
        'route': {
            'start': start_location,
            'finish': finish_location,
            'start_coords': {'lat': round(start_lat, 6), 'lon': round(start_lon, 6)},
            'finish_coords': {'lat': round(finish_lat, 6), 'lon': round(finish_lon, 6)},
            'total_distance_miles': round(total_miles, 1),
            'estimated_drive_hours': round(total_hours, 1),
        },
        'fuel_stops': [
            {
                'stop_number': i + 1,
                'name': s['name'],
                'city': s['city'],
                'state': s['state'],
                'lat': s['lat'],
                'lon': s['lon'],
                'price_per_gallon': round(s['price'], 3),
                'gallons_purchased': round(s['gallons'], 2),
                'stop_cost_usd': round(s['cost'], 2),
                'miles_from_start': round(s['dist_from_start'], 1),
            }
            for i, s in enumerate(fuel_stops)
        ],
        'summary': {
            'total_fuel_cost_usd': round(total_cost, 2),
            'total_gallons_purchased': round(total_gallons, 2),
            'number_of_stops': len(fuel_stops),
            'avg_price_per_gallon': round(avg_price, 3),
            'vehicle_range_miles': tank,
            'vehicle_mpg': mpg,
        },
        'map_html': map_html,
        'geojson': _build_geojson(coords, fuel_stops, start_lat, start_lon, finish_lat, finish_lon),
    }


def _states_along_route(route_coords: list) -> set:
    """
    Return set of US state abbreviations whose bounding boxes overlap the route.
    Uses the route's bounding box expanded by ~1 degree as a fast heuristic.
    """
    lats = [c[1] for c in route_coords]
    lons = [c[0] for c in route_coords]
    min_lat, max_lat = min(lats) - 1.0, max(lats) + 1.0
    min_lon, max_lon = min(lons) - 1.0, max(lons) + 1.0

    states = set()
    for state, (slat_min, slat_max, slon_min, slon_max) in _STATE_BOUNDS.items():
        if slat_max >= min_lat and slat_min <= max_lat and slon_max >= min_lon and slon_min <= max_lon:
            states.add(state)
    return states


def _find_optimal_stops(
    stations: list,
    total_distance: float,
    tank: float,
    mpg: float,
) -> tuple:
    fuel = tank          # start with full tank
    pos = 0.0
    total_cost = 0.0
    stops = []
    n = len(stations)

    for i, station in enumerate(stations):
        travel = station['dist_from_start'] - pos

        if travel < 0:
            continue

        if travel > fuel + 0.5:
            raise ValueError(
                f"No reachable fuel station: gap of {travel:.0f} miles near "
                f"{station.get('city', '?')}, {station.get('state', '?')}. "
                f"Vehicle range is {tank:.0f} miles but only {fuel:.0f} miles of fuel remain."
            )

        fuel -= travel
        pos = station['dist_from_start']

        remaining = total_distance - pos
        if fuel >= remaining:
            continue  # can coast to the finish

        # Look ahead: find first cheaper station reachable from here
        next_cheaper = None
        for j in range(i + 1, n):
            gap = stations[j]['dist_from_start'] - pos
            if gap > tank:
                break
            if stations[j]['price'] < station['price']:
                next_cheaper = stations[j]
                break

        if next_cheaper is not None:
            needed = next_cheaper['dist_from_start'] - pos
            if needed > fuel:
                fill_miles = needed - fuel
                gallons = fill_miles / mpg
                cost = gallons * station['price']
                fuel += fill_miles
                total_cost += cost
                stops.append({**station, 'gallons': gallons, 'cost': cost})
        else:
            fill_miles = tank - fuel
            if fill_miles > 0.1:
                gallons = fill_miles / mpg
                cost = gallons * station['price']
                fuel = tank
                total_cost += cost
                stops.append({**station, 'gallons': gallons, 'cost': cost})

    return stops, total_cost


def _build_geojson(coords, fuel_stops, s_lat, s_lon, f_lat, f_lon):
    features = [
        {
            'type': 'Feature',
            'geometry': {'type': 'LineString', 'coordinates': coords},
            'properties': {'type': 'route'},
        },
        {
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [s_lon, s_lat]},
            'properties': {'type': 'start'},
        },
        {
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [f_lon, f_lat]},
            'properties': {'type': 'finish'},
        },
    ]
    for i, s in enumerate(fuel_stops):
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [s['lon'], s['lat']]},
            'properties': {
                'type': 'fuel_stop',
                'stop_number': i + 1,
                'name': s['name'],
                'city': s['city'],
                'state': s['state'],
                'price_per_gallon': round(s['price'], 3),
                'gallons': round(s['gallons'], 2),
                'cost': round(s['cost'], 2),
            },
        })
    return {'type': 'FeatureCollection', 'features': features}
