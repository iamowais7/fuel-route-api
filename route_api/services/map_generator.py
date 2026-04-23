import json


def generate_map_html(
    coords: list,
    fuel_stops: list,
    start: tuple,
    finish: tuple,
) -> str:
    """
    Returns a self-contained Leaflet HTML page string.
    coords: [[lon, lat], ...]  (OSRM format — Leaflet needs [lat, lon])
    start/finish: (lat, lon, label)
    """
    # Leaflet expects [lat, lon]
    route_latlng = [[c[1], c[0]] for c in coords]

    stops_data = [
        {
            'lat': s['lat'],
            'lon': s['lon'],
            'name': s['name'],
            'city': s['city'],
            'state': s['state'],
            'price': round(s['price'], 3),
            'gallons': round(s['gallons'], 2),
            'cost': round(s['cost'], 2),
            'dist': round(s['dist_from_start'], 1),
        }
        for s in fuel_stops
    ]

    s_lat, s_lon, s_label = start
    f_lat, f_lon, f_label = finish
    total_cost = sum(s['cost'] for s in fuel_stops)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Fuel Route — {s_label} → {f_label}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', sans-serif; display: flex; height: 100vh; }}
    #sidebar {{
      width: 320px; min-width: 280px; background: #1a1a2e; color: #eee;
      display: flex; flex-direction: column; overflow-y: auto; z-index: 1000;
    }}
    #sidebar h1 {{ font-size: 1rem; padding: 16px; background: #16213e; border-bottom: 1px solid #0f3460; }}
    #sidebar h1 span {{ color: #e94560; }}
    .summary {{ padding: 12px 16px; background: #16213e; margin: 8px; border-radius: 8px; font-size: 0.85rem; }}
    .summary .big {{ font-size: 1.8rem; font-weight: 700; color: #e94560; }}
    .summary .label {{ color: #aaa; font-size: 0.75rem; }}
    .stops-header {{ padding: 8px 16px; color: #aaa; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; }}
    .stop-card {{
      margin: 4px 8px; padding: 10px 12px; background: #16213e;
      border-radius: 8px; cursor: pointer; border-left: 3px solid #e94560;
      transition: background 0.15s;
    }}
    .stop-card:hover {{ background: #0f3460; }}
    .stop-card .stop-num {{ font-size: 0.7rem; color: #e94560; font-weight: 700; }}
    .stop-card .stop-name {{ font-size: 0.9rem; font-weight: 600; }}
    .stop-card .stop-meta {{ font-size: 0.78rem; color: #aaa; margin-top: 2px; }}
    .stop-card .stop-cost {{ font-size: 0.85rem; color: #4ecca3; font-weight: 600; }}
    #map {{ flex: 1; }}
    .leaflet-popup-content {{ font-family: 'Segoe UI', sans-serif; font-size: 13px; min-width: 180px; }}
    .popup-title {{ font-weight: 700; font-size: 14px; margin-bottom: 4px; }}
    .popup-row {{ display: flex; justify-content: space-between; margin: 2px 0; }}
    .popup-label {{ color: #666; }}
    .popup-value {{ font-weight: 600; }}
  </style>
</head>
<body>
  <div id="sidebar">
    <h1>Fuel Route<br/><span>{s_label}</span><br/>→ <span>{f_label}</span></h1>
    <div class="summary">
      <div class="big">${total_cost:.2f}</div>
      <div class="label">Total Fuel Cost</div>
      <br/>
      <div style="display:flex;gap:16px">
        <div>
          <div style="font-weight:600">{len(fuel_stops)}</div>
          <div class="label">Stops</div>
        </div>
        <div>
          <div style="font-weight:600">{sum(s['gallons'] for s in fuel_stops):.1f} gal</div>
          <div class="label">Total Gallons</div>
        </div>
      </div>
    </div>
    <div class="stops-header">Fuel Stops</div>
    {''.join(f"""
    <div class="stop-card" onclick="flyToStop({i})">
      <div class="stop-num">STOP {i+1} · {s['dist']:.0f} mi from start</div>
      <div class="stop-name">{s['name']}</div>
      <div class="stop-meta">{s['city']}, {s['state']}</div>
      <div class="stop-meta">${s['price']:.3f}/gal · {s['gallons']:.1f} gal</div>
      <div class="stop-cost">${s['cost']:.2f}</div>
    </div>""" for i, s in enumerate(stops_data))}
  </div>
  <div id="map"></div>
  <script>
    var map = L.map('map');
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }}).addTo(map);

    var routeCoords = {json.dumps(route_latlng)};
    var routeLine = L.polyline(routeCoords, {{color: '#4ecca3', weight: 4, opacity: 0.85}}).addTo(map);
    map.fitBounds(routeLine.getBounds(), {{padding: [20, 20]}});

    // Start marker
    L.marker([{s_lat}, {s_lon}], {{
      icon: L.divIcon({{
        html: '<div style="background:#4ecca3;color:#1a1a2e;border-radius:50%;width:28px;height:28px;text-align:center;line-height:28px;font-weight:900;font-size:14px;border:2px solid white">S</div>',
        iconSize:[28,28], iconAnchor:[14,14]
      }})
    }}).addTo(map).bindPopup('<div class="popup-title">START</div>{s_label}');

    // Finish marker
    L.marker([{f_lat}, {f_lon}], {{
      icon: L.divIcon({{
        html: '<div style="background:#e94560;color:white;border-radius:50%;width:28px;height:28px;text-align:center;line-height:28px;font-weight:900;font-size:14px;border:2px solid white">F</div>',
        iconSize:[28,28], iconAnchor:[14,14]
      }})
    }}).addTo(map).bindPopup('<div class="popup-title">FINISH</div>{f_label}');

    var stops = {json.dumps(stops_data)};
    var stopMarkers = stops.map(function(s, i) {{
      var m = L.marker([s.lat, s.lon], {{
        icon: L.divIcon({{
          html: '<div style="background:#e94560;color:white;border-radius:50%;width:26px;height:26px;text-align:center;line-height:26px;font-weight:700;font-size:12px;border:2px solid white">' + (i+1) + '</div>',
          iconSize:[26,26], iconAnchor:[13,13]
        }})
      }}).addTo(map);
      m.bindPopup(
        '<div class="popup-title">Stop ' + (i+1) + ': ' + s.name + '</div>' +
        '<div class="popup-row"><span class="popup-label">Location</span><span class="popup-value">' + s.city + ', ' + s.state + '</span></div>' +
        '<div class="popup-row"><span class="popup-label">Price</span><span class="popup-value">$' + s.price.toFixed(3) + '/gal</span></div>' +
        '<div class="popup-row"><span class="popup-label">Purchased</span><span class="popup-value">' + s.gallons.toFixed(2) + ' gal</span></div>' +
        '<div class="popup-row"><span class="popup-label">Cost</span><span class="popup-value" style="color:#e94560">$' + s.cost.toFixed(2) + '</span></div>' +
        '<div class="popup-row"><span class="popup-label">Mile marker</span><span class="popup-value">' + s.dist.toFixed(0) + ' mi</span></div>'
      );
      return m;
    }});

    function flyToStop(i) {{
      var s = stops[i];
      map.flyTo([s.lat, s.lon], 12, {{duration: 1}});
      stopMarkers[i].openPopup();
    }}
  </script>
</body>
</html>"""
