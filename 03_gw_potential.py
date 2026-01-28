#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Groundwater Potential Module
지하수 Depth + DEM -> Potential 변환

================================================================================
Potential (Hydraulic Head) 개념
================================================================================

Potential = DEM - Depth (모두 미터 단위)

- DEM: 지표면 해발고도 (m) - USGS 3DEP에서 획득
- Depth: 지표면 아래 지하수 깊이 (ft → m 변환) - USGS NWIS에서 획득
- Potential: 지하수의 해발고도 (m) - 지하수 흐름 방향 결정

예시:
    지표면 고도(DEM) = 100m, 지하수 깊이(Depth) = 30m
    → Potential = 100 - 30 = 70m (해발 70m에 지하수면 위치)

================================================================================
논리적 흐름 (Pipeline)
================================================================================

create_potential_dataset() 전체 파이프라인:

    ┌─────────────────────────────────────────────────────────────┐
    │  Input: depth_csv (USGS 지하수 깊이 데이터)                  │
    └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Step 1: DEM 획득 (USGS 3DEP)                               │
    │  - fetch_dem_from_usgs(bbox)                                │
    │  - 각 관측정 좌표의 지표면 고도 추출                         │
    └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Step 2: Potential 계산                                     │
    │  - Depth: ft → m 단위 변환                                  │
    │  - Potential = DEM - Depth                                  │
    └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Output: potential_dataset.csv                              │
    │  - Lat, Lon, Depth_m, DEM_m, Potential_m                    │
    └─────────────────────────────────────────────────────────────┘

================================================================================

Functions:
- calculate_potential: Depth + DEM -> Potential 계산
- create_potential_dataset: 전체 파이프라인
"""

import json
import numpy as np
import pandas as pd
import requests
import os


def fetch_dem_from_usgs(bbox: str, resolution: int = 500) -> tuple:
    """USGS에서 DEM 가져오기"""
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
        "f": "image"
    }

    response = requests.get(url, params=params, timeout=120)

    if response.status_code != 200:
        raise Exception(f"DEM fetch failed: HTTP {response.status_code}")

    import rasterio
    from rasterio.io import MemoryFile

    with MemoryFile(response.content) as memfile:
        with memfile.open() as src:
            dem = src.read(1)

    bounds = {"west": west, "south": south, "east": east, "north": north}
    return dem, bounds


def get_dem_value(lat: float, lon: float, dem: np.ndarray, bounds: dict) -> float:
    """단일 좌표의 DEM 값 추출"""
    if not (bounds["west"] <= lon <= bounds["east"] and
            bounds["south"] <= lat <= bounds["north"]):
        return np.nan

    col = int((lon - bounds["west"]) / (bounds["east"] - bounds["west"]) * dem.shape[1])
    row = int((bounds["north"] - lat) / (bounds["north"] - bounds["south"]) * dem.shape[0])
    col = np.clip(col, 0, dem.shape[1] - 1)
    row = np.clip(row, 0, dem.shape[0] - 1)
    return float(dem[row, col])


def calculate_potential(
    depth_csv: str,
    bbox: str,
    depth_col: str = None,
    depth_unit: str = "ft",
    lat_col: str = "Lat",
    lon_col: str = "Lon",
    output_csv: str = None,
    output_dir: str = None
) -> str:
    """
    지하수 Depth 데이터에 DEM을 결합하여 Potential 계산.

    Potential = DEM - Depth (모두 미터 단위)

    Args:
        depth_csv: Input CSV with groundwater depth data
        bbox: Bounding box as 'west,south,east,north' for DEM fetch
        depth_col: Column name for depth values (auto-detect if None)
        depth_unit: Depth unit - 'ft' (feet) or 'm' (meters), default 'ft'
        lat_col: Latitude column name (default: 'Lat')
        lon_col: Longitude column name (default: 'Lon')
        output_csv: Output CSV filename
        output_dir: Optional output directory

    Returns:
        JSON string with calculation results
    """
    try:
        # CSV 읽기
        df = pd.read_csv(depth_csv)

        # Depth 컬럼 자동 탐지
        if depth_col is None:
            # 날짜 형식 컬럼 찾기 (YYYY-MM-DD)
            date_cols = [c for c in df.columns if '-' in str(c) and len(str(c)) == 10]
            if date_cols:
                depth_col = date_cols[-1]  # 가장 최근 날짜
            else:
                # 숫자 컬럼 중 Lat, Lon 제외
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                exclude = [lat_col, lon_col, 'Site']
                depth_col = [c for c in numeric_cols if c not in exclude][0]

        # DEM 가져오기
        dem, bounds = fetch_dem_from_usgs(bbox)

        # 데이터 준비
        result_df = df[[lat_col, lon_col, depth_col]].copy()
        result_df.columns = ['Lat', 'Lon', 'Depth_original']
        result_df = result_df.dropna()

        # 단위 변환
        if depth_unit.lower() == 'ft':
            result_df['Depth_m'] = result_df['Depth_original'] * 0.3048
        else:
            result_df['Depth_m'] = result_df['Depth_original']

        # DEM 값 추출
        result_df['DEM_m'] = result_df.apply(
            lambda r: get_dem_value(r['Lat'], r['Lon'], dem, bounds), axis=1
        )

        # Potential 계산
        result_df['Potential_m'] = result_df['DEM_m'] - result_df['Depth_m']

        # 유효 데이터만
        result_df = result_df.dropna()

        # 저장
        if output_csv:
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, output_csv)
            else:
                output_path = output_csv

            result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        else:
            output_path = None

        response = {
            "input_csv": depth_csv,
            "depth_column": depth_col,
            "depth_unit": depth_unit,
            "bbox": bbox,
            "total_points": len(result_df),
            "statistics": {
                "depth_m": {
                    "min": round(result_df['Depth_m'].min(), 2),
                    "max": round(result_df['Depth_m'].max(), 2),
                    "mean": round(result_df['Depth_m'].mean(), 2)
                },
                "dem_m": {
                    "min": round(result_df['DEM_m'].min(), 2),
                    "max": round(result_df['DEM_m'].max(), 2),
                    "mean": round(result_df['DEM_m'].mean(), 2)
                },
                "potential_m": {
                    "min": round(result_df['Potential_m'].min(), 2),
                    "max": round(result_df['Potential_m'].max(), 2),
                    "mean": round(result_df['Potential_m'].mean(), 2)
                }
            }
        }

        if output_path:
            response["output_csv"] = output_path

        return json.dumps(response, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


def create_potential_dataset(
    depth_csv: str,
    bbox: str,
    depth_col: str = None,
    depth_unit: str = "ft",
    lat_col: str = "Lat",
    lon_col: str = "Lon",
    resolution: int = 500,
    output_csv: str = None,
    output_dir: str = None
) -> str:
    """
    전체 파이프라인: Potential 계산.

    Kriging 입력 데이터로 바로 사용 가능한 CSV 생성.
    - 관측정: Potential = DEM - Depth

    Args:
        depth_csv: Input CSV with groundwater depth data
        bbox: Bounding box as 'west,south,east,north'
        depth_col: Column name for depth values (auto-detect if None)
        depth_unit: Depth unit - 'ft' or 'm' (default: 'ft')
        lat_col: Latitude column name (default: 'Lat')
        lon_col: Longitude column name (default: 'Lon')
        resolution: DEM resolution (default: 500)
        output_csv: Output CSV filename
        output_dir: Optional output directory

    Returns:
        JSON string with dataset info
    """
    try:
        # CSV 읽기
        df = pd.read_csv(depth_csv)

        # Depth 컬럼 자동 탐지
        if depth_col is None:
            date_cols = [c for c in df.columns if '-' in str(c) and len(str(c)) == 10]
            if date_cols:
                depth_col = date_cols[-1]
            else:
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                exclude = [lat_col, lon_col, 'Site']
                depth_col = [c for c in numeric_cols if c not in exclude][0]

        # DEM 가져오기
        dem, bounds = fetch_dem_from_usgs(bbox, resolution)

        # Potential 계산
        result_df = df[[lat_col, lon_col, depth_col]].copy()
        result_df.columns = ['Lat', 'Lon', 'Depth_original']
        result_df = result_df.dropna()

        if depth_unit.lower() == 'ft':
            result_df['Depth_m'] = result_df['Depth_original'] * 0.3048
        else:
            result_df['Depth_m'] = result_df['Depth_original']

        result_df['DEM_m'] = result_df.apply(
            lambda r: get_dem_value(r['Lat'], r['Lon'], dem, bounds), axis=1
        )
        result_df['Potential_m'] = result_df['DEM_m'] - result_df['Depth_m']
        result_df = result_df.dropna()

        # 최종 출력 컬럼
        result_df = result_df[['Lat', 'Lon', 'Depth_m', 'DEM_m', 'Potential_m']]

        # 저장
        if output_csv:
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, output_csv)
            else:
                output_path = output_csv

            result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        else:
            output_path = None

        response = {
            "input_csv": depth_csv,
            "depth_column": depth_col,
            "bbox": bbox,
            "total_points": len(result_df),
            "statistics": {
                "depth_m": {
                    "min": round(result_df['Depth_m'].min(), 2),
                    "max": round(result_df['Depth_m'].max(), 2),
                    "mean": round(result_df['Depth_m'].mean(), 2)
                },
                "dem_m": {
                    "min": round(result_df['DEM_m'].min(), 2),
                    "max": round(result_df['DEM_m'].max(), 2),
                    "mean": round(result_df['DEM_m'].mean(), 2)
                },
                "potential_m": {
                    "min": round(result_df['Potential_m'].min(), 2),
                    "max": round(result_df['Potential_m'].max(), 2),
                    "mean": round(result_df['Potential_m'].mean(), 2)
                }
            }
        }

        if output_path:
            response["output_csv"] = output_path

        return json.dumps(response, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    # Example usage
    print("=== Groundwater Potential Module ===\n")
    print("This module requires:")
    print("  - depth_csv: CSV file with groundwater depth data")
    print("  - bbox: Bounding box as 'west,south,east,north'")
    print("\nFunctions available:")
    print("  - calculate_potential()")
    print("  - create_potential_dataset()")
