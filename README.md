# Hwang Viewer

강의 자료(PPT) 제작을 위한 가볍고 빠른 Windows DICOM 뷰어  
단일 Python 파일(`dicom_viewer.py`)로 실행 가능합니다.

---

## 설치

```bash
pip install pydicom pyqt6 numpy pylibjpeg
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
# → dist\HwangViewer.exe 생성 (~60MB, Python 설치 불필요)
```

---

## 주요 기능

### 레이아웃
- **1×1 / 2×2** 레이아웃 전환 (`Ctrl+1` / `Ctrl+2`)
- **Space** — 활성 패널 1×1 확대 ↔ 2×2 복원 (슬라이스 위치·WL 유지)
- 2×2에서 패널 선택 후 Space → 그 패널만 전체화면 확대, 다시 Space → 원래 2×2 완전 복원

### 시리즈 로딩
- 폴더 드롭 시 **헤더만 병렬 스캔** (8 스레드) → 즉시 시리즈 목록 표시
- 픽셀은 표시할 때만 **지연 로딩** (최근 40장 캐시)
- 복수 시리즈 폴더 → **자동 2×2 배치** (처음 4개)
- 1개 시리즈 → 2×2 → 같은 시리즈를 20 / 40 / 60 / 80% 위치로 **균등 분배**
- 툴바 **◀ ▶** 버튼으로 4개씩 페이지 이동 (1–4 → 5–8 → …)

### 영상 조작
| 동작 | 기능 |
|------|------|
| 우클릭 드래그 **좌우** | Window Width 조절 |
| 우클릭 드래그 **상하** | Window Level 조절 |
| 좌클릭 드래그 **상하** | 슬라이스 이동 |
| 스크롤 휠 | 슬라이스 이동 |
| **Ctrl** + 스크롤 | 확대 / 축소 |
| **R** | W/L + Zoom 리셋 |

### Cross-reference (`X` 키)
- **X** 키 또는 툴바 `✛ Cross-ref` 버튼으로 ON/OFF
- ON 상태에서 패널 **좌클릭** → 클릭 위치의 3D 월드 좌표 계산
- 나머지 패널이 자동으로 해당 위치의 **가장 가까운 슬라이스로 이동**
- 모든 패널에 **시안색(Cyan) 교차선 + 원** 표시
- Axial ↔ Sagittal ↔ Coronal 등 다른 orientation 간에도 작동
- `ImagePositionPatient` 태그 없는 시리즈(Localizer 등)는 자동 제외
- 드래그는 cross-reference 영향 없이 슬라이스 이동 그대로 작동

### DICOM 태그 오버레이 (`T` 키)
| 위치 | 표시 내용 |
|------|-----------|
| 상단 좌 | 환자명, ID, 성별/나이, 검사일, Modality |
| 상단 우 | Series Description, Sequence Name, Series # |
| 하단 좌 | 슬라이스 번호/위치, Thickness, Pixel spacing, 해상도 |
| 하단 우 | TR / TE / TI / FA (MRI), kV / mA (CT) |
| 항상 표시 | WL / WW / Zoom 배율 |

### 캡처 / 클립보드
| 단축키 | 기능 |
|--------|------|
| **Ctrl+C** | 활성 패널 → 클립보드 (PowerPoint에 바로 붙여넣기) |
| **Ctrl+Shift+C** | 전체 2×2 → 클립보드 |
| **Ctrl+S** | 활성 패널 PNG/JPG 저장 |
| **Ctrl+Shift+S** | 전체 패널 저장 |

> 캡처 시 파란 선택 테두리 자동 제거

---

## 전체 단축키

| 키 | 기능 |
|----|------|
| `Space` | 1×1 확대 ↔ 2×2 복원 토글 |
| `X` | Cross-reference ON/OFF |
| `T` | DICOM 태그 오버레이 ON/OFF |
| `R` | W/L & Zoom 리셋 |
| `Ctrl+1` | 1×1 레이아웃 |
| `Ctrl+2` | 2×2 레이아웃 |
| `Ctrl+C` | 활성 패널 클립보드 복사 |
| `Ctrl+Shift+C` | 전체 패널 클립보드 복사 |
| `Ctrl+S` | 활성 패널 저장 |
| `Ctrl+Shift+S` | 전체 패널 저장 |
| `Ctrl+O` | DICOM 파일 열기 |
| `Ctrl+Shift+O` | DICOM 폴더 열기 |
| `↑↓←→` | 슬라이스 이동 |

---

## 파일 구성

```
dicom_viewer.py   — 메인 소스 (단일 파일)
build.bat         — Windows EXE 빌드 스크립트
HwangViewer.spec  — PyInstaller 빌드 설정
requirements.txt  — 의존 패키지 목록
```
