import math

EARTH_RADIUS_MILES = 3959.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(max(0.0, a)))


def compute_cumulative_distances(coords: list) -> list:
    """coords: list of [lon, lat]. Returns cumulative miles from start."""
    distances = [0.0]
    for i in range(1, len(coords)):
        lon1, lat1 = coords[i - 1]
        lon2, lat2 = coords[i]
        distances.append(distances[-1] + haversine(lat1, lon1, lat2, lon2))
    return distances


def find_stations_near_route(
    route_coords: list,
    cumulative_dists: list,
    stations: list,
    max_off_route_miles: float = 5.0,
) -> list:
    """
    Returns stations within max_off_route_miles of the route,
    annotated with dist_from_start along the route.

    Uses a bounding-box pre-filter to eliminate irrelevant stations fast,
    then samples the route to ~500 points so the inner loop stays small.
    """
    if not stations or not route_coords:
        return []

    route_lats = [c[1] for c in route_coords]
    route_lons = [c[0] for c in route_coords]

    # Bounding box of the route + buffer
    buf = max_off_route_miles / 55.0
    min_lat = min(route_lats) - buf
    max_lat = max(route_lats) + buf
    min_lon = min(route_lons) - buf
    max_lon = max(route_lons) + buf

    # Sample route to at most 500 points for speed
    n = len(route_coords)
    step = max(1, n // 500)
    sampled = list(range(0, n, step))
    if sampled[-1] != n - 1:
        sampled.append(n - 1)

    result = []
    for station in stations:
        slat = station['lat']
        slon = station['lon']

        # Fast bounding-box reject — skips ~90% of stations on a typical route
        if not (min_lat <= slat <= max_lat and min_lon <= slon <= max_lon):
            continue

        cos_slat = math.cos(math.radians(slat))
        best_dist = float('inf')
        best_idx = 0

        for i in sampled:
            dlat = math.radians(route_lats[i] - slat)
            dlon = math.radians(route_lons[i] - slon)
            a = (math.sin(dlat / 2) ** 2 +
                 cos_slat * math.cos(math.radians(route_lats[i])) *
                 math.sin(dlon / 2) ** 2)
            d = 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(max(0.0, a)))
            if d < best_dist:
                best_dist = d
                best_idx = i

        if best_dist <= max_off_route_miles:
            result.append({
                **station,
                'dist_from_start': cumulative_dists[best_idx],
                'off_route_miles': round(best_dist, 2),
            })

    return sorted(result, key=lambda x: x['dist_from_start'])
