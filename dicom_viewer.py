#!/usr/bin/env python3
"""
Hwang Viewer for Radiologic Presentation — v3.1
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
import os
import re
import json
import time
import multiprocessing
import numpy as np
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

try:
    import pydicom
    PYDICOM_OK = True
except ImportError:
    PYDICOM_OK = False


def _read_dicom_header(path_str: str):
    """ProcessPoolExecutor 워커 — pickle을 위해 반드시 top-level 함수여야 함."""
    try:
        ds = pydicom.dcmread(path_str, stop_before_pixels=True, force=True)
        _ = str(getattr(ds, 'SeriesInstanceUID', None) or '')
        return (path_str, ds)
    except Exception:
        return None


_header_cache: dict = {}  # {폴더 절대경로: (파일수, [(Path, ds), ...])}

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QLabel,
        QHBoxLayout, QVBoxLayout, QGridLayout,
        QListWidget, QFileDialog, QMessageBox, QInputDialog,
        QToolBar, QToolButton, QMenu, QProgressBar,
        QListWidgetItem, QPushButton,
        QDialog, QTextBrowser, QDialogButtonBox
    )
    from PyQt6.QtCore import Qt, QObject, pyqtSignal, QSize, QEvent, QRect, QPoint
    from PyQt6.QtGui import (
        QImage, QPixmap, QPainter, QPen, QColor,
        QFont, QFontMetrics, QPalette, QAction, QKeySequence, QCursor, QIcon
    )
    PYQT_OK = True
except ImportError:
    PYQT_OK = False


# ─────────────────────────────────────────────────────────────
#  i18n — translations & LocaleManager
# ─────────────────────────────────────────────────────────────
_SETTINGS_PATH = Path(__file__).with_name('settings.json')

_SHORTCUTS_HTML = {
    'ko': """
<h2 style='margin-bottom:4px;'>Keyboard &amp; Mouse Shortcuts</h2>
<table width='100%' cellspacing='0' cellpadding='0'><tr>
<td width='50%' valign='top' style='padding-right:20px;'>
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
<tr><td><b>Ctrl+C</b></td><td>활성 패널 복사 (Copy Image)</td></tr>
<tr><td><b>Ctrl+Shift+C</b></td><td>전체 화면 복사 (Copy Screen)<br><span style='color:#888;'>활성 테두리·사이드바·툴바 자동 제외</span></td></tr>
<tr><td><b>Ctrl+Alt+C</b></td><td>영역 선택 복사 (Copy Area)<br><span style='color:#888;'>드래그로 사각형 선택, Esc 취소</span></td></tr>
</table>
<h3>⇔ 이미지 이동 (PPT 캡처용 — 오버랩 허용)</h3>
<table cellpadding='4'>
<tr><td><b>Shift + 좌클릭 드래그</b></td><td>패널을 가운데/바깥으로 이동<br>
<span style='color:#888;'>한 번에 한 축만 (가로 또는 세로) 작동<br>
오른쪽/아래 = 안쪽 (오버랩)<br>
왼쪽/위 = 바깥쪽 (갭 증가)<br>
부드럽게: 마우스 4px 당 1px 이동</span></td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — Gap / Zoom / Pan / W/L 모두 리셋</td></tr>
<tr><td colspan='2' style='color:#888;'>수동 입력 (다른 환자 재사용): View → 이미지 이동 설정...</td></tr>
</table>
</td><td width='50%' valign='top' style='padding-left:20px; border-left:1px solid #444;'>
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
<tr><td><b>R</b></td><td>활성 패널 W/L 리셋 (zoom/pan은 유지)</td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — 모든 패널의 Gap / Zoom / Pan / W/L 리셋</td></tr>
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
</td></tr></table>
""",
    'en': """
<h2 style='margin-bottom:4px;'>Keyboard &amp; Mouse Shortcuts</h2>
<table width='100%' cellspacing='0' cellpadding='0'><tr>
<td width='50%' valign='top' style='padding-right:20px;'>
<h3>📂 File</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+O</b></td><td>Open file</td></tr>
<tr><td><b>Ctrl+Shift+O</b></td><td>Open folder</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Save active panel</td></tr>
<tr><td><b>Ctrl+Shift+S</b></td><td>Save all panels</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>
</table>
<h3>📋 Clipboard</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+C</b></td><td>Copy active panel</td></tr>
<tr><td><b>Ctrl+Shift+C</b></td><td>Copy full screen<br><span style='color:#888;'>Active border, sidebar &amp; toolbar excluded</span></td></tr>
<tr><td><b>Ctrl+Alt+C</b></td><td>Area copy<br><span style='color:#888;'>Drag to select, Esc to cancel</span></td></tr>
</table>
<h3>⇔ Image Offset (for PPT — overlap allowed)</h3>
<table cellpadding='4'>
<tr><td><b>Shift + left-drag</b></td><td>Move panel inward/outward<br>
<span style='color:#888;'>One axis at a time (H or V)<br>
Right/down = inward (overlap)<br>
Left/up = outward (gap increase)<br>
Smooth: 1px per 4px mouse</span></td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — Gap / Zoom / Pan / W/L</td></tr>
<tr><td colspan='2' style='color:#888;'>Manual input: View → Image Offset...</td></tr>
</table>
</td><td width='50%' valign='top' style='padding-left:20px; border-left:1px solid #444;'>
<h3>⊞ Layout</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+1</b></td><td>1 × 1 (single panel)</td></tr>
<tr><td><b>Ctrl+2</b></td><td>2 × 2</td></tr>
<tr><td><b>Ctrl+3</b></td><td>3 × 3</td></tr>
<tr><td colspan='2' style='color:#888;'>Others: 1×2, 1×3, 2×1, 2×3, 3×1, 3×2 — View → Layout</td></tr>
<tr><td><b>Space</b></td><td>Toggle active panel 1×1 ↔ multi</td></tr>
</table>
<h3>🖼️ Display</h3>
<table cellpadding='4'>
<tr><td><b>T</b></td><td>DICOM tag overlay ON/OFF (includes WL/WW)</td></tr>
<tr><td><b>R</b></td><td>Reset W/L of active panel (zoom/pan preserved)</td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — all panels Gap / Zoom / Pan / W/L</td></tr>
<tr><td><b>X</b></td><td>Cross-reference ON/OFF</td></tr>
<tr><td><b>P</b></td><td>Panning ON/OFF<br><span style='color:#888;'>Left-drag moves image<br>Use after zoom or gap reduction</span></td></tr>
</table>
<h3>🖱️ Mouse</h3>
<table cellpadding='4'>
<tr><td><b>Scroll wheel</b></td><td>Navigate slices</td></tr>
<tr><td><b>Ctrl + scroll</b></td><td>Zoom in / out</td></tr>
<tr><td><b>Middle button drag ↕</b></td><td>Zoom (up = in)</td></tr>
<tr><td><b>Left-drag ↕</b></td><td>Navigate slices (10px = 1)</td></tr>
<tr><td><b>Left-drag (Panning ON)</b></td><td>Move image</td></tr>
<tr><td><b>Right-drag</b></td><td>W/L (↕) &amp; W/W (↔)</td></tr>
<tr><td><b>Left-click (Cross-ref ON)</b></td><td>Set cross position</td></tr>
</table>
<h3>⌨ Navigation</h3>
<table cellpadding='4'>
<tr><td><b>↑ / ←</b></td><td>Previous slice</td></tr>
<tr><td><b>↓ / →</b></td><td>Next slice</td></tr>
</table>
</td></tr></table>
""",
    'es': """
<h2 style='margin-bottom:4px;'>Keyboard &amp; Mouse Shortcuts</h2>
<table width='100%' cellspacing='0' cellpadding='0'><tr>
<td width='50%' valign='top' style='padding-right:20px;'>
<h3>📂 File</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+O</b></td><td>Abrir archivo</td></tr>
<tr><td><b>Ctrl+Shift+O</b></td><td>Abrir carpeta</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Guardar panel activo</td></tr>
<tr><td><b>Ctrl+Shift+S</b></td><td>Guardar todos los paneles</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>Salir</td></tr>
</table>
<h3>📋 Clipboard</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+C</b></td><td>Copiar panel activo</td></tr>
<tr><td><b>Ctrl+Shift+C</b></td><td>Copiar pantalla completa<br><span style='color:#888;'>Borde activo, barra lateral y herramientas excluidos</span></td></tr>
<tr><td><b>Ctrl+Alt+C</b></td><td>Copiar área<br><span style='color:#888;'>Arrastrar para seleccionar, Esc para cancelar</span></td></tr>
</table>
<h3>⇔ Desplazamiento de imagen (para PPT — superposición permitida)</h3>
<table cellpadding='4'>
<tr><td><b>Shift + arrastrar izq.</b></td><td>Mover panel hacia adentro/afuera<br>
<span style='color:#888;'>Un eje a la vez (H o V)<br>
Derecha/abajo = adentro (superposición)<br>
Izquierda/arriba = afuera (aumenta espacio)<br>
Suave: 1px por cada 4px de ratón</span></td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — Gap / Zoom / Pan / W/L</td></tr>
<tr><td colspan='2' style='color:#888;'>Entrada manual: View → Ajuste de imagen...</td></tr>
</table>
</td><td width='50%' valign='top' style='padding-left:20px; border-left:1px solid #444;'>
<h3>⊞ Layout</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+1</b></td><td>1 × 1 (panel único)</td></tr>
<tr><td><b>Ctrl+2</b></td><td>2 × 2</td></tr>
<tr><td><b>Ctrl+3</b></td><td>3 × 3</td></tr>
<tr><td colspan='2' style='color:#888;'>Otros: 1×2, 1×3, 2×1, 2×3, 3×1, 3×2 — View → Layout</td></tr>
<tr><td><b>Space</b></td><td>Alternar panel activo 1×1 ↔ multi</td></tr>
</table>
<h3>🖼️ Display</h3>
<table cellpadding='4'>
<tr><td><b>T</b></td><td>Superposición DICOM ON/OFF (incluye WL/WW)</td></tr>
<tr><td><b>R</b></td><td>Reset W/L del panel activo (zoom/pan preservados)</td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — todos los paneles Gap / Zoom / Pan / W/L</td></tr>
<tr><td><b>X</b></td><td>Cross-reference ON/OFF</td></tr>
<tr><td><b>P</b></td><td>Paneo ON/OFF<br><span style='color:#888;'>Arrastrar mueve la imagen<br>Usar tras zoom o reducción de espacio</span></td></tr>
</table>
<h3>🖱️ Mouse</h3>
<table cellpadding='4'>
<tr><td><b>Rueda</b></td><td>Navegar cortes</td></tr>
<tr><td><b>Ctrl + rueda</b></td><td>Zoom + / -</td></tr>
<tr><td><b>Botón central arrastrar ↕</b></td><td>Zoom (arriba = acercar)</td></tr>
<tr><td><b>Arrastrar izq. ↕</b></td><td>Navegar cortes (10px = 1)</td></tr>
<tr><td><b>Arrastrar izq. (Paneo ON)</b></td><td>Mover imagen</td></tr>
<tr><td><b>Arrastrar der.</b></td><td>W/L (↕) &amp; W/W (↔)</td></tr>
<tr><td><b>Clic izq. (Cross-ref ON)</b></td><td>Establecer posición cruzada</td></tr>
</table>
<h3>⌨ Navigation</h3>
<table cellpadding='4'>
<tr><td><b>↑ / ←</b></td><td>Corte anterior</td></tr>
<tr><td><b>↓ / →</b></td><td>Corte siguiente</td></tr>
</table>
</td></tr></table>
""",
    'ja': """
<h2 style='margin-bottom:4px;'>Keyboard &amp; Mouse Shortcuts</h2>
<table width='100%' cellspacing='0' cellpadding='0'><tr>
<td width='50%' valign='top' style='padding-right:20px;'>
<h3>📂 File</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+O</b></td><td>ファイルを開く</td></tr>
<tr><td><b>Ctrl+Shift+O</b></td><td>フォルダを開く</td></tr>
<tr><td><b>Ctrl+S</b></td><td>アクティブパネルを保存</td></tr>
<tr><td><b>Ctrl+Shift+S</b></td><td>全パネルを保存</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>終了</td></tr>
</table>
<h3>📋 Clipboard</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+C</b></td><td>アクティブパネルをコピー</td></tr>
<tr><td><b>Ctrl+Shift+C</b></td><td>全画面コピー<br><span style='color:#888;'>アクティブ枠・サイドバー・ツールバーを除外</span></td></tr>
<tr><td><b>Ctrl+Alt+C</b></td><td>領域コピー<br><span style='color:#888;'>ドラッグで選択、Escでキャンセル</span></td></tr>
</table>
<h3>⇔ 画像オフセット (PPT用 — オーバーラップ可)</h3>
<table cellpadding='4'>
<tr><td><b>Shift + 左ドラッグ</b></td><td>パネルを内側/外側に移動<br>
<span style='color:#888;'>一度に1軸のみ (水平または垂直)<br>
右/下 = 内側 (オーバーラップ)<br>
左/上 = 外側 (ギャップ増加)<br>
スムーズ: マウス4px = 1px移動</span></td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — Gap / Zoom / Pan / W/L</td></tr>
<tr><td colspan='2' style='color:#888;'>手動入力: View → 画像オフセット設定...</td></tr>
</table>
</td><td width='50%' valign='top' style='padding-left:20px; border-left:1px solid #444;'>
<h3>⊞ Layout</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+1</b></td><td>1 × 1 (単一パネル)</td></tr>
<tr><td><b>Ctrl+2</b></td><td>2 × 2</td></tr>
<tr><td><b>Ctrl+3</b></td><td>3 × 3</td></tr>
<tr><td colspan='2' style='color:#888;'>その他: 1×2, 1×3, 2×1, 2×3, 3×1, 3×2 — View → Layout</td></tr>
<tr><td><b>Space</b></td><td>アクティブパネル 1×1 ↔ マルチ 切替</td></tr>
</table>
<h3>🖼️ Display</h3>
<table cellpadding='4'>
<tr><td><b>T</b></td><td>DICOMタグオーバーレイ ON/OFF (WL/WW含む)</td></tr>
<tr><td><b>R</b></td><td>アクティブパネルのW/Lリセット (zoom/pan保持)</td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — 全パネルのGap / Zoom / Pan / W/L</td></tr>
<tr><td><b>X</b></td><td>Cross-reference ON/OFF</td></tr>
<tr><td><b>P</b></td><td>パンモード ON/OFF<br><span style='color:#888;'>左ドラッグで画像移動<br>ズームやギャップ縮小後の位置調整用</span></td></tr>
</table>
<h3>🖱️ Mouse</h3>
<table cellpadding='4'>
<tr><td><b>ホイール</b></td><td>スライスナビゲーション</td></tr>
<tr><td><b>Ctrl + ホイール</b></td><td>ズーム + / -</td></tr>
<tr><td><b>中ボタンドラッグ ↕</b></td><td>ズーム (上 = 拡大)</td></tr>
<tr><td><b>左ドラッグ ↕</b></td><td>スライスナビゲーション (10px = 1枚)</td></tr>
<tr><td><b>左ドラッグ (パンON)</b></td><td>画像移動</td></tr>
<tr><td><b>右ドラッグ</b></td><td>W/L (↕) &amp; W/W (↔)</td></tr>
<tr><td><b>左クリック (Cross-ref ON)</b></td><td>クロス位置を指定</td></tr>
</table>
<h3>⌨ Navigation</h3>
<table cellpadding='4'>
<tr><td><b>↑ / ←</b></td><td>前のスライス</td></tr>
<tr><td><b>↓ / →</b></td><td>次のスライス</td></tr>
</table>
</td></tr></table>
""",
    'zh': """
<h2 style='margin-bottom:4px;'>Keyboard &amp; Mouse Shortcuts</h2>
<table width='100%' cellspacing='0' cellpadding='0'><tr>
<td width='50%' valign='top' style='padding-right:20px;'>
<h3>📂 File</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+O</b></td><td>打开文件</td></tr>
<tr><td><b>Ctrl+Shift+O</b></td><td>打开文件夹</td></tr>
<tr><td><b>Ctrl+S</b></td><td>保存活动面板</td></tr>
<tr><td><b>Ctrl+Shift+S</b></td><td>保存所有面板</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>退出</td></tr>
</table>
<h3>📋 Clipboard</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+C</b></td><td>复制活动面板</td></tr>
<tr><td><b>Ctrl+Shift+C</b></td><td>复制全屏<br><span style='color:#888;'>自动排除活动边框、侧边栏和工具栏</span></td></tr>
<tr><td><b>Ctrl+Alt+C</b></td><td>区域复制<br><span style='color:#888;'>拖动选择矩形，Esc取消</span></td></tr>
</table>
<h3>⇔ 图像偏移 (PPT截图用 — 允许重叠)</h3>
<table cellpadding='4'>
<tr><td><b>Shift + 左键拖动</b></td><td>向内/向外移动面板<br>
<span style='color:#888;'>每次仅操作一个轴 (水平或垂直)<br>
右/下 = 向内 (重叠)<br>
左/上 = 向外 (增大间距)<br>
平滑: 鼠标4px = 1px移动</span></td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — Gap / Zoom / Pan / W/L</td></tr>
<tr><td colspan='2' style='color:#888;'>手动输入: View → 图像偏移设置...</td></tr>
</table>
</td><td width='50%' valign='top' style='padding-left:20px; border-left:1px solid #444;'>
<h3>⊞ Layout</h3>
<table cellpadding='4'>
<tr><td><b>Ctrl+1</b></td><td>1 × 1 (单面板)</td></tr>
<tr><td><b>Ctrl+2</b></td><td>2 × 2</td></tr>
<tr><td><b>Ctrl+3</b></td><td>3 × 3</td></tr>
<tr><td colspan='2' style='color:#888;'>其他: 1×2, 1×3, 2×1, 2×3, 3×1, 3×2 — View → Layout</td></tr>
<tr><td><b>Space</b></td><td>切换活动面板 1×1 ↔ 多面板</td></tr>
</table>
<h3>🖼️ Display</h3>
<table cellpadding='4'>
<tr><td><b>T</b></td><td>DICOM标签叠加 ON/OFF (含WL/WW)</td></tr>
<tr><td><b>R</b></td><td>重置活动面板W/L (保留zoom/pan)</td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — 所有面板的Gap / Zoom / Pan / W/L</td></tr>
<tr><td><b>X</b></td><td>交叉参考 ON/OFF</td></tr>
<tr><td><b>P</b></td><td>平移模式 ON/OFF<br><span style='color:#888;'>左键拖动移动图像<br>缩放或缩小间距后用于位置调整</span></td></tr>
</table>
<h3>🖱️ Mouse</h3>
<table cellpadding='4'>
<tr><td><b>滚轮</b></td><td>切换层面</td></tr>
<tr><td><b>Ctrl + 滚轮</b></td><td>放大 / 缩小</td></tr>
<tr><td><b>中键拖动 ↕</b></td><td>缩放 (向上 = 放大)</td></tr>
<tr><td><b>左键拖动 ↕</b></td><td>切换层面 (10px = 1层)</td></tr>
<tr><td><b>左键拖动 (平移ON)</b></td><td>移动图像</td></tr>
<tr><td><b>右键拖动</b></td><td>W/L (↕) &amp; W/W (↔)</td></tr>
<tr><td><b>左键单击 (交叉参考ON)</b></td><td>设置交叉位置</td></tr>
</table>
<h3>⌨ Navigation</h3>
<table cellpadding='4'>
<tr><td><b>↑ / ←</b></td><td>上一层面</td></tr>
<tr><td><b>↓ / →</b></td><td>下一层面</td></tr>
</table>
</td></tr></table>
""",
}

_TRANSLATIONS = {
    'ko': {
        'panel_placeholder':    "시리즈 목록에서 더블클릭\n또는 파일/폴더를 여기에 드롭",
        'area_select_hint':     "✂️  영역을 좌클릭 드래그로 선택하세요  (Esc 취소)",
        'sidebar_tip':          "  더블클릭 → 활성 패널 로드  |  ▲ ▼ 휠로 스크롤",
        'status_initial':       "File 메뉴 또는 드래그&드롭으로 DICOM 폴더 열기  |  T: 태그  R: 리셋  Ctrl+C: 복사",
        'status_no_dicom_found':    "DICOM 파일을 찾지 못했습니다.",
        'status_no_dicom_readable': "읽을 수 있는 DICOM 파일 없음.",
        'status_need_folder':   "먼저 DICOM 폴더를 열어주세요.",
        'status_cross_on':      "✛  Cross-reference ON  —  커서 위치 자동 지정  |  좌클릭=위치 변경  |  X=끄기",
        'status_cross_off':     "✛  Cross-reference OFF",
        'status_panning_on':    "✋  Panning ON  —  좌클릭 드래그로 영상 위치 이동  |  슬라이스는 휠로  |  P 또는 R로 종료/리셋",
        'status_panning_off':   "✋  Panning OFF",
        'status_copy_image':    "✓  클립보드 복사 완료  —  PowerPoint에 Ctrl+V 로 붙여넣기",
        'status_copy_screen':   "✓  전체 패널 클립보드 복사 완료",
        'status_area_cancel':   "✂️  영역 캡처 취소",
        'status_zoom_1x1':      "🔍  1×1 확대  |  Space: 복원",
        'status_restore_multi': "↩  복원  |  Space: 다시 확대",
        'status_wl_reset':      "↺  W/L 리셋",
        'status_position_reset':"↺  Position 리셋  —  Gap / Zoom / Pan / W/L 초기화",
        'status_scanning':      "파일 목록 수집 중: {path}",
        'status_header_scan':   "헤더 스캔 중: {total}개 파일",
        'status_thumbnails':    "썸네일 생성 중: {n}개 시리즈",
        'status_1series':       "✓  1개 시리즈  ({n}개 이미지) — 픽셀은 표시 시 로드",
        'status_multi_series':  "✓  {n}개 이미지, {s}개 시리즈  —  처음 {p}개 {mode} 배치 완료",
        'status_multi_hint':    "  |  ◀ ▶ 페이지  T: 태그  R: 리셋",
        'status_layout':        "⊞  Layout {mode}  —  {shown}/{total} 시리즈 표시 중",
        'status_tags_on':       "🏷️  DICOM 태그 오버레이: ON  ✓",
        'status_tags_off':      "🏷️  DICOM 태그 오버레이: OFF",
        'status_restore_mode':  "↩  {mode} 복원  |  Space: 다시 확대",
        'status_area_done':     "✓  영역 캡처 완료  —  {w}×{h}px  |  PowerPoint에 Ctrl+V",
        'status_img_offset_drag':"⇔  이미지 이동: x={ox}px, y={oy}px  |  Shift+드래그(한 축씩)  |  Ctrl+G 리셋",
        'status_img_offset_set':"✓  이미지 이동: x={nx}px, y={ny}px",
        'status_saved':         "✓  저장: {path}",
        'status_page_nav':      "✓  시리즈 {s}–{e} 표시 중  (p{page}/{total})  |  ◀ ▶ 로 페이지 이동",
        'status_page_error':    "⚠ 페이지 전환 오류: {e}",
        'menu_img_offset':      "⇔  이미지 이동 설정...",
        'dlg_error_title':      "오류",
        'dlg_no_dicom':         "읽을 수 있는 DICOM 파일을 찾지 못했습니다.",
        'dlg_offset_x_title':   "이미지 이동 X",
        'dlg_offset_x_label':   "가로 이동량 (픽셀)\n\n양수 = 패널이 바깥쪽으로 (갭 증가)\n음수 = 패널이 안쪽으로 (오버랩)\n0    = 격자 정렬\n\n범위: -2000 ~ 2000",
        'dlg_offset_y_title':   "이미지 이동 Y",
        'dlg_offset_y_label':   "세로 이동량 (픽셀)\n\n양수 = 패널이 바깥쪽으로 (갭 증가)\n음수 = 패널이 안쪽으로 (오버랩)\n0    = 격자 정렬\n\n범위: -2000 ~ 2000",
        'about_desc':           "강의 자료(PPT) 제작을 위한 가볍고 빠른 DICOM 뷰어",
    },
    'en': {
        'panel_placeholder':    "Double-click in series list\nor drop file / folder here",
        'area_select_hint':     "✂️  Click and drag to select area  (Esc to cancel)",
        'sidebar_tip':          "  Double-click → load to active panel  |  ▲ ▼ scroll",
        'status_initial':       "Open DICOM folder via File menu or drag & drop  |  T: Tags  R: Reset  Ctrl+C: Copy",
        'status_no_dicom_found':    "No DICOM files found.",
        'status_no_dicom_readable': "No readable DICOM files.",
        'status_need_folder':   "Please open a DICOM folder first.",
        'status_cross_on':      "✛  Cross-reference ON  —  cursor auto-positioned  |  left-click=change position  |  X=off",
        'status_cross_off':     "✛  Cross-reference OFF",
        'status_panning_on':    "✋  Panning ON  —  left-drag to move image  |  scroll for slices  |  P or R to exit/reset",
        'status_panning_off':   "✋  Panning OFF",
        'status_copy_image':    "✓  Copied to clipboard  —  Ctrl+V to paste into PowerPoint",
        'status_copy_screen':   "✓  All panels copied to clipboard",
        'status_area_cancel':   "✂️  Area capture cancelled",
        'status_zoom_1x1':      "🔍  1×1 zoom  |  Space: restore",
        'status_restore_multi': "↩  Restored  |  Space: zoom again",
        'status_wl_reset':      "↺  W/L reset",
        'status_position_reset':"↺  Position reset  —  Gap / Zoom / Pan / W/L initialized",
        'status_scanning':      "Collecting files: {path}",
        'status_header_scan':   "Scanning headers: {total} files",
        'status_thumbnails':    "Generating thumbnails: {n} series",
        'status_1series':       "✓  1 series  ({n} images) — pixels loaded on display",
        'status_multi_series':  "✓  {n} images, {s} series  —  first {p} placed in {mode}",
        'status_multi_hint':    "  |  ◀ ▶ pages  T: Tags  R: Reset",
        'status_layout':        "⊞  Layout {mode}  —  {shown}/{total} series displayed",
        'status_tags_on':       "🏷️  DICOM tag overlay: ON  ✓",
        'status_tags_off':      "🏷️  DICOM tag overlay: OFF",
        'status_restore_mode':  "↩  {mode} restored  |  Space: zoom again",
        'status_area_done':     "✓  Area captured  —  {w}×{h}px  |  Ctrl+V in PowerPoint",
        'status_img_offset_drag':"⇔  Image offset: x={ox}px, y={oy}px  |  Shift+drag (one axis)  |  Ctrl+G reset",
        'status_img_offset_set':"✓  Image offset: x={nx}px, y={ny}px",
        'status_saved':         "✓  Saved: {path}",
        'status_page_nav':      "✓  Series {s}–{e} displayed  (p{page}/{total})  |  ◀ ▶ for pages",
        'status_page_error':    "⚠ Page navigation error: {e}",
        'menu_img_offset':      "⇔  Image Offset...",
        'dlg_error_title':      "Error",
        'dlg_no_dicom':         "No readable DICOM files found.",
        'dlg_offset_x_title':   "Image Offset X",
        'dlg_offset_x_label':   "Horizontal offset (pixels)\n\nPositive = panels outward (gap increase)\nNegative = panels inward (overlap)\n0        = grid alignment\n\nRange: -2000 ~ 2000",
        'dlg_offset_y_title':   "Image Offset Y",
        'dlg_offset_y_label':   "Vertical offset (pixels)\n\nPositive = panels outward (gap increase)\nNegative = panels inward (overlap)\n0        = grid alignment\n\nRange: -2000 ~ 2000",
        'about_desc':           "A lightweight, fast DICOM viewer for creating lecture slides",
    },
    'es': {
        'panel_placeholder':    "Doble clic en la lista de series\no arrastre archivo/carpeta aquí",
        'area_select_hint':     "✂️  Arrastre para seleccionar área  (Esc para cancelar)",
        'sidebar_tip':          "  Doble clic → cargar en panel activo  |  ▲ ▼ desplazar",
        'status_initial':       "Abrir carpeta DICOM desde menú Archivo o arrastrar y soltar  |  T: Etiquetas  R: Reset  Ctrl+C: Copiar",
        'status_no_dicom_found':    "No se encontraron archivos DICOM.",
        'status_no_dicom_readable': "Sin archivos DICOM legibles.",
        'status_need_folder':   "Por favor, abra primero una carpeta DICOM.",
        'status_cross_on':      "✛  Referencia cruzada ON  —  cursor posicionado  |  clic izq.=cambiar posición  |  X=apagar",
        'status_cross_off':     "✛  Referencia cruzada OFF",
        'status_panning_on':    "✋  Paneo ON  —  arrastrar para mover imagen  |  rueda para cortes  |  P/R para salir/reset",
        'status_panning_off':   "✋  Paneo OFF",
        'status_copy_image':    "✓  Copiado al portapapeles  —  Ctrl+V para pegar en PowerPoint",
        'status_copy_screen':   "✓  Todos los paneles copiados",
        'status_area_cancel':   "✂️  Captura de área cancelada",
        'status_zoom_1x1':      "🔍  Zoom 1×1  |  Espacio: restaurar",
        'status_restore_multi': "↩  Restaurado  |  Espacio: ampliar de nuevo",
        'status_wl_reset':      "↺  W/L reiniciado",
        'status_position_reset':"↺  Posición reiniciada  —  Gap / Zoom / Pan / W/L inicializados",
        'status_scanning':      "Recopilando archivos: {path}",
        'status_header_scan':   "Escaneando cabeceras: {total} archivos",
        'status_thumbnails':    "Generando miniaturas: {n} series",
        'status_1series':       "✓  1 serie  ({n} imágenes) — píxeles cargados al mostrar",
        'status_multi_series':  "✓  {n} imágenes, {s} series  —  primeras {p} en {mode}",
        'status_multi_hint':    "  |  ◀ ▶ páginas  T: Etiquetas  R: Reset",
        'status_layout':        "⊞  Layout {mode}  —  {shown}/{total} series mostradas",
        'status_tags_on':       "🏷️  Superposición DICOM: ON  ✓",
        'status_tags_off':      "🏷️  Superposición DICOM: OFF",
        'status_restore_mode':  "↩  {mode} restaurado  |  Espacio: ampliar de nuevo",
        'status_area_done':     "✓  Área capturada  —  {w}×{h}px  |  Ctrl+V en PowerPoint",
        'status_img_offset_drag':"⇔  Desplazamiento: x={ox}px, y={oy}px  |  Shift+arrastrar (un eje)  |  Ctrl+G reset",
        'status_img_offset_set':"✓  Desplazamiento: x={nx}px, y={ny}px",
        'status_saved':         "✓  Guardado: {path}",
        'status_page_nav':      "✓  Series {s}–{e} mostradas  (p{page}/{total})  |  ◀ ▶ para páginas",
        'status_page_error':    "⚠ Error de navegación: {e}",
        'menu_img_offset':      "⇔  Ajuste de imagen...",
        'dlg_error_title':      "Error",
        'dlg_no_dicom':         "No se encontraron archivos DICOM legibles.",
        'dlg_offset_x_title':   "Desplazamiento X",
        'dlg_offset_x_label':   "Desplazamiento horizontal (píxeles)\n\nPositivo = paneles hacia afuera (aumenta espacio)\nNegativo = paneles hacia adentro (superposición)\n0        = alineación de cuadrícula\n\nRango: -2000 ~ 2000",
        'dlg_offset_y_title':   "Desplazamiento Y",
        'dlg_offset_y_label':   "Desplazamiento vertical (píxeles)\n\nPositivo = paneles hacia afuera (aumenta espacio)\nNegativo = paneles hacia adentro (superposición)\n0        = alineación de cuadrícula\n\nRango: -2000 ~ 2000",
        'about_desc':           "Visor DICOM ligero y rápido para crear materiales de clase",
    },
    'ja': {
        'panel_placeholder':    "シリーズ一覧でダブルクリック\nまたはファイル/フォルダをドロップ",
        'area_select_hint':     "✂️  ドラッグで領域を選択  (Esc でキャンセル)",
        'sidebar_tip':          "  ダブルクリック → アクティブパネルに読み込む  |  ▲ ▼ スクロール",
        'status_initial':       "Fileメニューまたはドラッグ&ドロップでDICOMフォルダを開く  |  T: タグ  R: リセット  Ctrl+C: コピー",
        'status_no_dicom_found':    "DICOMファイルが見つかりません。",
        'status_no_dicom_readable': "読み取れるDICOMファイルがありません。",
        'status_need_folder':   "先にDICOMフォルダを開いてください。",
        'status_cross_on':      "✛  クロスリファレンス ON  —  カーソル自動配置  |  左クリック=位置変更  |  X=オフ",
        'status_cross_off':     "✛  クロスリファレンス OFF",
        'status_panning_on':    "✋  パンモード ON  —  左ドラッグで画像移動  |  ホイールでスライス  |  P/Rで終了/リセット",
        'status_panning_off':   "✋  パンモード OFF",
        'status_copy_image':    "✓  クリップボードにコピー完了  —  PowerPointでCtrl+Vで貼り付け",
        'status_copy_screen':   "✓  全パネルをクリップボードにコピー完了",
        'status_area_cancel':   "✂️  領域キャプチャをキャンセル",
        'status_zoom_1x1':      "🔍  1×1ズーム  |  Space: 復元",
        'status_restore_multi': "↩  復元  |  Space: 再拡大",
        'status_wl_reset':      "↺  W/L リセット",
        'status_position_reset':"↺  位置リセット  —  Gap / Zoom / Pan / W/L を初期化",
        'status_scanning':      "ファイル収集中: {path}",
        'status_header_scan':   "ヘッダースキャン中: {total}ファイル",
        'status_thumbnails':    "サムネイル生成中: {n}シリーズ",
        'status_1series':       "✓  1シリーズ  ({n}画像) — ピクセルは表示時に読み込み",
        'status_multi_series':  "✓  {n}画像, {s}シリーズ  —  最初の{p}個を{mode}に配置完了",
        'status_multi_hint':    "  |  ◀ ▶ ページ  T: タグ  R: リセット",
        'status_layout':        "⊞  レイアウト {mode}  —  {shown}/{total} シリーズ表示中",
        'status_tags_on':       "🏷️  DICOMタグオーバーレイ: ON  ✓",
        'status_tags_off':      "🏷️  DICOMタグオーバーレイ: OFF",
        'status_restore_mode':  "↩  {mode} 復元  |  Space: 再拡大",
        'status_area_done':     "✓  領域キャプチャ完了  —  {w}×{h}px  |  PowerPointでCtrl+V",
        'status_img_offset_drag':"⇔  画像オフセット: x={ox}px, y={oy}px  |  Shift+ドラッグ(1軸ずつ)  |  Ctrl+G リセット",
        'status_img_offset_set':"✓  画像オフセット: x={nx}px, y={ny}px",
        'status_saved':         "✓  保存: {path}",
        'status_page_nav':      "✓  シリーズ {s}–{e} 表示中  (p{page}/{total})  |  ◀ ▶ ページ移動",
        'status_page_error':    "⚠ ページ移動エラー: {e}",
        'menu_img_offset':      "⇔  画像オフセット設定...",
        'dlg_error_title':      "エラー",
        'dlg_no_dicom':         "読み取れるDICOMファイルが見つかりません。",
        'dlg_offset_x_title':   "画像オフセット X",
        'dlg_offset_x_label':   "水平移動量 (ピクセル)\n\n正の値 = パネルを外側に (ギャップ増加)\n負の値 = パネルを内側に (オーバーラップ)\n0      = グリッド整列\n\n範囲: -2000 ~ 2000",
        'dlg_offset_y_title':   "画像オフセット Y",
        'dlg_offset_y_label':   "垂直移動量 (ピクセル)\n\n正の値 = パネルを外側に (ギャップ増加)\n負の値 = パネルを内側に (オーバーラップ)\n0      = グリッド整列\n\n範囲: -2000 ~ 2000",
        'about_desc':           "講義スライド作成のための軽量・高速DICOMビューア",
    },
    'zh': {
        'panel_placeholder':    "双击系列列表\n或将文件/文件夹拖放至此",
        'area_select_hint':     "✂️  拖动鼠标选择区域  (Esc 取消)",
        'sidebar_tip':          "  双击 → 加载到活动面板  |  ▲ ▼ 滚动",
        'status_initial':       "通过File菜单或拖放方式打开DICOM文件夹  |  T: 标签  R: 重置  Ctrl+C: 复制",
        'status_no_dicom_found':    "未找到DICOM文件。",
        'status_no_dicom_readable': "没有可读取的DICOM文件。",
        'status_need_folder':   "请先打开DICOM文件夹。",
        'status_cross_on':      "✛  交叉参考 ON  —  自动定位光标  |  左键单击=更改位置  |  X=关闭",
        'status_cross_off':     "✛  交叉参考 OFF",
        'status_panning_on':    "✋  平移模式 ON  —  左键拖动移动图像  |  滚轮切换层面  |  P/R退出/重置",
        'status_panning_off':   "✋  平移模式 OFF",
        'status_copy_image':    "✓  已复制到剪贴板  —  在PowerPoint中Ctrl+V粘贴",
        'status_copy_screen':   "✓  所有面板已复制到剪贴板",
        'status_area_cancel':   "✂️  区域截图已取消",
        'status_zoom_1x1':      "🔍  1×1放大  |  Space: 还原",
        'status_restore_multi': "↩  已还原  |  Space: 再次放大",
        'status_wl_reset':      "↺  W/L 已重置",
        'status_position_reset':"↺  位置重置  —  Gap / Zoom / Pan / W/L 已初始化",
        'status_scanning':      "收集文件中: {path}",
        'status_header_scan':   "扫描文件头: {total}个文件",
        'status_thumbnails':    "生成缩略图: {n}个系列",
        'status_1series':       "✓  1个系列  ({n}幅图像) — 显示时加载像素",
        'status_multi_series':  "✓  {n}幅图像, {s}个系列  —  前{p}个已排列至{mode}",
        'status_multi_hint':    "  |  ◀ ▶ 翻页  T: 标签  R: 重置",
        'status_layout':        "⊞  布局 {mode}  —  显示 {shown}/{total} 个系列",
        'status_tags_on':       "🏷️  DICOM标签叠加: ON  ✓",
        'status_tags_off':      "🏷️  DICOM标签叠加: OFF",
        'status_restore_mode':  "↩  {mode} 已还原  |  Space: 再次放大",
        'status_area_done':     "✓  区域截图完成  —  {w}×{h}px  |  在PowerPoint中Ctrl+V",
        'status_img_offset_drag':"⇔  图像偏移: x={ox}px, y={oy}px  |  Shift+拖动(单轴)  |  Ctrl+G重置",
        'status_img_offset_set':"✓  图像偏移: x={nx}px, y={ny}px",
        'status_saved':         "✓  已保存: {path}",
        'status_page_nav':      "✓  显示系列 {s}–{e}  (p{page}/{total})  |  ◀ ▶ 翻页",
        'status_page_error':    "⚠ 页面切换错误: {e}",
        'menu_img_offset':      "⇔  图像偏移设置...",
        'dlg_error_title':      "错误",
        'dlg_no_dicom':         "未找到可读取的DICOM文件。",
        'dlg_offset_x_title':   "图像偏移 X",
        'dlg_offset_x_label':   "水平偏移量（像素）\n\n正值 = 面板向外（增大间距）\n负值 = 面板向内（重叠）\n0    = 网格对齐\n\n范围: -2000 ~ 2000",
        'dlg_offset_y_title':   "图像偏移 Y",
        'dlg_offset_y_label':   "垂直偏移量（像素）\n\n正值 = 面板向外（增大间距）\n负值 = 面板向内（重叠）\n0    = 网格对齐\n\n范围: -2000 ~ 2000",
        'about_desc':           "用于制作讲义幻灯片的轻量级快速DICOM查看器",
    },
}


class LocaleManager(QObject):
    language_changed = pyqtSignal(str)
    _instance = None

    def __init__(self):
        super().__init__()
        self._lang = 'ko'
        try:
            if _SETTINGS_PATH.exists():
                data = json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
                if data.get('language') in _TRANSLATIONS:
                    self._lang = data['language']
        except Exception:
            pass

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def lang(self):
        return self._lang

    def set_lang(self, lang):
        if lang in _TRANSLATIONS and lang != self._lang:
            self._lang = lang
            self.language_changed.emit(lang)
            try:
                data = {}
                if _SETTINGS_PATH.exists():
                    data = json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
                data['language'] = lang
                _SETTINGS_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )
            except Exception:
                pass

    def tr(self, key):
        d = _TRANSLATIONS.get(self._lang, _TRANSLATIONS['ko'])
        return d.get(key, _TRANSLATIONS['ko'].get(key, key))


def tr(key):
    return LocaleManager.instance().tr(key)


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


def _get_bvalue(ds):
    """Return DiffusionBValue as int, or None if the slice has no b-value tag."""
    try:
        return int(round(float(ds.DiffusionBValue)))
    except Exception:
        pass
    for attr in ('ImageComments', 'SequenceName'):
        try:
            txt = str(getattr(ds, attr, ''))
            m = re.search(r'\bb\s*[=:]?\s*(\d+)', txt, re.IGNORECASE)
            if m:
                return int(m.group(1))
        except Exception:
            pass
    return None


def _slice_pos_key(ds):
    """Return a scalar (mm) representing the slice's position along the acquisition axis."""
    try:
        return round(float(ds.SliceLocation), 2)
    except Exception:
        pass
    try:
        ipp    = np.array([float(x) for x in ds.ImagePositionPatient])
        iop    = np.array([float(x) for x in ds.ImageOrientationPatient])
        normal = np.cross(iop[:3], iop[3:])
        nlen   = np.linalg.norm(normal)
        if nlen > 0:
            normal /= nlen
        return round(float(np.dot(ipp, normal)), 2)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
#  그룹 동기화 매니저
# ─────────────────────────────────────────────────────────────
class GroupSyncManager:
    """Syncs scroll/WL/zoom/pan for a selected subset of DicomPanels.

    Activation paths:
      • ∞ badge click  → ctrl_toggle(panel): add/remove that panel
      • Ctrl+click     → ctrl_toggle(panel): add/remove individual panels
                         + ctrl_add(active): always include current active panel

    _sync_set holds the currently synced panels.  is_active = len >= 2.
    _propagating guard prevents re-broadcast loops.
    """

    def __init__(self):
        self._panels      = []       # all registered panels
        self._sync_set    = set()    # active sync subset
        self._propagating = False

    @property
    def is_active(self):
        return len(self._sync_set) >= 2

    def register(self, panel):
        if panel not in self._panels:
            self._panels.append(panel)

    def unregister(self, panel):
        try:
            self._panels.remove(panel)
        except ValueError:
            pass
        self._sync_set.discard(panel)
        self._refresh_all()

    # ── toggle paths ─────────────────────────────────────────

    def toggle_badge(self):
        """∞ badge: toggle between all-panels sync and off."""
        if self._sync_set == set(self._panels):
            self._sync_set.clear()
        else:
            self._sync_set = set(self._panels)
        self._refresh_all()

    def toggle(self):
        """Alias for toggle_badge (connected via badge.clicked signal)."""
        self.toggle_badge()

    def ctrl_toggle(self, panel):
        """Ctrl+click: add/remove one panel from the sync set."""
        if panel in self._sync_set:
            self._sync_set.discard(panel)
        else:
            self._sync_set.add(panel)
        self._refresh_all()

    def ctrl_add(self, panel):
        """Add panel to sync set only — never removes it (used for active-panel auto-include)."""
        if panel not in self._sync_set:
            self._sync_set.add(panel)
            self._refresh_all()

    def ctrl_clear(self):
        """Deselect all panels."""
        if self._sync_set:
            self._sync_set.clear()
            self._refresh_all()

    def _refresh_all(self):
        """Update every panel's _sync_selected flag, badge style, and border."""
        for p in self._panels:
            in_set = p in self._sync_set
            p._sync_selected = in_set
            if p._sync_badge is not None:
                p._sync_badge.set_active(in_set)
            p.update()

    # ── helpers ──────────────────────────────────────────────

    def _src_world(self, src):
        """Return the 3-D center of src's current slice (broadcast position).
        Uses pre-cached _slice_centers when available, else computes from header."""
        if (src._slice_centers
                and src.idx < len(src._slice_centers)
                and src._slice_centers[src.idx] is not None):
            return src._slice_centers[src.idx]
        # Fallback: compute center directly from header
        ds = src._get_ds()
        if ds is None:
            return None
        try:
            ipp = np.array([float(x) for x in ds.ImagePositionPatient], dtype=np.float64)
            iop = np.array([float(x) for x in ds.ImageOrientationPatient], dtype=np.float64)
            ps   = [float(x) for x in ds.PixelSpacing]
            rows = int(ds.Rows)
            cols = int(ds.Columns)
            return (ipp
                    + (cols - 1) / 2.0 * ps[1] * iop[:3]
                    + (rows - 1) / 2.0 * ps[0] * iop[3:])
        except Exception:
            return None

    # ── broadcast methods ────────────────────────────────────

    def broadcast_scroll(self, src, delta=0):
        if not self.is_active or self._propagating or src not in self._sync_set:
            return
        world = self._src_world(src)
        src_normal = src._series_normal
        self._propagating = True
        try:
            for p in self._sync_set:
                if p is src or not p.series:
                    continue
                # Same orientation → 3-D projection sync (anatomically correct)
                # Cross-plane     → delta sync (scroll together step-for-step)
                same_plane = (src_normal is not None
                              and p._series_normal is not None
                              and abs(float(np.dot(src_normal, p._series_normal))) > 0.9)
                if same_plane and world is not None:
                    p.sync_scroll_to_world(world)
                elif delta:
                    p.sync_scroll_delta(delta)
        finally:
            self._propagating = False

    def broadcast_wl(self, src, wl, ww):
        if not self.is_active or self._propagating or src not in self._sync_set:
            return
        self._propagating = True
        try:
            for p in self._sync_set:
                if p is src or not p.series:
                    continue
                p.sync_set_wl(wl, ww)
        finally:
            self._propagating = False

    def broadcast_zoom(self, src, zoom):
        if not self.is_active or self._propagating or src not in self._sync_set:
            return
        self._propagating = True
        try:
            for p in self._sync_set:
                if p is src or not p.series:
                    continue
                p.sync_set_zoom(zoom)
        finally:
            self._propagating = False

    def broadcast_pan_delta(self, src, dx, dy):
        if not self.is_active or self._propagating or src not in self._sync_set:
            return
        self._propagating = True
        try:
            for p in self._sync_set:
                if p is src or not p.series:
                    continue
                p.sync_pan_delta(dx, dy)
        finally:
            self._propagating = False


# ─────────────────────────────────────────────────────────────
#  반응형 폰트 유틸리티
# ─────────────────────────────────────────────────────────────
def _fit_font_px(text_lines, avail_w, font_family="Consolas", min_px=9, max_px=20):
    """text_lines 중 가장 긴 줄이 avail_w 안에 들어오는 최대 픽셀 크기를 반환.
    min_px에서도 안 들어오면 min_px 반환 (호출자가 word-wrap 처리)."""
    if not text_lines or avail_w <= 0:
        return max_px
    for px in range(max_px, min_px - 1, -1):
        f = QFont(font_family)
        f.setPixelSize(px)
        fm = QFontMetrics(f)
        if all(fm.horizontalAdvance(ln) <= avail_w for ln in text_lines if ln.strip()):
            return px
    return min_px


class AutoSizeLabel(QLabel):
    """각 \\n 구분 줄이 위젯 너비 안에 한 줄로 들어오도록 폰트 크기를 자동 조정하는 QLabel.
    min_px에서도 안 들어오면 word-wrap으로 두 줄 허용."""

    def __init__(self, *args, font_family="Consolas", min_px=9, max_px=18,
                 h_pad=16, base_style="", **kwargs):
        super().__init__(*args, **kwargs)
        self._font_family = font_family
        self._min_px      = min_px
        self._max_px      = max_px
        self._h_pad       = h_pad
        self._base_style  = base_style
        self._last_px     = -1
        self._refreshing  = False
        self.setWordWrap(True)

    def setText(self, text):
        super().setText(text)
        self._refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._refreshing:
            self._refresh()

    def _refresh(self):
        if self._refreshing or self.width() <= 0:
            return
        text    = self.text()
        avail_w = max(1, self.width() - self._h_pad)
        lines   = [ln for ln in text.split('\n') if ln.strip()]
        if not lines:
            return
        px = _fit_font_px(lines, avail_w, self._font_family, self._min_px, self._max_px)
        if px != self._last_px:
            self._refreshing = True
            self._last_px    = px
            self.setStyleSheet(
                self._base_style +
                f"font-size:{px}px;font-family:{self._font_family};"
            )
            self._refreshing = False


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
        self.initial_wl = None   # WL at series load time — used by Reset W/L
        self.initial_ww = None
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
        self.dwi_info            = None   # DWI position/b-value tables, or None
        self._bval_overlay       = None   # BValueOverlay child widget, or None
        self._active_bval_filter = None   # int b-value filter, or None = show all slices
        self.sync_manager        = None   # GroupSyncManager, set after construction
        self._sync_badge         = None   # SyncBadge child widget, or None
        self._sync_selected      = False  # True when Ctrl-selected for sync group
        self._series_normal      = None   # unit np.ndarray slice normal, or None
        self._slice_centers      = []     # 3-D world centre (np.ndarray) per slice
        self._slice_projections  = []     # dot(centre, normal) per slice (float|None)
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
        self.initial_wl = self.wl   # freeze load-time W/L for reset
        self.initial_ww = self.ww
        self._active_bval_filter = None
        self._build_dwi_info()
        self._build_position_cache()
        self._setup_bvalue_overlay()
        self._render()

    def clear(self):
        self.series        = []
        self._pixel_cache  = {}
        self._raw_pix = self._disp_pix = None
        self.initial_wl          = None
        self.initial_ww          = None
        self.dwi_info            = None
        self._active_bval_filter = None
        self._series_normal      = None
        self._slice_centers      = []
        self._slice_projections  = []
        self._teardown_bvalue_overlay()
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
        if idx < 0 or idx >= len(self.series):
            return None
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

        # ── Cross-reference 교차선 (이미지에 묶인 요소만 — _disp_pix에 그림) ─
        if self._crosshair is not None:
            painter = QPainter(result)
            row_f, col_f = self._crosshair
            ch_x = int(col_f * W / iw)
            ch_y = int(row_f * H / ih)
            pen = QPen(QColor(0, 255, 255), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(0, ch_y, W, ch_y)
            painter.drawLine(ch_x, 0, ch_x, H)
            painter.setPen(QPen(QColor(0, 255, 255), 2))
            painter.drawEllipse(ch_x - 6, ch_y - 6, 12, 12)
            painter.end()

        self._disp_pix = result
        self.update()
        # _disp_pix 크기 변경 → letterbox 크기 변경 → ViewerGrid가 paint offset 재계산해야
        par = self.parent()
        if par is not None and hasattr(par, '_relayout_panels'):
            par._relayout_panels()
        if self._bval_overlay is not None:
            self._update_bvalue_overlay()
        if self._sync_badge is not None:
            self._update_sync_badge()

    # _make_display 끝 위치 마커 — 텍스트/테두리는 paintEvent에서 그림

    def set_active(self, v):
        self._active = v
        self._make_display() if self._raw_pix else self.update()

    def toggle_tags(self, state=None):
        self.show_tags = (not self.show_tags) if state is None else state
        if self._bval_overlay is not None:
            if self.show_tags:
                self._update_bvalue_overlay()
            else:
                self._bval_overlay.hide()
        if self._sync_badge is not None:
            if self.show_tags:
                self._update_sync_badge()
            else:
                self._sync_badge.hide()
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

            # ── clip 해제 후 letterbox 영역 위에 텍스트/테두리 오버레이 ──
            # zoom과 무관하게 항상 letterbox 안 가장자리에 표시되도록 paintEvent에서 그림
            p.setClipRect(cx, cy, base_w, base_h)   # 글자/테두리도 letterbox 영역만
            self._paint_overlay(p, cx, cy, base_w, base_h)
            p.setClipping(False)
        else:
            p.setPen(QColor(65, 65, 65))
            _ph   = min(self.width(), self.height())
            _fpx  = max(10, min(28, round(_ph * 0.028)))
            _pf   = QFont("Arial")
            _pf.setPixelSize(_fpx)
            p.setFont(_pf)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       f"Panel {self.panel_id + 1}\n\n{tr('panel_placeholder')}")
            if self._active:
                p.setPen(QPen(QColor(0, 160, 255), 3))
                p.drawRect(1, 1, self.width() - 2, self.height() - 2)

    def _paint_overlay(self, painter, cx, cy, cw, ch):
        """letterbox 영역 (cx,cy,cw,ch) 위에 DICOM 태그 텍스트 + 활성 테두리 그리기.
        zoom의 영향을 받지 않아 항상 letterbox 가장자리에 위치."""
        _fpx = max(8, min(13, round(cw * 0.011)))
        FONT = QFont("Consolas")
        FONT.setPixelSize(_fpx)
        painter.setFont(FONT)
        LH = _fpx + 5
        M  = 5

        def draw_text(x_local, y_local, text, right=False):
            """letterbox 좌상단 기준 (x_local, y_local) 위치에 황색 그림자 텍스트.
            right=True면 letterbox 우측 정렬."""
            if not text or not text.strip():
                return
            if right:
                # 우측 정렬용 rect = letterbox 영역
                rect = QRect(cx, cy + y_local - LH + 2, cw - M, LH)
                flags = (Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
                # 그림자
                rect_s = QRect(cx + 1, cy + y_local - LH + 3, cw - M, LH)
                painter.setPen(QColor(0, 0, 0, 200))
                painter.drawText(rect_s, flags, text)
                painter.setPen(QColor(255, 255, 0))
                painter.drawText(rect, flags, text)
            else:
                ax = cx + x_local; ay = cy + y_local
                painter.setPen(QColor(0, 0, 0, 200))
                painter.drawText(ax + 1, ay + 1, text)
                painter.setPen(QColor(255, 255, 0))
                painter.drawText(ax, ay, text)

        # WL / WW / Zoom (T 토글 대상)
        if self.show_tags:
            wl_str = f"WL {self.wl:.0f}  WW {self.ww:.0f}   {self.zoom:.1f}×"
            draw_text(M, ch - 6, wl_str)

        # DICOM 태그 4-corner 오버레이
        if self.show_tags and self.series:
            ds = self._get_ds()
            if ds is not None:
                v_idx, v_total = self._virtual_idx_total()
                tl, tr, bl, br = build_overlay(ds, v_idx, v_total)
                # 상단 좌
                for i, line in enumerate(tl):
                    draw_text(M, M + LH * i + LH, line)
                # 상단 우
                for i, line in enumerate(tr):
                    draw_text(M, M + LH * i + LH, line, right=True)
                # 하단 좌 (WL 줄 위로)
                base = ch - 6 - LH
                for i, line in enumerate(reversed(bl)):
                    draw_text(M, base - LH * i, line)
                # 하단 우
                for i, line in enumerate(reversed(br)):
                    draw_text(M, base - LH * i, line, right=True)

        # 활성 패널 파란 테두리 — letterbox 영역 가장자리에 (clip 안에 들어옴)
        if self._active:
            painter.setPen(QPen(QColor(0, 160, 255), 3))
            painter.drawRect(cx + 1, cy + 1, cw - 2, ch - 2)

        # Ctrl-선택된 sync 패널 — 황금색 2px 테두리
        if getattr(self, '_sync_selected', False):
            painter.setPen(QPen(QColor(255, 215, 0), 2))
            painter.drawRect(cx + 2, cy + 2, cw - 4, ch - 4)

    # ── 마우스 ───────────────────────────────────────────────
    def mousePressEvent(self, event):
        # 갭 줄임/오버랩 상태에서 z-order 기반으로 진짜 보이는 패널을 찾아 위임.
        # QMouseEvent 재생성은 PyQt 버전 간 시그니처 차이로 위험 → 직접 상태만 셋업.
        vg   = self.parentWidget()
        real = self
        r    = None      # panel whose letterbox contains the click (or None)
        gx   = gy = 0
        if vg is not None and hasattr(vg, '_panel_at_global'):
            gx = self.x() + event.pos().x()
            gy = self.y() + event.pos().y()
            r  = vg._panel_at_global(gx, gy)
            if r is not None:
                real = r

        # Ctrl+click → toggle clicked panel + auto-include the currently active panel
        if (event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            sm = real.sync_manager
            if sm is not None:
                sm.ctrl_toggle(real)
                # In overlap mode self may differ from real — include it too
                if self is not real and self.sync_manager is not None:
                    self.sync_manager.ctrl_toggle(self)
                # Auto-include the currently active panel so the user never has
                # to Ctrl+click a panel that is already focused/active
                vg_parent = self.parentWidget()
                if vg_parent is not None and hasattr(vg_parent, 'active_panel'):
                    active = vg_parent.active_panel
                    if (active is not None
                            and active is not real
                            and active is not self
                            and active.sync_manager is not None):
                        active.sync_manager.ctrl_add(active)
            event.accept()
            return

        # Plain left click: clear sync group when clicking a non-member viewport
        # or the black letterbox area.  Badge clicks never reach here (child accepts).
        if event.button() == Qt.MouseButton.LeftButton:
            sm = self.sync_manager
            if sm is not None:
                if r is None and self.series:
                    # Click landed in the black letterbox border (not in any image rect)
                    sm.ctrl_clear()
                elif r is not None and r not in sm._sync_set:
                    # Click on a viewport that is not part of the sync group
                    sm.ctrl_clear()

        if real is not self:
            # 활성 패널 전환 + 드래그 동안의 좌표 추적은 real이 담당
            vg._activate(real)
            real._last_pos   = QPoint(gx - real.x(), gy - real.y())
            real._drag_accum = 0
            real._drag_moved = False
            real._gap_accum_x   = 0
            real._gap_accum_y   = 0
            real._gap_locked_ax = None
            # 이후 mouse move/release는 grabMouse로 real이 받음
            real.grabMouse()
            # Panning 모드 + 좌클릭 → 닫힌 손
            if (event.button() == Qt.MouseButton.LeftButton
                    and getattr(self.window(), '_pan_mode', False)):
                real.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

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
        # Shift+클릭(드래그 없음) → 그룹 sync 토글 (Shift+드래그는 이미지 이동)
        if (event.button() == Qt.MouseButton.LeftButton
                and not self._drag_moved
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                and self.sync_manager is not None):
            self.sync_manager.ctrl_toggle(self)
        # Panning 모드면 다시 열린 손으로
        if (event.button() == Qt.MouseButton.LeftButton
                and getattr(self.window(), '_pan_mode', False)):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._last_pos   = None
        self._drag_accum = 0
        # mousePress에서 grabMouse를 했을 수 있음 — 안전하게 해제
        if QApplication.mouseButtons() == Qt.MouseButton.NoButton:
            try:
                self.releaseMouse()
            except Exception:
                pass

    def mouseDoubleClickEvent(self, event):
        """패널 더블클릭 → Space 토글과 동일 (1×1 ↔ multi-panel)."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # z-order 위 패널로 위임 (활성 패널을 그 패널로 만듦)
        vg = self.parentWidget()
        if vg is not None and hasattr(vg, '_panel_at_global'):
            gx = self.x() + event.pos().x()
            gy = self.y() + event.pos().y()
            real = vg._panel_at_global(gx, gy)
            if real is not None and real is not self:
                vg._activate(real)
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
        """화면 픽셀(sx,sy) → 이미지 픽셀(row_f, col_f). 범위 밖이면 None,None.
        zoom + paint_offset(갭) + pan_offset 모두 반영."""
        if self._raw_pix is None or self._disp_pix is None:
            return None, None
        iw = self._raw_pix.width()
        ih = self._raw_pix.height()
        dw = self._disp_pix.width()
        dh = self._disp_pix.height()
        # _disp_pix가 그려지는 widget 내 좌상단 — paintEvent와 동일 식
        ox = (self.width()  - dw) // 2 + self._paint_offset_x + self._pan_offset_x
        oy = (self.height() - dh) // 2 + self._paint_offset_y + self._pan_offset_y
        lx = sx - ox
        ly = sy - oy
        if lx < 0 or ly < 0 or lx >= dw or ly >= dh:
            return None, None
        return ly * ih / dh, lx * iw / dw   # row_f, col_f

    def set_crosshair_from_world(self, world):
        """외부에서 world 좌표를 받아 교차선 설정 + 가장 가까운 슬라이스로 이동.
        Cross-link는 슬라이스 위치만 동기화 — W/L은 절대 변경하지 않는다.
        DWI 시리즈는 현재 b-value를 유지한 채 해부학적 위치만 이동."""
        if not self.series:
            return
        _wl, _ww = self.wl, self.ww          # guard: cross-link must never change W/L
        best_i = (self._find_dwi_slice(world)
                  if self.dwi_info is not None
                  else _find_best_slice(self.series, world))
        self.idx = best_i
        ds = self.series[best_i][1]
        self._crosshair = _world_to_pixel(ds, world) if _has_position_tags(ds) else None
        self._render()
        self.wl, self.ww = _wl, _ww          # restore in case any future code path modifies them

    def clear_crosshair(self):
        self._crosshair = None
        if self._raw_pix:
            self._make_display()

    # ── DWI b-value support ──────────────────────────────────

    def _build_dwi_info(self):
        """Scan series headers for multi-b-value DWI and build position/b-value tables."""
        self.dwi_info = None
        if not self.series:
            return
        slice_bvals = [_get_bvalue(ds)      for _, ds in self.series]
        slice_pos   = [_slice_pos_key(ds)   for _, ds in self.series]

        unique_bvals = sorted({b for b in slice_bvals if b is not None})
        if len(unique_bvals) < 2:
            return  # not multi-b-value DWI

        # Map rounded position → sequential position index
        pos_keys  : list  = []
        pos_to_pi : dict  = {}
        for pos in slice_pos:
            if pos is None:
                continue
            rp = round(pos, 1)
            if rp not in pos_to_pi:
                pos_to_pi[rp] = len(pos_keys)
                pos_keys.append(rp)

        # (pos_index, bval) → first slice index at that combination
        table     : dict  = {}
        slice_pidx: list  = []
        for i, (pos, bval) in enumerate(zip(slice_pos, slice_bvals)):
            rp   = round(pos, 1) if pos is not None else None
            pidx = pos_to_pi.get(rp) if rp is not None else None
            slice_pidx.append(pidx)
            if pidx is not None and bval is not None:
                table.setdefault((pidx, bval), i)

        # per-b-value list of raw slice indices (sorted by their order in series)
        b_value_slices = {bv: [i for i, b in enumerate(slice_bvals) if b == bv]
                          for bv in unique_bvals}

        self.dwi_info = {
            'b_values'      : unique_bvals,
            'pos_keys'      : pos_keys,
            'pos_to_pi'     : pos_to_pi,
            'table'         : table,
            'slice_bval'    : slice_bvals,
            'slice_pidx'    : slice_pidx,
            'b_value_slices': b_value_slices,
        }

    def _build_position_cache(self):
        """Pre-compute per-slice ImagePositionPatient and its projection onto the
        series normal.  Called at series load time.

        Algorithm (user spec):
          normal = cross(IOP_row, IOP_col) — normalised
          per slice: center = IPP + (cols-1)/2*ps[1]*row_dir + (rows-1)/2*ps[0]*col_dir
          sync lookup: argmin |dot(broadcast_center, recv_normal) - recv_proj_i|
        """
        self._series_normal     = None
        self._slice_centers     = []     # 3-D center of each slice (np.array), or None
        self._slice_projections = []     # dot(IPP, series_normal) per slice, or None
        if not self.series:
            return
        # Determine series normal from the first slice that has IOP
        normal = None
        for _, ds in self.series:
            try:
                iop  = np.array([float(x) for x in ds.ImageOrientationPatient],
                                dtype=np.float64)
                n    = np.cross(iop[:3], iop[3:])
                nlen = float(np.linalg.norm(n))
                if nlen > 1e-9:
                    normal = n / nlen
                    break
            except Exception:
                continue
        if normal is None:
            return
        self._series_normal = normal
        # Cache slice CENTER and dot(IPP, normal) for every slice.
        # Center = IPP + half-FOV offset along row/col directions.
        # dot(IPP, normal) suffices for receiver lookup because all points on
        # the same plane share the same projection along the plane's own normal.
        for _, ds in self.series:
            try:
                ipp = np.array([float(x) for x in ds.ImagePositionPatient],
                               dtype=np.float64)
                iop = np.array([float(x) for x in ds.ImageOrientationPatient],
                               dtype=np.float64)
                ps   = [float(x) for x in ds.PixelSpacing]
                rows = int(ds.Rows)
                cols = int(ds.Columns)
                center = (ipp
                          + (cols - 1) / 2.0 * ps[1] * iop[:3]
                          + (rows - 1) / 2.0 * ps[0] * iop[3:])
                self._slice_centers.append(center)
                self._slice_projections.append(float(np.dot(ipp, normal)))
            except Exception:
                self._slice_centers.append(None)
                self._slice_projections.append(None)

    def _find_dwi_slice(self, world):
        """For DWI: find anatomically closest slice while preserving the current b-value.
        Prevents interleaved DWI (b0/b1000 at identical positions) from jumping b-values."""
        best_i = _find_best_slice(self.series, world)
        di = self.dwi_info
        if di is None:
            return best_i
        pidx = (di['slice_pidx'][best_i]
                if best_i < len(di['slice_pidx']) else None)
        if pidx is None:
            return best_i
        # Use active filter b-value; fall back to the b-value of the current slice
        target_bval = self._active_bval_filter
        if target_bval is None:
            target_bval = (di['slice_bval'][self.idx]
                           if self.idx < len(di['slice_bval']) else None)
        if target_bval is None:
            return best_i
        same = di['table'].get((pidx, target_bval))
        return same if same is not None else best_i

    def _setup_bvalue_overlay(self):
        """Create BValueOverlay when series is multi-b-value DWI; teardown otherwise."""
        self._teardown_bvalue_overlay()
        if self.dwi_info is None:
            return
        ov = BValueOverlay(self.dwi_info['b_values'], parent=self)
        ov.b_value_clicked.connect(self._on_bvalue_selected)
        self._bval_overlay = ov

    def _teardown_bvalue_overlay(self):
        if self._bval_overlay is not None:
            self._bval_overlay.hide()
            self._bval_overlay.setParent(None)
            self._bval_overlay.deleteLater()
            self._bval_overlay = None

    def _update_bvalue_overlay(self):
        """Sync active-badge highlight and reposition overlay inside the letterbox."""
        ov = self._bval_overlay
        if ov is None:
            return
        # Hide with tags
        if not self.show_tags:
            ov.hide()
            return
        # Sync which badge is active (filter takes priority; fall back to per-slice tag)
        di = self.dwi_info
        active_bval = self._active_bval_filter
        if active_bval is None and di and 0 <= self.idx < len(di['slice_bval']):
            active_bval = di['slice_bval'][self.idx]
        if active_bval is not None:
            ov.set_active_bval(active_bval)
        # Reposition: bottom-left of the image letterbox
        if self._disp_pix is None or not self.series:
            ov.hide()
            return
        zoom   = max(0.001, float(self.zoom))
        base_w = int(round(self._disp_pix.width()  / zoom))
        base_h = int(round(self._disp_pix.height() / zoom))
        cx = (self.width()  - base_w) // 2 + self._paint_offset_x
        cy = (self.height() - base_h) // 2 + self._paint_offset_y
        MARGIN = 8
        ov.adjustSize()
        oy = cy + base_h - ov.height() - MARGIN
        ov.move(cx + MARGIN, max(cy + MARGIN, oy))
        ov.show()
        ov.raise_()

    def _on_bvalue_selected(self, bval):
        """Badge click: filter the slice stack to only the chosen b-value pool.
        Scrolling, drag, and key-nav will be restricted to that pool until another
        badge is clicked.  Img counter shows position within the filtered pool."""
        if not self.dwi_info or not self.series:
            return
        di   = self.dwi_info
        pool = di['b_value_slices'].get(bval, [])
        if not pool:
            return
        _wl, _ww = self.wl, self.ww
        self._active_bval_filter = bval
        self.idx = pool[0]              # reset to first slice in filtered pool
        self._render()
        self.wl, self.ww = _wl, _ww

    # ── slice navigation (respects active b-value filter pool) ──

    def _navigate_slice(self, step):
        """Move self.idx by step within the active filter pool (or the full series)."""
        if not self.series:
            return
        if self._active_bval_filter is not None and self.dwi_info:
            pool = self.dwi_info['b_value_slices'].get(self._active_bval_filter, [])
            if pool:
                try:
                    cur_pos = pool.index(self.idx)
                except ValueError:
                    cur_pos = 0
                new_pos = max(0, min(len(pool) - 1, cur_pos + step))
                new_idx = pool[new_pos]
                if new_idx != self.idx:
                    self.idx = new_idx
                    self._render()
                    if self.sync_manager:
                        self.sync_manager.broadcast_scroll(self, delta=step)
                return
        # no filter — navigate within full series
        new_idx = max(0, min(len(self.series) - 1, self.idx + step))
        if new_idx != self.idx:
            self.idx = new_idx
            self._render()
            if self.sync_manager:
                self.sync_manager.broadcast_scroll(self, delta=step)

    def _virtual_idx_total(self):
        """Return (display_idx, display_total) for the Img counter.
        When a b-value filter is active, reports position within the filtered pool."""
        if self._active_bval_filter is not None and self.dwi_info:
            pool = self.dwi_info['b_value_slices'].get(self._active_bval_filter, [])
            if pool:
                try:
                    vi = pool.index(self.idx)
                except ValueError:
                    vi = 0
                return vi, len(pool)
        return self.idx, len(self.series)

    # ── 그룹 동기화 ──────────────────────────────────────────

    def setup_sync(self, manager):
        """Attach panel to a GroupSyncManager and create the ∞ badge overlay."""
        self.sync_manager = manager
        manager.register(self)
        badge = SyncBadge(parent=self)
        badge.set_active(False)
        badge.clicked.connect(lambda: manager.ctrl_toggle(self))
        self._sync_badge = badge

    def _update_sync_badge(self):
        """Reposition ∞ badge in bottom-right of letterbox; hide when tags are off."""
        badge = self._sync_badge
        if badge is None:
            return
        if not self.show_tags:
            badge.hide()
            return
        if self._disp_pix is None or not self.series:
            badge.hide()
            return
        zoom   = max(0.001, float(self.zoom))
        base_w = int(round(self._disp_pix.width()  / zoom))
        base_h = int(round(self._disp_pix.height() / zoom))
        cx = (self.width()  - base_w) // 2 + self._paint_offset_x
        cy = (self.height() - base_h) // 2 + self._paint_offset_y
        MARGIN = 8
        badge.move(cx + base_w - badge.width()  - MARGIN,
                   cy + base_h - badge.height() - MARGIN)
        badge.show()
        badge.raise_()

    def sync_scroll_delta(self, delta):
        """Receive cross-plane broadcast: step by delta (used when planes are perpendicular)."""
        if not self.series:
            return
        new_idx = max(0, min(len(self.series) - 1, self.idx + delta))
        if new_idx != self.idx:
            self.idx = new_idx
            self._render()

    def sync_scroll_to_world(self, world):
        """Receive broadcast scroll: navigate to closest slice at world position.
        Algorithm: project broadcast center onto this series' own normal; find argmin."""
        if not self.series:
            return
        if self.dwi_info is not None:
            idx = self._find_dwi_slice(world)
        elif self._series_normal is not None and self._slice_projections:
            # dot(broadcast_IPP, recv_normal) vs dot(IPP_i, recv_normal) per slice
            target = float(np.dot(world, self._series_normal))
            best_i, best_d = 0, float('inf')
            for i, proj in enumerate(self._slice_projections):
                if proj is None:
                    continue
                d = abs(proj - target)
                if d < best_d:
                    best_d, best_i = d, i
            idx = best_i
        else:
            idx = _find_best_slice(self.series, world)
        idx = max(0, min(len(self.series) - 1, idx))
        if idx != self.idx:
            self.idx = idx
            self._render()

    def sync_set_wl(self, wl, ww):
        if not self.series:
            return
        self.wl = wl
        self.ww = ww
        self._render()

    def sync_set_zoom(self, zoom):
        if not self.series:
            return
        self.zoom = max(0.05, min(30.0, zoom))
        self._make_display()

    def sync_pan_delta(self, dx, dy):
        if not self.series:
            return
        self._pan_offset_x += dx
        self._pan_offset_y += dy
        self.update()

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
                old_pan_x, old_pan_y = self._pan_offset_x, self._pan_offset_y
                new_x = old_pan_x + dx
                new_y = old_pan_y + dy

                # 자석 효과: 인접 패널의 이미지 가장자리에 8px 이내로 가까워지면 정확히 맞춤
                vg = self.parentWidget()
                if vg is not None and hasattr(vg, '_snap_to_neighbors'):
                    new_x, new_y = vg._snap_to_neighbors(self, new_x, new_y, threshold=3)

                self._pan_offset_x = new_x
                self._pan_offset_y = new_y
                self.update()
                self._last_pos = event.pos()
                if self.sync_manager:
                    adx = self._pan_offset_x - old_pan_x
                    ady = self._pan_offset_y - old_pan_y
                    if adx != 0 or ady != 0:
                        self.sync_manager.broadcast_pan_delta(self, adx, ady)
                return

            # 좌클릭 드래그 상하 → 슬라이스 이동 (10px 누적마다 1장)
            self._drag_accum += dy
            step = int(self._drag_accum / 10)   # 10px = 슬라이스 1장
            if step != 0:
                self._drag_accum -= step * 10
                self._navigate_slice(step)
            self._last_pos = event.pos()

        elif event.buttons() & Qt.MouseButton.RightButton:
            # 우클릭 드래그: 좌우 → WW, 상하 → WL
            self.ww  = max(1.0, self.ww + dx * 3)
            self.wl += dy * 2
            self._last_pos = event.pos()
            self._render()
            if self.sync_manager:
                self.sync_manager.broadcast_wl(self, self.wl, self.ww)

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
                if self.sync_manager:
                    self.sync_manager.broadcast_zoom(self, self.zoom)
            self._last_pos = event.pos()

    def wheelEvent(self, event):
        # 갭 줄임/오버랩 상태에서 z-order 위 패널이 진짜 사용자가 보는 것 → 그쪽으로 위임
        vg = self.parentWidget()
        if vg is not None and hasattr(vg, '_panel_at_global'):
            pos = event.position()
            gx = self.x() + pos.x()
            gy = self.y() + pos.y()
            real = vg._panel_at_global(int(gx), int(gy))
            if real is not None and real is not self:
                # QWheelEvent 재생성 대신 직접 처리 — 호환성/안정성 우선
                real._handle_wheel(event.angleDelta().y(), event.modifiers())
                event.accept()
                return
        self._handle_wheel(event.angleDelta().y(), event.modifiers())
        event.accept()

    def _handle_wheel(self, delta, modifiers):
        """wheelEvent 본체 — 다른 패널에서 위임 호출도 가능하도록 분리."""
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+스크롤 → 확대/축소
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.zoom = max(0.05, min(30.0, self.zoom * factor))
            self._make_display()
            if self.sync_manager:
                self.sync_manager.broadcast_zoom(self, self.zoom)
        else:
            # 스크롤 → 슬라이스 이동
            if not self.series:
                return
            step = -1 if delta > 0 else 1   # 위로 스크롤 = 이전 슬라이스
            self._navigate_slice(step)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Left):
            self._navigate_slice(-1)
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Right):
            self._navigate_slice(1)
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
#  DWI b-value badge overlay
# ─────────────────────────────────────────────────────────────
class BValueOverlay(QWidget):
    """Semi-transparent pill-badge strip that floats inside a DicomPanel.
    Shows one badge per unique b-value; clicking a badge emits b_value_clicked(int)."""

    b_value_clicked = pyqtSignal(int)

    _BADGE_H  = 22
    _TOGGLE_W = 24
    _MARGIN   = 5
    _SPACING  = 4

    def __init__(self, b_values: list, parent=None):
        super().__init__(parent)
        self._b_values  = sorted(b_values)
        self._active    = self._b_values[0] if self._b_values else None
        self._collapsed = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(self._MARGIN, self._MARGIN,
                               self._MARGIN, self._MARGIN)
        lay.setSpacing(self._SPACING)

        # [b▾] toggle button
        self._toggle = QPushButton("b▾", self)
        self._toggle.setFixedSize(self._TOGGLE_W, self._BADGE_H)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(self._on_toggle)
        lay.addWidget(self._toggle)

        # One badge per b-value
        self._btns: dict[int, QPushButton] = {}
        for bv in self._b_values:
            lbl = "b0" if bv == 0 else f"b{bv}"
            btn = QPushButton(lbl, self)
            btn.setFixedHeight(self._BADGE_H)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda checked=False, b=bv: self.b_value_clicked.emit(b)
            )
            self._btns[bv] = btn
            lay.addWidget(btn)

        self._refresh_style()
        self.adjustSize()

    # ── public API ───────────────────────────────────────────

    def set_active_bval(self, bval):
        if bval == self._active:
            return
        self._active = bval
        self._refresh_style()

    # ── internals ────────────────────────────────────────────

    def _on_toggle(self):
        self._collapsed = not self._collapsed
        for btn in self._btns.values():
            btn.setVisible(not self._collapsed)
        self._toggle.setText("b▸" if self._collapsed else "b▾")
        self.adjustSize()
        p = self.parent()
        if p and hasattr(p, '_update_bvalue_overlay'):
            p._update_bvalue_overlay()

    def _refresh_style(self):
        base = ("border-radius:9px; font-family:Consolas; font-size:12px;"
                " font-weight:bold; padding:0 8px; border:none;")
        for bv, btn in self._btns.items():
            if bv == self._active:
                btn.setStyleSheet(base + " background:rgba(10,132,255,210); color:white;")
            else:
                btn.setStyleSheet(base + " background:rgba(30,30,30,190); color:#bbb;")
        self._toggle.setStyleSheet(
            "QPushButton { border-radius:4px; font-family:Consolas; font-size:10px;"
            " background:rgba(50,50,50,190); color:#999; border:none; padding:0 4px; }"
            "QPushButton:hover { background:rgba(80,80,80,210); }"
        )

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 80))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)
        p.end()


# ─────────────────────────────────────────────────────────────
#  동기화 배지 (∞, bottom-right of viewport)
# ─────────────────────────────────────────────────────────────
class SyncBadge(QWidget):
    """Circular ∞ badge in the bottom-right corner of a DicomPanel viewport.
    Clicking toggles global group sync ON/OFF via GroupSyncManager (all panels at once).
    Uses QPainter for text rendering to avoid QPushButton font/encoding issues."""

    clicked = pyqtSignal()
    _SIZE = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def set_active(self, v):
        if v != self._active:
            self._active = v
            self.update()

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(10, 132, 255, 210) if self._active else QColor(30, 30, 30, 200)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        fg = QColor(255, 255, 255) if self._active else QColor(200, 200, 200)
        painter.setPen(fg)
        f = QFont()
        f.setPixelSize(16)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "∞")
        painter.end()


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
        self.sync_manager = None         # set by DicomViewer after construction

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
            if self.sync_manager is not None:
                self.sync_manager.unregister(p)
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
            if self.sync_manager is not None:
                p.setup_sync(self.sync_manager)

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

    def _panel_letterbox_global_rect(self, panel):
        """패널의 letterbox(이미지가 실제 보이는 영역) 글로벌 좌표.
        zoom과 무관 — 사용자가 화면에서 이미지 영역으로 인식하는 사각형.
        hit-test (어떤 패널을 클릭했는가) 용."""
        if not panel._disp_pix:
            return None
        zoom = max(0.001, float(panel.zoom))
        base_w = int(round(panel._disp_pix.width()  / zoom))
        base_h = int(round(panel._disp_pix.height() / zoom))
        # paintEvent와 동일한 letterbox 좌상단 식 (pan_offset은 미적용)
        local_x = (panel.width()  - base_w) // 2 + panel._paint_offset_x
        local_y = (panel.height() - base_h) // 2 + panel._paint_offset_y
        return (panel.x() + local_x, panel.y() + local_y, base_w, base_h)

    def _panel_at_global(self, gx, gy):
        """ViewerGrid 좌표 (gx, gy)에서 클릭/마우스 위치에 해당하는 패널 반환.

        z-order(위에 그려진 패널이 화면에서도 위에 보임) 기준 — panels 리스트의 뒤에서
        앞으로 검사하면서 letterbox에 들어가는 첫 패널을 반환. 사용자가 화면에서 본 이미지의
        패널과 일치하는 동작.
        """
        # 뒤(위) → 앞(아래) 순회
        for p in reversed(self.panels):
            r = self._panel_letterbox_global_rect(p)
            if r is None:
                continue
            x, y, w, h = r
            if x <= gx < x + w and y <= gy < y + h:
                return p
        return None

    def _panel_image_global_rect(self, panel, pan_x=None, pan_y=None):
        """패널의 _disp_pix가 차지하는 글로벌(ViewerGrid) 좌표 사각형.
        pan_x, pan_y가 주어지면 그 값으로, 아니면 panel._pan_offset_*로."""
        if not panel._disp_pix:
            return None
        if pan_x is None:
            pan_x = panel._pan_offset_x
        if pan_y is None:
            pan_y = panel._pan_offset_y
        # 패널 widget 안에서 _disp_pix 그려지는 좌상단 (paint_offset + pan_offset)
        local_x = ((panel.width()  - panel._disp_pix.width())  // 2
                   + panel._paint_offset_x + pan_x)
        local_y = ((panel.height() - panel._disp_pix.height()) // 2
                   + panel._paint_offset_y + pan_y)
        # 글로벌 좌표 = 패널 widget의 위치 + 로컬
        gx = panel.x() + local_x
        gy = panel.y() + local_y
        return (gx, gy, panel._disp_pix.width(), panel._disp_pix.height())

    def _snap_to_neighbors(self, active_panel, new_pan_x, new_pan_y, threshold=8):
        """active_panel이 (new_pan_x, new_pan_y)로 panning할 때
        인접 패널 이미지의 4개 가장자리(L/R/T/B)에 threshold 이내로 가까워지면 정확히 일치시킴.
        반환: 보정된 (pan_x, pan_y)."""
        rect_a = self._panel_image_global_rect(active_panel, new_pan_x, new_pan_y)
        if rect_a is None:
            return (new_pan_x, new_pan_y)
        ax, ay, aw, ah = rect_a
        a_left, a_right  = ax,         ax + aw
        a_top,  a_bot    = ay,         ay + ah

        # 후보 가장자리 모음
        best_dx = None; best_x_dist = threshold + 1
        best_dy = None; best_y_dist = threshold + 1

        for p in self.panels:
            if p is active_panel:
                continue
            r = self._panel_image_global_rect(p)
            if r is None:
                continue
            bx, by, bw, bh = r
            b_left, b_right = bx, bx + bw
            b_top,  b_bot   = by, by + bh

            # X 가장자리 매칭: active 좌↔이웃 좌, 좌↔우, 우↔좌, 우↔우
            for ae, be in ((a_left, b_left), (a_left, b_right),
                           (a_right, b_left), (a_right, b_right)):
                d = be - ae   # 이웃 가장자리에 맞추려면 active를 d만큼 이동
                if abs(d) <= threshold and abs(d) < best_x_dist:
                    best_x_dist = abs(d)
                    best_dx = d

            # Y 가장자리 매칭
            for ae, be in ((a_top, b_top), (a_top, b_bot),
                           (a_bot, b_top), (a_bot, b_bot)):
                d = be - ae
                if abs(d) <= threshold and abs(d) < best_y_dist:
                    best_y_dist = abs(d)
                    best_dy = d

        snapped_x = new_pan_x + (best_dx if best_dx is not None else 0)
        snapped_y = new_pan_y + (best_dy if best_dy is not None else 0)
        return (snapped_x, snapped_y)

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
            (p.series[:], p.idx, p.wl, p.ww, p.zoom, p.initial_wl, p.initial_ww)
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
        for i, saved in enumerate(self._saved_multi):
            if i >= len(self.panels):
                break
            p = self.panels[i]
            series, idx, wl, ww, zoom = saved[:5]
            initial_wl = saved[5] if len(saved) > 5 else wl
            initial_ww = saved[6] if len(saved) > 6 else ww
            if series:
                p.series               = series
                p.idx                  = idx
                p.wl                   = wl
                p.ww                   = ww
                p.initial_wl           = initial_wl
                p.initial_ww           = initial_ww
                p.zoom                 = zoom
                p._pixel_cache         = {}
                p._active_bval_filter  = None
                p._build_dwi_info()
                p._setup_bvalue_overlay()
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
        ap = self.active_panel
        # 캡처 전 파란 테두리 + cross-hair 제거
        ap._active = False
        ch_backup = ap._crosshair
        if ch_backup is not None:
            ap._crosshair = None
            if ap._raw_pix:
                ap._make_display()
        ap.repaint()
        QApplication.processEvents()
        try:
            pix = ap.grab()
        finally:
            # 복원
            ap._active = True
            if ch_backup is not None:
                ap._crosshair = ch_backup
                if ap._raw_pix:
                    ap._make_display()
            ap.update()
        return pix

    def grab_all(self):
        # 전체 캡처도 활성 테두리 + 모든 cross-hair 없이
        ap = self.active_panel
        was_active = False
        if ap and ap._active:
            was_active = True
            ap._active = False
            ap.update()

        # 모든 패널의 crosshair 잠시 끄기 + 백업
        ch_backup = []
        for p in self.panels:
            ch_backup.append((p, p._crosshair))
            if p._crosshair is not None:
                p._crosshair = None
                if p._raw_pix:
                    p._make_display()
        # 강제 즉시 paint 처리
        for p in self.panels:
            p.repaint()
        QApplication.processEvents()

        try:
            pix = self.grab()
        finally:
            if was_active and ap:
                ap._active = True
                ap.update()
            for p, ch in ch_backup:
                if ch is not None:
                    p._crosshair = ch
                    if p._raw_pix:
                        p._make_display()
        return pix


# ─────────────────────────────────────────────────────────────
#  Copy Area 영역 선택 오버레이
# ─────────────────────────────────────────────────────────────
class _AreaSelector(QWidget):
    """viewer_grid 위에 띄워서 사용자가 좌클릭 드래그로 직사각형 영역을 선택.
    완료/취소 시 callback(rect) 호출. rect는 viewer_grid 좌표계의 QRect 또는 None(취소)."""
    def __init__(self, target, callback):
        super().__init__(target)
        self.target   = target
        self.callback = callback
        self._start   = None
        self._cur     = None
        self.setGeometry(0, 0, target.width(), target.height())
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._finish(cancel=True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.pos()
            self._cur   = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self._start is not None:
            self._cur = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._start is None:
            return
        self._cur = event.pos()
        self._finish(cancel=False)

    def _finish(self, cancel):
        # 콜백 전에 selector를 먼저 숨김 — callback 안에서 grab을 호출하면
        # selector overlay가 결과에 포함되어 어두운 사각형/외곽선이 캡처되는 걸 방지
        self.hide()
        QApplication.processEvents()
        if cancel or self._start is None or self._cur is None:
            self.callback(None)
        else:
            x1, y1 = self._start.x(), self._start.y()
            x2, y2 = self._cur.x(),   self._cur.y()
            rect = QRect(min(x1, x2), min(y1, y2),
                         abs(x2 - x1), abs(y2 - y1))
            self.callback(rect)
        self.deleteLater()

    def paintEvent(self, event):
        p = QPainter(self)
        # 화면 전체 어두운 오버레이 (선택 영역 제외)
        if self._start is not None and self._cur is not None:
            x1, y1 = self._start.x(), self._start.y()
            x2, y2 = self._cur.x(),   self._cur.y()
            sel = QRect(min(x1, x2), min(y1, y2),
                        abs(x2 - x1), abs(y2 - y1))
            # 4 영역 어둡게
            dark = QColor(0, 0, 0, 128)
            p.fillRect(0, 0, self.width(), sel.top(), dark)            # 위
            p.fillRect(0, sel.bottom() + 1,
                       self.width(), self.height() - sel.bottom() - 1, dark)  # 아래
            p.fillRect(0, sel.top(),
                       sel.left(), sel.height() + 1, dark)             # 좌
            p.fillRect(sel.right() + 1, sel.top(),
                       self.width() - sel.right() - 1, sel.height() + 1, dark)  # 우
            # 선택 사각형 외곽선
            pen = QPen(QColor(0, 200, 255), 2)
            p.setPen(pen)
            p.drawRect(sel)
            # 우상단에 크기 표시
            label = f"{sel.width()} × {sel.height()}"
            p.setFont(QFont("Consolas", 11))
            p.fillRect(sel.left(), sel.top() - 22,
                       len(label) * 9 + 12, 20, QColor(0, 0, 0, 200))
            p.setPen(QColor(0, 200, 255))
            p.drawText(sel.left() + 6, sel.top() - 7, label)
        else:
            # 시작 전: 전체 살짝 어둡게 + 안내 메시지
            p.fillRect(self.rect(), QColor(0, 0, 0, 60))
            p.setPen(QColor(0, 200, 255))
            p.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       tr('area_select_hint'))


# ─────────────────────────────────────────────────────────────
#  레이아웃 그리드 피커 (PowerPoint 스타일)
# ─────────────────────────────────────────────────────────────
class _LayoutPicker(QWidget):
    """Popup 3×3 grid picker — hover to preview, click to apply layout."""
    layout_selected = pyqtSignal(str)   # e.g. "2x3"

    CELL = 30   # px per cell
    GAP  = 5    # gap between cells
    PAD  = 12   # outer padding
    N    = 3    # grid dimension (3×3 max)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True)
        self._hc = 0   # highlighted cols (1-based, 0 = none)
        self._hr = 0   # highlighted rows
        inner = self.N * self.CELL + (self.N - 1) * self.GAP
        self.setFixedSize(inner + self.PAD * 2,
                          inner + self.PAD * 2 + 24)  # 24 = label row

    # ── geometry helpers ────────────────────────────────────────
    def _cell_rect(self, c, r):
        x = self.PAD + c * (self.CELL + self.GAP)
        y = self.PAD + r * (self.CELL + self.GAP)
        return QRect(x, y, self.CELL, self.CELL)

    def _hit(self, pos):
        """Return (col, row) 1-based under pos; (0,0) if outside grid."""
        x, y = pos.x(), pos.y()
        stride = self.CELL + self.GAP
        cx = (x - self.PAD) // stride
        ry = (y - self.PAD) // stride
        if cx < 0 or ry < 0 or cx >= self.N or ry >= self.N:
            return 0, 0
        # Reject if cursor landed in the gap, not the cell itself
        if (x - self.PAD) - cx * stride >= self.CELL:
            return 0, 0
        if (y - self.PAD) - ry * stride >= self.CELL:
            return 0, 0
        return int(cx) + 1, int(ry) + 1

    # ── paint ───────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # background + rounded border
        p.fillRect(self.rect(), QColor(36, 36, 36))
        p.setPen(QPen(QColor(88, 88, 88), 1))
        p.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 6, 6)

        hc, hr = self._hc, self._hr
        for r in range(self.N):
            for c in range(self.N):
                rect = self._cell_rect(c, r)
                lit = (c < hc and r < hr)
                fill   = QColor(0, 100, 200)   if lit else QColor(62, 62, 62)
                border = QColor(0, 160, 255)   if lit else QColor(105, 105, 105)
                p.fillRect(rect, fill)
                p.setPen(QPen(border, 1))
                p.drawRect(rect)

        # dimension label
        if hc > 0 and hr > 0:
            label = f"{hr} × {hc}"
            p.setPen(QColor(220, 220, 220))
        else:
            label = "Layout"
            p.setPen(QColor(140, 140, 140))
        label_y = self.PAD + self.N * (self.CELL + self.GAP) - self.GAP + 5
        p.setFont(QFont("Consolas", 10))
        p.drawText(QRect(0, label_y, self.width(), 20),
                   Qt.AlignmentFlag.AlignCenter, label)

    # ── interaction ─────────────────────────────────────────────
    def mouseMoveEvent(self, event):
        c, r = self._hit(event.pos())
        if (c, r) != (self._hc, self._hr):
            self._hc, self._hr = c, r
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            c, r = self._hit(event.pos())
            if c > 0 and r > 0:
                self.layout_selected.emit(f"{r}x{c}")
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def leaveEvent(self, _event):
        self._hc = self._hr = 0
        self.update()


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

        self.study_info = AutoSizeLabel(
            "",
            font_family="Consolas",
            min_px=10, max_px=16,
            h_pad=18,
            base_style="background:#161616;color:#999;"
                       "padding:8px;border-bottom:1px solid #2a2a2a;"
        )
        layout.addWidget(self.study_info)

        self._tip_label = AutoSizeLabel(
            tr('sidebar_tip'),
            font_family="Consolas",
            min_px=9, max_px=14,
            h_pad=14,
            base_style="background:#111;color:#666;"
                       "padding:5px 6px;border-bottom:1px solid #222;"
        )
        layout.addWidget(self._tip_label)

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

        # ── 아이콘(144px) + 좌우 여백을 제외한 텍스트 가용 폭 ──
        avail_w = max(50, self.width() - 144 - 22)

        # 1단계: 모든 항목 데이터 수집 + 첫 줄(설명) 목록 생성
        items_data   = []
        first_lines  = []
        for label, pairs in series_list:
            ds0  = pairs[0][1]
            num  = _tag(ds0, 'SeriesNumber',      '?')
            desc = _tag(ds0, 'SeriesDescription', f'Series {num}')
            mod  = _tag(ds0, 'Modality',           '')
            first_lines.append(f"[{num}] {desc}")
            items_data.append((label, num, desc, mod, len(pairs)))

        # 2단계: 모든 첫 줄이 한 줄에 들어오는 최대 폰트 크기 계산
        font_px = _fit_font_px(first_lines, avail_w, "Consolas", min_px=11, max_px=18)

        # 3단계: 최소 크기에서도 넘치는 항목이 있으면 word-wrap 활성화
        chk_f  = QFont("Consolas")
        chk_f.setPixelSize(font_px)
        chk_fm = QFontMetrics(chk_f)
        needs_wrap = any(chk_fm.horizontalAdvance(ln) > avail_w
                         for ln in first_lines if ln.strip())
        self.lw.setWordWrap(needs_wrap)

        # 4단계: 계산된 크기로 stylesheet 업데이트
        self.lw.setStyleSheet(f"""
            QListWidget {{
                background:#111;color:#ccc;
                border:none;font-size:{font_px}px;font-family:Consolas;
            }}
            QListWidget::item {{ padding:8px 6px;border-bottom:1px solid #1c1c1c; }}
            QListWidget::item:selected {{ background:#004a8f;color:white; }}
            QListWidget::item:hover    {{ background:#1e3a5f; }}
        """)

        # 5단계: 항목 추가
        for i, (label, num, desc, mod, count) in enumerate(items_data):
            item = QListWidgetItem(f"[{num}] {desc}\n      {count}개  {mod}")
            item.setToolTip(label)
            if thumbnails and i < len(thumbnails) and thumbnails[i] is not None:
                item.setIcon(QIcon(thumbnails[i]))
            self.lw.addItem(item)

    def clear_all(self):
        self.lw.clear()
        self.study_info.setText("")

    def retranslate(self):
        self._tip_label.setText(tr('sidebar_tip'))


# ─────────────────────────────────────────────────────────────
#  메인 윈도우
# ─────────────────────────────────────────────────────────────
class DicomViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hwang Viewer for Radiologic Presentation v3.1")
        self.setAcceptDrops(True)
        self._series_list = []
        self._series_page = 0      # 현재 페이지 (0-based)
        self._pan_mode    = False  # P 토글: 좌클릭 드래그가 영상 panning이 됨

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        LocaleManager.instance().language_changed.connect(self.retranslate)
        self.showMaximized()       # ② 시작부터 전체화면

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        hbox = QHBoxLayout(central)
        hbox.setSpacing(4)
        hbox.setContentsMargins(4, 4, 4, 4)

        self.sidebar      = SeriesSidebar()
        self.viewer_grid  = ViewerGrid()
        self.sync_manager = GroupSyncManager()
        self.viewer_grid.sync_manager = self.sync_manager
        # Register the panel(s) already created by ViewerGrid's initial set_layout call
        for p in self.viewer_grid.panels:
            p.setup_sync(self.sync_manager)
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

        self.statusBar().showMessage(tr('status_initial'))
        self.setStyleSheet(self._app_stylesheet(self._toolbar_params()))

    def _build_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("File")
        self._act(fm, "📂  Open File...",    "Ctrl+O",       self.open_file)
        self._act(fm, "📁  Open Folder...",  "Ctrl+Shift+O", self.open_folder)
        fm.addSeparator()
        self._act(fm, "💾  Save Image...",   "Ctrl+S",       self.save_active)
        self._act(fm, "💾  Save Screen...", "Ctrl+Shift+S", self.save_all)
        fm.addSeparator()
        self._act(fm, "Quit", "Ctrl+Q", self.close)

        em = mb.addMenu("Edit")
        self._act(em, "📋  Copy Image",   "Ctrl+C",       self.copy_active)
        self._act(em, "🗂️  Copy Screen",  "Ctrl+Shift+C", self.copy_all)
        self._act(em, "✂️  Copy Area...", "Ctrl+Alt+C",   self.copy_area)

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
        self._act(vm, "↺  Reset W/L",                   "R",      self._reset_active)
        self._act(vm, "⛶  Toggle 1×1 ↔ Multi  (Space)", "Space",  self._toggle_panel_zoom)
        self._act(vm, "✛  Cross-reference ON/OFF",      "X",      self._toggle_cross_link)
        self._act(vm, "✋  Panning ON/OFF",              "P",      self._toggle_pan_mode)
        vm.addSeparator()
        self._act_img_offset = self._act(vm, tr('menu_img_offset'), "", self.set_image_offset_dialog)
        self._act(vm, "↺  Reset Position",             "Ctrl+G", self.reset_image_offset)
        vm.addSeparator()
        self._act(vm, "⊞  Fill Grid with Series", "", self._fill_grid_with_series)

        hm = mb.addMenu("Help")
        self._act(hm, "⌨  Keyboard & Mouse Shortcuts...", "F1", self._show_shortcuts)
        hm.addSeparator()
        self._act(hm, "ⓘ  About...", "", self._show_about)
        hm.addSeparator()
        lang_menu = hm.addMenu("🌐  Language")
        self._lang_actions = {}
        for _code, _label in [('ko', '한국어'), ('en', 'English'), ('es', 'Español'),
                               ('ja', '日本語'), ('zh', '中文')]:
            _act = QAction(_label, self)
            _act.triggered.connect(lambda checked=False, c=_code: self._switch_lang(c))
            lang_menu.addAction(_act)
            self._lang_actions[_code] = _act
        self._update_lang_marks()

    def _act(self, menu, label, shortcut, slot):
        a = QAction(label, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _show_layout_picker(self):
        picker = _LayoutPicker(self)
        picker.layout_selected.connect(self._change_layout)
        for tb in (self._toolbar1, self._toolbar2):
            w = tb.widgetForAction(self._layout_action)
            if w is not None:
                picker.move(w.mapToGlobal(QPoint(0, w.height())))
                break
        else:
            picker.move(QCursor.pos())
        picker.show()

    def _switch_lang(self, lang):
        LocaleManager.instance().set_lang(lang)

    def _update_lang_marks(self):
        current = LocaleManager.instance().lang()
        labels = {'ko': '한국어', 'en': 'English', 'es': 'Español', 'ja': '日本語', 'zh': '中文'}
        for code, act in self._lang_actions.items():
            act.setText(('● ' if code == current else '  ') + labels[code])

    def retranslate(self):
        self._act_img_offset.setText(tr('menu_img_offset'))
        self._update_lang_marks()
        self.sidebar.retranslate()
        self.viewer_grid.update()

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
        p = self._toolbar_params()
        self._tb_has_break     = True   # break exists between tb1/tb2 initially
        self._tb_widths_stale  = True   # widths need measuring on first layout call
        self._tb_base_widths   = []     # widths measured at DPI-base font
        self._tb_font_applied  = None   # font_px currently reflected in stylesheet

        # ── Two toolbar rows (content distributed dynamically) ────
        tb1 = QToolBar("Row 1", self)
        tb1.setMovable(False)
        tb1.setIconSize(QSize(p['icon_sz'], p['icon_sz']))
        self.addToolBar(tb1)
        self._toolbar1 = tb1

        self.addToolBarBreak()

        tb2 = QToolBar("Row 2", self)
        tb2.setMovable(False)
        tb2.setIconSize(QSize(p['icon_sz'], p['icon_sz']))
        self.addToolBar(tb2)
        self._toolbar2 = tb2

        # ── helpers ───────────────────────────────────────────────
        def act(label, slot=None):
            a = QAction(label, self)
            if slot:
                a.triggered.connect(slot)
            return a

        def sep():
            a = QAction(self)
            a.setSeparator(True)
            return a

        # ── Layout action (replaces QToolButton; position resolved via widgetForAction) ──
        self._layout_action = act("⊞ Layout ▾", self._show_layout_picker)

        # ── Page label action (replaces QLabel; dim-styled after each redistribution) ──
        self._page_action = act("  Series  -  ")

        # ── Flat ordered list of ALL toolbar items ────────────────
        self._all_tb_actions = [
            act("📂 File",         self.open_file),
            act("📁 Folder",       self.open_folder),
            sep(),
            self._layout_action,
            act("⊞ Fill",          self._fill_grid_with_series),
            sep(),
            self._page_action,
            act("◀",               self._series_prev_page),
            act("▶",               self._series_next_page),
            sep(),
            act("🏷️ Tags",         self._toggle_tags),
            act("↺ W/L",           self._reset_active),
            act("↺ Position",      self.reset_image_offset),
            act("✛ Cross-ref",     self._toggle_cross_link),
            act("✋ Panning",       self._toggle_pan_mode),
            sep(),
            act("📋 Copy Image",   self.copy_active),
            act("🗂️ Copy Screen",  self.copy_all),
            act("✂️ Copy Area",    self.copy_area),
            sep(),
            act("💾 Save Image",   self.save_active),
            act("💾 Save Screen",  self.save_all),
        ]

        # ── Load all into tb1 initially; _update_toolbar_layout redistributes ──
        for a in self._all_tb_actions:
            tb1.addAction(a)

    # ── DPI-adaptive toolbar scaling ────────────────────────────

    def _toolbar_params(self):
        """Compute toolbar font/icon sizes scaled to the current screen's logical DPI.

        Uses logicalDotsPerInch so that:
          • 100%-scaling 4K (high physical DPI, no OS scaling) → scale > 1 (text grows)
          • HiDPI-managed 4K (devicePixelRatio=2, logical DPI ≈ 96) → scale ≈ 1 (Qt handles it)
          • Windows 125%/150% text scaling → scale 1.25/1.5
        """
        screen = self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        dpi   = screen.logicalDotsPerInch() if screen else 96.0
        scale = max(0.6, min(3.0, dpi / 96.0))

        font_px = max(8,  round(24 * scale * 0.64))  # 4/5 × 4/5 of baseline
        icon_sz = max(14, round(24 * scale * 0.8))
        pad_v   = max(1,  round(3  * scale))   # tight vertical padding
        pad_h   = max(6,  round(12 * scale))
        spacing = max(1,  round(3  * scale))   # tight inter-button spacing
        tb_pad  = max(1,  round(2  * scale))   # tight toolbar outer padding

        # Anti-clipping: iteratively reduce font_px until text height ≤ icon height.
        # This caps the toolbar row to max(icon_sz, font_h) + 2*pad_v, preventing
        # oversized text from blowing out the toolbar on extreme DPI values.
        f = QFont()
        f.setPixelSize(font_px)
        while QFontMetrics(f).height() > icon_sz and font_px > 8:
            font_px -= 1
            f.setPixelSize(font_px)

        return dict(scale=scale, font_px=font_px, icon_sz=icon_sz,
                    pad_v=pad_v, pad_h=pad_h, spacing=spacing, tb_pad=tb_pad)

    def _app_stylesheet(self, p):
        """Build the application stylesheet using DPI-scaled toolbar params."""
        sc  = p['scale']
        fs  = p['font_px']
        pv  = p['pad_v']
        ph  = p['pad_h']
        sp  = p['spacing']
        tbp = p['tb_pad']
        fs_s = max(10, round(14 * sc))   # status bar
        fs_m = max(11, round(15 * sc))   # menu bar
        fs_u = max(10, round(14 * sc))   # menus
        fs_p = max(8,  round(12 * sc))   # progress bar
        return f"""
            QMainWindow {{ background:#111; }}
            QStatusBar  {{ background:#1a1a1a;color:#888;font-size:{fs_s}px; }}
            QMenuBar    {{ background:#1e1e1e;color:#ccc;font-size:{fs_m}px; }}
            QMenuBar::item:selected {{ background:#333; }}
            QMenu       {{ background:#2a2a2a;color:#ccc;border:1px solid #444;font-size:{fs_u}px; }}
            QMenu::item:selected {{ background:#004a8f; }}
            QToolBar    {{ background:#1e1e1e;border-bottom:1px solid #333;
                          spacing:{sp}px;padding:{tbp}px; }}
            QToolButton {{ color:#ccc;padding:{pv}px {ph}px;border-radius:4px;font-size:{fs}px; }}
            QToolButton:hover   {{ background:#333; }}
            QToolButton:pressed {{ background:#004a8f; }}
            QProgressBar {{
                background:#222; color:#ddd; border:1px solid #333;
                border-radius:3px; text-align:center; font-size:{fs_p}px;
            }}
            QProgressBar::chunk {{ background:#0a84ff; border-radius:2px; }}
        """

    def _apply_toolbar_scale(self):
        """Re-apply DPI-scaled toolbar params (called on screen change)."""
        p = self._toolbar_params()
        self.setStyleSheet(self._app_stylesheet(p))
        for attr in ('_toolbar1', '_toolbar2'):
            if hasattr(self, attr):
                getattr(self, attr).setIconSize(QSize(p['icon_sz'], p['icon_sz']))
        self._tb_widths_stale = True  # button sizes changed — re-measure on next layout
        self._update_toolbar_layout()

    def _update_toolbar_layout(self):
        """Distribute toolbar actions across rows, growing font to fill row 1 when possible.

        Strategy:
          1. Measure button widths at base DPI font.
          2. If all fit in row 1 with slack, scale up font (linear estimate) so the
             row is filled.  Apply the new font and re-measure once to verify.
             If the scaled font overshoots, revert to base.
          3. If base font already overflows row 1, fall back to two rows.
        """
        if not hasattr(self, '_all_tb_actions') or not hasattr(self, '_toolbar1'):
            return

        actions   = self._all_tb_actions
        available = self.width()
        if available <= 0:
            return

        p         = self._toolbar_params()
        base_font = p['font_px']
        max_font  = p['icon_sz']   # text height must not exceed icon height

        def _do_measure(font_px):
            """Apply font_px to stylesheet, load all actions into tb1, return width list."""
            self.setStyleSheet(self._app_stylesheet(dict(p, font_px=font_px)))
            for tb in (self._toolbar1, self._toolbar2):
                tb.setIconSize(QSize(p['icon_sz'], p['icon_sz']))
            self._toolbar1.clear()
            self._toolbar2.clear()
            for a in actions:
                self._toolbar1.addAction(a)
            return [
                (self._toolbar1.widgetForAction(a).sizeHint().width()
                 if self._toolbar1.widgetForAction(a) else 0)
                for a in actions
            ]

        # ── (Re-)measure base widths when DPI changes ─────────────
        if getattr(self, '_tb_widths_stale', True):
            self._tb_base_widths  = _do_measure(base_font)
            self._tb_widths       = self._tb_base_widths[:]
            self._tb_font_applied = base_font
            self._tb_widths_stale = False

        base_total = sum(self._tb_base_widths)

        # ── Determine target font ─────────────────────────────────
        if 0 < base_total <= available:
            # Everything fits in one row — scale font to fill width
            target = min(round(base_font * available / base_total), max_font)
            target = max(target, base_font)
        else:
            target = base_font   # needs two rows; stay at base

        # ── Apply target font if changed ──────────────────────────
        if target != getattr(self, '_tb_font_applied', base_font):
            new_w = _do_measure(target)
            if target > base_font and sum(new_w) > available:
                # Linear estimate overshot due to fixed padding — revert
                new_w = _do_measure(base_font)
                target = base_font
            self._tb_widths       = new_w
            self._tb_font_applied = target

        # ── Find split: fill row 1 until width exceeded ───────────
        cumulative = 0
        split      = len(actions)
        for i, w in enumerate(self._tb_widths):
            cumulative += w
            if cumulative > available:
                split = i
                break

        # Trim trailing separators from row 1
        while split > 0 and actions[split - 1].isSeparator():
            split -= 1

        # Skip leading separators for row 2
        row2_start = split
        while row2_start < len(actions) and actions[row2_start].isSeparator():
            row2_start += 1

        # ── Redistribute ──────────────────────────────────────────
        self._toolbar1.clear()
        self._toolbar2.clear()
        for a in actions[:split]:
            self._toolbar1.addAction(a)
        for a in actions[row2_start:]:
            self._toolbar2.addAction(a)

        # Dim the page-label action so it reads as a label, not a button
        for tb in (self._toolbar1, self._toolbar2):
            w = tb.widgetForAction(self._page_action)
            if w is not None:
                w.setStyleSheet("color:#aaa; background:transparent;")
                break

        # ── Toggle the row break ───────────────────────────────────
        has_row2 = row2_start < len(actions)
        if has_row2 != self._tb_has_break:
            self._tb_has_break = has_row2
            if has_row2:
                self.insertToolBarBreak(self._toolbar2)
            else:
                self.removeToolBarBreak(self._toolbar2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_toolbar_layout()

    def showEvent(self, event):
        super().showEvent(event)
        win = self.windowHandle()
        if win is not None and not getattr(self, '_screen_signal_connected', False):
            win.screenChanged.connect(self._on_screen_changed)
            self._screen_signal_connected = True
        self._update_toolbar_layout()

    def _on_screen_changed(self, _screen):
        self._apply_toolbar_scale()

    # ────────────────────────────────────────────────────────────

    def _page_size(self):
        """현재 layout의 패널 수 (페이지당 시리즈 수)."""
        return max(1, len(self.viewer_grid.panels))

    def _update_page_label(self):
        n = len(self._series_list)
        if n == 0:
            self._page_action.setText("  Series  -  ")
            return
        ps      = self._page_size()
        page    = self._series_page
        start   = page * ps + 1
        end     = min(start + ps - 1, n)
        total_pages = (n - 1) // ps + 1
        self._page_action.setText(
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
            self.statusBar().showMessage(tr('status_page_error').format(e=e), 10000)

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
            self.statusBar().showMessage(tr('status_page_error').format(e=e), 10000)

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
        self.statusBar().showMessage(tr('status_page_nav').format(
            s=s, e=e, page=self._series_page + 1, total=total_pages))

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
        self.statusBar().showMessage(tr('status_scanning').format(path=path))
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
            self.statusBar().showMessage(tr('status_no_dicom_found'))
            QMessageBox.warning(self, tr('dlg_error_title'), tr('dlg_no_dicom'))
            return

        total = len(candidates)
        self._progress_show("Header scan", 0, total)
        self.statusBar().showMessage(tr('status_header_scan').format(total=total))

        _t_start = time.perf_counter()  # ⏱ TIMER: 전체 시작

        # ── 1단계: 헤더 병렬 읽기 (캐시 우선) ──────────────────
        _t0       = time.perf_counter()  # ⏱ TIMER: 헤더 스캔 시작
        file_headers: list = []
        cache_key = str(p.resolve()) if p.is_dir() else None
        cache_hit = False

        if cache_key and cache_key in _header_cache:
            cached_n, cached_headers = _header_cache[cache_key]
            if cached_n == total:
                file_headers = list(cached_headers)
                cache_hit    = True
            else:
                del _header_cache[cache_key]   # 파일 수 변경 → 캐시 무효화

        if not file_headers:
            done      = 0
            n_workers = max(2, os.cpu_count() or 4)
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                futures = {ex.submit(_read_dicom_header, str(f)): f
                           for f in candidates}
                for fut in as_completed(futures):
                    try:
                        result = fut.result()
                        if result:
                            path_str, ds = result
                            file_headers.append((Path(path_str), ds))
                    except Exception:
                        pass
                    done += 1
                    if done % 10 == 0 or done == total:
                        self._progress_show("Header scan", done, total)
            if cache_key and file_headers:
                _header_cache[cache_key] = (total, list(file_headers))

        _t1 = time.perf_counter()  # ⏱ TIMER: 헤더 스캔 종료
        print(f"[TIMER] 1단계 헤더 스캔:    {_t1-_t0:.3f}s  "
              f"({total}파일, {len(file_headers)}성공)"
              + (" [캐시 히트]" if cache_hit else ""))

        if not file_headers:
            self._progress_hide()
            self.statusBar().showMessage(tr('status_no_dicom_readable'))
            QMessageBox.warning(self, tr('dlg_error_title'), tr('dlg_no_dicom'))
            return

        # ── 2단계: SeriesInstanceUID 기준 그룹핑 ────────────────
        _t0 = time.perf_counter()  # ⏱ TIMER: 그룹핑 시작
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
        _t1 = time.perf_counter()  # ⏱ TIMER: 그룹핑 종료
        print(f"[TIMER] 2단계 그룹핑:        {_t1-_t0:.3f}s  ({len(self._series_list)}개 시리즈)")

        # ── 3단계: 시리즈별 썸네일 생성 (가운데 슬라이스) ──────
        _t0 = time.perf_counter()  # ⏱ TIMER: 썸네일 시작
        n_series = len(self._series_list)
        self._progress_show("Thumbnails", 0, n_series)
        self.statusBar().showMessage(tr('status_thumbnails').format(n=n_series))
        thumbs = []
        for i, (label, pairs) in enumerate(self._series_list):
            thumbs.append(self._make_thumbnail(pairs))
            self._progress_show("Thumbnails", i + 1, n_series)
        _t1 = time.perf_counter()  # ⏱ TIMER: 썸네일 종료
        print(f"[TIMER] 3단계 썸네일 생성:  {_t1-_t0:.3f}s  ({n_series}개 시리즈, 평균 {((_t1-_t0)/max(1,n_series)):.3f}s/시리즈)")

        # 사이드바
        self.sidebar.set_study(file_headers[0][1])
        self.sidebar.populate(self._series_list, thumbs)
        self._series_page = 0

        # ── 4단계: 첫 이미지 패널 로드 ─────────────────────────
        _t0 = time.perf_counter()  # ⏱ TIMER: 이미지 로드 시작
        n = len(self._series_list)
        if n == 1:
            self.viewer_grid.set_layout('1x1')
            self.viewer_grid.load_to_active(self._series_list[0][1])
            msg = tr('status_1series').format(n=len(file_headers))
        else:
            # 사용자가 1×1로 두고 있었다면 시리즈 수에 맞는 layout 자동 선택.
            # 이미 multi-panel 모드면 그대로 존중 (3×3 골라뒀으면 9개 다 채움)
            if self.viewer_grid._mode == '1x1':
                self.viewer_grid.set_layout(self._auto_pick_layout(n))
            ps = self._page_size()
            self.viewer_grid.load_multi_series(self._series_list[:ps])
            placed = min(n, ps)
            msg = tr('status_multi_series').format(
                n=len(file_headers), s=n, p=placed, mode=self.viewer_grid._mode)
        _t1 = time.perf_counter()  # ⏱ TIMER: 이미지 로드 종료
        print(f"[TIMER] 4단계 이미지 패널 로드: {_t1-_t0:.3f}s")

        print(f"[TIMER] ─────────────────────────────────────────")
        print(f"[TIMER] 전체 로딩:           {_t1-_t_start:.3f}s  (총 {total}파일, {len(self._series_list)}시리즈)")

        self._update_page_label()
        self._progress_hide()
        self.statusBar().showMessage(msg + tr('status_multi_hint'))

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
            self.statusBar().showMessage(tr('status_need_folder'))
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
        self.statusBar().showMessage(tr('status_layout').format(
            mode=mode, shown=len(used_idx), total=len(self._series_list)))

    def _toggle_cross_link(self):
        new_state = not self.viewer_grid.cross_link_state()
        self.viewer_grid.set_cross_link(new_state)
        if new_state:
            self.statusBar().showMessage(tr('status_cross_on'))
        else:
            self.statusBar().showMessage(tr('status_cross_off'))

    def _toggle_tags(self):
        self.viewer_grid.toggle_tags_all()
        state = self.viewer_grid.tag_state()
        self.statusBar().showMessage(
            tr('status_tags_on') if state else tr('status_tags_off')
        )

    def _show_shortcuts(self):
        """전체 단축키 / 마우스 조작 가이드"""
        lang = LocaleManager.instance().lang()
        html = _SHORTCUTS_HTML.get(lang, _SHORTCUTS_HTML['ko'])

        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard & Mouse Shortcuts")
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            dlg.resize(min(int(sg.width() * 0.82), 1400),
                       min(int(sg.height() * 0.88), 1000))
        else:
            dlg.resize(1100, 800)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 8)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(html)
        browser.setStyleSheet(
            "QTextBrowser { background:#1e1e1e; color:#ddd; "
            "font-size:13px; border:1px solid #444; }"
        )
        layout.addWidget(browser)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(dlg.accept)
        layout.addWidget(btns)

        dlg.exec()

    def _show_about(self):
        """About 대화상자"""
        QMessageBox.about(
            self,
            "About",
            "<h2>Hwang Viewer for Radiologic Presentation</h2>"
            "<p><b>v3.1</b></p>"
            f"<p>{tr('about_desc')}</p>"
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
                self.statusBar().showMessage(tr('status_restore_mode').format(mode=mode))
            else:
                self._load_current_page()
                self.statusBar().showMessage(tr('status_restore_multi'))
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
                p.series              = saved
                p.idx                 = saved_idx
                p.wl                  = saved_wl
                p.ww                  = saved_ww
                p.zoom                = saved_zoom
                p._pixel_cache        = {}
                p._active_bval_filter = None
                p._build_dwi_info()
                p._setup_bvalue_overlay()
                p._render()
                self.statusBar().showMessage(tr('status_zoom_1x1'))

    def _reset_active(self):
        """활성 패널의 W/L만 리셋. zoom과 pan은 유지 (Reset Position이 따로 담당)."""
        p = self.viewer_grid.active_panel
        if p and p.series:
            if p.initial_wl is not None and p.initial_ww is not None:
                p.wl = p.initial_wl
                p.ww = p.initial_ww
            else:
                p._auto_wl()
            p._render()
            if p.sync_manager and p.sync_manager.is_active:
                p.sync_manager.broadcast_wl(p, p.wl, p.ww)
            self.statusBar().showMessage(tr('status_wl_reset'))

    # ── Panning 모드 (P) ─────────────────────────────────────
    def _toggle_pan_mode(self):
        self._pan_mode = not self._pan_mode
        cursor = (Qt.CursorShape.OpenHandCursor if self._pan_mode
                  else Qt.CursorShape.ArrowCursor)
        for p in self.viewer_grid.panels:
            p.setCursor(cursor)
        if self._pan_mode:
            self.statusBar().showMessage(tr('status_panning_on'))
        else:
            self.statusBar().showMessage(tr('status_panning_off'))

    # ── 캡처 ─────────────────────────────────────────────────
    def copy_active(self):
        pix = self.viewer_grid.grab_active()
        if pix:
            QApplication.clipboard().setPixmap(pix)
            self.statusBar().showMessage(tr('status_copy_image'))

    def copy_all(self):
        pix = self.viewer_grid.grab_all()
        if pix:
            QApplication.clipboard().setPixmap(pix)
            self.statusBar().showMessage(tr('status_copy_screen'))

    def copy_area(self):
        """사용자가 viewer_grid 위에 사각형을 그려서 그 영역만 캡처."""
        # 활성 패널 파란 테두리 + 모든 패널의 cross-hair 일시 제거
        active = self.viewer_grid.active_panel
        was_active = False
        if active and active._active:
            was_active = True
            active._active = False
            active.update()

        # 모든 패널의 crosshair 잠시 끄기 (각 패널 별 backup)
        crosshair_backup = []
        for p in self.viewer_grid.panels:
            crosshair_backup.append((p, p._crosshair))
            if p._crosshair is not None:
                p._crosshair = None
                if p._raw_pix:
                    p._make_display()   # crosshair는 _disp_pix에 그려지므로 재생성 필요
        QApplication.processEvents()

        def on_done(rect):
            try:
                if rect is None or rect.width() < 4 or rect.height() < 4:
                    self.statusBar().showMessage(tr('status_area_cancel'))
                    return
                # 캡처 직전 — paint가 확실히 끝난 상태로 보장
                if active is not None:
                    active.repaint()
                for p, _ch in crosshair_backup:
                    p.repaint()
                QApplication.processEvents()

                full = self.viewer_grid.grab()
                # HiDPI 보정
                dpr_x = full.width()  / max(1, self.viewer_grid.width())
                dpr_y = full.height() / max(1, self.viewer_grid.height())
                scaled = QRect(
                    int(round(rect.x()      * dpr_x)),
                    int(round(rect.y()      * dpr_y)),
                    int(round(rect.width()  * dpr_x)),
                    int(round(rect.height() * dpr_y)),
                )
                cropped = full.copy(scaled)
                QApplication.clipboard().setPixmap(cropped)
                self.statusBar().showMessage(
                    tr('status_area_done').format(w=cropped.width(), h=cropped.height())
                )
            finally:
                # 활성 테두리 복원
                if was_active and active:
                    active._active = True
                    active.update()
                # crosshair 복원
                for p, ch in crosshair_backup:
                    if ch is not None:
                        p._crosshair = ch
                        if p._raw_pix:
                            p._make_display()

        sel = _AreaSelector(self.viewer_grid, on_done)
        sel.show()
        sel.raise_()
        sel.setFocus()

    # ── 패널 이미지 이동 (PPT 캡처용 — 갭 조절 + 오버랩) ────
    def _adjust_image_offset_delta(self, dx, dy):
        """Shift+드래그에서 호출 — 이미지 offset에 (dx, dy) 더하기."""
        ox, oy = self.viewer_grid.adjust_image_offset_by(dx, dy)
        self.statusBar().showMessage(
            tr('status_img_offset_drag').format(ox=f"{ox:+d}", oy=f"{oy:+d}"), 3000
        )

    def set_image_offset_dialog(self):
        """View 메뉴에서 호출 — 이미지 offset 수동 입력 (다른 환자에서도 같은 값 재사용)."""
        ox, oy = self.viewer_grid.image_offset()
        x, ok = QInputDialog.getInt(
            self, tr('dlg_offset_x_title'), tr('dlg_offset_x_label'),
            ox, -2000, 2000, 5
        )
        if not ok:
            return
        y, ok = QInputDialog.getInt(
            self, tr('dlg_offset_y_title'), tr('dlg_offset_y_label'),
            oy, -2000, 2000, 5
        )
        if not ok:
            return
        nx, ny = self.viewer_grid.set_image_offset(x, y)
        self.statusBar().showMessage(tr('status_img_offset_set').format(nx=f"{nx:+d}", ny=f"{ny:+d}"))

    def reset_image_offset(self):
        """모든 위치 관련 상태 리셋: 갭, 패널 이동, 모든 패널의 zoom + pan + W/L."""
        self.viewer_grid.reset_image_offset()
        for p in self.viewer_grid.panels:
            if p.series:
                p.zoom = 1.0
                if p.initial_wl is not None and p.initial_ww is not None:
                    p.wl = p.initial_wl
                    p.ww = p.initial_ww
                else:
                    p._auto_wl()
                p._pan_offset_x = 0
                p._pan_offset_y = 0
                p._render()
            else:
                p._pan_offset_x = 0
                p._pan_offset_y = 0
                p.update()
        self.statusBar().showMessage(tr('status_position_reset'))

    def save_active(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", "capture",
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)"
        )
        if path:
            pix = self.viewer_grid.grab_active()
            if pix:
                pix.save(path)
                self.statusBar().showMessage(tr('status_saved').format(path=path))

    def save_all(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save All Panels", "capture_all",
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)"
        )
        if path:
            pix = self.viewer_grid.grab_all()
            if pix:
                pix.save(path)
                self.statusBar().showMessage(tr('status_saved').format(path=path))

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
    multiprocessing.freeze_support()  # PyInstaller EXE에서 서브프로세스 spawn 허용
    main()
