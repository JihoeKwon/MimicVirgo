# MimicVirgo 작업 로그

## 2025-01-28

### 팝업 차트 공백 문제 해결
- **문제**: Scatter 마커 클릭 시 Historical Percentile 차트와 시계열 차트가 실제 그래프보다 세로로 공간을 많이 차지하며 공백이 크게 보이는 문제
- **해결**:
  - CSS에 `min-height: 0 !important` 추가하여 Plotly 컨테이너 높이 제어
  - JavaScript에서 `autosize: false` 설정 및 고정 높이 적용
  - `.main-svg` 요소에도 `height: auto` 적용

### 팝업 드래그 이동 기능 추가
- 팝업 헤더(파란색 제목 영역)를 마우스로 드래그하여 위치 이동 가능
- CSS: `cursor: move`, `user-select: none` 추가
- JavaScript: `setupResizeEvents()` 함수에 드래그 로직 추가
- 화면 경계를 벗어나지 않도록 제한

### 프로젝트 정리
- 임시 파일 삭제 (*.tmp.* 약 40개)
- 스크린샷 파일 삭제 (screenshot*.png 약 20개)
- 테스트 파일 삭제 (test_*.png, test_*.html 약 50개)
- images 폴더 삭제
- 성공한 코드 백업: `sandiego_popup_final.html`

### README.md 작성
- 프로젝트 개요 (Virgo 벤치마킹, AEGIS 활용 계획)
- 주요 기능 설명
- 프로젝트 구조
- 데이터 소스 (CADWR, USGS)
- 기술 스택
- 설치 및 실행 방법
- 개발자 정보: 권지회 (KIGAM AI융합연구실)
- 저작권: 한국지질자원연구원 (KIGAM)

### README.md 업데이트
- 데모 GIF 추가 (`docs/demo.gif`)
  - 지도 초기 화면 → 줌 인 → 팝업 열기 (332114N1173775W001)
- CADWR 수집 데이터 필드 상세 설명 추가
  - site_no, name, lat/lon, county, basin_name
  - depth_ft, gwe_ft, gse_ft, change
  - pct_lowest ~ pct_highest, percentile_class
- 지도 레이어 출처 명시
  - CARTO Positron (OpenStreetMap)
  - NASA ASTER GDEM Shaded Relief
- 개발자/저작권 정보를 개요 위로 이동

### GitHub 저장소 초기화 및 Push
- 저장소: https://github.com/JihoeKwon/MimicVirgo
- 커밋 목록:
  1. Initial commit: MimicVirgo groundwater monitoring platform
  2. Add developer and copyright information
  3. Add popup drag-to-move functionality
  4. Add demo GIF to README
  5. Update demo GIF
  6. Add CADWR data fields and map layer sources to README
  7. Move developer and copyright info to top of README

### 커밋된 파일 목록
```
.gitignore
README.md
mapservice.py
cadwr_gwinfo.py
usgs_gwinfo.py
01_usgs_gwdata.py
02_dem_elevation.py
03_gw_potential.py
sandiego_popup_final.html
static/mapservice.css
static/mapservice.js
take_screenshot.py
docs/demo.gif
```

---

## 기술 상세

### 차트 공백 해결 - CSS 변경사항
```css
#pctChartArea .js-plotly-plot,
#chartArea .js-plotly-plot {
    height: auto !important;
    min-height: 0 !important;
}

#pctChartArea .main-svg,
#chartArea .main-svg {
    height: auto !important;
}
```

### 드래그 기능 - JavaScript 핵심 로직
```javascript
// Drag by header
else if (e.target.classList.contains('popup-header') || e.target.closest('.popup-header')) {
    if (!e.target.classList.contains('close-popup')) {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        startLeft = popup.offsetLeft;
        startTop = popup.offsetTop;
        popup.style.transform = 'none';
        e.preventDefault();
    }
}
```
