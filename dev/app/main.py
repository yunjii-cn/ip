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
import ctypes
import queue
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame,
    QFileDialog, QMessageBox, QListWidget,
    QListWidgetItem, QTextEdit, QComboBox, QSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPixmap, QIcon, QFont, QColor, QPainter, QPen, QFontMetrics

VERSION = datetime.now().strftime("%Y.%m.%d.%H%M")
VERSION_CHECK_URL = "https://gitee.com/yunjii/ip/raw/master/ver/version.json"
VERSION_DOWNLOAD_URL = "https://gitee.com/yunjii/ip/raw/master/ver/"
APP_NAME = f"云集智能网联代理专家 v{VERSION}"
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 7890
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
QLabel#title {{ color: {COLOR_RED_LIGHT}; font-size: 14pt; font-weight: bold; }}
QLabel#subtitle {{ color: {COLOR_DIM}; font-size: 8pt; }}
QLabel#status-on {{ color: {COLOR_GREEN}; font-size: 11pt; font-weight: bold; }}
QLabel#status-off {{ color: {COLOR_TEXT}; font-size: 11pt; font-weight: bold; }}
QLabel#latency {{ color: {COLOR_GREEN}; font-size: 10pt; font-weight: bold; }}
QLabel#restart-hint {{ color: {COLOR_ORANGE}; font-size: 8pt; }}

QPushButton {{ background-color: #2D2D2D; color: {COLOR_TEXT}; border: none; border-radius: 4px; padding: 8px 16px; font-size: 10pt; font-weight: bold; }}
QPushButton:hover {{ background-color: #3A3A3A; }}
QPushButton#start {{ background-color: {COLOR_RED}; color: #FFFFFF; font-size: 12pt; padding: 12px; }}
QPushButton#start:hover {{ background-color: {COLOR_RED_LIGHT}; }}
QPushButton#stop {{ background-color: {COLOR_BLUE}; color: #FFFFFF; font-size: 12pt; padding: 12px; }}
QPushButton#stop:hover {{ background-color: #1976D2; }}
QPushButton#small {{ padding: 4px 10px; font-size: 9pt; }}
QPushButton#small-blue {{ background-color: #1A1A1A; color: {COLOR_BLUE_LIGHT}; border: 1px solid {COLOR_BORDER}; padding: 4px 10px; font-size: 9pt; }}
QPushButton#small-blue:hover {{ background-color: {COLOR_BLUE_DIM}; }}
QPushButton#small-green {{ background-color: #2E7D32; color: #FFFFFF; padding: 4px 10px; font-size: 9pt; }}
QPushButton#small-green:hover {{ background-color: #388E3C; }}
QPushButton#small-red {{ background-color: {COLOR_RED}; color: #FFFFFF; padding: 4px 10px; font-size: 9pt; }}
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
QPushButton#nav-btn {{ background-color: {COLOR_CARD}; color: {COLOR_DIM}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; padding: 10px 0px; font-size: 11pt; font-weight: bold; }}
QPushButton#nav-btn:hover {{ background-color: #222222; color: {COLOR_TEXT}; }}
QPushButton#nav-btn:checked {{ background-color: {COLOR_RED}; color: #FFFFFF; border: 1px solid {COLOR_RED}; }}

QCheckBox {{ color: {COLOR_TEXT}; spacing: 8px; font-size: 10pt; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QRadioButton {{ color: {COLOR_TEXT}; spacing: 8px; font-size: 10pt; }}
QRadioButton::indicator {{ width: 0px; height: 0px; }}

QListWidget {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; color: {COLOR_TEXT}; outline: none; }}
QListWidget::item {{ padding: 6px; border-bottom: 1px solid {COLOR_BORDER}; }}
QListWidget::item:selected {{ background-color: {COLOR_BLUE_DIM}; color: {COLOR_BLUE_LIGHT}; }}

QComboBox {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 6px 12px; color: {COLOR_TEXT}; font-size: 9pt; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background-color: {COLOR_CARD}; color: {COLOR_TEXT}; selection-background-color: {COLOR_BLUE_DIM}; border: 1px solid {COLOR_BORDER}; }}

QSpinBox {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 4px 8px; color: {COLOR_TEXT}; font-size: 9pt; }}
QSpinBox::up-button, QSpinBox::down-button {{ background-color: #2D2D2D; border: none; width: 20px; }}

QTextEdit#log {{ background-color: #0A0A0A; color: #AAAAAA; border: 1px solid {COLOR_BORDER}; border-radius: 4px; font-family: "Consolas", "Courier New", monospace; font-size: 8pt; padding: 4px; }}
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
        box_x = 0
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
        return QSize(16 + 8 + text_w + 8, 28)


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
        circle_x = 0
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
        return QSize(16 + 8 + text_w + 8, 28)


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


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
        sock.settimeout(2)
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
    except Exception:
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


def start_browser(exe_path, args=None):
    if not os.path.isfile(exe_path):
        log.error(f"浏览器不存在: {exe_path}")
        return False
    cmd_args = [exe_path, f"--proxy-server={PROXY_URL}"]
    if args:
        cmd_args.extend(args)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 1
    subprocess.Popen(cmd_args, startupinfo=si)
    log.info(f"已启动浏览器: {exe_path}")
    return True


def set_system_proxy(enable):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                             0, winreg.KEY_SET_VALUE)
        if enable:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, PROXY_URL)
            log.info(f"已开启系统代理: {PROXY_URL}")
        else:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            log.info("已关闭系统代理")
        winreg.CloseKey(key)
        ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)
        ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)
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
        "quick_dir_path": "",
        "auto_line_switch": False,
        "auto_line_interval": 30,
        "browser_proxy_mode": "all",
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


class ServiceWorker(QThread):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    line_tested = pyqtSignal(str, float, bool)

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
            self.progress.emit("正在测试线路延迟...")
            fastest_name, fastest_data, fastest_time = None, None, float('inf')
            for name, data in downloaded:
                elapsed = test_direct_latency()
                if elapsed < fastest_time:
                    fastest_time = elapsed
                    fastest_name = name
                    fastest_data = data
            if fastest_data:
                save_config(quick_dir, fastest_data)
                self.progress.emit(f"已选择: {fastest_name}")
                log.info(f"最快线路: {fastest_name} ({fastest_time:.1f}s)")
            else:
                if not os.path.isfile(os.path.join(quick_dir, "config.yaml")):
                    self.finished.emit(False, "无可用配置")
                    return
        else:
            if not os.path.isfile(os.path.join(quick_dir, "config.yaml")):
                self.finished.emit(False, "无可用配置")
                return
        self.progress.emit("正在启动代理内核...")
        start_quick(quick_dir)
        if not wait_for_proxy(timeout=15):
            self.finished.emit(False, "代理内核启动失败")
            return
        connected, latency = verify_proxy_connection(timeout=10)
        lat_str = f"{latency:.1f}s" if latency else "未知"
        log.info(f"代理已启动, 延迟: {lat_str}")
        self.finished.emit(True, f"代理已启动 (延迟: {lat_str})")

    def _do_test_lines(self):
        self.progress.emit("正在下载配置文件...")
        downloaded = download_all_configs()
        if not downloaded:
            self.finished.emit(False, "无法下载配置")
            return

        result_queue = queue.Queue()
        total = len(downloaded)

        def test_single_line(name, data):
            latencies = []
            for _, test_url in NODE_TEST_URLS:
                try:
                    start = time.time()
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = urllib.request.Request(test_url, headers={"User-Agent": "Mozilla/5.0"})
                    urllib.request.urlopen(req, timeout=NODE_TEST_TIMEOUT, context=ctx)
                    latencies.append(time.time() - start)
                except Exception:
                    pass
            if latencies:
                avg = sum(latencies) / len(latencies)
                best = min(latencies)
                result_queue.put((name, avg, best, len(latencies), data))
            else:
                result_queue.put((name, -1.0, -1.0, 0, data))

        self.progress.emit(f"正在并行检测 {total} 条线路...")

        line_threads = []
        for name, data in downloaded:
            t = threading.Thread(target=test_single_line, args=(name, data))
            t.start()
            line_threads.append(t)

        results = []
        received = 0
        while received < total:
            try:
                name, avg, best, count, data = result_queue.get(timeout=NODE_TEST_TIMEOUT + 5)
                received += 1
                is_ok = avg >= 0
                self.line_tested.emit(name, avg, is_ok)
                self.progress.emit(f"正在检测线路 {received}/{total}...")
                if is_ok:
                    results.append((name, avg, best, count, data))
                else:
                    results.append((name, -1.0, -1.0, 0, data))
            except queue.Empty:
                break

        for t in line_threads:
            t.join(timeout=1)

        self.kwargs["results"] = results
        self.finished.emit(True, "检测完成")

    def _do_auto_select(self):
        self.progress.emit("正在下载配置文件...")
        downloaded = download_all_configs()
        if not downloaded:
            self.finished.emit(False, "无法下载配置")
            return
        fastest_name, fastest_data, fastest_time = None, None, float('inf')
        for name, data in downloaded:
            self.progress.emit(f"正在测试 {name}...")
            elapsed = test_direct_latency()
            if elapsed < fastest_time:
                fastest_time = elapsed
                fastest_name = name
                fastest_data = data
        if fastest_data:
            quick_dir = self.kwargs.get("quick_dir")
            if quick_dir:
                save_config(quick_dir, fastest_data)
            self.finished.emit(True, f"已选择最快线路: {fastest_name}")
        else:
            self.finished.emit(False, "无可用线路")

    def _do_use_line(self):
        name = self.kwargs.get("name")
        data = self.kwargs.get("data")
        quick_dir = self.kwargs.get("quick_dir")
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
            else:
                self.finished.emit(True, f"已选择 {name}，请启动服务")
        else:
            self.finished.emit(False, "无配置数据")

    def _do_update_config(self):
        self.progress.emit("正在下载最新配置...")
        downloaded = download_all_configs()
        if downloaded:
            fastest_name, fastest_data, fastest_time = None, None, float('inf')
            for name, data in downloaded:
                elapsed = test_direct_latency()
                if elapsed < fastest_time:
                    fastest_time = elapsed
                    fastest_name = name
                    fastest_data = data
            if fastest_data:
                quick_dir = self.kwargs.get("quick_dir")
                if quick_dir:
                    save_config(quick_dir, fastest_data)
                self.finished.emit(True, f"配置更新成功: {fastest_name}")
            else:
                self.finished.emit(False, "所有线路不可用")
        else:
            self.finished.emit(False, "无法下载配置")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(560, 780)
        self.setStyleSheet(STYLESHEET)

        self.settings = load_settings()
        self.quick_dir = self._resolve_quick_dir()
        self.current_line = ""
        self.line_results = {}
        self.worker = None
        self._auto_line_timer = None

        log.info(f"应用版本: {VERSION}")
        log.info(f"基础目录: {get_base_dir()}")
        log.info(f"Quick目录: {self.quick_dir}")

        self._set_icon()
        self._build_ui()
        self._update_status(is_proxy_running())
        self._update_kernel_status()
        self._update_active_line()

        self.monitor = ProxyMonitor()
        self.monitor.status_changed.connect(self._update_status)
        self.monitor.start()

        if self.settings.get("auto_start", True) and self.quick_dir:
            QTimer.singleShot(500, self._on_start)

        QTimer.singleShot(1000, self._startup_download_config)

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

        layout.addWidget(self._build_bottom_bar())
        layout.addWidget(self._build_tabs(), stretch=1)

    def _build_bottom_bar(self):
        frame = QFrame()
        frame.setObjectName("card")
        h = QHBoxLayout(frame)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(12)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("font-size: 18px; color: #FF6B80;")
        h.addWidget(self.status_dot)
        h.addSpacing(4)

        info = QVBoxLayout()
        info.setSpacing(1)
        self.status_label = QLabel("代理未启动")
        self.status_label.setObjectName("status-off")
        info.addWidget(self.status_label)
        self.detail_label = QLabel("开启代理服务")
        self.detail_label.setObjectName("dim")
        self.detail_label.setStyleSheet("font-size: 8pt;")
        info.addWidget(self.detail_label)
        h.addLayout(info, stretch=1)

        self.latency_label = QLabel("")
        self.latency_label.setObjectName("latency")
        h.addWidget(self.latency_label)

        self.switch_proxy = ToggleSwitch("代理服务", default=False)
        self.switch_proxy.setFixedWidth(160)
        self.switch_proxy.toggled.connect(self._on_proxy_switch_toggled)
        h.addWidget(self.switch_proxy)

        return frame

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
            ("🔍 线路检测", 0),
            ("⚙️ 代理设置", 1),
            ("📋 运行日志", 2),
            ("🔄 版本更新", 3),
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
        self.stack.addWidget(self._build_line_tab())
        self.stack.addWidget(self._build_proxy_tab())
        self.stack.addWidget(self._build_log_tab())
        self.stack.addWidget(self._build_update_tab())
        layout.addWidget(self.stack, stretch=1)

        return container

    def _on_nav_clicked(self, idx):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)
        self.stack.setCurrentIndex(idx)

    def _build_line_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        btn_row = QHBoxLayout()
        self.btn_test = QPushButton("🔍 检测所有线路")
        self.btn_test.setObjectName("small-blue")
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.clicked.connect(self._on_test_lines)
        btn_row.addWidget(self.btn_test)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.line_rows = {}
        for name, _, _ in CONFIG_URLS:
            row = QFrame()
            row.setObjectName("line-row")
            rh = QHBoxLayout(row)
            rh.setContentsMargins(12, 8, 12, 8)
            name_lbl = QLabel(name)
            name_lbl.setObjectName("suggestion")
            name_lbl.setFixedWidth(50)
            rh.addWidget(name_lbl)
            status_lbl = QLabel("未检测")
            status_lbl.setObjectName("dim")
            status_lbl.setWordWrap(True)
            status_lbl.setStyleSheet("font-size: 9pt;")
            rh.addWidget(status_lbl, stretch=1)
            use_btn = QPushButton("使用")
            use_btn.setObjectName("small-blue")
            use_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            use_btn.clicked.connect(lambda checked, n=name: self._on_use_line(n))
            rh.addWidget(use_btn)
            layout.addWidget(row)
            self.line_rows[name] = {"status": status_lbl, "use_btn": use_btn, "data": None, "row": row}

        auto_card = QFrame()
        auto_card.setObjectName("card")
        al = QVBoxLayout(auto_card)
        al.setSpacing(8)

        auto_title = QLabel("自动切换")
        auto_title.setObjectName("accent")
        auto_title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        al.addWidget(auto_title)

        auto_switch_row = QFrame()
        auto_switch_row.setObjectName("switch-row")
        asr = QHBoxLayout(auto_switch_row)
        asr.setContentsMargins(12, 6, 12, 6)
        auto_info = QVBoxLayout()
        auto_info.setSpacing(0)
        auto_lbl = QLabel("🔄 自动切换最快线路")
        auto_lbl.setStyleSheet("font-size: 10pt; font-weight: bold;")
        auto_info.addWidget(auto_lbl)
        auto_desc = QLabel("检测后自动激活最快线路，并按间隔定时切换")
        auto_desc.setObjectName("dim")
        auto_desc.setStyleSheet("font-size: 8pt;")
        auto_info.addWidget(auto_desc)
        asr.addLayout(auto_info, stretch=1)
        self.switch_auto_line = ToggleSwitch("", default=self.settings.get("auto_line_switch", False))
        self.switch_auto_line.setFixedWidth(80)
        self.switch_auto_line.toggled.connect(self._on_auto_line_switch_toggled)
        asr.addWidget(self.switch_auto_line)
        al.addWidget(auto_switch_row)

        interval_row = QHBoxLayout()
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
        al.addLayout(interval_row)

        layout.addWidget(auto_card)

        browser_card = QFrame()
        browser_card.setObjectName("card")
        bl = QVBoxLayout(browser_card)
        bl.setSpacing(8)

        browser_title = QLabel("浏览器")
        browser_title.setObjectName("accent")
        browser_title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        bl.addWidget(browser_title)

        auto_browser_row = QFrame()
        auto_browser_row.setObjectName("switch-row")
        abr = QHBoxLayout(auto_browser_row)
        abr.setContentsMargins(12, 6, 12, 6)
        auto_browser_info = QVBoxLayout()
        auto_browser_info.setSpacing(0)
        auto_browser_lbl = QLabel("🌐 启动后自动打开浏览器")
        auto_browser_lbl.setStyleSheet("font-size: 10pt; font-weight: bold;")
        auto_browser_info.addWidget(auto_browser_lbl)
        abr.addLayout(auto_browser_info, stretch=1)
        self.switch_auto_browser = ToggleSwitch("", default=self.settings.get("auto_open_browser", True))
        self.switch_auto_browser.setFixedWidth(80)
        self.switch_auto_browser.toggled.connect(self._on_auto_open_browser_toggled)
        abr.addWidget(self.switch_auto_browser)
        bl.addWidget(auto_browser_row)

        select_row = QHBoxLayout()
        select_row.addWidget(QLabel("浏览器:"))
        self.browser_type_group = []
        self.system_rb = RadioButton("系统", default=self.settings.get("browser_type", "system") == "system")
        self.browser_type_group.append(self.system_rb)
        select_row.addWidget(self.system_rb)
        self.custom_rb = RadioButton("自定义", default=self.settings.get("browser_type", "system") == "custom")
        self.browser_type_group.append(self.custom_rb)
        select_row.addWidget(self.custom_rb)
        self.system_rb.toggled.connect(lambda checked: self._on_custom_radio_toggled("system", checked))
        self.custom_rb.toggled.connect(lambda checked: self._on_custom_radio_toggled("custom", checked))
        self.browser_combo = QComboBox()
        self.browser_combo.setMinimumWidth(200)
        self._populate_browsers()
        self.browser_combo.currentIndexChanged.connect(self._on_system_browser_changed)
        select_row.addWidget(self.browser_combo, stretch=1)
        browse_btn = QPushButton("...")
        browse_btn.setObjectName("small-blue")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setFixedWidth(36)
        browse_btn.clicked.connect(self._on_browse_browser)
        select_row.addWidget(browse_btn)
        bl.addLayout(select_row)

        self.custom_browser_input = QLabel(self.settings.get("browser_path", "未选择"))
        self.custom_browser_input.setObjectName("dim")
        self.custom_browser_input.setStyleSheet("font-size: 8pt;")
        self.custom_browser_input.setVisible(self.settings.get("browser_type", "system") == "custom")
        bl.addWidget(self.custom_browser_input)

        self.selected_browser_label = QLabel("")
        self.selected_browser_label.setObjectName("dim")
        self.selected_browser_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_RED_LIGHT};")
        self.selected_browser_label.setWordWrap(True)
        bl.addWidget(self.selected_browser_label)
        self._update_selected_browser_label()

        open_row = QHBoxLayout()
        self.btn_open_browser = QPushButton("🌐 打开浏览器")
        self.btn_open_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_browser.setStyleSheet(
            f"background-color: {COLOR_RED}; color: #FFFFFF; padding: 8px 20px; "
            f"font-size: 10pt; font-weight: bold; border-radius: 4px;"
        )
        self.btn_open_browser.clicked.connect(self._on_open_browser)
        open_row.addWidget(self.btn_open_browser)
        open_row.addStretch()
        bl.addLayout(open_row)

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
        proxy_title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        pl.addWidget(proxy_title)

        browser_row = QFrame()
        browser_row.setObjectName("switch-row")
        br = QHBoxLayout(browser_row)
        br.setContentsMargins(12, 6, 12, 6)
        browser_info = QVBoxLayout()
        browser_info.setSpacing(0)
        browser_lbl = QLabel("🌐 浏览器代理")
        browser_lbl.setStyleSheet("font-size: 10pt; font-weight: bold;")
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
        global_lbl.setStyleSheet("font-size: 10pt; font-weight: bold;")
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
        custom_title = QLabel("🎯 指定程序代理")
        custom_title.setStyleSheet("font-size: 10pt; font-weight: bold;")
        custom_info.addWidget(custom_title)
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

        add_btn = QPushButton("＋ 添加程序")
        add_btn.setObjectName("small-blue")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_app)
        cl.addWidget(add_btn)
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
        startup_title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        sl.addWidget(startup_title)

        autostart_row = QFrame()
        autostart_row.setObjectName("switch-row")
        asr = QHBoxLayout(autostart_row)
        asr.setContentsMargins(12, 6, 12, 6)
        autostart_info = QVBoxLayout()
        autostart_info.setSpacing(0)
        autostart_lbl = QLabel("🚀 启动时自动开启服务")
        autostart_lbl.setStyleSheet("font-size: 10pt; font-weight: bold;")
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        info_card = QFrame()
        info_card.setObjectName("card")
        il = QVBoxLayout(info_card)
        il.setSpacing(6)
        info_title = QLabel("当前版本")
        info_title.setObjectName("accent")
        info_title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        il.addWidget(info_title)
        for label, value in [("应用版本", VERSION), ("代理内核版本", self._get_quick_version())]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setObjectName("dim")
            lbl.setFixedWidth(100)
            row.addWidget(lbl)
            val = QLabel(value or "未知")
            row.addWidget(val, stretch=1)
            il.addLayout(row)
        layout.addWidget(info_card)

        check_card = QFrame()
        check_card.setObjectName("card")
        cl = QVBoxLayout(check_card)
        cl.setSpacing(6)
        check_title = QLabel("版本更新")
        check_title.setObjectName("accent")
        check_title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        cl.addWidget(check_title)

        self.btn_check_update = QPushButton("🔍 检查更新")
        self.btn_check_update.setObjectName("small-blue")
        self.btn_check_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_update.clicked.connect(self._on_check_update)
        cl.addWidget(self.btn_check_update)

        self.update_info_label = QLabel("")
        self.update_info_label.setObjectName("dim")
        self.update_info_label.setWordWrap(True)
        self.update_info_label.setStyleSheet("font-size: 9pt;")
        cl.addWidget(self.update_info_label)

        self.btn_download_update = QPushButton("📥 下载最新版本")
        self.btn_download_update.setObjectName("small-green")
        self.btn_download_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download_update.setStyleSheet(
            f"background-color: {COLOR_RED}; color: #FFFFFF; padding: 10px 24px; "
            f"font-size: 10pt; font-weight: bold; border-radius: 6px;"
        )
        self.btn_download_update.clicked.connect(self._on_download_update)
        self.btn_download_update.setVisible(False)
        cl.addWidget(self.btn_download_update)

        layout.addWidget(check_card)

        actions_card = QFrame()
        actions_card.setObjectName("card")
        al = QVBoxLayout(actions_card)
        al.setSpacing(6)
        actions_title = QLabel("手动更新")
        actions_title.setObjectName("accent")
        actions_title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        al.addWidget(actions_title)
        for text, slot in [
            ("📥 更新线路配置", self._on_update_config),
            ("🔄 更新代理内核版本", self._on_update_quick),
        ]:
            btn = QPushButton(text)
            btn.setObjectName("small-blue")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            al.addWidget(btn)
        layout.addWidget(actions_card)

        self.update_status = QLabel("")
        self.update_status.setObjectName("dim")
        self.update_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.update_status)
        layout.addStretch()
        return page

    def _populate_browsers(self):
        self.browser_combo.clear()
        browsers = find_system_browsers()
        for name, path in browsers:
            self.browser_combo.addItem(f"{name} ({path})", path)

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
            self.status_dot.setStyleSheet(f"font-size: 18px; color: {COLOR_GREEN};")
            self.status_label.setText("代理运行中")
            self.status_label.setObjectName("status-on")
            self.detail_label.setText(f"本地代理: {PROXY_URL} | 当前线路: {self.current_line or '未知'}")
            if not self.switch_proxy.isChecked():
                self.switch_proxy.setChecked(True)
        else:
            self.status_dot.setStyleSheet("font-size: 18px; color: #FF6B80;")
            self.status_label.setText("代理未启动")
            self.status_label.setObjectName("status-off")
            self.detail_label.setText("开启代理服务")
            self.latency_label.setText("")
            if self.switch_proxy.isChecked():
                self.switch_proxy.setChecked(False)
        self.status_label.setStyleSheet(self.status_label.styleSheet())

    def _update_active_line(self):
        for name, info in self.line_rows.items():
            row = info["row"]
            if name == self.current_line:
                row.setObjectName("line-active")
                row.setStyleSheet(row.styleSheet())
                info["status"].setStyleSheet(f"color: {COLOR_RED_LIGHT}; font-weight: bold;")
            else:
                row.setObjectName("line-row")
                row.setStyleSheet(row.styleSheet())

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

        self.settings["browser_type"] = browser_type
        save_settings(self.settings)

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
        log.info("自动线路检测: 开始检测...")
        self.auto_line_status.setText("正在检测线路...")
        self.worker = ServiceWorker("auto_select", quick_dir=self.quick_dir)
        self.worker.finished.connect(self._on_auto_line_check_finished)
        self.worker.start()

    def _on_auto_line_check_finished(self, ok, msg):
        if ok:
            line_name = msg.split(":")[-1].strip() if ":" in msg else ""
            if line_name and line_name != self.current_line:
                log.info(f"自动切换线路: {self.current_line} → {line_name}")
                self.current_line = line_name
                self._update_active_line()
                if is_proxy_running() and line_name in self.line_results and self.line_results[line_name]:
                    self.worker = ServiceWorker("use_line", name=line_name, data=self.line_results[line_name], quick_dir=self.quick_dir)
                    self.worker.start()
            interval = self.settings.get("auto_line_interval", 30)
            self.auto_line_status.setText(f"下次检测: {interval}分钟后")
        else:
            self.auto_line_status.setText("检测失败，等待下次")

    def _on_proxy_switch_toggled(self, checked):
        if checked:
            self._on_start()
        else:
            self._on_stop()

    def _on_start(self):
        if not self.quick_dir:
            self.switch_proxy.setChecked(False)
            QMessageBox.critical(self, "错误",
                "未找到代理内核！\n\n"
                f"基础目录: {get_base_dir()}\n\n"
                "请确保 app/Quick/ 目录中包含 quick.exe。")
            return
        self.switch_proxy.setEnabled(False)
        self.detail_label.setText("正在启动代理服务...")
        self.worker = ServiceWorker("start", quick_dir=self.quick_dir)
        self.worker.progress.connect(lambda t: self.detail_label.setText(t))
        self.worker.finished.connect(self._on_start_finished)
        self.worker.start()

    def _on_start_finished(self, ok, msg):
        self.switch_proxy.setEnabled(True)
        if ok:
            self.detail_label.setText(msg)
            connected, latency = verify_proxy_connection()
            if connected and latency:
                self.latency_label.setText(f"{latency:.2f}s")
            browser_proxy_mode = self.settings.get("browser_proxy_mode", "all")
            if self.settings.get("global_proxy", False) and browser_proxy_mode == "all":
                set_system_proxy(True)
                self._update_sys_proxy_label()
            if self.switch_auto_browser.isChecked():
                self._on_open_browser()
            self.global_restart_hint.setVisible(False)
            self.custom_restart_hint.setVisible(False)
            if self.settings.get("auto_line_switch", False):
                self._start_auto_line_timer()
        else:
            self.switch_proxy.setChecked(False)
            QMessageBox.critical(self, "错误", msg)

    def _on_stop(self):
        if self.settings.get("global_proxy", False):
            set_system_proxy(False)
            self._update_sys_proxy_label()
        stop_quick()
        self.current_line = ""
        self._update_active_line()
        self.detail_label.setText("服务已停止")
        self._stop_auto_line_timer()

    def _on_open_browser(self):
        if not is_proxy_running():
            QMessageBox.warning(self, "提示", "代理服务未启动，请先启动服务！")
            return
        browser_path = self._get_browser_path()
        if not browser_path or not os.path.isfile(browser_path):
            QMessageBox.critical(self, "错误", "未找到浏览器！请在浏览器设置中配置。")
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
        self.settings["browser_proxy_mode"] = mode
        save_settings(self.settings)
        self._update_browser_proxy_hint()
        if is_proxy_running():
            set_system_proxy(self.settings.get("global_proxy", False))

    def _update_browser_proxy_hint(self):
        mode = self.settings.get("browser_proxy_mode", "all")
        if mode == "all":
            self.specified_browser_hint.setText("所有浏览器都将通过代理访问网络")
            self.browser_proxy_desc.setText("浏览器通过本地代理访问")
        else:
            browser_name = self._get_current_browser_name()
            self.specified_browser_hint.setText(f"仅代理: {browser_name}")
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
        self.settings["global_proxy"] = checked
        save_settings(self.settings)
        if is_proxy_running() and self.settings.get("browser_proxy_mode", "all") == "all":
            set_system_proxy(checked)
            self._update_sys_proxy_label()
            self.global_restart_hint.setVisible(False)
        else:
            self.global_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
            self.global_restart_hint.setVisible(True)
        log.info(f"全局系统代理: {'开启' if checked else '关闭'}")

    def _on_custom_apps_toggled(self, checked):
        self.settings["custom_apps_enabled"] = checked
        save_settings(self.settings)
        if is_proxy_running():
            self.custom_restart_hint.setText("⚠ 修改需重启服务后生效，当前仍使用原设置")
            self.custom_restart_hint.setVisible(True)
        else:
            self.custom_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
            self.custom_restart_hint.setVisible(True)
        log.info(f"指定程序代理: {'开启' if checked else '关闭'}")

    def _on_auto_open_browser_toggled(self, checked):
        self.settings["auto_open_browser"] = checked
        save_settings(self.settings)
        log.info(f"自动打开浏览器: {'开启' if checked else '关闭'}")

    def _on_auto_start_toggled(self, checked):
        self.settings["auto_start"] = checked
        save_settings(self.settings)
        log.info(f"启动时自动开启服务: {'开启' if checked else '关闭'}")

    def _on_auto_line_switch_toggled(self, checked):
        self.settings["auto_line_switch"] = checked
        save_settings(self.settings)
        if checked and is_proxy_running():
            self._start_auto_line_timer()
        else:
            self._stop_auto_line_timer()
        log.info(f"自动线路切换: {'开启' if checked else '关闭'}")

    def _on_interval_changed(self, value):
        self.settings["auto_line_interval"] = value
        save_settings(self.settings)
        if self.settings.get("auto_line_switch", False) and is_proxy_running():
            self._start_auto_line_timer()
        log.info(f"自动检测间隔: {value}分钟")

    def _on_test_lines(self):
        if not self.quick_dir:
            QMessageBox.warning(self, "提示", "请先设置代理内核目录")
            return
        self.btn_test.setEnabled(False)
        self.btn_test.setText("检测中...")
        for name, info in self.line_rows.items():
            info["status"].setText("检测中...")
            info["status"].setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 9pt;")
            info["use_btn"].setEnabled(False)
        self.worker = ServiceWorker("test_lines", quick_dir=self.quick_dir)
        self.worker.progress.connect(lambda t: self.line_progress.setText(t))
        self.worker.line_tested.connect(self._on_line_tested)
        self.worker.finished.connect(self._on_test_finished)
        self.worker.start()

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
        self.btn_test.setText("🔍 检测所有线路")
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
        if name not in self.line_results or self.line_results[name] is None:
            QMessageBox.information(self, "提示", "请先检测线路")
            return
        if not self.quick_dir:
            return
        self.current_line = name
        self._update_active_line()
        self.worker = ServiceWorker("use_line", name=name, data=self.line_results[name], quick_dir=self.quick_dir)
        self.worker.progress.connect(lambda t: self.detail_label.setText(t))
        self.worker.finished.connect(lambda ok, msg: self.detail_label.setText(msg) if ok else QMessageBox.warning(self, "提示", msg))
        self.worker.start()

    def _on_add_app(self):
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

    def _on_browse_browser(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择浏览器", "", "可执行文件 (*.exe);;所有文件 (*.*)")
        if path:
            self.settings["browser_path"] = path
            self.custom_browser_input.setText(path)
            save_settings(self.settings)
            self._update_selected_browser_label()
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
        self.settings["browser_type"] = browser_type
        save_settings(self.settings)
        self._update_selected_browser_label()
        self._update_browser_proxy_hint()
        self.custom_browser_input.setVisible(browser_type == "custom")
        log.info(f"浏览器类型切换为: {browser_type}")

    def _on_system_browser_changed(self, idx):
        if idx >= 0:
            path = self.browser_combo.itemData(idx)
            self.settings["system_browser_path"] = path
            save_settings(self.settings)
            self._update_selected_browser_label()

    def _update_selected_browser_label(self):
        path = self._get_browser_path()
        if path and os.path.isfile(path):
            self.selected_browser_label.setText(f"✓ 将启动: {path}")
            self.selected_browser_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_GREEN};")
        elif path:
            self.selected_browser_label.setText(f"⚠ 路径不存在: {path}")
            self.selected_browser_label.setStyleSheet("font-size: 8pt; color: #FF6B80;")
        else:
            self.selected_browser_label.setText("⚠ 未选择浏览器")
            self.selected_browser_label.setStyleSheet("font-size: 8pt; color: #FF6B80;")

    def _on_export_log(self):
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
        def do_download():
            try:
                downloaded = download_all_configs()
                if downloaded:
                    name, data = downloaded[0]
                    save_config(self.quick_dir, data)
                    log.info(f"启动时已下载最新配置: {name}")
            except Exception as e:
                log.warning(f"启动时下载配置失败: {e}")
        import threading
        threading.Thread(target=do_download, daemon=True).start()

    def _on_check_update(self):
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText("检查中...")
        self.update_info_label.setText("正在连接服务器检查更新...")
        self.update_info_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM};")
        self.btn_download_update.setVisible(False)

        def do_check():
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(VERSION_CHECK_URL, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                    data = json.loads(resp.read().decode())
                latest = data.get("latest", "")
                versions = data.get("versions", [])
                latest_info = next((v for v in versions if v["version"] == latest), None)
                self._latest_version = latest
                self._latest_info = latest_info
                if latest and latest != VERSION:
                    changes = "\n".join(f"  • {c}" for c in (latest_info.get("changes", [])[:5])) if latest_info else ""
                    self.update_info_label.setText(
                        f"🆕 发现新版本: v{latest}\n\n{changes}\n\n当前版本: v{VERSION}"
                    )
                    self.update_info_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_RED_LIGHT};")
                    self.btn_download_update.setVisible(True)
                else:
                    self.update_info_label.setText(f"✓ 已是最新版本 (v{VERSION})")
                    self.update_info_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_GREEN};")
            except Exception as e:
                self.update_info_label.setText(f"检查更新失败: {e}")
                self.update_info_label.setStyleSheet("font-size: 9pt; color: #FF6B80;")
            finally:
                self.btn_check_update.setEnabled(True)
                self.btn_check_update.setText("🔍 检查更新")

        import threading
        threading.Thread(target=do_check, daemon=True).start()

    def _on_download_update(self):
        if not hasattr(self, '_latest_info') or not self._latest_info:
            return
        filename = self._latest_info.get("filename", "")
        if not filename:
            return
        url = VERSION_DOWNLOAD_URL + filename
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.warning(self, "下载失败", f"无法打开下载链接:\n{e}")

    def _on_update_config(self):
        if not self.quick_dir:
            return
        self.worker = ServiceWorker("update_config", quick_dir=self.quick_dir)
        self.worker.progress.connect(lambda t: self.update_status.setText(t))
        self.worker.finished.connect(lambda ok, msg: (
            self.update_status.setText(msg),
            self.update_status.setStyleSheet(f"color: {COLOR_GREEN};" if ok else "color: #FF6B80;")
        ))
        self.worker.start()

    def _on_update_quick(self):
        QMessageBox.information(self, "更新代理内核",
            "请手动操作:\n1. 下载最新版 Clash/Quick 内核\n2. 替换 Quick\\quick.exe 文件\n3. 重启本启动器")

    def closeEvent(self, event):
        self._stop_auto_line_timer()
        self.monitor.stop()
        self.monitor.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
