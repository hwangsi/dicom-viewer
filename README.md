# Hwang Viewer for Radiologic Presentation — v2.1

강의 자료(PPT) 제작에 최적화된 가볍고 빠른 Windows DICOM 뷰어.
단일 Python 파일(`dicom_viewer.py`)로 실행 가능합니다.

![demo1](assets/final_part1.gif)

---

## 설치

```bash
pip install -r requirements.txt
```

또는 직접:

```bash
pip install pydicom pyqt6 numpy pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg
```

## 실행

```bash
python dicom_viewer.py
```

## EXE 빌드 (배포용)

```
방법 1: build.bat 더블클릭 (Windows)
방법 2: pyinstaller HwangViewer.spec
        → dist\HwangViewer.exe 생성 (~60–80 MB, Python 설치 불필요)
```

생성된 `HwangViewer.exe` 단일 파일을 다른 PC에 복사하면 Python 없이도 실행 가능합니다 (Windows 10/11 64-bit).

---

## 주요 기능

### 9가지 레이아웃

| 단축키 | 레이아웃 |
|--------|---------|
| `Ctrl+1` | 1×1 |
| `Ctrl+2` | 2×2 |
| `Ctrl+3` | 3×3 |

툴바 `⊞ Layout ▾` 드롭다운으로 9개 (1×1 / 1×2 / 1×3 / 2×1 / 2×2 / 2×3 / 3×1 / 3×2 / 3×3) 선택. `Space` 또는 패널 더블클릭으로 1×1 ↔ 다중 패널 토글.

### 시리즈 사이드바

- 폴더 드롭 시 statusBar 좌측에 **진행률 표시줄** (Header scan → Thumbnails)
- 시리즈마다 **가운데 슬라이스 썸네일** 144×144 자동 생성
- ▲ ▼ **삼각형 버튼**으로 사이드바 스크롤 (길게 누르면 연속)
- 휠은 사이드바 내부 스크롤만
- 툴바 `◀ ▶`로 페이지 이동

### 자동 시리즈 분배

- **1개 시리즈 + 다중 패널**: 같은 시리즈를 모든 패널에 균등 분배
- **여러 시리즈**: 각 패널에 다른 시리즈 자동 배치
- 시리즈 수 ≥ 7개면 자동으로 `3×3` 추천

### 영상 조작

| 동작 | 기능 |
|------|------|
| **좌클릭 드래그 ↕** | 슬라이스 이동 (10px당 1장) |
| **우클릭 드래그 ↔** | Window Width |
| **우클릭 드래그 ↕** | Window Level |
| **가운데 드래그 ↕** | 확대/축소 (5px당 1단계) |
| **스크롤 휠** | 슬라이스 이동 |
| `Ctrl` + 휠 | 확대/축소 (1.15배) |
| `R` | 활성 패널의 W/L 리셋 (zoom/pan 유지) |
| `Ctrl+G` | **Reset Position** — 모든 패널 Gap / Zoom / Pan / W/L 전체 리셋 |

오버랩/줌 상태에서도 마우스 커서 위치의 패널이 자동으로 활성/조작됨 (z-order 기반 hit-test).

### Panning 모드 (`P` 키)

확대했거나 갭을 줄인 상태에서 영상 위치를 미세 조정.

| 동작 | 기능 |
|------|------|
| `P` 또는 툴바 `✋ Panning` | 모드 ON/OFF |
| 모드 ON + 좌클릭 드래그 | 영상 위치 이동 (1:1 비율) |
| 자석 효과 | 인접 패널 이미지 가장자리 3px 이내에 자동 정렬 |
| 모드 OFF | 좌클릭 드래그가 다시 슬라이스 이동으로 복귀 |

### 패널 갭 / 오버랩

PowerPoint에 깔끔하게 붙여넣기 위해 패널 사이 검정 띠를 줄이거나 이미지를 겹침.

| 동작 | 기능 |
|------|------|
| **Shift + 좌클릭 드래그** | 패널을 가운데/바깥 이동 (한 번에 한 축) |
| `Ctrl+G` | Reset Position |
| 툴바 `↺ Reset Position` | 동일 |
| View → 이미지 이동 설정... | 픽셀 수동 입력 |

#### Two-Phase 오버랩

1. 처음에는 widget 안에서 이미지만 안쪽 이동 → 검정 letterbox부터 줄어듦
2. letterbox 사라지면 이미지끼리 인접 (PPT 친화적)
3. 더 끌면 widget 자체 이동 → 실제 오버랩

확대해도 갭이 유지됩니다 (letterbox 클리핑) — 확대 이미지가 인접 패널을 침범하지 않음.

### Cross-reference (`X` 키)

- 패널 좌클릭 → 클릭 위치의 3D 월드 좌표 계산
- 다른 패널들이 자동으로 가장 가까운 슬라이스로 이동 + 시안 십자선/원
- Axial ↔ Sagittal ↔ Coronal 간에도 작동
- Zoom + Pan 후에도 정확한 마우스 위치 반영

### DICOM 태그 오버레이 (`T` 키)

| 위치 | 표시 |
|------|------|
| 상단 좌 | 환자명 / ID / 성별·나이 / 검사일 / Modality |
| 상단 우 | Series Description / Sequence / Series # |
| 하단 좌 | Img/Total / Loc / Thickness / Pixel / 해상도 |
| 하단 우 | TR / TE / FA (MRI), kV / mA (CT) |
| 항상 | WL / WW / Zoom 배율 |

Zoom과 무관하게 letterbox 가장자리에 항상 일정한 크기로 표시 (paintEvent overlay).

### 캡처 / 클립보드

| 단축키 | 기능 |
|--------|------|
| `Ctrl+C` | 활성 패널 → 클립보드 (Copy Image) |
| `Ctrl+Shift+C` | 전체 화면 → 클립보드 (Copy Screen) |
| `Ctrl+Alt+C` | **영역 선택 → 클립보드 (Copy Area)** — 사용자가 직접 사각형 그리기 |
| `Ctrl+S` | 활성 패널 PNG/JPG 저장 |

활성 패널 파란 테두리 + Cross-reference 십자선은 **모든 캡처에서 자동 제거**.
HiDPI(125%/150%/200% 스케일) 환경에서도 영역 정확히 캡처.

---

## 전체 단축키

| 키 | 기능 |
|----|------|
| `Space` | 1×1 ↔ 다중 패널 (= 패널 더블클릭) |
| `P` | Panning ON/OFF |
| `X` | Cross-reference ON/OFF |
| `T` | DICOM 태그 오버레이 ON/OFF |
| `R` | W/L 리셋 (활성 패널만) |
| `Ctrl+G` | Reset Position (전체) |
| `Ctrl+1/2/3` | 1×1 / 2×2 / 3×3 |
| `Ctrl+C` / `Ctrl+Shift+C` / `Ctrl+Alt+C` | Copy Image / Screen / Area |
| `Ctrl+S` / `Ctrl+Shift+S` | Save Active / All |
| `Ctrl+O` / `Ctrl+Shift+O` | Open File / Folder |
| `↑↓←→` | 슬라이스 이동 |
| `F1` | 단축키 가이드 |
| **Shift + 좌클릭 드래그** | 패널 갭 조절 |
| **마우스 우클릭 드래그** | WW / WL |
| **마우스 가운데 드래그** | 확대/축소 |

---

## 파일 구성

```
dicom_viewer.py    — 메인 소스 (단일 파일, ~2400줄)
HwangViewer.spec   — PyInstaller 빌드 설정
build.bat          — Windows EXE 빌드 스크립트
requirements.txt   — 의존 패키지
README.md          — 본 문서
```

---

## v2.1 변경 사항 (v2 대비)

### 새 기능
- **Panning 모드** (`P` 키) — 확대/갭 조절 후 영상 위치 미세 조정 + 인접 패널 가장자리에 자석 정렬
- **Reset Position** (`Ctrl+G`) — 갭/zoom/pan/WL 전체 리셋. 라벨은 메뉴와 툴바 모두 명확화
- **Copy Area** (`Ctrl+Alt+C`) — 화면에서 사각형 영역을 직접 그려 클립보드 복사. HiDPI 정확도 보정
- **Reset W/L (`R`)** — 활성 패널의 W/L만 리셋, zoom/pan은 유지

### 정확도 / UX 개선
- **z-order 기반 hit-test** — 갭 줄임/오버랩 상태에서 마우스 커서 위에 있는 패널이 정확히 활성화 (클릭 / 휠 / 더블클릭 모두)
- **Zoom 시 letterbox 클리핑** — 확대해도 인접 패널 영역 침범 안 함
- **태그/테두리 오버레이를 paintEvent로** — 줌과 무관하게 letterbox 가장자리에 항상 가시
- **Cross-ref 좌표 정확도** — zoom + pan 후에도 클릭 정확한 위치
- **Capture overlay 제거** — 모든 캡처(Image/Screen/Area)에서 활성 테두리 + cross-hair + selector overlay 자동 제거
- **HiDPI 영역 캡처 보정** — Windows 디스플레이 스케일링 환경에서 정확한 영역 캡처

### 안정성
- 마우스 이벤트 forwarding을 직접 method dispatch 방식으로 (PyQt6 버전 호환성)
- 빌드 스크립트 ASCII + CRLF (Windows cmd 인코딩 문제 방지)
