#!/usr/bin/env python3
"""
DICOM Viewer - Lecture Edition v2
==================================
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
        QListWidget, QFileDialog, QMessageBox,
        QToolBar, QListWidgetItem, QPushButton
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QSize
    from PyQt6.QtGui import (
        QImage, QPixmap, QPainter, QPen, QColor,
        QFont, QPalette, QAction, QKeySequence
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
#  단일 DICOM 패널
# ─────────────────────────────────────────────────────────────
class DicomPanel(QWidget):
    clicked = pyqtSignal(object)

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
        self._last_pos   = None
        self._drag_accum = 0       # 좌클릭 드래그 픽셀 누적
        self._active     = False
        self._pixel_cache = {}     # {slice_idx: np.ndarray}
        self.show_tags = True

        self.setMinimumSize(200, 200)
        self.setStyleSheet("background:#000;")
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
        arr = self._get_array()
        if arr is None:
            self._raw_pix = self._disp_pix = None
            self.update()
            return
        arr8  = self._apply_wl(arr)
        h, w  = arr8.shape
        qimg  = QImage(arr8.tobytes(), w, h, w, QImage.Format.Format_Grayscale8)
        self._raw_pix = QPixmap.fromImage(qimg)
        self._make_display()

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

        # 항상 표시: WL / WW / Zoom
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

        # 활성 패널 파란 테두리
        if self._active:
            painter.setPen(QPen(QColor(0, 160, 255), 3))
            painter.drawRect(1, 1, W - 2, H - 2)

        painter.end()
        self._disp_pix = result
        self.update()

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
        p.fillRect(self.rect(), QColor(0, 0, 0))
        if self._disp_pix:
            x = (self.width()  - self._disp_pix.width())  // 2
            y = (self.height() - self._disp_pix.height()) // 2
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
        self._last_pos = event.pos()
        self.clicked.emit(self)

    def mouseReleaseEvent(self, event):
        self._last_pos   = None
        self._drag_accum = 0

    def mouseMoveEvent(self, event):
        if self._last_pos is None or not self.series:
            return
        dy = event.pos().y() - self._last_pos.y()
        dx = event.pos().x() - self._last_pos.x()

        if event.buttons() & Qt.MouseButton.LeftButton:
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.panels       = []
        self.active_panel = None
        self._mode        = None

        self.grid = QGridLayout(self)
        self.grid.setSpacing(2)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.set_layout('1x1')

    def set_layout(self, mode):
        if mode == self._mode:
            return
        old_series = [p.series[:] for p in self.panels]
        old_tags   = self.panels[0].show_tags if self.panels else True
        for p in self.panels:
            self.grid.removeWidget(p)
            p.deleteLater()
        self.panels = []
        self._mode  = mode

        positions = [(0, 0)] if mode == '1x1' else [(0,0),(0,1),(1,0),(1,1)]
        n_panels  = len(positions)

        # 단일 시리즈 → 2×2 전환 시 4등분 배치
        unique = [s for s in old_series if s]
        all_same = len(unique) >= 1 and all(s is unique[0] for s in unique)
        single_series = unique[0] if unique else None

        for i, (r, c) in enumerate(positions):
            p = DicomPanel(panel_id=i, parent=self)
            p.show_tags = old_tags
            p.clicked.connect(self._on_clicked)
            p.setAcceptDrops(True)

            if mode == '2x2' and all_same and single_series:
                # 같은 시리즈를 4개 패널에 균등 분배
                total = len(single_series)
                idx   = int(total * (i + 1) / (n_panels + 1))
                p.load_series(single_series, start_idx=idx)
            elif i < len(old_series) and old_series[i]:
                p.load_series(old_series[i])

            self.grid.addWidget(p, r, c)
            self.panels.append(p)

        self._activate(self.panels[0])

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
        series_list: [(label, datasets), ...]  최대 4개
        - 1개 시리즈 → 2×2, 4개 패널에 균등 분배
        - 2~4개 시리즈 → 2×2, 각 패널에 다른 시리즈
        """
        n = min(len(series_list), 4)
        if n == 0:
            return

        if n == 1:
            # 단일 시리즈 2×2: 4 패널에 균등 분배
            dss   = series_list[0][1]
            total = len(dss)
            self.set_layout('2x2')
            for i, p in enumerate(self.panels):
                idx = int(total * (i + 1) / 5)   # 1/5, 2/5, 3/5, 4/5
                p.load_series(dss, start_idx=idx)
        else:
            self.set_layout('2x2')
            for i in range(n):
                self.panels[i].load_series(series_list[i][1])

        self._activate(self.panels[0])

    def toggle_tags_all(self):
        if not self.panels:
            return
        new_state = not self.panels[0].show_tags
        for p in self.panels:
            p.toggle_tags(new_state)

    def tag_state(self):
        return self.panels[0].show_tags if self.panels else True

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
        self.setFixedWidth(320)

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

        tip = QLabel("  더블클릭 → 활성 패널에 로드")
        tip.setStyleSheet(
            "background:#111;color:#666;font:13px Consolas;"
            "padding:5px 6px;border-bottom:1px solid #222;"
        )
        layout.addWidget(tip)

        self.lw = QListWidget()
        self.lw.setStyleSheet("""
            QListWidget {
                background:#111;color:#ccc;
                border:none;font-size:14px;font-family:Consolas;
            }
            QListWidget::item {
                padding:8px 6px;border-bottom:1px solid #1c1c1c;
            }
            QListWidget::item:selected { background:#004a8f;color:white; }
            QListWidget::item:hover    { background:#1e3a5f; }
        """)
        self.lw.itemDoubleClicked.connect(
            lambda item: self.series_double_clicked.emit(self.lw.row(item))
        )
        layout.addWidget(self.lw)

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

    def populate(self, series_list):
        self.lw.clear()
        for i, (label, pairs) in enumerate(series_list):
            ds0  = pairs[0][1]   # (Path, hdr_ds) → hdr_ds
            num  = _tag(ds0, 'SeriesNumber',      '?')
            desc = _tag(ds0, 'SeriesDescription', f'Series {num}')
            mod  = _tag(ds0, 'Modality',           '')
            item = QListWidgetItem(f"[{num}] {desc}\n      {len(pairs)}개  {mod}")
            item.setToolTip(label)
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
        self.setWindowTitle("DICOM Viewer  —  Lecture Edition")
        self.setAcceptDrops(True)
        self._series_list = []
        self._series_page = 0      # 현재 페이지 (0-based, 4개씩)

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
                          spacing:4px;padding:4px; }
            QToolButton { color:#ccc;padding:6px 14px;border-radius:4px;font-size:15px; }
            QToolButton:hover   { background:#333; }
            QToolButton:pressed { background:#004a8f; }
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
        self._act(em, "📋  Copy Active",  "Ctrl+C",       self.copy_active)
        self._act(em, "🗂️  Copy All",     "Ctrl+Shift+C", self.copy_all)

        vm = mb.addMenu("View")
        self._act(vm, "1 × 1",  "Ctrl+1", lambda: self.viewer_grid.set_layout('1x1'))
        self._act(vm, "2 × 2",  "Ctrl+2", lambda: self.viewer_grid.set_layout('2x2'))
        vm.addSeparator()
        self._act(vm, "🏷️  Tag Overlay ON/OFF",        "T",     self._toggle_tags)
        self._act(vm, "↺  Reset W/L & Zoom",            "R",     self._reset_active)
        self._act(vm, "⛶  Toggle 1×1 / 2×2  (Space)",  "Space", self._toggle_panel_zoom)
        vm.addSeparator()
        self._act(vm, "⊞  Load 4 Series → 2×2", "", self._load_4_to_grid)

    def _act(self, menu, label, shortcut, slot):
        a = QAction(label, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))

        def tbtn(label, slot):
            a = QAction(label, self); a.triggered.connect(slot); tb.addAction(a)

        tbtn("📂 File",     self.open_file)
        tbtn("📁 Folder",   self.open_folder)
        tb.addSeparator()
        tbtn("1×1", lambda: self.viewer_grid.set_layout('1x1'))
        tbtn("2×2", lambda: self.viewer_grid.set_layout('2x2'))
        tbtn("⊞ 4 Series", self._load_4_to_grid)
        tb.addSeparator()

        # ① 시리즈 페이지 네비게이션
        self._page_label = QLabel("  시리즈  -  ")
        self._page_label.setStyleSheet("color:#aaa; font-size:15px; padding:0 4px;")
        tb.addWidget(self._page_label)

        tbtn("◀", self._series_prev_page)
        tbtn("▶", self._series_next_page)
        tb.addSeparator()

        tbtn("🏷️ Tags",    self._toggle_tags)
        tbtn("↺ Reset WL", self._reset_active)
        tb.addSeparator()
        tbtn("📋 Copy",    self.copy_active)
        tbtn("💾 Save",    self.save_active)

    def _update_page_label(self):
        n = len(self._series_list)
        if n == 0:
            self._page_label.setText("  시리즈  -  ")
            return
        page    = self._series_page
        start   = page * 4 + 1
        end     = min(start + 3, n)
        total_pages = (n - 1) // 4 + 1
        self._page_label.setText(
            f"  시리즈  {start}–{end} / {n}  (p{page+1}/{total_pages})  "
        )

    def _series_next_page(self):
        if not self._series_list:
            return
        total_pages = (len(self._series_list) - 1) // 4 + 1
        self._series_page = (self._series_page + 1) % total_pages
        self._load_current_page()

    def _series_prev_page(self):
        if not self._series_list:
            return
        total_pages = (len(self._series_list) - 1) // 4 + 1
        self._series_page = (self._series_page - 1) % total_pages
        self._load_current_page()

    def _load_current_page(self):
        start = self._series_page * 4
        page_series = self._series_list[start:start + 4]
        self.viewer_grid.load_multi_series(page_series)
        self._update_page_label()
        s = start + 1
        e = min(start + 4, len(self._series_list))
        self.statusBar().showMessage(
            f"✓  시리즈 {s}–{e} 표시 중  |  ◀ ▶ 로 페이지 이동"
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
        self.statusBar().showMessage(f"헤더 스캔 중: 0 / {total}")
        QApplication.processEvents()

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
                if done % 50 == 0 or done == total:
                    self.statusBar().showMessage(
                        f"헤더 스캔 중: {done} / {total}  ({len(file_headers)} 유효)"
                    )
                    QApplication.processEvents()

        if not file_headers:
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

        # 사이드바
        self.sidebar.set_study(file_headers[0][1])
        self.sidebar.populate(self._series_list)
        self._series_page = 0

        n = len(self._series_list)
        if n == 1:
            self.viewer_grid.set_layout('1x1')
            self.viewer_grid.load_to_active(self._series_list[0][1])
            msg = f"✓  1개 시리즈  ({len(file_headers)}개 이미지) — 픽셀은 표시 시 로드"
        else:
            self.viewer_grid.load_multi_series(self._series_list[:4])
            placed = min(n, 4)
            msg = (f"✓  {len(file_headers)}개 이미지, {n}개 시리즈  —  "
                   f"처음 {placed}개 2×2 배치 완료")

        self._update_page_label()
        self.statusBar().showMessage(msg + "  |  ◀ ▶ 페이지  T: 태그  R: 리셋")

    def _activate_panel(self, panel):
        self.viewer_grid._activate(panel)

    def _on_series_double_click(self, idx):
        if 0 <= idx < len(self._series_list):
            self.viewer_grid.load_to_active(self._series_list[idx][1])
            self.sidebar.lw.setCurrentRow(idx)

    def _load_4_to_grid(self):
        if not self._series_list:
            self.statusBar().showMessage("먼저 DICOM 폴더를 열어주세요.")
            return
        self._load_current_page()

    def _toggle_tags(self):
        self.viewer_grid.toggle_tags_all()
        state = self.viewer_grid.tag_state()
        self.statusBar().showMessage(
            f"🏷️  DICOM 태그 오버레이: {'ON  ✓' if state else 'OFF'}"
        )

    def _toggle_panel_zoom(self):
        """Space: 활성 패널 1×1 확대 ↔ 2×2 복원 토글"""
        if self.viewer_grid._mode == '1x1':
            # 현재 1×1 → 2×2로 복원
            self._load_current_page()
            self.statusBar().showMessage("↩  2×2 복원  |  Space: 다시 확대")
        else:
            # 현재 2×2 → 활성 패널만 1×1 확대
            active = self.viewer_grid.active_panel
            if active and active.series:
                saved = active.series[:]
                saved_idx = active.idx
                self.viewer_grid.set_layout('1x1')
                self.viewer_grid.panels[0].load_series(saved, start_idx=saved_idx)
                self.statusBar().showMessage("🔍  1×1 확대  |  Space: 2×2 복원")
        self.viewer_grid.toggle_tags_all()
        state = self.viewer_grid.tag_state()
        self.statusBar().showMessage(
            f"🏷️  DICOM 태그 오버레이: {'ON  ✓' if state else 'OFF'}"
        )

    def _reset_active(self):
        p = self.viewer_grid.active_panel
        if p and p.series:
            p.zoom = 1.0
            p._auto_wl()
            p._render()

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
    app.setApplicationName("DICOM Viewer")
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
