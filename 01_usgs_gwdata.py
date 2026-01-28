"""
USGS Groundwater Info Module
- Fetch groundwater data by bounding box
- Support single date or date range queries
- Filter by aquifer type
- Export to CSV
"""

import json
import os
import requests
from datetime import datetime


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


def _get_sites_by_bbox(bbox, aquifer_type='U', timeout=120):
    """
    Internal: Fetch groundwater monitoring sites within a bounding box.

    Returns:
        tuple: (list of site codes, dict of site info)
    """
    site_url = 'https://waterservices.usgs.gov/nwis/site/'
    site_params = {
        'format': 'rdb',
        'bBox': bbox,
        'siteType': 'GW',
        'siteOutput': 'expanded',
        'siteStatus': 'active'
    }

    response = requests.get(site_url, params=site_params, timeout=timeout)

    if response.status_code != 200:
        return [], {}

    target_sites = []
    site_info = {}

    lines = response.text.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('agency_cd'):
            headers = line.split('\t')
            site_idx = headers.index('site_no')
            type_idx = headers.index('aqfr_type_cd')
            name_idx = headers.index('station_nm')
            lat_idx = headers.index('dec_lat_va')
            lon_idx = headers.index('dec_long_va')

            for data_line in lines[i+2:]:
                if data_line.strip() and not data_line.startswith('#'):
                    values = data_line.split('\t')
                    if len(values) > type_idx:
                        aq_type = values[type_idx]
                        if aq_type == aquifer_type:
                            site = values[site_idx]
                            target_sites.append(site)
                            site_info[site] = {
                                'name': values[name_idx] if name_idx < len(values) else '',
                                'lat': values[lat_idx] if lat_idx < len(values) else '',
                                'lon': values[lon_idx] if lon_idx < len(values) else ''
                            }
            break

    return target_sites, site_info


def _fetch_groundwater_data(sites, start_date, end_date=None, timeout=120):
    """
    Internal: Fetch groundwater data for given sites.

    Returns:
        tuple: (dict of site data, set of dates)
    """
    if end_date is None:
        end_date = start_date

    data_url = 'https://waterservices.usgs.gov/nwis/dv/'
    data_params = {
        'format': 'json',
        'sites': ','.join(sites),
        'parameterCd': '72019',  # Depth to water level
        'startDT': start_date,
        'endDT': end_date
    }

    resp = requests.get(data_url, params=data_params, timeout=timeout)

    if resp.status_code != 200:
        return {}, set()

    data = resp.json()
    ts_list = data.get('value', {}).get('timeSeries', [])

    all_data = {}  # {site: {date: value}}
    all_dates = set()

    for ts in ts_list:
        vlist = ts.get('values', [{}])[0].get('value', [])
        valid = [v for v in vlist if float(v.get('value', -999999)) > -9999]

        if valid:
            si = ts['sourceInfo']
            code = si['siteCode'][0]['value']

            if code not in all_data:
                all_data[code] = {}

            for v in valid:
                date = v['dateTime'][:10]
                all_dates.add(date)
                all_data[code][date] = float(v['value'])

    return all_data, all_dates


def _save_to_csv(all_data, all_dates, site_info, output_file, include_change=True):
    """
    Internal: Save groundwater data to CSV file.
    """
    sorted_dates = sorted(all_dates)

    with open(output_file, 'w', encoding='utf-8-sig') as f:
        # Header
        header = ['Site', 'Name', 'Lat', 'Lon'] + sorted_dates
        if include_change and len(sorted_dates) > 1:
            header.append('Change')
        f.write(','.join(header) + '\n')

        # Data rows
        for site in sorted(all_data.keys()):
            info = site_info.get(site, {})
            name = info.get('name', '').replace('"', "'")
            row = [
                site,
                f'"{name}"',
                str(info.get('lat', '')),
                str(info.get('lon', ''))
            ]

            # Date values
            values_list = []
            for date in sorted_dates:
                val = all_data[site].get(date, '')
                if val != '':
                    row.append(f'{val:.2f}')
                    values_list.append(val)
                else:
                    row.append('')

            # Calculate change (last - first)
            if include_change and len(sorted_dates) > 1:
                if len(values_list) >= 2:
                    change = values_list[-1] - values_list[0]
                    row.append(f'{change:.2f}')
                else:
                    row.append('')

            f.write(','.join(row) + '\n')

    return output_file


def get_groundwater_sites(
    bbox: str,
    aquifer_type: str = "U"
) -> str:
    """
    Get groundwater monitoring sites within a bounding box.

    Args:
        bbox: Bounding box as 'west,south,east,north' (e.g., '-117.5,32.5,-116.5,33.5')
        aquifer_type: Aquifer type - 'U' (Unconfined), 'C' (Confined), 'X' (Mixed), 'M' (Multiple)

    Returns:
        JSON string with site information
    """
    sites, site_info = _get_sites_by_bbox(bbox, aquifer_type)

    site_list = []
    for site_no in sites:
        info = site_info.get(site_no, {})
        site_list.append({
            'site_no': site_no,
            'name': info.get('name', ''),
            'lat': float(info['lat']) if info.get('lat') else None,
            'lon': float(info['lon']) if info.get('lon') else None,
            'aquifer_type': aquifer_type
        })

    return json.dumps({
        "bbox": bbox,
        "aquifer_type": aquifer_type,
        "count": len(site_list),
        "sites": site_list
    }, indent=2)


def get_groundwater_data(
    bbox: str,
    start_date: str,
    end_date: str,
    aquifer_type: str = "U",
    output_csv: str = None,
    output_dir: str = None
) -> str:
    """
    Fetch groundwater level data for a bounding box and date range.

    Args:
        bbox: Bounding box as 'west,south,east,north' (e.g., '-117.5,32.5,-116.5,33.5')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        aquifer_type: Aquifer type - 'U' (Unconfined), 'C' (Confined)
        output_csv: Optional CSV filename to save results
        output_dir: Optional output directory (created if not exists)

    Returns:
        JSON string with groundwater data
    """
    # Step 1: Get sites
    target_sites, site_info = _get_sites_by_bbox(bbox, aquifer_type)

    if not target_sites:
        return json.dumps({
            "error": "No sites found",
            "bbox": bbox,
            "aquifer_type": aquifer_type
        })

    # Step 2: Fetch data
    all_data, all_dates = _fetch_groundwater_data(target_sites, start_date, end_date)

    if not all_data:
        return json.dumps({
            "error": "No data available for the specified date range",
            "bbox": bbox,
            "start_date": start_date,
            "end_date": end_date
        })

    # Step 3: Save to CSV if requested
    output_path = None
    if output_csv:
        output_path = _get_output_path(output_csv, output_dir)
        _save_to_csv(all_data, all_dates, site_info, output_path, include_change=True)

    # Build response with full data
    data_response = {}
    for site in all_data:
        info = site_info.get(site, {})
        data_response[site] = {
            'name': info.get('name', ''),
            'lat': info.get('lat', ''),
            'lon': info.get('lon', ''),
            'values': all_data[site]
        }

    # Calculate statistics
    all_values = []
    for site_data in all_data.values():
        all_values.extend(site_data.values())

    stats = None
    if all_values:
        stats = {
            'min': min(all_values),
            'max': max(all_values),
            'mean': sum(all_values) / len(all_values)
        }

    return json.dumps({
        "bbox": bbox,
        "start_date": start_date,
        "end_date": end_date,
        "aquifer_type": aquifer_type,
        "sites_found": len(target_sites),
        "sites_with_data": len(all_data),
        "date_count": len(all_dates),
        "dates": sorted(list(all_dates)),
        "stats": stats,
        "output_csv": output_path,
        "output_dir": output_dir,
        "data": data_response
    }, indent=2)


def get_groundwater_data_single_date(
    bbox: str,
    date: str,
    aquifer_type: str = "U",
    output_csv: str = None,
    output_dir: str = None
) -> str:
    """
    Fetch groundwater level data for a bounding box and single date.

    Args:
        bbox: Bounding box as 'west,south,east,north' (e.g., '-117.5,32.5,-116.5,33.5')
        date: Target date (YYYY-MM-DD)
        aquifer_type: Aquifer type - 'U' (Unconfined), 'C' (Confined)
        output_csv: Optional CSV filename to save results
        output_dir: Optional output directory (created if not exists)

    Returns:
        JSON string with groundwater data
    """
    # Step 1: Get sites
    target_sites, site_info = _get_sites_by_bbox(bbox, aquifer_type)

    if not target_sites:
        return json.dumps({
            "error": "No sites found",
            "bbox": bbox,
            "aquifer_type": aquifer_type
        })

    # Step 2: Fetch data (single day)
    all_data, all_dates = _fetch_groundwater_data(target_sites, date, date)

    if not all_data:
        return json.dumps({
            "error": "No data available for the specified date",
            "bbox": bbox,
            "date": date
        })

    # Step 3: Save to CSV if requested
    output_path = None
    if output_csv:
        output_path = _get_output_path(output_csv, output_dir)
        _save_to_csv(all_data, all_dates, site_info, output_path, include_change=False)

    # Build response
    data_response = {}
    for site in all_data:
        info = site_info.get(site, {})
        data_response[site] = {
            'name': info.get('name', ''),
            'lat': info.get('lat', ''),
            'lon': info.get('lon', ''),
            'value': all_data[site].get(date, None)
        }

    return json.dumps({
        "bbox": bbox,
        "date": date,
        "aquifer_type": aquifer_type,
        "sites_found": len(target_sites),
        "sites_with_data": len(all_data),
        "output_csv": output_path,
        "output_dir": output_dir,
        "data": data_response
    }, indent=2)


def get_site_history(
    site_no: str,
    days: int = 365
) -> str:
    """
    Get historical groundwater data for a specific site.

    Args:
        site_no: USGS site number (e.g., '323527117050001')
        days: Number of days of history (default: 365)

    Returns:
        JSON string with historical data
    """
    url = 'https://waterservices.usgs.gov/nwis/dv/'
    params = {
        'format': 'json',
        'sites': site_no,
        'parameterCd': '72019',
        'period': f'P{days}D',
        'siteStatus': 'all'
    }

    response = requests.get(url, params=params, timeout=60)

    if response.status_code != 200:
        return json.dumps({"error": f"API error: {response.status_code}"})

    data = response.json()
    ts_list = data.get('value', {}).get('timeSeries', [])

    records = []
    site_name = ''

    for ts in ts_list:
        si = ts.get('sourceInfo', {})
        site_name = si.get('siteName', '')
        geo = si.get('geoLocation', {}).get('geogLocation', {})

        vlist = ts.get('values', [{}])[0].get('value', [])
        for v in vlist:
            if float(v.get('value', -999999)) > -9999:
                records.append({
                    'date': v['dateTime'][:10],
                    'depth_ft': float(v['value'])
                })

    return json.dumps({
        "site_no": site_no,
        "site_name": site_name,
        "days": days,
        "record_count": len(records),
        "records": records
    }, indent=2)


if __name__ == "__main__":
    # Example usage
    print("=== USGS Groundwater Data Module ===\n")

    # Example: San Diego area
    bbox = "-117.5,32.5,-116.5,33.5"

    print(f"Fetching groundwater sites for bbox: {bbox}")
    result = get_groundwater_sites(bbox, aquifer_type="U")
    print(result)
