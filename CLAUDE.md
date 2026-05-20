# Hwang Viewer — Claude Code Context

## 현재 버전
v4.2 (2026-05-21)

## 파일
- `dicom_viewer.py` : 메인 단일 파일 (5262 lines)
- `HwangViewer.spec` : PyInstaller 빌드 스펙
- `build.bat` : 가상환경 생성 + 의존성 설치 + PyInstaller 빌드 자동화

## 타이머 출력 예시
```
[TIMER] 1단계 헤더 스캔:     0.420s  (320개 파일, 320개 성공)
[TIMER] 2단계 시리즈 그룹:   0.003s  (8개 시리즈)
[TIMER] 3단계 썸네일 생성:   2.150s  (8개 시리즈, 평균 0.269s/시리즈)
[TIMER] 4단계 패널 로드:     0.380s
[TIMER] ─────────────────────────────────────────
[TIMER] 전체 로딩:           2.953s  (총 320개 파일, 8시리즈)
```

## 로딩 파이프라인 (`_load_path` 함수, ~line 4664)

### 1단계 — 헤더 스캔 ✅ 완료 (v3.1)
- ProcessPoolExecutor(max_workers=max(2, cpu_count)) — GIL 우회
- 폴더 경로 기반 헤더 캐시 (`_header_cache`)
- `_read_dicom_header()` top-level 함수로 분리 (line 38) — pickle 가능

### 2단계 — 시리즈 그룹핑 ✅ 빠름
- SeriesInstanceUID 기준 그룹핑 + InstanceNumber 정렬
- 순수 dict 연산, 병목 아님

### 3단계 — 썸네일 생성 🔴 순차 (개선 여지)
- `_make_thumbnail()` 함수 (line 4220)
- 시리즈 수만큼 순차 for loop
- 중간 슬라이스 선택, 5-95 퍼센타일 자동 W/L
- **병렬화 가능**: numpy 처리는 thread 가능, QPixmap 변환은 main thread 필요

### 4단계 — 패널 로드
- 시리즈 수에 따라 자동 레이아웃 선택 (1x1, 1x2, 2x2, 2x3, 3x3 등)
- 사이드바에 썸네일 + 시리즈 목록 채우기
- `ViewerGrid.load_multi_series()` 호출

## 아키텍처 핵심 사항
- PyQt6 기반 — QPixmap/QImage는 반드시 main thread에서 생성
- 썸네일 병렬화 시: numpy array까지만 thread에서 처리, QPixmap 변환은 main thread
- `multiprocessing.freeze_support()` — PyInstaller EXE에서 다중프로세스 spawn 필수 (line 5260)
- 헤더 캐시 `_header_cache`: 같은 폴더 재로드 시 1단계 스킵

## 주요 클래스 위치

| 클래스 | Line | 역할 |
|--------|------|------|
| `LocaleManager` | 627 | i18n 싱글톤 (한국어, 영어, 스페인어, 일본어) |
| `GroupSyncManager` | 904 | 멀티패널 슬라이스 동기화 관리 |
| `AutoSizeLabel` | 1083 | 동적 폰트 크기 자동 조정 라벨 |
| `DicomPanel` | 1130 | 단일 슬라이스 뷰어 (W/L, 줌, 팬, 어노테이션) |
| `BValueOverlay` | 2738 | DWI b-value 필터 오버레이 |
| `SyncBadge` | 2832 | 패널별 그룹 동기화 뱃지 (클릭으로 토글) |
| `ViewerGrid` | 2882 | 멀티패널 레이아웃 그리드 |
| `_AreaSelector` | 3430 | ROI 영역 선택 위젯 (Ctrl+Alt+C) |
| `_LayoutPicker` | 3522 | 레이아웃 선택 다이얼로그 |
| `SeriesSidebar` | 3622 | 왼쪽 사이드바 (시리즈 목록 + 썸네일) |
| `LoadingWindow` | 3787 | 4단계 진행 상황 표시 스플래시 화면 |
| `DicomViewer` | 3894 | 메인 윈도우 (QMainWindow) |

## 주요 함수 위치

| 함수 | Line | 역할 |
|------|------|------|
| `_read_dicom_header()` | 38 | ProcessPoolExecutor용 top-level 헤더 읽기 |
| `DicomPanel.load_series()` | 1193 | 패널에 시리즈 로드, 픽셀 캐시·W/L 초기화 |
| `DicomPanel._render()` | 1295 | 현재 슬라이스 QPixmap 렌더 |
| `ViewerGrid.load_multi_series()` | 3173 | 여러 패널에 시리즈 분배 |
| `DicomViewer._make_thumbnail()` | 4220 | 144×144 썸네일 생성 |
| `DicomViewer._load_path()` | 4664 | 4단계 로딩 파이프라인 오케스트레이터 |

## v4.1 주요 신기능 (v3.1 대비)

- **멀티패널 그리드** — ViewerGrid: 1×1~3×3 레이아웃, 자동 선택 + 수동 선택(_LayoutPicker)
- **SeriesSidebar** — 왼쪽 사이드바에 시리즈 목록 + 썸네일, 더블클릭으로 패널 로드
- **LoadingWindow** — 4단계 진행 스플래시 화면 (stage별 프로그레스바)
- **GroupSyncManager + SyncBadge** — 멀티패널 슬라이스 동기화, 클릭으로 그룹 토글
- **BValueOverlay** — DWI 멀티-b-value 자동 감지 + 필터 드롭다운
- **어노테이션** — 거리 측정(캘리퍼), 화살표, 텍스트, ROI 통계; 드래그 이동
- **_AreaSelector** — Ctrl+Alt+C로 ROI 직사각형 선택 → 클립보드 복사
- **i18n** — LocaleManager: 한국어/영어/스페인어/일본어 지원
- **크로스 레퍼런스** — 멀티패널 클릭 시 십자선 동기화
- **패닝 모드(P)** — Shift+드래그로 패널 위치 조정 (간격/오버랩)
- **레이아웃 상태 유지** — 레이아웃 변경 시 W/L·줌·어노테이션 상태 복원

## 실행 환경
- Windows (개발/배포 대상)
- Python 3.10+
- `pip install pydicom pyqt6 numpy pylibjpeg`

## 배포
- `build.bat` 실행: 가상환경 생성 → 의존성 설치 → PyInstaller 빌드
- `HwangViewer.spec` 기준 단독 EXE 생성 (~60-80 MB)
- Hidden imports: pydicom, pydicom.pixels.decoders.*, pylibjpeg, numpy
- Excludes: tkinter, matplotlib, scipy, pandas, PIL, PySide6, PyQt5
- C extension / .pyd 추가 시 spec 파일도 같이 수정 필요
