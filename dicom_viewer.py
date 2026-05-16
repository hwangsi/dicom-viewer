#!/usr/bin/env python3
"""
Hwang Viewer for Radiologic Presentation v4.1
==========================================
?ㅼ튂: pip install pydicom pyqt6 numpy pylibjpeg

議곗옉:
  Left drag (醫뚯슦/?곹븯)  : WW / WL 議곗젅
  Scroll                 : ?щ씪?댁뒪 ?대룞 (?댁쟾/?ㅼ쓬)
  Ctrl + Scroll          : ?뺣? / 異뺤냼
  T                      : DICOM ?쒓렇 ?ㅻ쾭?덉씠 ON/OFF
  R                      : W/L & Zoom 由ъ뀑
  Ctrl+1 / Ctrl+2        : 1횞1 / 2횞2 ?덉씠?꾩썐
  Ctrl+C                 : ?쒖꽦 ?⑤꼸 ?대┰蹂대뱶 蹂듭궗
  Ctrl+Shift+C           : ?꾩껜 ?⑤꼸 ?대┰蹂대뱶 蹂듭궗
  Ctrl+S / Ctrl+Shift+S  : ?쒖꽦/?꾩껜 ???
"""

import sys
import os
import re
import json
import time
import math
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
    """ProcessPoolExecutor ?뚯빱 ??pickle???꾪빐 諛섎뱶??top-level ?⑥닔?ъ빞 ??"""
    try:
        ds = pydicom.dcmread(path_str, stop_before_pixels=True, force=True)
        _ = str(getattr(ds, 'SeriesInstanceUID', None) or '')
        return (path_str, ds)
    except Exception:
        return None


_header_cache: dict = {}  # {?대뜑 ?덈?寃쎈줈: (?뚯씪?? [(Path, ds), ...])}

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


# ?????????????????????????????????????????????????????????????
#  i18n ??translations & LocaleManager
# ?????????????????????????????????????????????????????????????
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
<tr><td><b>T</b></td><td>표시 3단계 전환<br><span style='color:#888;'>태그+annotation → annotation만 → 모두 숨김</span></td></tr>
<tr><td><b>R</b></td><td>활성 패널 W/L 리셋 (zoom/pan은 유지)</td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — 모든 패널의 Gap / Zoom / Pan / W/L 리셋</td></tr>
<tr><td><b>X</b></td><td>Cross-reference ON/OFF</td></tr>
<tr><td><b>P</b></td><td>Panning ON/OFF<br><span style='color:#888;'>좌클릭 드래그가 영상 이동이 됨<br>줌이나 갭 줄임 후 영상 위치 조정용</span></td></tr>
</table>
<h3>✏️ Annotation</h3>
<table cellpadding='4'>
<tr><td><b>Measure / Arrow / Text / ROI</b></td><td>툴바 또는 Annotation 메뉴에서 선택 후 영상 위에 작성</td></tr>
<tr><td><b>ESC</b></td><td>현재 annotation tool 종료</td></tr>
<tr><td><b>기존 annotation 드래그</b></td><td>툴 선택 없이도 위치 수정<br><span style='color:#888;'>ROI/선/화살표/text를 잡아 이동, ROI는 이동 후 통계 재계산</span></td></tr>
<tr><td><b>측정값 박스 드래그</b></td><td>ROI 통계나 length 라벨 박스 위치만 이동</td></tr>
<tr><td><b>CLR Ann / CLR All Ann</b></td><td>활성 패널 또는 전체 패널 annotation 삭제</td></tr>
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
<tr><td><b>T</b></td><td>3-step display cycle<br><span style='color:#888;'>Tags+annotations → annotations only → hide both</span></td></tr>
<tr><td><b>R</b></td><td>Reset W/L of active panel (zoom/pan preserved)</td></tr>
<tr><td><b>Ctrl+G</b></td><td>Reset Position — all panels Gap / Zoom / Pan / W/L</td></tr>
<tr><td><b>X</b></td><td>Cross-reference ON/OFF</td></tr>
<tr><td><b>P</b></td><td>Panning ON/OFF<br><span style='color:#888;'>Left-drag moves image<br>Use after zoom or gap reduction</span></td></tr>
</table>
<h3>✏️ Annotation</h3>
<table cellpadding='4'>
<tr><td><b>Measure / Arrow / Text / ROI</b></td><td>Select from toolbar or Annotation menu, then draw on the image</td></tr>
<tr><td><b>ESC</b></td><td>Exit the current annotation tool</td></tr>
<tr><td><b>Drag existing annotation</b></td><td>Edit position without selecting a tool<br><span style='color:#888;'>Move ROI, line, arrow, or text directly; ROI statistics are recalculated after move</span></td></tr>
<tr><td><b>Drag value box</b></td><td>Move only the ROI statistics or length label box</td></tr>
<tr><td><b>CLR Ann / CLR All Ann</b></td><td>Delete annotations in the active panel or all panels</td></tr>
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


def _dicom_text(value, default=''):
    s = str(value).strip()
    if not s:
        return default

    candidates = [s]
    # Recover Korean text if pydicom had to decode bytes with a fallback charset.
    for src_enc in ('latin1', 'cp1252'):
        try:
            raw = s.encode(src_enc)
        except Exception:
            continue
        for dst_enc in ('cp949', 'euc-kr', 'utf-8'):
            try:
                cand = raw.decode(dst_enc).strip()
            except Exception:
                continue
            if cand and cand not in candidates:
                candidates.append(cand)

    def score(text):
        bad = text.count('\ufffd') * 8 + text.count('?') * 3
        bad += sum(1 for ch in text if ord(ch) < 32 and ch not in '\t\n\r')
        has_hangul = any('\uac00' <= ch <= '\ud7a3' for ch in text)
        return (bad, 0 if has_hangul else 1)

    return min(candidates, key=score) or default


def _decode_dicom_bytes(raw, default=''):
    if isinstance(raw, str):
        return _dicom_text(raw, default)
    if not isinstance(raw, (bytes, bytearray)):
        return default
    for enc in ('utf-8', 'cp949', 'euc-kr', 'latin1'):
        try:
            text = bytes(raw).decode(enc).strip()
        except Exception:
            continue
        if text:
            return _dicom_text(text, default)
    return default


# ?????????????????????????????????????????????????????????????
#  ?ы띁: DICOM ?쒓렇 ??臾몄옄??
# ?????????????????????????????????????????????????????????????
def _tag(ds, attr, default=''):
    try:
        raw_text = ''
        if hasattr(ds, 'data_element'):
            elem = ds.data_element(attr)
            if elem is not None:
                raw_value = elem.value
                if hasattr(raw_value, 'original_string'):
                    raw_text = _decode_dicom_bytes(raw_value.original_string, default)
                elif isinstance(raw_value, (bytes, bytearray)):
                    raw_text = _decode_dicom_bytes(raw_value, default)
        v = getattr(ds, attr, default)
        if v is None:
            return raw_text or default
        if isinstance(v, (list, tuple)) or v.__class__.__name__ == 'MultiValue':
            v = v[0]
        text = _dicom_text(v, default)
        if raw_text and (text == default or text.count('?') > raw_text.count('?')):
            return raw_text
        return text
    except Exception:
        return default


def _fmt_date(raw):
    try:
        return datetime.strptime(raw, '%Y%m%d').strftime('%Y-%m-%d')
    except Exception:
        return raw


def build_overlay(ds, idx, total):
    """4-肄붾꼫 ?띿뒪??由ъ뒪??諛섑솚: (top_left, top_right, bot_left, bot_right)"""
    # ?곷떒 醫????섏옄/?ㅽ꽣??
    patient  = _tag(ds, 'PatientName', 'Anonymous')
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

    # ?곷떒 ?????쒕━利?
    top_right = []
    for attr in ('SeriesDescription', 'SequenceName', 'ProtocolName'):
        v = _tag(ds, attr, '')
        if v and v not in top_right:
            top_right.append(v)
    sn = _tag(ds, 'SeriesNumber', '')
    if sn:
        top_right.append(f"Series #{sn}")

    # ?섎떒 醫????щ씪?댁뒪
    bot_left = [f"Img {idx+1} / {total}"]
    sl = _tag(ds, 'SliceLocation', '')
    if sl:
        bot_left.append(f"Loc {float(sl):.1f} mm")
    st = _tag(ds, 'SliceThickness', '')
    if st:
        bot_left.append(f"Thick {st} mm")
    try:
        sp = ds.PixelSpacing
        bot_left.append(f"Pixel {float(sp[0]):.2f} x {float(sp[1]):.2f} mm")
    except Exception:
        pass
    r = _tag(ds, 'Rows', ''); c = _tag(ds, 'Columns', '')
    if r and c:
        bot_left.append(f"{c} x {r} px")

    # ?섎떒 ????MR/CT ?뚮씪誘명꽣
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


# ?????????????????????????????????????????????????????????????
#  Cross-reference 醫뚰몴 怨꾩궛 ?ы띁
# ?????????????????????????????????????????????????????????????
def _has_position_tags(ds):
    return (hasattr(ds, 'ImagePositionPatient') and
            hasattr(ds, 'ImageOrientationPatient') and
            hasattr(ds, 'PixelSpacing'))

def _pixel_to_world(ds, row_f, col_f):
    """?대?吏 ?쎌? (row, col) ??3D ?붾뱶 醫뚰몴 (mm)."""
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
    """3D ?붾뱶 醫뚰몴 ???대?吏 ?쎌? (row_f, col_f)."""
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
    """?쒕━利덉뿉??world 醫뚰몴??媛??媛源뚯슫 ?щ씪?댁뒪 ?몃뜳??諛섑솚."""
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


# ?????????????????????????????????????????????????????????????
#  洹몃９ ?숆린??留ㅻ땲?
# ?????????????????????????????????????????????????????????????
class GroupSyncManager:
    """Syncs scroll/WL/zoom/pan for a selected subset of DicomPanels.

    Activation paths:
      ????badge click  ??ctrl_toggle(panel): add/remove that panel
      ??Ctrl+click     ??ctrl_toggle(panel): add/remove individual panels
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

    # ?? toggle paths ?????????????????????????????????????????

    def toggle_badge(self):
        """??badge: toggle between all-panels sync and off."""
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
        """Add panel to sync set only ??never removes it (used for active-panel auto-include)."""
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

    # ?? helpers ??????????????????????????????????????????????

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

    # ?? broadcast methods ????????????????????????????????????

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
                # Same orientation ??3-D projection sync (anatomically correct)
                # Cross-plane     ??delta sync (scroll together step-for-step)
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


# ?????????????????????????????????????????????????????????????
#  諛섏쓳???고듃 ?좏떥由ы떚
# ?????????????????????????????????????????????????????????????
def _fit_font_px(text_lines, avail_w, font_family="Consolas", min_px=9, max_px=20):
    """text_lines 以?媛??湲?以꾩씠 avail_w ?덉뿉 ?ㅼ뼱?ㅻ뒗 理쒕? ?쎌? ?ш린瑜?諛섑솚.
    min_px?먯꽌?????ㅼ뼱?ㅻ㈃ min_px 諛섑솚 (?몄텧?먭? word-wrap 泥섎━)."""
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
    """媛?\\n 援щ텇 以꾩씠 ?꾩젽 ?덈퉬 ?덉뿉 ??以꾨줈 ?ㅼ뼱?ㅻ룄濡??고듃 ?ш린瑜??먮룞 議곗젙?섎뒗 QLabel.
    min_px?먯꽌?????ㅼ뼱?ㅻ㈃ word-wrap?쇰줈 ??以??덉슜."""

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


# ?????????????????????????????????????????????????????????????
#  ?⑥씪 DICOM ?⑤꼸
# ?????????????????????????????????????????????????????????????
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
        self.initial_wl = None   # WL at series load time ??used by Reset W/L
        self.initial_ww = None
        self.zoom      = 1.0
        self._raw_pix  = None
        self._disp_pix = None
        self._last_pos    = None
        self._drag_accum  = 0
        self._drag_moved  = False      # ?쒕옒洹?vs ?대┃ 援щ텇
        self._active      = False
        self._pixel_cache = {}
        self.show_tags    = True
        self.show_annotations = True
        self.cross_link   = False      # cross-reference ?쒖꽦 ?щ?
        self._crosshair   = None       # (row_f, col_f) ?대?吏 醫뚰몴, None=?놁쓬
        self.dwi_info            = None   # DWI position/b-value tables, or None
        self._bval_overlay       = None   # BValueOverlay child widget, or None
        self._active_bval_filter = None   # int b-value filter, or None = show all slices
        self.sync_manager        = None   # GroupSyncManager, set after construction
        self._sync_badge         = None   # SyncBadge child widget, or None
        self._sync_selected      = False  # True when Ctrl-selected for sync group
        self._series_normal      = None   # unit np.ndarray slice normal, or None
        self._slice_centers      = []     # 3-D world centre (np.ndarray) per slice
        self._slice_projections  = []     # dot(centre, normal) per slice (float|None)
        # Shift+?쒕옒洹?(?대?吏 ?대룞) ??1/2 ?띾룄 + axis lock
        self._gap_accum_x   = 0
        self._gap_accum_y   = 0
        self._gap_locked_ax = None     # None | 'x' | 'y'
        # ?대?吏瑜?widget ?덉뿉??媛?대뜲 ???덉そ?쇰줈 洹몃┫ ?뚯쓽 異붽? offset
        # (letterbox ?곸뿭??以꾩씠??phase. ViewerGrid媛 ?몃??먯꽌 set)
        self._paint_offset_x = 0
        self._paint_offset_y = 0
        # ?ъ슜??Panning offset (P 紐⑤뱶?먯꽌 醫뚰겢由??쒕옒洹몃줈 ?꾩쟻)
        self._pan_offset_x = 0
        self._pan_offset_y = 0
        self._annotations = []
        self._ann_drag = None
        self._ann_label_drag = None
        self._ann_item_drag = None

        self.setMinimumSize(200, 200)
        # 諛곌꼍 transparent ??letterbox ?곸뿭??ViewerGrid??寃?뺤씠 鍮꾩튂怨?
        # ?⑤꼸??寃뱀튂硫??ㅻⅨ ?⑤꼸 ?대?吏媛 蹂댁엫 (?ㅻ쾭??媛??
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

    # ?? ?곗씠?????????????????????????????????????????????????
    # self.series: [(filepath, header_ds), ...]  ???ㅻ뜑留?蹂댁쑀
    # self._pixel_cache: {idx: np.ndarray}       ???쎌? 罹먯떆 (理쒓렐 N??

    def load_series(self, file_header_pairs, start_idx=None):
        """
        file_header_pairs: [(Path, header_ds), ...]
        header_ds ??stop_before_pixels=True 濡??쎌? ?ㅻ뜑 ?꾩슜 ds.
        """
        self.series        = file_header_pairs
        self._pixel_cache  = {}        # 罹먯떆 珥덇린??
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
        self._annotations = []
        self._ann_drag = None
        self._ann_label_drag = None
        self._ann_item_drag = None
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
        self._annotations        = []
        self._ann_drag           = None
        self._ann_label_drag     = None
        self._ann_item_drag      = None
        self._teardown_bvalue_overlay()
        self.update()

    def _get_ds(self):
        """?꾩옱 ?щ씪?댁뒪???ㅻ뜑 ds 諛섑솚."""
        if not self.series:
            return None
        return self.series[self.idx][1]

    def _get_pixel(self, idx):
        """idx ?щ씪?댁뒪???쎌? 諛곗뿴 諛섑솚 (罹먯떆 ?쒖슜, 理쒕? 40??蹂닿?)."""
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
        # 罹먯떆 ?ш린 ?쒗븳 (40??
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

    # ?? ?뚮뜑留????????????????????????????????????????????????
    def _render(self):
        try:
            arr = self._get_array()
            if arr is None:
                self._raw_pix = self._disp_pix = None
                self.update()
                return

            # ?ㅼ콈??/ ?ㅽ봽?덉엫 泥섎━ ??_apply_wl ?꾩뿉 2D濡?異뺤냼
            # 1) 3D?몃뜲 (frames, H, W) ?먮뒗 (H, W, channels) ?뺥깭?????덉쓬
            if arr.ndim == 3:
                # (H, W, 3 or 4) ??洹몃젅?댁뒪耳??(luminance)
                if arr.shape[2] in (3, 4):
                    # RGB/RGBA ???쒖? luminance
                    arr = (arr[..., 0] * 0.299
                           + arr[..., 1] * 0.587
                           + arr[..., 2] * 0.114)
                else:
                    # (frames, H, W) ??泥??꾨젅?꾨쭔 ?ъ슜
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
                # ?????녿뒗 ?뺥깭 ???덉쟾?섍쾶 鍮??붾㈃
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
            # ???⑤꼸???뚮뜑 ?ㅽ뙣媛 ?꾩껜 ?섏씠吏 濡쒕뱶瑜?源⑦듃由ъ? ?딅룄濡?
            import traceback; traceback.print_exc()
            self._raw_pix = self._disp_pix = None
            self.update()

    def _make_display(self):
        if self._raw_pix is None:
            return
        # ?⑤꼸 ?ш린??留욊쾶 苑?梨꾩슦??base scale 怨꾩궛 (zoom=1.0 = fit)
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

        # ?? Cross-reference 援먯감??(?대?吏??臾띠씤 ?붿냼留???_disp_pix??洹몃┝) ?
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
        # _disp_pix ?ш린 蹂寃???letterbox ?ш린 蹂寃???ViewerGrid媛 paint offset ?ш퀎?고빐??
        par = self.parent()
        if par is not None and hasattr(par, '_relayout_panels'):
            par._relayout_panels()
        if self._bval_overlay is not None:
            self._update_bvalue_overlay()
        if self._sync_badge is not None:
            self._update_sync_badge()

    # _make_display ???꾩튂 留덉빱 ???띿뒪???뚮몢由щ뒗 paintEvent?먯꽌 洹몃┝

    def set_active(self, v):
        self._active = v
        self._make_display() if self._raw_pix else self.update()

    def toggle_tags(self, state=None):
        self.show_tags = (not self.show_tags) if state is None else state
        self._refresh_overlay_visibility()

    def set_overlay_visibility(self, show_tags=True, show_annotations=True):
        self.show_tags = bool(show_tags)
        self.show_annotations = bool(show_annotations)
        self._refresh_overlay_visibility()

    def _refresh_overlay_visibility(self):
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

    # ?? 洹몃━湲????????????????????????????????????????????????
    def paintEvent(self, event):
        p = QPainter(self)
        # background 洹몃━吏 ?딆쓬 ??WA_TranslucentBackground濡?letterbox ?곸뿭??transparent
        if self._disp_pix:
            # zoom 1.0 ?쒖젏??letterbox(?대?吏媛 ?ㅼ뼱媛?? ?곸뿭 怨꾩궛.
            # ???곸뿭?쇰줈 clip?댁꽌, zoom?쇰줈 _disp_pix媛 而ㅼ졇???몄젒 ?⑤꼸 ?곸뿭??移⑤쾾?섏? ?딄쾶 ??
            zoom = max(0.001, float(self.zoom))
            base_w = int(round(self._disp_pix.width()  / zoom))
            base_h = int(round(self._disp_pix.height() / zoom))
            # base ?곸뿭??醫뚯긽????paint_offset(媛?議곗젅)? ?곕씪媛吏留?pan_offset? 誘몄쟻??
            # (panning? zoom ?대?吏 ?덉뿉???ㅻⅨ 遺遺꾩쓣 蹂대뒗 嫄곕땲源?clip ?곸뿭? 怨좎젙)
            cx = (self.width()  - base_w) // 2 + self._paint_offset_x
            cy = (self.height() - base_h) // 2 + self._paint_offset_y
            p.setClipRect(cx, cy, base_w, base_h)

            # ?ㅼ젣 洹몃┫ ?꾩튂 (paint + pan offset 紐⑤몢 ?곸슜)
            x = ((self.width()  - self._disp_pix.width())  // 2
                 + self._paint_offset_x + self._pan_offset_x)
            y = ((self.height() - self._disp_pix.height()) // 2
                 + self._paint_offset_y + self._pan_offset_y)
            p.drawPixmap(x, y, self._disp_pix)

            # ?? clip ?댁젣 ??letterbox ?곸뿭 ?꾩뿉 ?띿뒪???뚮몢由??ㅻ쾭?덉씠 ??
            # zoom怨?臾닿??섍쾶 ??긽 letterbox ??媛?μ옄由ъ뿉 ?쒖떆?섎룄濡?paintEvent?먯꽌 洹몃┝
            p.setClipRect(cx, cy, base_w, base_h)   # 湲???뚮몢由щ룄 letterbox ?곸뿭留?
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
        """letterbox ?곸뿭 (cx,cy,cw,ch) ?꾩뿉 DICOM ?쒓렇 ?띿뒪??+ ?쒖꽦 ?뚮몢由?洹몃━湲?
        zoom???곹뼢??諛쏆? ?딆븘 ??긽 letterbox 媛?μ옄由ъ뿉 ?꾩튂."""
        _fpx = max(8, min(13, round(cw * 0.011)))
        FONT = QFont("Consolas")
        FONT.setPixelSize(_fpx)
        painter.setFont(FONT)
        LH = _fpx + 5
        M  = 5

        def draw_text(x_local, y_local, text, right=False):
            """letterbox 醫뚯긽??湲곗? (x_local, y_local) ?꾩튂???⑹깋 洹몃┝???띿뒪??
            right=True硫?letterbox ?곗륫 ?뺣젹."""
            if not text or not text.strip():
                return
            if right:
                # ?곗륫 ?뺣젹??rect = letterbox ?곸뿭
                rect = QRect(cx, cy + y_local - LH + 2, cw - M, LH)
                flags = (Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
                # 洹몃┝??
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

        # WL / WW / Zoom (T ?좉? ???
        if self.show_tags:
            wl_str = f"WL {self.wl:.0f}  WW {self.ww:.0f}   {self.zoom:.1f}x"
            draw_text(M, ch - 6, wl_str)

        # DICOM ?쒓렇 4-corner ?ㅻ쾭?덉씠
        if self.show_tags and self.series:
            ds = self._get_ds()
            if ds is not None:
                v_idx, v_total = self._virtual_idx_total()
                tl, tr, bl, br = build_overlay(ds, v_idx, v_total)
                # ?곷떒 醫?
                for i, line in enumerate(tl):
                    draw_text(M, M + LH * i + LH, line)
                # ?곷떒 ??
                for i, line in enumerate(tr):
                    draw_text(M, M + LH * i + LH, line, right=True)
                # ?섎떒 醫?(WL 以??꾨줈)
                base = ch - 6 - LH
                for i, line in enumerate(reversed(bl)):
                    draw_text(M, base - LH * i, line)
                # ?섎떒 ??
                for i, line in enumerate(reversed(br)):
                    draw_text(M, base - LH * i, line, right=True)

        # ?쒖꽦 ?⑤꼸 ?뚮? ?뚮몢由???letterbox ?곸뿭 媛?μ옄由ъ뿉 (clip ?덉뿉 ?ㅼ뼱??
        if self._active:
            painter.setPen(QPen(QColor(0, 160, 255), 3))
            painter.drawRect(cx + 1, cy + 1, cw - 2, ch - 2)

        # Ctrl-?좏깮??sync ?⑤꼸 ???⑷툑??2px ?뚮몢由?
        if getattr(self, '_sync_selected', False):
            painter.setPen(QPen(QColor(255, 215, 0), 2))
            painter.drawRect(cx + 2, cy + 2, cw - 4, ch - 4)

        if self.show_annotations:
            self._paint_annotations(painter)

    def _slice_key(self):
        if not self.series or self.idx < 0 or self.idx >= len(self.series):
            return None
        try:
            return str(self.series[self.idx][0])
        except Exception:
            return str(self.idx)

    def _image_to_screen(self, row_f, col_f):
        if self._raw_pix is None or self._disp_pix is None:
            return None
        iw = self._raw_pix.width()
        ih = self._raw_pix.height()
        dw = self._disp_pix.width()
        dh = self._disp_pix.height()
        if iw <= 0 or ih <= 0 or dw <= 0 or dh <= 0:
            return None
        ox = (self.width() - dw) // 2 + self._paint_offset_x + self._pan_offset_x
        oy = (self.height() - dh) // 2 + self._paint_offset_y + self._pan_offset_y
        return (ox + col_f * dw / iw, oy + row_f * dh / ih)

    def _pixel_spacing(self):
        ds = self._get_ds()
        try:
            ps = [float(x) for x in ds.PixelSpacing]
            return ps[0], ps[1]
        except Exception:
            return None, None

    def _current_2d_array(self):
        arr = self._get_array()
        if arr is None:
            return None
        if arr.ndim == 2:
            return arr
        if arr.ndim == 3:
            if arr.shape[2] in (3, 4):
                return (arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114)
            return arr[0]
        if arr.ndim == 4:
            f0 = arr[0]
            if f0.ndim == 3 and f0.shape[2] in (3, 4):
                return (f0[..., 0] * 0.299 + f0[..., 1] * 0.587 + f0[..., 2] * 0.114)
            return f0[0] if f0.ndim == 3 else f0
        return None

    def _annotation_unit(self):
        ds = self._get_ds()
        modality = str(getattr(ds, 'Modality', '') or '').upper() if ds else ''
        return 'HU' if modality == 'CT' else 'SI'

    def _format_length(self, p1, p2):
        r1, c1 = p1
        r2, c2 = p2
        row_sp, col_sp = self._pixel_spacing()
        if row_sp is not None and col_sp is not None:
            mm = math.hypot((r2 - r1) * row_sp, (c2 - c1) * col_sp)
            return f"{mm:.1f} mm"
        return f"{math.hypot(r2 - r1, c2 - c1):.1f} px"

    def _roi_stats(self, p1, p2):
        arr = self._current_2d_array()
        if arr is None:
            return None
        h, w = arr.shape[:2]
        r1, c1 = p1
        r2, c2 = p2
        rmin = max(0, int(math.floor(min(r1, r2))))
        rmax = min(h - 1, int(math.ceil(max(r1, r2))))
        cmin = max(0, int(math.floor(min(c1, c2))))
        cmax = min(w - 1, int(math.ceil(max(c1, c2))))
        if rmax <= rmin or cmax <= cmin:
            return None
        cy = (r1 + r2) / 2.0
        cx = (c1 + c2) / 2.0
        ry = max(0.5, abs(r2 - r1) / 2.0)
        rx = max(0.5, abs(c2 - c1) / 2.0)
        yy, xx = np.ogrid[rmin:rmax + 1, cmin:cmax + 1]
        mask = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0
        vals = arr[rmin:rmax + 1, cmin:cmax + 1][mask]
        if vals.size == 0:
            return None
        row_sp, col_sp = self._pixel_spacing()
        area = (f"{vals.size * row_sp * col_sp:.1f} mm2"
                if row_sp is not None and col_sp is not None
                else f"{vals.size} px2")
        return {
            'area': area,
            'mean': float(np.mean(vals)),
            'min': float(np.min(vals)),
            'max': float(np.max(vals)),
            'sd': float(np.std(vals)),
            'unit': self._annotation_unit(),
        }

    def _annotation_label_rect(self, x, y, lines, item=None):
        if not lines:
            return None
        font = QFont("Consolas")
        font.setPixelSize(12)
        fm = QFontMetrics(font)
        pad = 4
        width = max(fm.horizontalAdvance(line) for line in lines) + pad * 2
        height = len(lines) * (fm.height() + 1) + pad * 2
        offset = item.get('label_offset', (8, -height - 8)) if item else (8, -height - 8)
        rx = int(x + offset[0])
        ry = int(y + offset[1])
        if ry < 2:
            ry = int(y + 8)
        rx = max(2, min(rx, max(2, self.width() - width - 2)))
        ry = max(2, min(ry, max(2, self.height() - height - 2)))
        return QRect(rx, ry, width, height)

    def _draw_annotation_label(self, painter, x, y, lines, color, item=None):
        rect = self._annotation_label_rect(x, y, lines, item)
        if rect is None:
            return
        font = QFont("Consolas")
        font.setPixelSize(12)
        painter.setFont(font)
        fm = QFontMetrics(font)
        pad = 4
        rx = rect.x()
        ry = rect.y()
        painter.fillRect(rect, QColor(0, 0, 0, 170))
        painter.setPen(color)
        for i, line in enumerate(lines):
            painter.drawText(rx + pad, ry + pad + fm.ascent() + i * (fm.height() + 1), line)

    def _draw_arrow_head(self, painter, x1, y1, x2, y2, color):
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 12
        for delta in (150, -150):
            a = angle + math.radians(delta)
            px = x2 + math.cos(a) * size
            py = y2 + math.sin(a) * size
            painter.drawLine(int(x2), int(y2), int(px), int(py))

    def _paint_one_annotation(self, painter, item, preview=False):
        kind = item.get('type')
        color = QColor(0, 255, 170) if kind == 'roi' else QColor(255, 210, 0)
        if kind == 'arrow':
            color = QColor(255, 145, 0)
        elif kind == 'text':
            color = QColor(255, 255, 255)
        painter.setPen(QPen(color, 2, Qt.PenStyle.DashLine if preview else Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if kind in ('measure', 'arrow'):
            a = self._image_to_screen(*item['p1'])
            b = self._image_to_screen(*item['p2'])
            if a is None or b is None:
                return
            x1, y1 = a
            x2, y2 = b
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            if kind == 'arrow':
                self._draw_arrow_head(painter, x1, y1, x2, y2, color)
            else:
                label = item.get('label') or self._format_length(item['p1'], item['p2'])
                self._draw_annotation_label(painter, (x1 + x2) / 2, (y1 + y2) / 2,
                                            [label], color, item)
            return

        if kind == 'roi':
            a = self._image_to_screen(*item['p1'])
            b = self._image_to_screen(*item['p2'])
            if a is None or b is None:
                return
            x1, y1 = a
            x2, y2 = b
            painter.drawEllipse(int(min(x1, x2)), int(min(y1, y2)),
                                int(abs(x2 - x1)), int(abs(y2 - y1)))
            stats = item.get('stats')
            if stats:
                unit = stats.get('unit', '')
                lines = [
                    f"ROI {stats['area']}",
                    f"Mean {stats['mean']:.1f} {unit}",
                    f"Min {stats['min']:.1f}  Max {stats['max']:.1f}",
                    f"SD {stats['sd']:.1f}",
                ]
                self._draw_annotation_label(painter, max(x1, x2), min(y1, y2), lines, color, item)
            return

        if kind == 'text':
            a = self._image_to_screen(*item['pos'])
            if a is not None:
                self._draw_annotation_label(painter, a[0], a[1], [item.get('text', '')], color, item)

    def _annotation_label_info(self, item):
        kind = item.get('type')
        if kind == 'measure':
            a = self._image_to_screen(*item['p1'])
            b = self._image_to_screen(*item['p2'])
            if a is None or b is None:
                return None, None
            label = item.get('label') or self._format_length(item['p1'], item['p2'])
            return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), [label]
        if kind == 'roi':
            a = self._image_to_screen(*item['p1'])
            b = self._image_to_screen(*item['p2'])
            stats = item.get('stats')
            if a is None or b is None or not stats:
                return None, None
            x1, y1 = a
            x2, y2 = b
            unit = stats.get('unit', '')
            lines = [
                f"ROI {stats['area']}",
                f"Mean {stats['mean']:.1f} {unit}",
                f"Min {stats['min']:.1f}  Max {stats['max']:.1f}",
                f"SD {stats['sd']:.1f}",
            ]
            return (max(x1, x2), min(y1, y2)), lines
        if kind == 'text':
            a = self._image_to_screen(*item['pos'])
            if a is None:
                return None, None
            return a, [item.get('text', '')]
        return None, None

    def _annotation_label_at(self, pos):
        key = self._slice_key()
        if key is None:
            return None, None, None
        for item in reversed(self._annotations):
            if item.get('slice') != key:
                continue
            anchor, lines = self._annotation_label_info(item)
            if anchor is None or not lines:
                continue
            rect = self._annotation_label_rect(anchor[0], anchor[1], lines, item)
            if rect is not None and rect.adjusted(-4, -4, 4, 4).contains(pos):
                return item, anchor, rect
        return None, None, None

    def _distance_to_segment(self, px, py, ax, ay, bx, by):
        vx = bx - ax
        vy = by - ay
        wx = px - ax
        wy = py - ay
        denom = vx * vx + vy * vy
        if denom <= 1e-6:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
        cx = ax + t * vx
        cy = ay + t * vy
        return math.hypot(px - cx, py - cy)

    def _annotation_body_at(self, pos):
        key = self._slice_key()
        if key is None:
            return None
        px = pos.x()
        py = pos.y()
        for item in reversed(self._annotations):
            if item.get('slice') != key:
                continue
            kind = item.get('type')
            if kind in ('measure', 'arrow'):
                a = self._image_to_screen(*item['p1'])
                b = self._image_to_screen(*item['p2'])
                if a is None or b is None:
                    continue
                if self._distance_to_segment(px, py, a[0], a[1], b[0], b[1]) <= 7:
                    return item
            elif kind == 'roi':
                a = self._image_to_screen(*item['p1'])
                b = self._image_to_screen(*item['p2'])
                if a is None or b is None:
                    continue
                x1, y1 = a
                x2, y2 = b
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                rx = max(4.0, abs(x2 - x1) / 2.0)
                ry = max(4.0, abs(y2 - y1) / 2.0)
                norm = ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2
                if norm <= 1.12:
                    return item
            elif kind == 'text':
                anchor, lines = self._annotation_label_info(item)
                if anchor is None or not lines:
                    continue
                rect = self._annotation_label_rect(anchor[0], anchor[1], lines, item)
                if rect is not None and rect.adjusted(-4, -4, 4, 4).contains(pos):
                    return item
        return None

    def _start_annotation_item_drag(self, item, row, col):
        saved = {'type': item.get('type'), 'slice': item.get('slice')}
        for key in ('p1', 'p2', 'pos', 'label_offset'):
            if key in item:
                value = item[key]
                saved[key] = tuple(value) if isinstance(value, (list, tuple)) else value
        self._ann_item_drag = {
            'item': item,
            'row': row,
            'col': col,
            'saved': saved,
        }

    def _move_annotation_item(self, pos):
        if self._ann_item_drag is None:
            return False
        row, col = self._screen_to_image(pos.x(), pos.y())
        if row is None:
            return True
        drag = self._ann_item_drag
        item = drag['item']
        saved = drag['saved']
        dr = row - drag['row']
        dc = col - drag['col']
        if 'p1' in saved and 'p2' in saved:
            item['p1'] = (saved['p1'][0] + dr, saved['p1'][1] + dc)
            item['p2'] = (saved['p2'][0] + dr, saved['p2'][1] + dc)
        if 'pos' in saved:
            item['pos'] = (saved['pos'][0] + dr, saved['pos'][1] + dc)
        if 'label_offset' in saved:
            item['label_offset'] = saved['label_offset']
        self.update()
        return True

    def _paint_annotations(self, painter):
        key = self._slice_key()
        if key is None:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for item in self._annotations:
            if item.get('slice') == key:
                self._paint_one_annotation(painter, item)
        if self._ann_drag is not None and self._ann_drag.get('slice') == key:
            self._paint_one_annotation(painter, self._ann_drag, preview=True)

    def _annotation_tool(self):
        return getattr(self.window(), '_annotation_tool', 'none')

    def _annotation_error(self, exc):
        import traceback
        traceback.print_exc()
        self._ann_drag = None
        win = self.window()
        if hasattr(win, 'statusBar'):
            win.statusBar().showMessage(f"Annotation error: {exc}", 5000)
        self.update()

    def _annotation_press(self, pos):
        try:
            tool = self._annotation_tool()
            item, anchor, rect = self._annotation_label_at(pos)
            if item is not None:
                self._ann_label_drag = {
                    'item': item,
                    'anchor': anchor,
                    'grab_dx': pos.x() - rect.x(),
                    'grab_dy': pos.y() - rect.y(),
                }
                return True
            row, col = self._screen_to_image(pos.x(), pos.y())
            if row is None:
                return False
            key = self._slice_key()
            if key is None:
                return False
            item = self._annotation_body_at(pos)
            if item is not None:
                self._start_annotation_item_drag(item, row, col)
                return True
            if tool == 'text':
                text, ok = QInputDialog.getText(self, "Text Annotation", "Text:")
                if ok and text:
                    self._annotations.append({'type': 'text', 'slice': key, 'pos': (row, col), 'text': text})
                    self.update()
                return True
            if tool in ('measure', 'arrow', 'roi'):
                self._ann_drag = {'type': tool, 'slice': key, 'p1': (row, col), 'p2': (row, col)}
                return True
            return False
        except Exception as exc:
            self._annotation_error(exc)
            return True

    def _annotation_move(self, pos):
        try:
            if self._ann_item_drag is not None:
                return self._move_annotation_item(pos)
            if self._ann_label_drag is not None:
                item = self._ann_label_drag['item']
                ax, ay = self._ann_label_drag['anchor']
                dx = pos.x() - self._ann_label_drag['grab_dx'] - ax
                dy = pos.y() - self._ann_label_drag['grab_dy'] - ay
                item['label_offset'] = (dx, dy)
                self.update()
                return True
            if self._ann_drag is None:
                return False
            row, col = self._screen_to_image(pos.x(), pos.y())
            if row is not None:
                self._ann_drag['p2'] = (row, col)
                self.update()
            return True
        except Exception as exc:
            self._annotation_error(exc)
            return True

    def _annotation_release(self, pos):
        try:
            if self._ann_item_drag is not None:
                self._move_annotation_item(pos)
                item = self._ann_item_drag['item']
                self._ann_item_drag = None
                if item.get('type') == 'measure':
                    item['label'] = self._format_length(item['p1'], item['p2'])
                elif item.get('type') == 'roi':
                    stats = self._roi_stats(item['p1'], item['p2'])
                    if stats is not None:
                        item['stats'] = stats
                self.update()
                return True
            if self._ann_label_drag is not None:
                self._annotation_move(pos)
                self._ann_label_drag = None
                return True
            if self._ann_drag is None:
                return False
            row, col = self._screen_to_image(pos.x(), pos.y())
            item = self._ann_drag
            self._ann_drag = None
            if row is None:
                self.update()
                return True
            item['p2'] = (row, col)
            r1, c1 = item['p1']
            if math.hypot(row - r1, col - c1) < 2:
                self.update()
                return True
            if item['type'] == 'measure':
                item['label'] = self._format_length(item['p1'], item['p2'])
            elif item['type'] == 'roi':
                stats = self._roi_stats(item['p1'], item['p2'])
                if stats is None:
                    self.update()
                    return True
                item['stats'] = stats
            self._annotations.append(item)
            self.update()
            return True
        except Exception as exc:
            self._annotation_error(exc)
            return True

    def delete_last_annotation(self):
        key = self._slice_key()
        for i in range(len(self._annotations) - 1, -1, -1):
            if self._annotations[i].get('slice') == key:
                del self._annotations[i]
                self.update()
                return True
        return False

    def delete_annotation(self, item):
        try:
            self._annotations.remove(item)
        except ValueError:
            return False
        self._ann_drag = None
        self._ann_label_drag = None
        self._ann_item_drag = None
        self.update()
        return True

    def clear_annotations(self):
        self._annotations = []
        self._ann_drag = None
        self._ann_label_drag = None
        self._ann_item_drag = None
        self.update()

    # ?? 留덉슦?????????????????????????????????????????????????
    def mousePressEvent(self, event):
        # 媛?以꾩엫/?ㅻ쾭???곹깭?먯꽌 z-order 湲곕컲?쇰줈 吏꾩쭨 蹂댁씠???⑤꼸??李얠븘 ?꾩엫.
        # QMouseEvent ?ъ깮?깆? PyQt 踰꾩쟾 媛??쒓렇?덉쿂 李⑥씠濡??꾪뿕 ??吏곸젒 ?곹깭留??뗭뾽.
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

        # Ctrl+click ??toggle clicked panel + auto-include the currently active panel
        if (event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            sm = real.sync_manager
            if sm is not None:
                sm.ctrl_toggle(real)
                # In overlap mode self may differ from real ??include it too
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

        if (event.button() == Qt.MouseButton.LeftButton
                and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier)):
            ann_pos = QPoint(gx - real.x(), gy - real.y()) if real is not self else event.pos()
            label_item, _anchor, _rect = real._annotation_label_at(ann_pos)
            body_item = real._annotation_body_at(ann_pos)
            if (label_item is not None or body_item is not None) and real._annotation_press(ann_pos):
                if vg is not None and hasattr(vg, '_activate'):
                    vg._activate(real)
                if real is not self:
                    real.grabMouse()
                event.accept()
                return

        if event.button() == Qt.MouseButton.RightButton:
            ann_pos = QPoint(gx - real.x(), gy - real.y()) if real is not self else event.pos()
            label_item, _anchor, _rect = real._annotation_label_at(ann_pos)
            body_item = real._annotation_body_at(ann_pos)
            item = label_item or body_item
            if item is not None:
                if vg is not None and hasattr(vg, '_activate'):
                    vg._activate(real)
                menu = QMenu(real)
                delete_action = menu.addAction("Delete?")
                chosen = menu.exec(event.globalPosition().toPoint())
                if chosen is delete_action and real.delete_annotation(item):
                    win = real.window()
                    if hasattr(win, 'statusBar'):
                        win.statusBar().showMessage("Annotation deleted", 2500)
                event.accept()
                return

        if (event.button() == Qt.MouseButton.LeftButton
                and getattr(self.window(), '_annotation_tool', 'none') != 'none'):
            if vg is not None and hasattr(vg, 'active_panel') and real is not vg.active_panel:
                vg._activate(real)
                event.accept()
                return
            if real is not self and vg is not None:
                vg._activate(real)
                ann_pos = QPoint(gx - real.x(), gy - real.y())
            else:
                ann_pos = event.pos()
            if real._annotation_press(ann_pos):
                if real is not self:
                    real.grabMouse()
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
            # ?쒖꽦 ?⑤꼸 ?꾪솚 + ?쒕옒洹??숈븞??醫뚰몴 異붿쟻? real???대떦
            vg._activate(real)
            real._last_pos   = QPoint(gx - real.x(), gy - real.y())
            real._drag_accum = 0
            real._drag_moved = False
            real._gap_accum_x   = 0
            real._gap_accum_y   = 0
            real._gap_locked_ax = None
            # ?댄썑 mouse move/release??grabMouse濡?real??諛쏆쓬
            real.grabMouse()
            # Panning 紐⑤뱶 + 醫뚰겢由????ロ엺 ??
            if (event.button() == Qt.MouseButton.LeftButton
                    and getattr(self.window(), '_pan_mode', False)):
                real.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        self._last_pos   = event.pos()
        self._drag_accum = 0
        self._drag_moved = False
        # Shift+?쒕옒洹??꾩쟻/lock 由ъ뀑 (???쒕옒洹??몄뀡 ?쒖옉)
        self._gap_accum_x   = 0
        self._gap_accum_y   = 0
        self._gap_locked_ax = None
        # Panning 紐⑤뱶 + 醫뚰겢由????ロ엺 ??而ㅼ꽌
        if (event.button() == Qt.MouseButton.LeftButton
                and getattr(self.window(), '_pan_mode', False)):
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.clicked.emit(self)

    def mouseReleaseEvent(self, event):
        if self._annotation_release(event.pos()):
            if QWidget.mouseGrabber() is self:
                self.releaseMouse()
            event.accept()
            return

        # cross-link 紐⑤뱶: 醫뚰겢由?씠怨??쒕옒洹명븯吏 ?딆? 寃쎌슦 ??crosshair ?ㅼ젙
        if (self.cross_link
                and event.button() == Qt.MouseButton.LeftButton
                and not self._drag_moved
                and self.series):
            self._emit_cross_click(event.pos())
        # Shift+?대┃(?쒕옒洹??놁쓬) ??洹몃９ sync ?좉? (Shift+?쒕옒洹몃뒗 ?대?吏 ?대룞)
        if (event.button() == Qt.MouseButton.LeftButton
                and not self._drag_moved
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                and self.sync_manager is not None):
            self.sync_manager.ctrl_toggle(self)
        # Panning 紐⑤뱶硫??ㅼ떆 ?대┛ ?먯쑝濡?
        if (event.button() == Qt.MouseButton.LeftButton
                and getattr(self.window(), '_pan_mode', False)):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._last_pos   = None
        self._drag_accum = 0
        # mousePress?먯꽌 grabMouse瑜??덉쓣 ???덉쓬 ???덉쟾?섍쾶 ?댁젣
        if QApplication.mouseButtons() == Qt.MouseButton.NoButton:
            try:
                self.releaseMouse()
            except Exception:
                pass

    def mouseDoubleClickEvent(self, event):
        """?⑤꼸 ?붾툝?대┃ ??Space ?좉?怨??숈씪 (1횞1 ??multi-panel)."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # z-order ???⑤꼸濡??꾩엫 (?쒖꽦 ?⑤꼸??洹??⑤꼸濡?留뚮벀)
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
        """?대┃ ?꾩튂瑜?3D ?붾뱶 醫뚰몴濡?蹂?섑빐 cross_clicked ?쒓렇??諛쒖떊."""
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
        """?붾㈃ ?쎌?(sx,sy) ???대?吏 ?쎌?(row_f, col_f). 踰붿쐞 諛뽰씠硫?None,None.
        zoom + paint_offset(媛? + pan_offset 紐⑤몢 諛섏쁺."""
        if self._raw_pix is None or self._disp_pix is None:
            return None, None
        iw = self._raw_pix.width()
        ih = self._raw_pix.height()
        dw = self._disp_pix.width()
        dh = self._disp_pix.height()
        # _disp_pix媛 洹몃젮吏??widget ??醫뚯긽????paintEvent? ?숈씪 ??
        ox = (self.width()  - dw) // 2 + self._paint_offset_x + self._pan_offset_x
        oy = (self.height() - dh) // 2 + self._paint_offset_y + self._pan_offset_y
        lx = sx - ox
        ly = sy - oy
        if lx < 0 or ly < 0 or lx >= dw or ly >= dh:
            return None, None
        return ly * ih / dh, lx * iw / dw   # row_f, col_f

    def set_crosshair_from_world(self, world):
        """?몃??먯꽌 world 醫뚰몴瑜?諛쏆븘 援먯감???ㅼ젙 + 媛??媛源뚯슫 ?щ씪?댁뒪濡??대룞.
        Cross-link???щ씪?댁뒪 ?꾩튂留??숆린????W/L? ?덈? 蹂寃쏀븯吏 ?딅뒗??
        DWI ?쒕━利덈뒗 ?꾩옱 b-value瑜??좎???梨??대??숈쟻 ?꾩튂留??대룞."""
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

    # ?? DWI b-value support ??????????????????????????????????

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

        # Map rounded position ??sequential position index
        pos_keys  : list  = []
        pos_to_pi : dict  = {}
        for pos in slice_pos:
            if pos is None:
                continue
            rp = round(pos, 1)
            if rp not in pos_to_pi:
                pos_to_pi[rp] = len(pos_keys)
                pos_keys.append(rp)

        # (pos_index, bval) ??first slice index at that combination
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
          normal = cross(IOP_row, IOP_col) ??normalised
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

    # ?? slice navigation (respects active b-value filter pool) ??

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
        # no filter ??navigate within full series
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

    # ?? 洹몃９ ?숆린????????????????????????????????????????????

    def setup_sync(self, manager):
        """Attach panel to a GroupSyncManager and create the ??badge overlay."""
        self.sync_manager = manager
        manager.register(self)
        badge = SyncBadge(parent=self)
        badge.set_active(False)
        badge.clicked.connect(lambda: manager.ctrl_toggle(self))
        self._sync_badge = badge

    def _update_sync_badge(self):
        """Reposition ??badge in bottom-right of letterbox; hide when tags are off."""
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
        badge.move(cx + MARGIN, cy + MARGIN)
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
        if self._annotation_move(event.pos()):
            event.accept()
            return

        if self._last_pos is None or not self.series:
            return
        dy = event.pos().y() - self._last_pos.y()
        dx = event.pos().x() - self._last_pos.x()

        # 3px ?댁긽 ?吏곸씠硫??쒕옒洹몃줈 ?먯젙
        if abs(dx) > 3 or abs(dy) > 3:
            self._drag_moved = True

        if event.buttons() & Qt.MouseButton.LeftButton:
            # Shift+醫뚰겢由??쒕옒洹???紐⑤뱺 ?⑤꼸 widget??媛?대뜲/諛붽묑 諛⑺뼢?쇰줈 ?대룞
            # (PPT 罹≪쿂??媛?議곗젅, ?ㅻ쾭???덉슜)
            #  ??1/2 ?띾룄: 留덉슦??2px ??offset 1px
            #  ??axis lock: ?쒕옒洹??몄뀡 ?쒖옉 ??dominant 異뺤쑝濡??좉?????諛⑺뼢留??묐룞
            #  ??諛⑺뼢: 留덉슦?????덉そ?쇰줈 ?뚮㈃ ?⑤꼸???덉そ?쇰줈 紐⑥엫
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._gap_accum_x += dx
                self._gap_accum_y += dy

                # 泥?lock 寃곗젙 (4px ?댁긽 ?꾩쟻??dominant 異?
                if self._gap_locked_ax is None:
                    if (abs(self._gap_accum_x) >= 4
                            and abs(self._gap_accum_x) >= abs(self._gap_accum_y)):
                        self._gap_locked_ax = 'x'
                    elif abs(self._gap_accum_y) >= 4:
                        self._gap_locked_ax = 'y'

                win = self.window()
                # lock??異뺤뿉??2px ?꾩쟻???뚮쭏??1px ?곸슜 (1/2 ?띾룄) ??遺??諛섏쟾
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

            # Panning 紐⑤뱶 (P ?⑥텞???먮뒗 ?대컮濡??쒖꽦) ???곸긽 ?꾩튂 ?대룞
            win = self.window()
            if getattr(win, '_pan_mode', False):
                old_pan_x, old_pan_y = self._pan_offset_x, self._pan_offset_y
                new_x = old_pan_x + dx
                new_y = old_pan_y + dy

                # ?먯꽍 ?④낵: ?몄젒 ?⑤꼸???대?吏 媛?μ옄由ъ뿉 8px ?대궡濡?媛源뚯썙吏硫??뺥솗??留욎땄
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

            # 醫뚰겢由??쒕옒洹??곹븯 ???щ씪?댁뒪 ?대룞 (10px ?꾩쟻留덈떎 1??
            self._drag_accum += dy
            step = int(self._drag_accum / 10)   # 10px = ?щ씪?댁뒪 1??
            if step != 0:
                self._drag_accum -= step * 10
                self._navigate_slice(step)
            self._last_pos = event.pos()

        elif event.buttons() & Qt.MouseButton.RightButton:
            # ?고겢由??쒕옒洹? 醫뚯슦 ??WW, ?곹븯 ??WL
            self.ww  = max(1.0, self.ww + dx * 3)
            self.wl += dy * 2
            self._last_pos = event.pos()
            self._render()
            if self.sync_manager:
                self.sync_manager.broadcast_wl(self, self.wl, self.ww)

        elif event.buttons() & Qt.MouseButton.MiddleButton:
            # 媛?대뜲 ?쒕옒洹? ?곹븯 ???뺣?/異뺤냼 (?꾨줈 = zoom in)
            # 5px ?????④퀎, Ctrl+?좉낵 ?숈씪??1.15 諛곗쑉
            self._drag_accum += dy
            step = int(self._drag_accum / 5)
            if step != 0:
                self._drag_accum -= step * 5
                # ?꾨줈 ?뚮㈃ dy<0 ???뺣?
                factor = (1 / 1.15) ** step
                self.zoom = max(0.05, min(30.0, self.zoom * factor))
                self._make_display()
                if self.sync_manager:
                    self.sync_manager.broadcast_zoom(self, self.zoom)
            self._last_pos = event.pos()

    def wheelEvent(self, event):
        # 媛?以꾩엫/?ㅻ쾭???곹깭?먯꽌 z-order ???⑤꼸??吏꾩쭨 ?ъ슜?먭? 蹂대뒗 寃???洹몄そ?쇰줈 ?꾩엫
        vg = self.parentWidget()
        if vg is not None and hasattr(vg, '_panel_at_global'):
            pos = event.position()
            gx = self.x() + pos.x()
            gy = self.y() + pos.y()
            real = vg._panel_at_global(int(gx), int(gy))
            if real is not None and real is not self:
                # QWheelEvent ?ъ깮?????吏곸젒 泥섎━ ???명솚???덉젙???곗꽑
                real._handle_wheel(event.angleDelta().y(), event.modifiers())
                event.accept()
                return
        self._handle_wheel(event.angleDelta().y(), event.modifiers())
        event.accept()

    def _handle_wheel(self, delta, modifiers):
        """wheelEvent 蹂몄껜 ???ㅻⅨ ?⑤꼸?먯꽌 ?꾩엫 ?몄텧??媛?ν븯?꾨줉 遺꾨━."""
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+?ㅽ겕濡????뺣?/異뺤냼
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.zoom = max(0.05, min(30.0, self.zoom * factor))
            self._make_display()
            if self.sync_manager:
                self.sync_manager.broadcast_zoom(self, self.zoom)
        else:
            # ?ㅽ겕濡????щ씪?댁뒪 ?대룞
            if not self.series:
                return
            step = -1 if delta > 0 else 1   # ?꾨줈 ?ㅽ겕濡?= ?댁쟾 ?щ씪?댁뒪
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
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if not self.delete_last_annotation():
                super().keyPressEvent(event)
        elif key == Qt.Key.Key_Escape:
            if hasattr(self.window(), '_set_annotation_tool'):
                self.window()._set_annotation_tool('none')
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    # ?? ?쒕옒洹??쒕∼ ??????????????????????????????????????????
    def dragEnterEvent(self, event):
        event.accept() if event.mimeData().hasUrls() else event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            win = self.window()
            win._activate_panel(self)
            win._load_path(urls[0].toLocalFile())


# ?????????????????????????????????????????????????????????????
#  DWI b-value badge overlay
# ?????????????????????????????????????????????????????????????
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

        # [b?? toggle button
        self._toggle = QPushButton("b", self)
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

    # ?? public API ???????????????????????????????????????????

    def set_active_bval(self, bval):
        if bval == self._active:
            return
        self._active = bval
        self._refresh_style()

    # ?? internals ????????????????????????????????????????????

    def _on_toggle(self):
        self._collapsed = not self._collapsed
        for btn in self._btns.values():
            btn.setVisible(not self._collapsed)
        self._toggle.setText("+" if self._collapsed else "-")
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


# ?????????????????????????????????????????????????????????????
#  ?숆린??諛곗? (?? bottom-right of viewport)
# ?????????????????????????????????????????????????????????????
class SyncBadge(QWidget):
    """Circular ??badge in the bottom-right corner of a DicomPanel viewport.
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


# ?????????????????????????????????????????????????????????????
#  酉곗뼱 洹몃━??
# ?????????????????????????????????????????????????????????????
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
        # Space ?좉?: 吏곸쟾 multi-panel ?곹깭瑜????
        self._saved_multi      = []      # [(series, idx, wl, ww, zoom), ...]
        self._saved_multi_mode = '2x2'   # 吏곸쟾 multi 紐⑤뱶
        self._saved_multi_active = 0     # 吏곸쟾 ?쒖꽦 ?⑤꼸 ?몃뜳??
        self.sync_manager = None         # set by DicomViewer after construction

        # ?⑤꼸 widget ?먯껜???대룞 offset (PPT 罹≪쿂??媛?議곗젅)
        # ?묒닔 = 媛?대뜲濡쒕???硫?댁쭚 (媛?利앷?)
        # ?뚯닔 = 媛?대뜲濡?紐⑥엫 (?ㅻ쾭???덉슜)
        self._image_offset_x = 0
        self._image_offset_y = 0

        # background 寃????panels??transparent??letterbox ?곸뿭???닿쾶 鍮꾩묠
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
        old_annotations = [getattr(p, '_annotations', [])[:] for p in self.panels]
        old_tags     = self.panels[0].show_tags if self.panels else True
        old_ann_vis  = self.panels[0].show_annotations if self.panels else True
        old_crosslnk = self.panels[0].cross_link if self.panels else False
        for p in self.panels:
            if self.sync_manager is not None:
                self.sync_manager.unregister(p)
            p.setParent(None)
            p.deleteLater()
        self.panels = []
        self._mode  = mode

        positions = [(r, c) for r in range(rows) for c in range(cols)]

        # ?⑥씪 ?쒕━利덈쭔 ?덉쓣 ????multi-panel濡?洹좊벑 遺꾨같
        unique = [s for s in old_series if s]
        all_same = len(unique) >= 1 and all(s is unique[0] for s in unique)
        single_series = unique[0] if unique else None

        for i, (r, c) in enumerate(positions):
            p = DicomPanel(panel_id=i, parent=self)
            p.show_tags  = old_tags
            p.show_annotations = old_ann_vis
            p.cross_link = old_crosslnk
            p.clicked.connect(self._on_clicked)
            if old_crosslnk:
                p.cross_clicked.connect(self._on_cross_clicked)
            p.setAcceptDrops(True)
            if self.sync_manager is not None:
                p.setup_sync(self.sync_manager)

            if n_panels > 1 and all_same and single_series:
                # 媛숈? ?쒕━利덈? N媛??⑤꼸??洹좊벑 遺꾨같
                total = len(single_series)
                idx   = int(total * (i + 1) / (n_panels + 1))
                p.load_series(single_series, start_idx=idx)
            elif i < len(old_series) and old_series[i]:
                p.load_series(old_series[i])
                if i < len(old_annotations):
                    p._annotations = old_annotations[i][:]

            p.show()
            self.panels.append(p)

        self._relayout_panels()
        self._activate(self.panels[0])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout_panels()

    def _relayout_panels(self):
        """?꾩옱 mode + image_offset???곕씪 panels??setGeometry 吏곸젒 怨꾩궛.
        ?ㅻ쾭???숈옉 2?④퀎:
          Phase A ??癒쇱? widget ?덉뿉???대?吏(_disp_pix) ?꾩튂瑜??덉そ?쇰줈 ??꺼
                    letterbox(寃??媛?μ옄由? ?곸뿭??以꾩엫. ???④퀎?먯꽌??widget ?꾩튂 怨좎젙.
          Phase B ??letterbox媛 ???щ씪吏怨좊룄 ???뚮㈃ widget ?먯껜瑜??대룞 ???ㅼ젣 ?ㅻ쾭??
        諛붽묑履??대룞(offset > 0)? Phase A ?놁씠 怨㏃옣 widget ?대룞 (媛?利앷?).
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
        ox = self._image_offset_x   # ?묒닔=諛붽묑, ?뚯닔=?덉そ
        oy = self._image_offset_y

        for i, p in enumerate(self.panels):
            r = i // cols
            c = i %  cols
            # 媛?대뜲濡쒕???諛⑺뼢 遺??(-1, 0, +1)
            sx = 0 if abs(c - cc) < 1e-6 else (1 if c > cc else -1)
            sy = 0 if abs(r - cr) < 1e-6 else (1 if r > cr else -1)

            # 媛??⑤꼸??letterbox ?쒓퀎 (?대?吏 二쇰? 寃????
            if p._disp_pix is not None:
                lb_x = max(0, (cell_w - p._disp_pix.width())  // 2)
                lb_y = max(0, (cell_h - p._disp_pix.height()) // 2)
            else:
                lb_x = lb_y = 0

            # X異?
            if sx == 0:
                paint_x = 0; widget_x = 0
            elif ox < 0:
                # ?덉そ ?대룞: letterbox留뚰겮? paint, 珥덇낵遺꾨쭔 widget
                paint_x  = max(ox, -lb_x)         # ?뚯닔, |paint_x| ??lb_x
                widget_x = ox - paint_x            # ?⑥? ?덉そ ?대룞??(??)
            else:
                # 諛붽묑 ?대룞: paint ???곌퀬 widget留?
                paint_x = 0
                widget_x = ox

            # Y異?
            if sy == 0:
                paint_y = 0; widget_y = 0
            elif oy < 0:
                paint_y  = max(oy, -lb_y)
                widget_y = oy - paint_y
            else:
                paint_y = 0
                widget_y = oy

            # ?곸슜
            # paint_offset_for_panel: sx=-1 醫뚯륫 ?⑤꼸?닿퀬 paint_x=-5(?덉そ)硫?
            #   ?대?吏瑜?+5 (?ㅻⅨ履??덉そ) 諛⑺뼢?쇰줈 洹몃┝ ??sx * paint_x = -1 * -5 = +5 ??
            p._paint_offset_x = sx * paint_x
            p._paint_offset_y = sy * paint_y

            # widget ?꾩튂
            x = c * cell_w + sx * widget_x
            y = r * cell_h + sy * widget_y
            p.setGeometry(int(x), int(y), int(cell_w), int(cell_h))
            p.update()

    # ?? ?대?吏 ?대룞 (PPT 罹≪쿂??媛?議곗젅) ?????????????????????
    def image_offset(self):
        return (self._image_offset_x, self._image_offset_y)

    def set_image_offset(self, ox, oy):
        """?덈?媛??ㅼ젙. 蹂寃쎈맂 (ox, oy) 諛섑솚."""
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
        """?⑤꼸??letterbox(?대?吏媛 ?ㅼ젣 蹂댁씠???곸뿭) 湲濡쒕쾶 醫뚰몴.
        zoom怨?臾닿? ???ъ슜?먭? ?붾㈃?먯꽌 ?대?吏 ?곸뿭?쇰줈 ?몄떇?섎뒗 ?ш컖??
        hit-test (?대뼡 ?⑤꼸???대┃?덈뒗媛) ??"""
        if not panel._disp_pix:
            return None
        zoom = max(0.001, float(panel.zoom))
        base_w = int(round(panel._disp_pix.width()  / zoom))
        base_h = int(round(panel._disp_pix.height() / zoom))
        # paintEvent? ?숈씪??letterbox 醫뚯긽????(pan_offset? 誘몄쟻??
        local_x = (panel.width()  - base_w) // 2 + panel._paint_offset_x
        local_y = (panel.height() - base_h) // 2 + panel._paint_offset_y
        return (panel.x() + local_x, panel.y() + local_y, base_w, base_h)

    def _panel_at_global(self, gx, gy):
        """ViewerGrid 醫뚰몴 (gx, gy)?먯꽌 ?대┃/留덉슦???꾩튂???대떦?섎뒗 ?⑤꼸 諛섑솚.

        Qt???ㅼ젣 widget z-order(self.children() 留덉?留?= 留???瑜?湲곗??쇰줈
        letterbox hit-test瑜??섑뻾?쒕떎.  panels 由ъ뒪???쒖꽌 ???children() ?쒖꽌瑜?
        ?ъ슜?섎?濡? _relayout_panels?먯꽌 raise_()濡?蹂댁젙??z-order媛 洹몃?濡?諛섏쁺?쒕떎.
        """
        panel_set = set(self.panels)
        for child in reversed(self.children()):
            if child not in panel_set:
                continue
            r = self._panel_letterbox_global_rect(child)
            if r is None:
                continue
            x, y, w, h = r
            if x <= gx < x + w and y <= gy < y + h:
                return child
        return None

    def _panel_image_global_rect(self, panel, pan_x=None, pan_y=None):
        """?⑤꼸??_disp_pix媛 李⑥??섎뒗 湲濡쒕쾶(ViewerGrid) 醫뚰몴 ?ш컖??
        pan_x, pan_y媛 二쇱뼱吏硫?洹?媛믪쑝濡? ?꾨땲硫?panel._pan_offset_*濡?"""
        if not panel._disp_pix:
            return None
        if pan_x is None:
            pan_x = panel._pan_offset_x
        if pan_y is None:
            pan_y = panel._pan_offset_y
        # ?⑤꼸 widget ?덉뿉??_disp_pix 洹몃젮吏??醫뚯긽??(paint_offset + pan_offset)
        local_x = ((panel.width()  - panel._disp_pix.width())  // 2
                   + panel._paint_offset_x + pan_x)
        local_y = ((panel.height() - panel._disp_pix.height()) // 2
                   + panel._paint_offset_y + pan_y)
        # 湲濡쒕쾶 醫뚰몴 = ?⑤꼸 widget???꾩튂 + 濡쒖뺄
        gx = panel.x() + local_x
        gy = panel.y() + local_y
        return (gx, gy, panel._disp_pix.width(), panel._disp_pix.height())

    def _snap_to_neighbors(self, active_panel, new_pan_x, new_pan_y, threshold=8):
        """active_panel??(new_pan_x, new_pan_y)濡?panning????
        ?몄젒 ?⑤꼸 ?대?吏??4媛?媛?μ옄由?L/R/T/B)??threshold ?대궡濡?媛源뚯썙吏硫??뺥솗???쇱튂?쒗궡.
        諛섑솚: 蹂댁젙??(pan_x, pan_y)."""
        rect_a = self._panel_image_global_rect(active_panel, new_pan_x, new_pan_y)
        if rect_a is None:
            return (new_pan_x, new_pan_y)
        ax, ay, aw, ah = rect_a
        a_left, a_right  = ax,         ax + aw
        a_top,  a_bot    = ay,         ay + ah

        # ?꾨낫 媛?μ옄由?紐⑥쓬
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

            # X 媛?μ옄由?留ㅼ묶: active 醫뚢넄?댁썐 醫? 醫뚢넄?? ?겸넄醫? ?겸넄??
            for ae, be in ((a_left, b_left), (a_left, b_right),
                           (a_right, b_left), (a_right, b_right)):
                d = be - ae   # ?댁썐 媛?μ옄由ъ뿉 留욎텛?ㅻ㈃ active瑜?d留뚰겮 ?대룞
                if abs(d) <= threshold and abs(d) < best_x_dist:
                    best_x_dist = abs(d)
                    best_dx = d

            # Y 媛?μ옄由?留ㅼ묶
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
        ?꾩옱 layout??洹몃?濡??좎??섎㈃??N媛??⑤꼸??梨꾩썙 ?ｌ쓬.
        - 1媛??쒕━利?+ multi-panel ??紐⑤뱺 ?⑤꼸??洹좊벑 遺꾨같
        - ?щ윭 ?쒕━利???媛??⑤꼸???ㅻⅨ ?쒕━利? 遺議깊븳 ?⑤꼸? 鍮꾩?
        """
        n_panels = len(self.panels)
        n = min(len(series_list), n_panels)
        if n == 0:
            return

        if len(series_list) == 1 and n_panels > 1:
            # ?⑥씪 ?쒕━利덈? 紐⑤뱺 ?⑤꼸??洹좊벑 遺꾨같
            dss   = series_list[0][1]
            total = len(dss)
            for i, p in enumerate(self.panels):
                idx = int(total * (i + 1) / (n_panels + 1))
                p.load_series(dss, start_idx=idx)
        else:
            for i in range(n):
                self.panels[i].load_series(series_list[i][1])
            # ???섏씠吏媛 ?⑤꼸蹂대떎 ?곸쑝硫??붿뿬 ?⑤꼸 鍮꾩? (?댁쟾 ?섏씠吏 ?붿옱 ?쒓굅)
            for i in range(n, n_panels):
                self.panels[i].clear()

        # ?섏씠吏 ?꾪솚 ??泥??⑤꼸???쒖꽦?쇰줈
        if self.panels:
            self._activate(self.panels[0])

        self._activate(self.panels[0])

    def save_multi_state(self):
        """?꾩옱 multi-panel ?곹깭(layout + ?⑤꼸蹂?series, idx, wl, ww, zoom + active) ???"""
        self._saved_multi = [
            (p.series[:], p.idx, p.wl, p.ww, p.zoom, p.initial_wl, p.initial_ww,
             getattr(p, '_annotations', [])[:], p.show_tags, p.show_annotations)
            for p in self.panels
        ]
        self._saved_multi_mode = self._mode
        self._saved_multi_active = next(
            (i for i, p in enumerate(self.panels) if p is self.active_panel), 0
        )

    def restore_multi_state(self):
        """??λ맂 multi-panel ?곹깭 蹂듭썝. ?놁쑝硫?False 諛섑솚."""
        if not self._saved_multi:
            return False
        target_mode = getattr(self, '_saved_multi_mode', '2x2')
        if target_mode == self._mode:
            # 媛숈? 紐⑤뱶硫?set_layout ?몄텧??no-op?대?濡?媛뺤젣濡??⑤꼸 ?ъ깮?깊븯吏 ?딄퀬 ?곗씠?곕쭔 蹂듭썝
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
            annotations = saved[7] if len(saved) > 7 else []
            show_tags = saved[8] if len(saved) > 8 else True
            show_annotations = saved[9] if len(saved) > 9 else True
            if series:
                p.series               = series
                p.idx                  = idx
                p.wl                   = wl
                p.ww                   = ww
                p.initial_wl           = initial_wl
                p.initial_ww           = initial_ww
                p.zoom                 = zoom
                p._annotations         = annotations[:]
                p.show_tags            = show_tags
                p.show_annotations     = show_annotations
                p._pixel_cache         = {}
                p._active_bval_filter  = None
                p._build_dwi_info()
                p._setup_bvalue_overlay()
                p._render()
        active_i = getattr(self, '_saved_multi_active', 0)
        active_i = min(max(active_i, 0), len(self.panels) - 1)
        self._activate(self.panels[active_i])
        return True

    # ?섏쐞 ?명솚 alias
    def save_2x2_state(self):     return self.save_multi_state()
    def restore_2x2_state(self):  return self.restore_multi_state()

    def toggle_tags_all(self):
        if not self.panels:
            return
        show_tags, show_annotations = self.overlay_state()
        if show_tags and show_annotations:
            new_state = (False, True)
        elif not show_tags and show_annotations:
            new_state = (False, False)
        else:
            new_state = (True, True)
        for p in self.panels:
            p.set_overlay_visibility(*new_state)

    def tag_state(self):
        return self.panels[0].show_tags if self.panels else True

    def overlay_state(self):
        if not self.panels:
            return True, True
        return self.panels[0].show_tags, self.panels[0].show_annotations

    # ?? Cross-reference ??????????????????????????????????????
    def set_cross_link(self, active):
        """紐⑤뱺 ?⑤꼸??cross_link 紐⑤뱶 ?ㅼ젙 諛??쒓렇???곌껐/?댁젣."""
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
            # X ?꾨Ⅸ 利됱떆 ?쒖꽦 ?⑤꼸 以묒븰??湲곗??쇰줈 cross-line ?쒖떆
            self._init_cross_from_active()

    def _init_cross_from_active(self):
        """X ?꾨Ⅸ 利됱떆 cross-line ?쒖떆.
        ?곗꽑?쒖쐞:
          1) 留덉슦??而ㅼ꽌媛 ?대뒓 ?대?吏 ?꾩뿉 ?덉쑝硫????대떦 ?⑤꼸/?쎌?
          2) ?꾨땲硫????쒖꽦 ?⑤꼸 ?대?吏 以묒븰
        """
        src         = None
        cross_pixel = None    # (row_f, col_f)

        # ?? 1) 而ㅼ꽌 ?꾨옒 ?대?吏 李얘린 ?????????????????????????
        global_pos = QCursor.pos()
        for p in self.panels:
            if not p.series:
                continue
            local = p.mapFromGlobal(global_pos)
            if not p.rect().contains(local):
                continue
            row_f, col_f = p._screen_to_image(local.x(), local.y())
            if row_f is None:
                continue                       # ?⑤꼸 ?덉씠吏留??대?吏 ?쎌? 諛?
            src         = p
            cross_pixel = (row_f, col_f)
            break

        # ?? 2) ?대갚: ?쒖꽦 ?⑤꼸 以묒븰 ???????????????????????????
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

        # ?? 怨듯넻: world 蹂??+ ?ㅻⅨ ?⑤꼸 ?숆린????????????????
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
        """src_panel?먯꽌 ?대┃ ???섎㉧吏 ?⑤꼸??援먯감???щ씪?댁뒪 ?낅뜲?댄듃."""
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
        # 罹≪쿂 ???뚮? ?뚮몢由?+ cross-hair ?쒓굅
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
            # 蹂듭썝
            ap._active = True
            if ch_backup is not None:
                ap._crosshair = ch_backup
                if ap._raw_pix:
                    ap._make_display()
            ap.update()
        return pix

    def grab_all(self):
        # ?꾩껜 罹≪쿂???쒖꽦 ?뚮몢由?+ 紐⑤뱺 cross-hair ?놁씠
        ap = self.active_panel
        was_active = False
        if ap and ap._active:
            was_active = True
            ap._active = False
            ap.update()

        # 紐⑤뱺 ?⑤꼸??crosshair ?좎떆 ?꾧린 + 諛깆뾽
        ch_backup = []
        for p in self.panels:
            ch_backup.append((p, p._crosshair))
            if p._crosshair is not None:
                p._crosshair = None
                if p._raw_pix:
                    p._make_display()
        # 媛뺤젣 利됱떆 paint 泥섎━
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


# ?????????????????????????????????????????????????????????????
#  Copy Area ?곸뿭 ?좏깮 ?ㅻ쾭?덉씠
# ?????????????????????????????????????????????????????????????
class _AreaSelector(QWidget):
    """viewer_grid ?꾩뿉 ?꾩썙???ъ슜?먭? 醫뚰겢由??쒕옒洹몃줈 吏곸궗媛곹삎 ?곸뿭???좏깮.
    ?꾨즺/痍⑥냼 ??callback(rect) ?몄텧. rect??viewer_grid 醫뚰몴怨꾩쓽 QRect ?먮뒗 None(痍⑥냼)."""
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
        # 肄쒕갚 ?꾩뿉 selector瑜?癒쇱? ?④? ??callback ?덉뿉??grab???몄텧?섎㈃
        # selector overlay媛 寃곌낵???ы븿?섏뼱 ?대몢???ш컖???멸낸?좎씠 罹≪쿂?섎뒗 嫄?諛⑹?
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
        # ?붾㈃ ?꾩껜 ?대몢???ㅻ쾭?덉씠 (?좏깮 ?곸뿭 ?쒖쇅)
        if self._start is not None and self._cur is not None:
            x1, y1 = self._start.x(), self._start.y()
            x2, y2 = self._cur.x(),   self._cur.y()
            sel = QRect(min(x1, x2), min(y1, y2),
                        abs(x2 - x1), abs(y2 - y1))
            # 4 ?곸뿭 ?대몼寃?
            dark = QColor(0, 0, 0, 128)
            p.fillRect(0, 0, self.width(), sel.top(), dark)            # ??
            p.fillRect(0, sel.bottom() + 1,
                       self.width(), self.height() - sel.bottom() - 1, dark)  # ?꾨옒
            p.fillRect(0, sel.top(),
                       sel.left(), sel.height() + 1, dark)             # 醫?
            p.fillRect(sel.right() + 1, sel.top(),
                       self.width() - sel.right() - 1, sel.height() + 1, dark)  # ??
            # ?좏깮 ?ш컖???멸낸??
            pen = QPen(QColor(0, 200, 255), 2)
            p.setPen(pen)
            p.drawRect(sel)
            # ?곗긽?⑥뿉 ?ш린 ?쒖떆
            label = f"{sel.width()} x {sel.height()}"
            p.setFont(QFont("Consolas", 11))
            p.fillRect(sel.left(), sel.top() - 22,
                       len(label) * 9 + 12, 20, QColor(0, 0, 0, 200))
            p.setPen(QColor(0, 200, 255))
            p.drawText(sel.left() + 6, sel.top() - 7, label)
        else:
            # ?쒖옉 ?? ?꾩껜 ?댁쭩 ?대몼寃?+ ?덈궡 硫붿떆吏
            p.fillRect(self.rect(), QColor(0, 0, 0, 60))
            p.setPen(QColor(0, 200, 255))
            p.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       tr('area_select_hint'))


# ?????????????????????????????????????????????????????????????
#  ?덉씠?꾩썐 洹몃━???쇱빱 (PowerPoint ?ㅽ???
# ?????????????????????????????????????????????????????????????
class _LayoutPicker(QWidget):
    """Popup 3횞3 grid picker ??hover to preview, click to apply layout."""
    layout_selected = pyqtSignal(str)   # e.g. "2x3"

    CELL = 30   # px per cell
    GAP  = 5    # gap between cells
    PAD  = 12   # outer padding
    N    = 3    # grid dimension (3횞3 max)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True)
        self._hc = 0   # highlighted cols (1-based, 0 = none)
        self._hr = 0   # highlighted rows
        inner = self.N * self.CELL + (self.N - 1) * self.GAP
        self.setFixedSize(inner + self.PAD * 2,
                          inner + self.PAD * 2 + 24)  # 24 = label row

    # ?? geometry helpers ????????????????????????????????????????
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

    # ?? paint ???????????????????????????????????????????????????
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
            label = f"{hr} x {hc}"
            p.setPen(QColor(220, 220, 220))
        else:
            label = "Layout"
            p.setPen(QColor(140, 140, 140))
        label_y = self.PAD + self.N * (self.CELL + self.GAP) - self.GAP + 5
        p.setFont(QFont("Consolas", 10))
        p.drawText(QRect(0, label_y, self.width(), 20),
                   Qt.AlignmentFlag.AlignCenter, label)

    # ?? interaction ?????????????????????????????????????????????
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


# ?????????????????????????????????????????????????????????????
#  ?쒕━利??ъ씠?쒕컮
# ?????????????????????????????????????????????????????????????
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

        # ???꾨줈 ?ㅽ겕濡?踰꾪듉 (紐⑸줉 ?꾩そ)
        self.up_btn = QPushButton("^")
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
        self.lw.setIconSize(QSize(144, 144))   # ?몃꽕???쒖떆 ?ш린 (2諛?
        self.lw.itemDoubleClicked.connect(
            lambda item: self.series_double_clicked.emit(self.lw.row(item))
        )
        layout.addWidget(self.lw, 1)

        # ???꾨옒濡??ㅽ겕濡?踰꾪듉 (紐⑸줉 ?꾨옒)
        self.down_btn = QPushButton("v")
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
        """紐⑸줉??lines以꾨쭔???ㅽ겕濡?(????踰꾪듉)."""
        sb = self.lw.verticalScrollBar()
        sb.setValue(sb.value() + lines * sb.singleStep())

    def set_study(self, ds):
        patient  = _tag(ds, 'PatientName', 'Anonymous')
        pat_id   = _tag(ds, 'PatientID',  '')
        sex      = _tag(ds, 'PatientSex', '')
        age      = _tag(ds, 'PatientAge', '')
        date     = _fmt_date(_tag(ds, 'StudyDate', ''))
        modality = _tag(ds, 'Modality',   '')
        self.study_info.setText(
            f"{patient}\n"
            f"   {pat_id}  {sex}  {age}\n"
            f"{date}  [{modality}]"
        )

    def populate(self, series_list, thumbnails=None):
        """series_list: [(label, pairs), ...]
        thumbnails: [QPixmap or None, ...]  ??媛숈? 湲몄씠"""
        self.lw.clear()

        # ?? ?꾩씠肄?144px) + 醫뚯슦 ?щ갚???쒖쇅???띿뒪??媛??????
        avail_w = max(50, self.width() - 144 - 22)

        # 1?④퀎: 紐⑤뱺 ??ぉ ?곗씠???섏쭛 + 泥?以??ㅻ챸) 紐⑸줉 ?앹꽦
        items_data   = []
        first_lines  = []
        for label, pairs in series_list:
            ds0  = pairs[0][1]
            num  = _tag(ds0, 'SeriesNumber',      '?')
            desc = _tag(ds0, 'SeriesDescription', f'Series {num}')
            mod  = _tag(ds0, 'Modality',           '')
            first_lines.append(f"[{num}] {desc}")
            items_data.append((label, num, desc, mod, len(pairs)))

        # 2?④퀎: 紐⑤뱺 泥?以꾩씠 ??以꾩뿉 ?ㅼ뼱?ㅻ뒗 理쒕? ?고듃 ?ш린 怨꾩궛
        font_px = _fit_font_px(first_lines, avail_w, "Consolas", min_px=11, max_px=18)

        # 3?④퀎: 理쒖냼 ?ш린?먯꽌???섏튂????ぉ???덉쑝硫?word-wrap ?쒖꽦??
        chk_f  = QFont("Consolas")
        chk_f.setPixelSize(font_px)
        chk_fm = QFontMetrics(chk_f)
        needs_wrap = any(chk_fm.horizontalAdvance(ln) > avail_w
                         for ln in first_lines if ln.strip())
        self.lw.setWordWrap(needs_wrap)

        # 4?④퀎: 怨꾩궛???ш린濡?stylesheet ?낅뜲?댄듃
        self.lw.setStyleSheet(f"""
            QListWidget {{
                background:#111;color:#ccc;
                border:none;font-size:{font_px}px;font-family:Consolas;
            }}
            QListWidget::item {{ padding:8px 6px;border-bottom:1px solid #1c1c1c; }}
            QListWidget::item:selected {{ background:#004a8f;color:white; }}
            QListWidget::item:hover    {{ background:#1e3a5f; }}
        """)

        # 5?④퀎: ??ぉ 異붽?
        for i, (label, num, desc, mod, count) in enumerate(items_data):
            item = QListWidgetItem(f"[{num}] {desc}\n      {count} images  {mod}")
            item.setToolTip(label)
            if thumbnails and i < len(thumbnails) and thumbnails[i] is not None:
                item.setIcon(QIcon(thumbnails[i]))
            self.lw.addItem(item)

    def clear_all(self):
        self.lw.clear()
        self.study_info.setText("")

    def retranslate(self):
        self._tip_label.setText(tr('sidebar_tip'))


# ?????????????????????????????????????????????????????????????
#  硫붿씤 ?덈룄??
# ?????????????????????????????????????????????????????????????
class DicomViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hwang Viewer for Radiologic Presentation v4.1")
        self.setAcceptDrops(True)
        self._series_list = []
        self._series_page = 0      # ?꾩옱 ?섏씠吏 (0-based)
        self._pan_mode    = False
        self._annotation_tool = 'none'
        self._annotation_actions = {}
        self._build_annotation_actions()

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        LocaleManager.instance().language_changed.connect(self.retranslate)
        self.showMaximized()       # ???쒖옉遺???꾩껜?붾㈃

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

        # statusBar 醫뚯륫???곴뎄 progress bar (?됱냼???④?)
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
        self._act(fm, "Open File...",    "Ctrl+O",       self.open_file)
        self._act(fm, "Open Folder...",  "Ctrl+Shift+O", self.open_folder)
        fm.addSeparator()
        self._act(fm, "Save Img...",    "Ctrl+S",       self.save_active)
        self._act(fm, "Save Scr...",    "Ctrl+Shift+S", self.save_all)
        fm.addSeparator()
        self._act(fm, "Save Area...", "Ctrl+Alt+S", self.save_area)
        fm.addSeparator()
        self._act(fm, "Quit", "Ctrl+Q", self.close)

        em = mb.addMenu("Edit")
        self._act(em, "Copy Img",     "Ctrl+C",       self.copy_active)
        self._act(em, "Copy Scr",     "Ctrl+Shift+C", self.copy_all)
        self._act(em, "Copy Area...", "Ctrl+Alt+C",   self.copy_area)

        self._act(em, "Save Area...", "Ctrl+Alt+S", self.save_area)

        vm = mb.addMenu("View")
        # ?? Layout ?쒕툕硫붾돱 (1횞1 ~ 3횞3 9醫? ???????????????
        lm = vm.addMenu("Layout")
        self._act(lm, "1 x 1",  "Ctrl+1", lambda: self._change_layout('1x1'))
        self._act(lm, "1 x 2",  "",       lambda: self._change_layout('1x2'))
        self._act(lm, "1 x 3",  "",       lambda: self._change_layout('1x3'))
        lm.addSeparator()
        self._act(lm, "2 x 1",  "",       lambda: self._change_layout('2x1'))
        self._act(lm, "2 x 2",  "Ctrl+2", lambda: self._change_layout('2x2'))
        self._act(lm, "2 x 3",  "",       lambda: self._change_layout('2x3'))
        lm.addSeparator()
        self._act(lm, "3 x 1",  "",       lambda: self._change_layout('3x1'))
        self._act(lm, "3 x 2",  "",       lambda: self._change_layout('3x2'))
        self._act(lm, "3 x 3",  "Ctrl+3", lambda: self._change_layout('3x3'))
        vm.addSeparator()
        self._act(vm, "Tag / Annotation Display",  "T",      self._toggle_tags)
        self._act(vm, "Reset W/L",                 "R",      self._reset_active)
        self._act(vm, "Toggle 1x1 / Multi",        "Space",  self._toggle_panel_zoom)
        self._act(vm, "Cross-reference ON/OFF",    "X",      self._toggle_cross_link)
        self._act(vm, "Panning ON/OFF",            "P",      self._toggle_pan_mode)
        vm.addSeparator()
        self._act_img_offset = self._act(vm, tr('menu_img_offset'), "", self.set_image_offset_dialog)
        self._act(vm, "Reset Pos",                  "Ctrl+G", self.reset_image_offset)
        vm.addSeparator()
        self._act(vm, "Fill Grid with Series", "", self._fill_grid_with_series)

        am = mb.addMenu("Annotation")
        for tool in ('measure', 'arrow', 'text', 'roi'):
            am.addAction(self._annotation_actions[tool])
        am.addSeparator()
        am.addAction(self._clear_annotation_action)
        am.addAction(self._clear_all_annotation_action)

        hm = mb.addMenu("Help")
        self._act(hm, "Keyboard & Mouse Shortcuts...", "F1", self._show_shortcuts)
        hm.addSeparator()
        self._act(hm, "About...", "", self._show_about)
        hm.addSeparator()
        lang_menu = hm.addMenu("Language")
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

    def _make_icon(self, kind, size=32):
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fg = QColor(220, 225, 230)
        accent = QColor(0, 160, 255)
        warn = QColor(255, 190, 55)
        ok = QColor(0, 220, 160)
        danger = QColor(255, 90, 90)
        painter.setPen(QPen(fg, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if kind == 'file':
            painter.drawRect(8, 5, 15, 22)
            painter.drawLine(17, 5, 23, 11)
            painter.drawLine(17, 5, 17, 11)
            painter.drawLine(17, 11, 23, 11)
        elif kind == 'folder':
            painter.drawLine(5, 11, 13, 11)
            painter.drawLine(13, 11, 15, 8)
            painter.drawLine(15, 8, 25, 8)
            painter.drawRect(5, 11, 22, 15)
        elif kind == 'layout':
            for x in (6, 17):
                for y in (6, 17):
                    painter.drawRect(x, y, 9, 9)
        elif kind == 'fill':
            painter.setPen(QPen(accent, 2))
            painter.drawRect(6, 6, 20, 20)
            painter.drawLine(10, 16, 22, 16)
            painter.drawLine(16, 10, 16, 22)
        elif kind == 'prev':
            painter.setBrush(fg)
            painter.drawPolygon([QPoint(10, 16), QPoint(21, 8), QPoint(21, 24)])
        elif kind == 'next':
            painter.setBrush(fg)
            painter.drawPolygon([QPoint(22, 16), QPoint(11, 8), QPoint(11, 24)])
        elif kind == 'tags':
            painter.setPen(QPen(accent, 2))
            painter.drawRect(7, 8, 18, 15)
            font = QFont("Arial")
            font.setBold(True)
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(QRect(7, 8, 18, 15), Qt.AlignmentFlag.AlignCenter, "T")
        elif kind == 'wl':
            painter.drawEllipse(7, 7, 18, 18)
            painter.drawLine(16, 7, 16, 25)
            painter.drawLine(9, 21, 23, 11)
        elif kind == 'position':
            painter.setPen(QPen(accent, 2))
            painter.drawLine(16, 5, 16, 27)
            painter.drawLine(5, 16, 27, 16)
            painter.drawEllipse(12, 12, 8, 8)
        elif kind == 'cross':
            painter.setPen(QPen(ok, 2))
            painter.drawLine(7, 7, 25, 25)
            painter.drawLine(25, 7, 7, 25)
        elif kind == 'pan':
            painter.drawLine(16, 6, 16, 26)
            painter.drawLine(6, 16, 26, 16)
            painter.drawLine(16, 6, 12, 10)
            painter.drawLine(16, 6, 20, 10)
            painter.drawLine(16, 26, 12, 22)
            painter.drawLine(16, 26, 20, 22)
            painter.drawLine(6, 16, 10, 12)
            painter.drawLine(6, 16, 10, 20)
            painter.drawLine(26, 16, 22, 12)
            painter.drawLine(26, 16, 22, 20)
        elif kind == 'copy':
            painter.drawRect(10, 8, 14, 17)
            painter.drawRect(6, 5, 14, 17)
        elif kind == 'area':
            painter.setPen(QPen(warn, 2, Qt.PenStyle.DashLine))
            painter.drawRect(7, 7, 18, 18)
        elif kind == 'save':
            painter.drawRect(7, 6, 18, 20)
            painter.drawRect(11, 18, 10, 6)
            painter.drawLine(11, 6, 11, 13)
            painter.drawLine(21, 6, 21, 13)
        elif kind == 'measure':
            painter.setPen(QPen(warn, 2))
            painter.drawLine(6, 22, 26, 10)
            for t in range(0, 5):
                x = 8 + t * 4
                y = 21 - t * 2
                painter.drawLine(x, y, x + 2, y + 4)
        elif kind == 'arrow':
            painter.setPen(QPen(QColor(255, 145, 0), 2))
            painter.drawLine(7, 23, 24, 8)
            painter.drawLine(24, 8, 22, 17)
            painter.drawLine(24, 8, 15, 10)
        elif kind == 'text':
            painter.setPen(QPen(fg, 2))
            font = QFont("Arial")
            font.setBold(True)
            font.setPixelSize(22)
            painter.setFont(font)
            painter.drawText(QRect(5, 3, 22, 25), Qt.AlignmentFlag.AlignCenter, "T")
        elif kind == 'roi':
            painter.setPen(QPen(ok, 2))
            painter.drawEllipse(7, 7, 18, 18)
            font = QFont("Arial")
            font.setBold(True)
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(QRect(7, 7, 18, 18), Qt.AlignmentFlag.AlignCenter, "O")
        elif kind == 'clear':
            painter.setPen(QPen(danger, 2))
            painter.drawLine(8, 8, 24, 24)
            painter.drawLine(24, 8, 8, 24)
        elif kind == 'clear_all':
            painter.setPen(QPen(danger, 2))
            painter.drawRect(7, 7, 18, 18)
            painter.drawLine(9, 9, 23, 23)
            painter.drawLine(23, 9, 9, 23)

        painter.end()
        return QIcon(pix)

    def _icon_action(self, label, slot=None, icon=None):
        action = QAction(self._make_icon(icon), label, self) if icon else QAction(label, self)
        if slot:
            action.triggered.connect(slot)
        return action

    def _build_annotation_actions(self):
        labels = {'measure': 'Measure', 'arrow': 'Arrow', 'text': 'Text', 'roi': 'ROI'}
        self._annotation_actions = {}
        for tool, label in labels.items():
            action = QAction(self._make_icon(tool), label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, t=tool: self._set_annotation_tool(t))
            self._annotation_actions[tool] = action
        self._clear_annotation_action = QAction(self._make_icon('clear'), "CLR Ann", self)
        self._clear_annotation_action.triggered.connect(self._clear_active_annotations)
        self._clear_all_annotation_action = QAction(self._make_icon('clear_all'), "CLR All Ann", self)
        self._clear_all_annotation_action.triggered.connect(self._clear_all_annotations)

    def _show_layout_picker(self):
        picker = _LayoutPicker(self)
        picker.layout_selected.connect(self._change_layout)
        for tb in getattr(self, '_dynamic_toolbars', (self._toolbar1, self._toolbar2)):
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
            act.setText(('* ' if code == current else '  ') + labels[code])

    def retranslate(self):
        self._act_img_offset.setText(tr('menu_img_offset'))
        self._update_lang_marks()
        self.sidebar.retranslate()
        self.viewer_grid.update()

    # ?? progress bar ?ы띁 ???????????????????????????????????
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

    # ?? ?쒕━利?媛?대뜲 ?щ씪?댁뒪濡??몃꽕??QPixmap) ?앹꽦 ??????
    def _make_thumbnail(self, pairs, size=144):
        """
        pairs: [(Path, hdr_ds), ...] (?대? InstanceNumber ?뺣젹??
        媛?대뜲 ?щ씪?댁뒪???쎌????붿퐫?⑺빐??size횞size QPixmap 諛섑솚.
        ?ㅽ뙣?섎㈃ None.
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

            # multi-channel / multi-frame 泥섎━ ??_render? ?숈씪 濡쒖쭅
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

            # auto W/L (5??5 percentile)
            p5, p95 = np.percentile(arr, [5, 95])
            wl = (p5 + p95) / 2.0
            ww = max(1.0, float(p95 - p5))
            lo = wl - ww / 2.0
            hi = wl + ww / 2.0
            arr8 = ((np.clip(arr, lo, hi) - lo) / (hi - lo) * 255).astype(np.uint8)
            arr8 = np.ascontiguousarray(arr8)
            h, w = arr8.shape
            qimg = QImage(arr8.tobytes(), w, h, w, QImage.Format.Format_Grayscale8)
            pix  = QPixmap.fromImage(qimg.copy())  # bytes ?쇱씠?꾪???遺꾨━
            return pix.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        except Exception:
            return None

    def _build_toolbar(self):
        p = self._toolbar_params()
        self._tb_widths_stale  = True   # widths need measuring on first layout call
        self._tb_base_widths   = []     # widths measured at DPI-base font
        self._tb_font_applied  = None   # font_px currently reflected in stylesheet

        # ?? Toolbar rows (content distributed dynamically) ????????
        tb1 = QToolBar("Row 1", self)
        tb1.setMovable(False)
        tb1.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb1.setIconSize(QSize(p['icon_sz'], p['icon_sz']))
        self.addToolBar(tb1)
        self._toolbar1 = tb1

        self.addToolBarBreak()

        tb2 = QToolBar("Row 2", self)
        tb2.setMovable(False)
        tb2.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb2.setIconSize(QSize(p['icon_sz'], p['icon_sz']))
        self.addToolBar(tb2)
        self._toolbar2 = tb2
        self._dynamic_toolbars = [tb1, tb2]

        for row in range(3, 6):
            self.addToolBarBreak()
            tb = QToolBar(f"Row {row}", self)
            tb.setMovable(False)
            tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            tb.setIconSize(QSize(p['icon_sz'], p['icon_sz']))
            self.addToolBar(tb)
            tb.hide()
            self._dynamic_toolbars.append(tb)

        # ?? helpers ???????????????????????????????????????????????
        def act(label, slot=None, icon=None):
            return self._icon_action(label, slot, icon)

        def sep():
            a = QAction(self)
            a.setSeparator(True)
            return a

        # ?? Layout action (replaces QToolButton; position resolved via widgetForAction) ??
        self._layout_action = act("⊞ Layout ▾", self._show_layout_picker)

        # ?? Page label action (replaces QLabel; dim-styled after each redistribution) ??
        self._page_action = act("  Series  -  ")

        # ?? Flat ordered list of ALL toolbar items ????????????????
        self._all_tb_actions = [
            act("📁 File",         self.open_file),
            act("📁 Folder",       self.open_folder),
            sep(),
            self._layout_action,
            act("⊞ Fill",          self._fill_grid_with_series),
            sep(),
            self._page_action,
            act("◀",               self._series_prev_page),
            act("▶",               self._series_next_page),
            sep(),
            act("🏷️ Tags",        self._toggle_tags),
            act("↺ W/L",           self._reset_active),
            act("↺ Pos",           self.reset_image_offset),
            act("✣ X-ref",         self._toggle_cross_link),
            act("✋ Pan",          self._toggle_pan_mode),
            sep(),
            act("📋 Copy Img",     self.copy_active),
            act("🗂️ Copy Scr",    self.copy_all),
            act("✂️ Copy Area",    self.copy_area),
            sep(),
            act("💾 Save Img",     self.save_active),
            act("💾 Save Scr",     self.save_all),
            act("💾 Save Area",    self.save_area),
            sep(),
            self._annotation_actions['measure'],
            self._annotation_actions['arrow'],
            self._annotation_actions['text'],
            self._annotation_actions['roi'],
            self._clear_annotation_action,
            self._clear_all_annotation_action,
        ]

        # ?? Load all into tb1 initially; _update_toolbar_layout redistributes ??
        for a in self._all_tb_actions:
            tb1.addAction(a)

    # ?? DPI-adaptive toolbar scaling ????????????????????????????

    def _toolbar_params(self):
        """Compute toolbar font/icon sizes scaled to the current screen's logical DPI.

        Uses logicalDotsPerInch so that:
          ??100%-scaling 4K (high physical DPI, no OS scaling) ??scale > 1 (text grows)
          ??HiDPI-managed 4K (devicePixelRatio=2, logical DPI ??96) ??scale ??1 (Qt handles it)
          ??Windows 125%/150% text scaling ??scale 1.25/1.5
        """
        screen = self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        dpi   = screen.logicalDotsPerInch() if screen else 96.0
        scale = max(0.6, min(3.0, dpi / 96.0))

        font_px = max(8,  round(24 * scale * 0.64 * 0.84))
        icon_sz = max(14, round(24 * scale * 0.8))
        pad_v   = max(1,  round(3  * scale))   # tight vertical padding
        pad_h   = max(3,  round(6 * scale))
        spacing = max(1,  round(2  * scale))   # tight inter-button spacing
        tb_pad  = max(1,  round(2  * scale))   # tight toolbar outer padding

        # Anti-clipping: iteratively reduce font_px until text height ??icon height.
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
        for tb in getattr(self, '_dynamic_toolbars', []):
            tb.setIconSize(QSize(p['icon_sz'], p['icon_sz']))
        self._tb_widths_stale = True  # button sizes changed ??re-measure on next layout
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
        # QToolBar sizeHint can under-report a little on Windows/HiDPI with
        # text-beside-icon buttons. Use a conservative row width so actions
        # wrap before the right edge instead of being clipped.
        available = max(320, int(self.width() * 0.98) - 24)
        if available <= 0:
            return

        p         = self._toolbar_params()
        base_font = p['font_px']
        max_font  = p['icon_sz']   # text height must not exceed icon height

        def _do_measure(font_px):
            """Apply font_px to stylesheet, load all actions into tb1, return width list."""
            self.setStyleSheet(self._app_stylesheet(dict(p, font_px=font_px)))
            for tb in self._dynamic_toolbars:
                tb.setIconSize(QSize(p['icon_sz'], p['icon_sz']))
                tb.clear()
            for a in actions:
                self._toolbar1.addAction(a)
            return [
                ((self._toolbar1.widgetForAction(a).sizeHint().width() + 1)
                 if self._toolbar1.widgetForAction(a) else 0)
                for a in actions
            ]

        # ?? (Re-)measure base widths when DPI changes ?????????????
        if getattr(self, '_tb_widths_stale', True):
            self._tb_base_widths  = _do_measure(base_font)
            self._tb_widths       = self._tb_base_widths[:]
            self._tb_font_applied = base_font
            self._tb_widths_stale = False

        base_total = sum(self._tb_base_widths)

        # ?? Determine target font ?????????????????????????????????
        if 0 < base_total <= available:
            # Everything fits in one row ??scale font to fill width
            target = min(round(base_font * available / base_total), max_font)
            target = max(target, base_font)
        else:
            target = base_font   # needs two rows; stay at base

        # ?? Apply target font if changed ??????????????????????????
        if target != getattr(self, '_tb_font_applied', base_font):
            new_w = _do_measure(target)
            if target > base_font and sum(new_w) > available:
                # Linear estimate overshot due to fixed padding ??revert
                new_w = _do_measure(base_font)
                target = base_font
            self._tb_widths       = new_w
            self._tb_font_applied = target

        rows = []
        cur = []
        cur_w = 0
        for action, width in zip(actions, self._tb_widths):
            if action.isSeparator() and not cur:
                continue
            if cur and cur_w + width > available:
                while cur and cur[-1].isSeparator():
                    cur.pop()
                if cur:
                    rows.append(cur)
                cur = []
                cur_w = 0
                if action.isSeparator():
                    continue
            cur.append(action)
            cur_w += width
        while cur and cur[-1].isSeparator():
            cur.pop()
        if cur:
            rows.append(cur)

        if len(rows) > 2 and sum(self._tb_widths) <= available * 2:
            best = None
            best_score = None
            for split in range(1, len(actions)):
                left = list(actions[:split])
                right = list(actions[split:])
                while left and left[-1].isSeparator():
                    left.pop()
                while right and right[0].isSeparator():
                    right.pop(0)
                while right and right[-1].isSeparator():
                    right.pop()
                if not left or not right:
                    continue
                left_w = sum(self._tb_widths[actions.index(a)] for a in left)
                right_w = sum(self._tb_widths[actions.index(a)] for a in right)
                if left_w <= available and right_w <= available:
                    score = max(left_w, right_w)
                    if best is None or score < best_score:
                        best = (left, right)
                        best_score = score
            if best is not None:
                rows = list(best)

        if not rows:
            rows = [[]]

        while len(rows) > len(self._dynamic_toolbars):
            self.addToolBarBreak()
            tb = QToolBar(f"Row {len(self._dynamic_toolbars) + 1}", self)
            tb.setMovable(False)
            tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            tb.setIconSize(QSize(p['icon_sz'], p['icon_sz']))
            self.addToolBar(tb)
            self._dynamic_toolbars.append(tb)

        for i, tb in enumerate(self._dynamic_toolbars):
            tb.clear()
            if i < len(rows):
                for action in rows[i]:
                    tb.addAction(action)
                tb.show()
            else:
                tb.hide()

        for tb in self._dynamic_toolbars:
            w = tb.widgetForAction(self._page_action)
            if w is not None:
                w.setStyleSheet("color:#aaa; background:transparent;")
                break

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

    # ????????????????????????????????????????????????????????????

    def _page_size(self):
        """?꾩옱 layout???⑤꼸 ??(?섏씠吏???쒕━利???."""
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
            f"  Series  {start}-{end} / {n}  (p{page+1}/{total_pages})  "
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
        # ?섏씠吏 ?몃뜳?ㅻ? ?뺤긽 踰붿쐞濡?蹂댁젙 (layout 蹂寃??깆쑝濡?鍮쀫굹媛붿쓣 ???덉쓬)
        self._series_page = max(0, min(self._series_page, total_pages - 1))
        start       = self._series_page * ps
        page_series = self._series_list[start:start + ps]
        self.viewer_grid.load_multi_series(page_series)
        self._update_page_label()
        s = start + 1
        e = min(start + ps, len(self._series_list))
        self.statusBar().showMessage(tr('status_page_nav').format(
            s=s, e=e, page=self._series_page + 1, total=total_pages))

    # ?? ?뚯씪 濡쒕뱶 ?????????????????????????????????????????????
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

        _t_start = time.perf_counter()  # ??TIMER: ?꾩껜 ?쒖옉

        # ?? 1?④퀎: ?ㅻ뜑 蹂묐젹 ?쎄린 (罹먯떆 ?곗꽑) ??????????????????
        _t0       = time.perf_counter()  # ??TIMER: ?ㅻ뜑 ?ㅼ틪 ?쒖옉
        file_headers: list = []
        cache_key = str(p.resolve()) if p.is_dir() else None
        cache_hit = False

        if cache_key and cache_key in _header_cache:
            cached_n, cached_headers = _header_cache[cache_key]
            if cached_n == total:
                file_headers = list(cached_headers)
                cache_hit    = True
            else:
                del _header_cache[cache_key]   # ?뚯씪 ??蹂寃???罹먯떆 臾댄슚??

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

        _t1 = time.perf_counter()  # ??TIMER: ?ㅻ뜑 ?ㅼ틪 醫낅즺
        print(f"[TIMER] 1단계 헤더 스캔:     {_t1-_t0:.3f}s  "
              f"({total}개 파일, {len(file_headers)}개 성공)"
              + (" [캐시 히트]" if cache_hit else ""))

        if not file_headers:
            self._progress_hide()
            self.statusBar().showMessage(tr('status_no_dicom_readable'))
            QMessageBox.warning(self, tr('dlg_error_title'), tr('dlg_no_dicom'))
            return

        # ?? 2?④퀎: SeriesInstanceUID 湲곗? 洹몃９??????????????????
        _t0 = time.perf_counter()  # ??TIMER: 洹몃９???쒖옉
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
        _t1 = time.perf_counter()  # ??TIMER: 洹몃９??醫낅즺
        print(f"[TIMER] 2단계 시리즈 그룹:   {_t1-_t0:.3f}s  ({len(self._series_list)}개 시리즈)")

        # ?? 3?④퀎: ?쒕━利덈퀎 ?몃꽕???앹꽦 (媛?대뜲 ?щ씪?댁뒪) ??????
        _t0 = time.perf_counter()  # ??TIMER: ?몃꽕???쒖옉
        n_series = len(self._series_list)
        self._progress_show("Thumbnails", 0, n_series)
        self.statusBar().showMessage(tr('status_thumbnails').format(n=n_series))
        thumbs = []
        for i, (label, pairs) in enumerate(self._series_list):
            thumbs.append(self._make_thumbnail(pairs))
            self._progress_show("Thumbnails", i + 1, n_series)
        _t1 = time.perf_counter()  # ??TIMER: ?몃꽕??醫낅즺
        print(f"[TIMER] 3단계 썸네일 생성:   {_t1-_t0:.3f}s  "
              f"({n_series}개 시리즈, 평균 {((_t1-_t0)/max(1,n_series)):.3f}s/시리즈)")

        # ?ъ씠?쒕컮
        self.sidebar.set_study(file_headers[0][1])
        self.sidebar.populate(self._series_list, thumbs)
        self._series_page = 0

        # ?? 4?④퀎: 泥??대?吏 ?⑤꼸 濡쒕뱶 ?????????????????????????
        _t0 = time.perf_counter()  # ??TIMER: ?대?吏 濡쒕뱶 ?쒖옉
        n = len(self._series_list)
        if n == 1:
            self.viewer_grid.set_layout('1x1')
            self.viewer_grid.load_to_active(self._series_list[0][1])
            msg = tr('status_1series').format(n=len(file_headers))
        else:
            # ?ъ슜?먭? 1횞1濡??먭퀬 ?덉뿀?ㅻ㈃ ?쒕━利??섏뿉 留욌뒗 layout ?먮룞 ?좏깮.
            # ?대? multi-panel 紐⑤뱶硫?洹몃?濡?議댁쨷 (3횞3 怨⑤씪??쇰㈃ 9媛???梨꾩?)
            if self.viewer_grid._mode == '1x1':
                self.viewer_grid.set_layout(self._auto_pick_layout(n))
            ps = self._page_size()
            self.viewer_grid.load_multi_series(self._series_list[:ps])
            placed = min(n, ps)
            msg = tr('status_multi_series').format(
                n=len(file_headers), s=n, p=placed, mode=self.viewer_grid._mode)
        _t1 = time.perf_counter()  # ??TIMER: ?대?吏 濡쒕뱶 醫낅즺
        print(f"[TIMER] 4단계 패널 로드:     {_t1-_t0:.3f}s")

        print("[TIMER] ----------------------------------------")
        print(f"[TIMER] 전체 로딩:           {_t1-_t_start:.3f}s  "
              f"(총 {total}개 파일, {len(self._series_list)}개 시리즈)")

        self._update_page_label()
        self._progress_hide()
        self.statusBar().showMessage(msg + tr('status_multi_hint'))

    @staticmethod
    def _auto_pick_layout(n_series):
        """?쒕━利??섏뿉 ?곕씪 媛???곹빀??layout 異붿쿇."""
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
        """?꾩옱 layout???⑤꼸 ?섎쭔???쒕━利덈? 梨꾩썙 ?ｌ쓬."""
        if not self._series_list:
            self.statusBar().showMessage(tr('status_need_folder'))
            return
        self._load_current_page()

    def _change_layout(self, mode):
        """紐⑤뱺 layout 蹂寃쎌쓽 ?⑥씪 吏꾩엯??
        - set_layout?쇰줈 洹몃━???ш뎄??(湲곗〈 ?쒕━利??먮룞 ?좎?)
        - ?덈줈 ?앷릿 鍮??⑤꼸? ?ъ씠?쒕컮??誘몄궗???쒕━利덈줈 梨꾩?
        """
        grid = self.viewer_grid
        grid.set_layout(mode)

        if not self._series_list:
            self._update_page_label()
            return

        def _first_path(s):
            """?쒕━利덉쓽 泥??뚯씪 寃쎈줈 諛섑솚 (?덉젙??留ㅼ묶 ??."""
            if not s:
                return None
            try:
                first = s[0]
                if isinstance(first, tuple) and len(first) >= 1:
                    return str(first[0])
            except Exception:
                pass
            return None

        # ?대? 梨꾩썙吏??⑤꼸 ??_series_list ?몃뜳??留ㅼ묶 (file path 湲곗?)
        used_idx = set()
        for p in grid.panels:
            p_path = _first_path(p.series)
            if p_path is None:
                continue
            for i, (_, s) in enumerate(self._series_list):
                if _first_path(s) == p_path:
                    used_idx.add(i)
                    break

        # 鍮??⑤꼸??誘몄궗???쒕━利덈줈 ?쒖꽌?濡?梨꾩?
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

        # ?섏씠吏 ?몃뜳?ㅻ? ??layout??留욎떠 媛깆떊 ??泥??⑤꼸 ?꾩튂 湲곗?
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
        show_tags, show_annotations = self.viewer_grid.overlay_state()
        if show_tags and show_annotations:
            msg = "Overlay: DICOM headers + annotations"
        elif show_annotations:
            msg = "Overlay: DICOM headers hidden, annotations visible"
        else:
            msg = "Overlay: DICOM headers and annotations hidden"
        self.statusBar().showMessage(msg)

    def _show_shortcuts(self):
        """?꾩껜 ?⑥텞??/ 留덉슦??議곗옉 媛?대뱶"""
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
        """Show application information."""
        QMessageBox.about(
            self,
            "About",
            "<h2>Hwang Viewer for Radiologic Presentation</h2>"
            "<p><b>v4.1</b></p>"
            f"<p>{tr('about_desc')}</p>"
            "<p>© 2026 Sungil Hwang<br>"
            "Department of Radiology<br>"
            "Seoul National University Bundang Hospital</p>"
            "<p style='color:#888;'>Built with Python, PyQt6, and pydicom</p>"
        )

    def _toggle_panel_zoom(self):
        """Toggle active panel between 1x1 zoom and previous multi-panel layout."""
        if self.viewer_grid._mode == '1x1':
            # 1횞1 ??吏곸쟾 multi ?덉씠?꾩썐 蹂듭썝
            if self.viewer_grid.restore_multi_state():
                mode = self.viewer_grid._mode
                self.statusBar().showMessage(tr('status_restore_mode').format(mode=mode))
            else:
                self._load_current_page()
                self.statusBar().showMessage(tr('status_restore_multi'))
        else:
            # multi ??1횞1: ?꾩옱 ?곹깭 ??????쒖꽦 ?⑤꼸 ?뺣?
            active = self.viewer_grid.active_panel
            if active and active.series:
                self.viewer_grid.save_multi_state()        # ???곹깭 ???
                saved       = active.series[:]
                saved_idx   = active.idx
                saved_wl    = active.wl
                saved_ww    = active.ww
                saved_zoom  = active.zoom
                saved_ann   = getattr(active, '_annotations', [])[:]
                self.viewer_grid.set_layout('1x1')
                p = self.viewer_grid.panels[0]
                p.series              = saved
                p.idx                 = saved_idx
                p.wl                  = saved_wl
                p.ww                  = saved_ww
                p.zoom                = saved_zoom
                p._annotations        = saved_ann
                p._pixel_cache        = {}
                p._active_bval_filter = None
                p._build_dwi_info()
                p._setup_bvalue_overlay()
                p._render()
                self.statusBar().showMessage(tr('status_zoom_1x1'))

    def _reset_active(self):
        """?쒖꽦 ?⑤꼸??W/L留?由ъ뀑. zoom怨?pan? ?좎? (Reset Position???곕줈 ?대떦)."""
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

    # ?? Panning 紐⑤뱶 (P) ?????????????????????????????????????
    def _set_annotation_tool(self, tool):
        if tool == self._annotation_tool:
            tool = 'none'
        self._annotation_tool = tool
        for name, action in self._annotation_actions.items():
            action.blockSignals(True)
            action.setChecked(name == tool)
            action.blockSignals(False)
        if tool != 'none':
            self._pan_mode = False
            for p in self.viewer_grid.panels:
                p.setCursor(Qt.CursorShape.CrossCursor)
            self.statusBar().showMessage(f"Annotation: {tool}")
        else:
            for p in self.viewer_grid.panels:
                p.setCursor(Qt.CursorShape.ArrowCursor)
            self.statusBar().showMessage("Annotation off")

    def _clear_active_annotations(self):
        p = self.viewer_grid.active_panel
        if p is not None:
            p.clear_annotations()
            self.statusBar().showMessage("Annotations cleared")

    def _clear_all_annotations(self):
        for p in self.viewer_grid.panels:
            p.clear_annotations()
        self.statusBar().showMessage("All annotations cleared")

    def _toggle_pan_mode(self):
        if self._annotation_tool != 'none':
            self._set_annotation_tool('none')
        self._pan_mode = not self._pan_mode
        cursor = (Qt.CursorShape.OpenHandCursor if self._pan_mode
                  else Qt.CursorShape.ArrowCursor)
        for p in self.viewer_grid.panels:
            p.setCursor(cursor)
        if self._pan_mode:
            self.statusBar().showMessage(tr('status_panning_on'))
        else:
            self.statusBar().showMessage(tr('status_panning_off'))

    # ?? 罹≪쿂 ?????????????????????????????????????????????????
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
        """?ъ슜?먭? viewer_grid ?꾩뿉 ?ш컖?뺤쓣 洹몃젮??洹??곸뿭留?罹≪쿂."""
        # ?쒖꽦 ?⑤꼸 ?뚮? ?뚮몢由?+ 紐⑤뱺 ?⑤꼸??cross-hair ?쇱떆 ?쒓굅
        active = self.viewer_grid.active_panel
        was_active = False
        if active and active._active:
            was_active = True
            active._active = False
            active.update()

        # 紐⑤뱺 ?⑤꼸??crosshair ?좎떆 ?꾧린 (媛??⑤꼸 蹂?backup)
        crosshair_backup = []
        for p in self.viewer_grid.panels:
            crosshair_backup.append((p, p._crosshair))
            if p._crosshair is not None:
                p._crosshair = None
                if p._raw_pix:
                    p._make_display()   # crosshair??_disp_pix??洹몃젮吏誘濡??ъ깮???꾩슂
        QApplication.processEvents()

        def on_done(rect):
            try:
                if rect is None or rect.width() < 4 or rect.height() < 4:
                    self.statusBar().showMessage(tr('status_area_cancel'))
                    return
                # 罹≪쿂 吏곸쟾 ??paint媛 ?뺤떎???앸궃 ?곹깭濡?蹂댁옣
                if active is not None:
                    active.repaint()
                for p, _ch in crosshair_backup:
                    p.repaint()
                QApplication.processEvents()

                full = self.viewer_grid.grab()
                # HiDPI 蹂댁젙
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
                # ?쒖꽦 ?뚮몢由?蹂듭썝
                if was_active and active:
                    active._active = True
                    active.update()
                # crosshair 蹂듭썝
                for p, ch in crosshair_backup:
                    if ch is not None:
                        p._crosshair = ch
                        if p._raw_pix:
                            p._make_display()

        sel = _AreaSelector(self.viewer_grid, on_done)
        sel.show()
        sel.raise_()
        sel.setFocus()

    # ?? ?⑤꼸 ?대?吏 ?대룞 (PPT 罹≪쿂????媛?議곗젅 + ?ㅻ쾭?? ????
    def _select_area_pixmap(self, on_pixmap):
        active = self.viewer_grid.active_panel
        was_active = False
        if active and active._active:
            was_active = True
            active._active = False
            active.update()

        crosshair_backup = []
        for p in self.viewer_grid.panels:
            crosshair_backup.append((p, p._crosshair))
            if p._crosshair is not None:
                p._crosshair = None
                if p._raw_pix:
                    p._make_display()
        QApplication.processEvents()

        def on_done(rect):
            try:
                if rect is None or rect.width() < 4 or rect.height() < 4:
                    self.statusBar().showMessage(tr('status_area_cancel'))
                    return
                if active is not None:
                    active.repaint()
                for p, _ch in crosshair_backup:
                    p.repaint()
                QApplication.processEvents()

                full = self.viewer_grid.grab()
                dpr_x = full.width() / max(1, self.viewer_grid.width())
                dpr_y = full.height() / max(1, self.viewer_grid.height())
                scaled = QRect(
                    int(round(rect.x() * dpr_x)),
                    int(round(rect.y() * dpr_y)),
                    int(round(rect.width() * dpr_x)),
                    int(round(rect.height() * dpr_y)),
                )
                on_pixmap(full.copy(scaled))
            finally:
                if was_active and active:
                    active._active = True
                    active.update()
                for p, ch in crosshair_backup:
                    if ch is not None:
                        p._crosshair = ch
                        if p._raw_pix:
                            p._make_display()

        sel = _AreaSelector(self.viewer_grid, on_done)
        sel.show()
        sel.raise_()
        sel.setFocus()

    def _adjust_image_offset_delta(self, dx, dy):
        """Shift+?쒕옒洹몄뿉???몄텧 ???대?吏 offset??(dx, dy) ?뷀븯湲?"""
        ox, oy = self.viewer_grid.adjust_image_offset_by(dx, dy)
        self.statusBar().showMessage(
            tr('status_img_offset_drag').format(ox=f"{ox:+d}", oy=f"{oy:+d}"), 3000
        )

    def set_image_offset_dialog(self):
        """View 硫붾돱?먯꽌 ?몄텧 ???대?吏 offset ?섎룞 ?낅젰 (?ㅻⅨ ?섏옄?먯꽌??媛숈? 媛??ъ궗??."""
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
        """紐⑤뱺 ?꾩튂 愿???곹깭 由ъ뀑: 媛? ?⑤꼸 ?대룞, 紐⑤뱺 ?⑤꼸??zoom + pan + W/L."""
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

    def save_area(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Area", "capture_area",
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)"
        )
        if not path:
            return

        def on_pixmap(pix):
            if pix:
                pix.save(path)
                self.statusBar().showMessage(tr('status_saved').format(path=path))

        self._select_area_pixmap(on_pixmap)

    # ?? ?쒕옒洹??쒕∼ ??????????????????????????????????????????
    def dragEnterEvent(self, event):
        event.accept() if event.mimeData().hasUrls() else event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self._load_path(urls[0].toLocalFile())


# ?????????????????????????????????????????????????????????????
#  吏꾩엯??
# ?????????????????????????????????????????????????????????????
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
    multiprocessing.freeze_support()  # PyInstaller EXE?먯꽌 ?쒕툕?꾨줈?몄뒪 spawn ?덉슜
    main()

