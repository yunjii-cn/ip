import sys
import os
import logging
import winreg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import socket
import ssl
import shutil
import time
import threading
import urllib.request
import subprocess
import glob
import re
import ctypes
import queue
import tempfile
import zipfile
from datetime import datetime, date

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame,
    QMessageBox, QListWidget,
    QListWidgetItem, QTextEdit, QComboBox, QSpinBox, QSizePolicy,
    QSplashScreen, QScrollArea, QLineEdit, QStyle
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QMetaObject, Q_ARG
from PyQt6.QtGui import QPixmap, QIcon, QFont, QColor, QPainter, QPen, QFontMetrics, QPalette, QLinearGradient

VERSION = datetime.now().strftime("%Y.%m.%d.%H%M")
GITHUB_REPO = "yunjii-cn/ip"
GITEE_REPO = "yunjii/ip"
MIHOMO_REPO = "MetaCubeX/mihomo"


def _load_repo_token(filename):
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        meipass_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        meipass_dir = base_dir
    for search_dir in [base_dir, meipass_dir]:
        token_path = os.path.join(search_dir, filename)
        if os.path.isfile(token_path):
            try:
                with open(token_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            return line
            except Exception:
                pass
    return ""


GITEE_TOKEN = _load_repo_token(".gitee_token")
GITHUB_TOKEN = _load_repo_token(".github_token")
APP_NAME = f"云集智能网联代理专家 v{VERSION}"
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 7890
PROXY_URL = f"{PROXY_HOST}:{PROXY_PORT}"


def _update_proxy_url():
    global PROXY_HOST, PROXY_PORT, PROXY_URL
    PROXY_URL = f"{PROXY_HOST}:{PROXY_PORT}"
NODE_TEST_TIMEOUT = 3
NODE_TEST_URL = "https://www.gstatic.com/generate_204"
NODE_TEST_URLS = [
    ("Google", "https://www.gstatic.com/generate_204"),
    ("Cloudflare", "https://cp.cloudflare.com/"),
]

CONFIG_URLS = [
    ("线路1", "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/1/config.yaml",
     "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/1/config.yaml"),
    ("线路2", "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/2/config.yaml",
     "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/2/config.yaml"),
    ("线路3", "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/3/config.yaml",
     "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/3/config.yaml"),
    ("线路4", "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/4/config.yaml",
     "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/4/config.yaml"),
]

COLOR_RED = "#C62828"
COLOR_RED_LIGHT = "#EF5350"
COLOR_BLUE = "#1565C0"
COLOR_BLUE_LIGHT = "#42A5F5"
COLOR_BLUE_DIM = "#1A2A4A"
COLOR_BG = "#0D0D0D"
COLOR_CARD = "#1A1A1A"
COLOR_BORDER = "#2D2D2D"
COLOR_TEXT = "#E0E0E0"
COLOR_DIM = "#888888"
COLOR_GREEN = "#4EBA65"
COLOR_ORANGE = "#FF9800"

STYLESHEET = f"""
QMainWindow {{ background-color: {COLOR_BG}; }}
QWidget {{ color: {COLOR_TEXT}; font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; }}
QLabel {{ color: {COLOR_TEXT}; }}
QLabel#dim {{ color: {COLOR_DIM}; }}
QLabel#accent {{ color: {COLOR_RED_LIGHT}; }}
QLabel#success {{ color: {COLOR_GREEN}; }}
QLabel#error {{ color: #FF6B80; }}
QLabel#suggestion {{ color: {COLOR_BLUE_LIGHT}; }}
QLabel#title {{ color: {COLOR_RED_LIGHT}; font-size: 11pt; font-weight: bold; }}
QLabel#subtitle {{ color: {COLOR_DIM}; font-size: 7pt; }}
QLabel#status-on {{ color: {COLOR_GREEN}; font-size: 9pt; font-weight: bold; }}
QLabel#status-off {{ color: {COLOR_TEXT}; font-size: 9pt; font-weight: bold; }}
QLabel#latency {{ color: {COLOR_GREEN}; font-size: 9pt; font-weight: bold; }}
QLabel#restart-hint {{ color: {COLOR_ORANGE}; font-size: 7pt; }}

QPushButton {{ background-color: #2D2D2D; color: {COLOR_TEXT}; border: none; border-radius: 4px; padding: 6px 12px; font-size: 9pt; font-weight: bold; }}
QPushButton:hover {{ background-color: #3A3A3A; }}
QPushButton#start {{ background-color: {COLOR_RED}; color: #FFFFFF; font-size: 10pt; padding: 10px; }}
QPushButton#start:hover {{ background-color: {COLOR_RED_LIGHT}; }}
QPushButton#stop {{ background-color: {COLOR_BLUE}; color: #FFFFFF; font-size: 10pt; padding: 10px; }}
QPushButton#stop:hover {{ background-color: #1976D2; }}
QPushButton#small {{ padding: 3px 8px; font-size: 8pt; }}
QPushButton#small-blue {{ background-color: #1A1A1A; color: {COLOR_BLUE_LIGHT}; border: 1px solid {COLOR_BORDER}; padding: 3px 8px; font-size: 8pt; }}
QPushButton#small-blue:hover {{ background-color: {COLOR_BLUE_DIM}; }}
QPushButton#small-green {{ background-color: #2E7D32; color: #FFFFFF; padding: 3px 8px; font-size: 8pt; }}
QPushButton#small-green:hover {{ background-color: #388E3C; }}
QPushButton#small-red {{ background-color: {COLOR_RED}; color: #FFFFFF; padding: 3px 8px; font-size: 8pt; }}
QPushButton#small-red:hover {{ background-color: {COLOR_RED_LIGHT}; }}
QPushButton:disabled {{ background-color: #1A1A1A; color: #555555; }}

QFrame#card {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; }}
QFrame#switch-row {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; }}
QFrame#header {{ background-color: {COLOR_CARD}; border-bottom: 1px solid {COLOR_BORDER}; }}
QFrame#line-row {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; }}
QFrame#line-active {{ background-color: {COLOR_CARD}; border: 2px solid {COLOR_RED_LIGHT}; border-radius: 6px; }}
QFrame#bottom-bar {{ background-color: {COLOR_CARD}; border-top: 1px solid {COLOR_BORDER}; }}
QFrame#card {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; }}
QFrame#expand-header {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; }}
QFrame#expand-header:hover {{ background-color: #222222; }}
QFrame#expand-body {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-top: none; border-radius: 0 0 6px 6px; }}

QTabWidget::pane {{ border: 1px solid {COLOR_BORDER}; background-color: {COLOR_BG}; border-radius: 4px; }}
QPushButton#nav-btn {{ background-color: {COLOR_CARD}; color: {COLOR_DIM}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; padding: 8px 0px; font-size: 9pt; font-weight: bold; }}
QPushButton#nav-btn:hover {{ background-color: #222222; color: {COLOR_TEXT}; }}
QPushButton#nav-btn:checked {{ background-color: {COLOR_RED}; color: #FFFFFF; border: 1px solid {COLOR_RED}; }}

QCheckBox {{ color: {COLOR_TEXT}; spacing: 8px; font-size: 9pt; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QRadioButton {{ color: {COLOR_TEXT}; spacing: 8px; font-size: 9pt; }}
QRadioButton::indicator {{ width: 0px; height: 0px; }}

QListWidget {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; color: {COLOR_TEXT}; outline: none; }}
QListWidget::item {{ padding: 4px; border-bottom: 1px solid {COLOR_BORDER}; }}
QListWidget::item:selected {{ background-color: {COLOR_BLUE_DIM}; color: {COLOR_BLUE_LIGHT}; }}

QComboBox {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 4px 8px; color: {COLOR_TEXT}; font-size: 8pt; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background-color: #111111; color: {COLOR_TEXT}; selection-background-color: #FF0000; border: 1px solid {COLOR_BORDER}; outline: none; }}
QComboBox QAbstractItemView::item {{ padding: 4px 8px; }}
QComboBox QAbstractItemView::item:hover {{ background-color: #CC0000; color: #FFFFFF; }}
QComboBox QAbstractItemView::item:selected {{ background-color: #FF0000; color: #FFFFFF; }}

QSpinBox {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 3px 6px; color: {COLOR_TEXT}; font-size: 8pt; }}
QSpinBox::up-button, QSpinBox::down-button {{ background-color: #2D2D2D; border: none; width: 18px; }}

QTextEdit#log {{ background-color: #0A0A0A; color: #AAAAAA; border: 1px solid {COLOR_BORDER}; border-radius: 4px; font-family: "Consolas", "Courier New", monospace; font-size: 7pt; padding: 4px; }}
"""


class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, label="", parent=None, default=False, color_on=None):
        super().__init__(parent)
        self._checked = default
        self._label = label
        self.setFixedHeight(36)
        self._update_cursor()

        self._track_color_off = QColor("#3A3A3A")
        self._track_color_on = QColor(color_on or COLOR_RED_LIGHT)
        self._thumb_color = QColor("#FFFFFF")
        self._thumb_x = 4.0
        self._anim = QPropertyAnimation(self, b"thumb_x")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        if default:
            self._thumb_x = 36.0

    def get_thumb_x(self):
        return self._thumb_x

    def set_thumb_x(self, val):
        self._thumb_x = val
        self.update()

    thumb_x = pyqtProperty(float, get_thumb_x, set_thumb_x)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._animate_thumb()
            self.toggled.emit(checked)
            self.update()

    def _animate_thumb(self):
        self._anim.stop()
        self._anim.setStartValue(self._thumb_x)
        self._anim.setEndValue(36.0 if self._checked else 4.0)
        self._anim.start()

    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self._animate_thumb()
            self.toggled.emit(self._checked)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        total_w = self.width()
        track_rect_x = total_w - 72
        track_rect_y = 6
        track_w = 64
        track_h = 24
        track_r = 12

        if self._label:
            label_color = QColor(COLOR_DIM) if not self.isEnabled() else QColor(COLOR_TEXT)
            painter.setPen(label_color)
            painter.setFont(QFont("Microsoft YaHei UI", 10))
            painter.drawText(0, 0, track_rect_x - 8, 36, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)

        if self.isEnabled():
            track_color = self._track_color_on if self._checked else self._track_color_off
            thumb_color = self._thumb_color
        else:
            track_color = QColor("#2A2A2A") if not self._checked else QColor("#5A3A2A")
            thumb_color = QColor(COLOR_DIM)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(int(track_rect_x), track_rect_y, track_w, track_h, track_r, track_r)

        thumb_r = 9
        thumb_cx = track_rect_x + self._thumb_x + thumb_r
        thumb_cy = track_rect_y + track_h // 2
        painter.setBrush(thumb_color)
        painter.drawEllipse(QPoint(int(thumb_cx), int(thumb_cy)), thumb_r, thumb_r)

        painter.end()

    def minimumSizeHint(self):
        return QSize(200, 36)

    def _update_cursor(self):
        if self.isEnabled():
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self._update_cursor()
        self.update()


class CheckBox(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, label="", parent=None, default=False):
        super().__init__(parent)
        self._checked = default
        self._label = label
        self.setFixedHeight(28)
        self.setMinimumWidth(self.minimumSizeHint().width())
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self.toggled.emit(checked)
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.toggled.emit(self._checked)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        box_size = 16
        box_x = 4
        box_y = (self.height() - box_size) // 2

        if self._checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLOR_RED_LIGHT))
            painter.drawRoundedRect(box_x, box_y, box_size, box_size, 3, 3)
            pen = QPen(QColor("#FFFFFF"), 2.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(box_x + 3, box_y + box_size // 2, box_x + box_size // 2 - 1, box_y + box_size - 4)
            painter.drawLine(box_x + box_size // 2 - 1, box_y + box_size - 4, box_x + box_size - 3, box_y + 3)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLOR_CARD))
            painter.drawRoundedRect(box_x, box_y, box_size, box_size, 3, 3)
            painter.setPen(QPen(QColor("#555555"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box_x, box_y, box_size, box_size, 3, 3)

        if self._label:
            painter.setPen(QColor(COLOR_TEXT))
            painter.setFont(QFont("Microsoft YaHei UI", 10))
            text_x = box_x + box_size + 8
            painter.drawText(text_x, 0, self.width() - text_x, self.height(),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)

        painter.end()

    def minimumSizeHint(self):
        fm = QFontMetrics(QFont("Microsoft YaHei UI", 10))
        text_w = fm.horizontalAdvance(self._label) if self._label else 0
        return QSize(4 + 16 + 8 + text_w + 8, 28)


class RadioButton(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, label="", parent=None, default=False):
        super().__init__(parent)
        self._checked = default
        self._label = label
        self._block_signal = False
        self.setFixedHeight(28)
        self.setMinimumWidth(self.minimumSizeHint().width())
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            if not self._block_signal:
                self.toggled.emit(checked)
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = True
            self.toggled.emit(True)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        circle_size = 16
        circle_x = 4
        circle_y = (self.height() - circle_size) // 2
        center_x = circle_x + circle_size // 2
        center_y = circle_y + circle_size // 2

        if self._checked:
            painter.setPen(QPen(QColor(COLOR_RED_LIGHT), 2))
            painter.setBrush(QColor(COLOR_CARD))
            painter.drawEllipse(QPoint(center_x, center_y), circle_size // 2, circle_size // 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLOR_RED_LIGHT))
            painter.drawEllipse(QPoint(center_x, center_y), 4, 4)
        else:
            painter.setPen(QPen(QColor("#555555"), 2))
            painter.setBrush(QColor(COLOR_CARD))
            painter.drawEllipse(QPoint(center_x, center_y), circle_size // 2, circle_size // 2)

        if self._label:
            painter.setPen(QColor(COLOR_TEXT))
            painter.setFont(QFont("Microsoft YaHei UI", 10))
            text_x = circle_x + circle_size + 8
            painter.drawText(text_x, 0, self.width() - text_x, self.height(),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)

        painter.end()

    def minimumSizeHint(self):
        fm = QFontMetrics(QFont("Microsoft YaHei UI", 10))
        text_w = fm.horizontalAdvance(self._label) if self._label else 0
        return QSize(4 + 16 + 8 + text_w + 8, 28)


class UpComboBox(QComboBox):
    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        combo_pos = self.mapToGlobal(QPoint(0, 0))
        popup_x = combo_pos.x()
        popup_y = combo_pos.y() - popup.height()
        if popup_y < 0:
            popup_y = combo_pos.y() + self.height()
        popup.move(popup_x, popup_y)


class QTextEditLogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        msg = self.format(record)
        self.callback(msg)


log = logging.getLogger("yunji")
log.setLevel(logging.DEBUG)
_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')

if not getattr(sys, 'frozen', False):
    _console_handler = logging.StreamHandler()
    _console_handler.setFormatter(_formatter)
    log.addHandler(_console_handler)


def _find_dev_dir():
    if getattr(sys, 'frozen', False):
        d = os.path.dirname(os.path.abspath(sys.executable))
        for _ in range(5):
            if os.path.isfile(os.path.join(d, ".yunji.lock")) or os.path.isdir(os.path.join(d, "app")):
                return d
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_base_dir():
    return _find_dev_dir()


def get_app_dir():
    d = os.path.join(get_base_dir(), "app")
    os.makedirs(d, exist_ok=True)
    return d


def find_quick_dir():
    base_dir = get_base_dir()

    builtin_quick = os.path.join(get_app_dir(), "Quick")
    if os.path.isdir(builtin_quick) and os.path.isfile(os.path.join(builtin_quick, "quick.exe")):
        return builtin_quick

    saved = load_settings().get("quick_dir_path", "")
    if saved and os.path.isdir(saved) and os.path.isfile(os.path.join(saved, "quick.exe")):
        return saved

    search_dirs = [base_dir, os.path.dirname(base_dir)]
    parent = os.path.dirname(base_dir)
    if parent:
        grandparent = os.path.dirname(parent)
        if grandparent and grandparent != parent:
            search_dirs.append(grandparent)

    for search in search_dirs:
        if not search or not os.path.isdir(search):
            continue
        for pattern in ["*Quick*", "*quick*", "*Quick"]:
            for d in glob.glob(os.path.join(search, pattern)):
                if os.path.isdir(d) and os.path.isfile(os.path.join(d, "quick.exe")):
                    return d
        for root, dirs, files in os.walk(search):
            depth = root.replace(search, "").count(os.sep)
            if depth > 2:
                continue
            if "quick.exe" in [f.lower() for f in files]:
                return root
            for d in dirs:
                if d.lower() == "quick":
                    qd = os.path.join(root, d)
                    if os.path.isfile(os.path.join(qd, "quick.exe")):
                        return qd

    return None


def find_system_browsers():
    browsers = []
    paths = [
        ("Chrome", os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe")),
        ("Chrome (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe")),
        ("Chrome User", os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")),
        ("Edge", os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")),
        ("Edge (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")),
        ("Firefox", os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe")),
        ("Firefox (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe")),
        ("360安全浏览器", os.path.expandvars(r"%ProgramFiles%\360\360se6\Application\360se.exe")),
        ("360安全浏览器 (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\360\360se6\Application\360se.exe")),
        ("360安全浏览器 User", os.path.expandvars(r"%LocalAppData%\360\360se6\Application\360se.exe")),
        ("360极速浏览器", os.path.expandvars(r"%ProgramFiles%\360\360chrome\Chrome\Application\360chrome.exe")),
        ("360极速浏览器 (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\360\360chrome\Chrome\Application\360chrome.exe")),
        ("360极速浏览器 User", os.path.expandvars(r"%LocalAppData%\360\360chrome\Chrome\Application\360chrome.exe")),
        ("QQ浏览器", os.path.expandvars(r"%ProgramFiles%\Tencent\QQBrowser\QQBrowser.exe")),
        ("QQ浏览器 (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\Tencent\QQBrowser\QQBrowser.exe")),
        ("搜狗浏览器", os.path.expandvars(r"%ProgramFiles%\SogouExplorer\SogouExplorer.exe")),
        ("搜狗浏览器 (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\SogouExplorer\SogouExplorer.exe")),
        ("遨游浏览器", os.path.expandvars(r"%ProgramFiles%\Maxthon5\Bin\Maxthon.exe")),
        ("遨游浏览器 (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\Maxthon5\Bin\Maxthon.exe")),
        ("星愿浏览器", os.path.expandvars(r"%LocalAppData%\Twinkstar Browser\Application\twinkstar.exe")),
        ("Vivaldi", os.path.expandvars(r"%LocalAppData%\Vivaldi\Application\vivaldi.exe")),
        ("Brave", os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe")),
        ("Opera", os.path.expandvars(r"%LocalAppData%\Programs\Opera\launcher.exe")),
        ("Opera GX", os.path.expandvars(r"%LocalAppData%\Programs\Opera GX\launcher.exe")),
        ("Yandex", os.path.expandvars(r"%LocalAppData%\Yandex\YandexBrowser\Application\browser.exe")),
        ("Waterfox", os.path.expandvars(r"%ProgramFiles%\Waterfox\waterfox.exe")),
        ("Thorium", os.path.expandvars(r"%LocalAppData%\Thorium\Application\thorium.exe")),
    ]

    def _reg_enum_browsers(hive, hive_name):
        results = []
        for root_key in [
            r"SOFTWARE\Clients\StartMenuInternet",
            r"SOFTWARE\WOW6432Node\Clients\StartMenuInternet",
        ]:
            try:
                key = winreg.OpenKey(hive, root_key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        i += 1
                        try:
                            sk = winreg.OpenKey(key, fr"{subkey_name}\shell\open\command")
                            cmd, _ = winreg.QueryValueEx(sk, "")
                            winreg.CloseKey(sk)
                            if cmd:
                                exe_path = cmd.strip('"').split('"')[0] if '"' in cmd else cmd.split()[0]
                                if os.path.isfile(exe_path):
                                    results.append((subkey_name, exe_path))
                        except Exception:
                            pass
                    except Exception:
                        break
                winreg.CloseKey(key)
            except Exception:
                pass
        return results

    browsers.extend(_reg_enum_browsers(winreg.HKEY_LOCAL_MACHINE, "HKLM"))
    browsers.extend(_reg_enum_browsers(winreg.HKEY_CURRENT_USER, "HKCU"))

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                i += 1
                if not subkey_name.lower().endswith(".exe"):
                    continue
                try:
                    sk = winreg.OpenKey(key, subkey_name)
                    path_val, _ = winreg.QueryValueEx(sk, "")
                    winreg.CloseKey(sk)
                    if path_val:
                        exe_path = path_val.strip('"').split('"')[0] if '"' in path_val else path_val.split()[0]
                        if os.path.isfile(exe_path):
                            browser_name = subkey_name.replace(".exe", "")
                            browsers.append((browser_name, exe_path))
                except Exception:
                    pass
            except Exception:
                break
        winreg.CloseKey(key)
    except Exception:
        pass

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths", 0, winreg.KEY_READ)
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                i += 1
                if not subkey_name.lower().endswith(".exe"):
                    continue
                try:
                    sk = winreg.OpenKey(key, subkey_name)
                    path_val, _ = winreg.QueryValueEx(sk, "")
                    winreg.CloseKey(sk)
                    if path_val:
                        exe_path = path_val.strip('"').split('"')[0] if '"' in path_val else path_val.split()[0]
                        if os.path.isfile(exe_path):
                            browser_name = subkey_name.replace(".exe", "")
                            browsers.append((browser_name, exe_path))
                except Exception:
                    pass
            except Exception:
                break
        winreg.CloseKey(key)
    except Exception:
        pass

    _browser_keywords = {
        "chrome", "chromium", "firefox", "edge", "msedge", "opera",
        "vivaldi", "brave", "yandex", "safari", "maxthon", "thorium",
        "waterfox", "palemoon", "iron", "slimjet", "comodo", "dragon",
        "avast", "secure", "epic", "tor", "falkon", "midori", "qutebrowser",
        "360se", "360chrome", "360chromex", "qqbrowser", "sogou",
        "twinkstar", "quark", "doubao", "liebao", "ucbrowser", "uc",
        "world", "avant", "green", "coolnovo", "baidu", "sogouexplorer",
        "se", "theworld", "2345explorer", "hao123", "miui", "huohou",
        "browser", "navigator",
    }

    _exclude_keywords = {
        "devenv", "game", "update", "setup", "install", "uninstall",
        "helper", "service", "crash", "reporter", "notification",
        "360game", "360safe", "360sd", "360tray", "360leakfixer",
        "zhudongfangyu", "software", "manager", "guard", "protect",
        "plugin", "extension", "addon",
    }

    def _is_browser(name, path):
        name_lower = name.lower()
        path_lower = path.lower()
        for ek in _exclude_keywords:
            if ek in name_lower or ek in os.path.basename(path_lower):
                return False
        for bk in _browser_keywords:
            if bk in name_lower or bk in os.path.basename(path_lower):
                return True
        return False

    seen = set()
    unique = []
    for name, path in browsers + paths:
        if path not in seen and os.path.isfile(path) and _is_browser(name, path):
            seen.add(path)
            unique.append((name, path))
    return unique


def is_proxy_running():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex((PROXY_HOST, PROXY_PORT))
        sock.close()
        return result == 0
    except Exception:
        return False


def wait_for_proxy(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        if is_proxy_running():
            return True
        time.sleep(0.5)
    return False


def verify_proxy_connection(timeout=10):
    try:
        proxy_handler = urllib.request.ProxyHandler({
            'http': f'http://{PROXY_URL}',
            'https': f'http://{PROXY_URL}',
        })
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(NODE_TEST_URL, headers={"User-Agent": "Mozilla/5.0"})
        start = time.time()
        resp = opener.open(req, timeout=timeout)
        elapsed = time.time() - start
        return resp.status == 204, elapsed
    except Exception as e:
        log.warning(f"代理连接验证失败: {e}")
        return False, None


def test_direct_latency(timeout=NODE_TEST_TIMEOUT):
    try:
        start = time.time()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(NODE_TEST_URL, headers={"User-Agent": "Mozilla/5.0"})
        urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return time.time() - start
    except Exception:
        return float('inf')


def download_config(url, timeout=NODE_TEST_TIMEOUT):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read()


def download_all_configs():
    results = []
    lock = threading.Lock()

    def try_download(name, primary_url, fallback_url):
        config_data = None
        for url in [primary_url, fallback_url]:
            try:
                config_data = download_config(url)
                log.info(f"{name} 配置下载成功 ({url})")
                break
            except Exception as e:
                log.warning(f"{name} 配置下载失败 ({url}): {e}")
                continue
        with lock:
            results.append((name, config_data))

    threads = []
    for name, primary_url, fallback_url in CONFIG_URLS:
        t = threading.Thread(target=try_download, args=(name, primary_url, fallback_url))
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=NODE_TEST_TIMEOUT + 5)
    return [(n, d) for n, d in results if d is not None]


def save_config(quick_dir, config_data):
    config_path = os.path.join(quick_dir, "config.yaml")
    backup_path = os.path.join(quick_dir, "config.yaml_backup")
    if os.path.isfile(config_path):
        if os.path.isfile(backup_path):
            os.remove(backup_path)
        shutil.copy2(config_path, backup_path)
    with open(config_path, 'wb') as f:
        f.write(config_data)
    log.info(f"配置已保存到 {config_path}")


def start_quick(quick_dir):
    quick_exe = os.path.join(quick_dir, "quick.exe")
    if not os.path.isfile(quick_exe):
        log.error(f"quick.exe 不存在: {quick_exe}")
        return False
    config_path = os.path.join(quick_dir, "config.yaml")
    if not os.path.isfile(config_path):
        log.error(f"config.yaml 不存在: {config_path}")
        return False
    log.info(f"配置文件大小: {os.path.getsize(config_path)} bytes")
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    subprocess.Popen(
        [quick_exe, "-d", quick_dir],
        cwd=quick_dir,
        startupinfo=si,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    log.info(f"已启动代理内核: {quick_exe}")
    return True


def stop_quick():
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        subprocess.run(
            ["taskkill", "/f", "/im", "quick.exe"],
            capture_output=True,
            startupinfo=si,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        log.info("已停止代理内核")
    except Exception as e:
        log.error(f"停止代理内核失败: {e}")


def _detect_browser_type(exe_path):
    name = os.path.basename(exe_path).lower()
    firefox_names = {"firefox.exe"}
    chromium_names = {
        "chrome.exe", "msedge.exe", "brave.exe", "vivaldi.exe",
        "opera.exe", "dragon.exe", "iridium.exe", "slimjet.exe",
        "360chrome.exe", "360chromex.exe", "chromium.exe",
        "maxthon.exe", "avastbrowser.exe", "avsecurebrowser.exe",
        "qqbrowser.exe", "sogouexplorer.exe", "twinkstar.exe",
        "yandex.exe", "browser.exe",
    }
    if name in firefox_names:
        return "firefox"
    if name in chromium_names:
        return "chromium"
    if "firefox" in name:
        return "firefox"
    if any(k in name for k in ("chrome", "chromium", "edge", "brave", "opera", "vivaldi", "360", "qqbrowser", "sogou", "twinkstar", "yandex", "maxthon", "dragon")):
        return "chromium"
    return "unknown"


def _create_firefox_proxy_profile(proxy_host, proxy_port):
    tmp_dir = tempfile.mkdtemp(prefix="yunji_ff_proxy_")
    user_js = os.path.join(tmp_dir, "user.js")
    with open(user_js, "w", encoding="utf-8") as f:
        f.write(f'user_pref("network.proxy.type", 1);\n')
        f.write(f'user_pref("network.proxy.http", "{proxy_host}");\n')
        f.write(f'user_pref("network.proxy.http_port", {proxy_port});\n')
        f.write(f'user_pref("network.proxy.ssl", "{proxy_host}");\n')
        f.write(f'user_pref("network.proxy.ssl_port", {proxy_port});\n')
        f.write(f'user_pref("network.proxy.socks", "{proxy_host}");\n')
        f.write(f'user_pref("network.proxy.socks_port", {proxy_port});\n')
        f.write(f'user_pref("network.proxy.socks_version", 5);\n')
        f.write(f'user_pref("network.proxy.no_proxies_on", "localhost, 127.0.0.1, ::1");\n')
        f.write(f'user_pref("network.proxy.share_proxy_settings", true);\n')
    return tmp_dir


def _is_browser_running(exe_path):
    exe_name = os.path.basename(exe_path).lower()
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return exe_name in result.stdout.lower()
    except Exception:
        return False


def _kill_browser(exe_path):
    exe_name = os.path.basename(exe_path)
    try:
        subprocess.run(["taskkill", "/F", "/IM", exe_name], capture_output=True, timeout=10)
        time.sleep(1)
        return True
    except Exception as e:
        log.error(f"关闭浏览器失败: {e}")
        return False


def start_browser(exe_path, args=None):
    if not os.path.isfile(exe_path):
        log.error(f"浏览器不存在: {exe_path}")
        return False
    browser_type = _detect_browser_type(exe_path)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 1
    if browser_type == "chromium":
        cmd_args = [exe_path, f"--proxy-server=http://{PROXY_URL}"]
        if args:
            cmd_args.extend(args)
        subprocess.Popen(cmd_args, startupinfo=si)
        log.info(f"已启动浏览器(Chromium模式): {exe_path}")
    elif browser_type == "firefox":
        profile_dir = _create_firefox_proxy_profile(PROXY_HOST, PROXY_PORT)
        cmd_args = [exe_path, "-profile", profile_dir, "-no-remote"]
        if args:
            cmd_args.extend(args)
        subprocess.Popen(cmd_args, startupinfo=si)
        log.info(f"已启动浏览器(Firefox模式, 代理配置文件: {profile_dir}): {exe_path}")
    else:
        cmd_args = [exe_path, f"--proxy-server=http://{PROXY_URL}"]
        if args:
            cmd_args.extend(args)
        subprocess.Popen(cmd_args, startupinfo=si)
        log.info(f"已启动浏览器(未知类型,尝试Chromium模式): {exe_path}")
    return True


def set_system_proxy(enable):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                             0, winreg.KEY_SET_VALUE)
        if enable:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, PROXY_URL)
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ,
                              "<local>;localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;172.26.*;172.27.*;172.28.*;172.29.*;172.30.*;172.31.*;192.168.*")
            log.info(f"已开启系统代理: {PROXY_URL}")
        else:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            log.info("已关闭系统代理")
        winreg.CloseKey(key)
        INTERNET_OPTION_SETTINGS_CHANGED = 39
        INTERNET_OPTION_REFRESH = 37
        ctypes.windll.wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        ctypes.windll.wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Internet Settings",
            0x0002, 5000, None
        )
        return True
    except Exception as e:
        log.error(f"设置系统代理失败: {e}")
        return False


def get_system_proxy():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                             0, winreg.KEY_READ)
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        server, _ = winreg.QueryValueEx(key, "ProxyServer")
        winreg.CloseKey(key)
        return bool(enabled), str(server) if server else ""
    except Exception:
        return False, ""


def load_settings():
    path = os.path.join(get_app_dir(), "launcher_settings.json")
    defaults = {
        "auto_start": True,
        "auto_open_browser": True,
        "global_proxy": False,
        "custom_apps_enabled": False,
        "custom_apps": [],
        "browser_path": "",
        "browser_type": "system",
        "system_browser_path": "",
        "quick_dir_path": "",
        "auto_line_switch": False,
        "auto_line_interval": 30,
        "realtime_detect": False,
        "browser_proxy_mode": "all",
        "current_line": "",
        "proxy_enabled": False,
        "proxy_host": "127.0.0.1",
        "proxy_port": 7890,
        "last_config_update_date": "",
    }
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_settings(settings):
    path = os.path.join(get_app_dir(), "launcher_settings.json")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class ProxyMonitor(QThread):
    status_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        last = None
        while self._running:
            current = is_proxy_running()
            if current != last:
                self.status_changed.emit(current)
                last = current
            time.sleep(3)

    def stop(self):
        self._running = False


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str, str)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=60, context=ctx)
            total = int(resp.headers.get("Content-Length", 0))
            tmp_path = self.save_path + ".downloading"
            downloaded = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    self.progress.emit(downloaded, total)
            resp.close()
            if os.path.isfile(self.save_path):
                os.remove(self.save_path)
            os.rename(tmp_path, self.save_path)
            self.finished.emit(True, "下载完成", self.save_path)
        except Exception as e:
            tmp_path = self.save_path + ".downloading"
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
            self.finished.emit(False, f"下载失败: {e}", "")


class KernelUpdateWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    MIRROR_PREFIXES = [
        "",
        "https://mirror.ghproxy.com/",
        "https://gh-proxy.com/",
        "https://ghfast.top/",
    ]

    def __init__(self, quick_dir):
        super().__init__()
        self.quick_dir = quick_dir

    def _fetch_json(self, url, timeout=15):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _download_file(self, url, save_path, timeout=120):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(save_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(downloaded * 100 / total)
                        self.progress.emit(f"正在下载 {pct}% ({downloaded // 1024 // 1024}/{total // 1024 // 1024} MB)")

    def _find_asset(self, release):
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if "windows-amd64-v3" in name and name.endswith(".zip") and "compatible" not in name:
                return asset.get("name", ""), asset.get("browser_download_url", "")
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if "windows-amd64" in name and name.endswith(".zip") and "compatible" not in name and "go12" not in name:
                return asset.get("name", ""), asset.get("browser_download_url", "")
        return None, None

    def run(self):
        try:
            self.progress.emit("正在获取最新版本信息...")

            release = None
            api_url = f"https://api.github.com/repos/{MIHOMO_REPO}/releases/latest"
            for prefix in self.MIRROR_PREFIXES:
                try:
                    url = prefix + api_url if prefix else api_url
                    self.progress.emit(f"尝试连接{'加速镜像' if prefix else 'GitHub'}...")
                    release = self._fetch_json(url, timeout=10)
                    if release and release.get("tag_name"):
                        break
                    release = None
                except Exception:
                    release = None
                    continue

            if not release:
                self.finished.emit(False, "所有源均连接不上，请开启全局系统代理后再尝试")
                return

            latest_tag = release.get("tag_name", "")
            asset_name, github_url = self._find_asset(release)
            if not github_url:
                self.finished.emit(False, "未找到适合的 Windows 内核文件")
                return

            current_exe = os.path.join(self.quick_dir, "quick.exe")
            tmp_dir = tempfile.mkdtemp(prefix="mihomo_update_")
            zip_path = os.path.join(tmp_dir, asset_name)

            self.progress.emit(f"正在下载 mihomo {latest_tag}...")
            downloaded = False
            for prefix in self.MIRROR_PREFIXES:
                try:
                    url = prefix + github_url if prefix else github_url
                    self._download_file(url, zip_path)
                    if os.path.isfile(zip_path) and os.path.getsize(zip_path) > 1000:
                        downloaded = True
                        break
                    else:
                        if os.path.isfile(zip_path):
                            os.remove(zip_path)
                except Exception:
                    if os.path.isfile(zip_path):
                        os.remove(zip_path)
                    continue

            if not downloaded:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                self.finished.emit(False, "所有源均连接不上，请开启全局系统代理后再尝试")
                return

            self.progress.emit("正在解压...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                exe_name = None
                for name in zf.namelist():
                    if name.endswith(".exe"):
                        exe_name = name
                        break
                if not exe_name:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    self.finished.emit(False, "压缩包中未找到可执行文件")
                    return
                zf.extract(exe_name, tmp_dir)
                new_exe = os.path.join(tmp_dir, exe_name)

            self.progress.emit("正在替换内核文件...")
            backup_path = current_exe + ".bak"
            if os.path.isfile(backup_path):
                os.remove(backup_path)
            if os.path.isfile(current_exe):
                os.rename(current_exe, backup_path)
            shutil.move(new_exe, current_exe)

            try:
                os.remove(backup_path)
            except Exception:
                pass

            shutil.rmtree(tmp_dir, ignore_errors=True)
            self.finished.emit(True, f"内核已更新至 mihomo {latest_tag}")

        except Exception as e:
            self.finished.emit(False, f"更新失败: {e}")


class ServiceWorker(QThread):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    line_tested = pyqtSignal(str, float, bool)
    line_selected = pyqtSignal(str)

    def __init__(self, action, **kwargs):
        super().__init__()
        self.action = action
        self.kwargs = kwargs

    def run(self):
        try:
            getattr(self, f"_do_{self.action}", lambda: None)()
        except Exception as e:
            log.error(f"任务异常: {e}")
            self.finished.emit(False, str(e))

    def _do_start(self):
        quick_dir = self.kwargs.get("quick_dir")
        if is_proxy_running():
            self.finished.emit(True, "代理已在运行")
            return
        self.progress.emit("正在获取线路配置...")
        log.info("开始启动代理服务")
        downloaded = download_all_configs()
        if downloaded:
            saved_line = self.kwargs.get("current_line")
            selected = None
            if saved_line:
                for name, data in downloaded:
                    if name == saved_line:
                        selected = (name, data)
                        break
            if not selected:
                selected = downloaded[0]
            save_config(quick_dir, selected[1])
            self.line_selected.emit(selected[0])
            self.progress.emit(f"已选择: {selected[0]}")
            log.info(f"启动线路: {selected[0]}, 配置大小: {len(selected[1])} bytes")
        else:
            if not os.path.isfile(os.path.join(quick_dir, "config.yaml")):
                self.finished.emit(False, "无可用配置")
                return
            log.warning("未下载到新配置，使用本地已有配置")
        self.progress.emit("正在启动代理内核...")
        start_quick(quick_dir)
        if not wait_for_proxy(timeout=15):
            self.finished.emit(False, "代理内核启动失败")
            return
        log.info("代理内核已启动，正在验证连接...")
        connected, latency = verify_proxy_connection(timeout=10)
        lat_str = f"{latency:.1f}s" if latency else "未知"
        if connected:
            log.info(f"代理连接验证成功, 延迟: {lat_str}")
        else:
            log.warning(f"代理连接验证失败 (内核已启动但无法通过代理访问外网)")
        self.finished.emit(True, f"代理已启动 (延迟: {lat_str})")

    def _do_test_lines(self):
        self.progress.emit("正在下载配置文件...")
        downloaded = download_all_configs()
        if not downloaded:
            self.finished.emit(False, "无法下载配置")
            return

        quick_dir = self.kwargs.get("quick_dir")
        if not quick_dir:
            self.finished.emit(False, "未找到内核目录")
            return

        original_config = None
        config_path = os.path.join(quick_dir, "config.yaml")
        if os.path.isfile(config_path):
            with open(config_path, 'rb') as f:
                original_config = f.read()

        results = []
        total = len(downloaded)

        for i, (name, data) in enumerate(downloaded):
            self.progress.emit(f"正在检测线路 {i+1}/{total}: {name}...")
            save_config(quick_dir, data)

            if is_proxy_running():
                stop_quick()
                time.sleep(1)

            start_quick(quick_dir)
            if not wait_for_proxy(timeout=8):
                results.append((name, -1.0, -1.0, 0, data))
                self.line_tested.emit(name, -1.0, False)
                continue

            latencies = []
            for _, test_url in NODE_TEST_URLS:
                try:
                    proxy_handler = urllib.request.ProxyHandler({
                        'http': f'http://{PROXY_URL}',
                        'https': f'http://{PROXY_URL}',
                    })
                    opener = urllib.request.build_opener(proxy_handler)
                    req = urllib.request.Request(test_url, headers={"User-Agent": "Mozilla/5.0"})
                    start = time.time()
                    resp = opener.open(req, timeout=NODE_TEST_TIMEOUT)
                    elapsed = time.time() - start
                    if resp.status in (200, 204):
                        latencies.append(elapsed)
                except Exception:
                    pass

            if latencies:
                avg = sum(latencies) / len(latencies)
                best = min(latencies)
                results.append((name, avg, best, len(latencies), data))
                self.line_tested.emit(name, avg, True)
            else:
                results.append((name, -1.0, -1.0, 0, data))
                self.line_tested.emit(name, -1.0, False)

        proxy_enabled = self.kwargs.get("proxy_enabled", False)
        current_line = self.kwargs.get("current_line", "")
        if proxy_enabled:
            restore_data = original_config
            if current_line:
                for n, d in downloaded:
                    if n == current_line:
                        restore_data = d
                        break
            if restore_data:
                with open(config_path, 'wb') as f:
                    f.write(restore_data)
            if is_proxy_running():
                stop_quick()
                time.sleep(1)
            start_quick(quick_dir)
            wait_for_proxy(timeout=8)
        else:
            stop_quick()
            if original_config:
                with open(config_path, 'wb') as f:
                    f.write(original_config)

        self.kwargs["results"] = results
        self.finished.emit(True, "检测完成")

    def _do_auto_select(self):
        self.progress.emit("正在下载配置文件...")
        downloaded = download_all_configs()
        if not downloaded:
            self.finished.emit(False, "无法下载配置")
            return
        quick_dir = self.kwargs.get("quick_dir")
        if not quick_dir:
            self.finished.emit(False, "未找到内核目录")
            return

        original_config = None
        config_path = os.path.join(quick_dir, "config.yaml")
        if os.path.isfile(config_path):
            with open(config_path, 'rb') as f:
                original_config = f.read()

        fastest_name, fastest_data, fastest_time = None, None, float('inf')
        for name, data in downloaded:
            self.progress.emit(f"正在测试 {name}...")
            save_config(quick_dir, data)

            if is_proxy_running():
                stop_quick()
                time.sleep(1)

            start_quick(quick_dir)
            if not wait_for_proxy(timeout=8):
                continue

            try:
                proxy_handler = urllib.request.ProxyHandler({
                    'http': f'http://{PROXY_URL}',
                    'https': f'http://{PROXY_URL}',
                })
                opener = urllib.request.build_opener(proxy_handler)
                req = urllib.request.Request(NODE_TEST_URL, headers={"User-Agent": "Mozilla/5.0"})
                start = time.time()
                resp = opener.open(req, timeout=NODE_TEST_TIMEOUT)
                elapsed = time.time() - start
                if resp.status in (200, 204) and elapsed < fastest_time:
                    fastest_time = elapsed
                    fastest_name = name
                    fastest_data = data
            except Exception:
                pass

        proxy_enabled = self.kwargs.get("proxy_enabled", False)
        if proxy_enabled:
            if fastest_data:
                save_config(quick_dir, fastest_data)
            elif original_config:
                with open(config_path, 'wb') as f:
                    f.write(original_config)
            if is_proxy_running():
                stop_quick()
                time.sleep(1)
            start_quick(quick_dir)
            wait_for_proxy(timeout=8)
        else:
            stop_quick()
            if fastest_data:
                save_config(quick_dir, fastest_data)
            elif original_config:
                with open(config_path, 'wb') as f:
                    f.write(original_config)

        if fastest_data:
            self.line_selected.emit(fastest_name)
            self.finished.emit(True, f"已选择最快线路: {fastest_name}")
        else:
            self.finished.emit(False, "无可用线路")

    def _do_use_line(self):
        name = self.kwargs.get("name")
        data = self.kwargs.get("data")
        quick_dir = self.kwargs.get("quick_dir")
        proxy_enabled = self.kwargs.get("proxy_enabled", False)
        if data and quick_dir:
            save_config(quick_dir, data)
            if is_proxy_running():
                self.progress.emit(f"正在切换到 {name}...")
                stop_quick()
                time.sleep(2)
                start_quick(quick_dir)
                if wait_for_proxy(timeout=15):
                    self.finished.emit(True, f"已切换到 {name}")
                else:
                    self.finished.emit(False, "切换失败")
            elif proxy_enabled:
                self.progress.emit(f"正在连接 {name}...")
                start_quick(quick_dir)
                if wait_for_proxy(timeout=15):
                    self.finished.emit(True, f"已连接 {name}")
                else:
                    self.finished.emit(False, "连接失败")
            else:
                self.finished.emit(True, f"已选择 {name}，请启动服务")
        else:
            self.finished.emit(False, "无配置数据")

    def _do_update_config(self):
        self.progress.emit("正在下载最新配置...")
        downloaded = download_all_configs()
        if downloaded:
            quick_dir = self.kwargs.get("quick_dir")
            if quick_dir:
                saved_line = self.kwargs.get("current_line")
                selected = None
                if saved_line:
                    for name, data in downloaded:
                        if name == saved_line:
                            selected = (name, data)
                            break
                if not selected:
                    selected = downloaded[0]
                save_config(quick_dir, selected[1])
                if is_proxy_running():
                    stop_quick()
                    time.sleep(1)
                    start_quick(quick_dir)
                    wait_for_proxy(timeout=8)
                self.finished.emit(True, f"配置更新成功: {selected[0]}")
            else:
                self.finished.emit(False, "未找到内核目录")
        else:
            self.finished.emit(False, "无法下载配置")


class SplashScreen(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap(480, 300)
        pixmap.fill(QColor(COLOR_BG))
        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self._progress = 0.0
        self._message = "正在初始化..."
        self._icon_pixmap = None
        try:
            if hasattr(sys, '_MEIPASS'):
                base = sys._MEIPASS
            else:
                base = os.path.dirname(os.path.abspath(__file__))
            for name in ('icon.png', 'icon.ico'):
                p = os.path.join(base, name)
                if os.path.exists(p):
                    self._icon_pixmap = QPixmap(p)
                    if not self._icon_pixmap.isNull():
                        break
                    self._icon_pixmap = None
        except Exception:
            pass

    def _get_progress(self):
        return self._progress

    def _set_progress(self, val):
        self._progress = val
        self.repaint()

    progress = pyqtProperty(float, _get_progress, _set_progress)

    def set_progress(self, value, message=""):
        if message:
            self._message = message
        anim = QPropertyAnimation(self, b"progress")
        anim.setDuration(150)
        anim.setStartValue(self._progress)
        anim.setEndValue(value)
        anim.start()
        self._anim = anim
        if message:
            self._message = message
            self.repaint()

    def drawContents(self, painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(COLOR_BG))

        if self._icon_pixmap:
            icon_size = 64
            scaled = self._icon_pixmap.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((w - scaled.width()) // 2, 40, scaled)

        painter.setPen(QColor(COLOR_TEXT))
        painter.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title = "云集智能网联代理专家"
        fm = painter.fontMetrics()
        painter.drawText((w - fm.horizontalAdvance(title)) // 2, 150, title)

        bar_x, bar_y, bar_w, bar_h = 60, 200, w - 120, 6
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLOR_BORDER))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

        fill_w = bar_w * min(self._progress, 1.0)
        if fill_w > 0:
            grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            grad.setColorAt(0, QColor(COLOR_RED))
            grad.setColorAt(1, QColor(COLOR_RED_LIGHT))
            painter.setBrush(grad)
            painter.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 3, 3)

        painter.setPen(QColor(COLOR_DIM))
        painter.setFont(QFont("Microsoft YaHei", 9))
        fm2 = painter.fontMetrics()
        painter.drawText((w - fm2.horizontalAdvance(self._message)) // 2, 230, self._message)

        pct = f"{int(min(self._progress, 1.0) * 100)}%"
        painter.setPen(QColor(COLOR_RED_LIGHT))
        painter.setFont(QFont("Microsoft YaHei", 8))
        fm3 = painter.fontMetrics()
        painter.drawText((w - fm3.horizontalAdvance(pct)) // 2, 255, pct)


class _HelpBubble(QFrame):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            f"QFrame {{ background-color: #2a2a2a; border: 1px solid #555; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setStyleSheet("color: #EEEEEE; font-size: 9pt; background: transparent; border: none;")
        label.setMaximumWidth(320)
        label.setMinimumWidth(160)
        layout.addWidget(label)
        self.adjustSize()
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_at(self, anchor_widget):
        self.setParent(anchor_widget.window())
        pos = anchor_widget.mapTo(anchor_widget.window(), QPoint(0, 0))
        x = pos.x() + anchor_widget.width() + 4
        y = pos.y() - self.height() // 2 + anchor_widget.height() // 2
        win = anchor_widget.window()
        if x + self.width() > win.width() - 10:
            x = pos.x() - self.width() - 4
        if y < 10:
            y = 10
        if y + self.height() > win.height() - 10:
            y = win.height() - self.height() - 10
        self.move(x, y)
        self.show()

    def enterEvent(self, event):
        self._hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hide_timer.start(500)
        super().leaveEvent(event)


def _make_help_btn(tooltip, detail_title, detail_text):
    btn = QPushButton()
    btn.setFixedSize(22, 22)
    btn.setCursor(Qt.CursorShape.WhatsThisCursor)
    icon = btn.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
    btn.setIcon(icon)
    btn.setIconSize(QSize(18, 18))
    btn.setStyleSheet(
        f"QPushButton {{ background-color: transparent; border: none; }}"
        f"QPushButton:hover {{ background-color: rgba(255,255,255,30); border-radius: 11px; }}"
    )
    bubble = _HelpBubble(btn, detail_text)
    btn.clicked.connect(lambda: bubble.show_at(btn))
    btn._bubble = bubble
    btn._hover_timer = QTimer(btn)
    btn._hover_timer.setSingleShot(True)
    btn._hover_timer.timeout.connect(lambda: bubble.show_at(btn))
    def _on_enter(event):
        btn._hover_timer.start(600)
        if bubble.isVisible():
            bubble._hide_timer.stop()
        btn.setCursor(Qt.CursorShape.WhatsThisCursor)
        return QPushButton.enterEvent(btn, event)
    def _on_leave(event):
        btn._hover_timer.stop()
        if bubble.isVisible():
            bubble._hide_timer.start(500)
        return QPushButton.leaveEvent(btn, event)
    btn.enterEvent = _on_enter
    btn.leaveEvent = _on_leave
    return btn


class MainWindow(QMainWindow):
    _version_data_ready = pyqtSignal()

    def __init__(self, splash=None):
        super().__init__()
        self._splash = splash
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(560, 780)
        self.setStyleSheet(STYLESHEET)
        self.setAutoFillBackground(True)

        if self._splash:
            self._splash.set_progress(0.2, "正在加载配置...")

        self.settings = load_settings()
        self._version_data_ready.connect(self._on_version_data_ready)

        global PROXY_HOST, PROXY_PORT
        saved_host = self.settings.get("proxy_host", PROXY_HOST)
        saved_port = self.settings.get("proxy_port", PROXY_PORT)
        if saved_host:
            PROXY_HOST = saved_host
        if saved_port:
            PROXY_PORT = int(saved_port)
        _update_proxy_url()
        self.quick_dir = self._resolve_quick_dir()
        self.current_line = self.settings.get("current_line", "")
        self.line_results = {}
        self.worker = None
        self._auto_line_timer = None

        log.info(f"应用版本: {VERSION}")
        log.info(f"基础目录: {get_base_dir()}")
        log.info(f"Quick目录: {self.quick_dir}")

        if self._splash:
            self._splash.set_progress(0.4, "正在构建界面...")

        self._set_icon()
        self._build_ui()

        if self._splash:
            self._splash.set_progress(0.8, "正在初始化...")

        QTimer.singleShot(0, lambda: self._update_status(is_proxy_running()))
        self._update_kernel_status()
        self._update_active_line()

        self.switch_proxy.blockSignals(True)
        self.switch_proxy.setChecked(self.settings.get("proxy_enabled", False))
        self.switch_proxy.blockSignals(False)

        self.monitor = ProxyMonitor()
        self.monitor.status_changed.connect(self._update_status)
        self.monitor.status_changed.connect(lambda _: self._update_active_line())
        self.monitor.start()

        if self.settings.get("proxy_enabled", False) and self.settings.get("auto_start", True) and self.quick_dir:
            QTimer.singleShot(500, self._on_start)

        QTimer.singleShot(1000, self._startup_download_config)

        if self._splash:
            self._splash.set_progress(1.0, "加载完成！")
            QTimer.singleShot(200, self._finish_splash)

    def _resolve_quick_dir(self):
        builtin = os.path.join(get_app_dir(), "Quick")
        if os.path.isdir(builtin) and os.path.isfile(os.path.join(builtin, "quick.exe")):
            log.info(f"使用内置内核路径: {builtin}")
            return builtin

        saved = self.settings.get("quick_dir_path", "")
        if saved and os.path.isfile(os.path.join(saved, "quick.exe")):
            log.info(f"使用保存的内核路径: {saved}")
            return saved

        auto = find_quick_dir()
        if auto:
            self.settings["quick_dir_path"] = auto
            save_settings(self.settings)
            log.info(f"自动检测到内核路径: {auto}")
            return auto

        log.warning("未找到代理内核，请手动选择内核目录")
        return None

    def _set_icon(self):
        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.isfile(ico_path):
            self.setWindowIcon(QIcon(ico_path))

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_tabs(), stretch=1)

    def _build_tabs(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(8, 8, 8, 4)
        nav_bar.setSpacing(6)

        self.nav_buttons = []
        nav_items = [
            ("🚀 线路服务", 0),
            ("⚙️ 代理设置", 1),
            ("📋 运行日志", 2),
            ("🔄 软件更新", 3),
        ]
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("nav-btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._on_nav_clicked(i))
            nav_bar.addWidget(btn, stretch=1)
            self.nav_buttons.append(btn)
        self.nav_buttons[0].setChecked(True)

        layout.addLayout(nav_bar)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_service_tab())
        self.stack.addWidget(self._build_proxy_tab())
        self.stack.addWidget(self._build_log_tab())
        self.stack.addWidget(self._build_update_tab())
        layout.addWidget(self.stack, stretch=1)

        return container

    def _on_nav_clicked(self, idx):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)
        self.stack.setCurrentIndex(idx)

    def _build_service_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        status_card = QFrame()
        status_card.setObjectName("card")
        sc = QVBoxLayout(status_card)
        sc.setContentsMargins(16, 14, 16, 14)
        sc.setSpacing(8)

        status_top = QHBoxLayout()
        status_top.setSpacing(10)

        self.svc_status_dot = QLabel("●")
        self.svc_status_dot.setStyleSheet(f"font-size: 18px; color: #FF6B80;")
        self.svc_status_dot.setFixedSize(24, 24)
        self.svc_status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_top.addWidget(self.svc_status_dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.svc_status_label = QLabel("代理未启动")
        self.svc_status_label.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {COLOR_TEXT};")
        status_top.addWidget(self.svc_status_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.svc_detail_label = QLabel("开启代理服务以访问外网")
        self.svc_detail_label.setObjectName("dim")
        self.svc_detail_label.setStyleSheet("font-size: 7pt;")
        status_top.addWidget(self.svc_detail_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        status_top.addStretch()

        self.switch_proxy = ToggleSwitch("代理服务", default=False)
        self.switch_proxy.setFixedWidth(140)
        self.switch_proxy.toggled.connect(self._on_proxy_switch_toggled)
        status_top.addWidget(self.switch_proxy, alignment=Qt.AlignmentFlag.AlignVCenter)

        sc.addLayout(status_top)

        proxy_addr_row = QHBoxLayout()
        proxy_addr_row.setSpacing(6)
        proxy_addr_label = QLabel("本地代理:")
        proxy_addr_label.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        proxy_addr_row.addWidget(proxy_addr_label)

        self.proxy_help_btn = _make_help_btn(
            "本地代理地址和端口设置",
            "本地代理说明",
            "【代理地址】\n"
            "本地代理监听的IP地址，默认为 127.0.0.1（仅本机访问）。\n"
            "如需局域网内其他设备使用代理，可改为 0.0.0.0。\n\n"
            "【代理端口】\n"
            "本地代理监听的端口号，默认为 7890。\n"
            "如端口被占用，可修改为其他端口（1-65535）。\n\n"
            "【修改说明】\n"
            "点击「修改」按钮进入编辑模式，修改后点击「确认」生效。\n"
            "若代理服务正在运行，确认后将自动重启服务以应用新配置。\n"
            "点击「取消」可放弃修改并恢复原值。"
        )
        proxy_addr_row.addWidget(self.proxy_help_btn)

        self.proxy_host_input = QLineEdit(PROXY_HOST)
        self.proxy_host_input.setFixedWidth(110)
        self.proxy_host_input.setReadOnly(True)
        self.proxy_host_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 4px; padding: 2px 6px; color: {COLOR_TEXT}; font-size: 9pt; font-family: Consolas; }}"
            f"QLineEdit[readOnly=\"true\"] {{ background-color: #0a0a0a; color: #888; }}"
        )
        proxy_addr_row.addWidget(self.proxy_host_input)

        colon_label = QLabel(":")
        colon_label.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {COLOR_TEXT};")
        proxy_addr_row.addWidget(colon_label)

        self.proxy_port_input = QLineEdit(str(PROXY_PORT))
        self.proxy_port_input.setFixedWidth(70)
        self.proxy_port_input.setReadOnly(True)
        self.proxy_port_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 4px; padding: 2px 6px; color: {COLOR_TEXT}; font-size: 9pt; font-family: Consolas; }}"
            f"QLineEdit[readOnly=\"true\"] {{ background-color: #0a0a0a; color: #888; }}"
        )
        proxy_addr_row.addWidget(self.proxy_port_input)

        self._proxy_editing = False

        self.btn_edit_proxy = QPushButton("修改")
        self.btn_edit_proxy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit_proxy.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 2px 10px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        self.btn_edit_proxy.clicked.connect(self._on_proxy_edit_toggle)
        proxy_addr_row.addWidget(self.btn_edit_proxy)

        self.btn_copy_proxy = QPushButton("复制")
        self.btn_copy_proxy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_proxy.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 2px 10px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        self.btn_copy_proxy.clicked.connect(self._on_copy_proxy_addr)
        proxy_addr_row.addWidget(self.btn_copy_proxy)

        proxy_addr_row.addStretch()
        sc.addLayout(proxy_addr_row)

        status_info = QFrame()
        status_info.setStyleSheet(f"background-color: #111; border: 1px solid #1a1a1a; border-radius: 4px;")
        si_layout = QHBoxLayout(status_info)
        si_layout.setContentsMargins(12, 6, 12, 6)
        si_layout.setSpacing(16)

        self.svc_latency_label = QLabel("延迟: --")
        self.svc_latency_label.setObjectName("latency")
        self.svc_latency_label.setStyleSheet("font-size: 8pt;")
        si_layout.addWidget(self.svc_latency_label)

        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #333; font-size: 8pt;")
        si_layout.addWidget(sep1)

        self.svc_line_label = QLabel("线路: --")
        self.svc_line_label.setObjectName("dim")
        self.svc_line_label.setStyleSheet("font-size: 8pt;")
        si_layout.addWidget(self.svc_line_label)

        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #333; font-size: 8pt;")
        si_layout.addWidget(sep2)

        self.svc_kernel_label = QLabel(f"内核: {self._get_quick_version() or '未知'}")
        self.svc_kernel_label.setObjectName("dim")
        self.svc_kernel_label.setStyleSheet("font-size: 8pt;")
        si_layout.addWidget(self.svc_kernel_label)

        si_layout.addStretch()

        self.btn_test = QPushButton("🔍 检测线路")
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.setFixedSize(90, 26)
        self.btn_test.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
            f"QPushButton:disabled {{ background-color: #333; color: #666; }}"
        )
        self.btn_test.clicked.connect(self._on_test_lines)
        si_layout.addWidget(self.btn_test, alignment=Qt.AlignmentFlag.AlignVCenter)

        sc.addWidget(status_info)

        layout.addWidget(status_card)

        line_card = QFrame()
        line_card.setObjectName("card")
        lc = QVBoxLayout(line_card)
        lc.setContentsMargins(20, 14, 20, 14)
        lc.setSpacing(6)

        line_header = QHBoxLayout()
        line_title = QLabel("线路列表")
        line_title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        line_header.addWidget(line_title)
        line_header.addWidget(_make_help_btn(
            "可用代理线路列表",
            "线路列表说明",
            "【线路列表】\n"
            "显示所有可用的代理线路，每条线路可独立检测和使用。\n\n"
            "【检测线路】\n"
            "点击「检测线路」按钮，程序会自动先更新线路配置，\n"
            "然后测试所有线路的连通性和延迟，结果显示在每条线路旁边。\n"
            "每天仅自动更新一次配置，当天已更新过则直接检测。\n\n"
            "【使用线路】\n"
            "点击「使用」按钮切换到该线路，代理服务将自动重连。\n\n"
            "【手动更新配置】\n"
            "如需强制更新线路配置，请在「代理设置→更新管理」中\n"
            "点击「更新线路配置」按钮。"
        ))
        line_header.addStretch()
        lc.addLayout(line_header)

        self.line_rows = {}
        for name, _, _ in CONFIG_URLS:
            row = QFrame()
            row.setObjectName("line-row")
            rh = QHBoxLayout(row)
            rh.setContentsMargins(14, 10, 14, 10)
            rh.setSpacing(12)
            name_lbl = QLabel(name)
            name_lbl.setObjectName("suggestion")
            name_lbl.setFixedWidth(50)
            name_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
            rh.addWidget(name_lbl)
            status_lbl = QLabel("未检测")
            status_lbl.setObjectName("dim")
            status_lbl.setWordWrap(True)
            status_lbl.setStyleSheet("font-size: 9pt;")
            rh.addWidget(status_lbl, stretch=1)
            use_btn = QPushButton("使用")
            use_btn.setObjectName("small-blue")
            use_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            use_btn.setFixedWidth(70)
            use_btn.clicked.connect(lambda checked, n=name: self._on_use_line(n))
            rh.addWidget(use_btn)
            lc.addWidget(row)
            self.line_rows[name] = {"status": status_lbl, "use_btn": use_btn, "data": None, "row": row}

        layout.addWidget(line_card)

        smart_card = QFrame()
        smart_card.setObjectName("card")
        sm = QVBoxLayout(smart_card)
        sm.setContentsMargins(20, 14, 20, 14)
        sm.setSpacing(8)

        smart_title = QLabel("智能线路")
        smart_title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        sm_layout_title = QHBoxLayout()
        sm_layout_title.setSpacing(4)
        sm_layout_title.addWidget(smart_title)
        sm_layout_title.addWidget(_make_help_btn(
            "智能线路管理",
            "智能线路说明",
            "【实时检测】\n"
            "开启后持续监测当前线路的连通性，一旦断线自动重连。\n"
            "适合需要长时间稳定连接的场景。\n\n"
            "【超时切换最快线路】\n"
            "按设定间隔定时检测所有线路延迟，自动切换到最快的线路。\n"
            "适合对速度有要求的场景。\n\n"
            "【检测间隔】\n"
            "设置自动检测的时间间隔，范围5-120分钟。"
        ))
        sm_layout_title.addStretch()
        sm.addLayout(sm_layout_title)

        realtime_row = QFrame()
        realtime_row.setObjectName("switch-row")
        rr = QHBoxLayout(realtime_row)
        rr.setContentsMargins(14, 8, 14, 8)
        realtime_info = QVBoxLayout()
        realtime_info.setSpacing(1)
        realtime_lbl = QLabel("📡 实时检测")
        realtime_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        realtime_info.addWidget(realtime_lbl)
        realtime_desc = QLabel("持续监测连通性，断线自动重连")
        realtime_desc.setObjectName("dim")
        realtime_desc.setStyleSheet("font-size: 8pt;")
        realtime_info.addWidget(realtime_desc)
        rr.addLayout(realtime_info, stretch=1)
        self.switch_realtime_detect = ToggleSwitch("", default=self.settings.get("realtime_detect", False))
        self.switch_realtime_detect.setFixedWidth(80)
        self.switch_realtime_detect.toggled.connect(self._on_realtime_detect_toggled)
        rr.addWidget(self.switch_realtime_detect, alignment=Qt.AlignmentFlag.AlignVCenter)
        sm.addWidget(realtime_row)

        timeout_row = QFrame()
        timeout_row.setObjectName("switch-row")
        tr = QHBoxLayout(timeout_row)
        tr.setContentsMargins(14, 8, 14, 8)
        timeout_info = QVBoxLayout()
        timeout_info.setSpacing(1)
        timeout_lbl = QLabel("⚡ 超时切换最快线路")
        timeout_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        timeout_info.addWidget(timeout_lbl)
        timeout_desc = QLabel("按间隔定时检测，自动切换到最快线路")
        timeout_desc.setObjectName("dim")
        timeout_desc.setStyleSheet("font-size: 8pt;")
        timeout_info.addWidget(timeout_desc)
        tr.addLayout(timeout_info, stretch=1)
        self.switch_auto_line = ToggleSwitch("", default=self.settings.get("auto_line_switch", False))
        self.switch_auto_line.setFixedWidth(80)
        self.switch_auto_line.toggled.connect(self._on_auto_line_switch_toggled)
        tr.addWidget(self.switch_auto_line, alignment=Qt.AlignmentFlag.AlignVCenter)
        sm.addWidget(timeout_row)

        interval_row = QHBoxLayout()
        interval_row.setSpacing(8)
        interval_lbl = QLabel("检测间隔:")
        interval_lbl.setObjectName("dim")
        interval_lbl.setStyleSheet("font-size: 9pt;")
        interval_row.addWidget(interval_lbl)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 120)
        self.interval_spin.setValue(self.settings.get("auto_line_interval", 30))
        self.interval_spin.setSuffix(" 分钟")
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        interval_row.addWidget(self.interval_spin)
        interval_row.addStretch()
        self.auto_line_status = QLabel("")
        self.auto_line_status.setObjectName("dim")
        self.auto_line_status.setStyleSheet("font-size: 8pt;")
        interval_row.addWidget(self.auto_line_status)
        sm.addLayout(interval_row)

        layout.addWidget(smart_card)

        browser_card = QFrame()
        browser_card.setObjectName("card")
        bc = QVBoxLayout(browser_card)
        bc.setContentsMargins(20, 14, 20, 14)
        bc.setSpacing(8)

        browser_title = QLabel("浏览器")
        browser_title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        bc_title_row = QHBoxLayout()
        bc_title_row.setSpacing(4)
        bc_title_row.addWidget(browser_title)
        bc_title_row.addWidget(_make_help_btn(
            "浏览器设置",
            "浏览器设置说明",
            "【检测线路后打开浏览器】\n"
            "开启后，检测线路完成时自动打开浏览器。\n\n"
            "【系统浏览器】\n"
            "自动检测系统中已安装的浏览器，从列表中选择即可。\n\n"
            "【自定义浏览器】\n"
            "手动指定浏览器exe路径，适用于便携版或非标准安装路径的浏览器。\n"
            "点击「打开文件夹」浏览选择浏览器可执行文件。\n\n"
            "【打开浏览器】\n"
            "以代理模式启动浏览器。若浏览器已在运行，会提示关闭后重启，\n"
            "否则代理参数无法生效。"
        ))
        bc_title_row.addStretch()
        bc.addLayout(bc_title_row)

        auto_browser_row = QFrame()
        auto_browser_row.setObjectName("switch-row")
        abr = QHBoxLayout(auto_browser_row)
        abr.setContentsMargins(14, 8, 14, 8)
        auto_browser_lbl = QLabel("🌐 检测线路后打开浏览器")
        auto_browser_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        abr.addWidget(auto_browser_lbl, stretch=1)
        self.switch_auto_browser = ToggleSwitch("", default=self.settings.get("auto_open_browser", True))
        self.switch_auto_browser.setFixedWidth(80)
        self.switch_auto_browser.toggled.connect(self._on_auto_open_browser_toggled)
        abr.addWidget(self.switch_auto_browser, alignment=Qt.AlignmentFlag.AlignVCenter)
        bc.addWidget(auto_browser_row)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_row.addWidget(QLabel("浏览器:"))
        self.browser_type_group = []
        self.system_rb = RadioButton("系统", default=self.settings.get("browser_type", "system") == "system")
        self.browser_type_group.append(self.system_rb)
        mode_row.addWidget(self.system_rb)
        self.custom_rb = RadioButton("自定义", default=self.settings.get("browser_type", "system") == "custom")
        self.browser_type_group.append(self.custom_rb)
        mode_row.addWidget(self.custom_rb)
        self.system_rb.toggled.connect(lambda checked: self._on_custom_radio_toggled("system", checked))
        self.custom_rb.toggled.connect(lambda checked: self._on_custom_radio_toggled("custom", checked))
        mode_row.addStretch()
        bc.addLayout(mode_row)

        system_row = QHBoxLayout()
        system_row.setSpacing(6)
        self.browser_combo = UpComboBox()
        self.browser_combo.setMinimumWidth(200)
        self._populate_browsers()
        self.browser_combo.currentIndexChanged.connect(self._on_system_browser_changed)
        system_row.addWidget(self.browser_combo, stretch=1)
        self.btn_open_browser_system = QPushButton("打开浏览器")
        self.btn_open_browser_system.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_browser_system.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; padding: 6px 12px; "
            f"font-size: 8pt; font-weight: bold; border-radius: 6px; border: none; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        self.btn_open_browser_system.clicked.connect(self._on_open_browser)
        system_row.addWidget(self.btn_open_browser_system)
        self.system_browser_row_widget = QWidget()
        self.system_browser_row_widget.setLayout(system_row)
        bc.addWidget(self.system_browser_row_widget)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(6)
        self.custom_browser_input = QLineEdit(self.settings.get("browser_path", ""))
        self.custom_browser_input.setPlaceholderText("输入浏览器exe路径...")
        self.custom_browser_input.setStyleSheet(
            f"QLineEdit {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 4px; padding: 4px 8px; color: {COLOR_TEXT}; font-size: 8pt; }}"
        )
        self.custom_browser_input.textChanged.connect(self._on_custom_browser_input_changed)
        custom_row.addWidget(self.custom_browser_input, stretch=1)
        self.btn_browse_browser = QPushButton("打开文件夹")
        self.btn_browse_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse_browser.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #FFFFFF; padding: 6px 10px; "
            f"font-size: 8pt; font-weight: bold; border-radius: 6px; border: none; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        self.btn_browse_browser.clicked.connect(self._on_browse_browser)
        custom_row.addWidget(self.btn_browse_browser)
        self.btn_open_browser = QPushButton("打开浏览器")
        self.btn_open_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_browser.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; padding: 6px 12px; "
            f"font-size: 8pt; font-weight: bold; border-radius: 6px; border: none; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        self.btn_open_browser.clicked.connect(self._on_open_browser)
        custom_row.addWidget(self.btn_open_browser)
        self.custom_browser_row_widget = QWidget()
        self.custom_browser_row_widget.setLayout(custom_row)
        self.custom_browser_row_widget.setVisible(self.settings.get("browser_type", "system") == "custom")
        bc.addWidget(self.custom_browser_row_widget)

        self._update_browser_row_visibility()

        layout.addWidget(browser_card)

        self.line_progress = QLabel("")
        self.line_progress.setObjectName("dim")
        self.line_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.line_progress)
        layout.addStretch()
        return page

    def _build_proxy_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        proxy_card = QFrame()
        proxy_card.setObjectName("card")
        pl = QVBoxLayout(proxy_card)
        pl.setSpacing(10)

        proxy_title = QLabel("代理功能")
        proxy_title.setObjectName("accent")
        proxy_title.setStyleSheet("font-size: 9pt; font-weight: bold;")
        pl_title_row = QHBoxLayout()
        pl_title_row.setSpacing(4)
        pl_title_row.addWidget(proxy_title)
        pl_title_row.addWidget(_make_help_btn(
            "代理功能设置",
            "代理功能说明",
            "【浏览器代理】\n"
            "控制浏览器是否通过本地代理访问网络，始终开启。\n\n"
            "【代理范围】\n"
            "全部浏览器：通过系统代理设置，所有浏览器都走代理。\n"
            "指定浏览器：仅对线路服务页面选定的浏览器设置代理参数，\n"
            "其他浏览器不受影响。\n\n"
            "【全局系统代理】\n"
            "开启后，系统中所有应用（不仅浏览器）都通过代理访问网络。\n"
            "关闭后仅浏览器走代理，其他程序不受影响。"
        ))
        pl_title_row.addStretch()
        pl.addLayout(pl_title_row)

        browser_row = QFrame()
        browser_row.setObjectName("switch-row")
        br = QHBoxLayout(browser_row)
        br.setContentsMargins(12, 6, 12, 6)
        browser_info = QVBoxLayout()
        browser_info.setSpacing(0)
        browser_lbl = QLabel("🌐 浏览器代理")
        browser_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        browser_info.addWidget(browser_lbl)
        self.browser_proxy_desc = QLabel("浏览器通过本地代理访问")
        self.browser_proxy_desc.setObjectName("dim")
        self.browser_proxy_desc.setStyleSheet("font-size: 8pt;")
        browser_info.addWidget(self.browser_proxy_desc)
        br.addLayout(browser_info, stretch=1)
        browser_switch = ToggleSwitch("", default=True)
        browser_switch.setEnabled(False)
        browser_switch.setFixedWidth(80)
        br.addWidget(browser_switch)
        pl.addWidget(browser_row)

        browser_mode_row = QFrame()
        browser_mode_row.setObjectName("switch-row")
        bmr = QHBoxLayout(browser_mode_row)
        bmr.setContentsMargins(12, 6, 12, 6)
        bmr.addWidget(QLabel("代理范围:"))
        self.browser_proxy_group = []
        self.all_browser_rb = RadioButton("全部浏览器", default=self.settings.get("browser_proxy_mode", "all") == "all")
        self.browser_proxy_group.append(self.all_browser_rb)
        bmr.addWidget(self.all_browser_rb)
        self.spec_browser_rb = RadioButton("指定浏览器", default=self.settings.get("browser_proxy_mode", "all") == "specified")
        self.browser_proxy_group.append(self.spec_browser_rb)
        bmr.addWidget(self.spec_browser_rb)
        bmr.addStretch()
        self.all_browser_rb.toggled.connect(lambda checked: self._on_proxy_mode_radio_toggled("all", checked))
        self.spec_browser_rb.toggled.connect(lambda checked: self._on_proxy_mode_radio_toggled("specified", checked))
        pl.addWidget(browser_mode_row)

        self.specified_browser_hint = QLabel("")
        self.specified_browser_hint.setObjectName("dim")
        self.specified_browser_hint.setStyleSheet(f"font-size: 8pt; color: {COLOR_RED_LIGHT};")
        self.specified_browser_hint.setWordWrap(True)
        self._update_browser_proxy_hint()
        pl.addWidget(self.specified_browser_hint)

        global_row = QFrame()
        global_row.setObjectName("switch-row")
        gr = QHBoxLayout(global_row)
        gr.setContentsMargins(12, 6, 12, 6)
        global_info = QVBoxLayout()
        global_info.setSpacing(0)
        global_lbl = QLabel("🌍 全局系统代理")
        global_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        global_info.addWidget(global_lbl)
        global_desc = QLabel("所有系统应用通过代理访问")
        global_desc.setObjectName("dim")
        global_desc.setStyleSheet("font-size: 8pt;")
        global_info.addWidget(global_desc)
        gr.addLayout(global_info, stretch=1)
        self.switch_global_proxy = ToggleSwitch("", default=self.settings.get("global_proxy", False))
        self.switch_global_proxy.setFixedWidth(80)
        self.switch_global_proxy.toggled.connect(self._on_global_proxy_toggled)
        gr.addWidget(self.switch_global_proxy)
        pl.addWidget(global_row)

        self.global_restart_hint = QLabel("⚠ 修改后需重启服务生效")
        self.global_restart_hint.setObjectName("restart-hint")
        self.global_restart_hint.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 8pt;")
        self.global_restart_hint.setVisible(False)
        pl.addWidget(self.global_restart_hint)

        layout.addWidget(proxy_card)

        custom_card = QFrame()
        custom_card.setObjectName("card")
        cl = QVBoxLayout(custom_card)
        cl.setSpacing(8)

        custom_header = QHBoxLayout()
        custom_info = QVBoxLayout()
        custom_info.setSpacing(0)
        custom_title_row = QHBoxLayout()
        custom_title_row.setSpacing(4)
        custom_title = QLabel("🎯 指定程序代理")
        custom_title.setStyleSheet("font-size: 8pt; font-weight: bold;")
        custom_title_row.addWidget(custom_title)
        custom_title_row.addWidget(_make_help_btn(
            "指定程序代理",
            "指定程序代理说明",
            "【功能说明】\n"
            "添加指定程序后，这些程序也会通过代理访问网络。\n"
            "适合需要让某些非浏览器应用也走代理的场景。\n\n"
            "【使用方法】\n"
            "1. 开启开关\n"
            "2. 点击「添加程序」选择exe文件\n"
            "3. 修改后需重启代理服务生效"
        ))
        custom_title_row.addStretch()
        custom_info.addLayout(custom_title_row)
        custom_desc = QLabel("添加的程序也通过代理访问")
        custom_desc.setObjectName("dim")
        custom_desc.setStyleSheet("font-size: 8pt;")
        custom_info.addWidget(custom_desc)
        custom_header.addLayout(custom_info, stretch=1)
        self.switch_custom_apps = ToggleSwitch("", default=self.settings.get("custom_apps_enabled", False))
        self.switch_custom_apps.setFixedWidth(80)
        self.switch_custom_apps.toggled.connect(self._on_custom_apps_toggled)
        custom_header.addWidget(self.switch_custom_apps)
        cl.addLayout(custom_header)

        self.custom_restart_hint = QLabel("⚠ 修改后需重启服务生效")
        self.custom_restart_hint.setObjectName("restart-hint")
        self.custom_restart_hint.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 8pt;")
        self.custom_restart_hint.setVisible(False)
        cl.addWidget(self.custom_restart_hint)

        app_btn_row = QHBoxLayout()
        app_btn_row.setSpacing(8)
        add_btn = QPushButton("＋ 添加程序")
        add_btn.setObjectName("small-blue")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_app)
        app_btn_row.addWidget(add_btn)
        remove_btn = QPushButton("－ 删除程序")
        remove_btn.setObjectName("small-red")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; padding: 4px 12px; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        remove_btn.clicked.connect(self._on_remove_app)
        app_btn_row.addWidget(remove_btn)
        app_btn_row.addStretch()
        cl.addLayout(app_btn_row)
        self.app_list = QListWidget()
        self.app_list.setMaximumHeight(120)
        for app_path in self.settings.get("custom_apps", []):
            self._add_app_item(app_path)
        cl.addWidget(self.app_list)

        layout.addWidget(custom_card)

        startup_card = QFrame()
        startup_card.setObjectName("card")
        sl = QVBoxLayout(startup_card)
        sl.setSpacing(8)

        startup_title = QLabel("启动设置")
        startup_title.setObjectName("accent")
        startup_title.setStyleSheet("font-size: 9pt; font-weight: bold;")
        sl_title_row = QHBoxLayout()
        sl_title_row.setSpacing(4)
        sl_title_row.addWidget(startup_title)
        sl_title_row.addWidget(_make_help_btn(
            "启动设置",
            "启动设置说明",
            "【启动时自动开启服务】\n"
            "开启后，打开软件时自动启动代理服务并连接线路。\n"
            "关闭后，需要手动点击代理服务开关来启动。"
        ))
        sl_title_row.addStretch()
        sl.addLayout(sl_title_row)

        autostart_row = QFrame()
        autostart_row.setObjectName("switch-row")
        asr = QHBoxLayout(autostart_row)
        asr.setContentsMargins(12, 6, 12, 6)
        autostart_info = QVBoxLayout()
        autostart_info.setSpacing(0)
        autostart_lbl = QLabel("🚀 启动时自动开启服务")
        autostart_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        autostart_info.addWidget(autostart_lbl)
        autostart_desc = QLabel("打开启动器时自动启动代理服务")
        autostart_desc.setObjectName("dim")
        autostart_desc.setStyleSheet("font-size: 8pt;")
        autostart_info.addWidget(autostart_desc)
        asr.addLayout(autostart_info, stretch=1)
        self.switch_auto_start = ToggleSwitch("", default=self.settings.get("auto_start", True))
        self.switch_auto_start.setFixedWidth(80)
        self.switch_auto_start.toggled.connect(self._on_auto_start_toggled)
        asr.addWidget(self.switch_auto_start)
        sl.addWidget(autostart_row)

        layout.addWidget(startup_card)

        update_card = QFrame()
        update_card.setObjectName("card")
        ul = QVBoxLayout(update_card)
        ul.setSpacing(8)

        update_title = QLabel("更新管理")
        update_title.setObjectName("accent")
        update_title.setStyleSheet("font-size: 9pt; font-weight: bold;")
        ul_title_row = QHBoxLayout()
        ul_title_row.setSpacing(4)
        ul_title_row.addWidget(update_title)
        ul_title_row.addWidget(_make_help_btn(
            "更新管理",
            "更新管理说明",
            "【更新代理内核版本】\n"
            "自动从 GitHub 下载最新版 mihomo 内核并替换 quick.exe。\n"
            "如代理正在运行，更新后会自动重启服务。\n\n"
            "【更新线路配置】\n"
            "下载最新的线路服务器列表。\n"
            "检测线路时会自动更新配置（每天仅自动更新一次），\n"
            "如需立即更新可手动点击此按钮。"
        ))
        ul_title_row.addStretch()
        ul.addLayout(ul_title_row)

        update_btn_row = QHBoxLayout()
        update_btn_row.setSpacing(16)

        btn_update_quick = QPushButton("🔄 更新代理内核")
        btn_update_quick.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_update_quick.setFixedSize(140, 34)
        btn_update_quick.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #FFFFFF; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        btn_update_quick.clicked.connect(self._on_update_quick)
        update_btn_row.addWidget(btn_update_quick)

        btn_update_config = QPushButton("📥 更新线路配置")
        btn_update_config.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_update_config.setFixedSize(140, 34)
        btn_update_config.setStyleSheet(
            f"QPushButton {{ background-color: #1B5E20; color: #FFFFFF; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: #2E7D32; }}"
        )
        btn_update_config.clicked.connect(self._on_update_config)
        update_btn_row.addWidget(btn_update_config)

        update_btn_row.addStretch()
        ul.addLayout(update_btn_row)
        self.update_status = QLabel("")
        self.update_status.setObjectName("dim")
        self.update_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ul.addWidget(self.update_status)

        layout.addWidget(update_card)

        self.sys_proxy_lbl = QLabel("")
        self.sys_proxy_lbl.setObjectName("dim")
        self._update_sys_proxy_label()
        layout.addWidget(self.sys_proxy_lbl)
        layout.addStretch()
        return page

    def _build_log_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("log")
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("清空日志")
        clear_btn.setObjectName("small-blue")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self.log_text.clear)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()

        export_btn = QPushButton("导出日志")
        export_btn.setObjectName("small-blue")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._on_export_log)
        btn_row.addWidget(export_btn)
        layout.addLayout(btn_row)

        handler = QTextEditLogHandler(self._append_log)
        handler.setFormatter(_formatter)
        log.addHandler(handler)

        return page

    def _build_update_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tab_bar = QFrame()
        tab_bar.setStyleSheet(f"background-color: #1e1e1e; border: none;")
        tab_bar.setFixedHeight(48)
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(10, 7, 10, 7)
        tab_layout.setSpacing(4)

        self._ver_tab_stable_btn = QPushButton("📦 EXE稳定版")
        self._ver_tab_stable_btn.setFixedSize(140, 34)
        self._ver_tab_stable_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ver_tab_stable_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        self._ver_tab_stable_btn.clicked.connect(lambda: self._switch_ver_tab("stable"))
        tab_layout.addWidget(self._ver_tab_stable_btn)

        self._ver_tab_git_btn = QPushButton("🔧 Git开发版")
        self._ver_tab_git_btn.setFixedSize(140, 34)
        self._ver_tab_git_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ver_tab_git_btn.setStyleSheet(
            f"QPushButton {{ background-color: #444; color: #888; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED}; }}"
        )
        self._ver_tab_git_btn.clicked.connect(lambda: self._switch_ver_tab("git"))
        tab_layout.addWidget(self._ver_tab_git_btn)

        tab_layout.addStretch()

        tab_layout.addWidget(_make_help_btn(
            "软件版本管理",
            "软件更新说明",
            "【EXE稳定版】\n"
            "显示已发布正式版本的列表，可切换、下载和查看更新内容。\n"
            "绿色标记为当前使用的版本。\n\n"
            "【Git开发版】\n"
            "显示远程仓库的开发提交记录，仅开发者可见。\n"
            "需要本地有源码环境才能切换到开发版。\n\n"
            "【切换版本】\n"
            "点击「切换」按钮可在已下载的版本间切换，\n"
            "切换后程序会自动重启。\n\n"
            "【下载版本】\n"
            "点击「下载」按钮从远程仓库下载新版本EXE文件，\n"
            "下载完成后可选择立即切换。"
        ))

        self._ver_status_label = QLabel("")
        self._ver_status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_DIM}; border: none;")
        tab_layout.addWidget(self._ver_status_label)

        btn_check_remote = QPushButton("🔄 检查更新")
        btn_check_remote.setFixedSize(100, 30)
        btn_check_remote.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_check_remote.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 6px; "
            f"font-size: 8pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        btn_check_remote.clicked.connect(self._check_remote_versions)
        tab_layout.addWidget(btn_check_remote)

        self._ver_expand_btn = QPushButton("📋 收起详情")
        self._ver_expand_btn.setFixedSize(100, 30)
        self._ver_expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ver_expand_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 6px; "
            f"font-size: 8pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        self._ver_expand_btn.clicked.connect(self._toggle_expand_all)
        tab_layout.addWidget(self._ver_expand_btn)

        layout.addWidget(tab_bar)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {COLOR_BG}; border: none; }}"
            f"QScrollBar:vertical {{ background-color: {COLOR_BG}; width: 8px; border: none; }}"
            f"QScrollBar::handle:vertical {{ background-color: #333; border-radius: 4px; min-height: 30px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
        )
        self._ver_scroll_content = QWidget()
        self._ver_scroll_layout = QVBoxLayout(self._ver_scroll_content)
        self._ver_scroll_layout.setContentsMargins(10, 6, 10, 6)
        self._ver_scroll_layout.setSpacing(4)
        self._ver_scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self._ver_scroll_content)
        layout.addWidget(scroll_area, stretch=1)

        self._ver_stable_data = []
        self._ver_git_data = []
        self._ver_current_version = VERSION
        self._ver_active_tab = "stable"
        self._ver_info_text = "点击「检查远程更新」查看最新版本"
        self._ver_expanded = True
        self._latest_version = ""
        self._latest_info = None

        self._ver_status_label.setText("加载中...")
        QTimer.singleShot(100, self._check_remote_versions)

        return page

    def _populate_browsers(self):
        self.browser_combo.blockSignals(True)
        self.browser_combo.clear()
        browsers = find_system_browsers()
        saved_path = self.settings.get("system_browser_path", "")
        select_idx = 0
        for i, (name, path) in enumerate(browsers):
            self.browser_combo.addItem(f"{name} ({path})", path)
            if path == saved_path:
                select_idx = i
        if browsers:
            self.browser_combo.setCurrentIndex(select_idx)
        self.browser_combo.blockSignals(False)

    def _get_quick_version(self):
        if not self.quick_dir:
            return None
        try:
            return f"{os.path.getsize(os.path.join(self.quick_dir, 'quick.exe')) // 1024}KB"
        except Exception:
            return None

    def _add_app_item(self, app_path):
        item = QListWidgetItem(os.path.basename(app_path))
        item.setData(Qt.ItemDataRole.UserRole, app_path)
        self.app_list.addItem(item)

    def _append_log(self, msg):
        self.log_text.append(msg)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _update_kernel_status(self):
        if self.quick_dir:
            log.info(f"代理内核已就绪: {self.quick_dir}")
        else:
            log.warning("未找到代理内核")

    def _update_status(self, running):
        if running:
            self.svc_status_dot.setStyleSheet(f"font-size: 18px; color: {COLOR_GREEN};")
            self.svc_status_label.setText("代理运行中")
            self.svc_status_label.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {COLOR_GREEN};")
            self.svc_detail_label.setText("代理服务已启动")
            self.svc_line_label.setText(f"线路: {self.current_line or '未知'}")
        else:
            self.svc_status_dot.setStyleSheet(f"font-size: 18px; color: #FF6B80;")
            if self.switch_proxy.isChecked():
                self.svc_status_label.setText("代理未连接")
                self.svc_status_label.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {COLOR_ORANGE};")
                self.svc_detail_label.setText("代理服务已开启但未连接")
                self.svc_line_label.setText("线路: 点击重连")
            else:
                self.svc_status_label.setText("代理未启动")
                self.svc_status_label.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {COLOR_TEXT};")
                self.svc_detail_label.setText("开启代理服务以访问外网")
                self.svc_line_label.setText("线路: --")
            self.svc_latency_label.setText("延迟: --")

    def _update_active_line(self):
        for name, info in self.line_rows.items():
            row = info["row"]
            btn = info["use_btn"]
            if name == self.current_line and is_proxy_running():
                row.setObjectName("line-active")
                row.setStyleSheet(row.styleSheet())
                info["status"].setStyleSheet(f"color: {COLOR_RED_LIGHT}; font-weight: bold;")
                btn.setText("运行中")
                btn.setObjectName("small-red")
                btn.setStyleSheet(
                    f"background-color: {COLOR_RED}; color: #FFFFFF; padding: 3px 10px; "
                    f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none;"
                )
                btn.setEnabled(False)
                btn.setCursor(Qt.CursorShape.ArrowCursor)
            elif name == self.current_line:
                row.setObjectName("line-active")
                row.setStyleSheet(row.styleSheet())
                info["status"].setStyleSheet(f"color: {COLOR_ORANGE}; font-weight: bold;")
                btn.setText("重连")
                btn.setObjectName("small-orange")
                btn.setStyleSheet(
                    f"background-color: {COLOR_ORANGE}; color: #FFFFFF; padding: 3px 10px; "
                    f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none;"
                )
                btn.setEnabled(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                row.setObjectName("line-row")
                row.setStyleSheet(row.styleSheet())
                btn.setText("使用")
                btn.setObjectName("small-blue")
                btn.setStyleSheet("")
                btn.setEnabled(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _update_sys_proxy_label(self):
        enabled, server = get_system_proxy()
        if enabled:
            self.sys_proxy_lbl.setText(f"系统代理: 已开启 (服务器: {server})")
            self.sys_proxy_lbl.setStyleSheet(f"color: {COLOR_GREEN};")
        else:
            self.sys_proxy_lbl.setText("系统代理: 未开启")
            self.sys_proxy_lbl.setStyleSheet(f"color: {COLOR_DIM};")

    def _set_line_status(self, name, text, color=COLOR_DIM):
        if name in self.line_rows:
            self.line_rows[name]["status"].setText(text)
            if name != self.current_line:
                self.line_rows[name]["status"].setStyleSheet(f"color: {color};")

    def _get_browser_path(self):
        browser_type = "system"
        if self.custom_rb.isChecked():
            browser_type = "custom"

        self._save_setting("browser_type", browser_type)

        path = None
        if browser_type == "system":
            idx = self.browser_combo.currentIndex()
            if idx >= 0:
                path = self.browser_combo.itemData(idx)
        elif browser_type == "custom":
            path = self.settings.get("browser_path", "") or None

        log.info(f"浏览器类型: {browser_type}, 路径: {path or '未找到'}")
        return path

    def _start_auto_line_timer(self):
        if self._auto_line_timer:
            self._auto_line_timer.stop()
        interval = self.settings.get("auto_line_interval", 30)
        self._auto_line_timer = QTimer(self)
        self._auto_line_timer.timeout.connect(self._auto_line_check)
        self._auto_line_timer.start(interval * 60 * 1000)
        self.auto_line_status.setText(f"下次检测: {interval}分钟后")
        log.info(f"自动线路检测已启动，间隔: {interval}分钟")

    def _stop_auto_line_timer(self):
        if self._auto_line_timer:
            self._auto_line_timer.stop()
            self._auto_line_timer = None
        self.auto_line_status.setText("")
        log.info("自动线路检测已停止")

    def _auto_line_check(self):
        if not self.quick_dir or not is_proxy_running():
            return
        if self.worker and self.worker.isRunning():
            return
        self._cleanup_worker()
        log.info("自动线路检测: 开始检测...")
        self.auto_line_status.setText("正在检测线路...")
        self.worker = ServiceWorker("auto_select", quick_dir=self.quick_dir,
                                    proxy_enabled=self.settings.get("proxy_enabled", False),
                                    current_line=self.current_line)
        self.worker.line_selected.connect(self._on_line_selected)
        self.worker.finished.connect(self._on_auto_line_check_finished)
        self.worker.start()

    def _on_auto_line_check_finished(self, ok, msg):
        if ok:
            line_name = msg.split(":")[-1].strip() if ":" in msg else ""
            if line_name and line_name != self.current_line:
                log.info(f"自动切换线路: {self.current_line} → {line_name}")
                self.current_line = line_name
                self._save_setting("current_line", line_name)
                self._update_active_line()
                if is_proxy_running() and line_name in self.line_results and self.line_results[line_name]:
                    self.worker = ServiceWorker("use_line", name=line_name, data=self.line_results[line_name],
                                                quick_dir=self.quick_dir,
                                                proxy_enabled=self.settings.get("proxy_enabled", False))
                    self.worker.start()
            interval = self.settings.get("auto_line_interval", 30)
            self.auto_line_status.setText(f"下次检测: {interval}分钟后")
        else:
            self.auto_line_status.setText("检测失败，等待下次")

    def _on_proxy_switch_toggled(self, checked):
        self._save_setting("proxy_enabled", checked)
        if checked:
            self._on_start()
        else:
            self._on_stop()

    def _on_start(self):
        if not self.quick_dir:
            QMessageBox.critical(self, "错误",
                "未找到代理内核！\n\n"
                f"基础目录: {get_base_dir()}\n\n"
                "请确保 app/Quick/ 目录中包含 quick.exe。")
            return
        if self.worker and self.worker.isRunning():
            return
        self._cleanup_worker()
        self.switch_proxy.setEnabled(False)
        self.svc_detail_label.setText("正在启动代理服务...")
        self.worker = ServiceWorker("start", quick_dir=self.quick_dir, current_line=self.current_line)
        self.worker.line_selected.connect(self._on_line_selected)
        self.worker.progress.connect(lambda t: self.svc_detail_label.setText(t))
        self.worker.finished.connect(self._on_start_finished)
        self.worker.start()

    def _on_start_finished(self, ok, msg):
        self.switch_proxy.setEnabled(True)
        if ok:
            self.svc_detail_label.setText(msg)
            try:
                connected, latency = verify_proxy_connection(timeout=5)
                if connected and latency:
                    self.svc_latency_label.setText(f"延迟: {latency:.2f}s")
            except Exception as e:
                log.warning(f"验证代理连接异常: {e}")
            browser_proxy_mode = self.settings.get("browser_proxy_mode", "all")
            if self.settings.get("global_proxy", False) or browser_proxy_mode == "all":
                set_system_proxy(True)
                self._update_sys_proxy_label()
            self.global_restart_hint.setVisible(False)
            self.custom_restart_hint.setVisible(False)
            if self.settings.get("auto_line_switch", False):
                self._start_auto_line_timer()
            if self.settings.get("realtime_detect", False):
                self._start_realtime_monitor()
            self._update_active_line()
        else:
            self.svc_detail_label.setText(msg)
            self._update_active_line()

    def _on_stop(self):
        if self.settings.get("global_proxy", False) or self.settings.get("browser_proxy_mode", "all") == "all":
            set_system_proxy(False)
            self._update_sys_proxy_label()
        stop_quick()
        self._stop_auto_line_timer()
        self.svc_detail_label.setText("服务已停止")

    def _on_line_selected(self, name):
        if name and name != self.current_line:
            self.current_line = name
            self._save_setting("current_line", name)
            self._update_active_line()

    def _save_setting(self, key, value):
        self.settings[key] = value
        save_settings(self.settings)

    def _on_open_browser(self):
        if not is_proxy_running():
            QMessageBox.warning(self, "提示", "代理服务未启动，请先启动服务！")
            return
        browser_path = self._get_browser_path()
        if not browser_path or not os.path.isfile(browser_path):
            QMessageBox.critical(self, "错误", "未找到浏览器！请在浏览器设置中配置。")
            return
        browser_type = _detect_browser_type(browser_path)
        browser_name = os.path.basename(browser_path)
        if browser_type == "unknown" and self.settings.get("browser_proxy_mode", "all") == "specified":
            reply = QMessageBox.question(
                self, "提示",
                f"检测到浏览器 {browser_name} 可能不支持命令行代理参数。\n\n"
                f"如无法翻墙，建议切换到「全部浏览器」模式（通过系统代理生效）。\n\n"
                f"是否仍然启动？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        if _is_browser_running(browser_path):
            reply = QMessageBox.question(
                self, "浏览器已在运行",
                f"{browser_name} 当前正在运行。\n\n"
                f"浏览器已运行时，代理参数无法生效（浏览器会复用旧进程）。\n"
                f"需要先关闭浏览器再重新启动，代理才能生效。\n\n"
                f"是否关闭并重新启动？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                _kill_browser(browser_path)
            else:
                return
        start_browser(browser_path)

    def _on_proxy_mode_radio_toggled(self, mode, checked):
        if not checked:
            return
        for rb in self.browser_proxy_group:
            if rb is not self.sender():
                rb._block_signal = True
                rb.setChecked(False)
                rb._block_signal = False
        self._save_setting("browser_proxy_mode", mode)
        self._update_browser_proxy_hint()
        if is_proxy_running():
            if mode == "all" or self.settings.get("global_proxy", False):
                set_system_proxy(True)
            else:
                set_system_proxy(False)

    def _update_browser_proxy_hint(self):
        mode = self.settings.get("browser_proxy_mode", "all")
        browser_path = self._get_browser_path()
        browser_name = os.path.basename(browser_path) if browser_path else "未选择"
        if mode == "all":
            self.specified_browser_hint.setText("所有浏览器都将通过代理访问网络")
            self.browser_proxy_desc.setText("浏览器通过本地代理访问")
        else:
            type_label = ""
            if browser_path and os.path.isfile(browser_path):
                bt = _detect_browser_type(browser_path)
                type_map = {"chromium": "Chromium内核", "firefox": "Firefox", "unknown": "未知内核"}
                type_label = f" [{type_map.get(bt, '未知内核')}]"
            self.specified_browser_hint.setText(f"当前指定浏览器: {browser_name}{type_label}" + (f" ({browser_path})" if browser_path else ""))
            self.browser_proxy_desc.setText("仅指定浏览器通过代理访问")

    def _get_current_browser_name(self):
        browser_type = self.settings.get("browser_type", "system")
        if browser_type == "custom":
            path = self.settings.get("browser_path", "")
            if path:
                return os.path.basename(path)
            return "未选择浏览器"
        else:
            browsers = find_system_browsers()
            if browsers:
                return os.path.basename(browsers[0][1])
            return "系统浏览器"

    def _on_global_proxy_toggled(self, checked):
        self._save_setting("global_proxy", checked)
        if is_proxy_running():
            set_system_proxy(checked)
            self._update_sys_proxy_label()
            self.global_restart_hint.setVisible(False)
        else:
            self.global_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
            self.global_restart_hint.setVisible(True)
        log.info(f"全局系统代理: {'开启' if checked else '关闭'}")

    def _on_custom_apps_toggled(self, checked):
        self._save_setting("custom_apps_enabled", checked)
        if is_proxy_running():
            self.custom_restart_hint.setText("⚠ 修改需重启服务后生效，当前仍使用原设置")
            self.custom_restart_hint.setVisible(True)
        else:
            self.custom_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
            self.custom_restart_hint.setVisible(True)
        log.info(f"指定程序代理: {'开启' if checked else '关闭'}")

    def _on_auto_open_browser_toggled(self, checked):
        self._save_setting("auto_open_browser", checked)
        log.info(f"检测线路后打开浏览器: {'开启' if checked else '关闭'}")

    def _on_realtime_detect_toggled(self, checked):
        self._save_setting("realtime_detect", checked)
        if checked and is_proxy_running():
            self._start_realtime_monitor()
        else:
            self._stop_realtime_monitor()
        log.info(f"实时检测: {'开启' if checked else '关闭'}")

    def _start_realtime_monitor(self):
        if hasattr(self, '_realtime_timer') and self._realtime_timer:
            self._realtime_timer.stop()
        self._realtime_timer = QTimer(self)
        self._realtime_timer.timeout.connect(self._realtime_check)
        self._realtime_timer.start(10000)

    def _stop_realtime_monitor(self):
        if hasattr(self, '_realtime_timer') and self._realtime_timer:
            self._realtime_timer.stop()
            self._realtime_timer = None

    def _realtime_check(self):
        if not is_proxy_running() and self.settings.get("proxy_enabled", False):
            if self.worker and self.worker.isRunning():
                return
            log.warning("实时检测: 代理断开，尝试重连")
            self._cleanup_worker()
            if self.current_line and self.current_line in self.line_results and self.line_results[self.current_line]:
                self.worker = ServiceWorker("use_line", name=self.current_line,
                                            data=self.line_results[self.current_line],
                                            quick_dir=self.quick_dir,
                                            proxy_enabled=True)
                self.worker.line_selected.connect(self._on_line_selected)
                self.worker.progress.connect(lambda t: self.svc_detail_label.setText(t))
                self.worker.finished.connect(self._on_use_line_finished)
                self.worker.start()
            elif self.quick_dir:
                self._on_start()

    def _on_auto_start_toggled(self, checked):
        self._save_setting("auto_start", checked)
        log.info(f"启动时自动开启服务: {'开启' if checked else '关闭'}")

    def _on_auto_line_switch_toggled(self, checked):
        self._save_setting("auto_line_switch", checked)
        if checked and is_proxy_running():
            self._start_auto_line_timer()
        else:
            self._stop_auto_line_timer()
        log.info(f"自动线路切换: {'开启' if checked else '关闭'}")

    def _on_interval_changed(self, value):
        self._save_setting("auto_line_interval", value)
        if self.settings.get("auto_line_switch", False) and is_proxy_running():
            self._start_auto_line_timer()
        log.info(f"自动检测间隔: {value}分钟")

    def _should_skip_config_update(self):
        saved_date = self.settings.get("last_config_update_date", "")
        if not saved_date:
            return False
        return saved_date == date.today().isoformat()

    def _on_test_lines(self):
        if not self.quick_dir:
            QMessageBox.warning(self, "提示", "请先设置代理内核目录")
            return
        if self.worker and self.worker.isRunning():
            return
        self._cleanup_worker()
        if self._should_skip_config_update():
            self._start_line_test()
            return
        self.btn_test.setEnabled(False)
        self.btn_test.setText("更新配置...")
        for name, info in self.line_rows.items():
            info["status"].setText("更新配置...")
            info["status"].setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 9pt;")
            info["use_btn"].setEnabled(False)
        self.worker = ServiceWorker("update_config", quick_dir=self.quick_dir, current_line=self.current_line)
        self.worker.progress.connect(lambda t: self.line_progress.setText(t))
        self.worker.finished.connect(self._on_config_updated_then_test)
        self.worker.start()

    def _start_line_test(self):
        self.btn_test.setEnabled(False)
        self.btn_test.setText("检测中...")
        for name, info in self.line_rows.items():
            info["status"].setText("检测中...")
            info["status"].setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 9pt;")
            info["use_btn"].setEnabled(False)
        self.worker = ServiceWorker("test_lines", quick_dir=self.quick_dir,
                                    proxy_enabled=self.settings.get("proxy_enabled", False),
                                    current_line=self.current_line)
        self.worker.progress.connect(lambda t: self.line_progress.setText(t))
        self.worker.line_tested.connect(self._on_line_tested)
        self.worker.finished.connect(self._on_test_finished)
        self.worker.start()

    def _on_config_updated_then_test(self, ok, msg):
        self.line_progress.setText(msg if ok else f"配置更新失败: {msg}")
        if not ok:
            self.btn_test.setEnabled(True)
            self.btn_test.setText("🔍 检测线路")
            for name, info in self.line_rows.items():
                info["status"].setText("配置更新失败")
                info["status"].setStyleSheet(f"color: #FF6B80; font-size: 9pt;")
            return
        self._save_setting("last_config_update_date", date.today().isoformat())
        self._cleanup_worker()
        self._start_line_test()

    def _on_line_tested(self, name, avg, is_ok):
        if name not in self.line_rows:
            return
        info = self.line_rows[name]
        if is_ok:
            info["status"].setText(f"平均{avg:.2f}s")
            info["status"].setStyleSheet(f"color: {COLOR_GREEN}; font-size: 9pt;")
            info["use_btn"].setEnabled(True)
        else:
            info["status"].setText("超时")
            info["status"].setStyleSheet(f"color: #FF6B80; font-size: 9pt;")
            info["use_btn"].setEnabled(False)

    def _on_test_finished(self, ok, msg):
        self.btn_test.setEnabled(True)
        self.btn_test.setText("🔍 检测线路")
        try:
            if not ok:
                self.line_progress.setText(msg if msg else "检测失败")
                self.line_progress.setStyleSheet("color: #FF6B80;")
                return

            worker = self.worker
            if not worker or "results" not in worker.kwargs:
                self.line_progress.setText("检测结果异常")
                self.line_progress.setStyleSheet("color: #FF6B80;")
                return

            results = list(worker.kwargs["results"])
            auto_switch = self.switch_auto_line.isChecked()

            for name, avg, best, count, data in results:
                self.line_results[name] = data
                if name not in self.line_rows:
                    continue
                info = self.line_rows[name]
                if avg >= 0:
                    info["status"].setText(f"平均{avg:.2f}s | 最快{best:.2f}s | {count}/{len(NODE_TEST_URLS)}节点")
                    info["status"].setStyleSheet(f"color: {COLOR_GREEN}; font-size: 9pt;")
                    info["use_btn"].setEnabled(True)
                else:
                    info["status"].setText("超时")
                    info["status"].setStyleSheet(f"color: #FF6B80; font-size: 9pt;")
                    info["use_btn"].setEnabled(False)

            valid = [r for r in results if r[1] >= 0]
            if valid:
                fastest = min(valid, key=lambda x: x[1])
                if fastest[0] in self.line_rows:
                    self.line_rows[fastest[0]]["status"].setText(f"最快 ✓ (平均{fastest[1]:.2f}s)")
                    self.line_rows[fastest[0]]["status"].setStyleSheet(f"color: {COLOR_ORANGE}; font-weight: bold; font-size: 9pt;")
                self.line_progress.setText(f"检测完成 - {len(valid)}条可用线路")
                self.line_progress.setStyleSheet(f"color: {COLOR_GREEN};")
                if auto_switch and fastest[0] in self.line_rows:
                    self._pending_browser_open = self.switch_auto_browser.isChecked()
                    self._on_use_line(fastest[0])
            else:
                self.line_progress.setText("检测完成 - 无可用线路")
                self.line_progress.setStyleSheet("color: #FF6B80;")
        except Exception as e:
            import traceback
            log.error(f"检测结果显示异常: {e}\n{traceback.format_exc()}")
            self.line_progress.setText(f"检测出错: {e}")
            self.line_progress.setStyleSheet("color: #FF6B80;")

    def _on_use_line(self, name):
        if not self.quick_dir:
            return
        if self.worker and self.worker.isRunning():
            return
        self._cleanup_worker()
        is_reconnect = (name == self.current_line)
        if not is_reconnect:
            if name not in self.line_results or self.line_results[name] is None:
                QMessageBox.information(self, "提示", "请先检测线路")
                return
            self.current_line = name
            self._save_setting("current_line", name)
        self._update_active_line()
        data = self.line_results.get(name)
        if data:
            self.worker = ServiceWorker("use_line", name=name, data=data, quick_dir=self.quick_dir,
                                        proxy_enabled=self.settings.get("proxy_enabled", False))
        else:
            self.worker = ServiceWorker("start", quick_dir=self.quick_dir, current_line=name)
        self.worker.line_selected.connect(self._on_line_selected)
        self.worker.progress.connect(lambda t: self.svc_detail_label.setText(t))
        self.worker.finished.connect(self._on_use_line_finished)
        self.worker.start()

    def _on_use_line_finished(self, ok, msg):
        self._update_active_line()
        if ok:
            self.svc_detail_label.setText(msg)
            try:
                connected, latency = verify_proxy_connection(timeout=5)
                if connected and latency:
                    self.svc_latency_label.setText(f"延迟: {latency:.2f}s")
            except Exception as e:
                log.warning(f"验证代理连接异常: {e}")
            if getattr(self, '_pending_browser_open', False):
                self._pending_browser_open = False
                QTimer.singleShot(500, self._on_open_browser)
        else:
            QMessageBox.warning(self, "提示", msg)

    def _cleanup_worker(self):
        if hasattr(self, 'worker') and self.worker:
            try:
                self.worker.finished.disconnect()
                self.worker.progress.disconnect()
                self.worker.line_tested.disconnect()
                self.worker.line_selected.disconnect()
            except (TypeError, RuntimeError):
                pass
            if self.worker.isRunning():
                self.worker.quit()
                self.worker.wait(3000)
            self.worker = None

    def _on_add_app(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择程序", "", "可执行文件 (*.exe);;所有文件 (*.*)")
        if path:
            self._add_app_item(path)
            self.settings["custom_apps"] = [
                self.app_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.app_list.count())
            ]
            save_settings(self.settings)
            if is_proxy_running():
                self.custom_restart_hint.setText("⚠ 添加程序需重启服务后生效，当前仍使用原设置")
                self.custom_restart_hint.setVisible(True)
            else:
                self.custom_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
                self.custom_restart_hint.setVisible(True)

    def _on_remove_app(self):
        current_item = self.app_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请先在列表中选择要删除的程序")
            return
        app_name = current_item.text()
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除「{app_name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.app_list.takeItem(self.app_list.row(current_item))
            self.settings["custom_apps"] = [
                self.app_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.app_list.count())
            ]
            save_settings(self.settings)
            if is_proxy_running():
                self.custom_restart_hint.setText("⚠ 删除程序需重启服务后生效，当前仍使用原设置")
                self.custom_restart_hint.setVisible(True)
            else:
                self.custom_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
                self.custom_restart_hint.setVisible(True)

    def _on_proxy_edit_toggle(self):
        if not self._proxy_editing:
            self._proxy_editing = True
            self.proxy_host_input.setReadOnly(False)
            self.proxy_port_input.setReadOnly(False)
            self.proxy_host_input.setStyleSheet(
                f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BLUE}; "
                f"border-radius: 4px; padding: 2px 6px; color: {COLOR_TEXT}; font-size: 9pt; font-family: Consolas; }}"
            )
            self.proxy_port_input.setStyleSheet(
                f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BLUE}; "
                f"border-radius: 4px; padding: 2px 6px; color: {COLOR_TEXT}; font-size: 9pt; font-family: Consolas; }}"
            )
            self.btn_edit_proxy.setText("确认")
            self.btn_edit_proxy.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_GREEN}; color: #FFFFFF; "
                f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 2px 10px; }}"
                f"QPushButton:hover {{ background-color: #388E3C; }}"
            )
            self.btn_copy_proxy.setText("取消")
            self.btn_copy_proxy.setStyleSheet(
                f"QPushButton {{ background-color: #666; color: #FFFFFF; "
                f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 2px 10px; }}"
                f"QPushButton:hover {{ background-color: #888; }}"
            )
            self.btn_copy_proxy.clicked.disconnect()
            self.btn_copy_proxy.clicked.connect(self._on_proxy_edit_cancel)
            self.proxy_host_input.setFocus()
            self.proxy_host_input.selectAll()
        else:
            self._on_proxy_edit_confirm()

    def _on_proxy_edit_confirm(self):
        global PROXY_HOST, PROXY_PORT
        new_host = self.proxy_host_input.text().strip()
        new_port_str = self.proxy_port_input.text().strip()
        if not new_host:
            self.proxy_host_input.setText(PROXY_HOST)
            return
        try:
            new_port = int(new_port_str)
            if not (1 <= new_port <= 65535):
                raise ValueError
        except ValueError:
            self.proxy_port_input.setText(str(PROXY_PORT))
            QMessageBox.warning(self, "端口无效", "端口号必须为 1-65535 之间的整数")
            return

        was_running = is_proxy_running()
        PROXY_HOST = new_host
        PROXY_PORT = new_port
        _update_proxy_url()
        self._save_setting("proxy_host", PROXY_HOST)
        self._save_setting("proxy_port", PROXY_PORT)
        log.info(f"代理地址已修改: {PROXY_URL}")

        self._proxy_exit_edit_mode()

        if was_running:
            self._on_stop()
            QTimer.singleShot(500, self._on_start)

    def _on_proxy_edit_cancel(self):
        self.proxy_host_input.setText(PROXY_HOST)
        self.proxy_port_input.setText(str(PROXY_PORT))
        self._proxy_exit_edit_mode()

    def _proxy_exit_edit_mode(self):
        self._proxy_editing = False
        self.proxy_host_input.setReadOnly(True)
        self.proxy_port_input.setReadOnly(True)
        self.proxy_host_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 4px; padding: 2px 6px; color: {COLOR_TEXT}; font-size: 9pt; font-family: Consolas; }}"
            f"QLineEdit[readOnly=\"true\"] {{ background-color: #0a0a0a; color: #888; }}"
        )
        self.proxy_port_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 4px; padding: 2px 6px; color: {COLOR_TEXT}; font-size: 9pt; font-family: Consolas; }}"
            f"QLineEdit[readOnly=\"true\"] {{ background-color: #0a0a0a; color: #888; }}"
        )
        self.btn_edit_proxy.setText("修改")
        self.btn_edit_proxy.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 2px 10px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        self.btn_copy_proxy.setText("复制")
        self.btn_copy_proxy.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 2px 10px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        try:
            self.btn_copy_proxy.clicked.disconnect()
        except Exception:
            pass
        self.btn_copy_proxy.clicked.connect(self._on_copy_proxy_addr)

    def _on_copy_proxy_addr(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(PROXY_URL)
        self.btn_copy_proxy.setText("已复制")
        QTimer.singleShot(1500, lambda: self.btn_copy_proxy.setText("复制"))

    def _on_browse_browser(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择浏览器", "", "可执行文件 (*.exe);;所有文件 (*.*)")
        if path:
            self._save_setting("browser_path", path)
            self.custom_browser_input.setText(path)
            self._update_browser_proxy_hint()
            log.info(f"已设置自定义浏览器: {path}")

    def _on_custom_radio_toggled(self, browser_type, checked):
        if not checked:
            return
        if browser_type == "system":
            self.custom_rb._block_signal = True
            self.custom_rb.setChecked(False)
            self.custom_rb._block_signal = False
        else:
            self.system_rb._block_signal = True
            self.system_rb.setChecked(False)
            self.system_rb._block_signal = False
        self._save_setting("browser_type", browser_type)
        self._update_browser_proxy_hint()
        self._update_browser_row_visibility()
        log.info(f"浏览器类型切换为: {browser_type}")

    def _update_browser_row_visibility(self):
        is_custom = self.settings.get("browser_type", "system") == "custom"
        self.system_browser_row_widget.setVisible(not is_custom)
        self.custom_browser_row_widget.setVisible(is_custom)

    def _on_custom_browser_input_changed(self, text):
        self._save_setting("browser_path", text.strip())
        self._update_browser_proxy_hint()

    def _on_system_browser_changed(self, idx):
        if idx >= 0:
            path = self.browser_combo.itemData(idx)
            self._save_setting("system_browser_path", path)
            self._update_browser_proxy_hint()

    def _on_export_log(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", f"yunji_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "文本文件 (*.txt)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                log.info(f"日志已导出到: {path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出日志失败: {e}")

    def _startup_download_config(self):
        if not self.quick_dir:
            return
        current_line = self.current_line
        quick_dir = self.quick_dir
        proxy_enabled = self.settings.get("proxy_enabled", False)
        def do_download():
            try:
                if proxy_enabled or is_proxy_running():
                    log.info("代理服务已启用或运行中，跳过启动时配置覆盖")
                    return
                downloaded = download_all_configs()
                if downloaded:
                    selected = None
                    if current_line:
                        for n, d in downloaded:
                            if n == current_line:
                                selected = (n, d)
                                break
                    if not selected:
                        selected = downloaded[0]
                    save_config(quick_dir, selected[1])
                    log.info(f"启动时已下载最新配置: {selected[0]}")
            except Exception as e:
                log.warning(f"启动时下载配置失败: {e}")
        import threading
        threading.Thread(target=do_download, daemon=True).start()

    def _switch_ver_tab(self, tab):
        if tab == self._ver_active_tab:
            return
        self._ver_active_tab = tab
        active_style = (
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        inactive_style = (
            f"QPushButton {{ background-color: #444; color: #888; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED}; }}"
        )
        if tab == "stable":
            self._ver_tab_stable_btn.setStyleSheet(active_style)
            self._ver_tab_git_btn.setStyleSheet(inactive_style)
        else:
            self._ver_tab_git_btn.setStyleSheet(active_style)
            self._ver_tab_stable_btn.setStyleSheet(inactive_style)
        self._render_active_tab()

    def _render_active_tab(self):
        if self._ver_scroll_content is None:
            return
        while self._ver_scroll_layout.count():
            item = self._ver_scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
        if self._ver_active_tab == "stable":
            self._render_stable_tab()
        else:
            self._render_git_tab()

    def _toggle_expand_all(self):
        self._ver_expanded = not self._ver_expanded
        if self._ver_expand_btn is not None:
            if self._ver_expanded:
                self._ver_expand_btn.setText("📋 收起详情")
                self._ver_expand_btn.setStyleSheet(
                    f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 6px; "
                    f"font-size: 8pt; font-weight: bold; }}"
                    f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
                )
            else:
                self._ver_expand_btn.setText("📋 展开详情")
                self._ver_expand_btn.setStyleSheet(
                    f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 6px; "
                    f"font-size: 8pt; font-weight: bold; }}"
                    f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
                )
        self._render_active_tab()

    def _render_stable_tab(self):
        current_v = next((v for v in self._ver_stable_data if v["version"] == self._ver_current_version), None)

        info_frame = QFrame()
        info_frame.setStyleSheet(f"background-color: #1a4a2a; border: 1px solid #2a6a3a; border-radius: 6px;")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setSpacing(4)

        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        ver_info_text = f"v{self._ver_current_version}  {self._ver_info_text}"
        info_label = QLabel(ver_info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: #FFFFFF; border: none;")
        info_row.addWidget(info_label, stretch=1)

        self._ver_info_expand_btn = QPushButton("▶ 详情")
        self._ver_info_expand_btn.setFixedSize(60, 22)
        self._ver_info_expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ver_info_expand_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 3px; "
            f"font-size: 8pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        self._ver_info_expand_btn.clicked.connect(self._toggle_current_version_detail)
        info_row.addWidget(self._ver_info_expand_btn)
        info_layout.addLayout(info_row)

        if current_v:
            changes = current_v.get("changes", [])
            if changes:
                desc_text = "、".join(changes[:3])
                if len(changes) > 3:
                    desc_text += f"等{len(changes)}项"
                desc_label = QLabel(desc_text)
                desc_label.setWordWrap(True)
                desc_label.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                info_layout.addWidget(desc_label)

            meta_parts = []
            build_time = current_v.get("build_time", "")
            if build_time:
                meta_parts.append(f"🕐 {build_time[:16]}")
            git_commit = current_v.get("git_commit", "")
            if git_commit:
                meta_parts.append(f"🔗 {git_commit[:8]}")
            if meta_parts:
                meta_label = QLabel("  ".join(meta_parts))
                meta_label.setStyleSheet(f"font-family: Consolas; font-size: 8pt; color: #EEEEEE; border: none;")
                info_layout.addWidget(meta_label)
        else:
            local_versions = self._get_local_version_history()
            latest_local = local_versions[0] if local_versions else None
            if latest_local:
                changes = latest_local.get("changes", [])
                if changes:
                    desc_text = "、".join(changes[:3])
                    if len(changes) > 3:
                        desc_text += f"等{len(changes)}项"
                    desc_label = QLabel(desc_text)
                    desc_label.setWordWrap(True)
                    desc_label.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                    info_layout.addWidget(desc_label)

                meta_parts = []
                build_time = latest_local.get("build_time", latest_local.get("date", ""))
                if build_time:
                    meta_parts.append(f"🕐 {build_time[:16]}")
                git_commit = latest_local.get("git_commit", "")
                if git_commit:
                    meta_parts.append(f"🔗 {git_commit[:8]}")
                if meta_parts:
                    meta_label = QLabel("  ".join(meta_parts))
                    meta_label.setStyleSheet(f"font-family: Consolas; font-size: 8pt; color: #EEEEEE; border: none;")
                    info_layout.addWidget(meta_label)

        self._ver_info_detail_frame = None

        self._ver_scroll_layout.addWidget(info_frame)

        self._render_stable_versions(self._ver_stable_data, self._ver_current_version)

    def _toggle_current_version_detail(self):
        if self._ver_info_detail_frame is not None:
            self._ver_info_detail_frame.deleteLater()
            self._ver_info_detail_frame = None
            if self._ver_info_expand_btn:
                self._ver_info_expand_btn.setText("▶ 详情")
            return

        current_v = next((v for v in self._ver_stable_data if v["version"] == self._ver_current_version), None)
        if not current_v:
            local_versions = self._get_local_version_history()
            current_v = local_versions[0] if local_versions else None
        if not current_v:
            return

        detail = QFrame()
        detail.setStyleSheet("background-color: #1a4a2a; border: 1px solid #2a6a3a; border-radius: 4px;")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(12, 6, 12, 6)
        detail_layout.setSpacing(2)

        changes = current_v.get("changes", [])
        if changes:
            for ch in changes:
                lbl = QLabel(f"· {ch}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                detail_layout.addWidget(lbl)
        else:
            lbl = QLabel("暂无修改记录")
            lbl.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
            detail_layout.addWidget(lbl)

        git_commit = current_v.get("git_commit", "")
        if git_commit:
            lbl = QLabel(f"🔗 commit: {git_commit}")
            lbl.setStyleSheet(f"font-family: Consolas; font-size: 8pt; color: #EEEEEE; border: none;")
            detail_layout.addWidget(lbl)

        build_time = current_v.get("build_time", current_v.get("date", ""))
        if build_time:
            lbl = QLabel(f"🕐 构建时间: {build_time}")
            lbl.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
            detail_layout.addWidget(lbl)

        self._ver_info_detail_frame = detail
        self._ver_scroll_layout.insertWidget(1, detail)

        if self._ver_info_expand_btn:
            self._ver_info_expand_btn.setText("▼ 详情")

    def _render_git_tab(self):
        git_header = QFrame()
        git_header.setStyleSheet(f"background-color: {COLOR_BG}; border: none;")
        git_header_layout = QHBoxLayout(git_header)
        git_header_layout.setContentsMargins(4, 6, 4, 2)
        git_title = QLabel("🔧 远程仓库开发动态")
        git_title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_BLUE_LIGHT}; border: none;")
        git_header_layout.addWidget(git_title)
        git_header_layout.addStretch()
        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedSize(60, 24)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(
            f"QPushButton {{ background-color: #2a2a2a; color: #EEEEEE; border: none; border-radius: 4px; "
            f"font-size: 9pt; }}"
            f"QPushButton:hover {{ background-color: #3a3a3a; }}"
        )
        refresh_btn.clicked.connect(self._refresh_git_history)
        git_header_layout.addWidget(refresh_btn)
        self._ver_scroll_layout.addWidget(git_header)

        if not self._ver_git_data:
            loading_lbl = QLabel("正在加载开发动态...")
            loading_lbl.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM}; border: none;")
            loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._ver_scroll_layout.addWidget(loading_lbl)
            QTimer.singleShot(100, self._fetch_remote_commits)
        else:
            self._render_git_history(self._ver_git_data)

    def _toggle_card_detail(self, card, data, card_type):
        detail_widget = card.findChild(QWidget, "_detail")
        if detail_widget is not None:
            detail_widget.deleteLater()
            toggle_btn = card.findChild(QPushButton, "_toggle_btn")
            if toggle_btn:
                toggle_btn.setText("▶")
            return

        card_bg = card.property("card_bg") or "#161616"
        detail = QFrame()
        detail.setObjectName("_detail")
        detail.setStyleSheet(f"background-color: {card_bg}; border: none;")
        detail_layout = QVBoxLayout(detail)
        left_margin = 140 if card_type == "stable" else 10
        detail_layout.setContentsMargins(left_margin, 0, 10, 6)
        detail_layout.setSpacing(2)

        if card_type == "stable":
            git_commit = data.get("git_commit", "")
            if git_commit:
                lbl = QLabel(f"🔗 commit: {git_commit}")
                lbl.setStyleSheet(f"font-family: Consolas; font-size: 9pt; color: #EEEEEE; border: none;")
                detail_layout.addWidget(lbl)
            changes = data.get("changes", [])
            if changes:
                for ch in changes:
                    lbl = QLabel(f"· {ch}")
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                    detail_layout.addWidget(lbl)
            else:
                lbl = QLabel("暂无修改记录")
                lbl.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                detail_layout.addWidget(lbl)
        else:
            message = data.get("message", "")
            msg_lines = message.split("\n") if message else []
            for line in msg_lines:
                line = line.strip()
                if line:
                    lbl = QLabel(f"· {line}")
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                    detail_layout.addWidget(lbl)
            author = data.get("author", "")
            if author:
                lbl2 = QLabel(f"👤 {author}")
                lbl2.setStyleSheet(f"font-size: 9pt; color: #EEEEEE; border: none;")
                detail_layout.addWidget(lbl2)

        card_layout = card.layout()
        card_layout.addWidget(detail)

        toggle_btn = card.findChild(QPushButton, "_toggle_btn")
        if toggle_btn:
            toggle_btn.setText("▼")

    def _render_stable_versions(self, all_versions, current_version):
        if not all_versions:
            lbl = QLabel("暂无稳定版本")
            lbl.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM}; border: none;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._ver_scroll_layout.addWidget(lbl)
            return

        expanded = self._ver_expanded

        header_row = QFrame()
        header_row.setStyleSheet("background-color: #1a1a1a; border: none; border-bottom: 1px solid #2a2a2a;")
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.setSpacing(0)

        for text, width, stretch in [("版本", 130, 0), ("描述", 0, 1), ("状态", 100, 0), ("操作", 120, 0)]:
            lbl = QLabel(text)
            if width > 0:
                lbl.setFixedWidth(width)
            lbl.setStyleSheet("font-size: 8pt; color: #FFFFFF; border: none; font-weight: bold;")
            header_layout.addWidget(lbl, stretch=stretch)

        self._ver_scroll_layout.addWidget(header_row)

        current_v = None
        other_versions = []
        for v in all_versions:
            if v["version"] == current_version:
                current_v = v
            else:
                other_versions.append(v)

        ordered = []
        if current_v:
            ordered.append(current_v)
        ordered.extend(other_versions)

        for v in ordered:
            ver = v["version"]
            is_current = (ver == current_version)
            is_available = v.get("available", False)
            is_remote_new = v.get("is_remote_new", False)
            changes = v.get("changes", [])
            exe_info = v.get("exe_info")

            if is_current:
                row_bg = "#1a4a2a"
                border_color = "#2a6a3a"
            elif is_remote_new:
                row_bg = "#161620"
                border_color = "#1f3a4f"
            elif is_available:
                row_bg = "#161616"
                border_color = "#222"
            else:
                row_bg = "#111"
                border_color = "#1a1a1a"

            card = QFrame()
            card.setProperty("card_bg", row_bg)
            card.setStyleSheet(
                f"background-color: {row_bg}; border: 1px solid {border_color}; border-radius: 0px;"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(0)

            row = QFrame()
            row.setStyleSheet(f"background-color: {row_bg}; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 5, 10, 5)
            row_layout.setSpacing(6)

            ver_color = "#4CAF50" if is_current else ("#42A5F5" if is_remote_new else (COLOR_TEXT if is_available else COLOR_DIM))
            ver_label = QLabel(f"v{ver}")
            ver_label.setFixedWidth(130)
            ver_font_size = "11pt" if is_current else "9pt"
            ver_label.setStyleSheet(f"font-family: Consolas; font-size: {ver_font_size}; font-weight: bold; color: {ver_color}; border: none;")
            row_layout.addWidget(ver_label)

            desc_text = ""
            if changes:
                if expanded:
                    desc_text = "、".join(changes)
                else:
                    desc_text = "、".join(changes[:2])
                    if len(changes) > 2:
                        desc_text += f"等{len(changes)}项"
                    if len(desc_text) > 40:
                        desc_text = desc_text[:37] + "..."

            desc_label = QLabel(desc_text if desc_text else "暂无描述")
            desc_label.setWordWrap(True)
            desc_color = "#EEEEEE"
            desc_label.setStyleSheet(f"font-size: 8pt; color: {desc_color}; border: none;")
            row_layout.addWidget(desc_label, stretch=1)

            status_label = QLabel("")
            status_label.setFixedWidth(100)
            if is_current:
                status_label.setText("● 当前版本")
                status_label.setStyleSheet(f"font-size: 8pt; color: #4CAF50; border: none; font-weight: bold;")
            elif is_remote_new:
                status_label.setText("🆕 远程新版")
                status_label.setStyleSheet(f"font-size: 8pt; color: #42A5F5; border: none;")
            elif is_available and exe_info:
                size_text = f" {exe_info.get('size_mb', '')}MB" if exe_info.get("size_mb") else ""
                status_label.setText(f"📦 稳定版{size_text}")
                status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_ORANGE}; border: none;")
            else:
                status_label.setText("—")
                status_label.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
            row_layout.addWidget(status_label)

            action_frame = QFrame()
            action_frame.setFixedWidth(120)
            action_frame.setStyleSheet(f"background-color: {row_bg}; border: none;")
            action_layout = QHBoxLayout(action_frame)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(4)

            btn_style_blue = (
                f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 3px; "
                f"font-size: 8pt; font-weight: bold; padding: 2px 8px; }}"
                f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
            )

            btn_style_red = (
                f"QPushButton {{ background-color: {COLOR_RED}; color: #fff; border: none; border-radius: 3px; "
                f"font-size: 8pt; font-weight: bold; padding: 2px 8px; }}"
                f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
            )

            if is_available and exe_info and not is_current:
                switch_btn = QPushButton("🔄 切换")
                switch_btn.setFixedSize(60, 22)
                switch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                switch_btn.setStyleSheet(btn_style_red)
                exe_path = exe_info["path"]
                git_commit = v.get("git_commit", "")
                switch_btn.clicked.connect(lambda checked, p=exe_path, gc=git_commit: self._switch_to_exe(p, gc))
                action_layout.addWidget(switch_btn)
            elif is_remote_new:
                dl_btn = QPushButton("📥 下载")
                dl_btn.setFixedSize(60, 22)
                dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                dl_btn.setStyleSheet(btn_style_blue)
                rinfo = v.get("remote_info")
                dl_btn.clicked.connect(lambda checked, ri=rinfo: self._on_download_version(ri))
                action_layout.addWidget(dl_btn)

            has_detail = bool(changes) or bool(v.get("git_commit", ""))
            if has_detail:
                toggle_text = "▼" if expanded else "▶"
                toggle_btn = QPushButton(toggle_text)
                toggle_btn.setObjectName("_toggle_btn")
                toggle_btn.setFixedSize(24, 22)
                toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                toggle_btn.setStyleSheet(
                    f"QPushButton {{ background-color: {row_bg}; color: #EEEEEE; border: none; border-radius: 3px; "
                    f"font-size: 8pt; }}"
                    f"QPushButton:hover {{ background-color: #2a2a2a; }}"
                )
                v_data = v
                toggle_btn.clicked.connect(lambda checked, c=card, d=v_data: self._toggle_card_detail(c, d, "stable"))
                action_layout.addWidget(toggle_btn)

            action_layout.addStretch()
            row_layout.addWidget(action_frame)

            card_layout.addWidget(row)

            if expanded and has_detail:
                detail = QFrame()
                detail.setObjectName("_detail")
                detail.setStyleSheet(f"background-color: {row_bg}; border: none;")
                detail_layout = QVBoxLayout(detail)
                detail_layout.setContentsMargins(140, 0, 10, 6)
                detail_layout.setSpacing(2)

                git_commit = v.get("git_commit", "")
                if git_commit:
                    lbl = QLabel(f"🔗 commit: {git_commit}")
                    lbl.setStyleSheet(f"font-family: Consolas; font-size: 9pt; color: #EEEEEE; border: none;")
                    detail_layout.addWidget(lbl)

                if changes:
                    for ch in changes:
                        lbl = QLabel(f"· {ch}")
                        lbl.setWordWrap(True)
                        lbl.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                        detail_layout.addWidget(lbl)
                else:
                    lbl = QLabel("暂无修改记录")
                    lbl.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                    detail_layout.addWidget(lbl)

                card_layout.addWidget(detail)

            self._ver_scroll_layout.addWidget(card)

    def _render_git_history(self, commits):
        if not commits:
            lbl = QLabel("暂无开发动态")
            lbl.setStyleSheet(f"font-size: 9pt; color: #EEEEEE; border: none;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._ver_scroll_layout.addWidget(lbl)
            return

        expanded = self._ver_expanded
        stable_exes = self._list_stable_exes()
        exe_versions = {e["version"]: e for e in stable_exes}

        header_row = QFrame()
        header_row.setStyleSheet("background-color: #1a1a1a; border: none; border-bottom: 1px solid #2a2a2a;")
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.setSpacing(0)

        for text, width, stretch in [("版本", 130, 0), ("描述", 0, 1), ("状态", 100, 0), ("操作", 120, 0)]:
            lbl = QLabel(text)
            if width > 0:
                lbl.setFixedWidth(width)
            lbl.setStyleSheet("font-size: 8pt; color: #FFFFFF; border: none; font-weight: bold;")
            header_layout.addWidget(lbl, stretch=stretch)

        self._ver_scroll_layout.addWidget(header_row)

        for commit in commits:
            sha = commit.get("sha", "")[:8]
            full_sha = commit.get("sha", "")
            message = commit.get("message", "")
            author = commit.get("author", "")
            date_str = commit.get("date", "")
            if date_str and "T" in date_str:
                date_str = date_str.split("T")[0]

            msg_first_line = message.split("\n")[0] if message else ""

            matched_exe = None
            for ver, exe in exe_versions.items():
                if full_sha and full_sha.startswith(ver) or ver.startswith(full_sha[:8]):
                    matched_exe = exe
                    break

            row_bg = "#161616"
            border_color = "#2a2a2a"

            card = QFrame()
            card.setProperty("card_bg", row_bg)
            card.setStyleSheet(
                f"background-color: {row_bg}; border: 1px solid {border_color}; border-radius: 0px;"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(0)

            row = QFrame()
            row.setStyleSheet(f"background-color: {row_bg}; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 5, 10, 5)
            row_layout.setSpacing(6)

            ver_label = QLabel(sha)
            ver_label.setFixedWidth(130)
            ver_label.setStyleSheet(f"font-family: Consolas; font-size: 9pt; font-weight: bold; color: #42A5F5; border: none;")
            row_layout.addWidget(ver_label)

            desc_text = msg_first_line
            if not expanded and len(desc_text) > 40:
                desc_text = desc_text[:37] + "..."

            desc_label = QLabel(desc_text if desc_text else "暂无描述")
            desc_label.setWordWrap(True)
            desc_color = "#EEEEEE"
            desc_label.setStyleSheet(f"font-size: 8pt; color: {desc_color}; border: none;")
            row_layout.addWidget(desc_label, stretch=1)

            status_label = QLabel("")
            status_label.setFixedWidth(100)
            if date_str:
                status_label.setText(f"📅 {date_str}")
                status_label.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
            else:
                status_label.setText("—")
                status_label.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
            row_layout.addWidget(status_label)

            action_frame = QFrame()
            action_frame.setFixedWidth(120)
            action_frame.setStyleSheet(f"background-color: {row_bg}; border: none;")
            action_layout = QHBoxLayout(action_frame)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(4)

            btn_style_blue = (
                f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 3px; "
                f"font-size: 8pt; font-weight: bold; padding: 2px 8px; }}"
                f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
            )

            btn_style_red = (
                f"QPushButton {{ background-color: {COLOR_RED}; color: #fff; border: none; border-radius: 3px; "
                f"font-size: 8pt; font-weight: bold; padding: 2px 8px; }}"
                f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
            )

            if matched_exe:
                switch_btn = QPushButton("🔄 切换")
                switch_btn.setFixedSize(60, 22)
                switch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                switch_btn.setStyleSheet(btn_style_red)
                exe_path = matched_exe["path"]
                switch_btn.clicked.connect(lambda checked, p=exe_path: self._switch_to_exe(p, ""))
                action_layout.addWidget(switch_btn)

            has_detail = len(message.split("\n")) > 1 or bool(author)
            if has_detail:
                toggle_text = "▼" if expanded else "▶"
                toggle_btn = QPushButton(toggle_text)
                toggle_btn.setObjectName("_toggle_btn")
                toggle_btn.setFixedSize(24, 22)
                toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                toggle_btn.setStyleSheet(
                    f"QPushButton {{ background-color: {row_bg}; color: #EEEEEE; border: none; border-radius: 3px; "
                    f"font-size: 8pt; }}"
                    f"QPushButton:hover {{ background-color: #2a2a2a; }}"
                )
                toggle_btn.clicked.connect(lambda checked, c=card, d=commit: self._toggle_card_detail(c, d, "git"))
                action_layout.addWidget(toggle_btn)

            action_layout.addStretch()
            row_layout.addWidget(action_frame)

            card_layout.addWidget(row)

            if expanded and has_detail:
                detail = QFrame()
                detail.setObjectName("_detail")
                detail.setStyleSheet(f"background-color: {row_bg}; border: none;")
                detail_layout = QVBoxLayout(detail)
                detail_layout.setContentsMargins(140, 0, 10, 6)
                detail_layout.setSpacing(2)

                msg_lines = message.split("\n") if message else []
                for line in msg_lines:
                    line = line.strip()
                    if line:
                        lbl = QLabel(f"· {line}")
                        lbl.setWordWrap(True)
                        lbl.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                        detail_layout.addWidget(lbl)

                if author:
                    lbl2 = QLabel(f"👤 {author}")
                    lbl2.setStyleSheet(f"font-size: 8pt; color: #EEEEEE; border: none;")
                    detail_layout.addWidget(lbl2)

                card_layout.addWidget(detail)

            self._ver_scroll_layout.addWidget(card)

    def _fetch_remote_commits(self):
        def do_fetch():
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                data = None
                gitee_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/commits?per_page=20"
                if GITEE_TOKEN:
                    gitee_url += f"&access_token={GITEE_TOKEN}"
                try:
                    req = urllib.request.Request(gitee_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                        data = json.loads(resp.read().decode())
                except Exception:
                    pass

                if data is None:
                    github_url = f"https://api.github.com/repos/{GITHUB_REPO}/commits?per_page=20"
                    headers = {"User-Agent": "Mozilla/5.0"}
                    if GITHUB_TOKEN:
                        headers["Authorization"] = f"token {GITHUB_TOKEN}"
                    req = urllib.request.Request(github_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                        data = json.loads(resp.read().decode())

                commits = []
                for c in data:
                    commit_info = c.get("commit", {})
                    commits.append({
                        "sha": c.get("sha", ""),
                        "message": commit_info.get("message", ""),
                        "author": commit_info.get("author", {}).get("name", ""),
                        "date": commit_info.get("author", {}).get("date", ""),
                    })
                self._ver_git_data = commits
                self._version_data_ready.emit()
            except Exception:
                self._ver_git_data = []
                self._version_data_ready.emit()

        threading.Thread(target=do_fetch, daemon=True).start()

    def _refresh_git_history(self):
        self._ver_git_data = []
        if self._ver_active_tab == "git":
            self._render_active_tab()
            self._fetch_remote_commits()

    def _get_project_root(self):
        return os.path.dirname(_find_dev_dir())

    def _get_dev_dir(self):
        return _find_dev_dir()

    def _list_stable_exes(self):
        dev_dir = self._get_dev_dir()
        ver_dir = os.path.join(dev_dir, "ver")
        if not os.path.isdir(ver_dir):
            return []
        exes = []
        for f in os.listdir(ver_dir):
            if f.endswith(".exe") and "云集智能网联代理专家" in f:
                path = os.path.join(ver_dir, f)
                m = re.search(r'v(\d+\.\d+\.\d+\.\d+)', f)
                ver = m.group(1) if m else "unknown"
                size_mb = round(os.path.getsize(path) / (1024 * 1024), 1)
                exes.append({"filename": f, "path": path, "version": ver, "size_mb": size_mb})
        exes.sort(key=lambda x: x["version"], reverse=True)
        return exes

    def _get_local_version_history(self):
        dev_dir = self._get_dev_dir()
        path = os.path.join(dev_dir, "app", "version_history.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return []
        except Exception:
            return []

    def _on_version_data_ready(self):
        self._render_active_tab()
        if self._ver_status_label is not None:
            count = len(self._ver_stable_data)
            hist = len(self._ver_git_data)
            self._ver_status_label.setText(f"稳定版 {count} 个 | 版本历史 {hist} 条")

    def _load_all_versions(self):
        if self._ver_status_label is not None:
            self._ver_status_label.setText("正在加载版本信息...")

        def do_load():
            stable_exes = self._list_stable_exes()
            exe_versions = {e["version"]: e for e in stable_exes}
            local_versions = self._get_local_version_history()

            current_version = VERSION
            all_versions = []
            seen = set()

            for v in local_versions:
                ver = v.get("version", "")
                ver_num = self._normalize_version(ver)
                if not ver_num or ver_num in seen:
                    continue
                seen.add(ver_num)
                all_versions.append({
                    "version": ver_num,
                    "name": v.get("name", f"v{ver_num}"),
                    "changes": v.get("changes", []),
                    "build_time": v.get("build_time", v.get("date", "")),
                    "git_commit": v.get("git_commit", ""),
                    "available": ver_num in exe_versions,
                    "exe_info": exe_versions.get(ver_num),
                    "is_remote_new": False,
                })

            for ver, exe in exe_versions.items():
                if ver not in seen:
                    seen.add(ver)
                    all_versions.append({
                        "version": ver,
                        "name": exe["filename"],
                        "changes": [],
                        "build_time": "",
                        "git_commit": "",
                        "available": True,
                        "exe_info": exe,
                        "is_remote_new": False,
                    })

            all_versions.sort(key=lambda x: x["version"], reverse=True)
            self._ver_stable_data = all_versions
            self._ver_git_data = []
            self._ver_current_version = current_version
            self._version_data_ready.emit()

        threading.Thread(target=do_load, daemon=True).start()

    def _normalize_version(self, ver_str):
        m = re.search(r'v?(\d+\.\d+\.\d+(?:\.\d+)?)', ver_str)
        return m.group(1) if m else ""

    def _check_remote_versions(self):
        if self._ver_status_label is not None:
            self._ver_status_label.setText("正在检查远程更新...")

        def _fetch_version_json():
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            result = [None, None]

            def try_gitee():
                try:
                    gitee_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/contents/ver/version.json?ref=main"
                    if GITEE_TOKEN:
                        gitee_url += f"&access_token={GITEE_TOKEN}"
                    req = urllib.request.Request(gitee_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
                        raw = resp.read().decode()
                    api_data = json.loads(raw)
                    if isinstance(api_data, list):
                        file_data = api_data[0] if api_data else {}
                    else:
                        file_data = api_data
                    import base64
                    content_b64 = file_data.get("content", "")
                    result[0] = (json.loads(base64.b64decode(content_b64).decode("utf-8")), "gitee")
                except Exception:
                    result[0] = (None, None)

            def try_github():
                try:
                    github_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/ver/version.json?ref=main"
                    gh_headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"}
                    if GITHUB_TOKEN:
                        gh_headers["Authorization"] = f"token {GITHUB_TOKEN}"
                    req = urllib.request.Request(github_url, headers=gh_headers)
                    with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
                        raw = resp.read().decode()
                    api_data = json.loads(raw)
                    import base64
                    content_b64 = api_data.get("content", "")
                    result[1] = (json.loads(base64.b64decode(content_b64).decode("utf-8")), "github")
                except Exception:
                    try:
                        github_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/ver/version.json"
                        req = urllib.request.Request(github_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
                            result[1] = (json.loads(resp.read().decode()), "github")
                    except Exception:
                        result[1] = (None, None)

            t1 = threading.Thread(target=try_gitee, daemon=True)
            t2 = threading.Thread(target=try_github, daemon=True)
            t1.start()
            t2.start()
            t1.join(timeout=8)
            t2.join(timeout=8)

            if result[0] and result[0][0] is not None:
                return result[0]
            if result[1] and result[1][0] is not None:
                return result[1]
            return None, None

        def do_check():
            try:
                data, source = _fetch_version_json()
                if data is None:
                    self._ver_info_text = "❌ 无法连接远程仓库"
                    self._version_data_ready.emit()
                    return

                self._ver_source = source

                remote_latest = data.get("latest", "")
                remote_versions_list = data.get("versions", [])

                stable_exes = self._list_stable_exes()
                exe_versions = {e["version"]: e for e in stable_exes}
                local_versions = self._get_local_version_history()

                current_version = VERSION
                all_versions = []
                seen = set()

                for rinfo in remote_versions_list:
                    rv = rinfo.get("version", "")
                    ver_num = self._normalize_version(rv)
                    if not ver_num or ver_num in seen:
                        continue
                    seen.add(ver_num)
                    is_new = (ver_num != current_version and ver_num not in exe_versions)
                    all_versions.append({
                        "version": ver_num,
                        "name": rinfo.get("name", f"v{ver_num}"),
                        "changes": rinfo.get("changes", []),
                        "build_time": rinfo.get("build_time", rinfo.get("date", "")),
                        "git_commit": rinfo.get("git_commit", ""),
                        "available": ver_num in exe_versions,
                        "exe_info": exe_versions.get(ver_num),
                        "is_remote_new": is_new,
                        "remote_info": rinfo,
                    })

                for v in local_versions:
                    ver = v.get("version", "")
                    ver_num = self._normalize_version(ver)
                    if not ver_num or ver_num in seen:
                        continue
                    seen.add(ver_num)
                    all_versions.append({
                        "version": ver_num,
                        "name": v.get("name", f"v{ver_num}"),
                        "changes": v.get("changes", []),
                        "build_time": v.get("build_time", v.get("date", "")),
                        "git_commit": v.get("git_commit", ""),
                        "available": ver_num in exe_versions,
                        "exe_info": exe_versions.get(ver_num),
                        "is_remote_new": False,
                    })

                for ver, exe in exe_versions.items():
                    if ver not in seen:
                        seen.add(ver)
                        all_versions.append({
                            "version": ver,
                            "name": exe["filename"],
                            "changes": [],
                            "build_time": "",
                            "git_commit": "",
                            "available": True,
                            "exe_info": exe,
                            "is_remote_new": False,
                        })

                all_versions.sort(key=lambda x: x["version"], reverse=True)

                self._latest_version = remote_latest
                self._latest_info = next((v for v in remote_versions_list if v.get("version") == remote_latest), None)

                self._ver_stable_data = all_versions
                self._ver_git_data = []
                self._ver_current_version = current_version
                has_update = remote_latest and remote_latest != VERSION and remote_latest not in exe_versions
                if has_update:
                    self._ver_info_text = f"🆕 发现新版本 v{remote_latest}"
                else:
                    self._ver_info_text = "✅ 已是最新版本"
                self._version_data_ready.emit()
            except Exception as e:
                err_msg = str(e)[:80]
                self._load_all_versions()

        threading.Thread(target=do_check, daemon=True).start()

    def _on_download_version(self, remote_info):
        if not remote_info:
            return
        filename = remote_info.get("filename", "")
        if not filename:
            return
        dev_dir = self._get_dev_dir()
        ver_dir = os.path.join(dev_dir, "ver")
        os.makedirs(ver_dir, exist_ok=True)
        save_path = os.path.join(ver_dir, filename)
        if os.path.isfile(save_path):
            self._switch_to_exe(save_path, remote_info.get("git_commit", ""))
            return
        url = f"https://gitee.com/{GITEE_REPO}/releases/download/v{remote_info.get('version', '')}/{filename}"
        source = getattr(self, '_ver_source', 'gitee')
        if source == "github":
            url = f"https://github.com/{GITHUB_REPO}/releases/download/v{remote_info.get('version', '')}/{filename}"
        if hasattr(self, '_download_worker') and self._download_worker is not None and self._download_worker.isRunning():
            QMessageBox.information(self, "提示", "已有下载任务进行中")
            return
        self._download_worker = DownloadWorker(url, save_path)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        if self._ver_status_label is not None:
            self._ver_status_label.setText("正在下载 0%...")
        self._download_worker.start()

    def _on_download_progress(self, downloaded, total):
        if self._ver_status_label is not None:
            if total > 0:
                pct = int(downloaded * 100 / total)
                mb_d = downloaded / 1024 / 1024
                mb_t = total / 1024 / 1024
                self._ver_status_label.setText(f"正在下载 {pct}% ({mb_d:.1f}/{mb_t:.1f} MB)")
            else:
                mb_d = downloaded / 1024 / 1024
                self._ver_status_label.setText(f"正在下载 {mb_d:.1f} MB")

    def _on_download_finished(self, ok, msg, path):
        if self._ver_status_label is not None:
            self._ver_status_label.setText(msg if ok else f"下载失败")
        if ok and path:
            reply = QMessageBox.question(
                self, "下载完成",
                f"{msg}\n\n是否立即切换到该版本？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._switch_to_exe(path)
        elif not ok:
            QMessageBox.warning(self, "下载失败", msg)

    def _switch_to_exe(self, exe_path, git_commit=""):
        if not os.path.exists(exe_path):
            QMessageBox.critical(self, "错误", f"版本文件不存在:\n{exe_path}")
            return

        dev_dir = self._get_dev_dir()
        ver_dir = os.path.join(dev_dir, "ver")
        os.makedirs(ver_dir, exist_ok=True)

        target_filename = os.path.basename(exe_path)
        target_in_ver = os.path.join(ver_dir, target_filename)
        if os.path.normpath(exe_path) != os.path.normpath(target_in_ver):
            if not os.path.isfile(target_in_ver):
                shutil.copy2(exe_path, target_in_ver)

        entry_exe = os.path.join(dev_dir, "云集智能网联代理专家.exe")
        my_pid = os.getpid()

        bat_path = os.path.join(dev_dir, "_switch_version.bat")
        with open(bat_path, "w", encoding="gbk") as f:
            f.write("@echo off\n")
            f.write("chcp 65001 >nul 2>&1\n")
            f.write(f"set MY_PID={my_pid}\n")
            f.write(f"set ENTRY_EXE={entry_exe}\n")
            f.write(f"set TARGET_EXE={target_in_ver}\n")
            f.write("set MAX_WAIT=30\n")
            f.write("set WAITED=0\n")
            f.write(":wait_loop\n")
            f.write("tasklist /FI \"PID eq %MY_PID%\" 2>nul | find \"%MY_PID%\" >nul\n")
            f.write("if %ERRORLEVEL%==0 (\n")
            f.write("    set /a WAITED+=1\n")
            f.write("    if %WAITED% GEQ %MAX_WAIT% (\n")
            f.write("        taskkill /PID %MY_PID% /F >nul 2>&1\n")
            f.write("        timeout /t 2 /nobreak >nul\n")
            f.write("    ) else (\n")
            f.write("        timeout /t 1 /nobreak >nul\n")
            f.write("        goto wait_loop\n")
            f.write("    )\n")
            f.write(")\n")
            f.write("if exist \"%ENTRY_EXE%\" del /f /q \"%ENTRY_EXE%\"\n")
            f.write("mklink /H \"%ENTRY_EXE%\" \"%TARGET_EXE%\" >nul 2>&1\n")
            f.write("if not exist \"%ENTRY_EXE%\" (\n")
            f.write("    copy /y \"%TARGET_EXE%\" \"%ENTRY_EXE%\" >nul\n")
            f.write(")\n")
            f.write("start \"\" \"%ENTRY_EXE%\"\n")
            f.write("del /f /q \"%~f0\"\n")

        subprocess.Popen(
            f'cmd /c "{bat_path}"',
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            cwd=dev_dir,
        )
        self.close()

    def _on_check_update(self):
        self._check_remote_versions()

    def _on_download_update(self):
        if not hasattr(self, '_latest_info') or not self._latest_info:
            return
        self._on_download_version(self._latest_info)

    def _on_update_config(self):
        if not self.quick_dir:
            return
        self.worker = ServiceWorker("update_config", quick_dir=self.quick_dir, current_line=self.current_line)
        self.worker.progress.connect(lambda t: self.update_status.setText(t))
        self.worker.finished.connect(self._on_update_config_finished)
        self.worker.start()

    def _on_update_config_finished(self, ok, msg):
        self.update_status.setText(msg)
        self.update_status.setStyleSheet(f"color: {COLOR_GREEN};" if ok else "color: #FF6B80;")
        if ok:
            self._save_setting("last_config_update_date", date.today().isoformat())

    def _on_update_quick(self):
        if not self.quick_dir:
            QMessageBox.warning(self, "提示", "未找到代理内核目录")
            return
        if hasattr(self, '_kernel_worker') and self._kernel_worker and self._kernel_worker.isRunning():
            QMessageBox.information(self, "提示", "内核更新正在进行中")
            return
        was_running = is_proxy_running()
        if was_running:
            stop_quick()
            time.sleep(0.5)
        self.update_status.setText("正在检查内核更新...")
        self.update_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        self._kernel_worker = KernelUpdateWorker(self.quick_dir)
        self._kernel_worker.progress.connect(lambda t: (
            self.update_status.setText(t),
            self.update_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        ))
        self._kernel_worker.finished.connect(lambda ok, msg: self._on_kernel_update_finished(ok, msg, was_running))
        self._kernel_worker.start()

    def _on_kernel_update_finished(self, ok, msg, was_running):
        self.update_status.setText(msg)
        self.update_status.setStyleSheet(f"color: {COLOR_GREEN};" if ok else "color: #FF6B80;")
        if ok:
            self.svc_kernel_label.setText(f"内核: {self._get_quick_version() or '未知'}")
            if was_running and self.settings.get("proxy_enabled", False):
                self._on_start()
        else:
            if was_running and self.settings.get("proxy_enabled", False):
                start_quick(self.quick_dir)

    def closeEvent(self, event):
        self._stop_auto_line_timer()
        self._stop_realtime_monitor()
        self.monitor.stop()
        self.monitor.wait()
        event.accept()

    def _finish_splash(self):
        if self._splash and self._splash.isVisible():
            self.show()
            self._splash.finish(self)
            self._splash = None

def _global_exception_handler(exc_type, exc_value, exc_tb):
    import traceback
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.critical(f"未捕获异常:\n{tb_text}")
    try:
        from PyQt6.QtWidgets import QMessageBox
        app = QApplication.instance()
        if app:
            QMessageBox.critical(None, "程序异常", f"发生未预期的错误:\n\n{exc_value}\n\n详细信息已记录到日志。")
    except Exception:
        pass


def main():
    sys.excepthook = _global_exception_handler
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLOR_CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLOR_BORDER))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLOR_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_RED))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    splash = SplashScreen()
    screen = app.primaryScreen().geometry()
    splash.move((screen.width() - splash.width()) // 2,
                (screen.height() - splash.height()) // 2)
    splash.show()
    splash.repaint()
    app.processEvents()

    splash.set_progress(0.1, "正在创建主窗口...")
    app.processEvents()

    window = MainWindow(splash=splash)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
