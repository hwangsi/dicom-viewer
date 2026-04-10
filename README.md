# DICOM Viewer — Lecture Edition

강의 자료(PPT) 제작을 위한 가볍고 빠른 Windows DICOM 뷰어  
단일 Python 파일로 실행 가능합니다.

## 설치

```bash
pip install pydicom pyqt6 numpy pylibjpeg
```

## 실행

```bash
python dicom_viewer.py
```

## 주요 기능

- **1×1 / 2×2 레이아웃** — 최대 4개 시리즈 동시 표시
- **시리즈 페이지 네비게이션** — ◀ ▶ 버튼으로 4개씩 순환
- **1 시리즈 → 2×2** — 같은 시리즈를 20/40/60/80% 위치로 균등 분배
- **DICOM 태그 오버레이 ON/OFF** — T 키로 토글 (환자 정보, MR 파라미터 등)
- **빠른 로딩** — 헤더만 병렬 스캔 후 시리즈 목록 즉시 표시, 픽셀은 지연 로딩
- **픽셀 캐시** — 최근 40장 메모리 보관으로 스크롤 시 빠른 응답
- **Ctrl+C → 클립보드 → PPT 바로 붙여넣기** (캡처 시 선택 테두리 자동 제거)
- 드래그&드롭으로 파일/폴더 열기

## 조작법

| 동작 | 기능 |
|------|------|
| 마우스 우클릭 드래그 **좌우** | Window Width 조절 |
| 마우스 우클릭 드래그 **상하** | Window Level 조절 |
| 마우스 좌클릭 드래그 **상하** | 슬라이스 이동 |
| 스크롤 휠 | 슬라이스 이동 |
| **Ctrl** + 스크롤 | 확대 / 축소 |
| **Space** | 활성 패널 1×1 확대 ↔ 2×2 복원 |
| **T** | DICOM 태그 오버레이 ON/OFF |
| **R** | W/L + Zoom 리셋 |
| **Ctrl+1 / Ctrl+2** | 1×1 / 2×2 레이아웃 전환 |
| **Ctrl+C** | 활성 패널 → 클립보드 |
| **Ctrl+Shift+C** | 전체 패널 → 클립보드 |
| **Ctrl+S** | 활성 패널 PNG/JPG 저장 |
| 시리즈 목록 더블클릭 | 해당 시리즈를 활성 패널에 로드 |
| 파일 / 폴더 드래그&드롭 | 바로 열기 |

## DICOM 태그 오버레이 위치

| 위치 | 표시 내용 |
|------|-----------|
| 상단 좌 | 환자명, ID, 성별/나이, 검사일, Modality |
| 상단 우 | Series Description, Sequence Name, Series # |
| 하단 좌 | 슬라이스 번호/위치, Thickness, Pixel spacing |
| 하단 우 | TR / TE / TI / FA (MRI), kV / mA (CT) |
