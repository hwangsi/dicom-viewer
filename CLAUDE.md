# Hwang Viewer — Claude Code Context

## 현재 버전
v3.1 (2026-05-03)

## 현재 목표
**로딩 속도 최적화 완료 (v3.1)**
- 1단계 헤더 스캔: ProcessPoolExecutor(cpu_count) 적용
- 폴더 경로 기반 헤더 캐시 (_header_cache) 구현
- 다음 목표: 3단계 썸네일 병렬화

## 파일
- `dicom_viewer.py` : 메인 단일 파일 (3900+ lines)

## 타이머 출력 예시
```
[TIMER] 1단계 헤더 스캔:        0.420s  (320파일, 320성공)
[TIMER] 2단계 그룹핑:           0.003s  (8개 시리즈)
[TIMER] 3단계 썸네일 생성:      2.150s  (8개 시리즈, 평균 0.269s/시리즈)
[TIMER] 4단계 이미지 패널 로드: 0.380s
[TIMER] ─────────────────────────────────────────
[TIMER] 전체 로딩:              2.953s  (총 320파일, 8시리즈)
```

## 로딩 파이프라인 (dicom_viewer.py: `_load_path` 함수, ~line 3414)

### 1단계 — 헤더 스캔 ✅ 완료 (v3.1)
- ProcessPoolExecutor(max_workers=cpu_count) — GIL 우회
- 폴더 경로 + 파일 수 기반 캐시 (_header_cache)
- freeze_support() 추가 (PyInstaller EXE 호환)

### 2단계 — 그룹핑 ✅ 빠름
- 순수 dict 연산, 병목 아님

### 3단계 — 썸네일 생성 🔴 병목
- `_make_thumbnail()` 함수 (~line 3142)
- 시리즈 수만큼 순차 for loop
- 각 시리즈마다 full pixel dcmread (stop_before_pixels 없음)
- **병렬화로 개선 가능**

### 4단계 — 첫 이미지 패널 로드
- load_to_active / load_multi_series 호출
- pixel 디코딩 + render 포함

## 아키텍처 핵심 사항
- PyQt6 기반 — QPixmap/QImage는 반드시 main thread에서 생성
- `_make_thumbnail`의 numpy 처리는 thread 가능, QPixmap 변환은 main thread 필요
- 썸네일 병렬화 시: numpy array까지만 thread에서 처리, QPixmap 변환은 main thread

## 최적화 계획 (Claude Code 작업 지시용)

### 우선 할 일: 타이머 데이터 수집
```
python dicom_viewer.py
```
실제 전립선 MRI 폴더 열고 콘솔 출력 확인

### 그 다음: 썸네일 병렬화
`_make_thumbnail`을 두 단계로 분리:
1. `_make_thumbnail_array(pairs)` → np.ndarray (thread-safe, parallel OK)
2. main thread에서 ndarray → QPixmap 변환

ThreadPoolExecutor로 1번을 병렬 실행 후, 2번을 main thread에서 일괄 변환

## 주요 클래스/함수 위치
- `DicomViewer._load_path()` : 메인 로딩 함수 (~line 3414)
- `DicomViewer._make_thumbnail()` : 썸네일 생성 (~line 3142)
- `DicomPanel.load_series()` : 패널에 시리즈 로드
- `DicomPanel._render()` : 픽셀 디코딩 + 화면 렌더
- `ViewerGrid.load_multi_series()` : 여러 패널 동시 로드(~line 2432)

## 실행 환경
- Windows (개발/배포 대상)
- Python 3.10+
- pip install pydicom pyqt6 numpy pylibjpeg

## 배포
- PyInstaller로 단독 EXE 빌드 (HwangViewer.spec)
- 모든 최적화는 EXE 빌드 호환 필수
- C extension / .pyd 추가 시 spec 파일도 같이 수정 필요
