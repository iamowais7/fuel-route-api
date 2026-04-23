"""
One-time preprocessing script.

Downloads the free GeoNames US cities database (public domain, ~1 MB),
matches every OPIS station by city+state, and writes fuel_prices_processed.csv.

Run once before starting the Django server:

    python preprocess_stations.py [path/to/fuel-prices.csv]

Takes ~30 seconds (vs ~70 min with Nominatim).
"""

import csv
import io
import sys
import zipfile
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent / 'route_api' / 'data'
PROCESSED_CSV = DATA_DIR / 'fuel_prices_processed.csv'
GEONAMES_URL = "http://download.geonames.org/export/dump/US.zip"

US_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
    'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
    'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
    'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
    'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY',
}

# GeoNames admin1 code → 2-letter state abbreviation
_ADMIN1_TO_STATE = {
    'AL':'AL','AK':'AK','AZ':'AZ','AR':'AR','CA':'CA','CO':'CO','CT':'CT',
    'DE':'DE','FL':'FL','GA':'GA','HI':'HI','ID':'ID','IL':'IL','IN':'IN',
    'IA':'IA','KS':'KS','KY':'KY','LA':'LA','ME':'ME','MD':'MD','MA':'MA',
    'MI':'MI','MN':'MN','MS':'MS','MO':'MO','MT':'MT','NE':'NE','NV':'NV',
    'NH':'NH','NJ':'NJ','NM':'NM','NY':'NY','NC':'NC','ND':'ND','OH':'OH',
    'OK':'OK','OR':'OR','PA':'PA','RI':'RI','SC':'SC','SD':'SD','TN':'TN',
    'TX':'TX','UT':'UT','VT':'VT','VA':'VA','WA':'WA','WV':'WV','WI':'WI',
    'WY':'WY',
}


def download_geonames() -> dict:
    """Returns dict: (city_lower, state) → (lat, lon)."""
    print("Downloading GeoNames US cities database (~25 MB) ...")
    resp = requests.get(GEONAMES_URL, timeout=120, stream=True)
    resp.raise_for_status()

    raw = b""
    downloaded = 0
    for chunk in resp.iter_content(chunk_size=65536):
        raw += chunk
        downloaded += len(chunk)
        mb = downloaded / 1_048_576
        print(f"  {mb:.1f} MB downloaded ...", end="\r")
    print()

    print("Parsing city coordinates ...")
    lookup: dict = {}

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with zf.open("US.txt") as f:
            for line in io.TextIOWrapper(f, encoding='utf-8'):
                parts = line.split('\t')
                if len(parts) < 15:
                    continue
                feature_class = parts[6]   # P = populated place
                feature_code  = parts[7]   # PPL, PPLC, PPLA, PPLA2 …
                if feature_class != 'P':
                    continue
                name    = parts[2].strip()   # ASCII name
                lat     = float(parts[4])
                lon     = float(parts[5])
                admin1  = parts[10].strip()  # state code
                state   = _ADMIN1_TO_STATE.get(admin1)
                if not state:
                    continue
                key = (name.lower(), state)
                # Keep the entry with the largest population (parts[14])
                pop = int(parts[14]) if parts[14].strip().lstrip('-').isdigit() else 0
                if key not in lookup or pop > lookup[key][2]:
                    lookup[key] = (lat, lon, pop)

    # Strip population from final dict
    return {k: (v[0], v[1]) for k, v in lookup.items()}


def load_opis_csv(path: str) -> list:
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
                if station_id not in station_min or price < station_min[station_id]['price']:
                    station_min[station_id] = {
                        'id': station_id,
                        'name': row.get('Truckstop Name', 'Fuel Stop').strip(),
                        'address': row.get('Address', '').strip(),
                        'city': row.get('City', '').strip(),
                        'state': state,
                        'price': price,
                    }
            except (ValueError, KeyError):
                continue
    return list(station_min.values())


def main():
    raw_path = sys.argv[1] if len(sys.argv) > 1 else str(DATA_DIR / 'fuel_prices.csv')

    if not Path(raw_path).exists():
        print(f"ERROR: File not found: {raw_path}")
        sys.exit(1)

    print(f"Loading stations from: {raw_path}")
    stations = load_opis_csv(raw_path)
    print(f"  {len(stations)} unique stations (US only, min price per station)")

    city_coords = download_geonames()
    print(f"  {len(city_coords)} US city records loaded")

    matched, unmatched = 0, 0
    rows = []
    for s in stations:
        key = (s['city'].lower(), s['state'])
        coords = city_coords.get(key)
        if coords:
            rows.append({**s, 'lat': coords[0], 'lon': coords[1]})
            matched += 1
        else:
            unmatched += 1

    DATA_DIR.mkdir(exist_ok=True)
    with open(PROCESSED_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f, fieldnames=['id', 'name', 'address', 'city', 'state', 'lat', 'lon', 'price']
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone!")
    print(f"  Matched: {matched} stations with coordinates")
    print(f"  Skipped: {unmatched} stations (city not found in GeoNames)")
    print(f"  Written: {PROCESSED_CSV}")
    print(f"\nStart the server:  python manage.py runserver")


if __name__ == '__main__':
    main()
