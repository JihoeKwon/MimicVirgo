# MimicVirgo

NASA JPL [Virgo](https://wwao.jpl.nasa.gov/media/virgo) 플랫폼을 벤치마킹하여 개발한 지하수 모니터링 가시화 서비스입니다.

## 개요

이 프로젝트는 California Department of Water Resources (CADWR) API로부터 지하수 데이터를 수집하여 인터랙티브 지도 상에 가시화합니다. Virgo 플랫폼의 핵심 기능을 분석하고 재현하여, 향후 **대한민국 지하수 정보 플랫폼 AEGIS** 구현의 기반 기술로 활용될 예정입니다.

## 주요 기능

- **실시간 지하수 데이터 수집**: CADWR API를 통한 캘리포니아 지하수 관측정 데이터 수집
- **인터랙티브 지도 가시화**: Plotly 기반의 지도 위에 관측정 위치 및 수위 변화 표시
- **팝업 상세 정보**:
  - 관측정 기본 정보 (위치, 카운티, 유역 등)
  - Historical Percentile Distribution 차트
  - 시계열 수위 변화 그래프
  - 통계 요약 (최소/최대/평균/변화량)
- **레이어 컨트롤**: 데이터 소스별 레이어 표시/숨김
- **지도 컨트롤**: 줌 인/아웃, 홈 위치 이동, 스케일 바

## 프로젝트 구조

```
MimicVirgo/
├── mapservice.py              # 메인 지도 서비스 생성 모듈
├── cadwr_gwinfo.py            # CADWR API 데이터 수집 모듈
├── usgs_gwinfo.py             # USGS 지하수 데이터 수집 모듈
├── 01_usgs_gwdata.py          # USGS 데이터 처리 스크립트
├── 02_dem_elevation.py        # DEM 고도 데이터 처리
├── 03_gw_potential.py         # 지하수 잠재량 분석
├── sandiego_popup_final.html  # 최종 팝업 기능 포함 지도 (백업)
├── sandiego_test.html         # 개발/테스트용 지도
├── take_screenshot.py         # 테스트용 스크린샷 스크립트
└── static/                    # 정적 파일 (CSS, JS)
```

## 데이터 소스

| 소스 | 설명 | API |
|------|------|-----|
| CADWR | California Department of Water Resources | [CADWR Open Data](https://data.cnra.ca.gov/) |
| USGS | U.S. Geological Survey | [USGS Water Services](https://waterservices.usgs.gov/) |

## 기술 스택

- **Backend**: Python 3.x
- **Data Processing**: Pandas, NumPy
- **Visualization**: Plotly, Mapbox/MapLibre GL
- **Base Map**: CARTO Positron + NASA ASTER GDEM Shaded Relief
- **Frontend**: HTML5, CSS3, JavaScript

## 설치 및 실행

### 요구사항

```bash
pip install plotly pandas requests
```

### 데이터 수집 및 지도 생성

```python
from cadwr_gwinfo import CADWRGroundwaterAPI
from mapservice import GroundwaterMapService

# CADWR 데이터 수집
api = CADWRGroundwaterAPI()
data = api.get_groundwater_data(county="San Diego")

# 지도 생성
map_service = GroundwaterMapService()
map_service.create_map(data, output_file="groundwater_map.html")
```

## 스크린샷

### 메인 지도 뷰
- 관측정 위치를 색상으로 구분 (수위 변화량 기준)
- 우측 레이어 패널에서 데이터 소스 선택
- 좌측 하단 컨트롤 버튼 (줌, 홈, 정보)

### 팝업 상세 정보
- 관측정 메타데이터
- Historical Percentile Distribution (수평 막대 차트)
- 시계열 수위 변화 그래프
- 통계 요약 카드

## 향후 계획

1. **AEGIS 플랫폼 적용**: 대한민국 지하수 정보 시스템에 본 기술 적용
2. **추가 데이터 소스**: 한국수자원공사, 환경부 지하수 데이터 연동
3. **예측 모델 통합**: 머신러닝 기반 지하수위 예측 기능 추가
4. **실시간 모니터링**: 자동 데이터 갱신 및 알림 시스템

## 참고 자료

- [NASA JPL Virgo Platform](https://wwao.jpl.nasa.gov/media/virgo)
- [CADWR Groundwater Data](https://data.cnra.ca.gov/)
- [USGS National Water Information System](https://waterdata.usgs.gov/nwis)

## 라이선스

This project is for research and development purposes.

---

*이 프로젝트는 NASA JPL Virgo 플랫폼의 기능을 참고하여 개발되었으며, 원본 플랫폼과는 별개의 독립적인 구현입니다.*
