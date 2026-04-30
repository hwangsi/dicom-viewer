# Hwang Viewer for Radiologic Presentation

강의 자료(PPT) 제작에 최적화된 가볍고 빠른 Windows DICOM 뷰어.
이제 PPT에서 이미지 각각을 붙여서 간격줄이고 크롭할 필요 없이, 뷰어에서 직접 간격 조정하고 zoom/panning을 시행하여
1x1에서 3x3 까지 모든 슬라이스 이미지를 한장에 만들 수 있습니다.
단일 Python 파일(`dicom_viewer.py`)로 실행 가능합니다.

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

```bash
# 방법 1: build.bat 더블클릭 (Windows)

# 방법 2: 직접 실행
pyinstaller HwangViewer.spec
# → dist\HwangViewer.exe 생성 (~60–80 MB, Python 설치 불필요)
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

툴바 `⊞ Layout ▾` 드롭다운으로 9개 레이아웃 (1×1 / 1×2 / 1×3 / 2×1 / 2×2 / 2×3 / 3×1 / 3×2 / 3×3) 모두 선택 가능. `Space` 또는 활성 패널 더블클릭으로 1×1 ↔ 다중 패널 토글.

### 시리즈 사이드바 (썸네일 + 진행률)

- 폴더 드롭 시 statusBar 좌측에 **진행률 표시줄** — Header scan → Thumbnails 두 단계 진행률
- 시리즈마다 **가운데 슬라이스 썸네일** 144×144px 자동 생성 (auto W/L)
- ▲ ▼ **삼각형 버튼**으로 사이드바 스크롤 (길게 누르면 연속)
- 휠은 사이드바 내부 스크롤만 — 패널 영향 없음
- 툴바 `◀ ▶`로 페이지 이동 (시리즈 수 > 패널 수일 때)

### 자동 시리즈 분배

- **1개 시리즈 + 다중 패널**: 같은 시리즈를 모든 패널에 균등 분배 (예: 2×2 → 20/40/60/80% 위치)
- **여러 시리즈**: 각 패널에 다른 시리즈 자동 배치
- 시리즈 수 ≥ 7개면 자동으로 `3×3` 레이아웃 추천

### 영상 조작

| 동작 | 기능 |
|------|------|
| **좌클릭 드래그 ↕** | 슬라이스 이동 (10px당 1장) |
| **우클릭 드래그 ↔** | Window Width 조절 |
| **우클릭 드래그 ↕** | Window Level 조절 |
| **가운데 드래그 ↕** | 확대/축소 (5px당 1단계) |
| **스크롤 휠** | 슬라이스 이동 |
| `Ctrl` + 휠 | 확대/축소 (1.15배) |
| `R` | W/L + Zoom + Pan 리셋 |

확대 시에도 패널 사이 갭은 유지됩니다 — 확대된 이미지가 인접 패널 영역을 절대 침범하지 않고 자기 letterbox 안에서만 보입니다.

### Panning 모드 (`P` 키)

확대했거나 갭을 줄인 상태에서 영상 위치를 미세하게 조정할 수 있습니다.

| 동작 | 기능 |
|------|------|
| `P` 또는 툴바 `✋ Panning` | Panning 모드 ON/OFF 토글 |
| 모드 ON + **좌클릭 드래그** | 활성 패널 영상 위치 이동 (1:1 비율) |
| 모드 ON 상태 표시 | 커서가 손바닥 모양으로 변경 |
| `R` | Panning 포함 모든 상태 리셋 |
| 휠 | Panning 모드 무관하게 슬라이스 이동 그대로 작동 |

### 패널 갭 / 오버랩 — PPT 캡처용

PowerPoint에 깔끔하게 붙여넣기 위해 패널 사이 검정 띠를 줄이거나 이미지를 겹쳐 표시할 수 있습니다.

| 동작 | 기능 |
|------|------|
| **Shift + 좌클릭 드래그** | 패널을 가운데/바깥 방향으로 이동<br>한 번에 한 축만 (가로 또는 세로)<br>오른쪽/아래 = 안쪽 (오버랩)<br>왼쪽/위 = 바깥쪽 (갭 증가) |
| `Ctrl+G` | 갭 리셋 (격자 정렬) |
| 툴바 `↺ Reset Gap` | 갭 리셋 |
| View → 이미지 이동 설정... | 픽셀 단위 수동 입력 (다른 환자에서도 같은 값 재사용) |

#### 동작 단계 (Two-Phase 오버랩)

1. 처음에는 widget 안에서 이미지 위치만 안쪽으로 이동 → **검정 letterbox부터 줄어듦**
2. letterbox가 다 사라지면 **이미지끼리 직접 인접** (PPT 친화적)
3. 더 끌면 widget 자체가 이동 → **실제 오버랩**

### Cross-reference (`X` 키)

- 패널 좌클릭 → 클릭 위치의 3D 월드 좌표 계산
- 다른 패널들이 자동으로 가장 가까운 슬라이스로 이동
- 모든 패널에 시안색 십자선 + 원 표시
- Axial ↔ Sagittal ↔ Coronal 간에도 작동
- `ImagePositionPatient` 없는 시리즈는 자동 제외

### DICOM 태그 오버레이 (`T` 키)

| 위치 | 표시 |
|------|------|
| 상단 좌 | 환자명 / ID / 성별·나이 / 검사일 / Modality |
| 상단 우 | Series Description / Sequence / Series # |
| 하단 좌 | Img/Total / Loc / Thickness / Pixel / 해상도 |
| 하단 우 | TR / TE / FA (MRI), kV / mA (CT) |
| 항상 | WL / WW / Zoom 배율 |

### 캡처 / 클립보드

| 단축키 | 기능 |
|--------|------|
| `Ctrl+C` | 활성 패널 → 클립보드 (`Copy image`) |
| `Ctrl+Shift+C` | 전체 화면 → 클립보드 (`Copy screen`) |
| `Ctrl+S` | 활성 패널 PNG/JPG 저장 |

활성 패널 파란 테두리는 캡처 시 자동 제거.

---

## 전체 단축키

| 키 | 기능 |
|----|------|
| `Space` | 1×1 ↔ 다중 패널 토글 (= 패널 더블클릭) |
| `P` | Panning ON/OFF |
| `X` | Cross-reference ON/OFF |
| `T` | DICOM 태그 오버레이 ON/OFF |
| `R` | W/L + Zoom + Pan 리셋 |
| `Ctrl+G` | 패널 갭 리셋 |
| `Ctrl+1` / `Ctrl+2` / `Ctrl+3` | 1×1 / 2×2 / 3×3 |
| `Ctrl+C` / `Ctrl+Shift+C` | Copy image / Copy screen |
| `Ctrl+S` / `Ctrl+Shift+S` | Save Active / Save All |
| `Ctrl+O` / `Ctrl+Shift+O` | Open File / Folder |
| `↑↓←→` | 슬라이스 이동 |
| `F1` | 단축키 가이드 |
| **Shift + 좌클릭 드래그** | 패널 갭 조절 |
| **마우스 우클릭 드래그 ↔/↕** | WW / WL |
| **마우스 가운데 드래그 ↕** | 확대/축소 |

---

## 파일 구성

```
dicom_viewer.py    — 메인 소스 (단일 파일, ~2000줄)
HwangViewer.spec   — PyInstaller 빌드 설정
build.bat          — Windows EXE 빌드 스크립트
requirements.txt   — 의존 패키지
README.md          — 본 문서
```

---

## v2 변경 사항 (이전 버전 대비)

- 레이아웃 4종 (1×1/2×2) → **9종** (1×1 ~ 3×3)
- 사이드바에 **시리즈 썸네일** 표시 (가운데 슬라이스, 144×144)
- 로딩 중 **진행률 표시줄** (헤더 스캔 + 썸네일 생성)
- **패널 갭 조절 / 오버랩** — PPT 캡처용 (Shift + 드래그, axis lock, two-phase)
- **Panning 모드** (`P` 키) — 확대/갭 조절 후 영상 위치 미세 조정
- 패널 **더블클릭으로 Space 토글**
- 마우스 **가운데 드래그로 확대/축소**
- 사이드바 **▲▼ 스크롤 버튼**, 휠은 사이드바 내부에서만
- **확대 시 갭 침범 방지** — letterbox 영역으로 자동 클리핑
- **F1 단축키 가이드** (Help 메뉴)
- 코드 안정화 — RGB / Multi-frame DICOM 안전 처리
