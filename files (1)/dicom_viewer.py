#!/usr/bin/env python3
"""
Hwang Viewer for Radiologic Presentation
==========================================
설치: pip install pydicom pyqt6 numpy pylibjpeg

조작:
  Left drag (좌우/상하)  : WW / WL 조절
  Scroll                 : 슬라이스 이동 (이전/다음)
  Ctrl + Scroll          : 확대 / 축소
  T                      : DICOM 태그 오버레이 ON/OFF
  R                      : W/L & Zoom 리셋
  Ctrl+1 / Ctrl+2        : 1×1 / 2×2 레이아웃
  Ctrl+C                 : 활성 패널 클립보드 복사
  Ctrl+Shift+C           : 전체 패널 클립보드 복사
  Ctrl+S / Ctrl+Shift+S  : 활성/전체 저장
"""

import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import pydicom
    PYDICOM_OK = True
except ImportError:
    PYDICOM_OK = False

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QLabel,
        QHBoxLayout, QVBoxLayout, QGridLayout,
        QListWidget, QFileDialog, QMessageBox, QInputDialog,
        QToolBar, QToolButton, QMenu, QProgressBar,
        QListWidgetItem, QPushButton
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent
    from PyQt6.QtGui import (
        QImage, QPixmap, QPainter, QPen, QColor,
        QFont, QPalette, QAction, QKeySequence, QCursor, QIcon
    )
    PYQT_OK = True
except ImportError:
    PYQT_OK = False


# ─────────────────────────────────────────────────────────────
#  헬퍼: DICOM 태그 → 문자열
# ─────────────────────────────────────────────────────────────
def _tag(ds, attr, default=''):
    try:
        v = getattr(ds, attr, default)
        if v is None:
            return default
        if hasattr(v, '__iter__') and not isinstance(v, str):
            v = v[0]
        return str(v).strip() or default
    except Exception:
        return default


def _fmt_date(raw):
    try:
        return datetime.strptime(raw, '%Y%m%d').strftime('%Y-%m-%d')
    except Exception:
        return raw


def build_overlay(ds, idx, total):
    """4-코너 텍스트 리스트 반환: (top_left, top_right, bot_left, bot_right)"""
    # 상단 좌 — 환자/스터디
    patient  = str(getattr(ds, 'PatientName', 'Anonymous')).strip()
    pat_id   = _tag(ds, 'PatientID',   '')
    sex      = _tag(ds, 'PatientSex',  '')
    age      = _tag(ds, 'PatientAge',  '')
    study_dt = _fmt_date(_tag(ds, 'StudyDate', ''))
    modality = _tag(ds, 'Modality', '')

    top_left = [patient, f"{pat_id}  {sex}  {age}".strip(),
                f"{study_dt}  {modality}".strip()]
    sd = _tag(ds, 'StudyDescription', '')
    if sd:
        top_left.append(sd)

    # 상단 우 — 시리즈
    top_right = []
    for attr in ('SeriesDescription', 'SequenceName', 'ProtocolName'):
        v = _tag(ds, attr, '')
        if v and v not in top_right:
            top_right.append(v)
    sn = _tag(ds, 'SeriesNumber', '')
    if sn:
        top_right.append(f"Series #{sn}")

    # 하단 좌 — 슬라이스
    bot_left = [f"Img {idx+1} / {total}"]
    sl = _tag(ds, 'SliceLocation', '')
    if sl:
        bot_left.append(f"Loc {float(sl):.1f} mm")
    st = _tag(ds, 'SliceThickness', '')
    if st:
        bot_left.append(f"Thick {st} mm")
    try:
        sp = ds.PixelSpacing
        bot_left.append(f"Pixel {float(sp[0]):.2f}×{float(sp[1]):.2f} mm")
    except Exception:
        pass
    r = _tag(ds, 'Rows', ''); c = _tag(ds, 'Columns', '')
    if r and c:
        bot_left.append(f"{c}×{r} px")

    # 하단 우 — MR/CT 파라미터
    bot_right = []
    for label, attr in [("TR", "RepetitionTime"), ("TE", "EchoTime"),
                         ("TI", "InversionTime"),  ("FA", "FlipAngle")]:
        v = _tag(ds, attr, '')
        if v:
            try:
                bot_right.append(f"{label} {float(v):.0f}")
            except Exception:
                bot_right.append(f"{label} {v}")
    for label, attr in [("kV", "KVP"), ("mA", "XRayTubeCurrent")]:
        v = _tag(ds, attr, '')
        if v:
            bot_right.append(f"{v} {label}")

    return top_left, top_right, bot_left, bot_right


# ─────────────────────────────────────────────────────────────
#  Cross-reference 좌표 계산 헬퍼
# ─────────────────────────────────────────────────────────────
def _has_position_tags(ds):
    return (hasattr(ds, 'ImagePositionPatient') and
            hasattr(ds, 'ImageOrientationPatient') and
            hasattr(ds, 'PixelSpacing'))

def _pixel_to_world(ds, row_f, col_f):
    """이미지 픽셀 (row, col) → 3D 월드 좌표 (mm)."""
    try:
        ipp     = np.array([float(x) for x in ds.ImagePositionPatient])
        iop     = np.array([float(x) for x in ds.ImageOrientationPatient])
        ps      = ds.PixelSpacing
        row_dir = iop[:3]
        col_dir = iop[3:]
        return ipp + col_f * float(ps[1]) * row_dir + row_f * float(ps[0]) * col_dir
    except Exception:
        return None

def _world_to_pixel(ds, world):
    """3D 월드 좌표 → 이미지 픽셀 (row_f, col_f)."""
    try:
        ipp     = np.array([float(x) for x in ds.ImagePositionPatient])
        iop     = np.array([float(x) for x in ds.ImageOrientationPatient])
        ps      = ds.PixelSpacing
        row_dir = iop[:3]
        col_dir = iop[3:]
        delta   = world - ipp
        col_f   = np.dot(delta, row_dir) / float(ps[1])
        row_f   = np.dot(delta, col_dir) / float(ps[0])
        return row_f, col_f
    except Exception:
        return None

def _find_best_slice(pairs, world):
    """시리즈에서 world 좌표에 가장 가까운 슬라이스 인덱스 반환."""
    best_i, best_d = 0, float('inf')
    for i, (_, ds) in enumerate(pairs):
        try:
            ipp    = np.array([float(x) for x in ds.ImagePositionPatient])
            iop    = np.array([float(x) for x in ds.ImageOrientationPatient])
            normal = np.cross(iop[:3], iop[3:])
            dist   = abs(np.dot(world - ipp, normal))
            if dist < best_d:
                best_d, best_i = dist, i
        except Exception:
            continue
    return best_i


# ─────────────────────────────────────────────────────────────
#  단일 DICOM 패널
# ─────────────────────────────────────────────────────────────
class DicomPanel(QWidget):
    clicked       = pyqtSignal(object)
    cross_clicked = pyqtSignal(object, object)  # (panel, world_np_array)

    def __init__(self, panel_id=0, parent=None):
        super().__init__(parent)
        self.panel_id  = panel_id
        self.series    = []
        self.idx       = 0
        self.wl        = 40.0
        self.ww        = 400.0
        self.zoom      = 1.0
        self._raw_pix  = None
        self._disp_pix = None
        self._last_pos    = None
        self._drag_accum  = 0
        self._drag_moved  = False      # 드래그 vs 클릭 구분
        self._active      = False
        self._pixel_cache = {}
        self.show_tags    = True
        self.cross_link   = False      # cross-reference 활성 여부
        self._crosshair   = None       # (row_f, col_f) 이미지 좌표, None=없음
        # Shift+드래그 (이미지 이동) — 1/2 속도 + axis lock
        self._gap_accum_x   = 0
        self._gap_accum_y   = 0
        self._gap_locked_ax = None     # None | 'x' | 'y'
        # 이미지를 widget 안에서 가운데 → 안쪽으로 그릴 때의 추가 offset
        # (letterbox 영역을 줄이는 phase. ViewerGrid가 외부에서 set)
        self._paint_offset_x = 0
        self._paint_offset_y = 0
        # 사용자 Panning offset (P 모드에서 좌클릭 드래그로 누적)
        self._pan_offset_x = 0
        self._pan_offset_y = 0

        self.setMinimumSize(200, 200)
        # 배경 transparent → letterbox 영역에 ViewerGrid의 검정이 비치고,
        # 패널이 겹치면 다른 패널 이미지가 보임 (오버랩 가능)
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

    # ── 데이터 ───────────────────────────────────────────────
    # self.series: [(filepath, header_ds), ...]  — 헤더만 보유
    # self._pixel_cache: {idx: np.ndarray}       — 픽셀 캐시 (최근 N장)

    def load_series(self, file_header_pairs, start_idx=None):
        """
        file_header_pairs: [(Path, header_ds), ...]
        header_ds 는 stop_before_pixels=True 로 읽은 헤더 전용 ds.
        """
        self.series        = file_header_pairs
        self._pixel_cache  = {}        # 캐시 초기화
        if start_idx is not None:
            self.idx = max(0, min(len(file_header_pairs) - 1, start_idx))
        else:
            self.idx = max(0, len(file_header_pairs) // 2)
        self.zoom = 1.0
        self._auto_wl()
        self._render()

    def clear(self):
        self.series        = []
        self._pixel_cache  = {}
        self._raw_pix = self._disp_pix = None
        self.update()

    def _get_ds(self):
        """현재 슬라이스의 헤더 ds 반환."""
        if not self.series:
            return None
        return self.series[self.idx][1]

    def _get_pixel(self, idx):
        """idx 슬라이스의 픽셀 배열 반환 (캐시 활용, 최대 40장 보관)."""
        if idx in self._pixel_cache:
            return self._pixel_cache[idx]
        fpath, hdr = self.series[idx]
        try:
            ds  = pydicom.dcmread(str(fpath), force=True)
            arr = ds.pixel_array.astype(np.float32)
            slope     = float(getattr(ds, 'RescaleSlope',     1))
            intercept = float(getattr(ds, 'RescaleIntercept', 0))
            arr = arr * slope + intercept
        except Exception:
            return None
        # 캐시 크기 제한 (40장)
        if len(self._pixel_cache) >= 40:
            oldest = next(iter(self._pixel_cache))
            del self._pixel_cache[oldest]
        self._pixel_cache[idx] = arr
        return arr

    def _auto_wl(self):
        if not self.series:
            return
        ds = self._get_ds()
        if ds is None:
            return
        try:
            wc = ds.WindowCenter
            ww = ds.WindowWidth
            if hasattr(wc, '__iter__'):
                wc, ww = wc[0], ww[0]
            self.wl = float(wc)
            self.ww = float(ww)
            return
        except Exception:
            pass
        arr = self._get_pixel(self.idx)
        if arr is not None:
            p5, p95 = np.percentile(arr, [5, 95])
            self.wl  = float((p5 + p95) / 2)
            self.ww  = max(1.0, float(p95 - p5))

    def _get_array(self):
        return self._get_pixel(self.idx)

    def _apply_wl(self, arr):
        lo = self.wl - self.ww / 2
        hi = self.wl + self.ww / 2
        return ((np.clip(arr, lo, hi) - lo) / (hi - lo) * 255).astype(np.uint8)

    # ── 렌더링 ───────────────────────────────────────────────
    def _render(self):
        try:
            arr = self._get_array()
            if arr is None:
                self._raw_pix = self._disp_pix = None
                self.update()
                return

            # 다채널 / 다프레임 처리 — _apply_wl 전에 2D로 축소
            # 1) 3D인데 (frames, H, W) 또는 (H, W, channels) 형태일 수 있음
            if arr.ndim == 3:
                # (H, W, 3 or 4) → 그레이스케일 (luminance)
                if arr.shape[2] in (3, 4):
                    # RGB/RGBA → 표준 luminance
                    arr = (arr[..., 0] * 0.299
                           + arr[..., 1] * 0.587
                           + arr[..., 2] * 0.114)
                else:
                    # (frames, H, W) — 첫 프레임만 사용
                    arr = arr[0]
            elif arr.ndim == 4:
                # (frames, H, W, channels)
                f0 = arr[0]
                if f0.ndim == 3 and f0.shape[2] in (3, 4):
                    arr = (f0[..., 0] * 0.299
                           + f0[..., 1] * 0.587
                           + f0[..., 2] * 0.114)
                else:
                    arr = f0[0] if f0.ndim == 3 else f0
            elif arr.ndim != 2:
                # 알 수 없는 형태 — 안전하게 빈 화면
                self._raw_pix = self._disp_pix = None
                self.update()
                return

            arr8  = self._apply_wl(arr)
            if arr8.ndim != 2:
                self._raw_pix = self._disp_pix = None
                self.update()
                return
            h, w  = arr8.shape
            qimg  = QImage(arr8.tobytes(), w, h, w, QImage.Format.Format_Grayscale8)
            self._raw_pix = QPixmap.fromImage(qimg)
            self._make_display()
        except Exception as e:
            # 한 패널의 렌더 실패가 전체 페이지 로드를 깨트리지 않도록
            import traceback; traceback.print_exc()
            self._raw_pix = self._disp_pix = None
            self.update()

    def _make_display(self):
        if self._raw_pix is None:
            return
        # 패널 크기에 맞게 꽉 채우는 base scale 계산 (zoom=1.0 = fit)
        pw, ph = self.width(), self.height()
        if pw < 1 or ph < 1:
            return
        iw, ih = self._raw_pix.width(), self._raw_pix.height()
        if iw < 1 or ih < 1:
            return
        base_scale = min(pw / iw, ph / ih)          # fit-to-panel
        final_w = max(1, int(iw * base_scale * self.zoom))
        final_h = max(1, int(ih * base_scale * self.zoom))

        scaled = self._raw_pix.scaled(
            final_w, final_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        result  = QPixmap(scaled)
        W, H    = result.width(), result.height()
        painter = QPainter(result)
        FONT    = QFont("Consolas", 8)
        painter.setFont(FONT)
        LH      = 13
        M       = 5

        def draw_text(x, y, text, right=False):
            """황색 그림자 텍스트. right=True 이면 우측 정렬."""
            if not text.strip():
                return
            rect = result.rect()
            flags = Qt.AlignmentFlag.AlignTop
            if right:
                flags |= Qt.AlignmentFlag.AlignRight
                rect.setRight(W - M + 1); rect.setTop(y + 1)
                painter.setPen(QColor(0, 0, 0, 200))
                painter.drawText(rect, flags, text)
                rect.setRight(W - M);     rect.setTop(y)
                painter.setPen(QColor(255, 255, 0))
                painter.drawText(rect, flags, text)
            else:
                painter.setPen(QColor(0, 0, 0, 200))
                painter.drawText(x + 1, y + 1, text)
                painter.setPen(QColor(255, 255, 0))
                painter.drawText(x, y, text)

        # WL / WW / Zoom — 오버레이와 함께 토글 (T 키)
        if self.show_tags:
            wl_str = f"WL {self.wl:.0f}  WW {self.ww:.0f}   {self.zoom:.1f}×"
            draw_text(M, H - 6, wl_str)

        # DICOM 태그 오버레이
        if self.show_tags and self.series:
            ds = self._get_ds()
            if ds is not None:
                tl, tr, bl, br = build_overlay(ds, self.idx, len(self.series))

                # 상단 좌
                for i, line in enumerate(tl):
                    draw_text(M, M + LH * i + LH, line)

                # 상단 우
                for i, line in enumerate(tr):
                    draw_text(M, M + LH * i + LH, line, right=True)

                # 하단 좌 (WL 줄 바로 위부터 역순)
                base = H - 6 - LH
                for i, line in enumerate(reversed(bl)):
                    draw_text(M, base - LH * i, line)

                # 하단 우
                for i, line in enumerate(reversed(br)):
                    draw_text(M, base - LH * i, line, right=True)

        # ── Cross-reference 교차선 ───────────────────────────
        if self._crosshair is not None:
            row_f, col_f = self._crosshair
            # 이미지 픽셀 → 표시 픽셀 변환
            ch_x = int(col_f * W / iw)
            ch_y = int(row_f * H / ih)
            # 시안색 점선 십자선
            pen = QPen(QColor(0, 255, 255), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(0, ch_y, W, ch_y)   # 수평선
            painter.drawLine(ch_x, 0, ch_x, H)   # 수직선
            # 중심 원
            painter.setPen(QPen(QColor(0, 255, 255), 2))
            painter.drawEllipse(ch_x - 6, ch_y - 6, 12, 12)

        # 활성 패널 파란 테두리
        if self._active:
            painter.setPen(QPen(QColor(0, 160, 255), 3))
            painter.drawRect(1, 1, W - 2, H - 2)

        painter.end()
        self._disp_pix = result
        self.update()
        # _disp_pix 크기 변경 → letterbox 크기 변경 → ViewerGrid가 paint offset 재계산해야
        par = self.parent()
        if par is not None and hasattr(par, '_relayout_panels'):
            par._relayout_panels()

    def set_active(self, v):
        self._active = v
        self._make_display() if self._raw_pix else self.update()

    def toggle_tags(self, state=None):
        self.show_tags = (not self.show_tags) if state is None else state
        self._make_display() if self._raw_pix else self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._raw_pix:
            self._make_display()

    # ── 그리기 ───────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        # background 그리지 않음 — WA_TranslucentBackground로 letterbox 영역이 transparent
        if self._disp_pix:
            # zoom 1.0 시점의 letterbox(이미지가 들어가는) 영역 계산.
            # 이 영역으로 clip해서, zoom으로 _disp_pix가 커져도 인접 패널 영역을 침범하지 않게 함.
            zoom = max(0.001, float(self.zoom))
            base_w = int(round(self._disp_pix.width()  / zoom))
            base_h = int(round(self._disp_pix.height() / zoom))
            # base 영역의 좌상단 — paint_offset(갭 조절)은 따라가지만 pan_offset은 미적용
            # (panning은 zoom 이미지 안에서 다른 부분을 보는 거니까 clip 영역은 고정)
            cx = (self.width()  - base_w) // 2 + self._paint_offset_x
            cy = (self.height() - base_h) // 2 + self._paint_offset_y
            p.setClipRect(cx, cy, base_w, base_h)

            # 실제 그릴 위치 (paint + pan offset 모두 적용)
            x = ((self.width()  - self._disp_pix.width())  // 2
                 + self._paint_offset_x + self._pan_offset_x)
            y = ((self.height() - self._disp_pix.height()) // 2
                 + self._paint_offset_y + self._pan_offset_y)
            p.drawPixmap(x, y, self._disp_pix)
        else:
            p.setPen(QColor(65, 65, 65))
            p.setFont(QFont("Arial", 11))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       f"Panel {self.panel_id + 1}\n\n시리즈 목록에서 더블클릭\n"
                       "또는 파일/폴더를 여기에 드롭")
        if self._active and not self._disp_pix:
            p.setPen(QPen(QColor(0, 160, 255), 3))
            p.drawRect(1, 1, self.width() - 2, self.height() - 2)

    # ── 마우스 ───────────────────────────────────────────────
    def mousePressEvent(self, event):
        self._last_pos   = event.pos()
        self._drag_accum = 0
        self._drag_moved = False
        # Shift+드래그 누적/lock 리셋 (새 드래그 세션 시작)
        self._gap_accum_x   = 0
        self._gap_accum_y   = 0
        self._gap_locked_ax = None
        # Panning 모드 + 좌클릭 → 닫힌 손 커서
        if (event.button() == Qt.MouseButton.LeftButton
                and getattr(self.window(), '_pan_mode', False)):
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.clicked.emit(self)

    def mouseReleaseEvent(self, event):
        # cross-link 모드: 좌클릭이고 드래그하지 않은 경우 → crosshair 설정
        if (self.cross_link
                and event.button() == Qt.MouseButton.LeftButton
                and not self._drag_moved
                and self.series):
            self._emit_cross_click(event.pos())
        # Panning 모드면 다시 열린 손으로
        if (event.button() == Qt.MouseButton.LeftButton
                and getattr(self.window(), '_pan_mode', False)):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._last_pos   = None
        self._drag_accum = 0

    def mouseDoubleClickEvent(self, event):
        """패널 더블클릭 → Space 토글과 동일 (1×1 ↔ multi-panel)."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        win = self.window()
        if hasattr(win, '_toggle_panel_zoom'):
            win._toggle_panel_zoom()

    def _emit_cross_click(self, pos):
        """클릭 위치를 3D 월드 좌표로 변환해 cross_clicked 시그널 발신."""
        ds = self._get_ds()
        if ds is None or not _has_position_tags(ds):
            return
        row_f, col_f = self._screen_to_image(pos.x(), pos.y())
        if row_f is None:
            return
        world = _pixel_to_world(ds, row_f, col_f)
        if world is None:
            return
        self._crosshair = (row_f, col_f)
        self._make_display()
        self.cross_clicked.emit(self, world)

    def _screen_to_image(self, sx, sy):
        """화면 픽셀(sx,sy) → 이미지 픽셀(row_f, col_f). 범위 밖이면 None,None."""
        if self._raw_pix is None or self._disp_pix is None:
            return None, None
        iw = self._raw_pix.width()
        ih = self._raw_pix.height()
        dw = self._disp_pix.width()
        dh = self._disp_pix.height()
        ox = (self.width()  - dw) // 2
        oy = (self.height() - dh) // 2
        lx = sx - ox
        ly = sy - oy
        if lx < 0 or ly < 0 or lx >= dw or ly >= dh:
            return None, None
        return ly * ih / dh, lx * iw / dw   # row_f, col_f

    def set_crosshair_from_world(self, world):
        """외부에서 world 좌표를 받아 교차선 설정 + 가장 가까운 슬라이스로 이동."""
        if not self.series:
            return
        best_i = _find_best_slice(self.series, world)
        self.idx = best_i
        ds = self.series[best_i][1]
        self._crosshair = _world_to_pixel(ds, world) if _has_position_tags(ds) else None
        self._render()

    def clear_crosshair(self):
        self._crosshair = None
        if self._raw_pix:
            self._make_display()

    def mouseMoveEvent(self, event):
        if self._last_pos is None or not self.series:
            return
        dy = event.pos().y() - self._last_pos.y()
        dx = event.pos().x() - self._last_pos.x()

        # 3px 이상 움직이면 드래그로 판정
        if abs(dx) > 3 or abs(dy) > 3:
            self._drag_moved = True

        if event.buttons() & Qt.MouseButton.LeftButton:
            # Shift+좌클릭 드래그 → 모든 패널 widget을 가운데/바깥 방향으로 이동
            # (PPT 캡처용 갭 조절, 오버랩 허용)
            #  • 1/2 속도: 마우스 2px 당 offset 1px
            #  • axis lock: 드래그 세션 시작 시 dominant 축으로 잠가서 한 방향만 작동
            #  • 방향: 마우스 → 안쪽으로 끌면 패널이 안쪽으로 모임
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._gap_accum_x += dx
                self._gap_accum_y += dy

                # 첫 lock 결정 (4px 이상 누적된 dominant 축)
                if self._gap_locked_ax is None:
                    if (abs(self._gap_accum_x) >= 4
                            and abs(self._gap_accum_x) >= abs(self._gap_accum_y)):
                        self._gap_locked_ax = 'x'
                    elif abs(self._gap_accum_y) >= 4:
                        self._gap_locked_ax = 'y'

                win = self.window()
                # lock된 축에서 2px 누적될 때마다 1px 적용 (1/2 속도) — 부호 반전
                if self._gap_locked_ax == 'x':
                    step = self._gap_accum_x // 2
                    if step != 0:
                        self._gap_accum_x -= step * 2
                        if hasattr(win, '_adjust_image_offset_delta'):
                            win._adjust_image_offset_delta(-step, 0)
                elif self._gap_locked_ax == 'y':
                    step = self._gap_accum_y // 2
                    if step != 0:
                        self._gap_accum_y -= step * 2
                        if hasattr(win, '_adjust_image_offset_delta'):
                            win._adjust_image_offset_delta(0, -step)

                self._last_pos = event.pos()
                return

            # Panning 모드 (P 단축키 또는 툴바로 활성) → 영상 위치 이동
            win = self.window()
            if getattr(win, '_pan_mode', False):
                self._pan_offset_x += dx
                self._pan_offset_y += dy
                self.update()
                self._last_pos = event.pos()
                return

            # 좌클릭 드래그 상하 → 슬라이스 이동 (10px 누적마다 1장)
            self._drag_accum += dy
            step = int(self._drag_accum / 10)   # 10px = 슬라이스 1장
            if step != 0:
                self._drag_accum -= step * 10
                new_idx = self.idx + step
                new_idx = max(0, min(len(self.series) - 1, new_idx))
                if new_idx != self.idx:
                    self.idx = new_idx
                    self._render()
            self._last_pos = event.pos()

        elif event.buttons() & Qt.MouseButton.RightButton:
            # 우클릭 드래그: 좌우 → WW, 상하 → WL
            self.ww  = max(1.0, self.ww + dx * 3)
            self.wl += dy * 2
            self._last_pos = event.pos()
            self._render()

        elif event.buttons() & Qt.MouseButton.MiddleButton:
            # 가운데 드래그: 상하 → 확대/축소 (위로 = zoom in)
            # 5px 당 한 단계, Ctrl+휠과 동일한 1.15 배율
            self._drag_accum += dy
            step = int(self._drag_accum / 5)
            if step != 0:
                self._drag_accum -= step * 5
                # 위로 끌면 dy<0 → 확대
                factor = (1 / 1.15) ** step
                self.zoom = max(0.05, min(30.0, self.zoom * factor))
                self._make_display()
            self._last_pos = event.pos()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+스크롤 → 확대/축소
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.zoom = max(0.05, min(30.0, self.zoom * factor))
            self._make_display()
        else:
            # 스크롤 → 슬라이스 이동
            if not self.series:
                return
            step = -1 if delta > 0 else 1   # 위로 스크롤 = 이전 슬라이스
            new_idx = self.idx + step
            if 0 <= new_idx < len(self.series):
                self.idx = new_idx
                self._render()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Left):
            if self.series:
                self.idx = max(0, self.idx - 1)
                self._render()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Right):
            if self.series:
                self.idx = min(len(self.series) - 1, self.idx + 1)
                self._render()
        elif key == Qt.Key.Key_T:
            self.window()._toggle_tags()
        elif key == Qt.Key.Key_R:
            self.window()._reset_active()
        elif key == Qt.Key.Key_Space:
            self.window()._toggle_panel_zoom()
        elif key == Qt.Key.Key_X:
            self.window()._toggle_cross_link()
        else:
            super().keyPressEvent(event)

    # ── 드래그&드롭 ──────────────────────────────────────────
    def dragEnterEvent(self, event):
        event.accept() if event.mimeData().hasUrls() else event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            win = self.window()
            win._activate_panel(self)
            win._load_path(urls[0].toLocalFile())


# ─────────────────────────────────────────────────────────────
#  뷰어 그리드
# ─────────────────────────────────────────────────────────────
class ViewerGrid(QWidget):
    LAYOUTS = {
        '1x1': (1, 1), '1x2': (1, 2), '1x3': (1, 3),
        '2x1': (2, 1), '2x2': (2, 2), '2x3': (2, 3),
        '3x1': (3, 1), '3x2': (3, 2), '3x3': (3, 3),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panels       = []
        self.active_panel = None
        self._mode        = None
        # Space 토글: 직전 multi-panel 상태를 저장
        self._saved_multi      = []      # [(series, idx, wl, ww, zoom), ...]
        self._saved_multi_mode = '2x2'   # 직전 multi 모드
        self._saved_multi_active = 0     # 직전 활성 패널 인덱스

        # 패널 widget 자체의 이동 offset (PPT 캡처용 갭 조절)
        # 양수 = 가운데로부터 멀어짐 (갭 증가)
        # 음수 = 가운데로 모임 (오버랩 허용)
        self._image_offset_x = 0
        self._image_offset_y = 0

        # background 검정 — panels는 transparent라 letterbox 영역에 이게 비침
        self.setStyleSheet("background:#000;")
        self.set_layout('1x1')

    def set_layout(self, mode):
        if mode == self._mode:
            return
        if mode not in self.LAYOUTS:
            return
        rows, cols = self.LAYOUTS[mode]
        n_panels   = rows * cols

        old_series   = [p.series[:] for p in self.panels]
        old_tags     = self.panels[0].show_tags if self.panels else True
        old_crosslnk = self.panels[0].cross_link if self.panels else False
        for p in self.panels:
            p.setParent(None)
            p.deleteLater()
        self.panels = []
        self._mode  = mode

        positions = [(r, c) for r in range(rows) for c in range(cols)]

        # 단일 시리즈만 있을 때 → multi-panel로 균등 분배
        unique = [s for s in old_series if s]
        all_same = len(unique) >= 1 and all(s is unique[0] for s in unique)
        single_series = unique[0] if unique else None

        for i, (r, c) in enumerate(positions):
            p = DicomPanel(panel_id=i, parent=self)
            p.show_tags  = old_tags
            p.cross_link = old_crosslnk
            p.clicked.connect(self._on_clicked)
            if old_crosslnk:
                p.cross_clicked.connect(self._on_cross_clicked)
            p.setAcceptDrops(True)

            if n_panels > 1 and all_same and single_series:
                # 같은 시리즈를 N개 패널에 균등 분배
                total = len(single_series)
                idx   = int(total * (i + 1) / (n_panels + 1))
                p.load_series(single_series, start_idx=idx)
            elif i < len(old_series) and old_series[i]:
                p.load_series(old_series[i])

            p.show()
            self.panels.append(p)

        self._relayout_panels()
        self._activate(self.panels[0])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout_panels()

    def _relayout_panels(self):
        """현재 mode + image_offset에 따라 panels의 setGeometry 직접 계산.
        오버랩 동작 2단계:
          Phase A — 먼저 widget 안에서 이미지(_disp_pix) 위치를 안쪽으로 옮겨
                    letterbox(검정 가장자리) 영역을 줄임. 이 단계에서는 widget 위치 고정.
          Phase B — letterbox가 다 사라지고도 더 끌면 widget 자체를 이동 → 실제 오버랩.
        바깥쪽 이동(offset > 0)은 Phase A 없이 곧장 widget 이동 (갭 증가).
        """
        if not self._mode or not self.panels:
            return
        rows, cols = self.LAYOUTS[self._mode]
        W, H = self.width(), self.height()
        if W <= 0 or H <= 0:
            return
        cell_w = W // cols
        cell_h = H // rows
        cr = (rows - 1) / 2.0
        cc = (cols - 1) / 2.0
        ox = self._image_offset_x   # 양수=바깥, 음수=안쪽
        oy = self._image_offset_y

        for i, p in enumerate(self.panels):
            r = i // cols
            c = i %  cols
            # 가운데로부터 방향 부호 (-1, 0, +1)
            sx = 0 if abs(c - cc) < 1e-6 else (1 if c > cc else -1)
            sy = 0 if abs(r - cr) < 1e-6 else (1 if r > cr else -1)

            # 각 패널의 letterbox 한계 (이미지 주변 검정 폭)
            if p._disp_pix is not None:
                lb_x = max(0, (cell_w - p._disp_pix.width())  // 2)
                lb_y = max(0, (cell_h - p._disp_pix.height()) // 2)
            else:
                lb_x = lb_y = 0

            # X축
            if sx == 0:
                paint_x = 0; widget_x = 0
            elif ox < 0:
                # 안쪽 이동: letterbox만큼은 paint, 초과분만 widget
                paint_x  = max(ox, -lb_x)         # 음수, |paint_x| ≤ lb_x
                widget_x = ox - paint_x            # 남은 안쪽 이동량 (≤0)
            else:
                # 바깥 이동: paint 안 쓰고 widget만
                paint_x = 0
                widget_x = ox

            # Y축
            if sy == 0:
                paint_y = 0; widget_y = 0
            elif oy < 0:
                paint_y  = max(oy, -lb_y)
                widget_y = oy - paint_y
            else:
                paint_y = 0
                widget_y = oy

            # 적용
            # paint_offset_for_panel: sx=-1 좌측 패널이고 paint_x=-5(안쪽)면
            #   이미지를 +5 (오른쪽=안쪽) 방향으로 그림 → sx * paint_x = -1 * -5 = +5 ✓
            p._paint_offset_x = sx * paint_x
            p._paint_offset_y = sy * paint_y

            # widget 위치
            x = c * cell_w + sx * widget_x
            y = r * cell_h + sy * widget_y
            p.setGeometry(int(x), int(y), int(cell_w), int(cell_h))
            p.update()

    # ── 이미지 이동 (PPT 캡처용 갭 조절) ─────────────────────
    def image_offset(self):
        return (self._image_offset_x, self._image_offset_y)

    def set_image_offset(self, ox, oy):
        """절대값 설정. 변경된 (ox, oy) 반환."""
        self._image_offset_x = int(ox)
        self._image_offset_y = int(oy)
        self._relayout_panels()
        return (self._image_offset_x, self._image_offset_y)

    def adjust_image_offset_by(self, dx, dy):
        self._image_offset_x += int(dx)
        self._image_offset_y += int(dy)
        self._relayout_panels()
        return (self._image_offset_x, self._image_offset_y)

    def reset_image_offset(self):
        self._image_offset_x = 0
        self._image_offset_y = 0
        self._relayout_panels()
        return (0, 0)

    def _activate(self, panel):
        if self.active_panel and self.active_panel is not panel:
            self.active_panel.set_active(False)
        self.active_panel = panel
        panel.set_active(True)
        panel.setFocus()

    def _on_clicked(self, panel):
        self._activate(panel)

    def load_to_active(self, datasets):
        if self.active_panel:
            self.active_panel.load_series(datasets)

    def load_multi_series(self, series_list):
        """
        series_list: [(label, datasets), ...]
        현재 layout을 그대로 유지하면서 N개 패널에 채워 넣음.
        - 1개 시리즈 + multi-panel → 모든 패널에 균등 분배
        - 여러 시리즈 → 각 패널에 다른 시리즈, 부족한 패널은 비움
        """
        n_panels = len(self.panels)
        n = min(len(series_list), n_panels)
        if n == 0:
            return

        if len(series_list) == 1 and n_panels > 1:
            # 단일 시리즈를 모든 패널에 균등 분배
            dss   = series_list[0][1]
            total = len(dss)
            for i, p in enumerate(self.panels):
                idx = int(total * (i + 1) / (n_panels + 1))
                p.load_series(dss, start_idx=idx)
        else:
            for i in range(n):
                self.panels[i].load_series(series_list[i][1])
            # 새 페이지가 패널보다 적으면 잔여 패널 비움 (이전 페이지 잔재 제거)
            for i in range(n, n_panels):
                self.panels[i].clear()

        # 페이지 전환 후 첫 패널을 활성으로
        if self.panels:
            self._activate(self.panels[0])

        self._activate(self.panels[0])

    def save_multi_state(self):
        """현재 multi-panel 상태(layout + 패널별 series, idx, wl, ww, zoom + active) 저장."""
        self._saved_multi = [
            (p.series[:], p.idx, p.wl, p.ww, p.zoom)
            for p in self.panels
        ]
        self._saved_multi_mode = self._mode
        self._saved_multi_active = next(
            (i for i, p in enumerate(self.panels) if p is self.active_panel), 0
        )

    def restore_multi_state(self):
        """저장된 multi-panel 상태 복원. 없으면 False 반환."""
        if not self._saved_multi:
            return False
        target_mode = getattr(self, '_saved_multi_mode', '2x2')
        if target_mode == self._mode:
            # 같은 모드면 set_layout 호출이 no-op이므로 강제로 패널 재생성하지 않고 데이터만 복원
            pass
        else:
            self.set_layout(target_mode)
        for i, (series, idx, wl, ww, zoom) in enumerate(self._saved_multi):
            if i >= len(self.panels):
                break
            p = self.panels[i]
            if series:
                p.series       = series
                p.idx          = idx
                p.wl           = wl
                p.ww           = ww
                p.zoom         = zoom
                p._pixel_cache = {}
                p._render()
        active_i = getattr(self, '_saved_multi_active', 0)
        active_i = min(max(active_i, 0), len(self.panels) - 1)
        self._activate(self.panels[active_i])
        return True

    # 하위 호환 alias
    def save_2x2_state(self):     return self.save_multi_state()
    def restore_2x2_state(self):  return self.restore_multi_state()

    def toggle_tags_all(self):
        if not self.panels:
            return
        new_state = not self.panels[0].show_tags
        for p in self.panels:
            p.toggle_tags(new_state)

    def tag_state(self):
        return self.panels[0].show_tags if self.panels else True

    # ── Cross-reference ──────────────────────────────────────
    def set_cross_link(self, active):
        """모든 패널에 cross_link 모드 설정 및 시그널 연결/해제."""
        for p in self.panels:
            p.cross_link = active
            try:
                p.cross_clicked.disconnect()
            except Exception:
                pass
            if active:
                p.cross_clicked.connect(self._on_cross_clicked)
        if not active:
            for p in self.panels:
                p.clear_crosshair()
        else:
            # X 누른 즉시 활성 패널 중앙을 기준으로 cross-line 표시
            self._init_cross_from_active()

    def _init_cross_from_active(self):
        """X 누른 즉시 cross-line 표시.
        우선순위:
          1) 마우스 커서가 어느 이미지 위에 있으면 → 해당 패널/픽셀
          2) 아니면 → 활성 패널 이미지 중앙
        """
        src         = None
        cross_pixel = None    # (row_f, col_f)

        # ── 1) 커서 아래 이미지 찾기 ─────────────────────────
        global_pos = QCursor.pos()
        for p in self.panels:
            if not p.series:
                continue
            local = p.mapFromGlobal(global_pos)
            if not p.rect().contains(local):
                continue
            row_f, col_f = p._screen_to_image(local.x(), local.y())
            if row_f is None:
                continue                       # 패널 안이지만 이미지 픽셀 밖
            src         = p
            cross_pixel = (row_f, col_f)
            break

        # ── 2) 폴백: 활성 패널 중앙 ───────────────────────────
        if src is None:
            src = self.active_panel
            if src is None or not src.series:
                src = next((p for p in self.panels if p.series), None)
                if src is None:
                    return
            ds_chk = src._get_ds()
            if ds_chk is None:
                return
            try:
                rows = int(ds_chk.Rows); cols = int(ds_chk.Columns)
            except Exception:
                return
            cross_pixel = (rows / 2.0, cols / 2.0)

        # ── 공통: world 변환 + 다른 패널 동기화 ──────────────
        ds = src._get_ds()
        if ds is None or not _has_position_tags(ds):
            return
        row_f, col_f = cross_pixel
        world = _pixel_to_world(ds, row_f, col_f)
        if world is None:
            return
        src._crosshair = (row_f, col_f)
        src._make_display()
        for p in self.panels:
            if p is src:
                continue
            p.set_crosshair_from_world(world)

    def _on_cross_clicked(self, src_panel, world):
        """src_panel에서 클릭 → 나머지 패널에 교차선+슬라이스 업데이트."""
        for p in self.panels:
            if p is src_panel:
                continue
            p.set_crosshair_from_world(world)

    def cross_link_state(self):
        return self.panels[0].cross_link if self.panels else False

    def grab_active(self):
        if not self.active_panel:
            return None
        # 캡처 전 파란 테두리 제거
        self.active_panel._active = False
        self.active_panel._make_display()
        QApplication.processEvents()
        pix = self.active_panel.grab()
        # 캡처 후 복원
        self.active_panel._active = True
        self.active_panel._make_display()
        return pix

    def grab_all(self):
        # 전체 캡처도 테두리 없이
        if self.active_panel:
            self.active_panel._active = False
            self.active_panel._make_display()
            QApplication.processEvents()
        pix = self.grab()
        if self.active_panel:
            self.active_panel._active = True
            self.active_panel._make_display()
        return pix


# ─────────────────────────────────────────────────────────────
#  시리즈 사이드바
# ─────────────────────────────────────────────────────────────
class SeriesSidebar(QWidget):
    series_double_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(336)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QLabel("  SERIES")
        hdr.setStyleSheet(
            "background:#222;color:#aaa;font:bold 16px Consolas;"
            "padding:8px;border-bottom:1px solid #444;"
        )
        layout.addWidget(hdr)

        self.study_info = QLabel("")
        self.study_info.setStyleSheet(
            "background:#161616;color:#999;font:14px Consolas;"
            "padding:8px;border-bottom:1px solid #2a2a2a;"
        )
        self.study_info.setWordWrap(True)
        layout.addWidget(self.study_info)

        tip = QLabel("  더블클릭 → 활성 패널 로드  |  ▲ ▼ 휠로 스크롤")
        tip.setStyleSheet(
            "background:#111;color:#666;font:13px Consolas;"
            "padding:5px 6px;border-bottom:1px solid #222;"
        )
        layout.addWidget(tip)

        # ▲ 위로 스크롤 버튼 (목록 위쪽)
        self.up_btn = QPushButton("▲")
        self.up_btn.setStyleSheet("""
            QPushButton {
                background:#1a1a1a; color:#ccc; border:none;
                border-bottom:1px solid #2a2a2a; padding:6px;
                font-size:18px;
            }
            QPushButton:hover   { background:#2a2a2a; color:#fff; }
            QPushButton:pressed { background:#004a8f; }
        """)
        self.up_btn.clicked.connect(lambda: self._scroll_by(-1))
        self.up_btn.setAutoRepeat(True)
        self.up_btn.setAutoRepeatDelay(300)
        self.up_btn.setAutoRepeatInterval(80)
        layout.addWidget(self.up_btn)

        self.lw = QListWidget()
        self.lw.setStyleSheet("""
            QListWidget {
                background:#111;color:#ccc;
                border:none;font-size:18px;font-family:Consolas;
            }
            QListWidget::item {
                padding:8px 6px;border-bottom:1px solid #1c1c1c;
            }
            QListWidget::item:selected { background:#004a8f;color:white; }
            QListWidget::item:hover    { background:#1e3a5f; }
        """)
        self.lw.setIconSize(QSize(144, 144))   # 썸네일 표시 크기 (2배)
        self.lw.itemDoubleClicked.connect(
            lambda item: self.series_double_clicked.emit(self.lw.row(item))
        )
        layout.addWidget(self.lw, 1)

        # ▼ 아래로 스크롤 버튼 (목록 아래)
        self.down_btn = QPushButton("▼")
        self.down_btn.setStyleSheet("""
            QPushButton {
                background:#1a1a1a; color:#ccc; border:none;
                border-top:1px solid #2a2a2a; padding:6px;
                font-size:18px;
            }
            QPushButton:hover   { background:#2a2a2a; color:#fff; }
            QPushButton:pressed { background:#004a8f; }
        """)
        self.down_btn.clicked.connect(lambda: self._scroll_by(1))
        self.down_btn.setAutoRepeat(True)
        self.down_btn.setAutoRepeatDelay(300)
        self.down_btn.setAutoRepeatInterval(80)
        layout.addWidget(self.down_btn)

    def _scroll_by(self, lines):
        """목록을 lines줄만큼 스크롤 (▲/▼ 버튼)."""
        sb = self.lw.verticalScrollBar()
        sb.setValue(sb.value() + lines * sb.singleStep())

    def set_study(self, ds):
        patient  = str(getattr(ds, 'PatientName', 'Anonymous')).strip()
        pat_id   = _tag(ds, 'PatientID',  '')
        sex      = _tag(ds, 'PatientSex', '')
        age      = _tag(ds, 'PatientAge', '')
        date     = _fmt_date(_tag(ds, 'StudyDate', ''))
        modality = _tag(ds, 'Modality',   '')
        self.study_info.setText(
            f"👤 {patient}\n"
            f"   {pat_id}  {sex}  {age}\n"
            f"📅 {date}  [{modality}]"
        )

    def populate(self, series_list, thumbnails=None):
        """series_list: [(label, pairs), ...]
        thumbnails: [QPixmap or None, ...]  — 같은 길이"""
        self.lw.clear()
        for i, (label, pairs) in enumerate(series_list):
            ds0  = pairs[0][1]   # (Path, hdr_ds) → hdr_ds
            num  = _tag(ds0, 'SeriesNumber',      '?')
            desc = _tag(ds0, 'SeriesDescription', f'Series {num}')
            mod  = _tag(ds0, 'Modality',           '')
            item = QListWidgetItem(f"[{num}] {desc}\n      {len(pairs)}개  {mod}")
            item.setToolTip(label)
            if thumbnails and i < len(thumbnails) and thumbnails[i] is not None:
                item.setIcon(QIcon(thumbnails[i]))
            self.lw.addItem(item)

    def clear_all(self):
        self.lw.clear()
        self.study_info.setText("")


# ─────────────────────────────────────────────────────────────
#  메인 윈도우
# ─────────────────────────────────────────────────────────────
class DicomViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hwang Viewer for Radiologic Presentation")
        self.setAcceptDrops(True)
        self._series_list = []
        self._series_page = 0      # 현재 페이지 (0-based)
        self._pan_mode    = False  # P 토글: 좌클릭 드래그가 영상 panning이 됨

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self.showMaximized()       # ② 시작부터 전체화면

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        hbox = QHBoxLayout(central)
        hbox.setSpacing(4)
        hbox.setContentsMargins(4, 4, 4, 4)

        self.sidebar     = SeriesSidebar()
        self.viewer_grid = ViewerGrid()
        self.sidebar.series_double_clicked.connect(self._on_series_double_click)

        hbox.addWidget(self.sidebar)
        hbox.addWidget(self.viewer_grid, 1)

        # statusBar 좌측에 영구 progress bar (평소엔 숨김)
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(360)
        self._progress.setMinimumWidth(280)
        self._progress.setMaximumHeight(20)
        self._progress.setTextVisible(True)
        self._progress.hide()
        self.statusBar().addWidget(self._progress)

        self.statusBar().showMessage(
            "File 메뉴 또는 드래그&드롭으로 DICOM 폴더 열기  |  T: 태그  R: 리셋  Ctrl+C: 복사"
        )
        self.setStyleSheet("""
            QMainWindow { background:#111; }
            QStatusBar  { background:#1a1a1a;color:#888;font-size:14px; }
            QMenuBar    { background:#1e1e1e;color:#ccc;font-size:15px; }
            QMenuBar::item:selected { background:#333; }
            QMenu       { background:#2a2a2a;color:#ccc;border:1px solid #444;font-size:14px; }
            QMenu::item:selected { background:#004a8f; }
            QToolBar    { background:#1e1e1e;border-bottom:1px solid #333;
                          spacing:6px;padding:6px; }
            QToolButton { color:#ccc;padding:8px 16px;border-radius:4px;font-size:24px; }
            QToolButton:hover   { background:#333; }
            QToolButton:pressed { background:#004a8f; }
            QProgressBar {
                background:#222; color:#ddd; border:1px solid #333;
                border-radius:3px; text-align:center; font-size:12px;
            }
            QProgressBar::chunk { background:#0a84ff; border-radius:2px; }
        """)

    def _build_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("File")
        self._act(fm, "📂  Open File...",    "Ctrl+O",       self.open_file)
        self._act(fm, "📁  Open Folder...",  "Ctrl+Shift+O", self.open_folder)
        fm.addSeparator()
        self._act(fm, "💾  Save Active...",  "Ctrl+S",       self.save_active)
        self._act(fm, "🖼️  Save All...",     "Ctrl+Shift+S", self.save_all)
        fm.addSeparator()
        self._act(fm, "Quit", "Ctrl+Q", self.close)

        em = mb.addMenu("Edit")
        self._act(em, "📋  Copy image",   "Ctrl+C",       self.copy_active)
        self._act(em, "🗂️  Copy screen",  "Ctrl+Shift+C", self.copy_all)

        vm = mb.addMenu("View")
        # ── Layout 서브메뉴 (1×1 ~ 3×3 9종) ───────────────
        lm = vm.addMenu("⊞  Layout")
        self._act(lm, "1 × 1",  "Ctrl+1", lambda: self._change_layout('1x1'))
        self._act(lm, "1 × 2",  "",       lambda: self._change_layout('1x2'))
        self._act(lm, "1 × 3",  "",       lambda: self._change_layout('1x3'))
        lm.addSeparator()
        self._act(lm, "2 × 1",  "",       lambda: self._change_layout('2x1'))
        self._act(lm, "2 × 2",  "Ctrl+2", lambda: self._change_layout('2x2'))
        self._act(lm, "2 × 3",  "",       lambda: self._change_layout('2x3'))
        lm.addSeparator()
        self._act(lm, "3 × 1",  "",       lambda: self._change_layout('3x1'))
        self._act(lm, "3 × 2",  "",       lambda: self._change_layout('3x2'))
        self._act(lm, "3 × 3",  "Ctrl+3", lambda: self._change_layout('3x3'))
        vm.addSeparator()
        self._act(vm, "🏷️  Tag Overlay ON/OFF",        "T",      self._toggle_tags)
        self._act(vm, "↺  Reset W/L & Zoom & Pan",      "R",      self._reset_active)
        self._act(vm, "⛶  Toggle 1×1 ↔ Multi  (Space)", "Space",  self._toggle_panel_zoom)
        self._act(vm, "✛  Cross-reference ON/OFF",      "X",      self._toggle_cross_link)
        self._act(vm, "✋  Panning ON/OFF",              "P",      self._toggle_pan_mode)
        vm.addSeparator()
        self._act(vm, "⇔  이미지 이동 설정...",          "",       self.set_image_offset_dialog)
        self._act(vm, "↺  이미지 이동 리셋",             "Ctrl+G", self.reset_image_offset)
        vm.addSeparator()
        self._act(vm, "⊞  Fill Grid with Series", "", self._fill_grid_with_series)

        hm = mb.addMenu("Help")
        self._act(hm, "⌨  Keyboard & Mouse Shortcuts...", "F1", self._show_shortcuts)
        hm.addSeparator()
        self._act(hm, "ⓘ  About...", "", self._show_about)

    def _act(self, menu, label, shortcut, slot):
        a = QAction(label, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    # ── progress bar 헬퍼 ───────────────────────────────────
    def _progress_show(self, label, value, total):
        self._progress.setRange(0, max(1, total))
        self._progress.setValue(value)
        self._progress.setFormat(f"{label}: %v / %m  (%p%)")
        if not self._progress.isVisible():
            self._progress.show()
        QApplication.processEvents()

    def _progress_hide(self):
        self._progress.hide()
        QApplication.processEvents()

    # ── 시리즈 가운데 슬라이스로 썸네일(QPixmap) 생성 ──────
    def _make_thumbnail(self, pairs, size=144):
        """
        pairs: [(Path, hdr_ds), ...] (이미 InstanceNumber 정렬됨)
        가운데 슬라이스의 픽셀을 디코딩해서 size×size QPixmap 반환.
        실패하면 None.
        """
        if not pairs:
            return None
        fpath, _ = pairs[len(pairs) // 2]
        try:
            ds  = pydicom.dcmread(str(fpath), force=True)
            arr = ds.pixel_array
            slope     = float(getattr(ds, 'RescaleSlope',     1))
            intercept = float(getattr(ds, 'RescaleIntercept', 0))
            arr = arr.astype(np.float32) * slope + intercept

            # multi-channel / multi-frame 처리 — _render와 동일 로직
            if arr.ndim == 3:
                if arr.shape[2] in (3, 4):
                    arr = (arr[..., 0] * 0.299
                           + arr[..., 1] * 0.587
                           + arr[..., 2] * 0.114)
                else:
                    arr = arr[arr.shape[0] // 2]
            elif arr.ndim == 4:
                f0 = arr[arr.shape[0] // 2]
                if f0.ndim == 3 and f0.shape[2] in (3, 4):
                    arr = (f0[..., 0] * 0.299
                           + f0[..., 1] * 0.587
                           + f0[..., 2] * 0.114)
                else:
                    arr = f0[f0.shape[0] // 2] if f0.ndim == 3 else f0
            elif arr.ndim != 2:
                return None

            # auto W/L (5–95 percentile)
            p5, p95 = np.percentile(arr, [5, 95])
            wl = (p5 + p95) / 2.0
            ww = max(1.0, float(p95 - p5))
            lo = wl - ww / 2.0
            hi = wl + ww / 2.0
            arr8 = ((np.clip(arr, lo, hi) - lo) / (hi - lo) * 255).astype(np.uint8)
            arr8 = np.ascontiguousarray(arr8)
            h, w = arr8.shape
            qimg = QImage(arr8.tobytes(), w, h, w, QImage.Format.Format_Grayscale8)
            pix  = QPixmap.fromImage(qimg.copy())  # bytes 라이프타임 분리
            return pix.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        except Exception:
            return None

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))

        def tbtn(label, slot):
            a = QAction(label, self); a.triggered.connect(slot); tb.addAction(a)

        tbtn("📂 File",     self.open_file)
        tbtn("📁 Folder",   self.open_folder)
        tb.addSeparator()

        # ── Layout 드롭다운 (1×1 ~ 3×3 9종) ──────────────
        layout_btn = QToolButton(self)
        layout_btn.setText("⊞ Layout ▾")
        layout_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        lmenu = QMenu(layout_btn)
        for mode in ['1x1', '1x2', '1x3', '2x1', '2x2', '2x3', '3x1', '3x2', '3x3']:
            label = mode.replace('x', ' × ')
            act = lmenu.addAction(label)
            act.triggered.connect(
                lambda checked=False, m=mode: self._change_layout(m)
            )
            if mode in ('1x3', '2x3'):
                lmenu.addSeparator()
        layout_btn.setMenu(lmenu)
        tb.addWidget(layout_btn)
        tbtn("⊞ Fill", self._fill_grid_with_series)
        tb.addSeparator()

        # ① 시리즈 페이지 네비게이션
        self._page_label = QLabel("  Series  -  ")
        self._page_label.setStyleSheet("color:#aaa; font-size:24px; padding:0 8px;")
        tb.addWidget(self._page_label)

        tbtn("◀", self._series_prev_page)
        tbtn("▶", self._series_next_page)
        tb.addSeparator()

        tbtn("🏷️ Tags",    self._toggle_tags)
        tbtn("↺ Reset WL",  self._reset_active)
        tbtn("↺ Reset Gap", self.reset_image_offset)
        tbtn("✛ Cross-ref", self._toggle_cross_link)
        tbtn("✋ Panning",   self._toggle_pan_mode)
        tb.addSeparator()
        tbtn("📋 Copy image",   self.copy_active)
        tbtn("🗂️ Copy screen",  self.copy_all)
        tbtn("💾 Save",         self.save_active)

    def _page_size(self):
        """현재 layout의 패널 수 (페이지당 시리즈 수)."""
        return max(1, len(self.viewer_grid.panels))

    def _update_page_label(self):
        n = len(self._series_list)
        if n == 0:
            self._page_label.setText("  Series  -  ")
            return
        ps      = self._page_size()
        page    = self._series_page
        start   = page * ps + 1
        end     = min(start + ps - 1, n)
        total_pages = (n - 1) // ps + 1
        self._page_label.setText(
            f"  Series  {start}–{end} / {n}  (p{page+1}/{total_pages})  "
        )

    def _series_next_page(self):
        if not self._series_list:
            return
        try:
            ps          = self._page_size()
            total_pages = max(1, (len(self._series_list) - 1) // ps + 1)
            self._series_page = (self._series_page + 1) % total_pages
            self._load_current_page()
        except Exception as e:
            import traceback; traceback.print_exc()
            self.statusBar().showMessage(f"⚠ 페이지 전환 오류: {e}", 10000)

    def _series_prev_page(self):
        if not self._series_list:
            return
        try:
            ps          = self._page_size()
            total_pages = max(1, (len(self._series_list) - 1) // ps + 1)
            self._series_page = (self._series_page - 1) % total_pages
            self._load_current_page()
        except Exception as e:
            import traceback; traceback.print_exc()
            self.statusBar().showMessage(f"⚠ 페이지 전환 오류: {e}", 10000)

    def _load_current_page(self):
        if not self._series_list:
            return
        ps          = self._page_size()
        total_pages = max(1, (len(self._series_list) - 1) // ps + 1)
        # 페이지 인덱스를 정상 범위로 보정 (layout 변경 등으로 빗나갔을 수 있음)
        self._series_page = max(0, min(self._series_page, total_pages - 1))
        start       = self._series_page * ps
        page_series = self._series_list[start:start + ps]
        self.viewer_grid.load_multi_series(page_series)
        self._update_page_label()
        s = start + 1
        e = min(start + ps, len(self._series_list))
        self.statusBar().showMessage(
            f"✓  시리즈 {s}–{e} 표시 중  (p{self._series_page+1}/{total_pages})  |  ◀ ▶ 로 페이지 이동"
        )

    # ── 파일 로드 ─────────────────────────────────────────────
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open DICOM File", "",
            "DICOM files (*.dcm *.DCM);;All files (*.*)"
        )
        if path:
            self._load_path(path)

    def open_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Open DICOM Folder")
        if path:
            self._load_path(path)

    def _load_path(self, path):
        self.statusBar().showMessage(f"파일 목록 수집 중: {path}")
        QApplication.processEvents()

        p = Path(path)
        if p.is_file():
            candidates = [p]
        else:
            candidates = sorted(p.rglob("*.dcm")) + sorted(p.rglob("*.DCM"))
            if not candidates:
                candidates = [f for f in sorted(p.rglob("*"))
                              if f.is_file() and not f.name.startswith('.')]

        if not candidates:
            self.statusBar().showMessage("DICOM 파일을 찾지 못했습니다.")
            QMessageBox.warning(self, "오류", "읽을 수 있는 DICOM 파일을 찾지 못했습니다.")
            return

        total = len(candidates)
        self._progress_show("Header scan", 0, total)
        self.statusBar().showMessage(f"헤더 스캔 중: {total}개 파일")

        # ── 1단계: 헤더만 병렬로 빠르게 읽기 ───────────────────
        file_headers = []   # [(Path, ds_header)]

        def read_header(fpath):
            try:
                ds = pydicom.dcmread(str(fpath),
                                     stop_before_pixels=True,
                                     force=True)
                # SeriesInstanceUID 없으면 스킵
                _ = str(getattr(ds, 'SeriesInstanceUID', None) or '')
                return (fpath, ds)
            except Exception:
                return None

        done = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(read_header, f): f for f in candidates}
            for fut in as_completed(futures):
                result = fut.result()
                if result:
                    file_headers.append(result)
                done += 1
                # progress bar 갱신 (10개 단위 또는 마지막)
                if done % 10 == 0 or done == total:
                    self._progress_show("Header scan", done, total)

        if not file_headers:
            self._progress_hide()
            self.statusBar().showMessage("읽을 수 있는 DICOM 파일 없음.")
            QMessageBox.warning(self, "오류", "읽을 수 있는 DICOM 파일을 찾지 못했습니다.")
            return

        # ── 2단계: SeriesInstanceUID 기준 그룹핑 ────────────────
        series_dict: dict = {}
        for fpath, ds in file_headers:
            uid = str(getattr(ds, 'SeriesInstanceUID', 'unknown'))
            series_dict.setdefault(uid, []).append((fpath, ds))

        def inst_sort(pair):
            try:
                return float(getattr(pair[1], 'InstanceNumber', 0))
            except Exception:
                return 0.0

        self._series_list = []
        for uid, pairs in series_dict.items():
            pairs.sort(key=inst_sort)
            ds0   = pairs[0][1]
            num   = _tag(ds0, 'SeriesNumber',      '999')
            desc  = _tag(ds0, 'SeriesDescription', uid[:8])
            label = f"[{num}] {desc} ({len(pairs)})"
            self._series_list.append((label, pairs))   # pairs = [(Path, hdr_ds), ...]

        self._series_list.sort(
            key=lambda x: _tag(x[1][0][1], 'SeriesNumber', '9999').zfill(6)
        )

        # ── 3단계: 시리즈별 썸네일 생성 (가운데 슬라이스) ──────
        n_series = len(self._series_list)
        self._progress_show("Thumbnails", 0, n_series)
        self.statusBar().showMessage(f"썸네일 생성 중: {n_series}개 시리즈")
        thumbs = []
        for i, (label, pairs) in enumerate(self._series_list):
            thumbs.append(self._make_thumbnail(pairs))
            self._progress_show("Thumbnails", i + 1, n_series)

        # 사이드바
        self.sidebar.set_study(file_headers[0][1])
        self.sidebar.populate(self._series_list, thumbs)
        self._series_page = 0

        n = len(self._series_list)
        if n == 1:
            self.viewer_grid.set_layout('1x1')
            self.viewer_grid.load_to_active(self._series_list[0][1])
            msg = f"✓  1개 시리즈  ({len(file_headers)}개 이미지) — 픽셀은 표시 시 로드"
        else:
            # 사용자가 1×1로 두고 있었다면 시리즈 수에 맞는 layout 자동 선택.
            # 이미 multi-panel 모드면 그대로 존중 (3×3 골라뒀으면 9개 다 채움)
            if self.viewer_grid._mode == '1x1':
                self.viewer_grid.set_layout(self._auto_pick_layout(n))
            ps = self._page_size()
            self.viewer_grid.load_multi_series(self._series_list[:ps])
            placed = min(n, ps)
            msg = (f"✓  {len(file_headers)}개 이미지, {n}개 시리즈  —  "
                   f"처음 {placed}개 {self.viewer_grid._mode} 배치 완료")

        self._update_page_label()
        self._progress_hide()
        self.statusBar().showMessage(msg + "  |  ◀ ▶ 페이지  T: 태그  R: 리셋")

    @staticmethod
    def _auto_pick_layout(n_series):
        """시리즈 수에 따라 가장 적합한 layout 추천."""
        if n_series <= 1:  return '1x1'
        if n_series == 2:  return '1x2'
        if n_series <= 4:  return '2x2'
        if n_series <= 6:  return '2x3'
        return '3x3'

    def _activate_panel(self, panel):
        self.viewer_grid._activate(panel)

    def _on_series_double_click(self, idx):
        if 0 <= idx < len(self._series_list):
            self.viewer_grid.load_to_active(self._series_list[idx][1])
            self.sidebar.lw.setCurrentRow(idx)

    def _fill_grid_with_series(self):
        """현재 layout의 패널 수만큼 시리즈를 채워 넣음."""
        if not self._series_list:
            self.statusBar().showMessage("먼저 DICOM 폴더를 열어주세요.")
            return
        self._load_current_page()

    def _change_layout(self, mode):
        """모든 layout 변경의 단일 진입점.
        - set_layout으로 그리드 재구성 (기존 시리즈 자동 유지)
        - 새로 생긴 빈 패널은 사이드바의 미사용 시리즈로 채움
        """
        grid = self.viewer_grid
        grid.set_layout(mode)

        if not self._series_list:
            self._update_page_label()
            return

        def _first_path(s):
            """시리즈의 첫 파일 경로 반환 (안정적 매칭 키)."""
            if not s:
                return None
            try:
                first = s[0]
                if isinstance(first, tuple) and len(first) >= 1:
                    return str(first[0])
            except Exception:
                pass
            return None

        # 이미 채워진 패널 → _series_list 인덱스 매칭 (file path 기준)
        used_idx = set()
        for p in grid.panels:
            p_path = _first_path(p.series)
            if p_path is None:
                continue
            for i, (_, s) in enumerate(self._series_list):
                if _first_path(s) == p_path:
                    used_idx.add(i)
                    break

        # 빈 패널을 미사용 시리즈로 순서대로 채움
        next_i = 0
        for p in grid.panels:
            if p.series:
                continue
            while next_i < len(self._series_list) and next_i in used_idx:
                next_i += 1
            if next_i >= len(self._series_list):
                break
            p.load_series(self._series_list[next_i][1])
            used_idx.add(next_i)
            next_i += 1

        # 페이지 인덱스를 새 layout에 맞춰 갱신 — 첫 패널 위치 기준
        first = grid.panels[0] if grid.panels else None
        first_path = _first_path(first.series) if first else None
        if first_path is not None:
            for i, (_, s) in enumerate(self._series_list):
                if _first_path(s) == first_path:
                    self._series_page = i // self._page_size()
                    break
        self._update_page_label()
        self.statusBar().showMessage(
            f"⊞  Layout {mode}  —  {len(used_idx)}/{len(self._series_list)} 시리즈 표시 중"
        )

    def _toggle_cross_link(self):
        new_state = not self.viewer_grid.cross_link_state()
        self.viewer_grid.set_cross_link(new_state)
        if new_state:
            self.statusBar().showMessage(
                "✛  Cross-reference ON  —  커서 위치 자동 지정  |  좌클릭=위치 변경  |  X=끄기"
            )
        else:
            self.statusBar().showMessage("✛  Cross-reference OFF")

    def _toggle_tags(self):
        self.viewer_grid.toggle_tags_all()
        state = self.viewer_grid.tag_state()
        self.statusBar().showMessage(
            f"🏷️  DICOM 태그 오버레이: {'ON  ✓' if state else 'OFF'}"
        )

    def _show_shortcuts(self):
        """전체 단축키 / 마우스 조작 가이드"""
        html = """
<h2>Keyboard &amp; Mouse Shortcuts</h2>

<h3>📂 File</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+O</b></td><td>파일 열기</td></tr>
<tr><td><b>Ctrl+Shift+O</b></td><td>폴더 열기</td></tr>
<tr><td><b>Ctrl+S</b></td><td>활성 패널 저장</td></tr>
<tr><td><b>Ctrl+Shift+S</b></td><td>전체 패널 저장</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>종료</td></tr>
</table>

<h3>📋 Clipboard</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+C</b></td><td>활성 패널 복사</td></tr>
<tr><td><b>Ctrl+Shift+C</b></td><td>전체 패널 복사 (PPT용)<br><span style='color:#888;'>활성 테두리·사이드바·툴바 자동 제외</span></td></tr>
</table>

<h3>⇔ 이미지 이동 (PPT 캡처용 — 오버랩 허용)</h3>
<table cellpadding='4'>
<tr><td><b>Shift + 좌클릭 드래그</b></td><td>패널을 가운데/바깥으로 이동<br>
<span style='color:#888;'>한 번에 한 축만 (가로 또는 세로) 작동<br>
오른쪽/아래 = 안쪽 (오버랩)<br>
왼쪽/위 = 바깥쪽 (갭 증가)<br>
부드럽게: 마우스 4px 당 1px 이동</span></td></tr>
<tr><td><b>Ctrl+G</b></td><td>이동 리셋 (격자 정렬)</td></tr>
<tr><td colspan='2' style='color:#888;'>수동 입력 (다른 환자 재사용): View → 이미지 이동 설정...</td></tr>
</table>

<h3>⊞ Layout</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+1</b></td><td>1 × 1 (단일 패널)</td></tr>
<tr><td><b>Ctrl+2</b></td><td>2 × 2</td></tr>
<tr><td><b>Ctrl+3</b></td><td>3 × 3</td></tr>
<tr><td colspan='2' style='color:#888;'>그 외 1×2, 1×3, 2×1, 2×3, 3×1, 3×2 — View → Layout 메뉴</td></tr>
<tr><td><b>Space</b></td><td>활성 패널 1×1 ↔ 직전 multi 토글</td></tr>
</table>

<h3>🖼️ Display</h3>
<table cellpadding='4'>
<tr><td><b>T</b></td><td>DICOM 태그 오버레이 ON/OFF<br>(WL/WW 정보 포함)</td></tr>
<tr><td><b>R</b></td><td>W/L &amp; Zoom &amp; Pan 리셋</td></tr>
<tr><td><b>X</b></td><td>Cross-reference ON/OFF</td></tr>
<tr><td><b>P</b></td><td>Panning ON/OFF<br><span style='color:#888;'>좌클릭 드래그가 영상 이동이 됨<br>줌이나 갭 줄임 후 영상 위치 조정용</span></td></tr>
</table>

<h3>🖱️ Mouse</h3>
<table cellpadding='4'>
<tr><td><b>휠 스크롤</b></td><td>슬라이스 이동</td></tr>
<tr><td><b>Ctrl + 휠</b></td><td>확대 / 축소</td></tr>
<tr><td><b>가운데 버튼 드래그 ↕</b></td><td>확대 / 축소 (위로 = 확대)</td></tr>
<tr><td><b>좌클릭 드래그 ↕</b></td><td>슬라이스 이동 (10px = 1장)</td></tr>
<tr><td><b>좌클릭 드래그 (Panning ON)</b></td><td>영상 위치 이동</td></tr>
<tr><td><b>우클릭 드래그</b></td><td>W/L (↕) &amp; W/W (↔)</td></tr>
<tr><td><b>좌클릭 (Cross-ref ON)</b></td><td>해당 위치 크로스 지정</td></tr>
</table>

<h3>⌨ Navigation</h3>
<table cellpadding='4'>
<tr><td><b>↑ / ←</b></td><td>이전 슬라이스</td></tr>
<tr><td><b>↓ / →</b></td><td>다음 슬라이스</td></tr>
</table>
"""
        box = QMessageBox(self)
        box.setWindowTitle("Keyboard & Mouse Shortcuts")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(html)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _show_about(self):
        """About 대화상자"""
        QMessageBox.about(
            self,
            "About",
            "<h2>Hwang Viewer for Radiologic Presentation</h2>"
            "<p>강의 자료(PPT) 제작을 위한 가볍고 빠른 DICOM 뷰어</p>"
            "<p>© 2026 Sungil Hwang (황성일)<br>"
            "Department of Radiology<br>"
            "Seoul National University Bundang Hospital</p>"
            "<p style='color:#888;'>Built with Python · PyQt6 · pydicom</p>"
        )

    def _toggle_panel_zoom(self):
        """Space: 활성 패널 1×1 확대 ↔ 직전 multi-panel 레이아웃 복원 토글"""
        if self.viewer_grid._mode == '1x1':
            # 1×1 → 직전 multi 레이아웃 복원
            if self.viewer_grid.restore_multi_state():
                mode = self.viewer_grid._mode
                self.statusBar().showMessage(f"↩  {mode} 복원  |  Space: 다시 확대")
            else:
                self._load_current_page()
                self.statusBar().showMessage("↩  복원  |  Space: 다시 확대")
        else:
            # multi → 1×1: 현재 상태 저장 후 활성 패널 확대
            active = self.viewer_grid.active_panel
            if active and active.series:
                self.viewer_grid.save_multi_state()        # ← 상태 저장
                saved       = active.series[:]
                saved_idx   = active.idx
                saved_wl    = active.wl
                saved_ww    = active.ww
                saved_zoom  = active.zoom
                self.viewer_grid.set_layout('1x1')
                p = self.viewer_grid.panels[0]
                p.series      = saved
                p.idx         = saved_idx
                p.wl          = saved_wl
                p.ww          = saved_ww
                p.zoom        = saved_zoom
                p._pixel_cache = {}
                p._render()
                self.statusBar().showMessage("🔍  1×1 확대  |  Space: 복원")

    def _reset_active(self):
        p = self.viewer_grid.active_panel
        if p and p.series:
            p.zoom = 1.0
            p._auto_wl()
            p._pan_offset_x = 0
            p._pan_offset_y = 0
            p._render()

    # ── Panning 모드 (P) ─────────────────────────────────────
    def _toggle_pan_mode(self):
        self._pan_mode = not self._pan_mode
        cursor = (Qt.CursorShape.OpenHandCursor if self._pan_mode
                  else Qt.CursorShape.ArrowCursor)
        for p in self.viewer_grid.panels:
            p.setCursor(cursor)
        if self._pan_mode:
            self.statusBar().showMessage(
                "✋  Panning ON  —  좌클릭 드래그로 영상 위치 이동  |  "
                "슬라이스는 휠로  |  P 또는 R로 종료/리셋"
            )
        else:
            self.statusBar().showMessage("✋  Panning OFF")

    # ── 캡처 ─────────────────────────────────────────────────
    def copy_active(self):
        pix = self.viewer_grid.grab_active()
        if pix:
            QApplication.clipboard().setPixmap(pix)
            self.statusBar().showMessage(
                "✓  클립보드 복사 완료  —  PowerPoint에 Ctrl+V 로 붙여넣기"
            )

    def copy_all(self):
        pix = self.viewer_grid.grab_all()
        if pix:
            QApplication.clipboard().setPixmap(pix)
            self.statusBar().showMessage("✓  전체 패널 클립보드 복사 완료")

    # ── 패널 이미지 이동 (PPT 캡처용 — 갭 조절 + 오버랩) ────
    def _adjust_image_offset_delta(self, dx, dy):
        """Shift+드래그에서 호출 — 이미지 offset에 (dx, dy) 더하기."""
        ox, oy = self.viewer_grid.adjust_image_offset_by(dx, dy)
        self.statusBar().showMessage(
            f"⇔  이미지 이동: x={ox:+d}px, y={oy:+d}px  "
            f"|  Shift+드래그(한 축씩)  |  Ctrl+G 리셋",
            3000
        )

    def set_image_offset_dialog(self):
        """View 메뉴에서 호출 — 이미지 offset 수동 입력 (다른 환자에서도 같은 값 재사용)."""
        ox, oy = self.viewer_grid.image_offset()
        x, ok = QInputDialog.getInt(
            self, "이미지 이동 X",
            "가로 이동량 (픽셀)\n\n"
            "양수 = 패널이 바깥쪽으로 (갭 증가)\n"
            "음수 = 패널이 안쪽으로 (오버랩)\n"
            "0    = 격자 정렬\n\n"
            "범위: -2000 ~ 2000",
            ox, -2000, 2000, 5
        )
        if not ok:
            return
        y, ok = QInputDialog.getInt(
            self, "이미지 이동 Y",
            "세로 이동량 (픽셀)\n\n"
            "양수 = 패널이 바깥쪽으로 (갭 증가)\n"
            "음수 = 패널이 안쪽으로 (오버랩)\n"
            "0    = 격자 정렬\n\n"
            "범위: -2000 ~ 2000",
            oy, -2000, 2000, 5
        )
        if not ok:
            return
        nx, ny = self.viewer_grid.set_image_offset(x, y)
        self.statusBar().showMessage(
            f"✓  이미지 이동: x={nx:+d}px, y={ny:+d}px"
        )

    def reset_image_offset(self):
        self.viewer_grid.reset_image_offset()
        self.statusBar().showMessage("↺  이미지 이동 리셋 (격자 정렬)")

    def save_active(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", "capture",
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)"
        )
        if path:
            pix = self.viewer_grid.grab_active()
            if pix:
                pix.save(path)
                self.statusBar().showMessage(f"✓  저장: {path}")

    def save_all(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save All Panels", "capture_all",
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)"
        )
        if path:
            pix = self.viewer_grid.grab_all()
            if pix:
                pix.save(path)
                self.statusBar().showMessage(f"✓  저장: {path}")

    # ── 드래그&드롭 ──────────────────────────────────────────
    def dragEnterEvent(self, event):
        event.accept() if event.mimeData().hasUrls() else event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self._load_path(urls[0].toLocalFile())


# ─────────────────────────────────────────────────────────────
#  진입점
# ─────────────────────────────────────────────────────────────
def main():
    missing = []
    if not PYQT_OK:
        missing.append("pyqt6")
    if not PYDICOM_OK:
        missing.append("pydicom")
    if missing:
        print(f"ERROR: pip install {' '.join(missing)} numpy pylibjpeg")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("Hwang Viewer for Radiologic Presentation")
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(30,  30,  30))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(210, 210, 210))
    pal.setColor(QPalette.ColorRole.Base,            QColor(18,  18,  18))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(40,  40,  40))
    pal.setColor(QPalette.ColorRole.Text,            QColor(210, 210, 210))
    pal.setColor(QPalette.ColorRole.Button,          QColor(50,  50,  50))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(210, 210, 210))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(0,   100, 200))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)

    win = DicomViewer()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
