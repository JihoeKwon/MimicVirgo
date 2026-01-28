"""
CADWR Groundwater Monitoring Map
캘리포니아 DWR 지하수 관측점을 지도에 표시하고 클릭 시 상세 정보와 그래프를 보여주는 인터랙티브 맵
- CADWR: 캘리포니아 주 지하수 데이터 (현재 수위 + 시계열)
"""

import plotly.graph_objects as go
import json
from pathlib import Path

from cadwr_gwinfo import (
    get_current_levels,
    get_measurement_history,
    get_sites_with_measurements,
    get_percentile_stats
)

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
STATIC_DIR = SCRIPT_DIR / "static"


def calculate_percentile_class(depth, pct_data):
    """Calculate percentile class based on current depth."""
    if depth is None:
        return None, None

    # Get percentile boundaries (deeper = worse, shallower = better)
    boundaries = [
        (0, pct_data.get('pct_lowest')),    # 0% - worst/deepest
        (10, pct_data.get('pct_10')),
        (25, pct_data.get('pct_25')),
        (50, pct_data.get('pct_50')),
        (75, pct_data.get('pct_75')),
        (90, pct_data.get('pct_90')),
        (100, pct_data.get('pct_highest')),  # 100% - best/shallowest
    ]

    # Filter valid boundaries
    valid = [(p, v) for p, v in boundaries if v is not None]
    if len(valid) < 2:
        return None, None

    # Find which interval the depth falls into
    for i in range(len(valid) - 1):
        p1, v1 = valid[i]      # higher percentile = deeper
        p2, v2 = valid[i + 1]  # lower percentile = shallower

        if v2 <= depth <= v1:
            return f"{p1}-{p2}", (p1 + p2) // 2

    # Edge cases
    if depth > valid[0][1]:  # deeper than worst
        return f"<{valid[0][0]}", 0
    if depth < valid[-1][1]:  # shallower than best
        return f">{valid[-1][0]}", 100

    return None, None


def _load_static_file(filename):
    """Load content from static file."""
    filepath = STATIC_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding='utf-8')
    return ""


def _get_html_template():
    """Generate minimal HTML template."""
    return '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-3.0.0.min.js"></script>
    <style>{css}</style>
</head>
<body>
{plot_div}

<div class="map-controls">
    <button class="map-btn zoom-in" onclick="return zoomIn(event)" title="Zoom In">
        <i class="fas fa-plus"></i>
    </button>
    <button class="map-btn zoom-out" onclick="return zoomOut(event)" title="Zoom Out">
        <i class="fas fa-minus"></i>
    </button>
    <button class="map-btn home" onclick="return goHome(event)" title="Home">
        <i class="fas fa-home"></i>
    </button>
    <button class="map-btn info" onclick="toggleInfo()" title="Info">
        <i class="fas fa-info"></i>
    </button>
</div>

<div class="info-modal" id="infoModal">
    <button class="close-btn" onclick="toggleInfo()">&times;</button>
    <h4>Groundwater Monitoring Map</h4>
    <p><strong>Region:</strong> {region_name}</p>
    <p><strong>Period:</strong> {data_period}</p>
    <p style="margin-top:10px;"><strong>Data Source:</strong></p>
    <p style="font-size:11px;"><span style="color:#4CAF50;">●</span> CA DWR - California state data</p>
    <p style="margin-top:10px; color:#999; font-size:11px;">Click markers for details.</p>
</div>

<div class="popup-overlay" id="popupOverlay" onclick="closeMarkerPopup()"></div>
<div class="marker-popup" id="markerPopup">
    <button class="close-popup" onclick="closeMarkerPopup()">&times;</button>
    <div class="popup-header" id="popupHeader">Site Information</div>
    <div class="popup-body" id="popupBody"></div>
</div>

<div class="scale-bar" id="scaleBar">
    <div class="scale-bar-line" id="scaleBarLine" style="width: 100px;"></div>
    <div class="scale-bar-label" id="scaleBarLabel">1 km</div>
</div>

<div class="loading-overlay" id="loadingOverlay">
    <div class="loading-spinner"></div>
</div>

{layer_panel}

<script>{js}</script>
<script>
    // Initialize map with config
    initMapState({{
        homeLat: {home_lat},
        homeLon: {home_lon},
        homeZoom: {home_zoom},
        timeSeries: {timeseries_json},
        layers: {layers_json}
    }});
</script>
</body>
</html>'''


def _get_layer_panel_html(layers):
    """Generate layer panel HTML."""
    if not layers:
        return ''

    items = []
    for layer in layers:
        layer_id = layer['name']
        items.append(f'''
        <div class="layer-item">
            <input type="checkbox" class="layer-checkbox" id="layer-{layer_id}"
                   checked onchange="toggleLayer('{layer_id}')">
            <label class="layer-label" for="layer-{layer_id}">
                <span class="layer-color" style="background:{layer['color']};"></span>
                {layer.get('label', layer_id)}
                <span class="layer-count">{layer['count']}</span>
            </label>
        </div>''')

    return f'''
<div class="layer-panel" id="layerPanel">
    <h4><i class="fas fa-layer-group" style="margin-right:8px;color:#1976D2;"></i>Data Layers</h4>
    {''.join(items)}
</div>'''


def create_map(title="CADWR Groundwater Monitoring", center_lat=33.0, center_lon=-117.0, zoom=9, relief_opacity=0.3):
    """Create base map with Carto Positron + NASA Shaded Relief."""
    fig = go.Figure()

    maplibre_style = {
        "version": 8,
        "name": "Carto Positron with Shaded Relief",
        "sources": {
            "carto": {
                "type": "raster",
                "tiles": ["https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"],
                "tileSize": 256,
                "maxzoom": 19,
                "attribution": "OpenStreetMap, CARTO"
            },
            "shaded-relief": {
                "type": "raster",
                "tiles": ["https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/ASTER_GDEM_Greyscale_Shaded_Relief/default/GoogleMapsCompatible_Level12/{z}/{y}/{x}.png"],
                "tileSize": 256,
                "maxzoom": 12,
                "attribution": "NASA ASTER GDEM"
            }
        },
        "layers": [
            {"id": "carto-layer", "type": "raster", "source": "carto", "paint": {"raster-opacity": 1.0}},
            {"id": "shaded-relief-layer", "type": "raster", "source": "shaded-relief", "paint": {"raster-opacity": relief_opacity}}
        ]
    }

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color="#333", family="Inter, sans-serif"), x=0.5, xanchor="center"),
        map=dict(style=maplibre_style, center=dict(lat=center_lat, lon=center_lon), zoom=zoom),
        paper_bgcolor="white",
        margin=dict(l=0, r=0, t=50, b=0),
        showlegend=False,
    )

    return fig, center_lat, center_lon, zoom


def add_groundwater_sites(fig, points_data, layer_name="CADWR", size=12, color="#4CAF50",
                          colorscale=None, show_colorbar=False):
    """Add groundwater monitoring points to map."""
    if not points_data:
        return fig

    lats = [p['lat'] for p in points_data]
    lons = [p['lon'] for p in points_data]
    names = [p.get('name', p.get('site_no', '')) for p in points_data]
    changes = [p.get('change', 0) for p in points_data]

    if colorscale and any(c != 0 for c in changes):
        marker = dict(
            size=size,
            color=changes,
            colorscale=colorscale,
            opacity=0.85,
            showscale=show_colorbar,
            cmin=-10 if min(changes) > -10 else min(changes),
            cmax=10 if max(changes) < 10 else max(changes),
            colorbar=dict(
                title=dict(text="Change (ft)", side="top", font=dict(size=10, family="Inter")),
                orientation="h", thickness=10, len=0.15,
                x=0.85, y=0.02, xanchor="center", yanchor="bottom",
                bgcolor="rgba(255,255,255,0.9)", bordercolor="#ddd", borderwidth=1,
                tickfont=dict(size=9, family="Inter"), tickformat=".1f",
            ) if show_colorbar else None,
        )
    else:
        marker = dict(size=size, color=color, opacity=0.85)

    fig.add_trace(go.Scattermap(
        lat=lats, lon=lons, mode='markers', name=layer_name,
        marker=marker, text=names, hoverinfo='text',
        hovertemplate='<b>%{text}</b><br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<br>Click for details<extra></extra>',
        customdata=points_data,
    ))

    return fig


def save_map(fig, filename, home_lat, home_lon, home_zoom, site_timeseries,
             region_name="", data_period="", layers=None):
    """Save map as HTML with controls."""
    if layers is None:
        layers = []

    # Load static files
    css = _load_static_file('mapservice.css')
    js = _load_static_file('mapservice.js')

    # Get plot div with CDN plotly.js (needed for inline script to work)
    plot_html = fig.to_html(include_plotlyjs='cdn', full_html=False)

    # Build HTML
    html = _get_html_template().format(
        title=f"Groundwater Map - {region_name}",
        css=css,
        js=js,
        plot_div=plot_html,
        region_name=region_name,
        data_period=data_period,
        home_lat=home_lat,
        home_lon=home_lon,
        home_zoom=home_zoom,
        timeseries_json=json.dumps(site_timeseries),
        layers_json=json.dumps(layers),
        layer_panel=_get_layer_panel_html(layers)
    )

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Saved: {filename}")


def fetch_cadwr_data(bbox, start_date=None, end_date=None, max_sites=500):
    """Fetch groundwater data from CADWR."""
    print(f"Fetching CADWR data for bbox: {bbox}")

    # Current levels
    result = get_current_levels(bbox=bbox, max_records=max_sites)
    data = json.loads(result)

    if 'error' in data:
        print(f"CADWR API error: {data['error']}")
        return [], {}

    wells = data.get('wells', [])
    print(f"Found {len(wells)} monitoring wells")

    if not wells:
        return [], {}

    # Percentile stats
    print("Fetching percentile statistics...")
    pct_result = get_percentile_stats(bbox=bbox, max_records=max_sites)
    pct_data = json.loads(pct_result)
    pct_wells = {w['site_code']: w for w in pct_data.get('wells', [])}
    print(f"Found {len(pct_wells)} wells with percentile data")

    points_data = []
    site_timeseries = {}

    for well in wells:
        site_code = well.get('site_code', '')
        lat, lon = well.get('lat'), well.get('lon')

        if not site_code or lat is None or lon is None:
            continue

        pct_info = pct_wells.get(site_code, {})

        point_info = {
            'site_no': site_code,
            'name': well.get('name', f'Site {site_code}'),
            'lat': lat, 'lon': lon,
            'source': 'CADWR',
            'county': well.get('county', ''),
            'basin_name': well.get('basin_name', ''),
            'measurement_date': well.get('measurement_date'),
            'depth_ft': well.get('depth_ft'),
            'gwe_ft': well.get('gwe_ft'),
            'gse_ft': well.get('gse_ft'),
            'well_use': well.get('well_use', ''),
            'change': 0,
            'pct_lowest': pct_info.get('pct_lowest'),
            'pct_10': pct_info.get('pct_10'),
            'pct_25': pct_info.get('pct_25'),
            'pct_50': pct_info.get('pct_50'),
            'pct_75': pct_info.get('pct_75'),
            'pct_90': pct_info.get('pct_90'),
            'pct_highest': pct_info.get('pct_highest'),
            'percentile_class': pct_info.get('percentile_class', ''),
            'percentile_class_code': pct_info.get('percentile_class_code'),
            'measurement_count': pct_info.get('count'),
        }

        # Recalculate percentile class based on current depth
        if pct_info and point_info['depth_ft'] is not None:
            calc_class, _ = calculate_percentile_class(point_info['depth_ft'], pct_info)
            if calc_class:
                point_info['percentile_class'] = calc_class

        points_data.append(point_info)

    print(f"Processed {len(points_data)} wells with valid coordinates")

    # Fetch time series for top N sites
    if start_date and end_date and points_data:
        print("Fetching time series data...")
        fetch_count = min(50, len(points_data))

        for i, point in enumerate(points_data[:fetch_count]):
            site_code = point['site_no']
            try:
                history = json.loads(get_measurement_history(site_code, start_date, end_date, limit=500))
                measurements = history.get('measurements', [])

                if measurements:
                    valid_data = [(m['date'], m.get('depth_ft') or (-(m.get('gwe_ft') or 0)))
                                  for m in measurements if m.get('depth_ft') or m.get('gwe_ft')]
                    if valid_data:
                        dates = [d for d, v in valid_data]
                        values = [v for d, v in valid_data]
                        site_timeseries[site_code] = {
                            'dates': dates,
                            'values': values
                        }
                        if len(valid_data) >= 2:
                            point['change'] = valid_data[-1][1] - valid_data[0][1]
            except:
                pass

            if (i + 1) % 10 == 0:
                print(f"  ... fetched {i + 1}/{fetch_count} time series")

    return points_data, site_timeseries


def create_groundwater_map(bbox, start_date, end_date, region_name, output_file, zoom=9, max_cadwr=None):
    """Create CADWR groundwater monitoring map."""

    # Fetch data
    print("\n--- Fetching CADWR Data ---")
    cadwr_points, timeseries = fetch_cadwr_data(
        bbox=bbox,
        start_date=start_date,
        end_date=end_date,
        max_sites=max_cadwr or 500
    )

    if max_cadwr and len(cadwr_points) > max_cadwr:
        cadwr_points = cadwr_points[:max_cadwr]
        print(f"Limited to {max_cadwr} sites for testing")

    if not cadwr_points:
        print("\nNo data available for the specified region.")
        return 0

    # Calculate center
    center_lat = sum(p['lat'] for p in cadwr_points) / len(cadwr_points)
    center_lon = sum(p['lon'] for p in cadwr_points) / len(cadwr_points)

    # Create map
    print("\n--- Creating Map ---")
    fig, home_lat, home_lon, home_zoom = create_map(
        title=f"CADWR Groundwater - {region_name}",
        center_lat=center_lat,
        center_lon=center_lon,
        zoom=zoom
    )

    # Add markers
    fig = add_groundwater_sites(
        fig, cadwr_points,
        layer_name="CADWR",
        size=12,
        colorscale="RdYlBu_r",
        show_colorbar=True
    )

    # Save
    data_period = f"{start_date} ~ {end_date}"
    save_map(
        fig, output_file, home_lat, home_lon, home_zoom, timeseries,
        region_name=region_name,
        data_period=data_period,
        layers=[]
    )

    print(f"Total sites: {len(cadwr_points)}")
    return len(cadwr_points)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CADWR Groundwater Map Generator")
    parser.add_argument('-b', '--bbox', required=True, help="Bounding box: 'west,south,east,north'")
    parser.add_argument('-s', '--start', required=True, help="Start date: YYYY-MM-DD")
    parser.add_argument('-e', '--end', required=True, help="End date: YYYY-MM-DD")
    parser.add_argument('-n', '--name', required=True, help="Region name")
    parser.add_argument('-o', '--output', default="groundwater_map.html", help="Output HTML file")
    parser.add_argument('-z', '--zoom', type=int, default=9, help="Initial zoom level")
    parser.add_argument('--max-cadwr', type=int, default=None, help="Limit sites (for testing)")

    args = parser.parse_args()

    print("=" * 60)
    print("CADWR Groundwater Monitoring Map Generator")
    print("=" * 60)
    print(f"\nRegion: {args.name}")
    print(f"Bbox: {args.bbox}")
    print(f"Period: {args.start} ~ {args.end}")

    count = create_groundwater_map(
        bbox=args.bbox,
        start_date=args.start,
        end_date=args.end,
        region_name=args.name,
        output_file=args.output,
        zoom=args.zoom,
        max_cadwr=args.max_cadwr
    )

    if count > 0:
        print("\nOpen the HTML file in a browser to view the map.")
