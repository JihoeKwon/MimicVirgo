"""
California DWR (Department of Water Resources) Groundwater Info Module
- Fetch groundwater monitoring well data from CalGWLive ArcGIS REST API
- Support bounding box queries
- Get current levels, seasonal changes, and trends
- Export to CSV

Data Source: California's Groundwater Live (CalGWLive)
https://sgma.water.ca.gov/CalGWLive/
"""

import json
import os
import requests
from datetime import datetime


# CKAN DataStore API (시계열 데이터)
CKAN_API_BASE = 'https://data.cnra.ca.gov/api/3/action/datastore_search'
CKAN_SQL_API = 'https://data.cnra.ca.gov/api/3/action/datastore_search_sql'
CKAN_RESOURCES = {
    'stations': 'af157380-fb42-4abf-b72a-6f9f98868077',
    'measurements': 'bfa9f262-24a1-45bd-8dc8-138bc8107266',
    'perforations': 'f1deaa6d-2cb5-4052-a73f-08a69f26b750',
}

# ArcGIS REST API Endpoints (layer ID는 서비스마다 다름)
ENDPOINTS = {
    # 최근 측정된 지하수위 (layer id: 2)
    'current_levels': 'https://services.arcgis.com/aa38u6OgfNoCkTJ6/arcgis/rest/services/GWL_Recently_Measured_v3/FeatureServer/2',

    # 지하수위 백분위 통계 (layer id: 0)
    'percentile_stats': 'https://services.arcgis.com/aa38u6OgfNoCkTJ6/arcgis/rest/services/GroundwaterLevelPercentileClass_gdb/FeatureServer/0',

    # 계절 변화 (layer id: 2)
    'seasonal_change': 'https://services.arcgis.com/aa38u6OgfNoCkTJ6/arcgis/rest/services/SeasonalChangeCalGWLive_gdb/FeatureServer/2',

    # 20년 Mann-Kendall 추세 (layer id: 2)
    'long_term_trend': 'https://services.arcgis.com/aa38u6OgfNoCkTJ6/arcgis/rest/services/MannKendallGWLTrendCalGWLive_gdb/FeatureServer/2',
}


def _ensure_output_dir(output_dir: str) -> str:
    """Create output directory if it doesn't exist."""
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _get_output_path(filename: str, output_dir: str = None) -> str:
    """Get full output path, creating directory if needed."""
    if output_dir:
        _ensure_output_dir(output_dir)
        return os.path.join(output_dir, filename)
    return filename


def _query_arcgis_feature_service(endpoint_url, bbox=None, where="1=1", out_fields="*",
                                   return_geometry=True, max_records=5000, timeout=120):
    """
    Query ArcGIS Feature Service REST API.

    Args:
        endpoint_url: Base URL of the feature service layer
        bbox: Bounding box as 'west,south,east,north' (optional)
        where: SQL where clause (default: "1=1" for all records)
        out_fields: Fields to return (default: "*" for all)
        return_geometry: Whether to return geometry (default: True)
        max_records: Maximum records to return (default: 5000)
        timeout: Request timeout in seconds

    Returns:
        dict: JSON response from API
    """
    query_url = f"{endpoint_url}/query"

    params = {
        'where': where,
        'outFields': out_fields,
        'returnGeometry': 'true' if return_geometry else 'false',
        'f': 'json',
        'resultRecordCount': max_records,
    }

    # Add spatial filter if bbox provided
    if bbox:
        west, south, east, north = map(float, bbox.split(','))
        params['geometry'] = json.dumps({
            'xmin': west, 'ymin': south,
            'xmax': east, 'ymax': north,
            'spatialReference': {'wkid': 4326}
        })
        params['geometryType'] = 'esriGeometryEnvelope'
        params['inSR'] = 4326
        params['spatialRel'] = 'esriSpatialRelIntersects'

    response = requests.get(query_url, params=params, timeout=timeout)

    if response.status_code != 200:
        raise Exception(f"API error: HTTP {response.status_code}")

    return response.json()


def get_service_info(endpoint_name='current_levels'):
    """
    Get metadata about a feature service.

    Args:
        endpoint_name: One of 'current_levels', 'percentile_stats', 'seasonal_change', 'long_term_trend'

    Returns:
        JSON string with service info
    """
    if endpoint_name not in ENDPOINTS:
        return json.dumps({"error": f"Unknown endpoint: {endpoint_name}"})

    url = ENDPOINTS[endpoint_name]
    params = {'f': 'json'}

    response = requests.get(url, params=params, timeout=60)

    if response.status_code != 200:
        return json.dumps({"error": f"API error: {response.status_code}"})

    data = response.json()

    # Extract useful info
    info = {
        "endpoint": endpoint_name,
        "name": data.get('name', ''),
        "description": data.get('description', ''),
        "fields": [
            {"name": f['name'], "type": f['type'], "alias": f.get('alias', '')}
            for f in data.get('fields', [])
        ],
        "geometry_type": data.get('geometryType', ''),
        "extent": data.get('extent', {}),
    }

    return json.dumps(info, indent=2)


def _convert_timestamp(ts):
    """Convert Unix timestamp (milliseconds) to date string."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
    except:
        return None


def get_current_levels(bbox=None, max_records=5000):
    """
    Get current groundwater levels from recently measured wells.

    Args:
        bbox: Bounding box as 'west,south,east,north' (optional, None for all California)
        max_records: Maximum records to return

    Returns:
        JSON string with well data
    """
    try:
        data = _query_arcgis_feature_service(
            ENDPOINTS['current_levels'],
            bbox=bbox,
            max_records=max_records
        )

        features = data.get('features', [])

        wells = []
        for f in features:
            attrs = f.get('attributes', {})

            # Use LATITUDE/LONGITUDE fields (geometry is in Web Mercator)
            lat = attrs.get('LATITUDE')
            lon = attrs.get('LONGITUDE')

            wells.append({
                'site_code': attrs.get('SITE_CODE', ''),
                'state_well_number': attrs.get('SWN', ''),
                'name': attrs.get('WELL_NAME', ''),
                'lat': lat,
                'lon': lon,
                'gse_ft': attrs.get('LAST_GSE'),  # Ground surface elevation
                'gwe_ft': attrs.get('LAST_GWE'),  # Groundwater elevation
                'depth_ft': attrs.get('LAST_GSE_GWE'),  # Depth to water (GSE - GWE)
                'well_depth_ft': attrs.get('WELL_DEPTH'),
                'measurement_date': _convert_timestamp(attrs.get('LAST_MSMT_DATE')),
                'basin_name': attrs.get('Basin_Name', ''),
                'county': attrs.get('COUNTY_NAME', ''),
                'well_use': attrs.get('WELL_USE', ''),
                'well_type': attrs.get('WELL_TYPE', ''),
                'monitoring_program': attrs.get('MONITORING_PROGRAM', ''),
                'submitting_org': attrs.get('LAST_MEAS_SUBMITTING_ORG_NAME', ''),
            })

        return json.dumps({
            "source": "CalGWLive - Current Levels",
            "bbox": bbox,
            "count": len(wells),
            "wells": wells
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_seasonal_change(bbox=None, years=10, max_records=5000):
    """
    Get seasonal groundwater level changes.

    Args:
        bbox: Bounding box as 'west,south,east,north' (optional)
        years: Filter by years (1, 3, 5, or 10). Default: 10
        max_records: Maximum records to return

    Returns:
        JSON string with seasonal change data
    """
    try:
        # Filter by YEARS field
        where_clause = f"YEARS = {years}"

        data = _query_arcgis_feature_service(
            ENDPOINTS['seasonal_change'],
            bbox=bbox,
            where=where_clause,
            max_records=max_records
        )

        features = data.get('features', [])

        wells = []
        for f in features:
            attrs = f.get('attributes', {})

            wells.append({
                'site_code': attrs.get('SITE_CODE', ''),
                'name': attrs.get('WELL_NAME', ''),
                'lat': attrs.get('LATITUDE'),
                'lon': attrs.get('LONGITUDE'),
                'wse_change_ft': attrs.get('WSE_CHANGE'),
                'wse_change_category': attrs.get('WSE_CHANGE_CATEGORY', ''),
                'wse_late_ft': attrs.get('WSE_LATE'),
                'wse_early_ft': attrs.get('WSE_EARLY'),
                'msmt_date_late': _convert_timestamp(attrs.get('MSMT_DATE_LATE')),
                'msmt_date_early': _convert_timestamp(attrs.get('MSMT_DATE_EARLY')),
                'years': attrs.get('YEARS'),
                'season': attrs.get('Measurement_Season', ''),
                'basin_name': attrs.get('Basin_Name', ''),
                'county': attrs.get('COUNTY_NAME', ''),
                'well_use': attrs.get('WELL_USE', ''),
            })

        # Statistics
        changes = [w['wse_change_ft'] for w in wells if w['wse_change_ft'] is not None]

        stats = None
        if changes:
            stats = {
                'wse_change': {
                    'min': min(changes),
                    'max': max(changes),
                    'mean': sum(changes) / len(changes),
                    'count': len(changes)
                }
            }

        # Category distribution
        categories = {}
        for w in wells:
            cat = w['wse_change_category'] or 'Unknown'
            categories[cat] = categories.get(cat, 0) + 1

        return json.dumps({
            "source": "CalGWLive - Seasonal Change",
            "bbox": bbox,
            "years": years,
            "count": len(wells),
            "statistics": stats,
            "category_distribution": categories,
            "wells": wells
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_long_term_trend(bbox=None, max_records=5000):
    """
    Get long-term (20-year) groundwater level trends using Mann-Kendall analysis.

    Args:
        bbox: Bounding box as 'west,south,east,north' (optional)
        max_records: Maximum records to return

    Returns:
        JSON string with trend data
    """
    try:
        data = _query_arcgis_feature_service(
            ENDPOINTS['long_term_trend'],
            bbox=bbox,
            max_records=max_records
        )

        features = data.get('features', [])

        wells = []
        for f in features:
            attrs = f.get('attributes', {})
            geom = f.get('geometry', {})

            wells.append({
                'site_code': attrs.get('SITE_CODE', ''),
                'state_well_number': attrs.get('SWN', ''),
                'lat': geom.get('y'),
                'lon': geom.get('x'),
                'trend_class': attrs.get('TREND_CLASS', ''),
                'trend_slope': attrs.get('TREND_SLOPE', None),
                'trend_pvalue': attrs.get('TREND_PVALUE', None),
                'basin_name': attrs.get('BASIN_NAME', ''),
                'county': attrs.get('COUNTY_NAME', ''),
            })

        # Trend distribution
        trend_counts = {}
        for w in wells:
            tc = w['trend_class'] or 'Unknown'
            trend_counts[tc] = trend_counts.get(tc, 0) + 1

        return json.dumps({
            "source": "CalGWLive - Long Term Trend (Mann-Kendall)",
            "bbox": bbox,
            "count": len(wells),
            "trend_distribution": trend_counts,
            "wells": wells
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_percentile_stats(bbox=None, max_records=5000, ranked_only=True):
    """
    Get groundwater level percentile statistics for wells.
    Shows where current water level falls within historical distribution.

    Args:
        bbox: Bounding box as 'west,south,east,north' (optional)
        max_records: Maximum records to return
        ranked_only: If True, exclude 'Not Ranked' sites (default: True)

    Returns:
        JSON string with percentile stats data
    """
    try:
        # Filter out 'Not Ranked' sites (PercentileClassCode = 8)
        where_clause = "PercentileClassCode <> 8" if ranked_only else "1=1"

        data = _query_arcgis_feature_service(
            ENDPOINTS['percentile_stats'],
            bbox=bbox,
            where=where_clause,
            max_records=max_records
        )

        features = data.get('features', [])

        wells = []
        for f in features:
            attrs = f.get('attributes', {})
            geom = f.get('geometry', {})

            wells.append({
                'site_code': attrs.get('SITE_CODE', ''),
                'lat': attrs.get('LATITUDE') or geom.get('y'),
                'lon': attrs.get('LONGITUDE') or geom.get('x'),
                'count': attrs.get('COUNT_'),
                'last_depth_ft': attrs.get('LAST_DEPTH'),
                'min_depth_ft': attrs.get('MIN_DEPTH'),
                'max_depth_ft': attrs.get('MAX_DEPTH'),
                # Percentile values (depth in ft)
                'pct_lowest': attrs.get('Lowest'),
                'pct_10': attrs.get('F10thpct'),
                'pct_25': attrs.get('F25thpct'),
                'pct_50': attrs.get('F50thpct'),
                'pct_75': attrs.get('F75thpct'),
                'pct_90': attrs.get('F90thpct'),
                'pct_highest': attrs.get('Highest'),
                # Classification
                'percentile_class': attrs.get('PercentileClass', ''),
                'percentile_class_code': attrs.get('PercentileClassCode'),
                # Location info
                'basin_name': attrs.get('Basin_Name', ''),
                'county': attrs.get('COUNTY_NAME', ''),
                'well_depth_ft': attrs.get('WELL_DEPTH'),
            })

        # Class distribution
        class_counts = {}
        for w in wells:
            pc = w['percentile_class'] or 'Unknown'
            class_counts[pc] = class_counts.get(pc, 0) + 1

        return json.dumps({
            "source": "CalGWLive - Percentile Statistics",
            "bbox": bbox,
            "count": len(wells),
            "class_distribution": class_counts,
            "wells": wells
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_wells_by_county(county_name, endpoint='current_levels', max_records=5000):
    """
    Get wells filtered by county name.

    Args:
        county_name: County name (e.g., 'San Diego', 'Los Angeles')
        endpoint: Which endpoint to query
        max_records: Maximum records to return

    Returns:
        JSON string with well data
    """
    if endpoint not in ENDPOINTS:
        return json.dumps({"error": f"Unknown endpoint: {endpoint}"})

    try:
        where_clause = f"COUNTY_NAME LIKE '%{county_name}%'"

        data = _query_arcgis_feature_service(
            ENDPOINTS[endpoint],
            where=where_clause,
            max_records=max_records
        )

        features = data.get('features', [])

        wells = []
        for f in features:
            attrs = f.get('attributes', {})
            geom = f.get('geometry', {})

            well_info = {
                'site_code': attrs.get('SITE_CODE', ''),
                'state_well_number': attrs.get('SWN', ''),
                'lat': geom.get('y'),
                'lon': geom.get('x'),
                'basin_name': attrs.get('BASIN_NAME', ''),
                'county': attrs.get('COUNTY_NAME', ''),
            }

            # Add endpoint-specific fields
            if endpoint == 'current_levels':
                well_info['wse_ft'] = attrs.get('WSE', None)
                well_info['measurement_date'] = attrs.get('MSMT_DATE', '')
            elif endpoint == 'seasonal_change':
                well_info['change_1yr_ft'] = attrs.get('CHANGE_1YR', None)
                well_info['change_5yr_ft'] = attrs.get('CHANGE_5YR', None)
            elif endpoint == 'long_term_trend':
                well_info['trend_class'] = attrs.get('TREND_CLASS', '')

            wells.append(well_info)

        return json.dumps({
            "source": f"CalGWLive - {endpoint}",
            "county": county_name,
            "count": len(wells),
            "wells": wells
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_wells_by_basin(basin_name, endpoint='current_levels', max_records=5000):
    """
    Get wells filtered by groundwater basin name.

    Args:
        basin_name: Basin name (e.g., 'San Diego River Valley')
        endpoint: Which endpoint to query
        max_records: Maximum records to return

    Returns:
        JSON string with well data
    """
    if endpoint not in ENDPOINTS:
        return json.dumps({"error": f"Unknown endpoint: {endpoint}"})

    try:
        where_clause = f"BASIN_NAME LIKE '%{basin_name}%'"

        data = _query_arcgis_feature_service(
            ENDPOINTS[endpoint],
            where=where_clause,
            max_records=max_records
        )

        features = data.get('features', [])

        wells = []
        for f in features:
            attrs = f.get('attributes', {})
            geom = f.get('geometry', {})

            wells.append({
                'site_code': attrs.get('SITE_CODE', ''),
                'state_well_number': attrs.get('SWN', ''),
                'lat': geom.get('y'),
                'lon': geom.get('x'),
                'basin_name': attrs.get('BASIN_NAME', ''),
                'county': attrs.get('COUNTY_NAME', ''),
            })

        return json.dumps({
            "source": f"CalGWLive - {endpoint}",
            "basin": basin_name,
            "count": len(wells),
            "wells": wells
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_measurement_history(site_code, start_date=None, end_date=None, limit=1000):
    """
    Get time-series groundwater level measurements for a specific site.

    Args:
        site_code: Site code (e.g., '325536N1170608W001')
        start_date: Start date filter (YYYY-MM-DD), optional
        end_date: End date filter (YYYY-MM-DD), optional
        limit: Maximum records to return (default: 1000)

    Returns:
        JSON string with measurement history
    """
    try:
        # Build filter
        filters = {'site_code': site_code}

        params = {
            'resource_id': CKAN_RESOURCES['measurements'],
            'filters': json.dumps(filters),
            'limit': limit,
            'sort': 'msmt_date desc'
        }

        response = requests.get(CKAN_API_BASE, params=params, timeout=120)

        if response.status_code != 200:
            return json.dumps({"error": f"API error: {response.status_code}"})

        data = response.json()

        if not data.get('success'):
            return json.dumps({"error": data.get('error', 'Unknown error')})

        records = data['result']['records']

        # Filter by date if specified
        measurements = []
        for r in records:
            msmt_date = r.get('msmt_date', '')[:10]  # YYYY-MM-DD

            if start_date and msmt_date < start_date:
                continue
            if end_date and msmt_date > end_date:
                continue

            measurements.append({
                'date': msmt_date,
                'gwe_ft': r.get('gwe'),  # Groundwater elevation
                'depth_ft': r.get('gse_gwe'),  # Depth to water
                'gse_ft': r.get('wlm_gse'),  # Ground surface elevation
                'qa': r.get('wlm_qa_desc', ''),
                'method': r.get('wlm_mthd_desc', ''),
                'org': r.get('wlm_org_name', ''),
            })

        # Sort by date ascending
        measurements.sort(key=lambda x: x['date'])

        return json.dumps({
            "source": "CADWR Periodic GWL Measurements",
            "site_code": site_code,
            "start_date": start_date,
            "end_date": end_date,
            "count": len(measurements),
            "measurements": measurements
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_sites_with_measurements(bbox=None, county=None, basin=None, limit=1000):
    """
    Get list of monitoring sites that have measurement data.

    Args:
        bbox: Bounding box as 'west,south,east,north' (optional)
        county: County name filter (optional)
        basin: Basin name filter (optional)
        limit: Maximum records

    Returns:
        JSON string with site list
    """
    try:
        filters = {}
        if county:
            filters['county_name'] = county

        params = {
            'resource_id': CKAN_RESOURCES['stations'],
            'limit': limit,
        }

        if filters:
            params['filters'] = json.dumps(filters)

        # Add SQL query for basin (uses LIKE)
        if basin:
            sql = f"SELECT * FROM \"{CKAN_RESOURCES['stations']}\" WHERE basin_name ILIKE '%{basin}%' LIMIT {limit}"
            response = requests.get(CKAN_SQL_API, params={'sql': sql}, timeout=120)
        else:
            response = requests.get(CKAN_API_BASE, params=params, timeout=120)

        if response.status_code != 200:
            return json.dumps({"error": f"API error: {response.status_code}"})

        data = response.json()

        if not data.get('success'):
            return json.dumps({"error": data.get('error', 'Unknown error')})

        records = data['result']['records']

        # Filter by bbox if specified
        sites = []
        for r in records:
            lat = r.get('latitude')
            lon = r.get('longitude')

            if bbox and lat and lon:
                west, south, east, north = map(float, bbox.split(','))
                if not (west <= lon <= east and south <= lat <= north):
                    continue

            sites.append({
                'site_code': r.get('site_code'),
                'stn_id': r.get('stn_id'),
                'name': r.get('well_name', ''),
                'lat': lat,
                'lon': lon,
                'gse_ft': r.get('gse'),
                'well_depth_ft': r.get('well_depth'),
                'basin_name': r.get('basin_name', ''),
                'county': r.get('county_name', ''),
                'well_use': r.get('well_use', ''),
                'monitoring_program': r.get('monitoring_program', ''),
            })

        return json.dumps({
            "source": "CADWR Periodic GWL Stations",
            "bbox": bbox,
            "county": county,
            "basin": basin,
            "count": len(sites),
            "sites": sites
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_measurements_by_county(county, start_date=None, end_date=None, limit=5000):
    """
    Get all measurements for a county within a date range.

    Args:
        county: County name (e.g., 'San Diego')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        limit: Maximum records

    Returns:
        JSON string with measurements grouped by site
    """
    try:
        # Build SQL query for efficient filtering
        conditions = [f"county_name = '{county}'"]
        if start_date:
            conditions.append(f"msmt_date >= '{start_date}'")
        if end_date:
            conditions.append(f"msmt_date <= '{end_date}'")

        where_clause = ' AND '.join(conditions)
        sql = f'SELECT * FROM "{CKAN_RESOURCES["measurements"]}" WHERE {where_clause} ORDER BY site_code, msmt_date LIMIT {limit}'

        response = requests.get(CKAN_SQL_API, params={'sql': sql}, timeout=180)

        if response.status_code != 200:
            return json.dumps({"error": f"API error: {response.status_code}"})

        data = response.json()

        if not data.get('success'):
            return json.dumps({"error": data.get('error', 'Unknown error')})

        records = data['result']['records']

        # Group by site
        sites_data = {}
        for r in records:
            site_code = r.get('site_code')
            if site_code not in sites_data:
                sites_data[site_code] = {
                    'site_code': site_code,
                    'county': r.get('county_name'),
                    'basin': r.get('basin_code'),
                    'measurements': []
                }

            sites_data[site_code]['measurements'].append({
                'date': r.get('msmt_date', '')[:10],
                'gwe_ft': r.get('gwe'),
                'depth_ft': r.get('gse_gwe'),
            })

        return json.dumps({
            "source": "CADWR Periodic GWL Measurements",
            "county": county,
            "start_date": start_date,
            "end_date": end_date,
            "sites_count": len(sites_data),
            "total_measurements": len(records),
            "sites": list(sites_data.values())
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def export_to_csv(data_json, output_csv, output_dir=None):
    """
    Export well data to CSV file.

    Args:
        data_json: JSON string from get_* functions
        output_csv: Output CSV filename
        output_dir: Optional output directory

    Returns:
        str: Output file path
    """
    import csv

    data = json.loads(data_json)

    if 'error' in data:
        raise Exception(data['error'])

    wells = data.get('wells', [])
    if not wells:
        raise Exception("No wells data to export")

    output_path = _get_output_path(output_csv, output_dir)

    # Get all unique keys
    all_keys = set()
    for w in wells:
        all_keys.update(w.keys())

    fieldnames = sorted(all_keys)

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(wells)

    return output_path


def plot_measurement_history(site_code, start_date=None, end_date=None, output_html=None):
    """
    Plot groundwater level time series for a site.

    Args:
        site_code: Site code
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        output_html: Output HTML file (optional, shows in browser if None)

    Returns:
        str: Output file path or None
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        print("Error: plotly is required. Install with: pip install plotly")
        return None

    # Get data
    result = get_measurement_history(site_code, start_date, end_date)
    data = json.loads(result)

    if 'error' in data:
        print(f"Error: {data['error']}")
        return None

    measurements = data.get('measurements', [])
    if not measurements:
        print("No measurements found")
        return None

    # Extract data
    dates = [m['date'] for m in measurements]
    gwe = [m['gwe_ft'] for m in measurements]
    depth = [m['depth_ft'] for m in measurements]

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Groundwater Elevation (primary y-axis)
    fig.add_trace(
        go.Scatter(
            x=dates, y=gwe,
            mode='lines+markers',
            name='GW Elevation (ft)',
            line=dict(color='#1976D2', width=2),
            marker=dict(size=6)
        ),
        secondary_y=False
    )

    # Depth to Water (secondary y-axis)
    fig.add_trace(
        go.Scatter(
            x=dates, y=depth,
            mode='lines+markers',
            name='Depth to Water (ft)',
            line=dict(color='#E53935', width=2, dash='dash'),
            marker=dict(size=6)
        ),
        secondary_y=True
    )

    # Layout
    fig.update_layout(
        title=dict(
            text=f'Groundwater Level History<br><sup>Site: {site_code}</sup>',
            x=0.5
        ),
        xaxis_title='Date',
        hovermode='x unified',
        template='plotly_white',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5
        )
    )

    fig.update_yaxes(title_text="GW Elevation (ft)", secondary_y=False)
    fig.update_yaxes(title_text="Depth to Water (ft)", autorange="reversed", secondary_y=True)

    if output_html:
        fig.write_html(output_html)
        print(f"Saved: {output_html}")
        return output_html
    else:
        fig.show()
        return None


def plot_county_summary(county, start_date=None, end_date=None, output_html=None, max_sites=20):
    """
    Plot groundwater level trends for multiple sites in a county.

    Args:
        county: County name
        start_date: Start date
        end_date: End date
        output_html: Output HTML file
        max_sites: Maximum number of sites to plot

    Returns:
        str: Output file path or None
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("Error: plotly is required. Install with: pip install plotly")
        return None

    # Get data
    result = get_measurements_by_county(county, start_date, end_date, limit=10000)
    data = json.loads(result)

    if 'error' in data:
        print(f"Error: {data['error']}")
        return None

    sites = data.get('sites', [])
    if not sites:
        print("No sites found")
        return None

    # Sort by number of measurements and take top N
    sites.sort(key=lambda x: len(x['measurements']), reverse=True)
    sites = sites[:max_sites]

    # Create figure
    fig = go.Figure()

    for site in sites:
        measurements = site['measurements']
        if len(measurements) < 3:
            continue

        dates = [m['date'] for m in measurements]
        depths = [m['depth_ft'] for m in measurements if m['depth_ft'] is not None]
        dates_valid = [m['date'] for m in measurements if m['depth_ft'] is not None]

        fig.add_trace(go.Scatter(
            x=dates_valid,
            y=depths,
            mode='lines+markers',
            name=site['site_code'][-12:],  # Shortened name
            marker=dict(size=4),
            line=dict(width=1.5)
        ))

    fig.update_layout(
        title=dict(
            text=f'Groundwater Depth Trends - {county} County<br><sup>{start_date or "Start"} to {end_date or "Present"}</sup>',
            x=0.5
        ),
        xaxis_title='Date',
        yaxis_title='Depth to Water (ft)',
        yaxis=dict(autorange='reversed'),  # Depth increases downward
        hovermode='x unified',
        template='plotly_white',
        legend=dict(
            orientation='v',
            yanchor='top',
            y=1,
            xanchor='left',
            x=1.02,
            font=dict(size=9)
        )
    )

    if output_html:
        fig.write_html(output_html)
        print(f"Saved: {output_html}")
        return output_html
    else:
        fig.show()
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="California DWR Groundwater Data Fetcher (CalGWLive + Periodic Measurements)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get current levels for San Diego area
  python cadwr_gwinfo.py -t current_levels --bbox="-117.5,32.5,-116.5,33.5"

  # Get seasonal changes (10 year)
  python cadwr_gwinfo.py -t seasonal_change -c "San Diego"

  # Get time-series history for a specific site
  python cadwr_gwinfo.py -t history --site 325536N1170608W001 -s 2020-01-01 -e 2025-12-31

  # Plot time-series graph for a site
  python cadwr_gwinfo.py -t history --site 325536N1170608W001 -s 2020-01-01 --plot

  # Plot county summary
  python cadwr_gwinfo.py -t county_summary -c "San Diego" -s 2020-01-01 --plot

  # Export to CSV
  python cadwr_gwinfo.py -t current_levels -o wells.csv

Data Types:
  current_levels   - Recently measured groundwater levels (CalGWLive)
  seasonal_change  - 1, 3, 5, 10 year seasonal changes (CalGWLive)
  long_term_trend  - 20-year Mann-Kendall trend analysis (CalGWLive)
  history          - Time-series measurements for a site (Periodic GWL)
  county_summary   - All measurements in a county (Periodic GWL)
  sites            - List of monitoring sites (Periodic GWL)
        """
    )

    parser.add_argument('-t', '--type', default='current_levels',
                        choices=['current_levels', 'seasonal_change', 'long_term_trend',
                                 'percentile_stats', 'history', 'county_summary', 'sites'],
                        help="Data type to fetch (default: current_levels)")
    parser.add_argument('-b', '--bbox',
                        help="Bounding box: 'west,south,east,north'")
    parser.add_argument('-c', '--county',
                        help="Filter by county name")
    parser.add_argument('--basin',
                        help="Filter by basin name")
    parser.add_argument('--site',
                        help="Site code for history query")
    parser.add_argument('-s', '--start',
                        help="Start date (YYYY-MM-DD) for time-series")
    parser.add_argument('-e', '--end',
                        help="End date (YYYY-MM-DD) for time-series")
    parser.add_argument('--years', type=int, default=10, choices=[1, 3, 5, 10],
                        help="Years for seasonal_change (default: 10)")
    parser.add_argument('-o', '--output',
                        help="Export to CSV file")
    parser.add_argument('--plot', action='store_true',
                        help="Generate interactive plot (HTML)")
    parser.add_argument('-n', '--max-records', type=int, default=5000,
                        help="Maximum records to fetch (default: 5000)")
    parser.add_argument('--info',
                        help="Get service info for specified endpoint")

    args = parser.parse_args()

    print("=" * 60)
    print("California DWR Groundwater Data")
    print("=" * 60)

    if args.info:
        print(f"\nService info for: {args.info}")
        result = get_service_info(args.info)
        print(result)

    elif args.type == 'history':
        if not args.site:
            print("Error: --site is required for history query")
            exit(1)

        print(f"\nFetching history for site: {args.site}")
        if args.start:
            print(f"Start date: {args.start}")
        if args.end:
            print(f"End date: {args.end}")

        if args.plot:
            output_html = args.output or f"gw_history_{args.site}.html"
            plot_measurement_history(args.site, args.start, args.end, output_html)
        else:
            result = get_measurement_history(args.site, args.start, args.end)
            data = json.loads(result)
            print(f"Found {data.get('count', 0)} measurements")
            print(json.dumps(data, indent=2))

    elif args.type == 'county_summary':
        if not args.county:
            print("Error: --county is required for county_summary")
            exit(1)

        print(f"\nFetching measurements for county: {args.county}")

        if args.plot:
            output_html = args.output or f"gw_summary_{args.county.replace(' ', '_')}.html"
            plot_county_summary(args.county, args.start, args.end, output_html)
        else:
            result = get_measurements_by_county(args.county, args.start, args.end, args.max_records)
            data = json.loads(result)
            print(f"Found {data.get('sites_count', 0)} sites, {data.get('total_measurements', 0)} measurements")

            if args.output:
                # Flatten for CSV export
                rows = []
                for site in data.get('sites', []):
                    for m in site.get('measurements', []):
                        rows.append({
                            'site_code': site['site_code'],
                            'date': m['date'],
                            'gwe_ft': m['gwe_ft'],
                            'depth_ft': m['depth_ft']
                        })
                flat_data = json.dumps({'measurements': rows})
                # Custom export
                import csv
                with open(args.output, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=['site_code', 'date', 'gwe_ft', 'depth_ft'])
                    writer.writeheader()
                    writer.writerows(rows)
                print(f"Exported to: {args.output}")

    elif args.type == 'sites':
        print(f"\nFetching monitoring sites...")
        result = get_sites_with_measurements(args.bbox, args.county, args.basin, args.max_records)
        data = json.loads(result)
        print(f"Found {data.get('count', 0)} sites")

        if args.output:
            path = export_to_csv(result, args.output)
            print(f"Exported to: {path}")
        else:
            if 'sites' in data and len(data['sites']) > 5:
                data['sites'] = data['sites'][:5]
                data['note'] = 'Showing first 5 sites only. Use -o to export all.'
            print(json.dumps(data, indent=2))

    elif args.county and args.type in ['current_levels', 'seasonal_change', 'long_term_trend']:
        print(f"\nFetching {args.type} for county: {args.county}")
        result = get_wells_by_county(args.county, args.type, args.max_records)
        data = json.loads(result)
        print(f"Found {data.get('count', 0)} wells")

        if args.output:
            path = export_to_csv(result, args.output)
            print(f"Exported to: {path}")
        else:
            if 'wells' in data and len(data['wells']) > 5:
                data['wells'] = data['wells'][:5]
                data['note'] = 'Showing first 5 wells only. Use -o to export all.'
            print(json.dumps(data, indent=2))

    elif args.basin:
        print(f"\nFetching {args.type} for basin: {args.basin}")
        result = get_wells_by_basin(args.basin, args.type, args.max_records)
        data = json.loads(result)
        print(f"Found {data.get('count', 0)} wells")

        if args.output:
            path = export_to_csv(result, args.output)
            print(f"Exported to: {path}")
        else:
            print(json.dumps(data, indent=2))

    else:
        print(f"\nFetching {args.type}...")
        if args.bbox:
            print(f"Bounding box: {args.bbox}")

        if args.type == 'current_levels':
            result = get_current_levels(args.bbox, args.max_records)
        elif args.type == 'seasonal_change':
            result = get_seasonal_change(args.bbox, args.years, args.max_records)
        elif args.type == 'long_term_trend':
            result = get_long_term_trend(args.bbox, args.max_records)
        else:
            result = json.dumps({"error": "Use --info for percentile_stats"})

        data = json.loads(result)
        print(f"Found {data.get('count', 0)} wells")

        if args.output:
            path = export_to_csv(result, args.output)
            print(f"Exported to: {path}")
        else:
            if 'wells' in data and len(data['wells']) > 5:
                data['wells'] = data['wells'][:5]
                data['note'] = 'Showing first 5 wells only. Use -o to export all.'
            print(json.dumps(data, indent=2))
