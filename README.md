# Hwang Viewer for Radiologic Presentation — v3.0

강의 자료(PPT) 제작에 최적화된 가볍고 빠른 Windows DICOM 뷰어.
레이아웃 자유, 갭줄이기, 확대, 축소, cross-link 가능하고, 전체화면 캡쳐, 선택화면 캡쳐 모두 가능하고 클립보드에 붙습니다.
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

### 자동 시리즈 그룹핑 및 분배

- **SeriesInstanceUID 기준 자동 그룹핑** — 동일 UID의 파일이 하나의 시리즈로 묶임
- 시리즈 목록은 **SeriesNumber 오름차순** 정렬
- 각 항목: `[시리즈번호] 설명 (슬라이스 수)` 형식으로 표시 (예: `[12] T1 AXIAL (43)`)
- **1개 시리즈 + 다중 패널**: 같은 시리즈를 모든 패널에 균등 분배
- **여러 시리즈**: 각 패널에 다른 시리즈 자동 배치
- 시리즈 수 ≥ 7개면 자동으로 `3×3` 추천

### 다국어 지원 (v3.0 신규)

메뉴 `Language` 에서 실시간 언어 전환. 선택 언어는 `settings.json`에 자동 저장되어 재시작 후에도 유지.

| 언어 코드 | 표시 |
|-----------|------|
| `ko` | 한국어 (기본값) |
| `en` | English |
| `es` | Español |
| `ja` | 日本語 |
| `zh` | 中文 |

상태바 메시지, 다이얼로그, 메뉴 항목 등 모든 UI 텍스트가 즉시 전환됩니다.

### DWI b-value 필터링 (v3.0 신규)

Multi-b-value DWI 시리즈를 열면 패널 좌상단에 **b-value 배지(badge)** 가 자동으로 나타납니다.

- 배지 클릭 → 해당 b-value 슬라이스만 필터링 (예: `b0`, `b1000`, `b2000`)
- `b▾` / `b▸` 토글로 배지 접기/펼치기
- 필터 활성 시 슬라이스 카운터는 필터 풀 내의 위치로 표시 (예: `12/25`)
- **해부학적 위치 보존 스크롤** — 인터리브 DWI(b0·b1000이 동일 위치 반복)에서 휠 스크롤 시 b-value가 의도치 않게 전환되지 않음
- Cross-reference 동기화도 b-value 필터와 함께 정상 작동

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
dicom_viewer.py    — 메인 소스 (단일 파일)
settings.json      — 언어 설정 저장 (자동 생성)
HwangViewer.spec   — PyInstaller 빌드 설정
build.bat          — Windows EXE 빌드 스크립트
requirements.txt   — 의존 패키지
README.md          — 본 문서
```

---

## v3.0 변경 사항 (v2.1 대비)

### 새 기능

- **다국어 지원** — 한국어·영어·스페인어·일본어·중국어 실시간 전환. `Language` 메뉴에서 선택, `settings.json`에 자동 저장
- **DWI b-value 필터링** — Multi-b-value DWI 시리즈에서 패널 좌상단에 b-value 배지 자동 표시. 배지 클릭으로 b-value별 슬라이스 필터링
- **시리즈 자동 그룹핑** — SeriesInstanceUID 기준으로 시리즈를 묶고 SeriesNumber 순 정렬. 사이드바에 `[번호] 설명 (슬라이스 수)` 형식 표시

### 버그 수정

- **인터리브 DWI 슬라이스 점프 수정** — b0·b1000이 동일 해부학적 위치에 반복되는 인터리브 DWI에서 휠 스크롤 시 b-value가 의도치 않게 전환되던 문제 수정. 현재 b-value를 유지하면서 해부학적 위치만 이동
- **Cross-reference 브로드캐스트 루프 방지** — 동기화된 다중 패널 간 스크롤 이벤트가 무한 루프를 일으키던 문제 수정

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
