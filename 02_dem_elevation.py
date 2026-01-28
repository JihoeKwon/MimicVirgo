#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEM (Digital Elevation Model) Module
USGS 3DEP National Map에서 DEM 데이터를 가져오는 모듈

================================================================================
설계 원칙: DEM과 Sea Mask의 분리
================================================================================

이 모듈은 순수하게 DEM(지형 고도) 데이터만 다룹니다.
바다/해양 영역 탐지는 별도의 sea_mask 모듈에서 담당합니다.

분리 이유:
    DEM 기반 Flood Fill로 바다를 탐지하는 방식은 다음과 같은 문제가 있습니다:

    1. 내륙 저지대 오탐지
       - Death Valley (-86m), Salton Sea (-69m) 등 해수면 이하 내륙 분지가
         flood fill에 의해 바다로 잘못 분류됨

    2. Flood Fill 전파 오류
       - 강 하구, 삼각주 저지대를 통해 바다 마스크가 내륙으로 확산
       - 좁은 지협이 DEM 해상도에서 누락되면 내륙 호수가 바다와 연결

    3. 책임 분리 (Separation of Concerns)
       - DEM: 지형 고도 데이터 제공 (USGS 3DEP)
       - Sea Mask: 해양 경계 정의 (Natural Earth polygon)
       - 각 데이터 소스의 장점을 살린 독립적 처리

권장 워크플로우:
    1. dem.get_dem() → 지형 고도 획득
    2. sea_mask.detect_sea_area() → 해양 영역 마스크 (Natural Earth 기반)
    3. potential.create_potential_dataset() → DEM + Depth → Potential 계산
       (내부적으로 sea_mask 사용)

================================================================================

Functions:
- fetch_dem_from_usgs: USGS에서 DEM 데이터 가져오기
- get_dem: bounding box 영역의 DEM 데이터 가져오기
- get_dem_at_points: 특정 좌표들의 DEM 값 추출
"""

import json
import numpy as np
import requests
from io import BytesIO
import os


def fetch_dem_from_usgs(bbox: str, resolution: int = 500) -> dict:
    """
    USGS National Map에서 DEM 데이터 가져오기

    Args:
        bbox: 'west,south,east,north' 형식
        resolution: 픽셀 해상도 (기본 500x500)

    Returns:
        dict with dem array, bounds, transform info
    """
    west, south, east, north = map(float, bbox.split(','))

    url = (
        "https://elevation.nationalmap.gov/arcgis/rest/services/"
        "3DEPElevation/ImageServer/exportImage"
    )

    params = {
        "bbox": f"{west},{south},{east},{north}",
        "bboxSR": 4326,
        "size": f"{resolution},{resolution}",
        "imageSR": 4326,
        "format": "tiff",
        "pixelType": "F32",
        "noDataInterpretation": "esriNoDataMatchAny",
        "interpolation": "+RSP_BilinearInterpolation",
        "f": "image"
    }

    response = requests.get(url, params=params, timeout=120)

    if response.status_code != 200:
        raise Exception(f"DEM fetch failed: HTTP {response.status_code}")

    # rasterio로 메모리에서 읽기
    import rasterio
    from rasterio.io import MemoryFile

    with MemoryFile(response.content) as memfile:
        with memfile.open() as src:
            dem = src.read(1)
            transform = src.transform
            crs = src.crs

    return {
        "dem": dem,
        "bounds": {"west": west, "south": south, "east": east, "north": north},
        "shape": dem.shape,
        "transform": transform,
        "crs": str(crs),
        "pixel_size_deg": (east - west) / dem.shape[1],
        "pixel_size_m": (east - west) / dem.shape[1] * 111000  # 대략적 미터 환산
    }


def get_dem(
    bbox: str,
    resolution: int = 500,
    output_tif: str = None,
    output_dir: str = None
) -> str:
    """
    Bounding box 영역의 DEM 데이터 가져오기.

    Args:
        bbox: Bounding box as 'west,south,east,north' (e.g., '-117.5,32.5,-116.5,33.5')
        resolution: Pixel resolution (default: 500, max: 2000)
        output_tif: Optional GeoTIFF filename to save
        output_dir: Optional output directory

    Returns:
        JSON string with DEM statistics and file path
    """
    try:
        result = fetch_dem_from_usgs(bbox, min(resolution, 2000))
        dem = result["dem"]
        bounds = result["bounds"]

        response = {
            "bbox": bbox,
            "shape": list(result["shape"]),
            "crs": result["crs"],
            "pixel_size_m": round(result["pixel_size_m"], 2),
            "statistics": {
                "min": round(float(np.nanmin(dem)), 2),
                "max": round(float(np.nanmax(dem)), 2),
                "mean": round(float(np.nanmean(dem)), 2),
                "std": round(float(np.nanstd(dem)), 2)
            }
        }

        # GeoTIFF 저장
        if output_tif:
            import rasterio
            from rasterio.transform import from_bounds

            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, output_tif)
            else:
                output_path = output_tif

            transform = from_bounds(
                bounds["west"], bounds["south"],
                bounds["east"], bounds["north"],
                dem.shape[1], dem.shape[0]
            )

            with rasterio.open(
                output_path, 'w',
                driver='GTiff',
                height=dem.shape[0],
                width=dem.shape[1],
                count=1,
                dtype=dem.dtype,
                crs='EPSG:4326',
                transform=transform,
            ) as dst:
                dst.write(dem, 1)

            response["output_tif"] = output_path

        return json.dumps(response, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def get_dem_at_points(
    bbox: str,
    points_csv: str,
    lat_col: str = "Lat",
    lon_col: str = "Lon",
    output_csv: str = None,
    output_dir: str = None
) -> str:
    """
    CSV 파일의 좌표들에 대한 DEM 값 추출.

    Args:
        bbox: Bounding box as 'west,south,east,north'
        points_csv: Input CSV file with coordinates
        lat_col: Latitude column name (default: 'Lat')
        lon_col: Longitude column name (default: 'Lon')
        output_csv: Optional output CSV filename with DEM values added
        output_dir: Optional output directory

    Returns:
        JSON string with DEM values for each point
    """
    import pandas as pd

    try:
        # DEM 가져오기
        result = fetch_dem_from_usgs(bbox)
        dem = result["dem"]
        bounds = result["bounds"]

        # CSV 읽기
        df = pd.read_csv(points_csv)

        if lat_col not in df.columns or lon_col not in df.columns:
            return json.dumps({"error": f"Columns '{lat_col}' or '{lon_col}' not found"})

        # 각 포인트의 DEM 값 추출
        def get_value(lat, lon):
            if not (bounds["west"] <= lon <= bounds["east"] and
                    bounds["south"] <= lat <= bounds["north"]):
                return np.nan

            col = int((lon - bounds["west"]) / (bounds["east"] - bounds["west"]) * dem.shape[1])
            row = int((bounds["north"] - lat) / (bounds["north"] - bounds["south"]) * dem.shape[0])
            col = np.clip(col, 0, dem.shape[1] - 1)
            row = np.clip(row, 0, dem.shape[0] - 1)
            return float(dem[row, col])

        df['DEM_m'] = df.apply(lambda r: get_value(r[lat_col], r[lon_col]), axis=1)

        # 결과 저장
        if output_csv:
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, output_csv)
            else:
                output_path = output_csv

            df.to_csv(output_path, index=False, encoding='utf-8-sig')
        else:
            output_path = None

        # 통계
        valid_dem = df['DEM_m'].dropna()

        response = {
            "bbox": bbox,
            "input_csv": points_csv,
            "total_points": len(df),
            "points_with_dem": len(valid_dem),
            "dem_statistics": {
                "min": round(valid_dem.min(), 2) if len(valid_dem) > 0 else None,
                "max": round(valid_dem.max(), 2) if len(valid_dem) > 0 else None,
                "mean": round(valid_dem.mean(), 2) if len(valid_dem) > 0 else None
            }
        }

        if output_path:
            response["output_csv"] = output_path

        return json.dumps(response, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    # Example usage
    print("=== DEM Elevation Module ===\n")

    # Example: San Diego area
    bbox = "-117.5,32.5,-116.5,33.5"

    print(f"Fetching DEM for bbox: {bbox}")
    result = get_dem(bbox, resolution=500)
    print(result)
