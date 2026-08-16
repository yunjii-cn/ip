import sys
import os
import logging
import winreg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import socket
import ssl
import http.client
import shutil
import time
import threading
import concurrent.futures
import urllib.request
import urllib.error
import subprocess
import re
import ctypes
import ctypes.wintypes
import queue
import tempfile
import zipfile
import base64
from datetime import datetime, date, timedelta
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Tuple, Any

import yaml
HAS_YAML = True

import maxminddb
HAS_MAXMINDDB = True

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QDialog,
    QMessageBox, QListWidget,
    QListWidgetItem, QTextEdit, QComboBox, QSpinBox, QSizePolicy,
    QSplashScreen, QScrollArea, QLineEdit, QStyle, QProgressBar,
    QSystemTrayIcon, QMenu, QCheckBox, QGridLayout, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QMetaObject, Q_ARG
from PyQt6.QtGui import QPixmap, QIcon, QFont, QColor, QPainter, QPen, QFontMetrics, QPalette, QLinearGradient, QTextOption, QAction

# 隐藏启动时闪现的控制台窗口（PyInstaller 默认是 console 子系统，会弹一个黑色 cmd 窗口）
# 双重保险：ShowWindow(SW_HIDE) + FreeConsole，前者隐藏窗口，后者彻底分离控制台
# 避免在自部署进度条跑到一半时，闪一个黑框在进度条左上角
if os.name == 'nt':
    try:
        _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if _hwnd:
            ctypes.windll.user32.ShowWindow(_hwnd, 0)  # SW_HIDE
        # FreeConsole 必须在所有日志 handler 初始化之前调用，否则 logging.StreamHandler 会失效
        # 但日志还有文件 handler，所以 console handler 失效不影响保存日志
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass

def _load_project_config():
    _DEFAULTS = {
        "brand_name": "云集智能网联代理专家",
        "version_format": "%Y.%m.%d.%H%M",
        "repos": {
            "github": "yunjii-cn/ip",
            "gitee": "yunjii/ip",
            "mihomo": "MetaCubeX/mihomo"
        },
        "paths": {
            "version_json": "release/version.json",
            "dev": "dev",
            "app": "app",
            "ver": "ver",
            "dist": "dist",
            "build": "build",
            "release": "release",
            "lock_file": ".yunji.lock"
        }
    }

    def _deep_merge(base, override):
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = _deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    for search_path in [
        os.path.join(getattr(sys, '_MEIPASS', ''), 'project.json'),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'project.json'),
    ]:
        try:
            with open(search_path, 'r', encoding='utf-8') as f:
                return _deep_merge(_DEFAULTS, json.load(f))
        except Exception:
            continue
    return _DEFAULTS

_CFG = _load_project_config()

def _get_build_version():
    """获取封装时固定的版本号。
    优先级：
    1. 从EXE内嵌的 _build_version.txt 读取（构建时写入，最可靠）
    2. 从EXE文件名提取版本号（如 xxx-v2026.06.06.0936.exe）
    3. 开发模式：使用当前日期时间
    版本号在封装时确定，不受运行时日期或用户改名影响。
    """
    # 1. 从内嵌版本文件读取（构建时通过 --add-data 打包进EXE）
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', '')
        if meipass:
            ver_file = os.path.join(meipass, '_build_version.txt')
            if os.path.isfile(ver_file):
                try:
                    with open(ver_file, 'r', encoding='utf-8') as f:
                        ver = f.read().strip()
                        if re.match(r'\d{4}\.\d{2}\.\d{2}\.\d{4}', ver):
                            return ver
                except Exception:
                    pass
    # 2. 从EXE文件名提取版本号
    if getattr(sys, 'frozen', False):
        exe_name = os.path.basename(sys.executable)
        m = re.search(r'v(\d{4}\.\d{2}\.\d{2}\.\d{4})', exe_name)
        if m:
            return m.group(1)
    # 3. 开发模式：使用当前日期时间
    return datetime.now().strftime(_CFG["version_format"])

VERSION = _get_build_version()
GITHUB_REPO = _CFG["repos"]["github"]
GITEE_REPO = _CFG["repos"]["gitee"]
MIHOMO_REPO = _CFG["repos"]["mihomo"]
VERSION_JSON_PATH = _CFG["paths"]["version_json"]


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
BRAND_NAME = _CFG["brand_name"]
APP_NAME = f"{BRAND_NAME} v{VERSION}"
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 7890
PROXY_URL = f"{PROXY_HOST}:{PROXY_PORT}"


def _update_proxy_url():
    global PROXY_HOST, PROXY_PORT, PROXY_URL
    PROXY_URL = f"{PROXY_HOST}:{PROXY_PORT}"
NODE_TEST_TIMEOUT = 6
NODE_TEST_URL = "https://www.gstatic.com/generate_204"
# 线路检测 URL：境内+境外混合
# - 境外：验证代理能翻墙访问外网（核心目标）
# - 境内：兜底，当境外域名首包慢/被重置时，至少能确认「代理内核本身是通的」
# 任一 URL 成功即判定该线路可用，避免误判整条线路超时
NODE_TEST_URLS = [
    # region: "abroad" 表示必须经由代理隧道才能到达（用于判定线路是否真能代理境外）；
    #         "cn"     表示境内直连可达（GEOIP,CN,DIRECT），仅作参考，不计入可用性。
    ("Google", "https://www.gstatic.com/generate_204", "abroad"),
    ("Cloudflare", "https://cp.cloudflare.com/", "abroad"),
    ("Baidu", "https://www.baidu.com/", "cn"),
]

_FREENODES_TOKEN = "__FREENODES_LATEST__"  # 占位符：运行时自动替换为最新日期文件

# =====================================================================
# 配置下载源（2026-08-09 重构）
# ---------------------------------------------------------------------
# 经验证，GitHub(raw.githubusercontent.com) 在国内被 GFW 的 IP+SNI 双重封锁，
# 即便走 DoH+IP / ghproxy / jsDelivr 镜像也极不稳定，导致"配置更新"长期失败。
# 参考可正常使用的 Chrome143_Quick 项目，其配置更新走的是 GitLab 镜像链路：
#   主源  gitlabip.xyz  —— 专用于绕过 GFW 的 GitLab 镜像域名（国内直连可达）
#   备源  gitlab.com    —— 直连兜底（部分网络可用）
# 二者内容同源（Alvin9999/PAC 与 free9999/ipupdate 两个仓库都托管同一份
# backup/img/1/2/ipp/quick/{1..4}/config.yaml），故 4 条线路直接映射到 quick/1..4。
# =====================================================================
_GITLAB_MIRROR = "https://www.gitlabip.xyz"          # GitLab GFW 绕过镜像
_GITLAB_RAW_TPL = "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/{n}/config.yaml"
_GITLAB_MIRROR_TPL = _GITLAB_MIRROR + "/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/{n}/config.yaml"

CONFIG_URLS = [
    # (线路名, 主源=GitLab 镜像[绕过 GFW], 备源=GitLab 直连)
    ("线路1", _GITLAB_MIRROR_TPL.format(n=1), _GITLAB_RAW_TPL.format(n=1)),
    ("线路2", _GITLAB_MIRROR_TPL.format(n=2), _GITLAB_RAW_TPL.format(n=2)),
    ("线路3", _GITLAB_MIRROR_TPL.format(n=3), _GITLAB_RAW_TPL.format(n=3)),
    ("线路4", _GITLAB_MIRROR_TPL.format(n=4), _GITLAB_RAW_TPL.format(n=4)),
]

# 内置存活默认节点（烤进包的 config.default.yaml，anytls2 真实可用节点）。
# 作为一条“内置可测线路”参与竞速检测，保证开箱即有一条可用线路，
# 避免内置免费源(gitlabip)节点集体失效时“检测线路”整页超时、用户误以为软件坏掉。
BUILTIN_DEFAULT_LINE_NAME = "默认节点(anytls2)"


def _load_builtin_default_config(quick_dir):
    """读取烤进包的默认配置(anytls2 活节点)，作为内置可测线路。无则返回 None。"""
    p = os.path.join(quick_dir, "config.default.yaml")
    if os.path.isfile(p):
        try:
            with open(p, "rb") as f:
                return f.read()
        except Exception:
            return None
    return None

# ========== 自定义订阅（Batch 1） ==========

# EXE 模式下 __file__ 指向 _MEIPASS 临时解压目录，需要用 sys.executable 定位实际应用目录
if getattr(sys, 'frozen', False):
    _ud_base = os.path.dirname(os.path.abspath(sys.executable))
    for _ in range(5):
        if os.path.isfile(os.path.join(_ud_base, '.yunji.lock')) or os.path.isdir(os.path.join(_ud_base, 'app')):
            break
        _p = os.path.dirname(_ud_base)
        if _p == _ud_base:
            break
        _ud_base = _p
    USER_DATA_DIR = os.path.join(_ud_base, 'app', 'user_data')
else:
    USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_data")
SUBSCRIPTIONS_FILE = os.path.join(USER_DATA_DIR, "subscriptions.json")


@dataclass
class Subscription:
    """用户自定义订阅（Clash YAML 格式）"""
    name: str            # 备注名（用户必填，在线路列表里显示这个名字）
    url: str             # 订阅 URL
    enabled: bool = True
    last_update: str = ""   # YYYY-MM-DD HH:MM
    node_count: int = 0
    last_status: str = "未下载"  # 未下载 / 下载成功 / 下载失败
    last_error: str = ""


def ensure_user_data_dir():
    os.makedirs(USER_DATA_DIR, exist_ok=True)


class SubscriptionManager:
    """用户自定义订阅的本地持久化管理"""

    def __init__(self):
        self.subscriptions: List[Subscription] = []
        self._load()

    def _load(self):
        ensure_user_data_dir()
        if not os.path.isfile(SUBSCRIPTIONS_FILE):
            self.subscriptions = []
            return
        try:
            with open(SUBSCRIPTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
            self.subscriptions = [Subscription(**item) for item in data if isinstance(item, dict)]
        except Exception as e:
            log.error(f"加载订阅文件失败: {e}")
            self.subscriptions = []

    def _save(self):
        ensure_user_data_dir()
        try:
            with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump([asdict(s) for s in self.subscriptions], f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"保存订阅文件失败: {e}")

    def add(self, name: str, url: str) -> Subscription:
        """添加订阅，名称重复抛 ValueError"""
        name = (name or "").strip()
        url = (url or "").strip()
        if not name:
            raise ValueError("订阅备注名不能为空")
        if not url:
            raise ValueError("订阅 URL 不能为空")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("订阅 URL 必须以 http:// 或 https:// 开头")
        if any(s.name == name for s in self.subscriptions):
            raise ValueError(f"订阅备注名「{name}」已存在")
        sub = Subscription(name=name, url=url)
        self.subscriptions.append(sub)
        self._save()
        return sub

    def remove(self, name: str) -> bool:
        before = len(self.subscriptions)
        self.subscriptions = [s for s in self.subscriptions if s.name != name]
        if len(self.subscriptions) < before:
            self._save()
            return True
        return False

    def toggle(self, name: str, enabled: bool):
        for s in self.subscriptions:
            if s.name == name:
                s.enabled = enabled
                self._save()
                return

    def get_enabled(self) -> List[Subscription]:
        return [s for s in self.subscriptions if s.enabled]

    def get_all(self) -> List[Subscription]:
        return list(self.subscriptions)

    def find(self, name: str) -> Optional[Subscription]:
        for s in self.subscriptions:
            if s.name == name:
                return s
        return None

    def update_status(self, name: str, status: str, error: str = "",
                      node_count: Optional[int] = None):
        sub = self.find(name)
        if not sub:
            return
        sub.last_status = status
        sub.last_error = error
        sub.last_update = time.strftime("%Y-%m-%d %H:%M")
        if node_count is not None:
            sub.node_count = node_count
        self._save()


# 全局单例（延迟初始化）
_subscription_manager: Optional[SubscriptionManager] = None


def get_subscription_manager() -> SubscriptionManager:
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = SubscriptionManager()
    return _subscription_manager


def parse_clash_yaml(text: str) -> Dict:
    """解析 Clash YAML 订阅内容，返回 dict（部分机场用 base64 编码，自动尝试解码）

    抛出 ValueError 表示解析失败
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("订阅内容为空")

    # 尝试直接当 YAML 解析
    if HAS_YAML:
        try:
            cfg = yaml.safe_load(text)
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
    else:
        # 退化：用极简文本解析，识别 proxies/proxy-groups/rules 顶层 key
        cfg = _parse_yaml_minimal(text)
        if cfg and (cfg.get("proxies") or cfg.get("proxy-groups")):
            return cfg

    # 尝试 base64 解码（部分机场用 V2RayN 格式返回 base64）
    try:
        # Clash YAML 的 base64 编码格式：每行一个 base64 节点
        # 简单判断：如果原内容不像 yaml 格式（无 'proxies:' 等关键字），尝试 base64
        if "proxies:" not in text and "proxy-groups:" not in text:
            decoded = base64.b64decode(text).decode("utf-8", errors="ignore")
            if HAS_YAML:
                cfg = yaml.safe_load(decoded)
                if isinstance(cfg, dict):
                    return cfg
    except Exception:
        pass

    raise ValueError("订阅内容不是有效的 Clash YAML 格式")


def _parse_yaml_minimal(text: str) -> Dict:
    """不依赖 PyYAML 的极简 YAML 解析（仅用于订阅内容只有 proxies 的情况）

    返回 dict 形如 {"proxies": [{"name": ..., "type": ..., "server": ...}]}
    """
    result = {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(\w[\w-]*):\s*$", line)
        if m:
            key = m.group(1)
            if key not in ("proxies", "proxy-groups", "rules"):
                i += 1
                continue
            items = []
            i += 1
            # 收集 - 开头的列表项
            while i < len(lines):
                ln = lines[i]
                if ln.startswith("  - ") or ln.startswith("    - "):
                    item = {"_raw": []}
                    # 去掉前导 "  - " 或 "    - "
                    stripped = re.sub(r"^\s*-\s*", "", ln)
                    if ":" in stripped:
                        k, v = stripped.split(":", 1)
                        item[k.strip()] = v.strip()
                    item["_raw"].append(ln)
                    i += 1
                    # 收集缩进的子项
                    while i < len(lines) and lines[i].startswith("    ") and not re.match(r"^\s+- ", lines[i]):
                        sub = lines[i].strip()
                        if ":" in sub:
                            k, v = sub.split(":", 1)
                            item[k.strip()] = v.strip()
                        item["_raw"].append(lines[i])
                        i += 1
                    items.append(item)
                elif ln.strip() == "" or ln.startswith("#"):
                    i += 1
                else:
                    break
            result[key] = items
        else:
            i += 1
    return result


def extract_proxies_count(text: str) -> int:
    """统计订阅里的代理节点数（仅 proxies 段，不含 proxy-groups/rules）

    通过解析 YAML 后取 len(cfg.get("proxies", [])) 准确计数。
    解析失败则用宽松正则（仅 2 空格缩进的 - name:）作兜底
    """
    if not text:
        return 0
    try:
        cfg = parse_clash_yaml(text.replace("\r\n", "\n").replace("\r", "\n"))
        if isinstance(cfg, dict) and isinstance(cfg.get("proxies"), list):
            return len(cfg["proxies"])
    except Exception:
        pass
    # 兜底：只数 2 空格缩进的 - name:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return len(re.findall(r"\n  - name:", text))


def download_subscription(sub: Subscription, timeout: int = 15) -> bytes:
    """下载并验证单个订阅内容，失败抛异常"""
    data = download_config(sub.url, timeout=timeout)
    # 统一 CRLF → LF（部分机场/Windows 环境下订阅是 CRLF 编码）
    text = data.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    # 验证一下能解析
    cfg = parse_clash_yaml(text)
    if not isinstance(cfg, dict):
        raise ValueError("订阅解析结果不是字典")
    if not cfg.get("proxies") and not cfg.get("proxy-groups"):
        log.warning(f"订阅 {sub.name} 解析后没有 proxies/proxy-groups 段")
    return text.encode("utf-8")


# ========== GeoIP 国家查询（Batch 2） ==========

# 找 mmdb 路径的优先级
GEOIP_MMDB_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Quick", "Country.mmdb"),
    os.path.join(USER_DATA_DIR, "Country.mmdb"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Country.mmdb"),
]
# 备用下载源（GitHub CDN 上的 GeoLite2-Country 镜像）
GEOIP_MMDB_DOWNLOAD_URLS = [
    "https://cdn.jsdelivr.net/gh/Hackl0us/GeoIP2-CN@release/Country.mmdb",
    "https://raw.githubusercontent.com/Hackl0us/GeoIP2-CN/release/Country.mmdb",
]

_geoip_reader = None  # 全局缓存
_geoip_path = None


def get_geoip_db_path() -> Optional[str]:
    """返回第一个存在的 mmdb 路径，不存在返回 None"""
    for p in GEOIP_MMDB_CANDIDATES:
        if os.path.isfile(p) and os.path.getsize(p) > 1000:
            return p
    return None


def get_geoip_reader():
    """懒加载 maxminddb Reader（单例）"""
    global _geoip_reader, _geoip_path
    if _geoip_reader is not None:
        return _geoip_reader
    path = get_geoip_db_path()
    if not path:
        return None
    try:
        _geoip_reader = maxminddb.open_database(path)
        _geoip_path = path
        log.info(f"GeoIP 数据库已加载: {path}")
        return _geoip_reader
    except Exception as e:
        log.error(f"加载 GeoIP 数据库失败 ({path}): {e}")
        return None


def download_geoip_db(force: bool = False) -> Optional[str]:
    """下载 GeoIP 数据库到 user_data 目录，返回下载后的路径，失败返回 None"""
    target = os.path.join(USER_DATA_DIR, "Country.mmdb")
    if not force and os.path.isfile(target) and os.path.getsize(target) > 1000:
        return target
    ensure_user_data_dir()
    for url in GEOIP_MMDB_DOWNLOAD_URLS:
        try:
            log.info(f"下载 GeoIP 数据库: {url}")
            data = download_config(url, timeout=60)
            if len(data) < 1000:
                raise ValueError(f"下载文件太小: {len(data)} bytes")
            with open(target, "wb") as f:
                f.write(data)
            log.info(f"GeoIP 数据库已下载: {target} ({len(data)} bytes)")
            return target
        except Exception as e:
            log.warning(f"下载 GeoIP 失败 ({url}): {e}")
            continue
    return None


# 国家代码 → 中文名 / 国旗 emoji
COUNTRY_NAMES = {
    "CN": "中国", "HK": "香港", "TW": "台湾", "MO": "澳门",
    "JP": "日本", "KR": "韩国", "SG": "新加坡", "MY": "马来西亚",
    "TH": "泰国", "VN": "越南", "ID": "印度尼西亚", "PH": "菲律宾",
    "IN": "印度", "PK": "巴基斯坦",
    "US": "美国", "CA": "加拿大", "MX": "墨西哥",
    "GB": "英国", "DE": "德国", "FR": "法国", "IT": "意大利", "ES": "西班牙",
    "NL": "荷兰", "RU": "俄罗斯", "TR": "土耳其", "UA": "乌克兰",
    "AU": "澳大利亚", "NZ": "新西兰",
    "BR": "巴西", "AR": "阿根廷",
    "ZA": "南非", "EG": "埃及",
    "AE": "阿联酋", "SA": "沙特阿拉伯", "IL": "以色列",
    "SE": "瑞典", "NO": "挪威", "FI": "芬兰", "CH": "瑞士", "AT": "奥地利",
    "PL": "波兰", "IE": "爱尔兰", "BE": "比利时", "PT": "葡萄牙", "GR": "希腊",
    "CZ": "捷克", "HU": "匈牙利", "RO": "罗马尼亚",
}

# 常用国旗 emoji
def country_flag(code: str) -> str:
    """国家代码 → 国旗 emoji（如 'US' → '🇺🇸'）"""
    if not code or len(code) != 2:
        return "🌐"
    try:
        return "".join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code.upper())
    except Exception:
        return "🌐"


def lookup_country(ip: str) -> Optional[str]:
    """查 IP 的国家代码（2 字母 ISO），未找到返回 None"""
    reader = get_geoip_reader()
    if not reader or not ip:
        return None
    try:
        r = reader.get(ip)
        if r and "country" in r:
            return r["country"].get("iso_code")
    except Exception:
        return None
    return None


def resolve_server_country(server: str) -> Optional[str]:
    """节点 server → 国家代码。server 可能是 IP 或域名（先 DNS 解析）"""
    if not server:
        return None
    # 已经是 IP
    try:
        socket.inet_aton(server)  # IPv4
        return lookup_country(server)
    except OSError:
        pass
    # 是域名，做 DNS 解析
    try:
        ip = socket.gethostbyname(server)
        return lookup_country(ip)
    except Exception:
        return None


def get_node_countries_for_config(config_text: str) -> Dict[str, str]:
    """从 config 文本中提取每个 proxy 节点对应的国家代码

    返回 {"proxy_name": "US", ...}
    """
    result = {}
    try:
        cfg = parse_clash_yaml(config_text)
    except Exception:
        return result
    if not isinstance(cfg, dict):
        return result
    for proxy in cfg.get("proxies", []):
        if not isinstance(proxy, dict):
            continue
        name = proxy.get("name")
        server = proxy.get("server")
        if name and server:
            country = resolve_server_country(server)
            if country:
                result[name] = country
    return result


# ========== 国家筛选设置（Batch 2） ==========

def load_country_whitelist() -> List[str]:
    """读取用户设置的国家白名单（空列表表示不筛选）"""
    settings_path = os.path.join(USER_DATA_DIR, "settings.json")
    if not os.path.isfile(settings_path):
        return []
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        wl = data.get("country_whitelist", [])
        if isinstance(wl, list):
            return [c for c in wl if isinstance(c, str) and len(c) == 2]
    except Exception as e:
        log.warning(f"读取国家白名单失败: {e}")
    return []


def save_country_whitelist(countries: List[str]):
    """保存国家白名单到 user_data/settings.json"""
    settings_path = os.path.join(USER_DATA_DIR, "settings.json")
    ensure_user_data_dir()
    data = {}
    if os.path.isfile(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data["country_whitelist"] = [c for c in countries if isinstance(c, str) and len(c) == 2]
    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"保存国家白名单失败: {e}")


def filter_proxies_by_country(config_text: str, countries: List[str]) -> str:
    """根据国家白名单过滤 config 中的 proxies 和 proxy-groups 引用

    countries: 空列表表示不过滤
    返回过滤后的 config 文本
    """
    if not countries:
        return config_text
    try:
        cfg = parse_clash_yaml(config_text)
    except Exception:
        return config_text
    if not isinstance(cfg, dict):
        return config_text

    proxies = cfg.get("proxies", [])
    if not isinstance(proxies, list):
        return config_text

    # 1. 标记保留的 proxy 名字
    keep_names = set()
    removed_names = set()
    for p in proxies:
        if not isinstance(p, dict):
            continue
        name = p.get("name")
        server = p.get("server")
        if not name:
            continue
        country = resolve_server_country(server) if server else None
        if country and country in countries:
            keep_names.add(name)
        else:
            removed_names.add(name)

    log.info(f"国家筛选: 保留 {len(keep_names)} 个, 移除 {len(removed_names)} 个 (白名单: {countries})")

    if not keep_names:
        log.warning("国家筛选后没有保留任何节点，跳过筛选")
        return config_text

    # 2. 过滤 proxies 段
    cfg["proxies"] = [p for p in proxies if isinstance(p, dict) and p.get("name") in keep_names]

    # 3. 清理 proxy-groups 里的引用
    for group in cfg.get("proxy-groups", []):
        if not isinstance(group, dict):
            continue
        # proxies 列表
        if "proxies" in group and isinstance(group["proxies"], list):
            group["proxies"] = [
                x for x in group["proxies"]
                if (isinstance(x, str) and x in keep_names) or x not in removed_names
            ]
            # 如果组里全空了，至少保留 DIRECT/REJECT
            if not group["proxies"]:
                group["proxies"] = ["DIRECT"]

    # 4. 序列化回 yaml
    try:
        import io
        buf = io.StringIO()
        yaml.safe_dump(cfg, buf, allow_unicode=True, sort_keys=False, default_flow_style=False)
        return buf.getvalue()
    except Exception as e:
        log.error(f"序列化筛选后 config 失败: {e}")
        return config_text


# =====================================================================
# Batch 3: 节点健康度统计 (HealthDB)
# =====================================================================
HEALTH_DB_FILE = os.path.join(USER_DATA_DIR, "health.json")
HEALTH_KEEP_DAYS = 30  # 最多保留 30 天


@dataclass
class HealthRecord:
    """单次线路检测的健康度记录"""
    ts: str           # ISO 时间戳 (e.g. "2026-06-18T21:00:00")
    success: bool     # 至少一个 URL 测试通过
    avg: float        # 平均延迟（秒），失败时为 -1
    best: float       # 最佳延迟（秒），失败时为 -1
    count: int        # 通过的测试 URL 数
    total: int        # 总测试 URL 数


class HealthDB:
    """线路健康度数据库，存 dev/app/user_data/health.json

    数据格式:
    {
        "线路1": [HealthRecord, ...],   # 按时间倒序
        "线路2": [...],
        ...
    }
    """

    def __init__(self, db_path: str = HEALTH_DB_FILE):
        self.db_path = db_path
        self._data: Dict[str, List[Dict]] = {}
        self._load()

    def _load(self):
        try:
            if os.path.isfile(self.db_path):
                with open(self.db_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    self._data = raw
        except Exception as e:
            log.warning(f"加载健康度数据失败（已重置）: {e}")
            self._data = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning(f"保存健康度数据失败: {e}")

    def append(self, line_name: str, record: HealthRecord):
        """追加一条记录 + 自动 trim 30 天前数据"""
        if not line_name:
            return
        records = self._data.get(line_name, [])
        if not isinstance(records, list):
            records = []
        records.append({
            "ts": record.ts,
            "success": record.success,
            "avg": record.avg,
            "best": record.best,
            "count": record.count,
            "total": record.total,
        })
        # 按时间倒序
        records.sort(key=lambda r: r.get("ts", ""), reverse=True)
        # trim 30 天前
        cutoff = datetime.now() - timedelta(days=HEALTH_KEEP_DAYS)
        cutoff_iso = cutoff.isoformat(timespec="seconds")
        records = [r for r in records if r.get("ts", "") >= cutoff_iso]
        self._data[line_name] = records
        self._save()

    def get_records(self, line_name: str) -> List[Dict]:
        return list(self._data.get(line_name, []))

    def get_7d_success_rate(self, line_name: str) -> Optional[float]:
        """获取近 7 天成功率（0.0 ~ 1.0），无数据时返回 None"""
        records = self._data.get(line_name, [])
        if not records:
            return None
        cutoff = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
        recent = [r for r in records if r.get("ts", "") >= cutoff]
        if not recent:
            return None
        succ = sum(1 for r in recent if r.get("success"))
        return succ / len(recent)

    def get_7d_avg_latency(self, line_name: str) -> Optional[float]:
        """获取近 7 天平均延迟（仅成功样本），无数据时返回 None"""
        records = self._data.get(line_name, [])
        cutoff = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
        recent = [r for r in records if r.get("ts", "") >= cutoff and r.get("success") and r.get("avg", -1) > 0]
        if not recent:
            return None
        return sum(r["avg"] for r in recent) / len(recent)

    def get_30d_history(self, line_name: str) -> List[Dict]:
        """获取近 30 天历史记录（按时间正序）"""
        records = self._data.get(line_name, [])
        return sorted(records, key=lambda r: r.get("ts", ""))

    def get_all_line_names(self) -> List[str]:
        return list(self._data.keys())

    def get_health_summary(self) -> Dict[str, Dict[str, Any]]:
        """汇总所有线路的 7 天健康度，供 UI 一次性读取

        返回: {line_name: {"rate": 0.85, "avg_latency": 0.42, "samples": 12, "last_ts": "..."}}
        """
        cutoff = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
        summary = {}
        for name, records in self._data.items():
            if not isinstance(records, list) or not records:
                continue
            recent = [r for r in records if r.get("ts", "") >= cutoff]
            if not recent:
                continue
            succ = [r for r in recent if r.get("success")]
            rate = len(succ) / len(recent)
            avg_lat = sum(r["avg"] for r in succ if r.get("avg", -1) > 0) / len(succ) if succ else None
            summary[name] = {
                "rate": rate,
                "avg_latency": avg_lat,
                "samples": len(recent),
                "last_ts": max(r.get("ts", "") for r in recent),
            }
        return summary


def get_health_db() -> HealthDB:
    """全局单例 HealthDB"""
    global _health_db
    try:
        return _health_db
    except NameError:
        _health_db = HealthDB()
        return _health_db


def format_health_bar(rate: float, width: int = 8) -> str:
    """渲染健康度条形图（▁▂▃▄▅▆▇█ 8 档）

    rate: 0.0 ~ 1.0
    返回: 8 字符的 Unicode 条形图 + 百分数
    """
    if rate is None:
        return "▱▱▱▱▱▱▱▱ -"
    blocks = "▁▂▃▄▅▆▇█"
    # rate → 0-7 档
    level = max(0, min(7, int(rate * 8) - (1 if rate > 0 else 0)))
    if rate >= 0.99:
        level = 7
    filled = blocks[level]
    bar = filled * width
    return f"{bar} {int(rate * 100)}%"


def get_health_label(rate: Optional[float]) -> Tuple[str, str]:
    """根据健康度返回 (文字, 颜色)

    颜色: #4EBA65(绿) / #FF9800(橙) / #FF6B80(红) / #888(灰)
    """
    if rate is None:
        return "无数据", "#888"
    if rate >= 0.8:
        return f"健康 {int(rate * 100)}%", COLOR_GREEN
    if rate >= 0.5:
        return f"一般 {int(rate * 100)}%", COLOR_ORANGE
    return f"差 {int(rate * 100)}%", "#FF6B80"


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


# =====================================================================
# Batch 4: 多上游支持 (备选仓库管理)
# =====================================================================
BACKUP_SOURCES_FILE = os.path.join(USER_DATA_DIR, "backup_sources.json")
BUILTIN_BACKUP_SOURCES_VERSION = 5  # 2026-08-09: 全量切到 GitLab 镜像链路（gitlabip.xyz + gitlab.com），解决 GitHub 被 GFW 封锁导致配置更新失败

# 已知失效的备选源名称（版本升级时自动删除，避免用户看到一堆"未下载"的死源）
DEPRECATED_BACKUP_SOURCE_NAMES = {
    "Alvin9999/PAC (gitlabip)",
    "Alvin9999-newpac/fanqiang (GitHub)",
    "Alvin9999/PAC (GitHub 原始)",
    "v2ray-free (GitHub)",
    "free-nodes (GitHub)",
    "free-nodes/clashfree (GitHub)",
    "Jsnzkpg/Jsnzkpg (GitHub)",
    "mfuu/v2ray (GitHub)",
    "mfuu/v2ray (GitHub→ghfast)",         # ghfast.top DNS 污染后失效
    "ripaojiedian/freenode (GitHub)",
    "ripaojiedian/freenode (GitHub→ghfast)",  # ghfast.top DNS 污染后失效
}


# 内置默认备选上游仓库（首次启动时自动写入 backup_sources.json）
# 每条: (备注名, 主URL, 备用URL列表, 默认启用?)
# 备用 URL 会在主 URL 失败时按顺序尝试。多个备用 URL 能大幅提升可达率。
# 2026-08-09: 全部改为 GitLab 镜像链路（参考可正常使用的 Chrome143_Quick 项目）。
#   主源 gitlabip.xyz 绕过 GFW；备源 gitlab.com 直连兜底。
#   与 CONFIG_URLS 不同的聚合仓库（free9999/ipupdate 主 + Alvin9999/PAC 备）提供额外冗余。
BUILTIN_BACKUP_SOURCES = [
    (
        "free9999/ipupdate 线路合集 (GitLab镜像)",
        "https://www.gitlabip.xyz/free9999/ipupdate/refs/heads/master/backup/img/1/2/ipp/quick/1/config.yaml",
        [
            "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/2/config.yaml",
            "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/3/config.yaml",
            "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/4/config.yaml",
            "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/1/config.yaml",
        ],
        True,
    ),
    (
        "Alvin9999/PAC 线路合集 (GitLab镜像)",
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/2/config.yaml",
        [
            "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/1/config.yaml",
            "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/3/config.yaml",
            "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/4/config.yaml",
            "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/2/config.yaml",
        ],
        True,
    ),
]


@dataclass
class BackupSource:
    """备选上游仓库（当主仓库 CONFIG_URLS 全部下载失败时降级使用）"""
    name: str            # 备注名（如 "备用仓库A"）
    url: str             # 订阅 URL（Clash YAML 格式）
    enabled: bool = True
    last_status: str = "未下载"
    last_error: str = ""
    last_update: str = ""
    urls: List[str] = field(default_factory=list)  # 备用 URL 列表（按顺序尝试）


def load_backup_sources() -> List[BackupSource]:
    """从 user_data/backup_sources.json 加载备选上游仓库列表"""
    try:
        if not os.path.isfile(BACKUP_SOURCES_FILE):
            return []
        with open(BACKUP_SOURCES_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        raw = json.loads(content)
        if not isinstance(raw, list):
            return []
        result = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            urls_field = item.get("urls", [])
            if not isinstance(urls_field, list):
                urls_field = []
            urls_field = [u for u in urls_field if isinstance(u, str) and u.strip()]
            result.append(BackupSource(
                name=item.get("name", ""),
                url=item.get("url", ""),
                enabled=item.get("enabled", True),
                last_status=item.get("last_status", "未下载"),
                last_error=item.get("last_error", ""),
                last_update=item.get("last_update", ""),
                urls=urls_field,
            ))
        return result
    except json.JSONDecodeError as e:
        log.warning(f"加载备选上游仓库失败（JSON损坏）: {e}")
        try:
            bak_path = BACKUP_SOURCES_FILE + ".bak"
            os.replace(BACKUP_SOURCES_FILE, bak_path)
            log.warning(f"已备份损坏文件到 {bak_path}，将重新生成默认备选源")
        except Exception:
            pass
        return []
    except Exception as e:
        log.warning(f"加载备选上游仓库失败: {e}")
        return []


def save_backup_sources(sources: List[BackupSource]):
    """保存备选上游仓库列表到 user_data/backup_sources.json"""
    try:
        os.makedirs(os.path.dirname(BACKUP_SOURCES_FILE), exist_ok=True)
        data = []
        for s in sources:
            data.append({
                "name": s.name,
                "url": s.url,
                "enabled": s.enabled,
                "last_status": s.last_status,
                "last_error": s.last_error,
                "last_update": s.last_update,
                "urls": list(s.urls or []),
            })
        with open(BACKUP_SOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"保存备选上游仓库失败: {e}")


def add_backup_source(name: str, url: str, urls: Optional[List[str]] = None) -> BackupSource:
    """添加一个备选上游仓库，返回新创建的对象。
    name 不能为空且不能与已有的重复。
    urls 是可选的备用 URL 列表（按顺序追加在主 URL 之后尝试）。
    """
    name = (name or "").strip()
    url = (url or "").strip()
    if not name:
        raise ValueError("备注名不能为空")
    if not url:
        raise ValueError("URL 不能为空")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL 必须以 http:// 或 https:// 开头")
    urls_clean = []
    for u in (urls or []):
        u = (u or "").strip()
        if not u:
            continue
        if not (u.startswith("http://") or u.startswith("https://")):
            raise ValueError(f"备用 URL 必须以 http:// 或 https:// 开头: {u}")
        if u == url:
            continue
        urls_clean.append(u)
    sources = load_backup_sources()
    for s in sources:
        if s.name == name:
            raise ValueError(f"已存在同名备选仓库「{name}」")
    new_src = BackupSource(name=name, url=url, enabled=True, urls=urls_clean)
    sources.append(new_src)
    save_backup_sources(sources)
    return new_src


def remove_backup_source(name: str) -> bool:
    """删除指定名称的备选上游仓库"""
    sources = load_backup_sources()
    before = len(sources)
    sources = [s for s in sources if s.name != name]
    if len(sources) < before:
        save_backup_sources(sources)
        return True
    return False


def toggle_backup_source(name: str, enabled: bool):
    """启用/禁用备选上游仓库"""
    sources = load_backup_sources()
    for s in sources:
        if s.name == name:
            s.enabled = enabled
    save_backup_sources(sources)


def update_backup_source_status(name: str, status: str, error: str = ""):
    """更新备选上游仓库的下载状态"""
    sources = load_backup_sources()
    for s in sources:
        if s.name == name:
            s.last_status = status
            s.last_error = error
            s.last_update = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_backup_sources(sources)


def ensure_builtin_backup_sources():
    """首次启动时自动写入内置默认备选上游仓库到 backup_sources.json。

    行为：
    - 如果文件不存在：写入全部内置默认源（保留默认启用状态）
    - 如果文件已存在：检查文件内记录的版本号，低于 BUILTIN_BACKUP_SOURCES_VERSION 时：
      ① 删除已知失效的旧源（DEPRECATED_BACKUP_SOURCE_NAMES）
      ② 追加新出现的内置源（已存在的同名条目不动，避免覆盖用户自定义设置）
    """
    ensure_user_data_dir()
    try:
        version_file = BACKUP_SOURCES_FILE + ".ver"
        current_version = 0
        if os.path.isfile(version_file):
            try:
                with open(version_file, "r", encoding="utf-8") as f:
                    current_version = int((f.read() or "0").strip() or "0")
            except Exception:
                current_version = 0

        existing = load_backup_sources()
        existing_names = {s.name for s in existing}
        new_entries: List[BackupSource] = []

        if current_version < BUILTIN_BACKUP_SOURCES_VERSION:
            # ① 清理已知失效的旧源
            before_count = len(existing)
            existing = [s for s in existing if s.name not in DEPRECATED_BACKUP_SOURCE_NAMES]
            removed_count = before_count - len(existing)
            if removed_count > 0:
                log.info(f"已清理 {removed_count} 个失效备选上游仓库")
            existing_names = {s.name for s in existing}

            # ② 追加新出现的内置源
            for name, primary_url, fallback_urls, default_enabled in BUILTIN_BACKUP_SOURCES:
                if name in existing_names:
                    continue
                new_entries.append(BackupSource(
                    name=name,
                    url=primary_url,
                    enabled=default_enabled,
                    last_status="未下载",
                    last_error="",
                    last_update="",
                    urls=list(fallback_urls or []),
                ))

        if new_entries or current_version < BUILTIN_BACKUP_SOURCES_VERSION:
            existing.extend(new_entries)
            save_backup_sources(existing)
            if new_entries:
                log.info(f"已自动写入 {len(new_entries)} 个内置备选上游仓库到 {BACKUP_SOURCES_FILE}")

        # 无论是否新增，都更新版本号（防止下次重复检查逻辑执行时漏掉）
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(str(BUILTIN_BACKUP_SOURCES_VERSION))
    except Exception as e:
        log.warning(f"自动写入内置备选上游仓库失败: {e}")


def get_all_backup_urls(src: BackupSource) -> List[str]:
    """获取一个备选上游仓库的所有下载 URL（主 URL + 备用 URL，去重保序）"""
    seen = set()
    out: List[str] = []
    for u in [src.url] + list(src.urls or []):
        u = (u or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


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
QPushButton#small-blue-solid {{ background-color: {COLOR_BLUE}; color: #FFFFFF; padding: 3px 8px; font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; }}
QPushButton#small-blue-solid:hover {{ background-color: #1976D2; }}
QPushButton#small-blue-solid:disabled {{ background-color: #1A1A1A; color: #555555; }}
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

QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 4px 8px; color: {COLOR_TEXT}; font-size: 9pt; }}
QLineEdit[readOnly="true"] {{ background-color: #0a0a0a; color: #888; }}
QLineEdit:disabled {{ background-color: #1A1A1A; color: #555; }}

QComboBox {{ background-color: #111; border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 4px 8px; color: {COLOR_TEXT}; font-size: 8pt; }}
QComboBox::drop-down {{ border: none; width: 20px; background-color: transparent; }}
QComboBox QAbstractItemView {{ background-color: #111111; color: {COLOR_TEXT}; selection-background-color: #FF0000; border: 1px solid {COLOR_BORDER}; outline: none; }}
QComboBox QAbstractItemView::item {{ padding: 4px 8px; }}
QComboBox QAbstractItemView::item:hover {{ background-color: #CC0000; color: #FFFFFF; }}
QComboBox QAbstractItemView::item:selected {{ background-color: #FF0000; color: #FFFFFF; }}

QSpinBox {{ background-color: #111; border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 3px 6px; color: {COLOR_TEXT}; font-size: 8pt; }}
QSpinBox::up-button, QSpinBox::down-button {{ background-color: #2D2D2D; border: none; width: 18px; }}
QSpinBox:disabled {{ background-color: #1A1A1A; color: #555; }}

QTextEdit#log {{ background-color: #0A0A0A; color: #AAAAAA; border: 1px solid {COLOR_BORDER}; border-radius: 4px; font-family: "Consolas", "Courier New", monospace; font-size: 7pt; padding: 4px; }}
"""


class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, label="", parent=None, default=False, color_on=None):
        super().__init__(parent)
        self._checked = default
        self._label = label
        # 不再固定高度，由内容自适应，避免挤占其他行
        self.setMinimumHeight(24)
        self._update_cursor()

        self._track_color_off = QColor("#3A3A3A")
        self._track_color_on = QColor(color_on or COLOR_RED_LIGHT)
        self._thumb_color = QColor("#FFFFFF")
        self._thumb_x = 4.0
        self._anim = QPropertyAnimation(self, b"thumb_x")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        if default:
            self._thumb_x = 42.0

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
        # 动画范围基于 64px track 的 thumb 偏移 (4=左, 42=右)
        # paintEvent 会按 actual_track_w 缩放，所以这里用 64 基准即可
        self._anim.setStartValue(self._thumb_x)
        self._anim.setEndValue(42.0 if self._checked else 4.0)
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
        # 严格裁切到 widget 范围内，避免任何元素画到边界外
        painter.setClipRect(self.rect())

        total_w = self.width()
        total_h = self.height()
        track_h = 22
        track_r = 11
        track_w = 64
        # 关键修复：保证 track 起点 >= 0，不画到 widget 外
        # 想要 layout 是：右 8px 边距 + 64px track + 8px 间隔 + label
        # 如果 widget 太小装不下完整 track，则按比例缩小
        right_margin = 4
        if total_w >= track_w + right_margin:
            track_rect_x = total_w - track_w - right_margin
            actual_track_w = track_w
        else:
            track_rect_x = 0
            actual_track_w = max(0, total_w)
        track_rect_y = (total_h - track_h) // 2

        if self._label:
            label_color = QColor(COLOR_DIM) if not self.isEnabled() else QColor(COLOR_TEXT)
            painter.setPen(label_color)
            painter.setFont(QFont("Microsoft YaHei UI", 9))
            # label 范围：从 0 到 track 起点 - 4
            label_w = max(0, track_rect_x - 4)
            if label_w > 0:
                painter.drawText(0, 0, label_w, total_h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)

        if self.isEnabled():
            track_color = self._track_color_on if self._checked else self._track_color_off
            thumb_color = self._thumb_color
        else:
            track_color = QColor("#2A2A2A") if not self._checked else QColor("#5A3A2A")
            thumb_color = QColor(COLOR_DIM)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(int(track_rect_x), track_rect_y, int(actual_track_w), track_h, track_r, track_r)

        # thumb 严格在 track 内绘制
        thumb_r = 9
        if actual_track_w >= thumb_r * 2 + 2:
            thumb_cx = track_rect_x + self._thumb_x * (actual_track_w / 64.0) + thumb_r
        else:
            thumb_cx = track_rect_x + actual_track_w // 2
        thumb_cy = track_rect_y + track_h // 2
        painter.setBrush(thumb_color)
        painter.drawEllipse(QPoint(int(thumb_cx), int(thumb_cy)), thumb_r, thumb_r)

        painter.end()

    def minimumSizeHint(self):
        # 最小宽度：label 60 + 间隔 4 + track 64 + 右边距 4 = 132（带 label 时）
        # 无 label 时只要装下 track + 边距 = 72
        if self._label:
            return QSize(132, 24)
        return QSize(72, 24)

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

    def setText(self, text):
        """动态更新标签文本"""
        if self._label != text:
            self._label = text
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._block_signal:
                return
            # 已经被选中时不再触发 toggle（避免误触）
            if self._checked:
                return
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

    def wheelEvent(self, event):
        # 禁止鼠标滚轮切换选项，避免误操作
        event.ignore()


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



# ── 自动部署（参考 云集智能音乐创意台 launcher._self_relocate 的成熟范式）──
# 机制：
#   - 便携版本号 EXE 首次运行 → 在同级建 <BRAND_NAME>/ 品牌文件夹（含 app/ver/），
#     写 version.txt + .yunji.lock，复制自身进 ver/，生成固定名入口 <BRAND_NAME>.exe，
#     分离式 spawn 入口（携带 --cleanup=<原始便携exe>）+ os._exit 退出自身；
#   - 入口 / 已部署运行 → 解析到品牌目录，先把“原始便携 exe”归档进 ver/ 并删除
#     （--cleanup），并确保固定名入口始终指向 ver/ 中最新版本（软件更新下载到 ver/ 切换版本）。
ENTRY_EXE_NAME = f"{BRAND_NAME}.exe"
VERSION_TXT = "version.txt"
_DEPLOY_SUBDIRS = [_CFG["paths"]["app"], _CFG["paths"]["ver"]]


def _resolve_deploy_dir(exe_path):
    """解析部署根目录（<exe_dir>/<BRAND_NAME>/ 或向上找到已存在的品牌目录）。

    与参考 launcher._resolve_deploy_dir 同源：逐级向上查找已存在的品牌目录
    （已部署时命中，避免把部署目录算成自身子目录导致无限嵌套 WinError 206）；
    找不到则回退到 exe 同级 <BRAND_NAME>。
    """
    exe_dir = os.path.dirname(os.path.abspath(exe_path))
    d = exe_dir
    while True:
        if os.path.basename(d) == BRAND_NAME:
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.join(exe_dir, BRAND_NAME)


def _safe_delete(path):
    """带重试地删除文件（Windows 偶发 PermissionError）。"""
    for _ in range(15):
        try:
            if os.path.exists(path):
                os.remove(path)
            return
        except PermissionError:
            time.sleep(0.3)
        except Exception:
            return


def _parse_cleanup():
    for a in sys.argv[1:]:
        if a.startswith("--cleanup="):
            return a.split("=", 1)[1]
    return None


def _find_newest_versioned_exe(deploy_dir, current_exe):
    """在 ver/ 中找出版本号最大的版本号 exe；当前运行的版本号 exe 也参与比较。"""
    candidates = []
    ver_dir = os.path.join(deploy_dir, _CFG["paths"]["ver"])
    if os.path.isdir(ver_dir):
        for name in os.listdir(ver_dir):
            mm = re.search(r'v(\d+\.\d+\.\d+\.\d+)', name)
            if name.lower().endswith(".exe") and mm:
                candidates.append((mm.group(1), os.path.join(ver_dir, name)))
    cur_m = re.search(r'v(\d+\.\d+\.\d+\.\d+)', os.path.basename(current_exe))
    if cur_m:
        candidates.append((cur_m.group(1), os.path.abspath(current_exe)))
    if not candidates:
        return None
    def _vt(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except Exception:
            return (0,)
    try:
        return max(candidates, key=lambda c: _vt(c[0]))[1]
    except Exception:
        return candidates[-1][1]


def _entry_points_to(entry_exe, target_exe):
    """判断 entry_exe 是否已硬链接/指向 target_exe（按 st_dev+st_ino 文件标识）。"""
    try:
        s1 = os.stat(entry_exe)
        s2 = os.stat(target_exe)
        return (s1.st_dev, s1.st_ino) == (s2.st_dev, s2.st_ino)
    except Exception:
        return False


def _ensure_entry_current(deploy_dir, current_exe):
    """确保固定名入口始终指向 ver/ 中最新的版本号 exe（软件更新切换版本）。"""
    entry_exe = os.path.join(deploy_dir, ENTRY_EXE_NAME)
    newest = _find_newest_versioned_exe(deploy_dir, current_exe)
    if newest is None:
        return entry_exe if os.path.exists(entry_exe) else None
    if os.path.exists(entry_exe) and _entry_points_to(entry_exe, newest):
        return entry_exe
    try:
        if os.path.exists(entry_exe):
            _safe_delete(entry_exe)
        try:
            os.link(newest, entry_exe)
        except Exception:
            shutil.copy2(newest, entry_exe)
    except Exception:
        pass
    return entry_exe if os.path.exists(entry_exe) else None


def _self_deploy():
    """自动部署闭环（参考 launcher._self_relocate）。

    返回部署根目录（品牌文件夹）。首跑会 spawn 入口并 os._exit(0) 退出自身。
    必须在单实例之前、GUI 创建之前调用（main() 顶部），以保证 os._exit 干净且
    便携 exe 部署阶段不持有互斥体（避免入口被自身 mutex 误判“已运行”而退出）。
    """
    if not getattr(sys, 'frozen', False):
        return _find_dev_dir()

    exe = os.path.abspath(sys.executable)
    exe_name = os.path.basename(exe)
    exe_dir = os.path.dirname(exe)

    # 入口被拉起时携带 --cleanup=<原始便携 exe>：删除原始便携 exe（f7d9105 proven 机制，
    # os.remove 无需管理员、不触发杀软——即用户所说“入口启动新 exe 就可以删除自身 exe”）。
    cleanup_target = _parse_cleanup()

    deploy_dir = _resolve_deploy_dir(exe)
    already = os.path.isdir(deploy_dir) and (
        os.path.isfile(os.path.join(deploy_dir, VERSION_TXT))
        or os.path.isfile(os.path.join(deploy_dir, _CFG["paths"]["lock_file"]))
    )

    if already:
        # 已部署：归档并删除被我们拉起的原始便携 exe（若有）
        if cleanup_target and os.path.exists(cleanup_target):
            try:
                ver_dir = os.path.join(deploy_dir, _CFG["paths"]["ver"])
                os.makedirs(ver_dir, exist_ok=True)
                dst = os.path.join(ver_dir, os.path.basename(cleanup_target))
                if not os.path.exists(dst):
                    shutil.copy2(cleanup_target, dst)
            except Exception:
                pass
            _safe_delete(cleanup_target)
        # 版本切换：若当前运行的不是 ver/ 中最新版（如手动双击新下载的便携 exe），
        # 归档进 ver/、重建入口指向它、重启入口、退出自身，保证运行的是入口。
        newest = _find_newest_versioned_exe(deploy_dir, exe)
        if newest and not _entry_points_to(exe, newest):
            try:
                ver_dir = os.path.join(deploy_dir, _CFG["paths"]["ver"])
                os.makedirs(ver_dir, exist_ok=True)
                # 守卫：ver/ 只接受「版本号 exe」。禁止把固定名入口(普通名 exe_name)
                # 归档进 ver/，否则会多出一份与版本号 exe 内容完全相同的冗余 exe（白占 ~84MB）。
                if re.search(r'v\d+\.\d+\.\d+\.\d+', exe_name):
                    dst = os.path.join(ver_dir, exe_name)
                    if not os.path.exists(dst):
                        shutil.copy2(exe, dst)
            except Exception:
                pass
            _ensure_entry_current(deploy_dir, exe)
            entry_exe = os.path.join(deploy_dir, ENTRY_EXE_NAME)
            if os.path.exists(entry_exe) and os.path.abspath(entry_exe) != exe:
                try:
                    subprocess.Popen([entry_exe],
                                    creationflags=0x00000008 | 0x08000000 | 0x00000200,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
                except Exception:
                    pass
                time.sleep(1.2)
                os._exit(0)
        _ensure_entry_current(deploy_dir, exe)
        return deploy_dir

    # ── 首次运行：建品牌文件夹 ──
    os.makedirs(deploy_dir, exist_ok=True)
    for sub in _DEPLOY_SUBDIRS:
        os.makedirs(os.path.join(deploy_dir, sub), exist_ok=True)

    # 历史兼容：旧版（≤1540/0717）把数据散落在 exe_dir 根下（.yunji.lock / app / Quick /
    # launcher_settings.json），迁移到品牌文件夹，避免重复与污染（仅当目标不存在时移动）。
    _legacy_lock = os.path.join(exe_dir, _CFG["paths"]["lock_file"])
    if os.path.isfile(_legacy_lock):
        try:
            os.remove(_legacy_lock)
        except Exception:
            pass
    _old_app = os.path.join(exe_dir, "app")
    _new_app = os.path.join(deploy_dir, "app")
    if os.path.isdir(_old_app) and not os.path.isdir(_new_app):
        try:
            shutil.move(_old_app, _new_app)
        except Exception:
            pass
    _old_quick = os.path.join(exe_dir, "Quick")
    _new_quick = os.path.join(deploy_dir, "app", "Quick")
    if os.path.isdir(_old_quick) and not os.path.isdir(_new_quick):
        try:
            shutil.move(_old_quick, _new_quick)
        except Exception:
            pass
    _old_cfg = os.path.join(exe_dir, "launcher_settings.json")
    _new_cfg = os.path.join(deploy_dir, "app", "launcher_settings.json")
    if os.path.isfile(_old_cfg) and not os.path.isfile(_new_cfg):
        try:
            shutil.move(_old_cfg, _new_cfg)
        except Exception:
            pass

    # 写 version.txt（main.py 按 ^\d+\.\d+\.\d+(\.\d+)?$ 解析）
    m = re.search(r'v(\d+\.\d+\.\d+\.\d+)', exe_name)
    version = m.group(1) if m else datetime.now().strftime("%Y.%m.%d.%H%M")
    try:
        with open(os.path.join(deploy_dir, VERSION_TXT), "w", encoding="utf-8") as f:
            f.write(version)
    except Exception:
        pass
    try:
        with open(os.path.join(deploy_dir, _CFG["paths"]["lock_file"]), "w", encoding="utf-8") as f:
            f.write("yunji")
    except Exception:
        pass

    # 生成固定名入口（硬链接优先，失败回退复制）
    entry_exe = os.path.join(deploy_dir, ENTRY_EXE_NAME)
    if not os.path.exists(entry_exe) and os.path.abspath(entry_exe) != exe:
        try:
            os.link(exe, entry_exe)
        except Exception:
            try:
                shutil.copy2(exe, entry_exe)
            except Exception:
                entry_exe = None

    # 归档一份进 ver/（供 _ensure_entry_current 指向最新版、版本回滚）
    ver_dir = os.path.join(deploy_dir, _CFG["paths"]["ver"])
    os.makedirs(ver_dir, exist_ok=True)
    ver_target = os.path.join(ver_dir, exe_name)
    if os.path.abspath(ver_target) != exe and not os.path.exists(ver_target):
        try:
            shutil.copy2(exe, ver_target)
        except Exception:
            pass

    # 桌面快捷方式（异步，静默）
    if entry_exe and os.path.exists(entry_exe):
        import threading
        threading.Thread(target=_create_desktop_shortcut, args=(entry_exe,), daemon=True).start()

    # 首跑：分离式拉起固定名入口（携带 --cleanup=<原始便携exe>）后退出自身
    if entry_exe and os.path.exists(entry_exe) and os.path.abspath(entry_exe) != exe:
        try:
            _child = subprocess.Popen(
                [entry_exe, "--cleanup=" + exe],
                creationflags=0x00000008 | 0x08000000 | 0x00000200,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            _child = None
        if _child is not None:
            try:
                ctypes.windll.user32.AllowSetForegroundWindow(_child.pid)
            except Exception:
                pass
            time.sleep(1.5)
            os._exit(0)

    # 兜底：入口未拉起（被杀软拦截）→ 本进程直接继续运行
    return deploy_dir


def _create_desktop_shortcut(entry_exe):
    """在桌面创建指向入口EXE的硬链接快捷方式"""
    try:
        # 通过注册表获取桌面路径
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders") as key:
            desktop_path = winreg.QueryValueEx(key, "Desktop")[0]
        if not desktop_path or not os.path.isdir(desktop_path):
            return

        base_name = BRAND_NAME
        # 使用 .lnk 快捷方式（标准方式，桌面图标美观）
        lnk_path = os.path.join(desktop_path, f"{base_name}.lnk")
        # 如果已存在同名硬链接文件，先删除
        exe_link = os.path.join(desktop_path, f"{base_name}.exe")
        if os.path.isfile(exe_link):
            try:
                os.remove(exe_link)
            except OSError:
                pass
        # 如果快捷方式不存在，则创建
        if not os.path.isfile(lnk_path):
            _create_windows_shortcut(lnk_path, entry_exe)
    except Exception as e:
        log.warning(f"创建桌面快捷方式失败: {e}")


def _create_windows_shortcut(lnk_path, target_exe):
    """在桌面创建硬链接文件（同名 .exe），双击即启动入口

    优先级（全程不弹任何窗口）：
    1. ctypes.windll.kernel32.CreateHardLinkW —— 直接系统调用，最快最静
    2. os.link —— Pythonic 硬链接，同上不产生新进程
    3. 复制入口 EXE（最坏情况，至少保证桌面有可点图标）
    """
    # 方案1：ctypes 直接调用 Win32 API（无任何进程产生，绝对静默）
    try:
        if not os.path.isfile(lnk_path):
            if ctypes.windll.kernel32.CreateHardLinkW(
                ctypes.c_wchar_p(lnk_path),
                ctypes.c_wchar_p(target_exe),
                None
            ):
                return
    except Exception:
        pass

    # 方案2：os.link（同盘符时与方案1等价，也无新进程）
    try:
        if not os.path.isfile(lnk_path):
            os.link(target_exe, lnk_path)
            return
    except OSError:
        pass

    # 方案3：最后回退到文件复制（保证至少能双击启动，仍静默无窗口）
    try:
        if not os.path.isfile(lnk_path):
            shutil.copy2(target_exe, lnk_path)
    except Exception:
        pass


def _find_dev_dir():
    if getattr(sys, 'frozen', False):
        # 已部署态：部署根由 _self_deploy 在 main() 顶部完成（含品牌文件夹创建与版本切换），
        # 这里只负责解析部署根目录（<exe_dir>/<BRAND_NAME>/ 或向上找到已存在的品牌目录），
        # 不再在此触发部署，避免递归/双重部署。
        return _resolve_deploy_dir(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_base_dir():
    return _find_dev_dir()


def get_app_dir():
    # 开发态与打包态使用同一套公式：<根目录>/app。
    # - 开发态：根目录 = dev/         → dev/app/（内核 Quick、配置、日志、设置全在此）
    # - 打包态：根目录 = EXE 所在目录 → <EXE目录>/app/（与 dev/app 完全镜像，
    #   相对 EXE 目录、绿色便携，换机器/目录即可运行，彻底消除扁平 exe 目录差异）
    d = os.path.join(get_base_dir(), _CFG["paths"]["app"])
    os.makedirs(d, exist_ok=True)
    # 一次性迁移：旧版扁平 exe_dir/Quick（及 launcher_settings.json）迁移到镜像 dev 的
    # exe_dir/app/，避免丢失已下载的真实配置与本地设置（仅当目标不存在时才移动）。
    if getattr(sys, 'frozen', False):
        _old_quick = os.path.join(get_base_dir(), "Quick")
        if os.path.isdir(_old_quick) and not os.path.isdir(os.path.join(d, "Quick")):
            try:
                shutil.move(_old_quick, os.path.join(d, "Quick"))
                _diagnose(f"已迁移旧数据目录 {_old_quick} -> {os.path.join(d, 'Quick')}")
            except Exception as _e:
                log.warning(f"迁移旧 Quick 目录失败(可忽略): {_e}")
        _old_cfg = os.path.join(get_base_dir(), "launcher_settings.json")
        _new_cfg = os.path.join(d, "launcher_settings.json")
        if os.path.isfile(_old_cfg) and not os.path.isfile(_new_cfg):
            try:
                shutil.move(_old_cfg, _new_cfg)
            except Exception:
                pass
    return d


def find_quick_dir():
    builtin_quick = os.path.join(get_app_dir(), "Quick")
    if os.path.isdir(builtin_quick) and os.path.isfile(os.path.join(builtin_quick, "quick.exe")):
        return builtin_quick
    saved = load_settings().get("quick_dir_path", "")
    if saved and os.path.isdir(saved) and os.path.isfile(os.path.join(saved, "quick.exe")):
        return saved
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


def _diagnose(msg):
    """把启动诊断写入用户易找到的日志文件：<app目录>/启动诊断.log。

    开发能跑、EXE 跑不了的差异定位长期卡在“用户只说‘还是不行’、拿不到真机报错”。
    本函数把所有关键启动事件（内核 fatal 行号、选线结果、端口占用）写到一个固定路径，
    用户只需把该文件贴回即可精确定位，避免在 config/端口/坏订阅之间反复盲猜。
    """
    try:
        d = get_app_dir()
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "启动诊断.log")
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(p, "a", encoding="utf-8") as _f:
            _f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def is_proxy_running():
    # 依次尝试配置主机与 127.0.0.1（IPv4 兜底）：当 proxy_host 为 "localhost" 时，
    # getaddrinfo 可能优先返回 ::1(IPv6)，而 mihomo 仅绑定 IPv4 的 127.0.0.1，
    # 仅连 ::1 会误报“代理未就绪”。强制补试 127.0.0.1 规避该 IPv4/IPv6 错配。
    hosts = [PROXY_HOST]
    if PROXY_HOST != "127.0.0.1":
        hosts.append("127.0.0.1")
    for host in hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((host, PROXY_PORT))
            sock.close()
            if result == 0:
                return True
        except Exception:
            pass
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


# DNS-over-HTTPS 服务器（国内可达，用于绕过 DNS 污染解析真实 IP）
_DOH_SERVERS = [
    "https://dns.alidns.com/resolve",
    "https://doh.pub/dns-query",
]


def _resolve_via_doh(host):
    """通过 DNS-over-HTTPS 解析域名真实 IP（绕过本地 DNS 污染）。
    返回 IPv4 地址列表，全部失败返回空列表。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # 强制直连 DoH 服务器，避免被本机系统代理 / HTTPS_PROXY 环境变量劫持
    # （下载阶段应用自身代理通常尚未启动，走代理会静默失败）
    doh_opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ctx),
    )
    for doh_url in _DOH_SERVERS:
        try:
            query_url = f"{doh_url}?name={host}&type=A"
            req = urllib.request.Request(query_url, headers={
                "Accept": "application/dns-json",
                "User-Agent": "Mozilla/5.0",
            })
            with doh_opener.open(req, timeout=5) as resp:
                result = json.loads(resp.read())
                answers = result.get("Answer", [])
                ips = [a["data"] for a in answers if a.get("type") == 1]
                if ips:
                    log.info(f"DoH {doh_url}: {host} -> {ips}")
                    return ips
        except Exception as e:
            log.debug(f"DoH {doh_url} 失败 ({host}): {type(e).__name__}: {e}")
    return []


def _try_doh_ip_download(url, host, ips, timeout):
    """尝试通过 DoH 解析出的 IP 直连下载（SNI=host, Host header=host）。
    逐个尝试 IP，第一个成功即返回数据。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    parsed = urllib.parse.urlparse(url)
    path = parsed.path + ("?" + parsed.query if parsed.query else "")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for ip in ips:
        try:
            sock = socket.create_connection((ip, port), timeout=timeout)
            ssock = ctx.wrap_socket(sock, server_hostname=host)
            conn = http.client.HTTPSConnection(ip, port, context=ctx, timeout=timeout)
            conn.sock = ssock
            conn.request("GET", path, headers={
                "Host": host,
                "User-Agent": "Mozilla/5.0",
            })
            resp = conn.getresponse()
            status = resp.status
            data = resp.read()
            conn.close()
            if status != 200:
                log.debug(f"DoH+IP {ip} 返回 HTTP {status} ({host})，跳过")
                continue
            # 防止把错误页面 HTML 当作 Clash YAML 写入配置
            head = data.lstrip()[:1]
            if head and head not in (b"#", b"-", b"{", b"[", b"p", b"r"):
                # Clash YAML 通常以 # / - / { / [ 或 proxy key 开头；HTML 以 < 开头
                if data.lstrip().startswith(b"<"):
                    log.debug(f"DoH+IP {ip} 返回非 YAML 内容（疑似 HTML）({host})，跳过")
                    continue
            log.info(f"DoH+IP 直连成功: {host} via {ip} ({len(data)} bytes)")
            return data
        except Exception as e:
            log.debug(f"DoH+IP {ip} 失败 ({host}): {type(e).__name__}: {e}")
    raise urllib.error.URLError(
        f"DoH+IP: 所有 IP 均失败 ({host}: {ips})"
    )


def _is_valid_config_bytes(data):
    """粗略判断下载到的字节是否像 Clash 配置（而非 HTML 错误页/空文件）。"""
    if not data or len(data) < 20:
        return False
    head = data.lstrip()[:1]
    if head.startswith(b"<"):
        return False
    # Clash YAML 常见起始： # / - / { / [ / proxy(s): / port: / mixed-port: / 任意可见文本
    if head in (b"#", b"-", b"{", b"[", b"p", b"r", b"m", b"v"):
        return True
    return bool(head) and head.isalpha()


def _expand_mirrors(url):
    """对 GitHub 原始/API 链接生成国内镜像候选（按可靠性排序），原始链接放最后兜底。

    返回 [(candidate_url, kind), ...]：
      'mirror' -> 普通直连（镜像站服务端已拉取，无需 DoH）
      'doh'    -> 原始 GitHub 链接，走 DoH+IP 直连
      'raw'    -> 非 GitHub 链接，普通直连

    2026-08-09: 新增 GitLab 镜像链路。gitlab.com 的 raw 链接自动转为
      gitlabip.xyz（专用于绕过 GFW 的 GitLab 镜像域名），作为最优先直连候选。
    """
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.endswith("raw.githubusercontent.com") or host in ("github.com", "api.github.com"):
        m = re.match(r"^/([^/]+)/([^/]+)/(?:raw/)?([^/]+)/(.*)$", parsed.path)
        out = []
        # ghproxy.net 前缀（可代理 raw 与 api），国内最稳
        out.append(("https://ghproxy.net/" + url, "mirror"))
        # jsDelivr（仅 raw 类路径可转换为 gh 形式）
        if m and host.endswith("raw.githubusercontent.com"):
            owner, repo, branch, path = m.groups()
            out.append((f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}", "mirror"))
        kind = "doh" if host.endswith("raw.githubusercontent.com") else "raw"
        out.append((url, kind))
        return out
    # GitLab 镜像链路：gitlab.com 的 /-/raw/ 链接转 gitlabip.xyz/refs/heads/ 形式
    if host == "gitlab.com":
        m = re.match(r"^/([^/]+)/([^/]+)/-/raw/([^/]+)/(.*)$", parsed.path)
        if m:
            owner, repo, branch, path = m.groups()
            mirror = f"https://www.gitlabip.xyz/{owner}/{repo}/refs/heads/{branch}/{path}"
            return [(mirror, "mirror"), (url, "raw")]
    return [(url, "raw")]


def download_config(url, timeout=30):
    """下载配置文件，多级回退，针对国内网络优化。

    回退顺序：
    0. 国内 GitHub 镜像直连（ghproxy.net / jsDelivr）—— 专为绕过 GFW 对 GitHub 的
       IP/SNI 封锁设计，绝大多数国内网络最稳最快，最优先。
    1. DNS-over-HTTPS + IP 直连 —— 兜底绕过 DNS 污染（部分网络仍可用）。
    2. 走 PROXY_URL（应用代理在跑时）。
    3. 强制直连（绕过系统代理/HTTPS_PROXY 环境变量）。
    4. 走 urlopen() 尊重环境代理。
    5. 显式走 127.0.0.1:7890。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    is_ip = bool(host) and host.replace(".", "").isdigit()

    candidates = _expand_mirrors(url)
    last_err = None

    # 层级 0：国内镜像直连（最优先，绕过 GFW 对 GitHub 的封锁）
    for cu, kind in candidates:
        if kind != "mirror":
            continue
        try:
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx), proxy_handler)
            req = urllib.request.Request(cu, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as resp:
                data = resp.read()
            if _is_valid_config_bytes(data):
                log.info(f"镜像下载成功 ({cu}) {len(data)}B")
                return data
            else:
                log.debug(f"镜像返回非配置内容 ({cu})，跳过")
        except Exception as e:
            last_err = e
            log.debug(f"镜像下载失败 ({cu}): {type(e).__name__}: {e}")

    # 层级 1：DoH+IP 直连（原始 GitHub 链接，兜底绕过 DNS 污染）
    if not is_ip and host:
        try:
            ips = _resolve_via_doh(host)
            if ips:
                data = _try_doh_ip_download(url, host, ips, timeout)
                if data and _is_valid_config_bytes(data):
                    log.info(f"DoH+IP 下载成功 ({host})")
                    return data
        except Exception as e:
            last_err = e
            log.debug(f"DoH+IP 失败 ({host}): {type(e).__name__}: {e}")

    # 层级 2：走 PROXY_URL（代理进程在跑时）
    if is_proxy_running():
        try:
            proxy_handler = urllib.request.ProxyHandler({
                'http': f'http://{PROXY_URL}',
                'https': f'http://{PROXY_URL}',
            })
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx),
                proxy_handler,
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as resp:
                data = resp.read()
            if _is_valid_config_bytes(data):
                log.info(f"代理下载成功 ({url})")
                return data
        except Exception as e:
            last_err = e
            log.debug(f"走 PROXY_URL 失败 ({url}): {type(e).__name__}: {e}")

    # 层级 3：强制直连（绕过 Windows 系统代理/HTTPS_PROXY 环境变量）
    try:
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            proxy_handler,
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read()
        if _is_valid_config_bytes(data):
            log.info(f"直连下载成功 ({url})")
            return data
    except Exception as e:
        last_err = e
        log.debug(f"强制直连失败 ({url}): {type(e).__name__}: {e}")

    # 层级 4：走 urlopen()，尊重环境代理设置（兜底）
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            data = resp.read()
        if _is_valid_config_bytes(data):
            log.info(f"urlopen 下载成功 ({url})")
            return data
    except Exception as e:
        last_err = e
        log.debug(f"urlopen 失败 ({url}): {type(e).__name__}: {e}")

    # 层级 5：显式走 127.0.0.1:7890（最后兜底）
    try:
        proxy_handler = urllib.request.ProxyHandler({
            'http': f'http://127.0.0.1:7890',
            'https': f'http://127.0.0.1:7890',
        })
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            proxy_handler,
        )
        req2 = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req2, timeout=8) as resp:
            data = resp.read()
        if _is_valid_config_bytes(data):
            log.info(f"127.0.0.1:7890 下载成功 ({url})")
            return data
    except Exception as e:
        last_err = e
        log.debug(f"127.0.0.1:7890 失败 ({url}): {type(e).__name__}: {e}")

    raise urllib.error.URLError(f"所有下载方式均失败 (last_err={last_err})")



# ========== free-nodes/clashfree 最新日期文件自动发现 ==========
# 该仓库每日生成 clashYYYYMMDD.yml，旧文件会被清理，硬编码日期会 404。
# 改为运行时自动发现最新日期文件，避免每次手动改 URL。
_FREENODES_RAW_TPL = "https://raw.githubusercontent.com/free-nodes/clashfree/main/clash{date}.yml"
_FREENODES_CACHE_TTL = 6 * 3600  # 缓存 6 小时，避免频繁打 GitHub API（有速率限制）
if getattr(sys, 'frozen', False):
    _FREENODES_APP_BASE = os.path.dirname(os.path.abspath(sys.executable))
else:
    _FREENODES_APP_BASE = os.path.dirname(os.path.abspath(__file__))
_FREENODES_CACHE_FILE = os.path.join(_FREENODES_APP_BASE, ".freenodes_latest.txt")
_free_nodes_latest = {"date": None, "ts": 0.0}


def _github_api_json(api_path):
    """通过 DoH+IP 直连 GitHub API（api.github.com 同样被 DNS 污染）。
    返回解析后的 JSON；失败返回 None。
    """
    host = "api.github.com"
    url = f"https://{host}{api_path}"
    # 先试国内 ghproxy 镜像（api.github.com 也常被封锁，镜像站服务端拉取）
    try:
        req = urllib.request.Request(
            "https://ghproxy.net/" + url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                return json.loads(r.read())
    except Exception as e:
        log.debug(f"GitHub API ghproxy 镜像失败 ({api_path}): {type(e).__name__}: {e}")
    # 回退：DoH+IP 直连
    ips = _resolve_via_doh(host)
    if not ips:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    parsed = urllib.parse.urlparse(url)
    req_path = parsed.path + (("?" + parsed.query) if parsed.query else "")
    for ip in ips:
        try:
            sock = socket.create_connection((ip, 443), timeout=10)
            ssock = ctx.wrap_socket(sock, server_hostname=host)
            conn = http.client.HTTPSConnection(ip, 443, context=ctx, timeout=10)
            conn.sock = ssock
            conn.request("GET", req_path, headers={
                "Host": host,
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/vnd.github+json",
            })
            resp = conn.getresponse()
            if resp.status != 200:
                conn.close()
                continue
            data = resp.read()
            conn.close()
            return json.loads(data)
        except Exception as e:
            log.debug(f"GitHub API {ip} 失败 ({api_path}): {type(e).__name__}: {e}")
    return None


def _load_freenodes_cache():
    try:
        if os.path.isfile(_FREENODES_CACHE_FILE):
            with open(_FREENODES_CACHE_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _save_freenodes_cache(date):
    try:
        with open(_FREENODES_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(date)
    except Exception:
        pass


def _discover_freenodes_latest_date():
    """发现 free-nodes/clashfree 最新 clashYYYYMMDD 日期。失败返回 ''。

    策略：
    1) GitHub API 列目录，取最大日期（最准确）
    2) API 失败/限流 → 从今天往回探测 7 天，第一个可下载的即最新可用
    """
    # 1) GitHub API（api.github.com 同样被 DNS 污染，走 DoH+IP）
    try:
        items = _github_api_json("/repos/free-nodes/clashfree/contents/")
        if items:
            dates = []
            for it in items:
                m = re.match(r"^clash(\d{8})\.yml$", it.get("name", ""))
                # 跳过当天尚未生成的空文件（size=0），否则会选到 0 字节的占位文件
                if m and it.get("size", 0) > 100:
                    dates.append(m.group(1))
            if dates:
                latest = max(dates)
                log.info(f"自动发现 free-nodes 最新文件: clash{latest}.yml (GitHub API)")
                return latest
    except Exception as e:
        log.debug(f"GitHub API 发现失败: {e}")

    # 2) 日期探测回退（复用 download_config 的 DoH+IP 链路，不走 API 不计速率）
    try:
        today = date.today()
        for back in range(0, 8):
            ds = (today - timedelta(days=back)).strftime("%Y%m%d")
            try:
                data = download_config(_FREENODES_RAW_TPL.format(date=ds), timeout=10)
                # 要求非空且体积合理（>100B），并排除 HTML 错误页
                if data and len(data) > 100 and not data.lstrip().startswith(b"<"):
                    log.info(f"自动发现 free-nodes 最新文件: clash{ds}.yml (日期探测)")
                    return ds
            except Exception:
                continue
    except Exception as e:
        log.debug(f"日期探测失败: {e}")
    return ""


def get_freenodes_latest_url(force=False):
    """返回 free-nodes 最新 clashYYYYMMDD.yml 的 raw URL（带 6h 缓存）。"""
    global _free_nodes_latest
    now = time.time()
    if not force and _free_nodes_latest.get("date"):
        if now - _free_nodes_latest.get("ts", 0) < _FREENODES_CACHE_TTL:
            return _FREENODES_RAW_TPL.format(date=_free_nodes_latest["date"])

    latest_date = _discover_freenodes_latest_date()
    if latest_date:
        _free_nodes_latest = {"date": latest_date, "ts": now}
        _save_freenodes_cache(latest_date)
        return _FREENODES_RAW_TPL.format(date=latest_date)

    # 发现失败：退回文件缓存（即便旧也尽量可用），再不行用硬编码兜底
    cached = _load_freenodes_cache()
    if cached:
        log.warning("free-nodes 自动发现失败，使用缓存日期 clash%s.yml" % cached)
        return _FREENODES_RAW_TPL.format(date=cached)
    log.warning("free-nodes 自动发现失败，使用兜底日期 clash20260805.yml")
    return _FREENODES_RAW_TPL.format(date="20260805")


def get_effective_config_urls():
    """把 CONFIG_URLS 中的 _FREENODES_TOKEN 替换为运行时发现的最新 URL。

    2026-08-09: 若 CONFIG_URLS 中已无任何 _FREENODES_TOKEN（当前默认如此，
    主源已全部切到 GitLab 镜像链路），则跳过 free-nodes 的 GitHub 发现，
    避免每次"更新配置"都徒增一次被 GFW 掐断的 GitHub API 请求（10~30s 延迟）。
    """
    uses_token = any(
        primary == _FREENODES_TOKEN or fallback == _FREENODES_TOKEN
        for _, primary, fallback in CONFIG_URLS
    )
    fn = get_freenodes_latest_url() if uses_token else ""
    out = []
    for name, primary, fallback in CONFIG_URLS:
        p = fn if primary == _FREENODES_TOKEN else primary
        fb = fn if fallback == _FREENODES_TOKEN else fallback
        out.append((name, p, fb))
    return out


def download_all_configs():
    """下载所有可用线路配置：
    - 内置 4 条（CONFIG_URLS）
    - 用户自定义订阅（SubscriptionManager 中 enabled 的）
    - Batch 4: 内置全失败时降级到备选上游仓库
    返回 [(name, data_bytes, source_tag), ...] 仅包含成功的
    source_tag: "主仓库" / "备选仓库" / "自定义订阅"
    """
    results = []  # [(name, data, source_tag)]
    lock = threading.Lock()
    sub_mgr = get_subscription_manager()

    def try_download(name, primary_url, fallback_url):
        config_data = None
        for url in [primary_url, fallback_url]:
            try:
                data = download_config(url)
                # 验证可解析（防止把 HTML 错误页当作 Clash YAML）
                text = data.decode("utf-8", errors="ignore")
                _ = extract_proxies_count(text)
                config_data = data
                log.info(f"{name} 配置下载成功 ({url})")
                break
            except Exception as e:
                log.warning(f"{name} 配置下载失败 ({url}): {type(e).__name__}: {e}")
                config_data = None
                continue
        if config_data is None:
            log.error(f"{name} 配置所有下载方式均失败")
        with lock:
            results.append((name, config_data, "主仓库"))

    def try_download_subscription(sub):
        """下载并验证一个自定义订阅，下载成功后解析出节点数并更新订阅状态"""
        config_data = None
        err = ""
        node_count = 0
        try:
            data = download_subscription(sub, timeout=15)
            text = data.decode("utf-8", errors="ignore")
            node_count = extract_proxies_count(text)
            config_data = data
            log.info(f"订阅「{sub.name}」下载成功 ({sub.url}), {node_count} 个节点")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            log.warning(f"订阅「{sub.name}」下载失败: {err}")
        try:
            sub_mgr.update_status(
                sub.name,
                "下载成功" if config_data else "下载失败",
                err,
                node_count=node_count if config_data else None,
            )
        except Exception:
            pass
        with lock:
            results.append((sub.name, config_data, "自定义订阅"))

    def try_download_backup(src):
        """Batch 4: 下载备选上游仓库（按主 URL + 备用 URL 列表顺序尝试）"""
        config_data = None
        err = ""
        tried_urls = 0
        for url in get_all_backup_urls(src):
            tried_urls += 1
            try:
                data = download_config(url, timeout=15)
                text = data.decode("utf-8", errors="ignore")
                # 验证可解析
                _ = extract_proxies_count(text)
                config_data = data
                log.info(f"备选仓库「{src.name}」下载成功 ({url})")
                break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                log.warning(f"备选仓库「{src.name}」URL {tried_urls} 失败 ({url}): {err}")
                continue
        try:
            update_backup_source_status(
                src.name,
                "下载成功" if config_data else "下载失败",
                err,
            )
        except Exception:
            pass
        with lock:
            results.append((src.name, config_data, "备选仓库"))

    # === 第一轮：主仓库 + 自定义订阅 ===
    threads = []
    for name, primary_url, fallback_url in get_effective_config_urls():
        t = threading.Thread(target=try_download, args=(name, primary_url, fallback_url))
        t.start()
        threads.append(t)
    for sub in sub_mgr.get_enabled():
        t = threading.Thread(target=try_download_subscription, args=(sub,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=120)

    succeeded = [(n, d, s) for n, d, s in results if d is not None]
    failed_names = [n for n, d, s in results if d is None]
    log.info(f"下载汇总（第一轮）: 成功 {len(succeeded)} 条, 失败 {len(failed_names)} 条 {failed_names if failed_names else ''}")

    # === Batch 4 follow-up: 第二轮 —— 主仓库成功率不足时降级到备选上游 ===
    # 触发条件（更激进，避免主仓库里大部分线路节点都死掉时无备选）：
    # 1. 内置主仓库全部失败  →  必降级
    # 2. 内置主仓库成功数 < 2 条（用户视野里基本没法用）  →  必降级
    builtin_results = [(n, d, s) for n, d, s in results if s == "主仓库"]
    builtin_succeeded = [n for n, d, s in builtin_results if d is not None]
    builtin_total = len(builtin_results)
    builtin_succeeded_count = len(builtin_succeeded)
    builtin_all_failed = builtin_total > 0 and builtin_succeeded_count == 0
    builtin_too_few = builtin_total >= 2 and builtin_succeeded_count < 2
    if builtin_all_failed or builtin_too_few:
        backup_sources = [s for s in load_backup_sources() if s.enabled]
        if backup_sources:
            reason = "全部失败" if builtin_all_failed else f"成功 {builtin_succeeded_count}/{builtin_total} 不足"
            log.warning(
                f"主仓库{reason}（{builtin_succeeded}），降级到 {len(backup_sources)} 个备选上游仓库"
            )
            backup_threads = []
            for src in backup_sources:
                t = threading.Thread(target=try_download_backup, args=(src,))
                t.start()
                backup_threads.append(t)
            for t in backup_threads:
                t.join(timeout=90)  # 备选可能要走代理通道，时间放宽
            backup_succeeded = [(n, d, s) for n, d, s in results if s == "备选仓库" and d is not None]
            if backup_succeeded:
                log.info(f"备选仓库降级成功: {len(backup_succeeded)} 条")
            else:
                log.error("备选仓库也全部失败，无可用线路")
        else:
            log.warning("主仓库成功率不足，且没有启用的备选上游仓库。可在「上游管理」添加备选源。")

    # 返回成功的（含来源标记）
    final = [(n, d, s) for n, d, s in results if d is not None]
    return final


def _ensure_proxy_port(config_path, port=7890, socks_port=7891, controller="127.0.0.1:9090"):
    """保证配置文件含有监听端口与外部控制端口，且【强制覆盖】为指定值。

    为什么强制覆盖（而不是“缺失才补”）：
      并发线路检测时每条线路通过 save_config 传入独立的 mixed_port/socks_port/
      controller（如 17901/17911/18901），用以避免多实例抢同一端口。但下载源
      配置自身常带 mixed-port（通常 7890 或上游固定值），若只在“缺失时补”，
      传入的独立端口会被忽略，导致多条线路内核全部抢占同一端口、互相 bind 失败
      / 测速串线。因此这里始终用传入值替换已有的监听端口键。

    订阅源（如 free-nodes/clashfree）原始内容不含这些键时，本函数同样会补上，
    避免 mihomo 不在指定端口监听、wait_for_proxy 永远超时（“代理未就绪”）。
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 强制替换【顶层（列 0）】的 port / mixed-port / socks-port / external-controller 行。
        # 注意：只匹配列 0 的键，绝不碰节点内部缩进的 port:（否则会把代理节点的
        # 内部端口误改成 mixed-port，导致 “proxy N: '' has unset fields: port” fatal）。
        content = re.sub(r'^(mixed-port|socks-port|external-controller)\s*:.*$',
                         lambda m: (f"mixed-port: {port}" if m.group(1) == "mixed-port"
                                    else f"socks-port: {socks_port}" if m.group(1) == "socks-port"
                                    else f"external-controller: {controller}"),
                         content, flags=re.MULTILINE)
        # 顶层 port:（singular，部分旧源使用）统一改为 mixed-port
        content = re.sub(r'^port\s*:.*$', f"mixed-port: {port}", content, flags=re.MULTILINE)
        # 若经替换后仍未出现（原配置完全没有这些顶层键），则补到顶部
        if not re.search(r'^mixed-port\s*:', content, re.MULTILINE):
            content = f"mixed-port: {port}\nsocks-port: {socks_port}\n" + content
        if not re.search(r'^external-controller\s*:', content, re.MULTILINE):
            content = f"external-controller: {controller}\n" + content
        # 去重：同一端口键（mixed-port / socks-port / external-controller）可能原配置
        # 与下载源各有一份，正则已全部统一为传入值，但会留下重复顶层键，mihomo 会报
        # “mapping key already defined”。这里每个键只保留第一份。
        out_lines = []
        seen = set()
        for line in content.split("\n"):
            m = re.match(r'^(mixed-port|socks-port|external-controller)\s*:', line)
            if m:
                key = m.group(1)
                if key in seen:
                    continue
                seen.add(key)
            out_lines.append(line)
        content = "\n".join(out_lines)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)
        log.info(f"已补全监听端口配置: ['mixed-port: {port}', 'socks-port: {socks_port}', 'external-controller: {controller}']")
    except Exception as e:
        log.warning(f"补全端口配置失败: {e}")


def _restore_one_mmdb(quick_dir, fname, min_size=1_000_000):
    """从内嵌/项目副本强制还原单个只读内核数据文件（geoip.metadb / Country.mmdb）。

    被杀软隔离/损坏时，启动前还原一份完好副本，避免内核卡在加载 GEOIP/GEOSITE
    → 不绑 7890 → “dev 能跑、EXE 跑不了”。仅还原 geoip 不够：Country.mmdb 缺失
    同样会让内核卡在加载阶段，且 EXE 部署目录比 dev 目录更容易被 Defender 实时隔离。
    """
    try:
        target = os.path.join(quick_dir, fname)
        if os.path.isfile(target) and os.path.getsize(target) > min_size:
            return True
        candidates = [
            os.path.join(get_app_dir(), "Quick", fname),
            os.path.join(getattr(sys, '_MEIPASS', ''), "Quick", fname),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "Quick", fname),
        ]
        for c in candidates:
            c = os.path.abspath(c)
            if os.path.isfile(c) and os.path.getsize(c) > min_size:
                shutil.copy2(c, target)
                log.info(f"已预置 {fname} -> {target}")
                return True
        log.warning(f"未找到 {fname} 副本，GEOIP/GEOSITE 规则可能需联网下载（或失败）")
        return False
    except Exception as e:
        log.warning(f"预置 {fname} 失败: {e}")
        return False


def _ensure_mmdb(quick_dir):
    """确保 mihomo 工作目录内有 geoip.metadb 与 Country.mmdb（GEOIP/GEOSITE 规则依赖）。

    mihomo 启动默认从 -d 目录加载；缺失时它会去 github.com/MetaCubeX/meta-rules-dat
    下载，而 GitHub 在国内被墙，会直接导致内核 fatal 退出（"can't download MMDB"）
    → 代理未就绪。因此预置本地副本，并关闭 geo-auto-update，彻底规避联网下载。
    两个只读数据文件被杀软隔离后都必须每次启动前强制还原（仅还原 geoip 不够，
    Country.mmdb 缺失同样会让内核卡在加载 GEOIP → 不绑 7890 → EXE 跑不了而 dev 能跑）。
    """
    ok1 = _restore_one_mmdb(quick_dir, "geoip.metadb")
    ok2 = _restore_one_mmdb(quick_dir, "Country.mmdb")
    return ok1 and ok2


def _safe_clash_text_fixes(text):
    """对订阅配置做【纯文本、零风险】兼容修复。

    只动“明确已知会让当前 mihomo 致命/报错”的写法，绝不重排缩进、绝不改动合法结构
    （历史教训：曾用按段拉齐缩进的 _normalize_clash_indentation，反而把本身合法的
    37000 行配置打坏，制造 “did not find expected key” 假致命）。

    处理项：
      1. chacha20-poly1305 → chacha20-ietf-poly1305
         部分老订阅/合并配置用了旧名，当前 mihomo 已移除，会触发
         “unknown method: chacha20-poly1305” fatal。
      2. 删除顶层 global-client-fingerprint
         当前 mihomo 已移除该顶层键（要求改到每个 proxy 的 client-fingerprint），
         虽不致命但会刷 error 日志，删掉消除噪音。

    返回 (text, list_of_changes)。
    """
    changes = []
    OLD, NEW = "chacha20-poly1305", "chacha20-ietf-poly1305"
    if OLD in text:
        n = text.count(OLD)
        text = text.replace(OLD, NEW)
        changes.append(f"修正 {n} 处过时 cipher 名({OLD}→{NEW})")
    new = re.sub(r'(?m)^global-client-fingerprint\s*:.*\r?\n?', "", text)
    if new != text:
        changes.append("移除已废弃的 global-client-fingerprint 顶层键")
        text = new
    # 修正 geoip 键名拼写错误 datgeip → datageip
    # （拼写错会让 mihomo 忽略本地 geoip.metadb，转而去下载被墙的 GitHub MMDB 而 fatal）
    if "datgeip" in text:
        n = text.count("datgeip")
        text = text.replace("datgeip", "datageip")
        changes.append(f"修正 {n} 处 geoip 键名拼写(datgeip→datageip)")
    return text, changes


def _repair_rules_indentation(text):
    """把 rules: 段里混排(列0 / 有缩进)的列表项与注释统一拉到列0，消除 mihomo 严格
    YAML 的 "did not find expected key"。

    只作用于 rules: 块内部的列表项('- ...')与注释('# ...')行，绝不改动其它段
    （如节点的 server:/port: 等），因此不会重蹈 _normalize_clash_indentation 把
    整个文件拉齐而打坏合法配置的覆辙。幂等：列0 项保持列0 不变。
    """
    lines = text.split("\n")
    out = []
    in_rules = False
    for ln in lines:
        if re.match(r'^rules\s*:\s*$', ln):
            in_rules = True
            out.append(ln)
            continue
        if in_rules:
            if ln and ln[0] not in (" ", "\t", "-", "#"):
                # 遇到下一个顶层键（列0 非列表/非注释行）→ 退出 rules 块
                in_rules = False
                out.append(ln)
                continue
            stripped = ln.lstrip()
            if stripped == "" or stripped[0] in ("-", "#"):
                # rules 块内的空行/列表项/注释：统一列0
                out.append(stripped)
                continue
            # rules 块内其它（极少见）原样保留
            out.append(ln)
            continue
        out.append(ln)
    return "\n".join(out)


def _preprocess_config_for_quick(config_data):
    """写入 mihomo 前对订阅配置做兼容预处理。

    核心目标：强制注入本地 geoip 段（指向 ./geoip.metadb）并关闭 geo-auto-update，
    避免内核启动联网下载 MMDB 被墙导致 fatal 退出（"代理未就绪"主因）。

    策略（安全第一，绝不破坏合法配置）：
    - 优先用 PyYAML 加载 → 在对象层注入 geoip 段 → dump。对 free-nodes/ripaojiedian
      这类合法配置，结构零破坏。
    - 若 YAML 加载失败（如 mfuu 上游脏数据 / rules 段顶格等格式问题），先做缩进修复
      再尝试，仍失败则在文本顶部安全注入 geoip 段，并标记 PARSE_FAILED，
      交由 mihomo 在测试时判定该线路不可用。

    返回 (bytes, list_of_issues)。issues 末尾可能含 "PARSE_FAILED" 标记。
    """
    issues = []
    if isinstance(config_data, (bytes, bytearray)):
        text = config_data.decode("utf-8", errors="ignore")
    else:
        text = config_data

    # 纯文本安全修复：只改明确已知会让 mihomo 致命/报错的写法，
    # 绝不重排缩进（历史教训：按段拉齐缩进会把合法配置打坏）
    text, t_changes = _safe_clash_text_fixes(text)
    if t_changes:
        issues.extend(t_changes)
    # rules: 段内混合缩进(numbered list 项与 YUNJI 注释列0/有缩进混排)是 mihomo
    # 严格 YAML 的致命源，且恰好会让下方 safe_load 失败。此处精准修复 rules 段缩进
    # （只动 rules 块内列表项/注释，列0 对齐），既不会打坏其它段，也能让下方
    # safe_load 从“加载失败”转为“成功重排”。
    text = _repair_rules_indentation(text)

    geoip_obj = {
        "geo-auto-update": False,
        "geoip": {
            "datageip": "./geoip.metadb",
            "download-url": "",
            "auto-update": False,
        },
    }

    # 尝试 PyYAML 安全路径（dev 运行环境自带 PyYAML）
    try:
        import yaml as _yaml
        doc = _yaml.safe_load(text)
        if isinstance(doc, dict):
            doc.pop("geosite", None)
            doc.pop("geo-auto-update", None)
            doc.update(geoip_obj)
            out = _yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
            issues.append("YAML 重排并注入本地 geoip 段")
            return out.encode("utf-8"), issues
    except Exception as e:
        issues.append(f"YAML 加载失败（脏数据）: {type(e).__name__}")

    # 兜底：文本顶部安全注入 geoip 段（不触碰下方正文，避免破坏结构）
    try:
        NL = chr(10)
        geoip_block = (
            "geo-auto-update: false" + NL
            + "geoip:" + NL
            + "  datageip: ./geoip.metadb" + NL
            + "  download-url: ''" + NL
            + "  auto-update: false" + NL
            + NL
        )
        def _strip_top(content, key):
            p = re.compile(r'^' + re.escape(key) + r'\s*:.*$(' + NL + r'(?:[ \t]+[^\n]*\n?)*)?', re.MULTILINE)
            return p.sub("", content)
        text = _strip_top(text, "geoip")
        text = _strip_top(text, "geosite")
        text = re.sub(r'^geo-auto-update\s*:.*$', "", text, flags=re.MULTILINE)
        out = geoip_block + text
        issues.append("PARSE_FAILED: 已文本注入 geoip 段，线路可能在测试时因解析失败不可用")
        return out.encode("utf-8"), issues
    except Exception as e:
        issues.append(f"预处理异常（已原样写入）: {e}")
        return text.encode("utf-8"), issues


def _inject_yunji_blocks(content, blocks):
    """把 YUNJI 规则块按本配置 rules: 段的实际缩进对齐后注入。

    背景：_preprocess_config_for_quick 用 PyYAML safe_dump 重排，列表项默认顶格
    （rules: 下的 - 在列 0）；而 YUNJI 块从历史配置抽取时带 2 空格缩进。两者混排
    会让 mihomo 报 “did not find expected key” 致命（切换小体积订阅时必现）。
    这里统一到 rules: 段首个列表项的缩进，保证序列内缩进一致。
    """
    lines = content.split("\n")
    base_indent = 0
    for i, l in enumerate(lines):
        if re.match(r'^rules:\s*$', l):
            for j in range(i + 1, min(i + 30, len(lines))):
                s = lines[j]
                if s.strip() == "" or s.strip().startswith("#"):
                    continue
                m = re.match(r'^(\s*)-\s', s)
                if m:
                    base_indent = len(m.group(1))
                break
            break
    norm = []
    for b in blocks:
        for bl in b.split("\n"):
            if bl.strip() == "":
                norm.append("")
            else:
                norm.append((" " * base_indent) + bl.lstrip(" "))
        norm.append("")
    rp = re.compile(r'^(rules:\s*)$', re.MULTILINE)
    return rp.sub(r'\1\n' + "\n".join(norm), content)


def _filter_advanced_sections(advanced_text, present_keys):
    """从 advanced_text 中只保留【新配置尚未包含】的顶层段（tun/dns/sniffing 等）。

    避免把旧配置的 dns/sniffing 重新拼到顶部，与下载源自带段形成重复顶层键
    （会被 _dedup_top_level_keys 删除，导致丢配置）。已存在的段直接丢弃。
    """
    lines = advanced_text.split("\n")
    sections = []
    cur_key = None
    cur = []
    for l in lines:
        m = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*)\s*:', l)
        if m and l[:1] not in (" ", "\t"):
            if cur_key is not None:
                sections.append((cur_key, cur))
            cur_key = m.group(1)
            cur = [l]
        elif cur_key is not None:
            cur.append(l)
    if cur_key is not None:
        sections.append((cur_key, cur))
    kept = []
    for key, sec in sections:
        if key not in present_keys:
            kept.extend(sec)
            kept.append("")
    return "\n".join(kept).strip("\n")


def _localize_external_providers(quick_dir, text):
    """将订阅配置里的外部 proxy-providers / rule-providers（type: http + url:）
    下载到本地 Quick/providers/ 并改写为 type: file + path:，使 mihomo 启动期
    不再阻塞下载被墙/慢的外链。

    背景（EXE 部署目录内核卡在 "Start initial compatible provider" 的根因）：
    EXE 全新释放的目录没有 provider 缓存，mihomo 启动会联网下载订阅里指向
    github 等的外链 provider，国内网络下常卡死、永远到不了
    "Initial configuration complete" → 7890 不绑 → 界面"未启动"。
    dev 因运行环境能下成功而表现正常，造成"dev 通 EXE 不通"的假象。
    本函数复用应用自带的多级回退下载器（download_config）提前把 provider
    拽到本地，从根上消除内核启动期的外链下载。

    文本级改写，保留整体结构与后续 YUNJI 注入所需的标记；下载失败则保留
    原样（降级，不阻断启动流程）。返回 str（调用方负责重新编码为 bytes）。
    """
    import re as _re
    if isinstance(text, (bytes, bytearray)):
        try:
            text = text.decode("utf-8", errors="ignore")
        except Exception:
            return text
    providers_dir = os.path.join(quick_dir, "providers")
    # 逐条匹配 provider 条目（必须有缩进，即 proxy-providers/rule-providers 的子项；
    # 排除顶层段头 proxy-providers: 本身，否则会把整段误当成一个 provider）
    entry_re = _re.compile(r'^([ \t]+)([\w\-]+):[ \t]*\n((?:[ \t]+[^\n]*\n)*)', _re.MULTILINE)

    def repl(m):
        indent = m.group(1)
        name = m.group(2)
        body = m.group(3)
        if 'type: http' not in body:
            return m.group(0)
        um = _re.search(r'^[ \t]*url:[ \t]*(\S+)\s*$', body, _re.MULTILINE)
        if not um:
            return m.group(0)
        url = um.group(1)
        # 已是本地文件则跳过
        if url.startswith(('file://', '/', './', '../')):
            return m.group(0)
        local_name = _re.sub(r'[^A-Za-z0-9_.-]', '_', name)
        rel = "providers/" + local_name + ".yaml"
        local_abs = os.path.join(quick_dir, rel)
        # 已本地化过则直接复用，避免每次 save_config 重复下载
        if os.path.isfile(local_abs) and os.path.getsize(local_abs) > 0:
            new_body = _rewrite_body(body, rel)
            log.info(f"复用已本地化 provider {name} -> {rel}")
            return indent + name + ":\n" + new_body
        try:
            os.makedirs(providers_dir, exist_ok=True)
            content = download_config(url, timeout=30)
            if not content:
                log.warning(f"本地化 provider 失败（下载为空，保留外链）{name}: {url}")
                return m.group(0)
            data = content if isinstance(content, (bytes, bytearray)) else content.encode("utf-8")
            with open(local_abs, "wb") as f:
                f.write(data)
            new_body = _rewrite_body(body, rel)
            log.info(f"已本地化外部 provider {name} -> {rel}")
            return indent + name + ":\n" + new_body
        except Exception as e:
            log.warning(f"本地化 provider 失败（保留外链）{name}: {e}")
            return m.group(0)

    def _rewrite_body(body, rel):
        """逐行缩进感知重写：type: http->file, url->path, 删 interval,
        删 health-check 及其更深的子块；保留 behavior: 等其它字段。"""
        out = []
        skip_depth = None
        for ln in body.split("\n"):
            st = ln.lstrip()
            cur_ind = len(ln) - len(st)
            if skip_depth is not None:
                if cur_ind > skip_depth:
                    continue
                skip_depth = None
            if ln == "":
                out.append(ln)
                continue
            if st.startswith("type:") and "http" in st:
                prefix = ln[:cur_ind]
                out.append(prefix + "type: file")
                continue
            if st.startswith("url:"):
                prefix = ln[:cur_ind]
                out.append(prefix + "path: " + rel)
                continue
            if st.startswith("interval:"):
                continue
            if st.startswith("health-check:"):
                skip_depth = cur_ind
                continue
            out.append(ln)
        result = "\n".join(out)
        if not result.endswith("\n"):
            result += "\n"
        return result

    try:
        return entry_re.sub(repl, text)
    except Exception as e:
        log.warning(f"本地化外部 provider 异常（原样）: {e}")
        return text


def save_config(quick_dir, config_data, mixed_port=None, socks_port=None, controller=None,
                yunji_src=None, inject_advanced=True):
    """写入配置。

    yunji_src: 指定从哪个配置提取 YUNJI 规则块（并行线路检测用它从【主配置】提取，
        保证每条测试线都带上与主代理一致的 GEOIP,CN,DIRECT 等路由规则；为 None 时
        从目标目录既有 config.yaml 提取——串行/主代理路径）。
    inject_advanced: 是否补充高级段(tun/dns/sniffing)。并行测试实例为临时 ephemeral 进程，
        不需要也不应启用 TUN（需管理员权限/虚拟网卡，可能初始化失败），故默认关闭。
    """
    config_path = os.path.join(quick_dir, "config.yaml")
    backup_path = os.path.join(quick_dir, "config.yaml_backup")
    # 先读取已有的 YUNJI 注入规则和高级配置段
    yunji_blocks = []
    advanced_text = ""  # 高级配置（tun / dns / sniffing / global-client-fingerprint）
    old_content = ""  # 提取源原文；src_path 为空时保持空串，避免下方引用未定义
    # 提取源：优先用 yunji_src（主配置），否则用目标目录既有 config.yaml
    src_path = yunji_src if (yunji_src and os.path.isfile(yunji_src)) else \
        (config_path if os.path.isfile(config_path) else None)
    if src_path:
        # 仅当提取源就是目标自身时才做备份（避免并行时把主配置内容备份到测试子目录）
        if src_path == config_path and os.path.isfile(backup_path):
            os.remove(backup_path)
            shutil.copy2(config_path, backup_path)
        # 提取所有 YUNJI 标记块 和 高级配置段
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                old_content = f.read()
            markers = [
                ("YUNJI_CUSTOM_RULES_START", "YUNJI_CUSTOM_RULES_END"),
                ("YUNJI_PROXY_MODE_START", "YUNJI_PROXY_MODE_END"),
                ("YUNJI_FINAL_RULE_START", "YUNJI_FINAL_RULE_END"),
            ]
            for start_m, end_m in markers:
                lines = old_content.split("\n")
                block = []
                in_block = False
                for line in lines:
                    if start_m in line:
                        in_block = True
                    if in_block:
                        block.append(line)
                    if end_m in line:
                        in_block = False
                        break
                if block:
                    yunji_blocks.append((start_m, "\n".join(block)))
            # 提取顶层高级配置段（tun / dns / sniffing）
            # 关键：切线/换线后必须保留 TUN 段，否则 mihomo 不会接管流量，DOMAIN 规则失效
            for section in ["tun", "dns", "sniffing"]:
                # 匹配顶层 section 标题 + 任意缩进（2/4/6 空格）的子项
                pattern = re.compile(
                    r'^' + re.escape(section) + r'\s*:\s*\n((?:[ \t]+[^\n]*\n)*)',
                    re.MULTILINE
                )
                m = pattern.search(old_content)
                if m:
                    advanced_text += m.group(0) + ("\n" if not m.group(0).endswith("\n") else "")
            # global-client-fingerprint（单行）
            fp_match = re.search(r'^global-client-fingerprint\s*:.*\n', old_content, re.MULTILINE)
            if fp_match:
                advanced_text += fp_match.group(0)
        except Exception:
            pass
    # 健壮性：无论主配置是否存在 / 是否带 YUNJI 标记，并行线路检测都必须保证
    # 境内直连规则 GEOIP,CN,DIRECT 存在。否则当主配置缺失（首次运行/损坏）或无标记
    # （旧版配置）时，yunji_blocks 为空 → baidu 等境内站点被迫走失效节点隧道 →
    # 全部测速 URL 失败 → 整页“超时”。这是 2026-08-10 并行检测“全部超时”的根因之一。
    if not any("GEOIP,CN,DIRECT" in b for _, b in yunji_blocks):
        yunji_blocks.append(("YUNJI_PROXY_MODE_START",
                             "# YUNJI_PROXY_MODE_START\n- GEOIP,CN,DIRECT\n# YUNJI_PROXY_MODE_END"))
        log.info("已强制补注入境内直连规则 GEOIP,CN,DIRECT（主配置无标记或缺失）")
    # Batch 2: 国家白名单过滤（在写入前生效）
    try:
        wl = load_country_whitelist()
    except Exception:
        wl = []
    if wl:
        try:
            text = config_data.decode("utf-8", errors="ignore") if isinstance(config_data, (bytes, bytearray)) else config_data
            filtered_text = filter_proxies_by_country(text, wl)
            if filtered_text != text:
                removed_n = text.count("- name:") - filtered_text.count("- name:")
                # yaml 序列化后用 # 开头注释会破坏结构，所以重新计数
                try:
                    before = parse_clash_yaml(text).get("proxies", [])
                    after = parse_clash_yaml(filtered_text).get("proxies", [])
                    removed_n = max(0, len(before) - len(after))
                except Exception:
                    pass
                log.info(f"国家筛选生效: 保留 {sorted(set(c.upper() for c in wl))}, 过滤 {removed_n} 个节点")
                config_data = filtered_text.encode("utf-8")
        except Exception as e:
            log.warning(f"国家筛选失败（已跳过）: {e}")
    # 预置 geoip.metadb 并预处理配置（注入本地 MMDB 段、容错补 name 引号）
    _ensure_mmdb(quick_dir)
    try:
        config_data, p_issues = _preprocess_config_for_quick(config_data)
        for it in p_issues:
            log.info(f"配置预处理: {it}")
    except Exception as e:
        log.warning(f"配置预处理失败（原样写入）: {e}")
    # 本地化外部 provider（消除内核启动期外链下载卡死；EXE 部署根因修复）
    try:
        config_data = _localize_external_providers(quick_dir, config_data)
        if isinstance(config_data, str):
            config_data = config_data.encode("utf-8")
    except Exception as e:
        log.warning(f"本地化外部 provider 跳过: {e}")
    # 写入新配置
    with open(config_path, 'wb') as f:
        f.write(config_data)
    # 恢复 YUNJI 注入规则 + 高级配置
    if yunji_blocks or advanced_text:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 恢复被注释的原始 MATCH 规则标记
            if "YUNJI_ORIGINAL_MATCH_DISABLED" in old_content:
                content = content.replace(
                    "- MATCH,", "# YUNJI_ORIGINAL_MATCH_DISABLED   - MATCH,"
                ) if "- MATCH," in content and "YUNJI_FINAL_RULE" not in content else content
            rules_pattern = re.compile(r'^(rules:\s*)$', re.MULTILINE)
            if rules_pattern.search(content) and yunji_blocks:
                # 关键修复：YUNJI 规则块按本配置 rules: 段实际缩进对齐，
                # 否则 2 空格(YUNJI) 与 0 空格(safe_dump 输出) 混排会让 mihomo
                # 报 “did not find expected key” 致命（切换小体积订阅时必现）。
                content = _inject_yunji_blocks(content, [b for _, b in yunji_blocks])
            # 高级配置：仅补充【新配置缺失】的段（如 tun），避免与下载源自带
            # 的 dns/sniffing 重复而产生顶层键冲突（重复键被 dedup 删除会丢配置）。
            # inject_advanced=False 时（并行测试实例）跳过，避免临时进程启用 TUN。
            if advanced_text and inject_advanced:
                new_keys = set(re.findall(r'^([a-zA-Z][a-zA-Z0-9_-]*)\s*:', content, re.MULTILINE))
                adv_to_add = _filter_advanced_sections(advanced_text, new_keys)
                if adv_to_add:
                    content = adv_to_add + "\n" + content
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
            log.info(f"已保留 {len(yunji_blocks)} 个 YUNJI 规则块" +
                      (" + 高级配置" if (advanced_text and inject_advanced) else "（跳过高级段）"))
        except Exception as e:
            log.warning(f"恢复 YUNJI 规则块和高级配置失败: {e}")
    # 兜底：确保监听端口存在（线路检测用单条订阅覆盖时尤其容易丢失）
    # mixed_port 等可选参数用于并发检测：让每条线路监听独立端口，互不冲突。
    _ensure_proxy_port(
        config_path,
        port=(mixed_port if mixed_port is not None else 7890),
        socks_port=(socks_port if socks_port is not None else 7891),
        controller=(controller if controller is not None else "127.0.0.1:9090"),
    )
    log.info(f"配置已保存到 {config_path}")


def _dedup_top_level_keys(config_path):
    """去除 config.yaml 中重复的顶层键，避免 mihomo 解析失败崩溃

    远程订阅源（如 mfuu/v2ray）可能自带重复的 dns / global-client-fingerprint 等顶层键，
    mihomo 解析时会报 "mapping key already defined" 错误并立即退出，
    导致 wait_for_proxy 轮询 15 秒超时——这是"启动很慢"的隐藏根因。
    本函数保留每个顶层键的第一次出现，删除后续重复定义及其子项。
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # 找出所有顶层键及其行号（行首非空格，匹配 key: 或 key: value）
        top_level_keys = {}  # key -> list of line indices
        for i, line in enumerate(lines):
            m = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*)\s*:', line)
            if m:
                key = m.group(1)
                top_level_keys.setdefault(key, []).append(i)

        # 找出重复的键
        dupes = {k: v for k, v in top_level_keys.items() if len(v) > 1}
        if not dupes:
            return True  # 无重复

        # 标记需要删除的行（保留第一个，删除后续重复定义及其子项）
        lines_to_delete = set()
        for key, line_indices in dupes.items():
            for start_idx in line_indices[1:]:
                lines_to_delete.add(start_idx)
                for j in range(start_idx + 1, len(lines)):
                    # 子项是缩进行的行（以空格/tab 开头且非空）
                    if lines[j].startswith((' ', '\t')) and lines[j].strip():
                        lines_to_delete.add(j)
                    else:
                        break

        new_lines = [line for i, line in enumerate(lines) if i not in lines_to_delete]
        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        log.info(f"已去除重复的顶层键: {list(dupes.keys())}")
        return True
    except Exception as e:
        log.warning(f"清理重复顶层键失败: {e}")
        return False


def _launch_quick(quick_dir, _heal=True):
    """拉起一个 mihomo(quick.exe) 实例（不等待端口就绪，仅做 6s 启动期 fatal 探测）。

    返回 subprocess.Popen 对象；若 exe/config 缺失或启动 6s 内 fatal 退出，返回 None
    （调用方据此判定该实例不可用）。并发线路检测会为每个线路启动独立实例并保留 proc
    句柄，以便结束时精确终止，避免误杀其它实例（如用户正在使用的主代理 7890）。

    _heal: 内核因配置解析 fatal 退出时，自动用 PyYAML 安全重排兜底并重试一次
    （仅一次，避免无限递归）。即使启动前文本修复把合法配置意外打坏，也能自愈启动。
    """
    quick_exe = os.path.join(quick_dir, "quick.exe")
    if not os.path.isfile(quick_exe):
        log.error(f"quick.exe 不存在: {quick_exe}")
        return None
    # 启动前对 quick.exe 本体做完整性自检（杀软可能在启动后再次隔离它）。
    # 体积异常偏小（< 内嵌源的 90%）立即从 _MEIPASS 重新还原一次，避免拉起损坏副本
    # 导致“内核未启动”。
    try:
        _src_exe = os.path.join(getattr(sys, '_MEIPASS', ''), "Quick", "quick.exe")
        if os.path.isfile(_src_exe):
            _dst_sz = os.path.getsize(quick_exe)
            _src_sz = os.path.getsize(_src_exe)
            if _src_sz > 0 and _dst_sz < _src_sz * 0.9:
                log.warning(f"quick.exe 体积异常偏小({_dst_sz}B < 源 {_src_sz}B，疑似被杀软隔离)，"
                            f"启动前重新还原")
                shutil.copy2(_src_exe, quick_exe)
    except Exception as _qe:
        log.warning(f"quick.exe 完整性自检/还原失败(继续尝试): {_qe}")
    config_path = os.path.join(quick_dir, "config.yaml")
    if not os.path.isfile(config_path):
        log.error(f"config.yaml 不存在: {config_path}")
        return None
    # 启动前清理重复的顶层键，避免 mihomo 解析失败崩溃
    _dedup_top_level_keys(config_path)
    # 启动前对配置做一次【确定性自愈】（纯文本安全修复 + rules 段缩进修复）。
    # 改动零风险、幂等；但为防“修复反而打坏合法配置”（罕见的交互性错误，会触发
    # mihomo "did not find expected key" 致命），修复后做 YAML 合法性校验，若仍非法
    # 则退回 PyYAML 安全重排（产出标准合法 YAML，mihomo 必能解析；代价是丢失注释标记，
    # 但 rules 内实际路由规则保留）。
    try:
        with open(config_path, "rb") as _f:
            _raw = _f.read()
        _text = _raw.decode("utf-8", errors="ignore")
        _fixed, _chg = _safe_clash_text_fixes(_text)
        _fixed = _repair_rules_indentation(_fixed)
        try:
            import yaml as _yaml
            _yaml.safe_load(_fixed)
        except Exception:
            _fb, _fb_chg = _preprocess_config_for_quick(_text)
            _fixed = _fb.decode("utf-8") if isinstance(_fb, (bytes, bytearray)) else _fb
            _chg = (_chg or []) + _fb_chg
            log.warning("启动前修复后配置仍非法，已用 PyYAML 安全重排兜底自愈")
        if _chg or _fixed != _text:
            with open(config_path, "w", encoding="utf-8") as _f:
                _f.write(_fixed)
            if _chg:
                log.info(f"启动前安全修复 config.yaml: {_chg}")
            else:
                log.info("启动前自愈 config.yaml: 已修复 rules 段缩进")
    except Exception as _e:
        log.warning(f"启动前修复 config.yaml 失败（沿用原文件）: {_e}")
    # 启动前确保 geoip.metadb 就位（GEOIP,CN,DIRECT 规则依赖）。
    # 这是【主代理 + 线路检测】共用的唯一内核启动入口；此前仅主代理路径(_do_start)
    # 调过 _ensure_mmdb，线路检测走 start_quick→_launch_quick 漏掉了它。EXE 运行时若
    # geoip.metadb 被杀软隔离/损坏，内核会卡在加载 GEOIP → 不绑 7890 → 线路全超时。
    # 在此兜底，使每一次内核拉起都从内嵌 _MEIPASS 还原一份完好 geoip，彻底消除
    # “dev 能跑、EXE 跑不了”的运行时差异（dev 的 geoip 永不被部署逻辑触碰）。
    try:
        _ensure_mmdb(quick_dir)
    except Exception as _ge:
        log.warning(f"启动前预置 geoip.metadb 失败(继续尝试启动): {_ge}")
    log.info(f"配置文件大小: {os.path.getsize(config_path)} bytes")
    # 内核输出落盘到 quick_out.log（行缓冲），便于“代理未就绪”时回看 mihomo 真实报错。
    # 旧逻辑用 PIPE 且仅在 6s 内读取，内核稍晚崩溃/卡死即丢失输出 → 诊断盲区。
    # Windows 下 subprocess 会 DuplicateHandle 给子进程，父进程句柄被回收不影响子进程写入。
    _out_log = os.path.join(quick_dir, "quick_out.log")
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    try:
        proc = subprocess.Popen(
            [quick_exe, "-d", quick_dir],
            cwd=quick_dir,
            stdout=open(_out_log, "w", encoding="utf-8", errors="ignore", buffering=1),
            stderr=subprocess.STDOUT,
            startupinfo=si,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception as e:
        log.error(f"启动 quick.exe 异常: {e}")
        return None
    # 轮询 6s：若进程已退出且非 0，则为 fatal（配置解析失败/MMDB 缺失等）。
    # 通过读取 quick_out.log 尾部判定（与 _is_config_yaml_valid 同思路），
    # 这样即使内核在 6s 之后才崩溃，输出也已落盘，wait_for_proxy 失败时可回看。
    for _ in range(12):
        time.sleep(0.5)
        if proc.poll() is not None:
            rc = proc.returncode
            _txt = ""
            try:
                with open(_out_log, "r", encoding="utf-8", errors="ignore") as _lf:
                    _txt = _lf.read()
            except Exception:
                pass
            tail = _txt[-600:]
            # 端口被占用：mihomo 绑 7890/9090 失败（level=error 而非 fatal）。
            # 常见于残留的 quick.exe 未退出、或其它代理软件(Clash/v2rayN)占用了端口。
            if ("address already in use" in _txt) or ("Only one usage" in _txt) or \
               ("bind:" in _txt and ("已被占用" in _txt or "in use" in _txt)):
                log.error("启动失败：端口 7890/9090 被其它进程占用（可能是残留的 quick.exe 或未关闭的其它代理软件）。"
                          "请先结束占用端口的进程后重试：任务管理器结束 quick.exe / mihomo*.exe，"
                          "或命令行 netstat -ano | findstr :7890 查 PID 后 taskkill /f /pid <PID>")
                return None
            if rc != 0 or "level=fatal" in tail:
                # 自愈：配置解析失败，用 PyYAML 安全重排兜底后重启一次（仅一次）
                if _heal:
                    try:
                        with open(config_path, "rb") as _f:
                            _raw2 = _f.read()
                        _t2 = _raw2.decode("utf-8", errors="ignore")
                        _fb2, _fb_chg2 = _preprocess_config_for_quick(_t2)
                        _fixed2 = _fb2.decode("utf-8") if isinstance(_fb2, (bytes, bytearray)) else _fb2
                        with open(config_path, "w", encoding="utf-8") as _f:
                            _f.write(_fixed2)
                        log.warning(f"内核解析失败，已安全重排配置并自愈重试: {_fb_chg2}")
                        _diagnose(f"内核解析失败，已安全重排并自愈重试（改动: {_fb_chg2}）")
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        return _launch_quick(quick_dir, _heal=False)
                    except Exception as _he:
                        log.warning(f"自愈重试失败: {_he}")
                log.error(f"quick.exe 启动即致命退出(rc={rc}): {tail}")
                _diagnose(f"内核启动致命退出 rc={rc} 关键输出: {tail}")
                return None
            break
    return proc


def _is_config_yaml_valid(quick_dir):
    """判断运行目录的 config.yaml 是否能被 mihomo 内核正常解析。

    必须用【真实内核】(quick.exe -d) 校验，不能用 PyYAML 近似：mihomo 是严格
    YAML 解析器，对 rules 段 0/2 空格混排等会报 "did not find expected key" 致命，
    而 PyYAML 对此类缩进较宽松会漏判（解析成功）。用户日志的 line 358 正是这类
    mihomo 专属错误，PyYAML 校验会误判为合法 → 漏掉重下载 → 内核持续 fatal。

    实现：以 -d 拉起内核做解析探测，把输出重定向到临时日志轮询：
      - 出现 "Initial configuration complete" → 合法（随后杀掉探测进程）
      - 出现 "did not find expected key" / "level=fatal" → 损坏
      - 端口被占用导致绑不上 → 既无完成行也无致命行 → 保守判为无效（触发重建/重启）
    任何异常均保守返回 False（宁可重下载，不能拿坏配置启动）。
    """
    config_path = os.path.join(quick_dir, "config.yaml")
    if not os.path.isfile(config_path):
        return False
    quick_exe = os.path.join(quick_dir, "quick.exe")
    if not os.path.isfile(quick_exe):
        # 无内核可用时退回 PyYAML 启发式（仅兜底，可能漏判 mihomo 专属错误）
        try:
            import yaml as _yaml
            with open(config_path, "rb") as _f:
                _text = _f.read().decode("utf-8", errors="ignore")
            _fixed, _ = _safe_clash_text_fixes(_text)
            _fixed = _repair_rules_indentation(_fixed)
            _yaml.safe_load(_fixed)
            return True
        except Exception:
            return False
    import tempfile
    _logf = os.path.join(tempfile.gettempdir(), f"_yunji_cfgchk_{os.getpid()}.log")
    proc = None
    try:
        with open(_logf, "w", encoding="utf-8", errors="ignore") as _lf:
            proc = subprocess.Popen(
                [quick_exe, "-d", quick_dir], cwd=quick_dir,
                stdout=_lf, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        _valid = False
        for _ in range(20):  # 最多 10s
            time.sleep(0.5)
            try:
                with open(_logf, "r", encoding="utf-8", errors="ignore") as _lf2:
                    _txt = _lf2.read()
            except Exception:
                _txt = ""
            if "did not find expected key" in _txt or "level=fatal" in _txt:
                _valid = False
                break
            if "Initial configuration complete" in _txt:
                _valid = True
                break
            if proc.poll() is not None:
                # 进程已退出但未命中完成/致命关键字（如端口被占），保守判无效
                _valid = False
                break
        return _valid
    except Exception:
        return False
    finally:
        try:
            if proc is not None and proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        try:
            os.remove(_logf)
        except Exception:
            pass


def _port_owner_info(port=7890):
    """返回 (pid, name) 占用指定端口的进程；无人占用返回 (None, '')。

    用于“代理未就绪”时定位真凶：开发机能跑、打包 EXE 跑不了，最常见原因是
    部署机上有 Clash / v2rayN / 其它代理软件占着 7890，而开发机没有。
    本函数直接查 netstat + tasklist，把占用者 PID 与进程名暴露给用户，
    比笼统的“代理未就绪”更有行动指引。
    """
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=12,
        ).stdout
        for line in out.splitlines():
            cols = line.split()
            if len(cols) >= 5 and f":{port}" in cols[1] and cols[3] == "LISTENING":
                pid = cols[4]
                name = ""
                try:
                    tl = subprocess.run(
                        ["tasklist", "/fi", f"PID eq {pid}"],
                        capture_output=True, text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW, timeout=12,
                    ).stdout
                    for l in tl.splitlines()[3:]:
                        if pid in l:
                            name = l.split()[0]
                            break
                except Exception:
                    pass
                return pid, name
    except Exception:
        pass
    return None, ""


def _read_kernel_log(quick_dir, n=3000):
    """读取内核上次运行的输出（quick_out.log），用于"代理未就绪"时定位真凶。

    内核由 _launch_quick 以行缓冲落盘到此文件：卡死（如联网下载被墙的 GEOIP/MMDB）、
    配置致命解析、端口冲突等真实报错都在里面。wait_for_proxy 超时但端口未被他人占用时，
    读取它能把模糊的"代理未就绪"变成可定位的具体原因。

    2026-08-17: 截取量从 1000 增到 3000。此前 1000 字符正好被 10 行
    'Start initial compatible provider'（端口绑定后的正常日志）占满，把前面的
    'Initial configuration complete' / 'listening at' / bind error 截掉了，
    导致误判"卡在 provider 初始化"。同时提取关键行单独标注，一眼看出根因。
    """
    try:
        p = os.path.join(quick_dir, "quick_out.log")
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8", errors="ignore") as _f:
                full = _f.read()
            # 提取关键诊断行（不论在文件何处），避免被尾部截取漏掉
            key_lines = []
            for kw in ["Initial configuration complete", "listening at",
                       "address already in use", "Only one usage", "bind:",
                       "level=fatal", "level=error", "can't download",
                       "Geodata Loader", "Start initial configuration"]:
                for line in full.split("\n"):
                    if kw in line and line not in key_lines:
                        key_lines.append(line)
            tail = full[-n:]
            if key_lines:
                return "[关键诊断行] " + " | ".join(key_lines) + "\n\n[尾部日志] " + tail
            return tail
    except Exception:
        pass
    return ""


def _select_first_valid_config(downloaded, preferred, quick_dir):
    """从下载结果中挑选第一个能被真实内核解析的合法配置。

    背景：某些订阅源（自定义订阅 / 备选上游 / 活订阅轮换）可能产出 mihomo 专属
    错误的坏 YAML（如 rules 段特殊缩进），PyYAML 漏判，必须用真实内核校验。
    旧逻辑只认 current_line（或 downloaded[0]），一旦它指向坏配置，就会反复
    下载同一份坏配置 → 内核持续 fatal → “代理未就绪”死循环。

    本函数：
      - 优先保留用户选定的线路（preferred），其余按下载顺序兜底；
      - 每条配置在独立临时目录用【真实内核】校验（绑定空闲端口，避免与 7890
        冲突造成误判），第一个合法的即返回；
      - 全部损坏返回 None（调用方给出清晰报错，而不是死循环）。
    """
    if not downloaded:
        return None
    order = []
    if preferred:
        for it in downloaded:
            if it[0] == preferred:
                order.append(it)
                break
    order += [it for it in downloaded if it not in order]
    valid = []
    for name, data, _src in order:
        sub = tempfile.mkdtemp(prefix="_cfgv_")
        try:
            for f in ("quick.exe", "geoip.metadb", "Country.mmdb"):
                s = os.path.join(quick_dir, f)
                if os.path.isfile(s):
                    try:
                        os.link(s, os.path.join(sub, f))
                    except Exception:
                        shutil.copy2(s, os.path.join(sub, f))
            cfg = os.path.join(sub, "config.yaml")
            with open(cfg, "wb") as fh:
                fh.write(data)
            # 用空闲端口探测，隔离 7890 占用造成的误判
            fp = _pick_free_port(18000)
            _ensure_proxy_port(sub, port=fp, socks_port=fp + 1,
                               controller=f"127.0.0.1:{fp + 2}")
            if _is_config_yaml_valid(sub):
                valid.append((name, data))
                if name == preferred or not preferred:
                    return (name, data)
        except Exception:
            pass
        finally:
            try:
                shutil.rmtree(sub)
            except Exception:
                pass
    return valid[0] if valid else None


def start_quick(quick_dir):
    """启动 mihomo(quick.exe)（单实例便捷封装）。

    返回 (ok, reason)：
      - ok=True  已成功拉起且未立即致命退出（端口是否就绪由调用方 wait_for_proxy 判定）
      - ok=False 启动文件缺失，或进程在 6s 内 fatal 退出（配置解析/MMDB 等错误），
        reason 含可读错误，便于线路检测区分“配置坏”与“代理未就绪”。
    """
    proc = _launch_quick(quick_dir)
    if proc is None:
        return False, "内核解析/启动失败或文件缺失"
    log.info(f"已启动代理内核: {os.path.join(quick_dir, 'quick.exe')}")
    return True, ""


def start_quick_proc(quick_dir):
    """并发检测专用：拉起一个内核实例并返回其 Popen 句柄（或 None）。

    与 start_quick 的区别：返回进程对象而非 (ok,reason)，便于调用方在检测结束后
    精确终止该实例（stop_quick_proc），而不会像 stop_quick() 那样 taskkill 掉全部
    quick.exe（会误杀用户正在使用的主代理）。
    """
    return _launch_quick(quick_dir)


def stop_quick_proc(proc):
    """精确终止一个内核实例（仅该进程），不影响其它 quick.exe 实例（如主代理）。"""
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    except Exception:
        pass
    # 兜底：若 proc.kill 未生效（子进程已脱离），按 pid 强杀
    try:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/f", "/pid", str(proc.pid)],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass


def is_port_listening(port, host="127.0.0.1"):
    """检测指定本地端口是否处于监听状态（并发检测用，不再只认 7890）。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def wait_for_proxy_port(port, timeout=8):
    """等待指定端口就绪（并发检测每条线路用各自端口，避免受全局 7890 限制）。"""
    start = time.time()
    while time.time() - start < timeout:
        if is_port_listening(port):
            return True
        time.sleep(0.3)
    return False


def _pick_free_port(base, host="127.0.0.1", span=50):
    """从 base 起找一个未被占用的本地端口（避免并发实例端口撞车）。"""
    p = base
    while p < base + span:
        if not is_port_listening(p, host):
            return p
        p += 1
    return base


def _pick_free_port_triple(base, host="127.0.0.1", span=200):
    """找一个从 base 起、连续 3 个端口(port/port+1/port+2)都空闲的起始端口。

    并发线路检测每条线路用独立 mixed/socks/controller 端口，避免实例间抢端口。
    """
    p = base
    while p < base + span:
        if (not is_port_listening(p, host) and not is_port_listening(p + 1, host)
                and not is_port_listening(p + 2, host)):
            return p
        p += 1
    return base


def _measure_line_through_port(name, port, timeout=NODE_TEST_TIMEOUT):
    """经指定本地端口的代理，实测各 URL 延迟（真正的“竞速”度量）。

    返回 (best_abroad, usable, avg_all, count)：
      - best_abroad: 境外经代理成功的最小延迟(秒)，无则 -1
      - usable: 至少有一个境外站点经代理成功（线路真正能翻墙的硬条件）
      - avg_all: 所有成功 URL 的平均延迟
      - count: 成功 URL 数
    端口未监听(内核崩溃/未起) → 直接判不可用。
    """
    if not wait_for_proxy_port(port, timeout=10):
        return (-1.0, False, -1.0, 0)
    latencies = []
    abroad_ok = False
    abroad_latencies = []
    for label, test_url, region in NODE_TEST_URLS:
        for attempt in range(2):
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    'http': f'http://127.0.0.1:{port}',
                    'https': f'http://127.0.0.1:{port}',
                })
                opener = urllib.request.build_opener(proxy_handler)
                req = urllib.request.Request(test_url, headers={"User-Agent": "Mozilla/5.0"})
                start = time.time()
                resp = opener.open(req, timeout=timeout)
                elapsed = time.time() - start
                if resp.status in (200, 204):
                    latencies.append(elapsed)
                    if region == "abroad":
                        abroad_ok = True
                        abroad_latencies.append(elapsed)
                    log.info(f"{name} 竞速通过 {label} 测试成功, 延迟 {elapsed:.2f}s"
                             + (" (重试)" if attempt else "")
                             + (" [境内直连]" if region == "cn" else " [境外经代理]"))
                    break
            except Exception:
                if attempt == 0:
                    log.warning(f"{name} {label} 竞速测试失败 (第1次): 超时/拒绝")
    usable = abroad_ok
    if abroad_latencies:
        best = min(abroad_latencies)
    elif latencies:
        best = min(latencies)
    else:
        best = -1.0
    avg = (sum(latencies) / len(latencies)) if latencies else -1.0
    return (best, usable, avg, len(latencies))


def _prepare_test_dir(base_quick_dir, line_dir):
    """为并发检测的某条线路准备独立工作子目录。

    mihomo 用 -d 指定 home 目录，所有相对路径（config.yaml / geoip.metadb /
    Country.mmdb / cache.db / logs）都相对该目录。为避免多实例抢同一 cache.db、
    又能共享只读的 MMDB，这里：
      - makedirs(line_dir)
      - 把 quick.exe 也硬链接进子目录（_launch_quick 依赖该目录内有 quick.exe，
        否则会报“quick.exe 不存在”导致该线路直接失败——这是并发改造初期
        所有线路瞬间失败、进而触发“全部失败→更新配置→重测”死循环的根因）
      - 对只读的 geoip.metadb / Country.mmdb 做硬链接（同卷零成本），失败则拷贝
      - cache.db / logs 由 mihomo 在子目录内自行创建（天然隔离）
    """
    os.makedirs(line_dir, exist_ok=True)
    # quick.exe 是自包含单文件（无配套 dll），必须进子目录，否则启动失败
    exe_src = os.path.join(base_quick_dir, "quick.exe")
    exe_dst = os.path.join(line_dir, "quick.exe")
    if os.path.isfile(exe_src) and not os.path.exists(exe_dst):
        try:
            os.link(exe_src, exe_dst)  # 53MB 同卷硬链接，零额外空间
        except Exception:
            try:
                shutil.copy2(exe_src, exe_dst)
            except Exception as e:
                log.warning(f"准备测试目录拷贝 quick.exe 失败: {e}")
    for name in ("geoip.metadb", "Country.mmdb"):
        src = os.path.join(base_quick_dir, name)
        dst = os.path.join(line_dir, name)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                os.link(src, dst)  # NTFS 同卷硬链接，零额外空间
            except Exception:
                try:
                    shutil.copy2(src, dst)
                except Exception as e:
                    log.warning(f"准备测试目录拷贝 {name} 失败: {e}")


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
        # 等待端口真正释放，避免新内核因端口被僵尸进程占用而绑定失败
        deadline = time.time() + 8
        while time.time() < deadline:
            if not is_proxy_running():
                break
            time.sleep(0.5)
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
            # 停止时不仅要关闭开关，还要清除 ProxyServer 残留值，避免污染系统代理配置。
            # 如果不清除，Windows 网络设置会残留 "127.0.0.1:7890" 这个无效地址，
            # 导致用户即使关闭软件也无法上网——因为系统仍指向一个不存在的代理。
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "")
            log.info("已关闭系统代理（清除残留配置）")
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


def get_available_proxy_url():
    if is_proxy_running():
        return f"http://{PROXY_URL}"
    sys_enabled, sys_server = get_system_proxy()
    if sys_enabled and sys_server:
        proxy_url = sys_server
        if not proxy_url.startswith("http://") and not proxy_url.startswith("https://"):
            proxy_url = f"http://{proxy_url}"
        return proxy_url
    return None


def load_settings():
    path = os.path.join(get_app_dir(), "launcher_settings.json")
    defaults = {
        "auto_start": True,
        "auto_open_browser": True,
        "global_proxy": True,
        "browser_proxy_enabled": True,
        "custom_apps_enabled": False,
        "custom_apps_scope": "all",
        "custom_apps": [],
        "browser_path": "",
        "browser_type": "system",
        "system_browser_path": "",
        "quick_dir_path": "",
        "realtime_reconnect": False,
        "realtime_interval": 10,
        "auto_line_switch": False,
        "auto_line_interval": 30,
        "update_config_freq": "always",
        "always_update_config": False,
        "browser_proxy_mode": "specified",
        "browser_proxy_scope": "all",
        "global_proxy_mode": "all",
        "address_proxy_enabled": True,
        "address_proxy_scope": "all",
        "address_proxy_selected": 0,
        "tun_enabled": False,
        "tun_stack": "gvisor",
        "tun_proxy_mode": "all",
        "tls_fingerprint": "none",
        "sniffing_enabled": False,
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

    MIRROR_PREFIXES = [
        "https://gh-proxy.com/",
        "https://ghproxy.net/",
        "https://ghproxy.homeboyc.cn/",
        "https://ghfast.top/",
        "https://mirror.ghproxy.com/",
    ]

    def __init__(self, urls, save_path):
        super().__init__()
        self.urls = urls if isinstance(urls, list) else [urls]
        self.save_path = save_path
        self._paused = False
        self._cancelled = False

    def _build_opener(self, proxy_url=None):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if proxy_url:
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    'http': proxy_url,
                    'https': proxy_url,
                })
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx),
                    proxy_handler,
                )
                return opener, ctx
            except Exception:
                pass
        elif is_proxy_running():
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    'http': f'http://{PROXY_URL}',
                    'https': f'http://{PROXY_URL}',
                })
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx),
                    proxy_handler,
                )
                return opener, ctx
            except Exception:
                pass
        return None, ctx

    def _download(self, url, timeout=120, proxy_url=None):
        opener, ctx = self._build_opener(proxy_url=proxy_url)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        if opener:
            resp = opener.open(req, timeout=timeout)
        else:
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return resp

    def run(self):
        tmp_path = self.save_path + ".downloading"
        last_err = None
        for url in self.urls:
            is_github = "github.com" in url
            is_gitee = "gitee.com" in url
            if is_github:
                for prefix in self.MIRROR_PREFIXES:
                    try:
                        mirror_url = prefix + url
                        resp = self._download(mirror_url)
                        if self._save(resp, tmp_path):
                            return
                    except Exception:
                        if os.path.isfile(tmp_path):
                            os.remove(tmp_path)
                        continue
            if is_proxy_running():
                try:
                    resp = self._download(url)
                    if self._save(resp, tmp_path):
                        return
                except urllib.error.HTTPError as http_err:
                    if http_err.code == 404:
                        last_err = "该版本暂无下载资源（Release不存在）"
                        continue
                    if http_err.code == 403:
                        if os.path.isfile(tmp_path):
                            os.remove(tmp_path)
                        continue
                    last_err = f"下载失败(HTTP {http_err.code})"
                    if os.path.isfile(tmp_path):
                        os.remove(tmp_path)
                    continue
                except Exception as e:
                    if os.path.isfile(tmp_path):
                        os.remove(tmp_path)
            sys_enabled, sys_server = get_system_proxy()
            if sys_enabled and sys_server and not is_proxy_running():
                proxy_url = sys_server
                if not proxy_url.startswith("http://") and not proxy_url.startswith("https://"):
                    proxy_url = f"http://{proxy_url}"
                try:
                    resp = self._download(url, proxy_url=proxy_url)
                    if self._save(resp, tmp_path):
                        return
                except urllib.error.HTTPError as http_err:
                    if http_err.code == 404:
                        last_err = "该版本暂无下载资源（Release不存在）"
                        continue
                    if http_err.code == 403:
                        if os.path.isfile(tmp_path):
                            os.remove(tmp_path)
                        continue
                    last_err = f"下载失败(HTTP {http_err.code})"
                    if os.path.isfile(tmp_path):
                        os.remove(tmp_path)
                    continue
                except Exception as e:
                    if os.path.isfile(tmp_path):
                        os.remove(tmp_path)
            try:
                resp = self._download(url)
                if self._save(resp, tmp_path):
                    return
            except urllib.error.HTTPError as http_err:
                if http_err.code == 404:
                    last_err = "该版本暂无下载资源（Release不存在）"
                    continue
                if http_err.code == 403:
                    last_err = "下载被拒绝(403)"
                    if os.path.isfile(tmp_path):
                        os.remove(tmp_path)
                    continue
                last_err = f"下载失败(HTTP {http_err.code})"
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
                continue
            except Exception as e:
                last_err = str(e)[:80]
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
                continue
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)
        self.finished.emit(False, f"下载失败: {last_err or '所有下载方式均失败'}", "")

    def _save(self, resp, tmp_path):
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(tmp_path, "wb") as f:
            while True:
                if self._cancelled:
                    resp.close()
                    if os.path.isfile(tmp_path):
                        os.remove(tmp_path)
                    self.finished.emit(False, "下载已取消", "")
                    return False
                while self._paused and not self._cancelled:
                    self.msleep(200)
                if self._cancelled:
                    resp.close()
                    if os.path.isfile(tmp_path):
                        os.remove(tmp_path)
                    self.finished.emit(False, "下载已取消", "")
                    return False
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
        return True

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self):
        self._cancelled = True
        self._paused = False


class KernelVersionWorker(QThread):
    finished = pyqtSignal(list, str)
    progress = pyqtSignal(str)

    def __init__(self, quick_dir):
        super().__init__()
        self.quick_dir = quick_dir

    def _build_opener(self, proxy_url=None):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if proxy_url:
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    'http': proxy_url,
                    'https': proxy_url,
                })
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx),
                    proxy_handler,
                )
                return opener, ctx
            except Exception:
                pass
        elif is_proxy_running():
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    'http': f'http://{PROXY_URL}',
                    'https': f'http://{PROXY_URL}',
                })
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx),
                    proxy_handler,
                )
                return opener, ctx
            except Exception:
                pass
        return None, ctx

    def _fetch_json(self, url, timeout=15, proxy_url=None):
        opener, ctx = self._build_opener(proxy_url=proxy_url)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        if opener:
            with opener.open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        else:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))

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

    def _get_current_version(self):
        ver_file = os.path.join(self.quick_dir, "_kernel_version.txt")
        if os.path.isfile(ver_file):
            try:
                with open(ver_file, "r", encoding="utf-8") as f:
                    v = f.read().strip()
                    if v:
                        return v
            except Exception:
                pass
        exe_path = os.path.join(self.quick_dir, "quick.exe")
        if not os.path.isfile(exe_path):
            return ""
        try:
            result = subprocess.run(
                [exe_path, "-v"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = (result.stdout or "") + (result.stderr or "")
            m = re.search(r'v?(\d+\.\d+\.\d+)', output)
            if m:
                ver = m.group(1)
                try:
                    with open(ver_file, "w", encoding="utf-8") as f:
                        f.write(ver)
                except Exception:
                    pass
                return ver
        except Exception:
            pass
        return ""

    def run(self):
        try:
            self.progress.emit("正在获取内核版本列表...")
            api_url = f"https://api.github.com/repos/{MIHOMO_REPO}/releases?per_page=15"
            mirror_prefixes = [
                "https://gh-proxy.com/",
                "https://ghproxy.net/",
                "https://ghproxy.homeboyc.cn/",
                "https://ghfast.top/",
                "https://mirror.ghproxy.com/",
            ]
            releases = None
            for prefix in mirror_prefixes:
                if self.isInterruptionRequested():
                    self.finished.emit([], "已取消")
                    return
                try:
                    url = prefix + api_url
                    self.progress.emit(f"尝试加速镜像...")
                    releases = self._fetch_json(url, timeout=20)
                    if releases and isinstance(releases, list):
                        break
                    releases = None
                except Exception:
                    releases = None
                    continue
            if not releases:
                if is_proxy_running():
                    try:
                        self.progress.emit("尝试通过本地代理直连GitHub...")
                        releases = self._fetch_json(api_url, timeout=30)
                        if not (releases and isinstance(releases, list)):
                            releases = None
                    except Exception:
                        releases = None
            if not releases:
                sys_enabled, sys_server = get_system_proxy()
                if sys_enabled and sys_server and not is_proxy_running():
                    proxy_url = sys_server
                    if not proxy_url.startswith("http://") and not proxy_url.startswith("https://"):
                        proxy_url = f"http://{proxy_url}"
                    try:
                        self.progress.emit("尝试通过系统代理直连GitHub...")
                        releases = self._fetch_json(api_url, timeout=30, proxy_url=proxy_url)
                        if not (releases and isinstance(releases, list)):
                            releases = None
                    except Exception:
                        releases = None
            if not releases:
                try:
                    self.progress.emit("尝试GitHub直连...")
                    releases = self._fetch_json(api_url, timeout=30)
                    if not (releases and isinstance(releases, list)):
                        releases = None
                except Exception:
                    releases = None
            if not releases:
                self.finished.emit([], "无法连接更新服务器，请检查网络后重试")
                return
            result = []
            for rel in releases:
                tag = rel.get("tag_name", "")
                if not tag:
                    continue
                asset_name, download_url = self._find_asset(rel)
                is_prerelease = rel.get("prerelease", False) or "-p" in tag or "-alpha" in tag or "-beta" in tag or "-rc" in tag
                result.append({
                    "tag": tag,
                    "name": rel.get("name", tag),
                    "published_at": rel.get("published_at", "")[:10],
                    "body": (rel.get("body") or "")[:500],
                    "asset_name": asset_name,
                    "download_url": download_url,
                    "prerelease": is_prerelease,
                })
            current_ver = self._get_current_version()
            self.finished.emit(result, current_ver)
        except Exception as e:
            self.finished.emit([], f"获取版本列表失败: {e}")


class KernelDownloadWorker(QThread):
    progress = pyqtSignal(str)
    download_percent = pyqtSignal(int)
    finished = pyqtSignal(bool, str, str)

    MIRROR_PREFIXES = [
        "https://gh-proxy.com/",
        "https://ghproxy.net/",
        "https://ghproxy.homeboyc.cn/",
        "https://ghfast.top/",
        "https://mirror.ghproxy.com/",
        "",
    ]

    def __init__(self, quick_dir, tag, download_url, asset_name):
        super().__init__()
        self.quick_dir = quick_dir
        self.tag = tag
        self.download_url = download_url
        self.asset_name = asset_name

    def _build_opener(self, proxy_url=None):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if proxy_url:
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    'http': proxy_url,
                    'https': proxy_url,
                })
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx),
                    proxy_handler,
                )
                return opener, ctx
            except Exception:
                pass
        elif is_proxy_running():
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    'http': f'http://{PROXY_URL}',
                    'https': f'http://{PROXY_URL}',
                })
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx),
                    proxy_handler,
                )
                return opener, ctx
            except Exception:
                pass
        return None, ctx

    def _download_file(self, url, save_path, timeout=180, proxy_url=None):
        opener, ctx = self._build_opener(proxy_url=proxy_url)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        if opener:
            resp = opener.open(req, timeout=timeout)
        else:
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        with resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(save_path, "wb") as f:
                while True:
                    if self.isInterruptionRequested():
                        return
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(downloaded * 100 / total)
                        self.progress.emit(f"正在下载 {pct}% ({downloaded // 1024 // 1024}/{total // 1024 // 1024} MB)")
                        self.download_percent.emit(pct)

    def run(self):
        try:
            kernels_dir = os.path.join(self.quick_dir, "kernels")
            os.makedirs(kernels_dir, exist_ok=True)
            target_exe = os.path.join(kernels_dir, f"mihomo_{self.tag}.exe")
            if os.path.isfile(target_exe) and os.path.getsize(target_exe) > 1000:
                self.finished.emit(True, f"mihomo {self.tag} 已存在", target_exe)
                return

            tmp_dir = tempfile.mkdtemp(prefix="mihomo_dl_")
            zip_path = os.path.join(tmp_dir, self.asset_name or "mihomo.zip")

            self.progress.emit(f"正在下载 mihomo {self.tag}...")
            dl_prefixes = [p for p in self.MIRROR_PREFIXES if p]
            downloaded = False
            for prefix in dl_prefixes:
                if self.isInterruptionRequested():
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    self.finished.emit(False, "已取消", "")
                    return
                try:
                    url = prefix + self.download_url
                    self.progress.emit(f"通过加速镜像下载...")
                    self._download_file(url, zip_path, timeout=180)
                    if self.isInterruptionRequested():
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                        self.finished.emit(False, "已取消", "")
                        return
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
                if is_proxy_running():
                    try:
                        self.progress.emit("通过本地代理直连下载...")
                        self._download_file(self.download_url, zip_path, timeout=180)
                        if os.path.isfile(zip_path) and os.path.getsize(zip_path) > 1000:
                            downloaded = True
                        else:
                            if os.path.isfile(zip_path):
                                os.remove(zip_path)
                    except Exception:
                        if os.path.isfile(zip_path):
                            os.remove(zip_path)

            if not downloaded:
                sys_enabled, sys_server = get_system_proxy()
                if sys_enabled and sys_server and not is_proxy_running():
                    proxy_url = sys_server
                    if not proxy_url.startswith("http://") and not proxy_url.startswith("https://"):
                        proxy_url = f"http://{proxy_url}"
                    try:
                        self.progress.emit("通过系统代理直连下载...")
                        self._download_file(self.download_url, zip_path, timeout=180, proxy_url=proxy_url)
                        if os.path.isfile(zip_path) and os.path.getsize(zip_path) > 1000:
                            downloaded = True
                        else:
                            if os.path.isfile(zip_path):
                                os.remove(zip_path)
                    except Exception:
                        if os.path.isfile(zip_path):
                            os.remove(zip_path)

            if not downloaded:
                try:
                    self.progress.emit("GitHub直连下载...")
                    self._download_file(self.download_url, zip_path, timeout=180)
                    if os.path.isfile(zip_path) and os.path.getsize(zip_path) > 1000:
                        downloaded = True
                    else:
                        if os.path.isfile(zip_path):
                            os.remove(zip_path)
                except Exception:
                    if os.path.isfile(zip_path):
                        os.remove(zip_path)

            if not downloaded:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                self.finished.emit(False, "下载失败，请检查网络后重试", "")
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
                    self.finished.emit(False, "压缩包中未找到可执行文件", "")
                    return
                zf.extract(exe_name, tmp_dir)
                extracted = os.path.join(tmp_dir, exe_name)

            shutil.move(extracted, target_exe)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            self.finished.emit(True, f"mihomo {self.tag} 下载完成", target_exe)
        except Exception as e:
            self.finished.emit(False, f"下载失败: {e}", "")


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
        config_path = os.path.join(quick_dir, "config.yaml")
        _cfg_exists = os.path.isfile(config_path)
        _cfg_valid = _is_config_yaml_valid(quick_dir) if _cfg_exists else False
        _diagnose(f"启动入口 quick_dir={quick_dir} config_exists={_cfg_exists} config_valid={_cfg_valid}")

        # 本地配置缺失/已损坏时，可能有旧内核占着 7890 → 先停掉，确保后续能重新
        # 下载合法配置并成功绑定端口。仅当“有合法本地配置且代理已在运行”才直接复用。
        if (not _cfg_valid) and is_proxy_running():
            log.warning("本地配置缺失/损坏，先停止运行中的旧内核以便重建")
            try:
                stop_quick()
            except Exception:
                pass
        elif _cfg_valid and is_proxy_running():
            self.finished.emit(True, "代理已在运行")
            return
        log.info("开始启动代理服务")

        config_path = os.path.join(quick_dir, "config.yaml")
        has_local_config = _cfg_exists

        # 优化启动速度：本地已有【合法】config.yaml 时先立即启动内核，再后台下载更新配置
        # （新上游 ghfast.top 下载需 10s+，不应阻塞内核启动）。
        # 注意：配置已损坏时必须走下面“下载重建”分支，否则会拿坏配置启动内核 → 致命退出。
        if has_local_config and _cfg_valid:
            self.progress.emit("正在启动代理内核...")
            # 启动前确保 geoip.metadb 就位（GEOIP,CN,DIRECT 规则依赖）。
            # 若 _restore_bundled_kernel 未还原或文件丢失，这里兜底补一份，
            # 否则内核加载 GEOIP 规则失败、不绑端口 → “代理未就绪”。
            try:
                _ensure_mmdb(quick_dir)
            except Exception as _e:
                log.warning(f"启动前预置 geoip.metadb 失败: {_e}")
            quick_exe = os.path.join(quick_dir, "quick.exe")
            if not os.path.isfile(quick_exe):
                self.finished.emit(False, "代理内核不存在，请先更新代理内核")
                return
            if not start_quick(quick_dir):
                self.finished.emit(False, "代理内核启动失败")
                return
            if not wait_for_proxy(timeout=15):
                pid, name = _port_owner_info(7890)
                if pid and name and name.lower() != "quick.exe":
                    _diagnose(f"端口 7890 被 {name}(PID {pid}) 占用，内核无法绑定")
                    self.finished.emit(False,
                        f"端口 7890 被 {name}(PID {pid}) 占用，内核无法绑定。"
                        f"请先结束该进程，或到“设置→代理地址”改用其它端口后重试。")
                else:
                    _klog = _read_kernel_log(quick_dir)
                    _diagnose(f"端口 7890 在 15s 内未就绪（无其它进程占用，可能内核静默退出）；内核最后输出: {_klog}")
                    self.finished.emit(False, "代理内核启动失败（端口 7890 未能就绪）")
                return
            log.info("代理内核已启动（使用本地配置），后台下载最新配置...")
            self.finished.emit(True, "代理已启动 (后台更新配置中)")

            # 后台下载最新配置，下载成功后静默覆盖（下次重启生效）
            saved_line = self.kwargs.get("current_line")
            def _bg_download():
                try:
                    downloaded = download_all_configs()
                    if downloaded:
                        # 同样用真实内核校验挑合法配置，避免把坏配置静默写回
                        chosen = _select_first_valid_config(downloaded, saved_line, quick_dir)
                        if chosen:
                            save_config(quick_dir, chosen[1])
                            self.line_selected.emit(chosen[0])
                            log.info(f"后台配置更新完成: {chosen[0]}")
                        else:
                            log.warning("后台更新：所有订阅配置均无法解析，保留当前运行配置")
                except Exception as e:
                    log.warning(f"后台下载配置失败: {e}")
            import threading
            threading.Thread(target=_bg_download, daemon=True).start()
            return

        # 本地无【合法】config.yaml：必须下载才能启动（首次启动 / 配置损坏重建场景）
        self.progress.emit("正在获取线路配置...")
        try:
            stop_quick()
        except Exception:
            pass
        downloaded = download_all_configs()
        if downloaded:
            # 用真实内核校验挑选第一条合法配置：优先保留用户选定线路，
            # 否则回退到第一条能起来的线；全部坏则清晰报错，不陷入死循环。
            chosen = _select_first_valid_config(
                downloaded, self.kwargs.get("current_line"), quick_dir)
            if chosen:
                selected = chosen
                # 启动前再确保 geoip.metadb 就位（GEOIP 规则依赖），避免内核卡在加载
                try:
                    _ensure_mmdb(quick_dir)
                except Exception:
                    pass
                save_config(quick_dir, selected[1])
                self.line_selected.emit(selected[0])
                self.progress.emit(f"已选择: {selected[0]}")
                _diagnose(f"启动线路已选合法配置: {selected[0]} (配置 {len(selected[1])} bytes)")
                log.info(f"启动线路: {selected[0]}, 配置大小: {len(selected[1])} bytes")
            else:
                broken_names = "、".join(n for n, _, _ in downloaded)
                _diagnose(f"所有 {len(downloaded)} 条订阅均无法被内核解析: {broken_names}")
                self.finished.emit(False,
                    f"所有 {len(downloaded)} 条订阅配置均无法被内核解析"
                    f"（可能上游格式损坏：{broken_names}）。"
                    f"请到“上游管理”检查/移除损坏的订阅源后重试。")
                return
        else:
            if not has_local_config:
                self.finished.emit(False, "无可用配置")
                return
            log.warning("未下载到新配置，使用本地已有配置")
        self.progress.emit("正在启动代理内核...")
        quick_exe = os.path.join(quick_dir, "quick.exe")
        if not os.path.isfile(quick_exe):
            self.finished.emit(False, "代理内核不存在，请先更新代理内核")
            return
        if not start_quick(quick_dir):
            self.finished.emit(False, "代理内核启动失败")
            return
        if not wait_for_proxy(timeout=15):
            pid, name = _port_owner_info(7890)
            if pid and name and name.lower() != "quick.exe":
                self.finished.emit(False,
                    f"端口 7890 被 {name}(PID {pid}) 占用，内核无法绑定。"
                    f"请先结束该进程，或到“设置→代理地址”改用其它端口后重试。")
            else:
                _klog = _read_kernel_log(quick_dir)
                _diagnose(f"代理内核启动失败（端口 7890 未能就绪）；内核最后输出: {_klog}")
                self.finished.emit(False, "代理内核启动失败（端口 7890 未能就绪）")
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
        quick_exe = os.path.join(quick_dir, "quick.exe")
        if not os.path.isfile(quick_exe):
            self.finished.emit(False, "代理内核不存在，请先更新代理内核")
            return

        original_config = None
        config_path = os.path.join(quick_dir, "config.yaml")
        if os.path.isfile(config_path):
            with open(config_path, 'rb') as f:
                original_config = f.read()

        results = []
        total = len(downloaded)

        for i, (name, data, _src) in enumerate(downloaded):
            self.progress.emit(f"正在检测线路 {i+1}/{total}: {name}...")
            save_config(quick_dir, data)

            # 无论端口是否响应，都先停掉旧内核（避免僵尸进程抢占 7890 端口）
            stop_quick()
            # taskkill /f 异步生效，socket 释放有延迟；轮询等待 7890 真正空闲，
            # 否则旧内核残留仍占 7890，新内核绑不上 → 整页“代理未就绪”。
            _free_deadline = time.time() + 6
            while time.time() < _free_deadline:
                _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                _s.settimeout(0.5)
                try:
                    _s.connect(("127.0.0.1", 7890))
                    _busy = True  # 仍有进程在监听 7890
                except Exception:
                    _busy = False  # 端口已空闲
                finally:
                    _s.close()
                if not _busy:
                    break
                time.sleep(0.3)
            time.sleep(0.5)

            ok, reason = start_quick(quick_dir)
            if not ok:
                # 内核启动即致命退出（配置解析失败 / MMDB 缺失等），该线路不可用
                log.warning(f"{name} 内核启动失败，跳过检测: {reason}")
                results.append((name, -1.0, -1.0, 0, data, False))
                self.line_tested.emit(name, -1.0, False)
                try:
                    get_health_db().append(name, HealthRecord(
                        ts=datetime.now().isoformat(timespec="seconds"),
                        success=False, avg=-1.0, best=-1.0,
                        count=0, total=len(NODE_TEST_URLS),
                    ))
                except Exception as e:
                    log.warning(f"写健康度记录失败 {name}: {e}")
                continue

            if not wait_for_proxy(timeout=25):
                pid, owner = _port_owner_info(7890)
                if pid and owner and owner.lower() != "quick.exe":
                    log.warning(f"{name} 代理未就绪：端口 7890 被 {owner}(PID {pid}) 占用（非本内核），"
                                f"请结束该进程或改用其它端口")
                else:
                    # 端口未被他人占用却绑不上 → 内核大概率卡死/崩溃。读取内核真实输出定位。
                    _klog = _read_kernel_log(quick_dir)
                    log.warning(f"{name} 代理未就绪，跳过延迟测试；内核最后输出: {_klog}")
                results.append((name, -1.0, -1.0, 0, data, False))
                self.line_tested.emit(name, -1.0, False)
                # Batch 3: 代理未就绪也算失败
                try:
                    get_health_db().append(name, HealthRecord(
                        ts=datetime.now().isoformat(timespec="seconds"),
                        success=False, avg=-1.0, best=-1.0,
                        count=0, total=len(NODE_TEST_URLS),
                    ))
                except Exception as e:
                    log.warning(f"写健康度记录失败 {name}: {e}")
                continue

            latencies = []          # 所有可达站点（含境内，用于展示/健康度）
            abroad_ok = False        # 至少有一个境外站点经代理成功（线路真正可用的硬条件）
            abroad_latencies = []    # 仅境外站点延迟（用于选路比较）
            for label, test_url, region in NODE_TEST_URLS:
                # 单 URL 失败后重试 1 次：quick.exe 刚启动可能尚未完成首次握手/DNS 解析，
                # 首包超时并不代表线路本身不可用，重试可显著降低误判
                for attempt in range(2):
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
                            if region == "abroad":
                                abroad_ok = True
                                abroad_latencies.append(elapsed)
                            log.info(f"{name} 通过 {label} 测试成功, 延迟 {elapsed:.2f}s" +
                                     (f" (重试第{attempt}次)" if attempt else "") +
                                     (" [境内直连]" if region == "cn" else " [境外经代理]"))
                            break
                        else:
                            log.warning(f"{name} {label} 测试返回非 200/204: {resp.status}")
                    except Exception as e:
                        log.warning(f"{name} {label} 测试失败 (第{attempt+1}次): {type(e).__name__}: {e}")

            # 线路可用判定：必须至少有一个境外站点经代理成功（Baidu 等境内直连不算）
            usable = abroad_ok
            if latencies:
                avg = sum(latencies) / len(latencies)
                best = min(latencies)
                # avg 仅用于展示；选路以 abroad_latencies 为准
                results.append((name, avg, best, len(latencies), data, usable))
                self.line_tested.emit(name, (min(abroad_latencies) if abroad_latencies else avg), usable)
                # Batch 3: 写健康度记录
                try:
                    get_health_db().append(name, HealthRecord(
                        ts=datetime.now().isoformat(timespec="seconds"),
                        success=usable, avg=(min(abroad_latencies) if abroad_latencies else -1.0),
                        best=(min(abroad_latencies) if abroad_latencies else -1.0),
                        count=len(abroad_latencies), total=len([u for u in NODE_TEST_URLS if u[2] == "abroad"]),
                    ))
                except Exception as e:
                    log.warning(f"写健康度记录失败 {name}: {e}")
                if not usable:
                    log.warning(f"{name} 仅境内可达（或境外经代理失败），不视为可用线路")
            else:
                results.append((name, -1.0, -1.0, 0, data, False))
                self.line_tested.emit(name, -1.0, False)
                # Batch 3: 失败也记录
                try:
                    get_health_db().append(name, HealthRecord(
                        ts=datetime.now().isoformat(timespec="seconds"),
                        success=False, avg=-1.0, best=-1.0,
                        count=0, total=len([u for u in NODE_TEST_URLS if u[2] == "abroad"]),
                    ))
                except Exception as e:
                    log.warning(f"写健康度记录失败 {name}: {e}")

        # 检测完成后自动选路：仅从“真正可用”（境外经代理成功）的线路中选一条
        fastest_name, fastest_data = None, None
        if results:
            successful = [(n, d) for n, avg, best, count, d, ok in results if ok]
            if successful:
                # 取第一条可用线路（免费节点延迟波动大，可用优先于最快）
                fastest_name, fastest_data = successful[0]
                log.info(f"自动选路: 选择可用线路 {fastest_name} (共 {len(successful)} 条可用)")

        proxy_enabled = self.kwargs.get("proxy_enabled", False)
        current_line = self.kwargs.get("current_line", "")
        if proxy_enabled:
            restore_data = original_config
            if fastest_data:
                restore_data = fastest_data
                log.info(f"检测后自动选路: {fastest_name}")
            elif current_line:
                for n, d, _src in downloaded:
                    if n == current_line:
                        restore_data = d
                        break
            if restore_data:
                save_config(quick_dir, restore_data)
            if is_proxy_running():
                stop_quick()
                time.sleep(1)
            start_quick(quick_dir)
            wait_for_proxy(timeout=8)
        else:
            stop_quick()
            if fastest_data:
                save_config(quick_dir, fastest_data)
                log.info(f"检测后自动选路（未启动代理）: {fastest_name}")
            elif original_config:
                save_config(quick_dir, original_config)

        self.kwargs["results"] = results
        # 检测完成后自动切换线路
        if fastest_name:
            self.line_selected.emit(fastest_name)
            self.finished.emit(True, f"检测完成 (已自动切换至最快线路: {fastest_name})")
        else:
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

        # Batch 3: 改为先测全部 → 用 (历史健康度 + 当前延迟) 联合打分
        # 旧逻辑：单次最快直接选。问题：一次延迟 0.5s 的线路可能 7 天成功率 30%
        # 新逻辑：综合 7d 成功率 (60%) + 当前延迟 (40%)
        test_results = []  # [(name, elapsed, data, success)]
        health_db = get_health_db()
        for name, data, _src in downloaded:
            self.progress.emit(f"正在测试 {name}...")
            save_config(quick_dir, data)

            if is_proxy_running():
                stop_quick()
                time.sleep(1)

            ok, reason = start_quick(quick_dir)
            if not ok:
                log.warning(f"{name} 内核启动失败，跳过自动选择: {reason}")
                try:
                    health_db.append(name, HealthRecord(
                        ts=datetime.now().isoformat(timespec="seconds"),
                        success=False, avg=-1.0, best=-1.0,
                        count=0, total=1,
                    ))
                except Exception:
                    pass
                continue
            if not wait_for_proxy(timeout=8):
                log.warning(f"{name} 代理未就绪，跳过自动选择")
                # 记录失败
                try:
                    health_db.append(name, HealthRecord(
                        ts=datetime.now().isoformat(timespec="seconds"),
                        success=False, avg=-1.0, best=-1.0,
                        count=0, total=1,
                    ))
                except Exception:
                    pass
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
                if resp.status in (200, 204):
                    test_results.append((name, elapsed, data, True))
                    log.info(f"{name} 自动选择测试成功, 延迟 {elapsed:.2f}s")
                    # 写健康度
                    try:
                        health_db.append(name, HealthRecord(
                            ts=datetime.now().isoformat(timespec="seconds"),
                            success=True, avg=elapsed, best=elapsed,
                            count=1, total=1,
                        ))
                    except Exception:
                        pass
                else:
                    log.warning(f"{name} 自动选择测试返回非 200/204: {resp.status}")
                    try:
                        health_db.append(name, HealthRecord(
                            ts=datetime.now().isoformat(timespec="seconds"),
                            success=False, avg=-1.0, best=-1.0,
                            count=0, total=1,
                        ))
                    except Exception:
                        pass
            except Exception as e:
                log.warning(f"{name} 自动选择测试失败: {type(e).__name__}: {e}")
                try:
                    health_db.append(name, HealthRecord(
                        ts=datetime.now().isoformat(timespec="seconds"),
                        success=False, avg=-1.0, best=-1.0,
                        count=0, total=1,
                    ))
                except Exception:
                    pass

        # 联合打分：score = 0.6 * 7d_success_rate + 0.4 * (1 - normalized_latency)
        # 无 7d 数据时降级为 score = 1.0 - normalized_latency
        fastest_name, fastest_data = None, None
        if test_results:
            max_lat = max(r[1] for r in test_results) or 1.0
            min_lat = min(r[1] for r in test_results)
            best_score = -1.0
            for name, elapsed, data, _ in test_results:
                rate = health_db.get_7d_success_rate(name)
                if rate is None:
                    # 无历史数据：仅用当前延迟 (但加权稍低)
                    score = 0.4 * (1 - (elapsed - min_lat) / max(max_lat - min_lat, 0.01))
                else:
                    lat_score = 1 - (elapsed - min_lat) / max(max_lat - min_lat, 0.01)
                    score = 0.6 * rate + 0.4 * lat_score
                log.info(f"自动选线评分: {name} rate={rate} elapsed={elapsed:.2f}s score={score:.3f}")
                if score > best_score:
                    best_score = score
                    fastest_name = name
                    fastest_data = data
            log.info(f"自动选线: 选择 {fastest_name} (综合得分 {best_score:.3f})")

        proxy_enabled = self.kwargs.get("proxy_enabled", False)
        if proxy_enabled:
            if fastest_data:
                save_config(quick_dir, fastest_data)
            elif original_config:
                save_config(quick_dir, original_config)
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
                save_config(quick_dir, original_config)

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
                    for name, data, _src in downloaded:
                        if name == saved_line:
                            selected = (name, data)
                            break
                if not selected:
                    selected = (downloaded[0][0], downloaded[0][1])
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
            for name in ('ico.png', 'icon.png', 'icon.ico'):
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
        self._progress = value
        self.repaint()
        QApplication.processEvents()

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
        title = BRAND_NAME
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


class CopyableLabel(QTextEdit):
    def __init__(self, text="", font_size="8pt", max_height=40, parent=None):
        super().__init__(parent)
        self._font_size = font_size
        self._color = "#888"
        self.setPlainText(text)
        self.setReadOnly(True)
        self.setMaximumHeight(max_height)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._apply_style()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _apply_style(self):
        self.setStyleSheet(
            f"QTextEdit {{ background-color: transparent; color: {self._color}; "
            f"font-size: {self._font_size}; border: none; padding: 0px; }} "
            f"QTextEdit:hover {{ background-color: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 3px; padding: 2px; }}"
        )

    def setText(self, text):
        self.setPlainText(text)

    def setStyleSheet(self, style):
        if "QTextEdit" not in style:
            import re
            m = re.search(r'color:\s*([^;]+)', style)
            if m:
                self._color = m.group(1).strip()
            m2 = re.search(r'font-size:\s*([^;]+)', style)
            if m2:
                self._font_size = m2.group(1).strip()
            self._apply_style()
        else:
            super().setStyleSheet(style)


class ElidedLabel(QLabel):
    """单行省略号标签：宽度不足时自动在右侧显示…

    与 CopyableLabel 的区别：
      - 基于 QLabel 而非 QTextEdit，开销更小
      - 强制单行显示，不换行
      - 宽度不足时自动调用 QFontMetrics.elidedText 省略
      - 完整内容通过 setToolTip 单独提供
    """

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = text or ""
        self.setWordWrap(False)
        # 不允许用户选中文字（保持单行省略号的简洁）
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._update_elided_text()

    def setText(self, text):
        """设置完整文本（宽度不够时自动在右侧加…）"""
        self._full_text = text or ""
        self._update_elided_text()

    def fullText(self):
        return self._full_text

    def _update_elided_text(self):
        if not self._full_text:
            super().setText("")
            return
        fm = self.fontMetrics()
        # 预留 4px 边距，避免文字触边
        avail = max(10, self.width() - 4)
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, avail)
        super().setText(elided)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()


def _clean_release_body(body):
    """清洗 mihomo release notes 的 Markdown，保留可读文本。

    处理内容：
      - ## What's Changed  →  What's Changed
      - **Full Changelog** →  Full Changelog
      - [text](url)        →  text
      - * feat: ...        →  • feat: ...
      - <br> 等 HTML 标签   →  移除
      - 长 commit hash 列表 →  去掉 hash 前缀，加 •
    """
    if not body:
        return ""
    # 移除 HTML 标签（<br>、<a> 等）
    body = re.sub(r"<[^>]+>", "", body)
    # 移除 markdown 标题符号（##、### 等）
    body = re.sub(r"^#+\s*", "", body, flags=re.MULTILINE)
    # 转换粗体 **text** → text
    body = re.sub(r"\*\*([^*]+)\*\*", r"\1", body)
    # 转换斜体 *text* → text（避免与 commit hash 后的空格冲突，先做粗体）
    body = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", body)
    # 转换 markdown 链接 [text](url) → text
    body = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", body)
    # 移除 commit hash 前缀（7-40 位 hex 字符 + 至少一个空格）
    body = re.sub(r"^\s*[0-9a-f]{7,40}\s+", "• ", body, flags=re.MULTILINE)
    # 移除普通 bullet 符号（*、-）转为统一 •
    body = re.sub(r"^\s*[\*\-]\s+", "• ", body, flags=re.MULTILINE)
    # 合并 3 个以上连续换行为 2 个
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


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


class _CurrentSizedStack(QStackedWidget):
    """QStackedWidget that sizes to the current page's sizeHint.

    默认 QStackedWidget 的 sizeHint 是所有页面中最大的一个，
    切到较矮的 tab 时，stack 会比当前页高，底部出现无法收起的多余区域。
    本子类让 stack 的尺寸跟随当前页面，底部多余区域自动消失。
    """
    def sizeHint(self):
        current = self.currentWidget()
        if current:
            return current.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        current = self.currentWidget()
        if current:
            return current.minimumSizeHint()
        return super().minimumSizeHint()


class MainWindow(QMainWindow):
    _version_data_ready = pyqtSignal()
    _kernel_versions_ready = pyqtSignal()

    def __init__(self, splash=None):
        super().__init__()
        self._splash = splash
        self.setWindowTitle(APP_NAME)

        # 根据屏幕分辨率动态设置窗口尺寸
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            # 窗口高度不超过屏幕可用高度的90%，宽度不超过90%
            max_w = int(screen_geom.width() * 0.90)
            max_h = int(screen_geom.height() * 0.90)
            # 默认高度按 1080P（≈1080px）适配为 750px（≈69%），保证 1080P 屏幕下
            # 代理设置栏目一屏可见主要内容、线路服务底部留白适中；
            # 屏幕更矮时按 max_h 收缩避免超出可视区。
            base_w, base_h = 780, 750
            win_w = min(base_w, max_w)
            win_h = min(base_h, max_h)
            # 最小尺寸设为较小值，内容通过滚动区域保证不被压缩
            self.setMinimumSize(min(780, max_w), min(600, max_h))
            self.resize(win_w, win_h)
        else:
            self.setMinimumSize(780, 600)
            self.resize(780, 750)

        self.setStyleSheet(STYLESHEET)
        self.setAutoFillBackground(True)

        if self._splash:
            self._splash.set_progress(0.2, "正在加载配置...")

        self.settings = load_settings()
        self._version_data_ready.connect(self._on_version_data_ready)
        self._kernel_versions_ready.connect(self._on_kernel_versions_ready)

        global PROXY_HOST, PROXY_PORT
        saved_host = self.settings.get("proxy_host", PROXY_HOST)
        saved_port = self.settings.get("proxy_port", PROXY_PORT)
        if saved_host:
            PROXY_HOST = saved_host
        if saved_port:
            PROXY_PORT = int(saved_port)
        _update_proxy_url()
        self._auto_download_kernel = False
        # 首次运行时从EXE内嵌资源还原数据文件（versions.json、gitlog.json）
        self._restore_bundled_data()
        self.quick_dir = self._resolve_quick_dir()
        self.current_line = self.settings.get("current_line", "")
        self.line_results = {}
        self.line_latencies = {}      # name -> 最佳境外延迟(秒)，-1 表示不可用
        self.line_usable = {}         # name -> 是否真正能代理境外
        self._last_auto_switch_ts = 0.0
        self.worker = None
        self._auto_line_timer = None

        log.info(f"应用版本: {VERSION}")
        log.info(f"基础目录: {get_base_dir()}")
        log.info(f"Quick目录: {self.quick_dir}")

        if self._splash:
            self._splash.set_progress(0.4, "正在构建界面...")

        self._set_icon()
        self._build_ui()

        # 关闭按钮默认最小化到托盘，而不是退出进程。
        # 必须在创建主窗口后立即设置，否则窗口隐藏时 app 会随最后一个窗口一起退出。
        QApplication.instance().setQuitOnLastWindowClosed(False)
        self._setup_tray()

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
            # 启动前先注入所有 Yunji 规则
            self._inject_all_rules()
            QTimer.singleShot(500, self._on_start)

        if self._auto_download_kernel and self.quick_dir:
            QTimer.singleShot(800, self._auto_download_latest_kernel)

        QTimer.singleShot(1000, self._startup_download_config)

        # 加载内核版本列表（缓存或本地数据）
        QTimer.singleShot(300, self._init_kernel_list)

        # 恢复调试模式
        if self.settings.get("debug_mode", False):
            self._start_debug_log()

        if self._splash:
            self._splash.set_progress(1.0, "加载完成！")
            QTimer.singleShot(200, self._finish_splash)
        else:
            self.show()
            QTimer.singleShot(500, self._force_foreground)

    def _resolve_quick_dir(self):
        """内核目录 = EXE 所在目录下的 Quick/（相对目录，绝不写死绝对路径）。

        设计铁律（呼应“不要硬编码路径”）：
        - 内核目录永远 = os.path.join(get_app_dir(), "Quick")，而 get_app_dir() 在打包态
          直接返回 EXE 自身所在目录（dirname(sys.executable)），因此无论 EXE 被拷贝到
          哪台机器、哪个文件夹，只要同目录释放出 Quick/ 即可运行，是纯相对路径。
        - 绝不把绝对路径写进 launcher_settings.json 的 quick_dir_path：一旦写死，EXE
          移动后该绝对路径就指向错误位置，导致“内嵌内核还原到 A、实际运行从 B”。
        - 因此这里不再读取/持久化 quick_dir_path，内核目录每启动都按 EXE 相对位置重算。
        """
        # 永远相对 EXE：get_app_dir() 打包态 = EXE 所在目录
        quick_dir = os.path.join(get_app_dir(), "Quick")
        os.makedirs(quick_dir, exist_ok=True)

        # 1) 优先从 EXE 内嵌资源还原到 EXE 相对目录（首启 / 版本刷新都会补齐内核）
        try:
            self._restore_bundled_kernel(quick_dir)
        except Exception as _e:
            log.warning(f"还原内嵌内核失败: {_e}")

        # 2) EXE 相对目录已有可用内核 → 直接采用（不再把绝对路径写进 settings）
        if os.path.isfile(os.path.join(quick_dir, "quick.exe")):
            # 显式打印推导来源，证明路径是 dirname(sys.executable)/Quick（相对 EXE，
            # 非写死）。用户把 EXE 放到哪，内核目录就解析到哪，换机器/目录零改动。
            log.info(f"内核目录(EXE相对): {quick_dir}  [推导自 sys.executable={sys.executable}]")
            # 防御：geoip.metadb 缺失会让 mihomo 联网下载被墙资源 → 卡死不绑 7890
            # （表现为“代理未就绪”）。该文件应已随 EXE 内嵌并还原，若仍缺失说明被杀软
            # 误删或还原失败，此处告警并强制再还原一次，便于从日志一眼定位。
            _geo = os.path.join(quick_dir, "geoip.metadb")
            if not os.path.isfile(_geo):
                log.warning("⚠️ 运行目录缺 geoip.metadb：内核可能因联网下载 GEOIP 被墙而卡死、"
                            "不绑 7890。本 EXE 应已内嵌该文件，请确认未被杀软误删；将强制再还原一次。")
                try:
                    self._restore_bundled_kernel(quick_dir)
                except Exception as _e:
                    log.warning(f"补齐 geoip.metadb 失败: {_e}")
            return quick_dir

        # 3) 既无内嵌可还原、也无有效内核 → 等待远程下载内核（仍落到 EXE 相对目录）
        log.info(f"内核目录已创建，等待下载内核: {quick_dir}")
        self._auto_download_kernel = True
        return quick_dir

    def _restore_bundled_kernel(self, quick_dir):
        """从EXE内嵌资源完整还原代理核心到Quick目录。
        构建时将整个 dev/app/Quick/（除运行时 config.yaml/backup）通过 --add-data
        打包进 EXE 的 _MEIPASS/Quick/ 目录。首次运行时把内嵌 Quick/ 完整递归还原到
        运行目录，使运行目录与开发模式字节级一致（含 ui/、kernels/、geoip.metadb、
        Country.mmdb、GeoSite.dat 等全部文件），彻底排除“缺文件导致开发能跑、EXE 跑不了”。

        仅排除运行时生成/陈旧状态文件：config.yaml、config.yaml_backup、cache.db、
        _bundled_build.txt 标记、以及 Windows 保留名 nul。config.yaml 由运行时下载生成，
        绝不被内嵌副本覆盖（构建时也已从包中剔除）。
        """
        if not getattr(sys, 'frozen', False):
            return
        meipass = getattr(sys, '_MEIPASS', '')
        if not meipass:
            return

        bundled_quick = os.path.join(meipass, "Quick")
        if not os.path.isdir(bundled_quick):
            return

        bundled_exe = os.path.join(bundled_quick, "quick.exe")
        if not os.path.isfile(bundled_exe):
            return

        # 运行时状态文件：保留用户已下载的真实配置与本地缓存，不被内嵌副本覆盖
        _skip_names = {
            "config.yaml",        # 运行时下载的真实多节点配置（包内本就无此文件）
            "config.yaml_backup",  # 运行时自动备份
            "cache.db",           # mihomo 运行时缓存，自动生成
            "_bundled_build.txt",  # 本函数的版本标记，非内核文件
        }

        # 只读内核数据文件：被杀软隔离/损坏后绝不能“存在即跳过”，必须每次强制覆盖，
        # 否则陈旧损坏副本永驻 → 内核卡在加载 GEOIP/MMDB → “dev 能跑、EXE 跑不了”。
        _force_overwrite = {
            "geoip.metadb",
            "Country.mmdb",
            "GeoSite.dat",
        }

        # 版本感知刷新标记：记录“上次还原来自哪个 EXE 构建版本”，构建版本变化则强制
        # 完整覆盖内核与数据文件，避免陈旧 runtime 永远不被新 EXE 覆盖——这正是“开发能跑、
        # EXE 跑不了、且换多个新 EXE 仍问题依旧”的根因（旧文件因“存在即跳过”永不更新）。
        _build_marker = os.path.join(quick_dir, "_bundled_build.txt")
        bundled_build = ""
        _bv = os.path.join(meipass, "_build_version.txt")
        if os.path.isfile(_bv):
            try:
                bundled_build = open(_bv, "r", encoding="utf-8").read().strip()
            except Exception:
                pass
        deployed_build = ""
        if os.path.isfile(_build_marker):
            try:
                deployed_build = open(_build_marker, "r", encoding="utf-8").read().strip()
            except Exception:
                pass
        need_refresh = bool(bundled_build) and (bundled_build != deployed_build)

        try:
            os.makedirs(quick_dir, exist_ok=True)

            # 需刷新且旧内核可能正在运行（占用文件导致无法覆盖）时，先停掉旧内核
            if need_refresh:
                try:
                    stop_quick()
                except Exception:
                    pass

            # 完整递归还原内嵌 Quick/：缺失即复制；构建版本变化则强制覆盖全部内核/数据文件
            _refresh_ok = True
            for _root, _dirs, _files in os.walk(bundled_quick):
                _rel = os.path.relpath(_root, bundled_quick)
                _target_root = quick_dir if _rel == "." else os.path.join(quick_dir, _rel)
                os.makedirs(_target_root, exist_ok=True)
                for _fn in _files:
                    if _fn.lower() == "nul":  # Windows 保留名，无法写入
                        continue
                    if _fn in _skip_names:
                        continue
                    _src = os.path.join(_root, _fn)
                    _dst = os.path.join(_target_root, _fn)
                    _need_copy = (not os.path.exists(_dst)) or need_refresh or (_fn in _force_overwrite)
                    # 杀软隔离特征：部署文件明显小于内嵌源（如 quick.exe 被杀软替换为
                    # 0 字节/损坏占位）→ 强制重新覆盖。否则“存在即跳过”会让损坏副本永驻，
                    # 直接导致内核进程起不来（表现为“代理内核未启动”），这是 dev 能跑、
                    # EXE 跑不了的另一真凶（geoip 修复只管“起了不绑 7890”，不管“起不来”）。
                    if (not _need_copy) and os.path.isfile(_dst):
                        try:
                            _dst_sz = os.path.getsize(_dst)
                            _src_sz = os.path.getsize(_src)
                            if _src_sz > 0 and _dst_sz < _src_sz * 0.9:
                                _need_copy = True
                                log.warning(f"部署文件 {_fn} 体积异常偏小({_dst_sz}B < 源 {_src_sz}B，"
                                            f"疑似被杀软隔离)，强制重新还原")
                        except Exception:
                            pass
                    if _need_copy:
                        try:
                            shutil.copy2(_src, _dst)
                        except OSError as _e:
                            _refresh_ok = False
                            log.warning(f"还原内核文件 {_fn} 失败(可能被占用): {_e}")

            # 仅当刷新成功（或本就无需刷新）才更新标记，确保刷新失败会在下次启动重试
            if (not need_refresh) or _refresh_ok:
                try:
                    with open(_build_marker, "w", encoding="utf-8") as _f:
                        _f.write(bundled_build)
                except Exception:
                    pass

            log.info(f"代理核心已从内嵌资源完整还原: {quick_dir}" + (f" (构建 {bundled_build})" if bundled_build else ""))
        except Exception as e:
            log.error(f"还原内嵌代理核心失败: {e}")

    def _restore_bundled_data(self):
        """从EXE内嵌资源还原数据文件（versions.json、gitlog.json）到本地dev/app/目录。
        构建时通过 --add-data 打包进EXE的 _MEIPASS/ 目录。
        首次运行时自动还原，后续检查更新时从远程获取覆盖本地。
        """
        if not getattr(sys, 'frozen', False):
            return
        meipass = getattr(sys, '_MEIPASS', '')
        if not meipass:
            return

        # 打包态 get_app_dir() = EXE 所在目录；开发态 = dev/app。统一用 get_app_dir()，
        # 避免 frozen 模式下多写一层 app/ 子目录导致与 load_settings/save_settings 错位。
        app_dir = get_app_dir()

        for filename in ["versions.json", "gitlog.json", "kernel_versions_cache.json"]:
            local_path = os.path.join(app_dir, filename)
            # 本地已存在则跳过（说明已还原过或检查更新已覆盖）
            if os.path.isfile(local_path):
                continue
            bundled_path = os.path.join(meipass, filename)
            if not os.path.isfile(bundled_path):
                continue
            try:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                shutil.copy2(bundled_path, local_path)
                log.info(f"已从内嵌资源还原数据文件: {filename}")
            except Exception as e:
                log.error(f"还原内嵌数据文件 {filename} 失败: {e}")

    def _set_icon(self):
        if hasattr(sys, '_MEIPASS'):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        for name in ('ico.png', 'icon.png', 'icon.ico'):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                self.setWindowIcon(QIcon(p))
                break

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # 不设 stretch=1：让 _build_tabs() 高度 = sizeHint = nav_bar + page.sizeHint()。
        # 每个 tab 切换时 _build_tabs() 高度自适应为当前 page 的实际内容高度，
        # central 高度同步变化，window 高度随之自适应，
        # 不再共用一个固定 viewport 高度，避免"线路服务"等较矮页面底部出现大留白。
        layout.addWidget(self._build_tabs())
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
            # 顶部菜单按钮收窄 10px：默认每个按钮约 186px（780 窗口下），限制为 176px
            btn.setMaximumWidth(176)
            btn.clicked.connect(lambda checked, i=idx: self._on_nav_clicked(i))
            nav_bar.addWidget(btn, stretch=1)
            self.nav_buttons.append(btn)
        self.nav_buttons[0].setChecked(True)

        layout.addLayout(nav_bar)

        # 给每个 page 各自包一个 QScrollArea：
        # - 之前所有 page 共用一个外层 QScrollArea，viewport 高度按 stack 在 main layout 中
        #   实际占用的空间算（不是 stack 的 sizeHint），所以切到较矮的 tab 时底部出现大留白。
        # - 改成每个 page 独立包 QScrollArea 后，stack 的 sizeHint = 当前 page 的
        #   QScrollArea sizeHint = page 内容 sizeHint，window 高度自然跟随当前 page 走，
        #   内容超过视口时各自出滚动条。
        # log / update tab 内部本来就有 scroll area，再嵌一层无害。
        self.stack = _CurrentSizedStack()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.stack.addWidget(self._wrap_in_scroll(self._build_service_tab()))
        self.stack.addWidget(self._wrap_in_scroll(self._build_proxy_tab()))
        self.stack.addWidget(self._wrap_in_scroll(self._build_log_tab()))
        self.stack.addWidget(self._wrap_in_scroll(self._build_update_tab()))
        self.stack.currentChanged.connect(self._on_tab_changed)

        # stack 直接占满 main layout
        layout.addWidget(self.stack, stretch=1)

        # 首次启动时强制初始化 window 高度为当前 page 的 sizeHint
        # （addWidget 不会触发 currentChanged，需要手动调用）
        QTimer.singleShot(0, lambda: self._on_tab_changed(0))

        return container

    def _wrap_in_scroll(self, page):
        """把单个 page 包进独立的 QScrollArea，让每个 page 拥有自己的 viewport 高度。

        之前所有 page 共用一个外层 QScrollArea，viewport 高度按外层 layout 实际
        分配给 scroll area 的高度算（≈ 窗口可用高度），切到较矮的 tab 时底部就
        出现与最高 tab 等高的空白。改成每个 page 独立包一层后，stack 的 sizeHint
        跟随当前 page 自己的内容高度，窗口高度也就能跟着当前 page 走了。
        """
        scroll = QScrollArea()
        scroll.setObjectName("page-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea#page-scroll {{ background-color: {COLOR_BG}; border: none; }}"
            f"QScrollBar:vertical {{ background-color: {COLOR_BG}; width: 8px; border: none; }}"
            f"QScrollBar::handle:vertical {{ background-color: #333; border-radius: 4px; min-height: 30px; }}"
            f"QScrollBar::handle:vertical:hover {{ background-color: #555; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
        )
        scroll.setWidget(page)
        return scroll

    def _on_tab_changed(self, idx):
        """tab 切换时更新布局和滚动条位置。

        现在每个 page 各自包了一个 QScrollArea，stack 的 sizeHint = 当前 page
        的 sizeHint。这里只做：
        1. 把当前 page 的滚动条重置到顶部；
        2. 仅当新内容高度超过当前窗口高度时扩大窗口，
           不要缩小——避免覆盖 __init__ 里设的 860px 默认高度。
           内容短时窗口保持用户的设定（底部留白可接受，由各 page 自己的滚动条保证可读性）。
        """
        current = self.stack.currentWidget()
        if current and isinstance(current, QScrollArea):
            current.verticalScrollBar().setValue(0)
        self.stack.updateGeometry()
        central = self.centralWidget()
        if central and central.layout():
            central.layout().activate()
        # 只在内容比当前窗口高时才扩大窗口，不缩小（保留默认 860px）
        if not self.isMaximized() and not self.isFullScreen():
            hint_h = self.layout().sizeHint().height()
            if hint_h > self.height():
                self.resize(self.width(), hint_h)
        self.updateGeometry()

    def _on_nav_clicked(self, idx):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)
        self.stack.setCurrentIndex(idx)

    def _build_service_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)  # 大面板间高度间隔 10px
        layout.addWidget(self._build_proxy_service_panel())
        layout.addWidget(self._build_browser_card())
        layout.addWidget(self._build_line_service_panel())
        # 底部 stretch：把 viewport 多余空间推到 panel 之后，
        # 避免 panel 被拉伸导致内部 title/子卡片间出现大空白。
        layout.addStretch(1)
        return page

    def _build_panel_card(self, title, sub_cards, help_btn=None):
        """创建带标题的大面板容器（包含多个子卡片）

        panel 用 (Expanding, Maximum)：水平可拉伸、垂直最大 = sizeHint。
        配合 setWidgetResizable(False)，让 stack 高度 = page.sizeHint()，
        page 高度 = 实际内容高度（sum(panel.sizeHint) + margins）。
        panel 内部 layout 高度严格 = sizeHint，不会被外部 layout 拉伸。

        help_btn：可选的问号气泡按钮，传进来后显示在标题右侧。
        """
        panel = QFrame()
        panel.setObjectName("card")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        v = QVBoxLayout(panel)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(10)  # 子卡片间高度间隔 10px
        # 标题行：标题 + 可选问号气泡按钮
        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {COLOR_TEXT};")
        title_row.addWidget(title_lbl)
        if help_btn is not None:
            title_row.addWidget(help_btn)
        title_row.addStretch()
        v.addLayout(title_row)
        # 子卡片
        for sub in sub_cards:
            v.addWidget(sub)
        return panel

    def _build_proxy_service_panel(self):
        """代理服务大面板：标题「代理服务」+ 2 个子卡片（代理状态 / 本地代理）"""
        # 问号气泡：强调开启代理服务的关键性，并配合检测线路的重要性
        proxy_service_help_btn = _make_help_btn(
            "代理服务说明",
            "代理服务说明",
            "【代理服务】\n"
            "代理服务是本软件的核心，只有开启后所有代理功能才会生效。\n"
            "包括：全局系统代理、地址代理、程序代理等。\n\n"
            "【开启步骤】\n"
            "1. 点击右上角开关启动服务\n"
            "2. 等待状态变为「运行中」\n"
            "3. 默认监听 127.0.0.1:7890（可在下方修改）\n\n"
            "【为什么必须先检测线路】\n"
            "• 开启服务前，请确保已有至少一条可用线路\n"
            "• 线路延迟和稳定性差异很大，直接使用可能卡顿\n"
            "• 建议点击「立即检测」测试所有线路延迟\n"
            "• 开启「智能线路」后会自动选择最佳线路，无需手动切换"
        )
        return self._build_panel_card("代理服务", [
            self._build_proxy_state_card(),
            self._build_local_proxy_card(),
        ], help_btn=proxy_service_help_btn)

    def _build_line_service_panel(self):
        """线路服务大面板：标题「线路服务」+ 6 个子卡片（线路状态 / 线路列表 / 国家筛选 / 我的订阅 / 上游管理 / 智能线路）"""
        return self._build_panel_card("线路服务", [
            self._build_line_test_card(),
            self._build_line_list_card(),
            self._build_country_filter_card(),
            self._build_subscription_card(),
            self._build_backup_source_card(),
            self._build_smart_line_card(),
        ])

    def _build_proxy_state_card(self):
        """代理状态子卡片：左 状态点+状态文字 | 中 内核信息 | 右 开关"""
        card = QFrame()
        card.setObjectName("switch-row")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer = QHBoxLayout(card)
        outer.setContentsMargins(14, 8, 14, 8)
        outer.setSpacing(10)

        # 左侧：标题
        title_lbl = QLabel("代理状态")
        title_lbl.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        outer.addWidget(title_lbl)

        # 状态点 + 状态文字
        status_wrap = QHBoxLayout()
        status_wrap.setSpacing(8)
        self.svc_status_dot = QLabel("●")
        self.svc_status_dot.setStyleSheet("font-size: 14px; color: #FF6B80; background: transparent;")
        self.svc_status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.svc_status_dot.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        status_wrap.addWidget(self.svc_status_dot)
        self.svc_status_label = QLabel("代理未启动")
        self.svc_status_label.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {COLOR_TEXT}; background: transparent;")
        status_wrap.addWidget(self.svc_status_label)
        outer.addLayout(status_wrap)

        # 中间：内核信息（居中）
        kernel_wrap = QHBoxLayout()
        kernel_wrap.setSpacing(8)
        kernel_wrap.addStretch(1)
        self.svc_kernel_label = QLabel(f"内核: {self._get_quick_version() or '未安装'}")
        if self._get_quick_version():
            self.svc_kernel_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_GREEN};")
        else:
            self.svc_kernel_label.setStyleSheet(f"font-size: 8pt; color: #FF6B80; font-weight: bold;")
        kernel_wrap.addWidget(self.svc_kernel_label)

        self.svc_kernel_status = QLabel("")
        self.svc_kernel_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self._get_quick_version():
            self.svc_kernel_status.setText("✅ 代理内核已启用")
            self.svc_kernel_status.setStyleSheet(f"color: {COLOR_GREEN}; font-size: 7pt; font-weight: bold;")
        elif self._auto_download_kernel:
            self.svc_kernel_status.setText("⏳ 获取新版代理内核...")
            self.svc_kernel_status.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 7pt; font-weight: bold;")
        else:
            self.svc_kernel_status.setText("⚠ 代理内核缺失，点击修复")
            self.svc_kernel_status.setCursor(Qt.CursorShape.PointingHandCursor)
            self.svc_kernel_status.setStyleSheet(f"color: #FF6B80; font-size: 7pt; font-weight: bold;")
            self.svc_kernel_status.mousePressEvent = lambda e: self._on_nav_clicked(1)
        kernel_wrap.addWidget(self.svc_kernel_status)

        self.svc_kernel_progress = QProgressBar()
        self.svc_kernel_progress.setFixedHeight(12)
        self.svc_kernel_progress.setFixedWidth(120)
        self.svc_kernel_progress.setTextVisible(True)
        self.svc_kernel_progress.setFormat("%p%")
        self.svc_kernel_progress.setRange(0, 100)
        self.svc_kernel_progress.setValue(0)
        self.svc_kernel_progress.setStyleSheet(
            f"QProgressBar {{ background-color: #1a2a3a; border: 1px solid #2a3a5a; border-radius: 3px; "
            f"font-size: 6pt; color: {COLOR_ORANGE}; text-align: center; }}"
            f"QProgressBar::chunk {{ background-color: {COLOR_ORANGE}; border-radius: 2px; }}"
        )
        self.svc_kernel_progress.hide()
        kernel_wrap.addWidget(self.svc_kernel_progress)
        kernel_wrap.addStretch(1)
        outer.addLayout(kernel_wrap, stretch=1)

        # 右侧：开关
        self.switch_proxy = ToggleSwitch("代理服务", default=False)
        self.switch_proxy.setFixedHeight(24)
        self.switch_proxy.setFixedWidth(132)
        self.switch_proxy.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.switch_proxy.toggled.connect(self._on_proxy_switch_toggled)
        outer.addWidget(self.switch_proxy, alignment=Qt.AlignmentFlag.AlignVCenter)
        return card

    def _build_local_proxy_card(self):
        """本地代理子卡片：标题 + 帮助气泡（左） + 地址/端口 + 修改/复制（右，10px 间隔）"""
        card = QFrame()
        card.setObjectName("switch-row")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer = QHBoxLayout(card)
        outer.setContentsMargins(14, 8, 14, 8)
        outer.setSpacing(10)

        # 左侧：标题 + 帮助气泡
        title_wrap = QHBoxLayout()
        title_wrap.setSpacing(4)
        proxy_addr_label = QLabel("本地代理")
        proxy_addr_label.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        title_wrap.addWidget(proxy_addr_label)
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
        title_wrap.addWidget(self.proxy_help_btn)
        outer.addLayout(title_wrap)

        # 右侧：地址 + : + 端口 + 修改 + 复制（整体右对齐，按钮加宽加图标，10px 间隔）
        right_wrap = QHBoxLayout()
        right_wrap.setSpacing(10)
        right_wrap.addStretch(1)  # 推到右侧
        self.proxy_host_input = QLineEdit(PROXY_HOST)
        self.proxy_host_input.setFixedWidth(120)
        self.proxy_host_input.setReadOnly(True)
        self.proxy_host_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 4px; padding: 3px 8px; color: {COLOR_TEXT}; font-size: 9pt; font-family: Consolas; }}"
            f"QLineEdit[readOnly=\"true\"] {{ background-color: #0a0a0a; color: #888; }}"
        )
        right_wrap.addWidget(self.proxy_host_input)
        colon_label = QLabel(":")
        colon_label.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {COLOR_TEXT};")
        right_wrap.addWidget(colon_label)
        self.proxy_port_input = QLineEdit(str(PROXY_PORT))
        self.proxy_port_input.setFixedWidth(80)
        self.proxy_port_input.setReadOnly(True)
        self.proxy_port_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 4px; padding: 3px 8px; color: {COLOR_TEXT}; font-size: 9pt; font-family: Consolas; }}"
            f"QLineEdit[readOnly=\"true\"] {{ background-color: #0a0a0a; color: #888; }}"
        )
        right_wrap.addWidget(self.proxy_port_input)
        self._proxy_editing = False
        self.btn_edit_proxy = QPushButton("✏  修改")
        self.btn_edit_proxy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit_proxy.setFixedHeight(26)
        self.btn_edit_proxy.setMinimumWidth(88)
        self.btn_edit_proxy.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 4px 14px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        self.btn_edit_proxy.clicked.connect(self._on_proxy_edit_toggle)
        right_wrap.addWidget(self.btn_edit_proxy)
        self.btn_copy_proxy = QPushButton("📋  复制")
        self.btn_copy_proxy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_proxy.setFixedHeight(26)
        self.btn_copy_proxy.setMinimumWidth(88)
        self.btn_copy_proxy.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 4px 14px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        self.btn_copy_proxy.clicked.connect(self._on_copy_proxy_addr)
        right_wrap.addWidget(self.btn_copy_proxy)
        outer.addLayout(right_wrap, stretch=1)
        return card

    def _build_line_list_card(self):
        """线路列表子卡片（内置 4 条 + 所有启用的自定义订阅）

        使用 _rebuild_line_rows() 在订阅变更后重绘
        """
        card = QFrame()
        card.setObjectName("switch-row")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._line_list_layout = QVBoxLayout(card)
        self._line_list_layout.setContentsMargins(14, 8, 14, 8)
        self._line_list_layout.setSpacing(6)

        line_header = QHBoxLayout()
        line_title = QLabel("线路列表")
        line_title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        line_header.addWidget(line_title)
        line_header.addWidget(_make_help_btn(
            "可用代理线路列表",
            "线路列表说明",
            "【线路列表】\n"
            "显示所有可用的代理线路（4 条内置 + 你添加的订阅），每条线路可独立检测和使用。\n\n"
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
        self._line_list_layout.addLayout(line_header)

        # 存储所有线路行（内置 + 自定义）
        self.line_rows = {}
        self._line_rows_container = QFrame()
        self._line_rows_layout = QVBoxLayout(self._line_rows_container)
        self._line_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._line_rows_layout.setSpacing(2)
        self._line_list_layout.addWidget(self._line_rows_container)

        # 首次构建
        self._rebuild_line_rows()
        return card

    def _make_line_row(self, name, is_custom=False):
        """创建一个线路行 widget（不加入 layout，调用方负责 addWidget）"""
        row = QFrame()
        row.setObjectName("line-row")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rh = QHBoxLayout(row)
        rh.setContentsMargins(14, 8, 14, 8)
        rh.setSpacing(12)
        # 名称（自定义订阅前加图标区分）
        display_name = ("📋 " + name) if is_custom else name
        name_lbl = QLabel(display_name)
        name_lbl.setObjectName("suggestion")
        name_lbl.setFixedWidth(90 if is_custom else 50)
        name_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        rh.addWidget(name_lbl)
        # Batch 3: 健康度徽章
        health_badge = QLabel("无数据")
        health_badge.setObjectName("health-badge")
        health_badge.setStyleSheet("color: #888; font-size: 7pt; padding: 0 4px;")
        health_badge.setFixedWidth(150)
        health_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rh.addWidget(health_badge)
        # 状态
        status_lbl = QLabel("未检测")
        status_lbl.setObjectName("dim")
        status_lbl.setWordWrap(True)
        status_lbl.setStyleSheet("font-size: 9pt;")
        rh.addWidget(status_lbl, stretch=1)
        # 使用按钮
        use_btn = QPushButton("使用")
        use_btn.setObjectName("small-blue")
        use_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        use_btn.setFixedWidth(70)
        use_btn.setFixedHeight(24)
        use_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        use_btn.clicked.connect(lambda checked, n=name: self._on_use_line(n))
        rh.addWidget(use_btn)
        # 存储
        self.line_rows[name] = {
            "status": status_lbl, "use_btn": use_btn, "data": None, "row": row,
            "is_custom": is_custom, "health_badge": health_badge,
        }
        return row

    def _rebuild_line_rows(self):
        """重建所有线路行（清空 → 内置 4 条 + 启用的自定义订阅）"""
        if not hasattr(self, "_line_rows_layout"):
            return
        # 清空旧行
        while self._line_rows_layout.count():
            item = self._line_rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.line_rows = {}
        # 内置 4 条（严格竞速线路，不含 anytls2 默认节点——它仅作静默兜底）
        for name, _, _ in CONFIG_URLS:
            self._line_rows_layout.addWidget(self._make_line_row(name, is_custom=False))
        # 启用的自定义订阅
        try:
            mgr = get_subscription_manager()
            for sub in mgr.get_enabled():
                self._line_rows_layout.addWidget(self._make_line_row(sub.name, is_custom=True))
        except Exception as e:
            log.warning(f"重建线路行失败: {e}")
        # 拉伸项
        self._line_rows_layout.addStretch(1)
        # Batch 3: 刷新健康度徽章
        self._refresh_line_health_badges()

    def _build_country_filter_card(self):
        """国家筛选子卡片：选择需要代理的 IP 区域/国家，保存 config 时自动过滤节点
        （Batch 2）
        """
        card = QFrame()
        card.setObjectName("switch-row")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 8, 14, 8)
        outer.setSpacing(6)

        # 标题行
        title_row = QHBoxLayout()
        title = QLabel("🌍 国家筛选")
        title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        title_row.addWidget(title)
        title_row.addWidget(_make_help_btn(
            "国家/地区筛选",
            "国家筛选说明",
            "【国家筛选】\n"
            "选择你需要的代理出口国家/地区，保存 config 时会过滤掉不在白名单中的节点。\n"
            "适用于：\n"
            "• 只想用某些地区的节点（如只用日本/美国）\n"
            "• 机场节点太多，加载慢，按地区精简\n"
            "• 测试某地区连通性\n\n"
            "【原理】\n"
            "本软件内置 GeoIP 库（Country.mmdb），节点下载完成后会按节点 server 域名/IP 解析国家，\n"
            "不在白名单的节点会被剔除，proxy-groups 里对这些节点的引用也会一并清理。\n"
            "未选任何国家 = 不筛选 = 保留所有节点。\n\n"
            "【生效时机】\n"
            "下一次点击「使用」某条线路时，自动按当前白名单过滤。\n"
            "也可以点「重新下载」强制重下并应用。"
        ))
        title_row.addStretch()
        outer.addLayout(title_row)

        # 摘要 + 按钮行
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self._country_filter_summary = QLabel("当前: 全部 (未筛选)")
        self._country_filter_summary.setStyleSheet("color: #aaa; font-size: 8pt;")
        self._country_filter_summary.setWordWrap(True)
        action_row.addWidget(self._country_filter_summary, stretch=1)
        # 选择按钮
        select_btn = QPushButton("🌍 选择国家")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setFixedHeight(26)
        select_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 0 12px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        select_btn.clicked.connect(self._on_select_countries)
        action_row.addWidget(select_btn)
        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFixedHeight(26)
        clear_btn.setStyleSheet(
            f"QPushButton {{ background-color: #2a2a2a; color: {COLOR_TEXT}; "
            f"font-size: 8pt; border-radius: 4px; border: 1px solid {COLOR_BORDER}; padding: 0 12px; }}"
            f"QPushButton:hover {{ background-color: #3a3a3a; }}"
        )
        clear_btn.clicked.connect(self._on_clear_country_filter)
        action_row.addWidget(clear_btn)
        outer.addLayout(action_row)

        # 初始化摘要
        self._refresh_country_filter_summary()
        return card

    def _refresh_country_filter_summary(self):
        """刷新国家筛选摘要文字"""
        if not hasattr(self, "_country_filter_summary"):
            return
        try:
            wl = load_country_whitelist()
        except Exception:
            wl = []
        if not wl:
            self._country_filter_summary.setText("当前: 全部 (未筛选)")
            self._country_filter_summary.setStyleSheet("color: #aaa; font-size: 8pt;")
        else:
            codes = sorted(set(c.upper() for c in wl if c))
            chips = " ".join(f"{country_flag(c)} {COUNTRY_NAMES.get(c, c)}" for c in codes[:8])
            if len(codes) > 8:
                chips += f" …(+{len(codes) - 8})"
            self._country_filter_summary.setText(f"已选 {len(codes)} 个: {chips}")
            self._country_filter_summary.setStyleSheet(f"color: {COLOR_GREEN}; font-size: 8pt;")

    def _on_select_countries(self):
        """打开国家多选对话框"""
        try:
            current = load_country_whitelist()
        except Exception:
            current = []
        dlg = CountryFilterDialog(current, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_sel = dlg.get_selected()
            try:
                save_country_whitelist(new_sel)
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"保存国家白名单失败: {e}")
                return
            self._refresh_country_filter_summary()
            n = len(new_sel)
            if n == 0:
                QMessageBox.information(self, "已保存", "已清空国家筛选，下次保存 config 将保留所有节点。")
            else:
                QMessageBox.information(
                    self, "已保存",
                    f"已保存 {n} 个国家到白名单。\n下次点击「使用」线路时会自动按白名单过滤。\n"
                    f"如要立即生效，请重新点「使用」目标线路。"
                )

    def _on_clear_country_filter(self):
        """清空国家筛选"""
        try:
            current = load_country_whitelist()
        except Exception:
            current = []
        if not current:
            return
        try:
            save_country_whitelist([])
        except Exception as e:
            QMessageBox.critical(self, "清空失败", f"{e}")
            return
        self._refresh_country_filter_summary()

    def _build_subscription_card(self):
        """我的订阅子卡片：添加订阅表单 + 已有订阅列表"""
        card = QFrame()
        card.setObjectName("switch-row")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        sc = QVBoxLayout(card)
        sc.setContentsMargins(14, 8, 14, 14)
        sc.setSpacing(8)

        # 标题行
        head = QHBoxLayout()
        title = QLabel("📋 我的订阅")
        title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        head.addWidget(title)
        head.addWidget(_make_help_btn(
            "自定义代理订阅",
            "我的订阅说明",
            "【自定义订阅】\n"
            "把你自己的机场订阅链接贴进来，软件会下载并解析，\n"
            "这些订阅会和内置的 4 条线路一起出现在「线路列表」中，\n"
            "可以点「检测线路」一起测速、点「使用」切到这条线。\n\n"
            "【支持的格式】\n"
            "Clash YAML 格式订阅（绝大多数机场都支持）。\n"
            "订阅 URL 一般在你的机场「复制订阅链接」页面里找。\n\n"
            "【备注名】\n"
            "必填，例：「机场A」、「我的订阅」，会显示在线路列表里。"
        ))
        head.addStretch()
        sc.addLayout(head)

        # 添加表单
        form = QHBoxLayout()
        form.setSpacing(6)
        self.sub_name_edit = QLineEdit()
        self.sub_name_edit.setPlaceholderText("备注名 (必填)")
        self.sub_name_edit.setMaximumWidth(120)
        self.sub_name_edit.setStyleSheet("font-size: 8pt; padding: 3px;")
        form.addWidget(self.sub_name_edit)
        self.sub_url_edit = QLineEdit()
        self.sub_url_edit.setPlaceholderText("订阅 URL (https://...)")
        self.sub_url_edit.setStyleSheet("font-size: 8pt; padding: 3px;")
        form.addWidget(self.sub_url_edit, stretch=1)
        add_btn = QPushButton("➕ 添加")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(26)
        add_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_GREEN}; color: #fff; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 0 10px; }}"
            f"QPushButton:hover {{ background-color: #2E7D32; }}"
            f"QPushButton:disabled {{ background-color: #333; color: #666; }}"
        )
        add_btn.clicked.connect(self._on_add_subscription)
        form.addWidget(add_btn)
        sc.addLayout(form)

        # 已有订阅列表
        self._sub_list_container = QFrame()
        self._sub_list_layout = QVBoxLayout(self._sub_list_container)
        self._sub_list_layout.setContentsMargins(0, 4, 0, 0)
        self._sub_list_layout.setSpacing(3)
        sc.addWidget(self._sub_list_container)

        self._rebuild_subscription_list()
        return card

    def _rebuild_subscription_list(self):
        """重建订阅管理列表"""
        if not hasattr(self, "_sub_list_layout"):
            return
        while self._sub_list_layout.count():
            item = self._sub_list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        mgr = get_subscription_manager()
        subs = mgr.get_all()
        if not subs:
            empty = QLabel("（暂无订阅，粘贴 Clash 订阅 URL 即可添加）")
            empty.setStyleSheet("color: #666; font-size: 8pt; font-style: italic; padding: 4px;")
            self._sub_list_layout.addWidget(empty)
        else:
            for sub in subs:
                self._sub_list_layout.addWidget(self._make_sub_row(sub))
        self._sub_list_layout.addStretch(1)

    def _make_sub_row(self, sub: Subscription):
        """单条订阅管理行：[启用] 名称 节点数 上次状态 [删除]"""
        row = QFrame()
        row.setObjectName("sub-row")
        row.setStyleSheet("#sub-row { background-color: #131820; border: 1px solid #1f2a38; border-radius: 3px; }")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rh = QHBoxLayout(row)
        rh.setContentsMargins(10, 5, 10, 5)
        rh.setSpacing(8)

        # 启用 checkbox
        chk = QCheckBox()
        chk.setChecked(sub.enabled)
        chk.setCursor(Qt.CursorShape.PointingHandCursor)
        chk.toggled.connect(lambda checked, n=sub.name: self._on_toggle_subscription(n, checked))
        rh.addWidget(chk)

        # 名称
        name_lbl = QLabel(sub.name)
        name_lbl.setStyleSheet("font-size: 9pt; font-weight: bold;")
        name_lbl.setFixedWidth(120)
        rh.addWidget(name_lbl)

        # 节点数 + 上次状态
        info = f"📡 {sub.node_count} 节点" if sub.node_count else "📡 ? 节点"
        if sub.last_update:
            info += f"  ·  {sub.last_update}"
        if sub.last_status == "下载成功":
            color = COLOR_GREEN
        elif sub.last_status == "下载失败":
            color = "#FF6B80"
        else:
            color = "#888"
        status_lbl = QLabel(info)
        status_lbl.setStyleSheet(f"color: {color}; font-size: 8pt;")
        status_lbl.setWordWrap(True)
        rh.addWidget(status_lbl, stretch=1)

        # 删除按钮
        del_btn = QPushButton("🗑")
        del_btn.setToolTip("删除此订阅")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFixedSize(26, 22)
        del_btn.setStyleSheet(
            "QPushButton { background-color: #2a1a1a; color: #FF6B80; "
            "border: 1px solid #5a2a2a; border-radius: 3px; font-size: 11pt; }"
            "QPushButton:hover { background-color: #5a2020; }"
        )
        del_btn.clicked.connect(lambda checked, n=sub.name: self._on_remove_subscription(n))
        rh.addWidget(del_btn)
        return row

    def _on_add_subscription(self):
        """添加订阅按钮回调"""
        name = self.sub_name_edit.text().strip()
        url = self.sub_url_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请填写备注名")
            return
        if not url:
            QMessageBox.warning(self, "提示", "请填写订阅 URL")
            return
        try:
            get_subscription_manager().add(name, url)
        except ValueError as e:
            QMessageBox.warning(self, "添加失败", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "添加失败", f"未知错误: {e}")
            return
        self.sub_name_edit.clear()
        self.sub_url_edit.clear()
        self._rebuild_subscription_list()
        self._rebuild_line_rows()
        QMessageBox.information(self, "已添加", f"订阅「{name}」已添加。下次点「检测线路」时一并下载测试。")

    def _on_remove_subscription(self, name: str):
        """删除订阅按钮回调"""
        ret = QMessageBox.question(
            self, "确认删除",
            f"确定要删除订阅「{name}」吗？\n该订阅会从线路列表中移除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        mgr = get_subscription_manager()
        mgr.remove(name)
        self._rebuild_subscription_list()
        self._rebuild_line_rows()

    def _on_toggle_subscription(self, name: str, enabled: bool):
        """启用/禁用订阅"""
        get_subscription_manager().toggle(name, enabled)
        self._rebuild_line_rows()

    def _build_line_test_card(self):
        """线路状态子卡片：延迟 | 线路 | 进度 | 检测按钮（内核信息已迁移到代理状态卡）"""
        card = QFrame()
        card.setObjectName("switch-row")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer = QHBoxLayout(card)
        outer.setContentsMargins(14, 8, 14, 8)
        outer.setSpacing(10)

        # 标题
        title_lbl = QLabel("线路状态")
        title_lbl.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        outer.addWidget(title_lbl)

        # 信息条：延迟 | 线路 | 进度
        info_bar = QFrame()
        info_bar.setObjectName("info-bar")
        info_bar.setStyleSheet(f"background-color: #111; border: 1px solid #1a1a1a; border-radius: 4px;")
        info_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ib = QHBoxLayout(info_bar)
        ib.setContentsMargins(12, 4, 12, 4)
        ib.setSpacing(10)

        self.svc_latency_label = QLabel("延迟: --")
        self.svc_latency_label.setObjectName("latency")
        self.svc_latency_label.setStyleSheet("font-size: 8pt;")
        ib.addWidget(self.svc_latency_label)

        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #333; font-size: 8pt;")
        ib.addWidget(sep1)

        self.svc_line_label = QLabel("线路: --")
        self.svc_line_label.setObjectName("dim")
        self.svc_line_label.setStyleSheet("font-size: 8pt;")
        ib.addWidget(self.svc_line_label)

        ib.addStretch()

        self.line_progress = CopyableLabel("", max_height=18)
        ib.addWidget(self.line_progress)

        # 必须 addWidget(info_bar) 而不是 addLayout(ib)：
        # info_bar 是 QFrame，必须有 QWidget parent 才能被 Qt 管理。
        # 之前用 addLayout(ib) 会让 info_bar 成为 orphan，被 PyQt GC 销毁，
        # 导致其下的 svc_line_label / svc_latency_label / line_progress C++ 对象被删除，
        # 后续 _update_status() 访问 self.svc_line_label 时抛 RuntimeError。
        outer.addWidget(info_bar, stretch=1)

        # Batch 3: 健康度详情按钮
        self.btn_health_detail = QPushButton("📊 健康度")
        self.btn_health_detail.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_health_detail.setFixedSize(80, 26)
        self.btn_health_detail.setStyleSheet(
            f"QPushButton {{ background-color: #2a2a2a; color: {COLOR_TEXT}; "
            f"font-size: 8pt; border-radius: 4px; border: 1px solid {COLOR_BORDER}; }}"
            f"QPushButton:hover {{ background-color: #3a3a3a; border-color: {COLOR_GREEN}; }}"
        )
        self.btn_health_detail.setToolTip("查看所有线路近 30 天健康度历史")
        self.btn_health_detail.clicked.connect(self._on_open_health_detail)
        outer.addWidget(self.btn_health_detail, alignment=Qt.AlignmentFlag.AlignVCenter)

        # 检测按钮
        self.btn_test = QPushButton("🔍 检测线路")
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.setFixedSize(90, 26)
        self.btn_test.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
            f"QPushButton:disabled {{ background-color: #333; color: #666; }}"
        )
        self.btn_test.clicked.connect(self._on_test_btn_clicked)
        outer.addWidget(self.btn_test, alignment=Qt.AlignmentFlag.AlignVCenter)
        return card

    def _on_open_health_detail(self):
        """打开健康度详情对话框（30 天历史）"""
        dlg = HealthDetailDialog(self)
        dlg.exec()

    def _refresh_line_health_badges(self):
        """刷新所有线路行的健康度徽章（启动/打开软件时调用一次）"""
        try:
            summary = get_health_db().get_health_summary()
        except Exception:
            summary = {}
        for name, info in self.line_rows.items():
            badge = info.get("health_badge")
            if badge is None:
                continue
            data = summary.get(name)
            if data is None:
                badge.setText("无数据")
                badge.setStyleSheet("color: #888; font-size: 7pt; padding: 0 4px;")
                badge.setToolTip("还没有检测记录")
            else:
                rate = data.get("rate", 0)
                avg = data.get("avg_latency")
                samples = data.get("samples", 0)
                txt, color = get_health_label(rate)
                bar = format_health_bar(rate, width=6).split(" ")[0]  # 仅条形图部分
                badge.setText(f"{bar} {txt}")
                badge.setStyleSheet(f"color: {color}; font-size: 7pt; padding: 0 4px; font-weight: bold;")
                tip = f"近 7 天 {samples} 次检测，{int(rate*100)}% 成功"
                if avg is not None:
                    tip += f"，平均延迟 {avg:.2f}s"
                badge.setToolTip(tip)

    def _build_backup_source_card(self):
        """上游管理子卡片：管理备选上游仓库（Batch 4）
        当主仓库 4 条线路全部下载失败时，自动降级到备选上游仓库。
        """
        card = QFrame()
        card.setObjectName("switch-row")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 8, 14, 8)
        outer.setSpacing(6)

        # 标题行
        title_row = QHBoxLayout()
        title = QLabel("🔄 上游管理")
        title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        title_row.addWidget(title)
        title_row.addWidget(_make_help_btn(
            "备选上游仓库",
            "上游管理说明",
            "【上游管理】\n"
            "当主仓库（内置 4 条线路）满足以下条件之一时，自动降级到备选上游仓库：\n"
            "  ① 全部下载失败 ② 成功条数 < 2（基本没法用）\n\n"
            "【内置默认源】\n"
            "首次启动会自动写入 2 个公开备选源（mfuu/v2ray + ripaojiedian/freenode），\n"
            "用户可自由启用/禁用/删除/添加新的。\n\n"
            "【多 URL 兜底】\n"
            "每个备选源可配 1 个主 URL + 多个备用 URL。\n"
            "下载时按顺序尝试，主 URL 失败会自动试下一个，\n"
            "大幅提升不同网络环境下的可达率。\n\n"
            "【适用场景】\n"
            "• 主仓库被墙或服务器宕机\n"
            "• 主仓库节点大部分失效（< 2 条成功）\n"
            "• 需要更多线路来源\n\n"
            "【注意】\n"
            "备选仓库 URL 必须是 Clash YAML 格式的订阅地址。"
        ))
        title_row.addStretch()
        outer.addLayout(title_row)

        # 添加行：备注名 + URL + 添加按钮
        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        self._backup_name_input = QLineEdit()
        self._backup_name_input.setPlaceholderText("备注名")
        self._backup_name_input.setFixedHeight(26)
        self._backup_name_input.setMaxLength(30)
        self._backup_name_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; color: {COLOR_TEXT}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 0 8px; font-size: 8pt; }}"
            f"QLineEdit:focus {{ border-color: {COLOR_GREEN}; }}"
        )
        add_row.addWidget(self._backup_name_input, 1)

        self._backup_url_input = QLineEdit()
        self._backup_url_input.setPlaceholderText("https:// 备选仓库订阅 URL (Clash YAML)")
        self._backup_url_input.setFixedHeight(26)
        self._backup_url_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; color: {COLOR_TEXT}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 4px; padding: 0 8px; font-size: 8pt; }}"
            f"QLineEdit:focus {{ border-color: {COLOR_GREEN}; }}"
        )
        add_row.addWidget(self._backup_url_input, 3)

        add_btn = QPushButton("➕ 添加")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(26)
        add_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_GREEN}; color: #fff; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 0 12px; }}"
            f"QPushButton:hover {{ background-color: #2E7D32; }}"
        )
        add_btn.clicked.connect(self._on_add_backup_source)
        add_row.addWidget(add_btn)
        outer.addLayout(add_row)

        # 备选仓库列表
        self._backup_list_layout = QVBoxLayout()
        self._backup_list_layout.setSpacing(2)
        outer.addLayout(self._backup_list_layout)

        # 初始化列表
        self._rebuild_backup_source_list()
        return card

    def _rebuild_backup_source_list(self):
        """重建备选仓库列表"""
        if not hasattr(self, "_backup_list_layout"):
            return
        # 清空
        while self._backup_list_layout.count():
            item = self._backup_list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        # 重新构建
        sources = load_backup_sources()
        if not sources:
            empty = QLabel("（暂无备选上游仓库。主仓库全部失败时将无线路可用。）")
            empty.setStyleSheet("color: #555; font-size: 8pt; padding: 4px 0;")
            empty.setWordWrap(True)
            self._backup_list_layout.addWidget(empty)
            return
        # 顶部统计
        enabled_count = sum(1 for s in sources if s.enabled)
        summary = QLabel(
            f"共 {len(sources)} 个备选源，启用 {enabled_count} 个"
            f"（主仓库失败或 < 2 条成功时自动降级）"
        )
        summary.setStyleSheet("color: #888; font-size: 7pt; padding: 2px 0;")
        self._backup_list_layout.addWidget(summary)
        for src in sources:
            self._backup_list_layout.addWidget(self._make_backup_source_row(src))

    def _make_backup_source_row(self, src: BackupSource) -> QFrame:
        """创建单个备选仓库行"""
        row = QFrame()
        row.setObjectName("line-row")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rh = QHBoxLayout(row)
        rh.setContentsMargins(8, 4, 8, 4)
        rh.setSpacing(8)

        # 启用/禁用 checkbox
        chk = QCheckBox()
        chk.setChecked(src.enabled)
        chk.setCursor(Qt.CursorShape.PointingHandCursor)
        chk.setFixedSize(18, 18)
        chk.setStyleSheet(
            f"QCheckBox {{ spacing: 0; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; }}"
        )
        chk.toggled.connect(lambda checked, n=src.name: self._on_toggle_backup_source(n, checked))
        rh.addWidget(chk)

        # 名称 + 状态
        info_text = f"📦 {src.name}"
        if src.last_status == "下载成功":
            info_text += f"  ✅ {src.last_update}"
        elif src.last_status == "下载失败":
            err_short = src.last_error[:30] if src.last_error else ""
            info_text += f"  ❌ {err_short}"
        else:
            info_text += f"  ⬜ {src.last_status}"
        name_lbl = QLabel(info_text)
        name_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        name_lbl.setWordWrap(True)
        rh.addWidget(name_lbl, stretch=1)

        # URL（截断显示）
        url_short = src.url if len(src.url) <= 50 else src.url[:47] + "..."
        extra = len(src.urls or [])
        if extra > 0:
            url_short = f"{url_short}  +{extra}备用"
        url_lbl = QLabel(url_short)
        url_lbl.setStyleSheet("color: #666; font-size: 7pt;")
        url_lbl.setWordWrap(False)
        tooltip = src.url
        if extra > 0:
            tooltip += "\n\n备用 URL：\n" + "\n".join(f"• {u}" for u in (src.urls or []))
        url_lbl.setToolTip(tooltip)
        rh.addWidget(url_lbl, stretch=2)

        # 删除按钮
        del_btn = QPushButton("✕")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFixedSize(22, 22)
        del_btn.setStyleSheet(
            f"QPushButton {{ background-color: #2a1a1a; color: #FF6B80; "
            f"font-size: 9pt; border-radius: 3px; border: 1px solid #3a1a1a; }}"
            f"QPushButton:hover {{ background-color: #5a2020; }}"
        )
        del_btn.clicked.connect(lambda checked, n=src.name: self._on_remove_backup_source(n))
        rh.addWidget(del_btn)
        return row

    def _on_add_backup_source(self):
        """添加备选上游仓库"""
        name = self._backup_name_input.text().strip()
        url = self._backup_url_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入备注名")
            return
        if not url:
            QMessageBox.warning(self, "提示", "请输入订阅 URL")
            return
        try:
            add_backup_source(name, url)
        except ValueError as e:
            QMessageBox.warning(self, "添加失败", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "添加失败", f"{type(e).__name__}: {e}")
            return
        # 清空输入框
        self._backup_name_input.clear()
        self._backup_url_input.clear()
        # 刷新列表
        self._rebuild_backup_source_list()
        # 刷新线路行（备选仓库不会出现在线路列表里，只在降级时使用）
        QMessageBox.information(
            self, "已添加",
            f"备选仓库「{name}」已添加。\n"
            f"当主仓库 4 条线路全部下载失败时，会自动降级到该仓库。"
        )

    def _on_remove_backup_source(self, name: str):
        """删除备选上游仓库"""
        ret = QMessageBox.question(
            self, "确认删除",
            f"确定要删除备选仓库「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            remove_backup_source(name)
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"{e}")
            return
        self._rebuild_backup_source_list()

    def _on_toggle_backup_source(self, name: str, enabled: bool):
        """启用/禁用备选上游仓库"""
        try:
            toggle_backup_source(name, enabled)
        except Exception as e:
            log.warning(f"切换备选仓库状态失败: {e}")

    def _build_smart_line_card(self):
        """智能线路子卡片：分组小标题 + 3 个开关行（断线自动切换 / 定时切换最快线路 / 检测线路前更新配置）"""
        card = QFrame()
        card.setObjectName("switch-row")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        sm = QVBoxLayout(card)
        sm.setContentsMargins(14, 8, 14, 14)
        sm.setSpacing(10)

        # 分组小标题（带帮助气泡），用于标识智能线路分组
        sm_title_row = QHBoxLayout()
        sm_title_row.setSpacing(4)
        smart_title = QLabel("智能线路")
        smart_title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
        sm_title_row.addWidget(smart_title)
        sm_title_row.addWidget(_make_help_btn(
            "智能线路管理",
            "智能线路说明",
            "【断线自动切换】\n"
            "按设定间隔检测代理连通性，发现断线时自动切换到最快线路。\n"
            "可自定义检测间隔时间，默认10秒。\n\n"
            "【定时切换最快线路】\n"
            "按设定间隔检测所有线路延迟，自动切换到最快线路。\n"
            "适合长时间使用时自动优化线路质量。\n\n"
            "两个功能独立控制，可按需开启，也可同时开启互补。\n"
            "同时开启时：断线时立即切换最快线路，定时检测持续优化。\n\n"
            "【检测线路前更新配置】\n"
            "控制检测线路时是否先更新线路配置。\n"
            "每次：每次都更新；每天：每天更新一次；每周：每周更新一次；每月：每月更新一次。\n\n"
            "【失败重测】\n"
            "当所有线路检测失败时，程序会自动更新配置并重新检测一次。"
        ))
        sm_title_row.addStretch()
        sm.addLayout(sm_title_row)

        # 子行1：断线自动切换
        sm.addWidget(self._build_switch_subrow(
            title="🔄 断线自动切换",
            desc="按间隔检测连通性，断线时自动切换到最快线路",
            switch_attr="switch_realtime_reconnect",
            spin_attr="realtime_spin",
            status_attr="realtime_status",
            spin_min=5, spin_max=120, spin_default=self.settings.get("realtime_interval", 10), spin_suffix=" 秒",
            switch_default=self.settings.get("realtime_reconnect", False),
            spin_handler="_on_realtime_interval_changed",
            switch_handler="_on_realtime_reconnect_toggled"
        ))
        # 子行2：定时切换最快线路
        sm.addWidget(self._build_switch_subrow(
            title="⚡ 定时切换最快线路",
            desc="按间隔检测所有线路延迟，自动切换到最快线路",
            switch_attr="switch_auto_line",
            spin_attr="interval_spin",
            status_attr="auto_line_status",
            spin_min=5, spin_max=120, spin_default=self.settings.get("auto_line_interval", 30), spin_suffix=" 分钟",
            switch_default=self.settings.get("auto_line_switch", False),
            spin_handler="_on_interval_changed",
            switch_handler="_on_auto_line_switch_toggled"
        ))
        # 子行3：检测线路前更新配置（特殊：包含频率下拉）
        sm.addWidget(self._build_update_freq_subrow())
        return card

    def _build_switch_subrow(self, title, desc, switch_attr, spin_attr, status_attr,
                              spin_min, spin_max, spin_default, spin_suffix,
                              switch_default, spin_handler, switch_handler):
        """通用的开关子行：标题 + 描述 + 间隔输入 + 状态 + 开关"""
        row = QFrame()
        row.setObjectName("switch-row")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)

        info = QVBoxLayout()
        info.setSpacing(1)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        info.addWidget(title_lbl)
        desc_lbl = QLabel(desc)
        desc_lbl.setObjectName("dim")
        desc_lbl.setStyleSheet("font-size: 8pt;")
        info.addWidget(desc_lbl)
        layout.addLayout(info, stretch=1)

        spin_wrap = QHBoxLayout()
        spin_wrap.setSpacing(6)
        spin_lbl = QLabel("间隔:")
        spin_lbl.setObjectName("dim")
        spin_lbl.setStyleSheet("font-size: 9pt;")
        spin_wrap.addWidget(spin_lbl)
        spin = QSpinBox()
        spin.setRange(spin_min, spin_max)
        spin.setValue(spin_default)
        spin.setSuffix(spin_suffix)
        spin.setFixedWidth(90)
        spin.valueChanged.connect(getattr(self, spin_handler))
        spin_wrap.addWidget(spin)
        status_lbl = QLabel("")
        status_lbl.setObjectName("dim")
        status_lbl.setStyleSheet("font-size: 8pt;")
        spin_wrap.addWidget(status_lbl)
        layout.addLayout(spin_wrap)
        setattr(self, spin_attr, spin)
        setattr(self, status_attr, status_lbl)

        switch = ToggleSwitch("", default=switch_default)
        switch.setFixedHeight(24)
        switch.setFixedWidth(72)
        switch.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        switch.toggled.connect(getattr(self, switch_handler))
        layout.addWidget(switch, alignment=Qt.AlignmentFlag.AlignVCenter)
        setattr(self, switch_attr, switch)
        return row

    def _build_update_freq_subrow(self):
        """检测线路前更新配置子行（包含频率下拉）"""
        row = QFrame()
        row.setObjectName("switch-row")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)

        info = QVBoxLayout()
        info.setSpacing(1)
        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        title_lbl = QLabel("📥 检测线路前更新配置")
        title_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        title_row.addWidget(title_lbl)
        info.addLayout(title_row)
        desc_lbl = QLabel("开启后按设定频率自动更新线路配置")
        desc_lbl.setObjectName("dim")
        desc_lbl.setStyleSheet("font-size: 8pt;")
        info.addWidget(desc_lbl)
        layout.addLayout(info, stretch=1)

        # 频率下拉
        self.update_config_freq_combo = UpComboBox()
        self.update_config_freq_combo.setFixedHeight(24)
        self.update_config_freq_combo.setFixedWidth(100)
        for display, value in [("每次", "always"), ("每天", "daily"), ("每周", "weekly"), ("每月", "monthly")]:
            self.update_config_freq_combo.addItem(display, value)
        saved_freq = self.settings.get("update_config_freq", "always")
        for i in range(self.update_config_freq_combo.count()):
            if self.update_config_freq_combo.itemData(i) == saved_freq:
                self.update_config_freq_combo.setCurrentIndex(i)
                break
        self.update_config_freq_combo.currentIndexChanged.connect(self._on_update_config_freq_changed)
        layout.addWidget(self.update_config_freq_combo)

        self.switch_always_update_config = ToggleSwitch("", default=self.settings.get("always_update_config", True))
        self.switch_always_update_config.setFixedHeight(24)
        self.switch_always_update_config.setFixedWidth(72)
        self.switch_always_update_config.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.switch_always_update_config.toggled.connect(self._on_always_update_config_toggled)
        layout.addWidget(self.switch_always_update_config, alignment=Qt.AlignmentFlag.AlignVCenter)
        return row

    def _build_browser_card(self):
        """浏览器设置卡片"""
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        bc = QVBoxLayout(card)
        bc.setContentsMargins(20, 14, 20, 14)
        bc.setSpacing(8)

        bc_title_row = QHBoxLayout()
        bc_title_row.setSpacing(4)
        browser_title = QLabel("浏览器设置")
        browser_title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT};")
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

        # 自动打开浏览器行
        auto_browser_row = QFrame()
        auto_browser_row.setObjectName("switch-row")
        auto_browser_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        abr = QHBoxLayout(auto_browser_row)
        abr.setContentsMargins(14, 8, 14, 8)
        auto_browser_lbl = QLabel("🌐 检测线路后打开浏览器")
        auto_browser_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        abr.addWidget(auto_browser_lbl, stretch=1)
        self.switch_auto_browser = ToggleSwitch("", default=self.settings.get("auto_open_browser", True))
        self.switch_auto_browser.setFixedHeight(24)
        self.switch_auto_browser.setFixedWidth(72)
        self.switch_auto_browser.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.switch_auto_browser.toggled.connect(self._on_auto_open_browser_toggled)
        abr.addWidget(self.switch_auto_browser, alignment=Qt.AlignmentFlag.AlignVCenter)
        bc.addWidget(auto_browser_row)

        # 浏览器模式：系统/自定义
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

        # 系统浏览器行
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

        # 自定义浏览器行
        custom_row = QHBoxLayout()
        custom_row.setSpacing(6)
        self.custom_browser_input = QLineEdit(self.settings.get("browser_path", ""))
        self.custom_browser_input.setPlaceholderText("输入浏览器exe路径...")
        self.custom_browser_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BORDER}; "
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
        return card

    def _build_proxy_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)  # 大面板间高度间隔统一 10px

        # ========================================================
        # 代理方式区域：1 个大卡片（标题"代理方式"）+ 4 个独立子小卡片
        # 设计语言统一：每个子卡片 = info+开关行 + 内容行 + 提示
        # ========================================================
        proxy_mode_card = QFrame()
        proxy_mode_card.setObjectName("card")
        pmc = QVBoxLayout(proxy_mode_card)
        pmc.setContentsMargins(20, 14, 20, 14)
        pmc.setSpacing(10)

        # 大卡片标题行：标题 + 问号气泡 + stretch + 重启生效按钮
        pm_title_row = QHBoxLayout()
        pm_title_row.setSpacing(4)
        pm_title_row.addWidget(QLabel("代理方式"))
        pm_title_row.itemAt(0).widget().setObjectName("accent")
        pm_title_row.itemAt(0).widget().setStyleSheet("font-size: 9pt; font-weight: bold;")
        pm_title_row.addWidget(_make_help_btn(
            "代理方式说明",
            "代理方式使用指南",
            "【代理方式】\n"
            "提供四种代理模式，可同时开启多个：\n\n"
            "• 系统代理 — 全局流量走代理，优先级最高\n"
            "• 浏览器代理 — 仅指定浏览器走代理\n"
            "• 地址代理 — 仅指定网址/IP走代理\n"
            "• 程序代理 — 仅指定程序走代理\n\n"
            "每种模式均支持「所有指定」和「单选指定」两种范围。\n"
            "修改设置后需点击「重启生效」按钮应用。"
        ))
        pm_title_row.addStretch()
        self.restart_apply_btn = QPushButton("🔄 重启生效")
        self.restart_apply_btn.setObjectName("small-blue-solid")
        self.restart_apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restart_apply_btn.setFixedSize(90, 28)
        self.restart_apply_btn.clicked.connect(self._on_restart_apply)
        pm_title_row.addWidget(self.restart_apply_btn)
        pmc.addLayout(pm_title_row)

        # ========== 0. TUN 模式 子卡片（最顶部，独立开关） ==========
        tun_row = QFrame()
        tun_row.setObjectName("switch-row")
        tr = QVBoxLayout(tun_row)
        tr.setContentsMargins(14, 8, 14, 8)
        tr.setSpacing(6)

        tr_title = QHBoxLayout()
        tr_title.setSpacing(4)
        tr_title.addWidget(QLabel("🛡️ TUN 模式"))
        tr_title.itemAt(0).widget().setStyleSheet("font-size: 8pt; font-weight: bold;")
        tr_title.addWidget(_make_help_btn(
            "TUN 模式设置",
            "TUN 模式说明",
            "【TUN 模式】\n"
            "通过虚拟网卡接管全部网络流量（含不遵守系统代理的 AI 软件、游戏等）。\n"
            "开启后系统代理、浏览器代理等设置将被忽略。\n\n"
            "【TUN 栈】\n"
            "gvisor：用户态网络栈，免驱动，兼容性好（推荐）\n"
            "system：系统协议栈，性能更高，需要 wintun.dll\n\n"
            "【管理员权限】\n"
            "TUN 模式需要管理员权限运行，否则无法创建虚拟网卡。\n\n"
            "修改后需要重启代理服务才能生效。"
        ))
        tr_title.addStretch()
        self.switch_tun = ToggleSwitch("", default=self.settings.get("tun_enabled", False))
        self.switch_tun.setFixedHeight(22)
        self.switch_tun.setFixedWidth(72)
        self.switch_tun.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.switch_tun.toggled.connect(self._on_tun_toggled)
        tr_title.addWidget(self.switch_tun, alignment=Qt.AlignmentFlag.AlignVCenter)
        tr.addLayout(tr_title)

        # TUN 栈选择行
        tun_stack_inner = QHBoxLayout()
        tun_stack_inner.setSpacing(8)
        tun_stack_lbl = QLabel("TUN 栈:")
        tun_stack_lbl.setStyleSheet("font-size: 8pt; color: #999999;")
        tun_stack_inner.addWidget(tun_stack_lbl)
        self.tun_stack_group = []
        self.tun_gvisor_rb = RadioButton("gvisor（免驱动）", default=self.settings.get("tun_stack", "gvisor") == "gvisor")
        self.tun_stack_group.append(self.tun_gvisor_rb)
        tun_stack_inner.addWidget(self.tun_gvisor_rb)
        self.tun_system_rb = RadioButton("system（需wintun）", default=self.settings.get("tun_stack", "gvisor") == "system")
        self.tun_stack_group.append(self.tun_system_rb)
        tun_stack_inner.addWidget(self.tun_system_rb)
        self.tun_gvisor_rb.toggled.connect(lambda checked: self._on_tun_stack_toggled("gvisor", checked))
        self.tun_system_rb.toggled.connect(lambda checked: self._on_tun_stack_toggled("system", checked))
        tr.addLayout(tun_stack_inner)

        # TUN 代理范围（3 选 1）：全部代理 / 绕过境内 / 仅指定
        tun_range_row = QHBoxLayout()
        tun_range_row.setSpacing(8)
        tun_range_label = QLabel("代理范围：")
        tun_range_label.setStyleSheet("font-size: 9pt;")
        tun_range_row.addWidget(tun_range_label)
        self.tun_range_group = []
        default_tun_range = self.settings.get("tun_proxy_mode", "all")
        self.tun_range_all_rb = RadioButton("全部代理", default=default_tun_range == "all")
        self.tun_range_group.append(self.tun_range_all_rb)
        tun_range_row.addWidget(self.tun_range_all_rb)
        self.tun_range_foreign_rb = RadioButton("绕过境内（仅代理境外）", default=default_tun_range == "foreign")
        self.tun_range_group.append(self.tun_range_foreign_rb)
        tun_range_row.addWidget(self.tun_range_foreign_rb)
        self.tun_range_specified_rb = RadioButton("仅指定（白名单）", default=default_tun_range == "specified")
        self.tun_range_group.append(self.tun_range_specified_rb)
        tun_range_row.addWidget(self.tun_range_specified_rb)
        tun_range_row.addStretch(1)
        self.tun_range_all_rb.toggled.connect(lambda c: self._on_tun_proxy_mode_toggled("all", c))
        self.tun_range_foreign_rb.toggled.connect(lambda c: self._on_tun_proxy_mode_toggled("foreign", c))
        self.tun_range_specified_rb.toggled.connect(lambda c: self._on_tun_proxy_mode_toggled("specified", c))
        tr.addLayout(tun_range_row)

        # 管理员权限提示
        self._is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        self.tun_admin_hint = QLabel()
        if not self._is_admin:
            self.tun_admin_hint.setText("⚠ TUN 模式需要管理员权限，请以管理员身份运行本程序")
            self.tun_admin_hint.setStyleSheet(f"font-size: 8pt; color: {COLOR_RED_LIGHT};")
        else:
            self.tun_admin_hint.setText("✓ 已获得管理员权限")
            self.tun_admin_hint.setStyleSheet(f"font-size: 8pt; color: {COLOR_GREEN};")
        self.tun_admin_hint.setVisible(self.settings.get("tun_enabled", False))
        tr.addWidget(self.tun_admin_hint)

        self.tun_restart_hint = QLabel("⚠ 修改后需重启服务生效")
        self.tun_restart_hint.setObjectName("restart-hint")
        self.tun_restart_hint.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 8pt;")
        self.tun_restart_hint.setVisible(False)
        tr.addWidget(self.tun_restart_hint)

        pmc.addWidget(tun_row)

        # ========== 0.5 高级设置 子卡片（TLS指纹 + 域名嗅探） ==========
        adv_row = QFrame()
        adv_row.setObjectName("switch-row")
        ar = QVBoxLayout(adv_row)
        ar.setContentsMargins(14, 8, 14, 8)
        ar.setSpacing(6)

        ar_title = QHBoxLayout()
        ar_title.setSpacing(4)
        ar_title.addWidget(QLabel("🛡️ 高级设置"))
        ar_title.itemAt(0).widget().setStyleSheet("font-size: 8pt; font-weight: bold;")
        ar_title.addWidget(_make_help_btn(
            "高级设置",
            "高级设置说明",
            "【TLS 指纹伪装】\n"
            "将代理连接的 TLS 指纹伪装为常见浏览器特征，防止流量被识别为代理。\n"
            "• Chrome：伪装为 Chrome 浏览器（推荐）\n"
            "• Firefox：伪装为 Firefox 浏览器\n"
            "• Safari：伪装为 Safari 浏览器\n"
            "• 随机：每次随机选择\n\n"
            "【域名嗅探】\n"
            "从 IP 流量中还原出真实域名，让代理规则基于域名而非 IP 匹配，更精准。\n"
            "适用于 TUN 模式或部分不携带域名信息的流量。\n\n"
            "修改后需要重启代理服务才能生效。"
        ))
        ar_title.addStretch()
        ar.addLayout(ar_title)

        # TLS 指纹选择行
        fp_inner = QHBoxLayout()
        fp_inner.setSpacing(8)
        fp_lbl = QLabel("TLS 指纹:")
        fp_lbl.setStyleSheet("font-size: 8pt; color: #999999;")
        fp_inner.addWidget(fp_lbl)
        self.tls_fingerprint_combo = QComboBox()
        self.tls_fingerprint_combo.addItem("不伪装", "none")
        self.tls_fingerprint_combo.addItem("Chrome", "chrome")
        self.tls_fingerprint_combo.addItem("Firefox", "firefox")
        self.tls_fingerprint_combo.addItem("Safari", "safari")
        self.tls_fingerprint_combo.addItem("随机", "random")
        # 设置当前值
        current_fp = self.settings.get("tls_fingerprint", "none")
        for i in range(self.tls_fingerprint_combo.count()):
            if self.tls_fingerprint_combo.itemData(i) == current_fp:
                self.tls_fingerprint_combo.setCurrentIndex(i)
                break
        self.tls_fingerprint_combo.setFixedHeight(26)
        self.tls_fingerprint_combo.currentIndexChanged.connect(self._on_tls_fingerprint_changed)
        fp_inner.addWidget(self.tls_fingerprint_combo)
        fp_inner.addStretch()
        ar.addLayout(fp_inner)

        # 域名嗅探开关行
        sniff_inner = QHBoxLayout()
        sniff_inner.setSpacing(4)
        sniff_inner.addWidget(QLabel("🔍 域名嗅探"))
        sniff_inner.itemAt(0).widget().setStyleSheet("font-size: 8pt; font-weight: bold;")
        sniff_inner.addStretch()
        self.switch_sniffing = ToggleSwitch("", default=self.settings.get("sniffing_enabled", False))
        self.switch_sniffing.setFixedHeight(22)
        self.switch_sniffing.setFixedWidth(72)
        self.switch_sniffing.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.switch_sniffing.toggled.connect(self._on_sniffing_toggled)
        sniff_inner.addWidget(self.switch_sniffing, alignment=Qt.AlignmentFlag.AlignVCenter)
        ar.addLayout(sniff_inner)

        self.adv_restart_hint = QLabel("⚠ 修改后需重启服务生效")
        self.adv_restart_hint.setObjectName("restart-hint")
        self.adv_restart_hint.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 8pt;")
        self.adv_restart_hint.setVisible(False)
        ar.addWidget(self.adv_restart_hint)

        pmc.addWidget(adv_row)

        # ========== 1. 系统代理 子卡片 ==========
        global_row = QFrame()
        global_row.setObjectName("switch-row")
        gr = QVBoxLayout(global_row)
        gr.setContentsMargins(14, 8, 14, 8)
        gr.setSpacing(6)

        # 标题行
        gr_title = QHBoxLayout()
        gr_title.setSpacing(4)
        gr_title.addWidget(QLabel("🌐 系统代理"))
        gr_title.itemAt(0).widget().setStyleSheet("font-size: 8pt; font-weight: bold;")
        gr_title.addWidget(_make_help_btn(
            "系统代理设置",
            "系统代理说明",
            "【系统代理】\n"
            "开启后，系统中所有应用（不仅浏览器）都通过代理访问网络。\n"
            "关闭后仅浏览器走代理，其他程序不受影响。\n\n"
            "【代理模式】\n"
            "全局系统代理：所有流量（包括国内网站）都走代理。\n"
            "绕过境内（仅代理境外）：仅国外流量走代理，国内网站直连，\n"
            "访问国内网站更快更省带宽。\n\n"
            "修改后需要重启代理服务才能生效。"
        ))
        gr_title.addStretch()
        # 开关
        self.switch_global_proxy = ToggleSwitch("", default=self.settings.get("global_proxy", False))
        self.switch_global_proxy.setFixedHeight(22)
        self.switch_global_proxy.setFixedWidth(72)
        self.switch_global_proxy.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.switch_global_proxy.toggled.connect(self._on_global_proxy_toggled)
        gr_title.addWidget(self.switch_global_proxy, alignment=Qt.AlignmentFlag.AlignVCenter)
        gr.addLayout(gr_title)

        # 模式选择行
        global_mode_inner = QHBoxLayout()
        global_mode_inner.setSpacing(8)
        global_mode_lbl = QLabel("代理模式:")
        global_mode_lbl.setStyleSheet("font-size: 8pt; color: #999999;")
        global_mode_inner.addWidget(global_mode_lbl)
        self.global_proxy_mode_group = []
        self.all_mode_rb = RadioButton("全局系统代理", default=self.settings.get("global_proxy_mode", "all") == "all")
        self.global_proxy_mode_group.append(self.all_mode_rb)
        global_mode_inner.addWidget(self.all_mode_rb)
        self.foreign_mode_rb = RadioButton("绕过境内（仅代理境外）", default=self.settings.get("global_proxy_mode", "all") == "foreign")
        self.global_proxy_mode_group.append(self.foreign_mode_rb)
        global_mode_inner.addWidget(self.foreign_mode_rb)
        self.all_mode_rb.toggled.connect(lambda checked: self._on_global_proxy_mode_toggled("all", checked))
        self.foreign_mode_rb.toggled.connect(lambda checked: self._on_global_proxy_mode_toggled("foreign", checked))
        gr.addLayout(global_mode_inner)

        self.global_restart_hint = QLabel("⚠ 修改后需重启服务生效")
        self.global_restart_hint.setObjectName("restart-hint")
        self.global_restart_hint.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 8pt;")
        self.global_restart_hint.setVisible(False)
        gr.addWidget(self.global_restart_hint)

        pmc.addWidget(global_row)

        # ========== 2. 浏览器代理 子卡片 ==========
        browser_row = QFrame()
        browser_row.setObjectName("switch-row")
        br = QVBoxLayout(browser_row)
        br.setContentsMargins(14, 8, 14, 8)
        br.setSpacing(6)

        br_title = QHBoxLayout()
        br_title.setSpacing(4)
        br_title.addWidget(QLabel("🌐 浏览器代理"))
        br_title.itemAt(0).widget().setStyleSheet("font-size: 8pt; font-weight: bold;")
        br_title.addWidget(_make_help_btn(
            "浏览器代理设置",
            "浏览器代理说明",
            "【浏览器代理】\n"
            "对选定的浏览器设置代理参数，其他浏览器不受影响。\n\n"
            "【代理范围】\n"
            "所有指定浏览器：所有已添加的浏览器都通过代理访问网络。\n"
            "单选指定浏览器：仅从已添加的浏览器中选择一个走代理。\n\n"
            "如需所有浏览器都走代理，请开启「全局系统代理」。"
        ))
        br_title.addStretch()
        self.switch_browser_proxy = ToggleSwitch("", default=self.settings.get("browser_proxy_enabled", True))
        self.switch_browser_proxy.setFixedHeight(22)
        self.switch_browser_proxy.setFixedWidth(72)
        self.switch_browser_proxy.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.switch_browser_proxy.toggled.connect(self._on_browser_proxy_toggled)
        br_title.addWidget(self.switch_browser_proxy, alignment=Qt.AlignmentFlag.AlignVCenter)
        br.addLayout(br_title)

        browser_scope_inner = QHBoxLayout()
        browser_scope_inner.setSpacing(8)
        browser_scope_lbl = QLabel("代理范围:")
        browser_scope_lbl.setStyleSheet("font-size: 8pt; color: #999999;")
        browser_scope_inner.addWidget(browser_scope_lbl)
        self.browser_proxy_scope_group = []
        self.all_browser_rb = RadioButton("所有指定浏览器", default=self.settings.get("browser_proxy_scope", "all") == "all")
        self.browser_proxy_scope_group.append(self.all_browser_rb)
        browser_scope_inner.addWidget(self.all_browser_rb)
        self.spec_browser_rb = RadioButton("单选指定浏览器", default=self.settings.get("browser_proxy_scope", "all") == "specified")
        self.browser_proxy_scope_group.append(self.spec_browser_rb)
        browser_scope_inner.addWidget(self.spec_browser_rb)
        self.all_browser_rb.toggled.connect(lambda checked: self._on_browser_proxy_scope_toggled("all", checked))
        self.spec_browser_rb.toggled.connect(lambda checked: self._on_browser_proxy_scope_toggled("specified", checked))
        br.addLayout(browser_scope_inner)

        self.specified_browser_hint = QLabel("")
        self.specified_browser_hint.setObjectName("dim")
        self.specified_browser_hint.setStyleSheet(f"font-size: 8pt; color: {COLOR_RED_LIGHT};")
        self.specified_browser_hint.setWordWrap(True)
        self._update_browser_proxy_scope_hint()
        br.addWidget(self.specified_browser_hint)

        pmc.addWidget(browser_row)

        # ========== 3. 地址代理 子卡片 ==========
        rules_row = QFrame()
        rules_row.setObjectName("switch-row")
        rr = QVBoxLayout(rules_row)
        rr.setContentsMargins(14, 8, 14, 8)
        rr.setSpacing(6)

        rr_title = QHBoxLayout()
        rr_title.setSpacing(4)
        rr_title.addWidget(QLabel("📋 地址代理"))
        rr_title.itemAt(0).widget().setStyleSheet("font-size: 8pt; font-weight: bold;")
        rr_title.addWidget(_make_help_btn(
            "地址代理设置",
            "地址代理说明",
            "【地址代理】\n"
            "指定特定网址或IP强制走代理，优先级高于默认规则。\n\n"
            "【代理范围】\n"
            "所有指定地址：所有已添加的规则都会走代理。\n"
            "单选指定地址：仅从已添加的规则中选择一条走代理。\n\n"
            "【规则类型】\n"
            "指定域名（DOMAIN-SUFFIX）：匹配该域名及其所有子域名\n"
            "  例: agnes-ai.com 将匹配 apihub.agnes-ai.com、www.agnes-ai.com 等\n\n"
            "指定网址（DOMAIN）：仅匹配精确网址\n"
            "  例: apihub.agnes-ai.com 仅匹配该网址\n\n"
            "IP地址段（IP-CIDR）：匹配IP地址范围\n"
            "  例: 192.168.1.0/24 匹配 192.168.1.0~192.168.1.255\n\n"
            "修改规则后需要重启代理服务才能生效。"
        ))
        rr_title.addStretch()
        self.switch_address_proxy = ToggleSwitch("", default=self.settings.get("address_proxy_enabled", True))
        self.switch_address_proxy.setFixedHeight(22)
        self.switch_address_proxy.setFixedWidth(72)
        self.switch_address_proxy.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.switch_address_proxy.toggled.connect(self._on_address_proxy_toggled)
        rr_title.addWidget(self.switch_address_proxy, alignment=Qt.AlignmentFlag.AlignVCenter)
        rr.addLayout(rr_title)

        address_scope_inner = QHBoxLayout()
        address_scope_inner.setSpacing(8)
        address_scope_lbl = QLabel("代理范围:")
        address_scope_lbl.setStyleSheet("font-size: 8pt; color: #999999;")
        address_scope_inner.addWidget(address_scope_lbl)
        self.address_proxy_scope_group = []
        self.all_address_rb = RadioButton("所有指定地址", default=self.settings.get("address_proxy_scope", "all") == "all")
        self.address_proxy_scope_group.append(self.all_address_rb)
        address_scope_inner.addWidget(self.all_address_rb)
        self.spec_address_rb = RadioButton("单选指定地址", default=self.settings.get("address_proxy_scope", "all") == "specified")
        self.address_proxy_scope_group.append(self.spec_address_rb)
        address_scope_inner.addWidget(self.spec_address_rb)
        self.all_address_rb.toggled.connect(lambda checked: self._on_address_proxy_scope_toggled("all", checked))
        self.spec_address_rb.toggled.connect(lambda checked: self._on_address_proxy_scope_toggled("specified", checked))
        rr.addLayout(address_scope_inner)

        # 单选指定地址模式下拉列表（仅在"单选指定地址"模式时显示）
        self.address_select_combo = UpComboBox()
        self.address_select_combo.currentIndexChanged.connect(self._on_address_select_combo_changed)
        # 先加入布局再设置可见性，避免 setVisible 在 addWidget 之前调用时高度异常
        rr.addWidget(self.address_select_combo)
        address_scope_is_specified = self.settings.get("address_proxy_scope", "all") == "specified"
        self.address_select_combo.setVisible(address_scope_is_specified)

        add_rule_row = QHBoxLayout()
        add_rule_row.setSpacing(6)
        self.rule_type_combo = UpComboBox()
        self.rule_type_combo.setFixedWidth(100)
        self.rule_type_combo.addItem("指定域名", "DOMAIN-SUFFIX")
        self.rule_type_combo.addItem("指定网址", "DOMAIN")
        self.rule_type_combo.addItem("IP地址段", "IP-CIDR")
        add_rule_row.addWidget(self.rule_type_combo)
        self.rule_value_input = QLineEdit()
        self.rule_value_input.setPlaceholderText("例: agnes-ai.com")
        self.rule_value_input.setStyleSheet(
            f"QLineEdit {{ background-color: #111; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 4px; padding: 4px 8px; color: {COLOR_TEXT}; font-size: 8pt; }}"
        )
        self.rule_value_input.returnPressed.connect(self._on_add_proxy_rule)
        add_rule_row.addWidget(self.rule_value_input, stretch=1)
        add_rule_btn = QPushButton("＋添加")
        add_rule_btn.setObjectName("small-blue")
        add_rule_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_rule_btn.setFixedSize(60, 28)
        add_rule_btn.clicked.connect(self._on_add_proxy_rule)
        add_rule_row.addWidget(add_rule_btn)
        self.add_rule_btn = add_rule_btn
        rr.addLayout(add_rule_row)

        self._proxy_rules = self.settings.get("proxy_rules", [])
        self._rule_rows = []
        self._rule_list_widget = QWidget()
        self._rule_list_layout = QVBoxLayout(self._rule_list_widget)
        self._rule_list_layout.setContentsMargins(0, 0, 0, 0)
        self._rule_list_layout.setSpacing(0)
        self._refresh_proxy_rules_ui()
        self._refresh_address_select_combo()
        rr.addWidget(self._rule_list_widget)

        self.rules_restart_hint = QLabel("⚠ 修改规则后需重启服务生效")
        self.rules_restart_hint.setObjectName("restart-hint")
        self.rules_restart_hint.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 8pt;")
        # 默认隐藏：只有在用户实际修改规则（增删/范围切换/类型切换）后才显示
        self.rules_restart_hint.setVisible(False)
        rr.addWidget(self.rules_restart_hint)

        pmc.addWidget(rules_row)

        # ========== 4. 程序代理 子卡片 ==========
        app_row = QFrame()
        app_row.setObjectName("switch-row")
        ar = QVBoxLayout(app_row)
        # 底部内边距加大到 14px，让删除按钮下方有更舒展的留白，与地址代理的体感保持一致
        ar.setContentsMargins(14, 8, 14, 14)
        # 间距 6px：与地址代理 / 浏览器代理 / 全局代理卡片保持统一的同结构节奏
        ar.setSpacing(6)

        ar_title = QHBoxLayout()
        ar_title.setSpacing(4)
        ar_title.addWidget(QLabel("🎯 程序代理"))
        ar_title.itemAt(0).widget().setStyleSheet("font-size: 8pt; font-weight: bold;")
        ar_title.addWidget(_make_help_btn(
            "程序代理设置",
            "程序代理说明",
            "【程序代理】\n"
            "添加指定程序后，这些程序也会通过代理访问网络。\n"
            "适合需要让某些非浏览器应用也走代理的场景。\n\n"
            "【代理范围】\n"
            "所有指定程序：所有已添加的程序都会通过代理访问网络。\n"
            "单选指定程序：仅从已添加的程序中选择一个程序走代理。\n\n"
            "【使用方法】\n"
            "1. 开启开关\n"
            "2. 选择代理范围（所有/单选）\n"
            "3. 点击「添加程序」选择exe文件\n"
            "4. 修改后需重启代理服务生效"
        ))
        ar_title.addStretch()
        self.switch_custom_apps = ToggleSwitch("", default=self.settings.get("custom_apps_enabled", False))
        self.switch_custom_apps.setFixedHeight(22)
        self.switch_custom_apps.setFixedWidth(72)
        self.switch_custom_apps.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.switch_custom_apps.toggled.connect(self._on_custom_apps_toggled)
        ar_title.addWidget(self.switch_custom_apps, alignment=Qt.AlignmentFlag.AlignVCenter)
        ar.addLayout(ar_title)

        app_scope_inner = QHBoxLayout()
        app_scope_inner.setSpacing(8)
        app_scope_lbl = QLabel("代理范围:")
        app_scope_lbl.setStyleSheet("font-size: 8pt; color: #999999;")
        app_scope_inner.addWidget(app_scope_lbl)
        self.custom_apps_scope_group = []
        self.all_custom_apps_rb = RadioButton("所有指定程序", default=self.settings.get("custom_apps_scope", "all") == "all")
        self.custom_apps_scope_group.append(self.all_custom_apps_rb)
        app_scope_inner.addWidget(self.all_custom_apps_rb)
        self.spec_custom_apps_rb = RadioButton("单选指定程序", default=self.settings.get("custom_apps_scope", "all") == "specified")
        self.custom_apps_scope_group.append(self.spec_custom_apps_rb)
        app_scope_inner.addWidget(self.spec_custom_apps_rb)
        self.all_custom_apps_rb.toggled.connect(lambda checked: self._on_custom_apps_scope_toggled("all", checked))
        self.spec_custom_apps_rb.toggled.connect(lambda checked: self._on_custom_apps_scope_toggled("specified", checked))
        ar.addLayout(app_scope_inner)

        self.specified_custom_apps_hint = QLabel("")
        self.specified_custom_apps_hint.setObjectName("dim")
        self.specified_custom_apps_hint.setStyleSheet(f"font-size: 8pt; color: {COLOR_RED_LIGHT};")
        self.specified_custom_apps_hint.setWordWrap(True)
        self._update_custom_apps_scope_hint()
        ar.addWidget(self.specified_custom_apps_hint)

        self.custom_restart_hint = QLabel("⚠ 修改后需重启服务生效")
        self.custom_restart_hint.setObjectName("restart-hint")
        self.custom_restart_hint.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 8pt;")
        self.custom_restart_hint.setVisible(False)
        ar.addWidget(self.custom_restart_hint)

        app_combo_row = QHBoxLayout()
        app_combo_row.setSpacing(8)
        self.app_combo = UpComboBox()
        self.app_combo.setFixedHeight(28)
        for app_path in self.settings.get("custom_apps", []):
            self._add_app_item(app_path)
        app_combo_row.addWidget(self.app_combo, stretch=1)
        add_app_btn = QPushButton("＋添加")
        add_app_btn.setObjectName("small-blue")
        add_app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_app_btn.setFixedSize(60, 28)
        add_app_btn.clicked.connect(self._on_add_app)
        app_combo_row.addWidget(add_app_btn)
        self.add_app_btn = add_app_btn
        remove_app_btn = QPushButton("－删除")
        remove_app_btn.setObjectName("small-red")
        remove_app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_app_btn.setFixedSize(60, 28)
        remove_app_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; padding: 4px 12px; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        remove_app_btn.clicked.connect(self._on_remove_app)
        app_combo_row.addWidget(remove_app_btn)
        self.remove_app_btn = remove_app_btn
        ar.addLayout(app_combo_row)

        pmc.addWidget(app_row)

        layout.addWidget(proxy_mode_card)

        self._update_proxy_ui_disabled_state()

        startup_card = QFrame()
        startup_card.setObjectName("card")
        sl = QVBoxLayout(startup_card)
        sl.setContentsMargins(20, 14, 20, 14)
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
        asr.setContentsMargins(14, 8, 14, 8)
        autostart_info = QVBoxLayout()
        autostart_info.setSpacing(1)
        autostart_lbl = QLabel("🚀 启动时自动开启服务")
        autostart_lbl.setStyleSheet("font-size: 8pt; font-weight: bold;")
        autostart_info.addWidget(autostart_lbl)
        autostart_desc = QLabel("打开启动器时自动启动代理服务")
        autostart_desc.setObjectName("dim")
        autostart_desc.setStyleSheet("font-size: 8pt;")
        autostart_info.addWidget(autostart_desc)
        asr.addLayout(autostart_info, stretch=1)
        self.switch_auto_start = ToggleSwitch("", default=self.settings.get("auto_start", True))
        self.switch_auto_start.setFixedHeight(22)
        self.switch_auto_start.setFixedWidth(72)
        self.switch_auto_start.toggled.connect(self._on_auto_start_toggled)
        asr.addWidget(self.switch_auto_start, alignment=Qt.AlignmentFlag.AlignVCenter)
        sl.addWidget(autostart_row)

        layout.addWidget(startup_card)

        kernel_card = QFrame()
        kernel_card.setObjectName("card")
        # 灵活自适应：Preferred/Preferred 策略，不硬卡最大高度
        # 让卡片根据内部内容自然伸缩（收起 ~100px，展开 ~250px）
        kernel_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        kl = QVBoxLayout(kernel_card)
        # 顶部内边距稍大（10px），让标题行的检查更新按钮视觉上不顶到卡片上沿
        # 底部 8px，水平 12px，控件间距 4px，整体比之前更舒展
        kl.setSpacing(4)
        kl.setContentsMargins(12, 10, 12, 8)

        kernel_title_row = QHBoxLayout()
        kernel_title_row.setSpacing(6)
        kernel_title = QLabel("代理内核")
        kernel_title.setObjectName("accent")
        kernel_title.setStyleSheet("font-size: 9pt; font-weight: bold;")
        kernel_title_row.addWidget(kernel_title)
        kernel_title_row.addWidget(_make_help_btn(
            "代理内核",
            "代理内核说明",
            "【代理内核版本管理】\n"
            "管理 mihomo 代理内核的版本，支持查看、下载和切换。\n\n"
            "【当前版本】\n"
            "显示当前正在使用的内核版本。\n\n"
            "【检查更新】\n"
            "从 GitHub 获取最新的内核版本列表。\n"
            "如代理正在运行，将优先通过代理加速下载。\n\n"
            "【切换版本】\n"
            "切换到已下载的其他内核版本。\n"
            "如遇新版本问题，可回滚到旧版本。"
        ))
        # 检查更新按钮：与标题同一行右侧，垂直居中
        # 尺寸调整为 92x28，比之前的 100x22 更舒展、不扁
        # 与版本页"检查更新"按钮（80x26）保持同款蓝色实心圆角风格
        self.btn_check_kernel = QPushButton("🔄 检查更新")
        self.btn_check_kernel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_kernel.setFixedSize(92, 28)
        self.btn_check_kernel.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #FFFFFF; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; padding: 0px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
            f"QPushButton:pressed {{ background-color: {COLOR_BLUE}; padding-top: 1px; padding-left: 1px; }}"
        )
        self.btn_check_kernel.clicked.connect(self._on_check_kernel_btn)
        kernel_title_row.addStretch()
        kernel_title_row.addWidget(self.btn_check_kernel, 0, Qt.AlignmentFlag.AlignVCenter)
        kl.addLayout(kernel_title_row)

        # 描述行：当前版本 + 已是最新版本/最新版本 + 共X个版本可用
        # 三个标签在同一行内紧凑展示，整体放在"检查更新"按钮下面
        kernel_info_row = QHBoxLayout()
        kernel_info_row.setSpacing(10)
        self.kernel_current_label = QLabel(f"当前版本: {self._get_mihomo_version() or '未知'}")
        self.kernel_current_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_GREEN}; font-weight: bold;")
        kernel_info_row.addWidget(self.kernel_current_label)
        self.kernel_latest_label = QLabel("")
        self.kernel_latest_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM};")
        kernel_info_row.addWidget(self.kernel_latest_label)
        # 版本数量描述（"共 X 个版本可用  |  上次检查: ..."）
        # 位置：推到 info_row 最右端，与上方"检查更新"按钮的右边缘对齐
        #   视觉上让"检查更新 → 数量反馈"形成一条从右上到右下的对齐线
        #   占据中间空白用 addStretch() 自适应填充（无论窗口宽度如何都对齐）
        self.kernel_count_label = QLabel("")
        self.kernel_count_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM};")
        kernel_info_row.addStretch()  # 关键：stretch 必须在 count 之前
        kernel_info_row.addWidget(self.kernel_count_label)

        kl.addLayout(kernel_info_row)

        # 状态行（默认隐藏，仅显示"正在检查..."等瞬时状态，不展示数量信息）
        self.kernel_status = CopyableLabel("", max_height=30)
        self.kernel_status.setVisible(False)
        # 文本非空时自动显示，为空时自动隐藏（避免在 30+ 个 setText 处手动控制）
        self.kernel_status.textChanged.connect(
            lambda: self.kernel_status.setVisible(bool(self.kernel_status.toPlainText().strip()))
        )
        kl.addWidget(self.kernel_status)
        # 描述行与下载列表之间保持 10px 间隔（setSpacing=4 + 此处 addSpacing(6) = 10）
        kl.addSpacing(6)

        # 列表区域：默认显示 2 排高度的下载列表框，框内显示提示文案
        # 点检查更新获取到结果后再展开高度
        self._kernel_scroll_visible = True
        self._kernel_scroll = QScrollArea()
        self._kernel_scroll.setWidgetResizable(True)
        self._kernel_scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {COLOR_BG}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; }}"
            f"QScrollBar:vertical {{ width: 6px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: #444; border-radius: 3px; min-height: 20px; }}"
        )
        self._kernel_scroll_content = QWidget()
        self._kernel_scroll_layout = QVBoxLayout(self._kernel_scroll_content)
        self._kernel_scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._kernel_scroll_layout.setSpacing(0)
        # 提示标签：默认显示，拿到版本列表后隐藏
        self._kernel_hint_label = QLabel("点击「检查更新」获取最新版本列表")
        self._kernel_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._kernel_hint_label.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 9pt; padding: 6px 4px; background: transparent; border: none;"
        )
        # 紧凑高度（2 排），用 setMaximumHeight 控制上限，避免内容撑高
        self._kernel_hint_label.setMaximumHeight(44)
        self._kernel_scroll_layout.addWidget(self._kernel_hint_label)
        # 表头行：版本 / 发布日期 / 更新说明(stretch) / 状态 / 操作
        # 关键：表头作为独立控件常驻在 scroll 布局的 index=1 位置，永远在下载列表最上方
        # 之前用 insertWidget(1, header_row) + insertWidget(count-1, card) 的写法，
        # 每次插入 card 都会把表头向下挤，导致表头被推到底部。
        # 改为：表头作为常驻控件仅创建/显示一次，cards 通过 addWidget 直接追加到尾部。
        # 列宽调整（与下方卡片"5 列"一一对应）：
        #   版本 70（v1.19.25 紧凑），发布日期 105（容纳 "2026-06-07 04:45" 完整显示），
        #   状态 90（"🧪 预发布 99MB" 紧凑），操作 100（容纳"🔄 切换 + 🗑"），
        #   更新说明 stretch（占满剩余宽度，与状态列互换位置后视觉重心更平衡）
        self._kernel_header_row = QFrame()
        self._kernel_header_row.setObjectName("kernel_header_row")
        self._kernel_header_row.setStyleSheet(
            "background-color: #1a1a1a; border: none; border-bottom: 1px solid #2a2a2a;"
        )
        header_layout = QHBoxLayout(self._kernel_header_row)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.setSpacing(6)
        for text, width, stretch in [
            ("版本", 70, 0), ("发布日期", 105, 0), ("更新说明", 0, 1),
            ("状态", 90, 0), ("操作", 100, 0)
        ]:
            lbl = QLabel(text)
            if width > 0:
                lbl.setFixedWidth(width)
            lbl.setStyleSheet("font-size: 8pt; color: #FFFFFF; border: none; font-weight: bold;")
            header_layout.addWidget(lbl, stretch=stretch)
        self._kernel_header_row.setVisible(False)  # 默认隐藏，拿到版本列表后显示
        self._kernel_scroll_layout.addWidget(self._kernel_header_row)
        # 关键：不加 addStretch()！
        # 原因：addStretch() 在 setMaximumHeight(N) 限制下，会撑满 scroll area
        #       视口的剩余空间，把后续插入的 cards 挤到不可见区域，
        #       导致"列表只有一排"的 bug。直接让 layout 由 widgets sizeHint 决定。
        self._kernel_scroll.setWidget(self._kernel_scroll_content)
        self._kernel_scroll.setVisible(True)
        # 默认紧凑 5 排高度（约 160px），点检查更新获取到结果后由 _show_kernel_list 调高
        self._kernel_scroll.setMaximumHeight(160)
        # 收起时不再 stretch，让卡片按内容自适应；展开时再 stretch
        kl.addWidget(self._kernel_scroll)

        # 拖拽手柄：用户可拖拽调整内核列表高度
        self._kernel_resize_handle = QFrame()
        self._kernel_resize_handle.setFixedHeight(8)
        self._kernel_resize_handle.setCursor(Qt.CursorShape.SizeVerCursor)
        self._kernel_resize_handle.setStyleSheet(
            f"QFrame {{ background-color: transparent; margin: 0 40px; }}"
        )
        self._kernel_resize_handle_label = QLabel("⋯")
        self._kernel_resize_handle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._kernel_resize_handle_label.setStyleSheet(
            f"color: #555; font-size: 10pt; background: transparent; border: none;"
        )
        resize_handle_layout = QVBoxLayout(self._kernel_resize_handle)
        resize_handle_layout.setContentsMargins(0, 0, 0, 0)
        resize_handle_layout.addWidget(self._kernel_resize_handle_label)
        self._kernel_resize_handle.mousePressEvent = self._on_kernel_resize_start
        self._kernel_resize_handle.mouseMoveEvent = self._on_kernel_resize_move
        self._kernel_resize_handle.mouseReleaseEvent = self._on_kernel_resize_end
        self._kernel_resizing = False
        self._kernel_resize_start_y = 0
        self._kernel_resize_start_h = 160
        kl.addWidget(self._kernel_resize_handle)

        # 保存为实例属性，便于 _show_kernel_list 动态调整最大高度
        self.kernel_card = kernel_card
        # 不加 stretch=1，让卡片根据内容自适应高度，避免被父布局拉伸导致收起状态也无法压缩
        layout.addWidget(kernel_card)

        self.sys_proxy_lbl = QLabel("")
        self.sys_proxy_lbl.setObjectName("dim")
        self._update_sys_proxy_label()
        layout.addWidget(self.sys_proxy_lbl)
        # 关键：末尾加 stretch，把父布局的剩余空白吃掉，避免下方露出大片黑色空区域
        layout.addStretch(1)
        return page

    def _build_log_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("log")
        self.log_text.setReadOnly(True)
        # 最小高度保证日志有足够可视区，剩余空间由 Expanding 策略自动撑开，
        # 避免 tab 区域比 450 大时底部留出大片黑色空白。
        self.log_text.setMinimumHeight(450)
        self.log_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.log_text)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(20)
        btn_row.setContentsMargins(0, 0, 0, 0)

        # 跟随滚动开关（红色，开关态时高亮）
        self._log_auto_scroll = True
        self.btn_auto_scroll = QPushButton("📌 跟随")
        self.btn_auto_scroll.setCheckable(True)
        self.btn_auto_scroll.setChecked(True)
        self.btn_auto_scroll.setCursor(Qt.CursorShape.PointingHandCursor)
        # 日志栏目下方按钮收窄 10px：原 min-width 90 → 80
        self.btn_auto_scroll.setMinimumWidth(80)
        self.btn_auto_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_auto_scroll.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #fff; border: none; border-radius: 4px; "
            f"font-size: 8pt; font-weight: bold; padding: 4px 6px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
            f"QPushButton:!checked {{ background-color: #555; color: #aaa; }}"
            f"QPushButton:!checked:hover {{ background-color: #666; color: #ccc; }}"
        )
        self.btn_auto_scroll.toggled.connect(self._on_auto_scroll_toggled)
        btn_row.addWidget(self.btn_auto_scroll)

        # 复制日志
        copy_btn = QPushButton("📋 复制")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setMinimumWidth(80)
        copy_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        copy_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 4px; "
            f"font-size: 8pt; font-weight: bold; padding: 4px 6px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        copy_btn.clicked.connect(self._on_copy_log)
        btn_row.addWidget(copy_btn)

        # 保存日志
        save_btn = QPushButton("💾 保存")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setMinimumWidth(80)
        save_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        save_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 4px; "
            f"font-size: 8pt; font-weight: bold; padding: 4px 6px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        save_btn.clicked.connect(self._on_export_log)
        btn_row.addWidget(save_btn)

        # 清空日志
        clear_btn = QPushButton("🗑 清空")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setMinimumWidth(80)
        clear_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        clear_btn.setStyleSheet(
            f"QPushButton {{ background-color: #555; color: #ddd; border: none; border-radius: 4px; "
            f"font-size: 8pt; font-weight: bold; padding: 4px 6px; }}"
            f"QPushButton:hover {{ background-color: #666; }}"
        )
        clear_btn.clicked.connect(self.log_text.clear)
        btn_row.addWidget(clear_btn)

        # 调试模式开关（深绿色按钮样式，与跟随开关风格一致）
        self.btn_debug_mode = QPushButton("🐛 调试")
        self.btn_debug_mode.setCheckable(True)
        self.btn_debug_mode.setChecked(self.settings.get("debug_mode", False))
        self.btn_debug_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_debug_mode.setMinimumWidth(80)
        self.btn_debug_mode.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_debug_mode.setStyleSheet(
            f"QPushButton {{ background-color: #2E5D3A; color: #fff; border: none; border-radius: 4px; "
            f"font-size: 8pt; font-weight: bold; padding: 4px 6px; }}"
            f"QPushButton:hover {{ background-color: #3A7548; }}"
            f"QPushButton:checked {{ background-color: #1E7D34; }}"
            f"QPushButton:checked:hover {{ background-color: #2A9D45; }}"
        )
        self.btn_debug_mode.toggled.connect(self._on_debug_mode_toggled)
        btn_row.addWidget(self.btn_debug_mode)

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

        header_frame = QFrame()
        header_frame.setStyleSheet(f"background-color: #1a1a1a; border: none; border-bottom: 1px solid #2a2a2a;")
        header_frame.setFixedHeight(44)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(6)

        btn_about = QPushButton("关于")
        btn_about.setFixedSize(50, 30)
        btn_about.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_about.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: #888; border: 1px solid #444; border-radius: 6px; "
            f"font-size: 8pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: #333; color: #fff; border-color: #666; }}"
        )
        btn_about.clicked.connect(self._show_about)
        header_layout.addWidget(btn_about)

        self._ver_tab_stable_btn = QPushButton("正式版本")
        self._ver_tab_stable_btn.setFixedSize(110, 30)
        self._ver_tab_stable_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ver_tab_stable_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        self._ver_tab_stable_btn.clicked.connect(lambda: self._switch_ver_tab("stable"))
        header_layout.addWidget(self._ver_tab_stable_btn)

        self._ver_tab_git_btn = QPushButton("开发动态")
        self._ver_tab_git_btn.setFixedSize(110, 30)
        self._ver_tab_git_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ver_tab_git_btn.setStyleSheet(
            f"QPushButton {{ background-color: #333; color: #888; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED}; color: #fff; }}"
        )
        self._ver_tab_git_btn.clicked.connect(lambda: self._switch_ver_tab("git"))
        header_layout.addWidget(self._ver_tab_git_btn)

        self._ver_status_label = QLabel("")
        self._ver_status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_DIM}; border: none;")
        header_layout.addWidget(self._ver_status_label, stretch=1)

        header_layout.addWidget(_make_help_btn(
            "软件版本管理",
            "软件更新说明",
            "【正式版本】\n"
            "已发布的正式版本列表，可切换、下载和查看更新内容。\n"
            "绿色标记为当前使用的版本。\n\n"
            "【开发动态】\n"
            "全量开发提交记录，每次构建时从git历史生成。\n"
            "点击检查更新可获取远程最新开发动态。\n\n"
            "【切换版本】\n"
            "点击「切换」按钮可在已下载的版本间切换，\n"
            "切换后程序会自动重启。\n\n"
            "【下载版本】\n"
            "点击「下载」按钮从远程仓库下载新版本EXE文件，\n"
            "下载完成后可选择立即切换。"
        ))

        self._ver_expand_btn = QPushButton("列表模式")
        self._ver_expand_btn.setFixedSize(80, 26)
        self._ver_expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ver_expand_btn.setStyleSheet(
            f"QPushButton {{ background-color: #333; color: #ccc; border: 1px solid #444; border-radius: 6px; "
            f"font-size: 8pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: #444; color: #fff; border-color: #555; }}"
        )
        self._ver_expand_btn.clicked.connect(self._toggle_expand_all)
        header_layout.addWidget(self._ver_expand_btn)

        btn_check_remote = QPushButton("检查更新")
        btn_check_remote.setFixedSize(80, 26)
        btn_check_remote.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_check_remote.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 6px; "
            f"font-size: 8pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        btn_check_remote.clicked.connect(self._check_remote_versions)
        header_layout.addWidget(btn_check_remote)

        layout.addWidget(header_frame)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        # 最小高度保证列表有足够可视区，剩余空间由 Expanding 策略自动撑开，
        # 避免 tab 区域比 550 大时底部留出大片黑色空白。
        scroll_area.setMinimumHeight(550)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {COLOR_BG}; border: none; }}"
            f"QScrollBar:vertical {{ background-color: {COLOR_BG}; width: 8px; border: none; }}"
            f"QScrollBar::handle:vertical {{ background-color: #333; border-radius: 4px; min-height: 30px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
        )
        self._ver_scroll_content = QWidget()
        self._ver_scroll_layout = QVBoxLayout(self._ver_scroll_content)
        self._ver_scroll_layout.setContentsMargins(12, 8, 12, 8)
        self._ver_scroll_layout.setSpacing(6)
        self._ver_scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self._ver_scroll_content)
        self._ver_scroll = scroll_area
        layout.addWidget(scroll_area)

        self._ver_stable_data = []
        self._ver_git_data = []
        self._ver_current_version = VERSION
        self._ver_active_tab = "stable"
        self._ver_info_text = "点击「检查远程更新」查看最新版本"
        self._ver_display_mode = "detail"
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
        ver = self._get_mihomo_version()
        if ver:
            return f"mihomo v{ver}"
        if not self.quick_dir:
            return None
        try:
            return f"{os.path.getsize(os.path.join(self.quick_dir, 'quick.exe')) // 1024}KB"
        except Exception:
            return None

    def _get_mihomo_version(self):
        if not self.quick_dir:
            return ""
        ver_file = os.path.join(self.quick_dir, "_kernel_version.txt")
        if os.path.isfile(ver_file):
            try:
                with open(ver_file, "r", encoding="utf-8") as f:
                    v = f.read().strip()
                    if v:
                        return v
            except Exception:
                pass
        exe_path = os.path.join(self.quick_dir, "quick.exe")
        if not os.path.isfile(exe_path):
            return ""
        try:
            result = subprocess.run(
                [exe_path, "-v"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = (result.stdout or "") + (result.stderr or "")
            m = re.search(r'v?(\d+\.\d+\.\d+)', output)
            if m:
                ver = m.group(1)
                try:
                    with open(ver_file, "w", encoding="utf-8") as f:
                        f.write(ver)
                except Exception:
                    pass
                return ver
        except Exception:
            pass
        return ""

    def _list_local_kernels(self):
        if not self.quick_dir:
            return []
        kernels_dir = os.path.join(self.quick_dir, "kernels")
        if not os.path.isdir(kernels_dir):
            return []
        result = []
        for f in os.listdir(kernels_dir):
            if f.startswith("mihomo_") and f.endswith(".exe"):
                m = re.search(r'mihomo_(v?[\d.]+)\.exe', f)
                if m:
                    tag = m.group(1)
                    if not tag.startswith("v"):
                        tag = "v" + tag
                    result.append({
                        "tag": tag,
                        "path": os.path.join(kernels_dir, f),
                        "size_mb": round(os.path.getsize(os.path.join(kernels_dir, f)) / 1024 / 1024, 1),
                    })
        return result

    def _add_app_item(self, app_path):
        self.app_combo.addItem(os.path.basename(app_path), app_path)

    def _append_log(self, msg):
        self.log_text.append(msg)
        if getattr(self, '_log_auto_scroll', True):
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _update_kernel_status(self):
        has_kernel = bool(self._get_quick_version())
        if has_kernel:
            self._set_home_kernel_status("ready")
        elif self._auto_download_kernel:
            self._set_home_kernel_status("initializing", "⏳ 获取新版代理内核...")
        else:
            self._set_home_kernel_status("missing")
        if self.quick_dir:
            log.info(f"代理内核已就绪: {self.quick_dir}")
        else:
            log.warning("未找到代理内核")

    def _set_home_kernel_status(self, state, text=None):
        if hasattr(self, 'svc_kernel_label'):
            ver = self._get_quick_version() or '未安装'
            self.svc_kernel_label.setText(f"内核: {ver}")
            if state == "ready":
                self.svc_kernel_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_GREEN};")
            else:
                self.svc_kernel_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_ORANGE}; font-weight: bold;")
        if not hasattr(self, 'svc_kernel_status'):
            return
        if state == "ready":
            self.svc_kernel_status.setText("✅ 代理内核已启用")
            self.svc_kernel_status.setStyleSheet(
                f"color: {COLOR_GREEN}; font-size: 7pt; font-weight: bold;"
            )
            self.svc_kernel_status.setCursor(Qt.CursorShape.ArrowCursor)
            self.svc_kernel_status.mousePressEvent = None
            if hasattr(self, 'svc_kernel_progress'):
                self.svc_kernel_progress.hide()
        elif state == "initializing":
            self.svc_kernel_status.setText(text or "⏳ 获取新版代理内核...")
            self.svc_kernel_status.setStyleSheet(
                f"color: {COLOR_ORANGE}; font-size: 7pt; font-weight: bold;"
            )
            self.svc_kernel_status.setCursor(Qt.CursorShape.ArrowCursor)
            self.svc_kernel_status.mousePressEvent = None
        elif state == "downloading":
            self.svc_kernel_status.setText(text or "⏳ 下载代理内核...")
            self.svc_kernel_status.setStyleSheet(
                f"color: {COLOR_ORANGE}; font-size: 7pt; font-weight: bold;"
            )
            self.svc_kernel_status.setCursor(Qt.CursorShape.ArrowCursor)
            self.svc_kernel_status.mousePressEvent = None
            if hasattr(self, 'svc_kernel_progress'):
                self.svc_kernel_progress.setValue(0)
                self.svc_kernel_progress.show()
        elif state == "failed":
            self.svc_kernel_status.setText(text or "⚠ 代理内核缺失，点击修复")
            self.svc_kernel_status.setStyleSheet(
                f"color: #FF6B80; font-size: 7pt; font-weight: bold;"
            )
            self.svc_kernel_status.setCursor(Qt.CursorShape.PointingHandCursor)
            self.svc_kernel_status.mousePressEvent = lambda e: self._on_nav_clicked(1)
            if hasattr(self, 'svc_kernel_progress'):
                self.svc_kernel_progress.hide()
        else:
            self.svc_kernel_status.setText("⚠ 代理内核缺失，点击修复")
            self.svc_kernel_status.setStyleSheet(
                f"color: #FF6B80; font-size: 7pt; font-weight: bold;"
            )
            self.svc_kernel_status.setCursor(Qt.CursorShape.PointingHandCursor)
            self.svc_kernel_status.mousePressEvent = lambda e: self._on_nav_clicked(1)
            if hasattr(self, 'svc_kernel_progress'):
                self.svc_kernel_progress.hide()

    def _on_home_kernel_download_percent(self, pct):
        if hasattr(self, 'svc_kernel_progress') and self.svc_kernel_progress.isVisible():
            self.svc_kernel_progress.setValue(pct)

    def _update_status(self, running):
        if running:
            self.svc_status_dot.setStyleSheet(f"font-size: 14px; color: {COLOR_GREEN};")
            self.svc_status_label.setText("代理运行中")
            self.svc_status_label.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {COLOR_GREEN};")
            if hasattr(self, 'line_progress') and self.line_progress is not None:
                try:
                    self.line_progress.setText("代理服务已启动")
                except RuntimeError:
                    pass
            self.svc_line_label.setText(f"线路: {self.current_line or '未知'}")
        else:
            self.svc_status_dot.setStyleSheet(f"font-size: 14px; color: #FF6B80;")
            if self.switch_proxy.isChecked():
                self.svc_status_label.setText("代理未连接")
                self.svc_status_label.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {COLOR_ORANGE};")
                if hasattr(self, 'line_progress') and self.line_progress is not None:
                    try:
                        self.line_progress.setText("代理服务已开启但未连接")
                    except RuntimeError:
                        pass
                self.svc_line_label.setText("线路: 点击重连")
            else:
                self.svc_status_label.setText("代理未启动")
                self.svc_status_label.setStyleSheet(f"font-size: 10pt; font-weight: bold; color: {COLOR_TEXT};")
                if hasattr(self, 'line_progress') and self.line_progress is not None:
                    try:
                        self.line_progress.setText("开启代理服务以访问外网")
                    except RuntimeError:
                        pass
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

    def _on_restart_apply(self):
        """重启代理服务以应用所有代理设置变更"""
        if not is_proxy_running():
            QMessageBox.information(self, "提示", "代理服务未启动，请先启动服务。")
            return
        self._on_stop()
        # 重启完成后更新所有提示为"当前设置已生效"，10秒后消失
        QTimer.singleShot(500, self._on_start)
        QTimer.singleShot(2000, self._show_restart_applied_hints)
        log.info("用户点击重启生效，正在重启代理服务")

    def _show_restart_applied_hints(self):
        """重启生效后，将所有提示改为'当前设置已生效'，10秒后消失"""
        green_style = f"color: {COLOR_GREEN}; font-size: 8pt;"
        for hint in (self.global_restart_hint, self.rules_restart_hint, self.custom_restart_hint,
                     self.tun_restart_hint, self.adv_restart_hint):
            hint.setText("✓ 当前设置已生效")
            hint.setStyleSheet(green_style)
            hint.setVisible(True)
        # 10秒后隐藏所有提示
        QTimer.singleShot(10000, self._hide_restart_hints)

    def _hide_restart_hints(self):
        """隐藏所有重启提示"""
        orange_style = f"color: {COLOR_ORANGE}; font-size: 8pt;"
        for hint in (self.global_restart_hint, self.rules_restart_hint, self.custom_restart_hint,
                     self.tun_restart_hint, self.adv_restart_hint):
            hint.setVisible(False)
            hint.setStyleSheet(orange_style)

    def _on_start(self):
        if not self.quick_dir:
            QMessageBox.critical(self, "错误",
                "未找到代理内核！\n\n"
                f"基础目录: {get_base_dir()}\n\n"
                "请确保 app/Quick/ 目录中包含 quick.exe。")
            return
        # TUN 模式需要管理员权限
        if self.settings.get("tun_enabled", False) and not self._is_admin:
            QMessageBox.warning(self, "权限不足",
                "TUN 模式需要管理员权限运行。\n\n"
                "请以管理员身份重新启动本程序，或关闭 TUN 模式后重试。")
            self.switch_proxy.setChecked(False)
            return
        if self.worker and self.worker.isRunning():
            return
        self._cleanup_worker()
        # 启动前注入所有 Yunji 规则（save_config 会保留这些规则）
        self._inject_all_rules()
        self.switch_proxy.setEnabled(False)
        self.line_progress.setText("正在启动代理服务...")
        self.worker = ServiceWorker("start", quick_dir=self.quick_dir, current_line=self.current_line)
        self.worker.line_selected.connect(self._on_line_selected)
        self.worker.progress.connect(lambda t: self.line_progress.setText(t))
        self.worker.finished.connect(self._on_start_finished)
        self.worker.start()

    def _on_start_finished(self, ok, msg):
        self.switch_proxy.setEnabled(True)
        if ok:
            self.line_progress.setText(msg)
            # 系统代理、监控等立即执行（不阻塞 UI）
            if self._needs_system_proxy():
                set_system_proxy(True)
                self._update_sys_proxy_label()
            self.global_restart_hint.setVisible(False)
            self.custom_restart_hint.setVisible(False)
            if self.settings.get("realtime_reconnect", False):
                self._start_realtime_monitor()
            if self.settings.get("auto_line_switch", False):
                self._start_auto_line_timer()
            self._update_active_line()
            # 延迟验证异步执行，避免卡 UI（节点不通时会等 5 秒）
            import threading
            def _verify():
                try:
                    connected, latency = verify_proxy_connection(timeout=5)
                    if connected and latency:
                        QTimer.singleShot(0, lambda: self.svc_latency_label.setText(f"延迟: {latency:.2f}s"))
                except Exception as e:
                    log.warning(f"验证代理连接异常: {e}")
            threading.Thread(target=_verify, daemon=True).start()
        else:
            self.line_progress.setText(msg)
            self._update_active_line()

    def _on_stop(self):
        set_system_proxy(False)
        self._update_sys_proxy_label()
        stop_quick()
        self._stop_realtime_monitor()
        self._stop_auto_line_timer()
        self.line_progress.setText("服务已停止")

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
        if browser_type == "unknown":
            reply = QMessageBox.question(
                self, "提示",
                f"检测到浏览器 {browser_name} 可能不支持命令行代理参数。\n\n"
                f"如无法翻墙，建议开启「全局系统代理」。\n\n"
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

    def _on_address_proxy_scope_toggled(self, scope, checked):
        if not checked:
            return
        # 2 选 1：手动取消其他 RadioButton 选中
        for rb in self.address_proxy_scope_group:
            if rb is not self.sender():
                rb._block_signal = True
                rb.setChecked(False)
                rb._block_signal = False
        self._save_setting("address_proxy_scope", scope)
        # 显示/隐藏单选下拉列表
        if hasattr(self, 'address_select_combo'):
            self.address_select_combo.setVisible(scope == "specified")
        if is_proxy_running():
            self._inject_all_rules()
            self.rules_restart_hint.setText("⚠ 代理范围已更改，重启服务后生效")
            self.rules_restart_hint.setVisible(True)
        log.info(f"地址代理范围: {'所有指定地址' if scope == 'all' else '单选指定地址'}")

    def _refresh_address_select_combo(self):
        """刷新单选指定地址下拉列表"""
        if not hasattr(self, 'address_select_combo'):
            return
        self.address_select_combo.blockSignals(True)
        self.address_select_combo.clear()
        type_labels = {"DOMAIN-SUFFIX": "指定域名", "DOMAIN": "指定网址", "IP-CIDR": "IP段"}
        for rule in (self._proxy_rules or []):
            label = type_labels.get(rule.get("type", ""), rule.get("type", ""))
            value = rule.get("value", "")
            self.address_select_combo.addItem(f"{label}: {value}")
        # 恢复选中
        selected_idx = self.settings.get("address_proxy_selected", 0)
        if self.address_select_combo.count() > 0:
            self.address_select_combo.setCurrentIndex(min(selected_idx, self.address_select_combo.count() - 1))
        self.address_select_combo.blockSignals(False)

    def _on_address_select_combo_changed(self, idx):
        """单选指定地址模式下拉列表变更"""
        if idx < 0:
            return
        self._save_setting("address_proxy_selected", idx)
        if is_proxy_running():
            self._inject_all_rules()
            self.rules_restart_hint.setText("⚠ 选中规则已更改，重启服务后生效")
            self.rules_restart_hint.setVisible(True)
        log.info(f"地址代理选中规则: 第{idx + 1}条")

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

    def _needs_system_proxy(self):
        """判断当前设置是否需要开启系统代理
        全局系统代理、地址代理、程序代理开启时均需要系统代理，
        以保证流量经过 mihomo 内核。
        TUN 模式下不需要系统代理（虚拟网卡接管全部流量）。
        """
        if self.settings.get("tun_enabled", False):
            return False
        if self.settings.get("global_proxy", False):
            return True
        if self.settings.get("address_proxy_enabled", False):
            return True
        if self.settings.get("custom_apps_enabled", False):
            return True
        return False

    def _on_address_proxy_toggled(self, checked):
        self._save_setting("address_proxy_enabled", checked)
        if is_proxy_running():
            self._inject_all_rules()
            # 管理系统代理：开启时设置，关闭时若不需要则取消
            if checked and self._needs_system_proxy():
                set_system_proxy(True)
                self._update_sys_proxy_label()
            elif not checked and not self._needs_system_proxy():
                set_system_proxy(False)
                self._update_sys_proxy_label()
            self.rules_restart_hint.setText("⚠ 地址代理设置已应用，重启服务后生效")
        else:
            self.rules_restart_hint.setText("⚠ 地址代理设置已保存，将在下次启动服务时生效")
        self.rules_restart_hint.setVisible(True)
        log.info(f"地址代理: {'开启' if checked else '关闭'}")

    def _on_tun_toggled(self, checked):
        """TUN 模式开关"""
        if checked and not self._is_admin:
            # 未获得管理员权限，阻止开启
            self.switch_tun.blockSignals(True)
            self.switch_tun.setChecked(False)
            self.switch_tun.blockSignals(False)
            QMessageBox.warning(self, "权限不足", "TUN 模式需要管理员权限运行。\n请以管理员身份重新启动本程序。")
            return
        self._save_setting("tun_enabled", checked)
        # TUN 开启时强制开启 sniffing（确保 DOMAIN 规则能匹配 HTTPS 流量）
        # 用户可手动关闭 sniffing，但 _inject_advanced_config 会在 TUN 模式下强制覆盖
        if hasattr(self, 'switch_sniffing'):
            self.switch_sniffing.blockSignals(True)
            self.switch_sniffing.setChecked(True)
            self.switch_sniffing.blockSignals(False)
            self.switch_sniffing.setEnabled(not checked)
            if checked:
                self.switch_sniffing.setStyleSheet("opacity: 0.6;")
            else:
                self.switch_sniffing.setStyleSheet("opacity: 1.0;")
        self.tun_admin_hint.setVisible(checked)
        if is_proxy_running():
            # 关键：TUN 模式切换时必须管理系统代理
            # - 开启 TUN：关闭系统代理（TUN 通过虚拟网卡接管全部流量，系统代理多余且冲突）
            # - 关闭 TUN：如果当前代理设置需要系统代理，重新开启
            if checked:
                set_system_proxy(False)
                self._update_sys_proxy_label()
                log.info("TUN 模式开启，已关闭系统代理（TUN 接管全部流量）")
            else:
                if self._needs_system_proxy():
                    set_system_proxy(True)
                    self._update_sys_proxy_label()
                    log.info("TUN 模式关闭，已恢复系统代理")
            self._inject_all_rules()
            self.tun_restart_hint.setText("⚠ TUN 设置已应用，重启服务后完全生效")
            self.tun_restart_hint.setVisible(True)
        else:
            self.tun_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
            self.tun_restart_hint.setVisible(True)
        self._update_proxy_ui_disabled_state()
        log.info(f"TUN 模式: {'开启' if checked else '关闭'}")

    def _on_tun_stack_toggled(self, stack, checked):
        """TUN 栈选择（2 选 1 互斥）"""
        if not checked:
            return
        # 手动取消其他 RadioButton 选中，确保互斥
        for rb in self.tun_stack_group:
            if rb is not self.sender():
                rb._block_signal = True
                rb.setChecked(False)
                rb._block_signal = False
        self._save_setting("tun_stack", stack)
        if is_proxy_running():
            self._inject_all_rules()
            self.tun_restart_hint.setVisible(True)
        log.info(f"TUN 栈: {stack}")

    def _on_tun_proxy_mode_toggled(self, mode, checked):
        """TUN 代理范围（3 选 1 互斥）：all / foreign / specified"""
        if not checked:
            return
        for rb in self.tun_range_group:
            if rb is not self.sender():
                rb._block_signal = True
                rb.setChecked(False)
                rb._block_signal = False
        self._save_setting("tun_proxy_mode", mode)
        if is_proxy_running():
            # TUN 模式下始终不需要系统代理（TUN 接管全部流量）
            # 切换范围时确保系统代理处于关闭状态
            set_system_proxy(False)
            self._update_sys_proxy_label()
            self._inject_all_rules()
            self.tun_restart_hint.setText("⚠ TUN 代理范围已应用，重启服务后完全生效")
            self.tun_restart_hint.setVisible(True)
        log.info(f"TUN 代理范围: {mode}")

    def _on_tls_fingerprint_changed(self):
        """TLS 指纹伪装选择"""
        fp = self.tls_fingerprint_combo.currentData()
        self._save_setting("tls_fingerprint", fp)
        if is_proxy_running():
            self._inject_all_rules()
            self.adv_restart_hint.setVisible(True)
        log.info(f"TLS 指纹: {fp}")

    def _on_sniffing_toggled(self, checked):
        """域名嗅探开关"""
        self._save_setting("sniffing_enabled", checked)
        if is_proxy_running():
            self._inject_all_rules()
            self.adv_restart_hint.setVisible(True)
        log.info(f"域名嗅探: {'开启' if checked else '关闭'}")

    def _on_global_proxy_toggled(self, checked):
        self._save_setting("global_proxy", checked)
        if is_proxy_running():
            if checked:
                set_system_proxy(True)
            elif not self._needs_system_proxy():
                set_system_proxy(False)
            self._update_sys_proxy_label()
            self._inject_all_rules()
            if checked:
                self.global_restart_hint.setVisible(False)
            else:
                self.global_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
                self.global_restart_hint.setVisible(True)
        else:
            self.global_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
            self.global_restart_hint.setVisible(True)
        self._update_proxy_ui_disabled_state()
        log.info(f"系统代理: {'开启' if checked else '关闭'}")

    def _on_global_proxy_mode_toggled(self, mode, checked):
        if not checked:
            return
        # 2 选 1：手动取消其他 RadioButton 选中
        for rb in self.global_proxy_mode_group:
            if rb is not self.sender():
                rb._block_signal = True
                rb.setChecked(False)
                rb._block_signal = False
        self._save_setting("global_proxy_mode", mode)
        if is_proxy_running():
            # 模式切换：注入所有规则（包括 GEOIP 规则和最终 MATCH 规则）
            self._inject_all_rules()
            self.global_restart_hint.setText("⚠ 代理模式已应用，重启服务后生效")
            self.global_restart_hint.setVisible(True)
        else:
            self.global_restart_hint.setText("⚠ 模式已保存，将在下次启动服务时生效")
            self.global_restart_hint.setVisible(True)
        mode_text = "全局系统代理" if mode == "all" else "绕过境内（仅代理境外）"
        log.info(f"系统代理模式: {mode_text}")

    def _update_proxy_ui_disabled_state(self):
        is_global = self.settings.get("global_proxy", False)
        is_tun = self.settings.get("tun_enabled", False)
        # 全局系统代理开启时禁用其他代理方式（注册表级别强制接管，规则失效）
        # TUN 模式开启时只禁用系统代理（地址/程序代理可与 TUN 协作，用规则过滤流量）
        disable_all_others = is_global
        disable_browser = is_global
        disable_system_proxy = is_tun  # TUN 模式下系统代理无意义
        if hasattr(self, 'switch_browser_proxy'):
            self.switch_browser_proxy.setEnabled(not disable_browser)
            self.switch_browser_proxy.setStyleSheet(
                f"opacity: {'0.5' if disable_browser else '1.0'}"
            )
        if hasattr(self, 'browser_proxy_scope_group') and self.browser_proxy_scope_group:
            for rb in self.browser_proxy_scope_group:
                rb.setEnabled(not disable_browser)
                rb.setStyleSheet(f"opacity: {'0.5' if disable_browser else '1.0'}")
        if hasattr(self, 'specified_browser_hint'):
            self.specified_browser_hint.setVisible(not disable_browser)
        if hasattr(self, 'switch_custom_apps'):
            self.switch_custom_apps.setEnabled(not disable_all_others)
            self.switch_custom_apps.setStyleSheet(
                f"opacity: {'0.5' if disable_all_others else '1.0'}"
            )
        if hasattr(self, 'custom_apps_scope_group') and self.custom_apps_scope_group:
            for rb in self.custom_apps_scope_group:
                rb.setEnabled(not disable_all_others)
                rb.setStyleSheet(f"opacity: {'0.5' if disable_all_others else '1.0'}")
        if hasattr(self, 'app_combo'):
            self.app_combo.setEnabled(not disable_all_others)
        if hasattr(self, 'add_app_btn'):
            self.add_app_btn.setEnabled(not disable_all_others)
            self.add_app_btn.setStyleSheet(f"opacity: {'0.5' if disable_all_others else '1.0'}")
        if hasattr(self, 'remove_app_btn'):
            self.remove_app_btn.setEnabled(not disable_all_others)
            self.remove_app_btn.setStyleSheet(f"opacity: {'0.5' if disable_all_others else '1.0'}")
        # 地址代理子卡片：TUN 模式下保留可用（地址规则可在 TUN 接管后过滤流量）
        if hasattr(self, 'switch_address_proxy'):
            self.switch_address_proxy.setEnabled(not disable_all_others)
            self.switch_address_proxy.setStyleSheet(
                f"opacity: {'0.5' if disable_all_others else '1.0'}"
            )
        if hasattr(self, 'address_proxy_scope_group') and self.address_proxy_scope_group:
            for rb in self.address_proxy_scope_group:
                rb.setEnabled(not disable_all_others)
                rb.setStyleSheet(f"opacity: {'0.5' if disable_all_others else '1.0'}")
        if hasattr(self, 'address_select_combo'):
            self.address_select_combo.setEnabled(not disable_all_others)
        if hasattr(self, 'rule_type_combo'):
            self.rule_type_combo.setEnabled(not disable_all_others)
            self.rule_type_combo.setStyleSheet(f"opacity: {'0.5' if disable_all_others else '1.0'}")
        if hasattr(self, 'rule_value_input'):
            self.rule_value_input.setEnabled(not disable_all_others)
            self.rule_value_input.setStyleSheet(f"opacity: {'0.5' if disable_all_others else '1.0'}")
        if hasattr(self, 'add_rule_btn'):
            self.add_rule_btn.setEnabled(not disable_all_others)
            self.add_rule_btn.setStyleSheet(f"opacity: {'0.5' if disable_all_others else '1.0'}")
        if hasattr(self, '_rule_list_widget'):
            self._rule_list_widget.setEnabled(not disable_all_others)
        if hasattr(self, 'rules_restart_hint') and disable_all_others:
            self.rules_restart_hint.setVisible(False)
        # TUN 模式下禁用系统代理开关本身（避免冲突），但代理模式（全/绕过境内）仍可选
        if hasattr(self, 'switch_global_proxy'):
            self.switch_global_proxy.setEnabled(not disable_system_proxy)
            self.switch_global_proxy.setStyleSheet(
                f"opacity: {'0.5' if disable_system_proxy else '1.0'}"
            )
        # 代理模式（all/foreign）始终可用：TUN 模式下「foreign」仍可注入 GEOIP 规则
        if hasattr(self, 'global_proxy_mode_group') and self.global_proxy_mode_group:
            for rb in self.global_proxy_mode_group:
                rb.setEnabled(True)
                rb.setStyleSheet("opacity: 1.0")
            # TUN 模式下调整标签：「全局系统代理」→「全局」（避免误导）
            if hasattr(self, 'all_mode_rb'):
                self.all_mode_rb.setText("全局" if is_tun else "全局系统代理")
        # TUN 代理范围 radio：仅 TUN 开启时可用
        if hasattr(self, 'tun_range_group') and self.tun_range_group:
            for rb in self.tun_range_group:
                rb.setEnabled(is_tun)
                rb.setStyleSheet(f"opacity: {'1.0' if is_tun else '0.5'}")

    def _on_browser_proxy_toggled(self, checked):
        self._save_setting("browser_proxy_enabled", checked)
        log.info(f"浏览器代理: {'开启' if checked else '关闭'}")

    def _on_browser_proxy_scope_toggled(self, scope, checked):
        if not checked:
            return
        # 2 选 1：手动取消其他 RadioButton 选中
        for rb in self.browser_proxy_scope_group:
            if rb is not self.sender():
                rb._block_signal = True
                rb.setChecked(False)
                rb._block_signal = False
        self._save_setting("browser_proxy_scope", scope)
        self._update_browser_proxy_scope_hint()
        log.info(f"浏览器代理范围: {'所有指定浏览器' if scope == 'all' else '单选指定浏览器'}")

    def _update_browser_proxy_scope_hint(self):
        scope = self.settings.get("browser_proxy_scope", "all")
        browser_path = self._get_browser_path()
        browser_name = os.path.basename(browser_path) if browser_path else "未选择"
        if scope == "all":
            self.specified_browser_hint.setText("所有指定浏览器都将通过代理访问网络")
        else:
            type_label = ""
            if browser_path and os.path.isfile(browser_path):
                bt = _detect_browser_type(browser_path)
                type_map = {"chromium": "Chromium内核", "firefox": "Firefox", "unknown": "未知内核"}
                type_label = f" [{type_map.get(bt, '未知内核')}]"
            self.specified_browser_hint.setText(f"当前选中浏览器: {browser_name}{type_label}" + (f" ({browser_path})" if browser_path else ""))

    def _on_custom_apps_toggled(self, checked):
        self._save_setting("custom_apps_enabled", checked)
        if is_proxy_running():
            # 重新注入规则（添加或移除 PROCESS-NAME 规则）
            self._inject_all_rules()
            # 管理系统代理：开启时设置，关闭时若不需要则取消
            if checked and self._needs_system_proxy():
                set_system_proxy(True)
                self._update_sys_proxy_label()
            elif not checked and not self._needs_system_proxy():
                set_system_proxy(False)
                self._update_sys_proxy_label()
            self.custom_restart_hint.setText("⚠ 程序代理设置已应用，重启服务后生效")
        else:
            self.custom_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
        self.custom_restart_hint.setVisible(True)
        log.info(f"指定程序代理: {'开启' if checked else '关闭'}")

    def _on_custom_apps_scope_toggled(self, scope, checked):
        if not checked:
            return
        # 2 选 1：手动取消其他 RadioButton 选中
        for rb in self.custom_apps_scope_group:
            if rb is not self.sender():
                rb._block_signal = True
                rb.setChecked(False)
                rb._block_signal = False
        self._save_setting("custom_apps_scope", scope)
        self._update_custom_apps_scope_hint()
        # 范围切换：重新注入规则（决定注入全部还是单条）
        if is_proxy_running():
            self._inject_all_rules()
            self.custom_restart_hint.setText("⚠ 代理范围已更改，重启服务后生效")
            self.custom_restart_hint.setVisible(True)
        log.info(f"程序代理范围: {scope}")

    def _update_custom_apps_scope_hint(self):
        mode = self.settings.get("custom_apps_scope", "all")
        if mode == "specified":
            self.specified_custom_apps_hint.setText("仅从已添加程序中选择的需要代理的程序会走代理")
        else:
            self.specified_custom_apps_hint.setText("")

    def _on_auto_open_browser_toggled(self, checked):
        self._save_setting("auto_open_browser", checked)
        log.info(f"检测线路后打开浏览器: {'开启' if checked else '关闭'}")

    def _on_realtime_reconnect_toggled(self, checked):
        self._save_setting("realtime_reconnect", checked)
        if checked and is_proxy_running():
            self._start_realtime_monitor()
        else:
            self._stop_realtime_monitor()

    def _on_realtime_interval_changed(self, value):
        self._save_setting("realtime_interval", value)
        if self.settings.get("realtime_reconnect", False) and is_proxy_running():
            self._start_realtime_monitor()
        log.info(f"实时检测间隔: {value}秒")

    def _on_always_update_config_toggled(self, checked):
        self._save_setting("always_update_config", checked)
        log.info(f"检测线路前更新配置: {'开启' if checked else '关闭'}")

    def _on_update_config_freq_changed(self, idx):
        value = self.update_config_freq_combo.itemData(idx)
        if value:
            self._save_setting("update_config_freq", value)
            freq_label = {"always": "每次", "daily": "每天", "weekly": "每周", "monthly": "每月"}.get(value, value)
            log.info(f"配置更新频率: {freq_label}")

    def _on_kernel_resize_start(self, event):
        self._kernel_resizing = True
        self._kernel_resize_start_y = event.globalPosition().toPoint().y()
        self._kernel_resize_start_h = self._kernel_scroll.height()

    def _on_kernel_resize_move(self, event):
        if not self._kernel_resizing:
            return
        delta = event.globalPosition().toPoint().y() - self._kernel_resize_start_y
        new_h = max(96, self._kernel_resize_start_h + delta)  # 最小3排
        self._kernel_scroll.setMinimumHeight(new_h)
        self._kernel_scroll.setMaximumHeight(new_h)

    def _on_kernel_resize_end(self, event):
        self._kernel_resizing = False

    def _on_add_proxy_rule(self):
        rule_type = self.rule_type_combo.currentData()
        value = self.rule_value_input.text().strip()
        if not value:
            return
        if any(r["type"] == rule_type and r["value"] == value for r in self._proxy_rules):
            QMessageBox.warning(self, "提示", "该规则已存在")
            return
        self._proxy_rules.append({"type": rule_type, "value": value})
        self._save_setting("proxy_rules", self._proxy_rules)
        self.rule_value_input.clear()
        self._refresh_proxy_rules_ui()
        self._refresh_address_select_combo()
        self.rules_restart_hint.setVisible(True)
        self._inject_all_rules()
        log.info(f"添加代理规则: {rule_type} {value}")

    def _on_remove_proxy_rule(self, idx):
        if 0 <= idx < len(self._proxy_rules):
            removed = self._proxy_rules.pop(idx)
            self._save_setting("proxy_rules", self._proxy_rules)
            self._refresh_proxy_rules_ui()
            self._refresh_address_select_combo()
            self.rules_restart_hint.setVisible(bool(self._proxy_rules))
            self._inject_all_rules()
            log.info(f"删除代理规则: {removed.get('type')} {removed.get('value')}")

    def _refresh_proxy_rules_ui(self):
        # 清空现有行
        for row in self._rule_rows:
            row.setParent(None)
            row.deleteLater()
        self._rule_rows.clear()
        # 重建
        type_labels = {"DOMAIN-SUFFIX": "指定域名", "DOMAIN": "指定网址", "IP-CIDR": "IP段"}
        type_colors = {"DOMAIN-SUFFIX": COLOR_BLUE, "DOMAIN": COLOR_GREEN, "IP-CIDR": COLOR_ORANGE}
        for i, rule in enumerate(self._proxy_rules):
            row = QFrame()
            row.setStyleSheet(f"border-bottom: 1px solid {COLOR_BORDER};")
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 4, 0, 4)
            rh.setSpacing(8)
            type_badge = QLabel(type_labels.get(rule["type"], rule["type"]))
            type_badge.setStyleSheet(
                f"font-size: 8pt; color: {type_colors.get(rule['type'], COLOR_TEXT)}; "
                f"background-color: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 3px; font-weight: bold;"
            )
            type_badge.setFixedWidth(72)
            rh.addWidget(type_badge)
            value_lbl = QLabel(rule["value"])
            value_lbl.setStyleSheet(f"font-size: 8pt; color: {COLOR_TEXT}; font-family: Consolas;")
            rh.addWidget(value_lbl, stretch=1)
            del_btn = QPushButton("删除")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setFixedSize(48, 22)
            del_btn.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; font-size: 7pt; "
                f"font-weight: bold; border-radius: 4px; border: none; }}"
                f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
            )
            del_btn.clicked.connect(lambda checked, idx=i: self._on_remove_proxy_rule(idx))
            rh.addWidget(del_btn)
            self._rule_list_layout.addWidget(row)
            self._rule_rows.append(row)

    def _inject_custom_rules(self):
        """在mihomo的config.yaml中注入用户自定义的代理规则
        若 address_proxy_enabled=False，则只保留空标记块，不注入实际规则。
        例外：TUN 白名单模式下，无论"地址代理"开关状态如何，都会注入规则
        （因为白名单本身就是通过规则 + MATCH,DIRECT 实现的）。
        """
        quick_dir = self.quick_dir
        if not quick_dir:
            return
        config_path = os.path.join(quick_dir, "config.yaml")
        if not os.path.isfile(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 先移除之前注入的规则（标记为 # YUNJI_CUSTOM_RULES）
            lines = content.split("\n")
            filtered = []
            skip = False
            for line in lines:
                if "# YUNJI_CUSTOM_RULES_START" in line:
                    skip = True
                    continue
                if "# YUNJI_CUSTOM_RULES_END" in line:
                    skip = False
                    continue
                if not skip:
                    filtered.append(line)
            content = "\n".join(filtered)
            # 构建自定义规则行
            custom_lines = ["  # YUNJI_CUSTOM_RULES_START"]
            # TUN 白名单模式下，无论"地址代理"开关状态如何，都需要注入规则
            # 因为白名单本身就是通过规则（DOMAIN-SUFFIX 等）+ MATCH,DIRECT 实现的
            is_tun_specified = (
                self.settings.get("tun_enabled", False)
                and self.settings.get("tun_proxy_mode", "all") == "specified"
            )
            if is_tun_specified or self.settings.get("address_proxy_enabled", True):
                # TUN 白名单模式：注入所有规则（白名单应包含所有用户添加的规则，
                # 不受地址代理的"所有/单选"范围设置影响）
                if is_tun_specified:
                    scope = "all"
                    selected_idx = 0
                else:
                    scope = self.settings.get("address_proxy_scope", "all")
                    selected_idx = self.settings.get("address_proxy_selected", 0)
                for i, rule in enumerate(self._proxy_rules or []):
                    rule_type = rule.get("type", "DOMAIN-SUFFIX")
                    value = rule.get("value", "").strip()
                    if value:
                        # 单选指定地址模式：只注入选中的那条规则
                        if scope == "specified" and i != selected_idx:
                            continue
                        custom_lines.append(f"  - {rule_type},{value},🚀 节点选择")
            if self.settings.get("custom_apps_enabled", False):
                custom_apps = self.settings.get("custom_apps", []) or []
                scope = self.settings.get("custom_apps_scope", "all")
                spec_idx = self.app_combo.currentIndex() if hasattr(self, "app_combo") else 0
                for i, app_path in enumerate(custom_apps):
                    if not app_path:
                        continue
                    # 单选指定程序模式：只注入选中的那条
                    if scope == "specified" and i != spec_idx:
                        continue
                    # mihomo 支持 PROCESS-NAME 规则匹配进程名
                    proc_name = os.path.basename(app_path)
                    custom_lines.append(f"  - PROCESS-NAME,{proc_name},🚀 节点选择")
            custom_lines.append("  # YUNJI_CUSTOM_RULES_END")
            # 在rules:后面插入
            rules_pattern = re.compile(r'^(rules:\s*)$', re.MULTILINE)
            if rules_pattern.search(content):
                content = rules_pattern.sub(r'\1\n' + "\n".join(custom_lines), content)
            else:
                content += "\nrules:\n" + "\n".join(custom_lines) + "\n"
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
            rule_count = len([r for r in (self._proxy_rules or []) if r.get("value", "").strip()])
            app_count = 0
            if self.settings.get("custom_apps_enabled", False):
                custom_apps = self.settings.get("custom_apps", []) or []
                scope = self.settings.get("custom_apps_scope", "all")
                spec_idx = self.app_combo.currentIndex() if hasattr(self, "app_combo") else 0
                for i, app_path in enumerate(custom_apps):
                    if not app_path:
                        continue
                    if scope == "specified" and i != spec_idx:
                        continue
                    app_count += 1
            if is_tun_specified or self.settings.get("address_proxy_enabled", True):
                log.info(f"已注入 {rule_count} 条地址代理规则")
            if self.settings.get("custom_apps_enabled", False):
                log.info(f"已注入 {app_count} 条程序代理规则（PROCESS-NAME）")
            else:
                log.info("程序代理已关闭，未注入程序规则")
        except Exception as e:
            log.error(f"注入自定义代理规则失败: {e}")

    def _inject_proxy_mode_rules(self):
        """根据当前代理模式注入 GEOIP 规则
        - 全局系统代理：
            - global_proxy_mode == "all"     : 不注入 GEOIP，所有流量走代理
            - global_proxy_mode == "foreign" : 注入 GEOIP,CN,DIRECT（仅代理境外）
        - TUN 模式：
            - tun_proxy_mode == "all"        : 不注入 GEOIP，TUN 接管全部流量
            - tun_proxy_mode == "foreign"    : 注入 GEOIP,CN,DIRECT（仅代理境外）
            - tun_proxy_mode == "specified"  : 不注入 GEOIP（白名单语义由 _inject_final_rule 注入 MATCH,DIRECT 实现）
        """
        quick_dir = self.quick_dir
        if not quick_dir:
            return
        config_path = os.path.join(quick_dir, "config.yaml")
        if not os.path.isfile(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 先移除之前注入的模式规则（标记为 # YUNJI_PROXY_MODE）
            lines = content.split("\n")
            filtered = []
            skip = False
            for line in lines:
                if "# YUNJI_PROXY_MODE_START" in line:
                    skip = True
                    continue
                if "# YUNJI_PROXY_MODE_END" in line:
                    skip = False
                    continue
                if not skip:
                    filtered.append(line)
            content = "\n".join(filtered)
            # 根据当前模式选择 mode 设置
            is_tun = self.settings.get("tun_enabled", False)
            if is_tun:
                mode = self.settings.get("tun_proxy_mode", "all")
                mode_label = "TUN"
            else:
                mode = self.settings.get("global_proxy_mode", "all")
                mode_label = "全局系统代理"
            mode_lines = ["  # YUNJI_PROXY_MODE_START"]
            if mode == "foreign":
                # 绕过境内：国内IP直连，其他走代理。
                # 关键安全网：GEOIP 规则依赖 geoip.metadb。若该库缺失（极旧 EXE /
                # 还原白名单漏掉 / 部署机异常），mihomo 加载 GEOIP 规则会 fatal 或
                # 挂起（尝试联网下载被墙的 GitHub MMDB）→ 内核不绑端口 → “代理未就绪”。
                # 此时退化为全局代理（不注入 GEOIP 规则），宁可境内流量也走代理，
                # 也绝不让内核起不来。
                geoip_path = os.path.join(quick_dir, "geoip.metadb")
                if not os.path.isfile(geoip_path):
                    log.warning("geoip.metadb 缺失，跳过 GEOIP,CN,DIRECT 注入"
                                "（退化为全局代理，避免内核因缺库致命）")
                else:
                    mode_lines.append("  - GEOIP,CN,DIRECT")
            mode_lines.append("  # YUNJI_PROXY_MODE_END")
            # 优先在自定义规则块之后插入，否则在 rules: 后插入
            custom_end_pattern = re.compile(r'^(\s*# YUNJI_CUSTOM_RULES_END\s*\n)', re.MULTILINE)
            rules_pattern = re.compile(r'^(rules:\s*)$', re.MULTILINE)
            if custom_end_pattern.search(content):
                content = custom_end_pattern.sub(
                    r'\1' + "\n".join(mode_lines) + "\n", content, count=1
                )
            elif rules_pattern.search(content):
                content = rules_pattern.sub(r'\1\n' + "\n".join(mode_lines), content)
            else:
                content += "\nrules:\n" + "\n".join(mode_lines) + "\n"
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
            if mode == "foreign":
                log.info(f"已注入 GEOIP,CN,DIRECT（{mode_label} · 绕过境内模式）")
            else:
                log.info(f"已注入代理模式规则（{mode_label} · {mode}）")
        except Exception as e:
            log.error(f"注入代理模式规则失败: {e}")

    def _inject_final_rule(self):
        """根据代理模式注入最终的 MATCH 规则
        需要注入 MATCH,DIRECT 的场景（白名单语义）：
        1. 仅地址代理（无全局、无 TUN）
        2. TUN 模式 + 代理范围 = "specified"（白名单：只代理指定地址/程序）
        其他场景：保持原始 MATCH 走代理
        """
        quick_dir = self.quick_dir
        if not quick_dir:
            return
        config_path = os.path.join(quick_dir, "config.yaml")
        if not os.path.isfile(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 先移除之前注入的最终规则
            lines = content.split("\n")
            filtered = []
            skip = False
            for line in lines:
                if "# YUNJI_FINAL_RULE_START" in line:
                    skip = True
                    continue
                if "# YUNJI_FINAL_RULE_END" in line:
                    skip = False
                    continue
                if not skip:
                    filtered.append(line)
            content = "\n".join(filtered)
            # 判断是否需要注入 MATCH,DIRECT
            global_proxy = self.settings.get("global_proxy", False)
            is_tun = self.settings.get("tun_enabled", False)
            tun_proxy_mode = self.settings.get("tun_proxy_mode", "all")
            address_proxy = self.settings.get("address_proxy_enabled", False)
            # 需要注入 MATCH,DIRECT 的两种场景：
            #   ① 仅地址代理（address_proxy + 无全局 + 无 TUN）→ 白名单
            #   ② TUN + 代理范围=specified → TUN 模式下白名单
            need_direct_match = (
                (address_proxy and not global_proxy and not is_tun)
                or (is_tun and tun_proxy_mode == "specified")
            )
            if need_direct_match:
                # 注释掉原始的 MATCH 规则（非 YUNJI 注入的）
                content = re.sub(
                    r'^(\s*-\s*MATCH\s*,.*)$',
                    r'# YUNJI_ORIGINAL_MATCH_DISABLED \1',
                    content,
                    flags=re.MULTILINE
                )
                final_lines = ["  # YUNJI_FINAL_RULE_START"]
                final_lines.append("  - MATCH,DIRECT")
                final_lines.append("  # YUNJI_FINAL_RULE_END")
                # 在代理模式规则块之后插入，否则在自定义规则块之后，否则在 rules: 后
                mode_end_pattern = re.compile(r'^(\s*# YUNJI_PROXY_MODE_END\s*\n)', re.MULTILINE)
                custom_end_pattern = re.compile(r'^(\s*# YUNJI_CUSTOM_RULES_END\s*\n)', re.MULTILINE)
                rules_pattern = re.compile(r'^(rules:\s*)$', re.MULTILINE)
                if mode_end_pattern.search(content):
                    content = mode_end_pattern.sub(
                        r'\1' + "\n".join(final_lines) + "\n", content, count=1
                    )
                elif custom_end_pattern.search(content):
                    content = custom_end_pattern.sub(
                        r'\1' + "\n".join(final_lines) + "\n", content, count=1
                    )
                elif rules_pattern.search(content):
                    content = rules_pattern.sub(r'\1\n' + "\n".join(final_lines), content)
                else:
                    content += "\nrules:\n" + "\n".join(final_lines) + "\n"
            else:
                # 恢复被注释的原始 MATCH 规则
                content = content.replace("# YUNJI_ORIGINAL_MATCH_DISABLED ", "")
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
            if need_direct_match:
                log.info("已注入 MATCH,DIRECT（仅地址代理模式），原始 MATCH 规则已注释")
            else:
                log.info("未注入 MATCH,DIRECT（全局代理或绕过境内模式，使用原始 MATCH 规则）")
        except Exception as e:
            log.error(f"注入最终规则失败: {e}")

    def _inject_all_rules(self):
        """注入所有 Yunji 规则：先自定义规则，后代理模式规则，最后最终规则，最后高级配置"""
        self._inject_custom_rules()
        self._inject_proxy_mode_rules()
        self._inject_final_rule()
        self._inject_advanced_config()

    def _inject_advanced_config(self):
        """注入高级配置：TUN模式、DNS、域名嗅探、TLS指纹伪装

        根据用户设置，在下载的远程 config.yaml 基础上覆盖/注入以下配置段：
        - tun_enabled=True 时注入 tun: 段和 dns: 段（TUN 模式必须配 DNS）
        - tls_fingerprint 非 none 时注入 global-client-fingerprint
        - sniffing_enabled 时注入 sniffing: 段
        """
        tun_enabled = self.settings.get("tun_enabled", False)
        tls_fingerprint = self.settings.get("tls_fingerprint", "none")
        sniffing_enabled = self.settings.get("sniffing_enabled", False)
        # 关键：TUN 模式必须开启 sniffing，否则 HTTPS 加密流量无法还原域名，
        # 所有 DOMAIN/DOMAIN-SUFFIX 规则都会失效，「仅指定」白名单模式直接变全 DIRECT
        if tun_enabled:
            sniffing_enabled = True

        # 如果没有任何高级配置需要注入，直接返回
        if not tun_enabled and tls_fingerprint == "none" and not sniffing_enabled:
            return

        quick_dir = self.quick_dir
        if not quick_dir:
            return
        config_path = os.path.join(quick_dir, "config.yaml")
        if not os.path.isfile(config_path):
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # ── 1. 移除远程配置中已有的高级段（避免重复/冲突）──
            content = self._remove_top_level_section(content, "tun")
            content = self._remove_top_level_section(content, "dns")
            content = self._remove_top_level_section(content, "sniffing")
            content = re.sub(r'^global-client-fingerprint\s*:.*$\n?', '', content, flags=re.MULTILINE)

            # ── 2. 构建高级配置段 ──
            advanced_blocks = []

            # TUN 模式配置
            # 关键修复（v2026.06.25）：补全 mihomo TUN 必需字段，并改用 redir-host + 境内外分流域
            # 旧配置缺陷：
            #   1) 缺 device/strict-route，部分内核版本无法创建虚拟网卡
            #   2) fake-ip 无 filter 白名单，境内服务（米家/苹果推送/内网）解析到 fake-ip 后路由错乱 → 外网打不开
            #   3) system 栈缺 auto-redirect，无法接管已建立连接
            if tun_enabled:
                tun_stack = self.settings.get("tun_stack", "gvisor")
                redirect_line = "  auto-redirect: true\n  auto-redirect-exclude: []\n" if tun_stack == "system" else ""
                tun_block = (
                    f"tun:\n"
                    f"  enable: true\n"
                    f"  stack: {tun_stack}\n"
                    f"  device: YunjiTun\n"
                    f"  dns-hijack:\n"
                    f"    - any:53\n"
                    f"    - tcp://any:53\n"
                    f"  auto-route: true\n"
                    f"  auto-detect-interface: true\n"
                    f"  strict-route: true\n"
                    f"{redirect_line}"
                )
                advanced_blocks.append(tun_block)

                dns_block = (
                    "dns:\n"
                    "  enable: true\n"
                    "  listen: 0.0.0.0:1053\n"
                    "  enhanced-mode: fake-ip\n"
                    "  fake-ip-range: 198.18.0.1/16\n"
                    "  nameserver:\n"
                    "    - https://dns.alidns.com/dns-query\n"
                    "    - https://doh.pub/dns-query\n"
                    "  fallback:\n"
                    "    - https://1.1.1.1/dns-query\n"
                    "    - https://dns.google/dns-query\n"
                    "  fallback-filter:\n"
                    "    geoip: true\n"
                    "    geoip-code: CN\n"
                    "  fake-ip-filter:\n"
                    "    - '+.lan'\n"
                    "    - '+.local'\n"
                    "    - '+.msftconnecttest.com'\n"
                    "    - '+.msftncsi.com'\n"
                    "    - 'localhost.ptlogin2.qq.com'\n"
                    "    - '+.push.apple.com'\n"
                    "    - '+.apple.com'\n"
                    "    - '+.market.xiaomi.com'\n"
                )
                advanced_blocks.append(dns_block)

            # 域名嗅探（从 IP 流量中还原域名，让规则更精准）
            if sniffing_enabled:
                sniffing_block = (
                    "sniffing:\n"
                    "  enable: true\n"
                    "  sniff:\n"
                    "    HTTP:\n"
                    "      ports: [80, 8080-8880]\n"
                    "      override-destination: true\n"
                    "    TLS:\n"
                    "      ports: [443, 8443]\n"
                    "    QUIC:\n"
                    "      ports: [443, 8443]\n"
                    "  force-domain:\n"
                    "    - '+'\n"
                    "  skip-domain:\n"
                    "    - 'Mijia Cloud'\n"
                    "    - '+.push.apple.com'\n"
                )
                advanced_blocks.append(sniffing_block)

            # TLS 指纹伪装（全局，覆盖所有代理节点）
            if tls_fingerprint != "none":
                advanced_blocks.append(f"global-client-fingerprint: {tls_fingerprint}\n")

            # ── 3. 在文件开头插入高级配置（确保 tun/dns 在其他段之前）──
            if advanced_blocks:
                content = content.lstrip('\n')
                advanced_text = "\n".join(advanced_blocks)
                content = advanced_text + "\n" + content

                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(content)
                log.info(f"已注入高级配置: tun={tun_enabled}, fingerprint={tls_fingerprint}, sniffing={sniffing_enabled}")
        except Exception as e:
            log.error(f"注入高级配置失败: {e}")

    def _remove_top_level_section(self, content, section_name):
        """移除 YAML 中的顶层段（如 tun:/dns:/sniffing:），直到下一个顶层键或文件末尾

        支持任意缩进级别（2/4/6 空格）的子项，避免漏掉嵌套列表
        （如 tun.dns-hijack 下的 `- any:53`）。
        """
        pattern = re.compile(
            r'^' + re.escape(section_name) + r'\s*:.*\n(?:[ \t]+[^\n]*\n)*',
            re.MULTILINE
        )
        return pattern.sub('', content)

    def _on_auto_line_switch_toggled(self, checked):
        self._save_setting("auto_line_switch", checked)
        if checked and is_proxy_running():
            self._start_auto_line_timer()
        else:
            self._stop_auto_line_timer()

    def _start_realtime_monitor(self):
        interval = self.settings.get("realtime_interval", 10)
        if hasattr(self, '_realtime_timer') and self._realtime_timer:
            self._realtime_timer.stop()
        self._realtime_timer = QTimer(self)
        self._realtime_timer.timeout.connect(self._realtime_check)
        self._realtime_timer.start(interval * 1000)

    def _stop_realtime_monitor(self):
        if hasattr(self, '_realtime_timer') and self._realtime_timer:
            self._realtime_timer.stop()
            self._realtime_timer = None

    def _realtime_check(self):
        if not is_proxy_running() and self.settings.get("proxy_enabled", False):
            if self.worker and self.worker.isRunning():
                return
            log.warning("实时检测: 代理断开，尝试切换到最快线路")
            self._cleanup_worker()
            # 断线时自动检测所有线路并切换到最快的
            self._auto_switch_on_disconnect()

    def _auto_switch_on_disconnect(self):
        """断线时自动切换到最快的『可用』线路；若无可用线路则不重启死配置（避免循环）。"""
        results = getattr(self, "line_results", {}) or {}
        if not results:
            # 没有线路数据时，直接启动代理
            if self.quick_dir:
                self._on_start()
            return
        latencies = getattr(self, "line_latencies", {}) or {}
        usable = getattr(self, "line_usable", {}) or {}

        # 只在“真正能代理境外”的线路里挑最快（best>0 即等价可用，避免误选死节点）
        candidates = [(n, latencies.get(n, -1.0))
                      for n in results
                      if usable.get(n) and latencies.get(n, -1.0) > 0]
        if candidates:
            candidates.sort(key=lambda x: x[1])
            best_line, best_latency = candidates[0]
            if best_line != self.current_line:
                log.info(f"断线切换: 从 {self.current_line} 切换到最快可用线路 {best_line} ({best_latency:.2f}s)")
                self._on_use_line(best_line)
            else:
                # 当前即最快可用线路：重连当前线路（瞬时断线恢复）
                log.info(f"断线恢复: 重连当前最快可用线路 {self.current_line}")
                self._on_use_line(self.current_line)
            return

        # 无可用线路：不重启死配置（否则会无限重连循环），明确提示用户。
        # 防抖：实时检测定时器周期性触发，60s 内只提示一次，避免日志刷屏。
        now = time.time()
        if now - getattr(self, "_last_auto_switch_ts", 0.0) < 60:
            return
        self._last_auto_switch_ts = now
        log.warning("断线自动切换失败: 当前无可用线路（内置免费节点可能已全部失效），"
                    "请到「上游管理」添加存活订阅，或手动选择一条线路")

    def _on_auto_start_toggled(self, checked):
        self._save_setting("auto_start", checked)
        log.info(f"启动时自动开启服务: {'开启' if checked else '关闭'}")

    def _on_interval_changed(self, value):
        self._save_setting("auto_line_interval", value)
        if self.settings.get("auto_line_switch", False) and is_proxy_running():
            self._start_auto_line_timer()
        log.info(f"自动检测间隔: {value}分钟")

    def _should_skip_config_update(self):
        freq = self.settings.get("update_config_freq", "always")
        if freq == "always":
            return False
        saved_date = self.settings.get("last_config_update_date", "")
        if not saved_date:
            return False
        if freq == "daily":
            return saved_date == date.today().isoformat()
        elif freq == "weekly":
            saved_dt = datetime.fromisoformat(saved_date)
            return (saved_dt.isocalendar()[1] == date.today().isocalendar()[1]
                    and saved_dt.year == date.today().year)
        elif freq == "monthly":
            saved_dt = datetime.fromisoformat(saved_date)
            return saved_dt.month == date.today().month and saved_dt.year == date.today().year
        return False

    def _config_needs_update(self):
        """检查是否需要更新配置（用于全部失败后的回退机制）"""
        freq = self.settings.get("update_config_freq", "always")
        if freq == "always":
            return True
        saved_date = self.settings.get("last_config_update_date", "")
        if not saved_date:
            return True
        if freq == "daily":
            return saved_date != date.today().isoformat()
        elif freq == "weekly":
            saved_dt = datetime.fromisoformat(saved_date)
            return not (saved_dt.isocalendar()[1] == date.today().isocalendar()[1]
                        and saved_dt.year == date.today().year)
        elif freq == "monthly":
            saved_dt = datetime.fromisoformat(saved_date)
            return not (saved_dt.month == date.today().month and saved_dt.year == date.today().year)
        return True

    def _on_test_btn_clicked(self):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.quit()
            self.worker.wait(3000)
            self.btn_test.setEnabled(True)
            self.btn_test.setText("🔍 检测线路")
            self.line_progress.setText("已取消")
            self.line_progress.setStyleSheet(f"color: {COLOR_ORANGE};")
            for name, info in self.line_rows.items():
                if info["status"].text() in ("检测中...", "更新配置...", "未检测"):
                    info["status"].setText("已取消")
                    info["status"].setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 9pt;")
            return
        self._on_test_lines()

    def _on_test_lines(self):
        if not self.quick_dir:
            QMessageBox.warning(self, "提示", "请先设置代理内核目录")
            return
        if self.worker and self.worker.isRunning():
            return
        self._cleanup_worker()
        # 用户手动发起新一轮检测：重置“全部失败后自动重测”的计数（仅允许自动重测 1 次）
        self._test_retry_count = 0
        if self._should_skip_config_update():
            self._start_line_test()
            return
        self.btn_test.setEnabled(True)
        self.btn_test.setText("⏹ 取消")
        for name, info in self.line_rows.items():
            info["status"].setText("更新配置...")
            info["status"].setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 9pt;")
            info["use_btn"].setEnabled(False)
        self.worker = ServiceWorker("update_config", quick_dir=self.quick_dir, current_line=self.current_line)
        self.worker.progress.connect(lambda t: self.line_progress.setText(t))
        self.worker.finished.connect(self._on_config_updated_then_test)
        self.worker.start()

    def _start_line_test(self):
        self.btn_test.setEnabled(True)
        self.btn_test.setText("⏹ 取消")
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

    def _on_retry_test_after_update(self, ok, msg):
        self.line_progress.setText(msg if ok else f"配置更新失败: {msg}")
        if not ok:
            self.btn_test.setEnabled(True)
            self.btn_test.setText("🔍 检测线路")
            for name, info in self.line_rows.items():
                info["status"].setText("更新配置失败，请检查网络")
                info["status"].setStyleSheet(f"color: #FF6B80; font-size: 9pt;")
            return
        log.info("配置更新成功，开始重新检测线路...")
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
        # Batch 3: 实时刷新健康度徽章
        self._refresh_line_health_badges()

    def _on_test_finished(self, ok, msg):
        self.btn_test.setEnabled(True)
        self.btn_test.setText("🔍 检测线路")
        try:
            if not ok:
                self.line_progress.setText(msg if msg else "检测失败")
                self.line_progress.setStyleSheet("font-size: 8pt; color: #FF6B80;")
                return

            # 检测完成后，重新注入所有 Yunji 规则（配置可能已被新数据覆盖）
            self._inject_all_rules()

            worker = self.worker
            if not worker or "results" not in worker.kwargs:
                self.line_progress.setText("检测结果异常")
                self.line_progress.setStyleSheet("font-size: 8pt; color: #FF6B80;")
                return

            results = list(worker.kwargs["results"])
            auto_switch = self.switch_auto_line.isChecked()

            for name, avg, best, count, data, usable in results:
                self.line_results[name] = data
                self.line_latencies[name] = best if best > 0 else -1.0
                self.line_usable[name] = bool(usable)
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

            # Batch 3: 刷新健康度徽章（刚写入了新记录）
            self._refresh_line_health_badges()

            valid = [r for r in results if r[1] >= 0]
            if valid:
                fastest = min(valid, key=lambda x: x[1])
                if fastest[0] in self.line_rows:
                    self.line_rows[fastest[0]]["status"].setText(f"最快 ✓ (平均{fastest[1]:.2f}s)")
                    self.line_rows[fastest[0]]["status"].setStyleSheet(f"color: {COLOR_ORANGE}; font-weight: bold; font-size: 9pt;")
                self.line_progress.setText(f"检测完成 - {len(valid)}条可用线路")
                self.line_progress.setStyleSheet(f"font-size: 8pt; color: {COLOR_GREEN};")
                if auto_switch and fastest[0] in self.line_rows and not self.worker.kwargs.get("_instant_winner"):
                    self._pending_browser_open = self.switch_auto_browser.isChecked()
                    self._on_use_line(fastest[0])
            else:
                # 全部失败后，最多再更新配置重测【一次】，避免节点普遍失效时无限循环
                self._test_retry_count = getattr(self, "_test_retry_count", 0) + 1
                if self._test_retry_count > 1:
                    self.line_progress.setText("检测完成 - 无可用线路（已重试 1 次仍失败）")
                    self.line_progress.setStyleSheet("font-size: 8pt; color: #FF6B80;")
                    return
                self.line_progress.setText("检测完成 - 无可用线路，正在更新配置并重测...")
                self.line_progress.setStyleSheet("font-size: 8pt; color: #FF6B80;")
                # 全部失败后，更新配置并重测一次
                self._save_setting("last_config_update_date", date.today().isoformat())
                self._cleanup_worker()
                self.btn_test.setEnabled(True)
                self.btn_test.setText("⏹ 取消")
                for name, info in self.line_rows.items():
                    info["status"].setText("更新配置...")
                    info["status"].setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 9pt;")
                    info["use_btn"].setEnabled(False)
                self.worker = ServiceWorker("update_config", quick_dir=self.quick_dir, current_line=self.current_line)
                self.worker.progress.connect(lambda t: self.line_progress.setText(t))
                self.worker.finished.connect(self._on_retry_test_after_update)
                self.worker.start()
        except Exception as e:
            import traceback
            log.error(f"检测结果显示异常: {e}\n{traceback.format_exc()}")
            self.line_progress.setText(f"检测出错: {e}")
            self.line_progress.setStyleSheet("font-size: 8pt; color: #FF6B80;")

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
        # 切换线路前先注入所有 Yunji 规则
        self._inject_all_rules()
        data = self.line_results.get(name)
        if data:
            self.worker = ServiceWorker("use_line", name=name, data=data, quick_dir=self.quick_dir,
                                        proxy_enabled=self.settings.get("proxy_enabled", False))
        else:
            self.worker = ServiceWorker("start", quick_dir=self.quick_dir, current_line=name)
        self.worker.line_selected.connect(self._on_line_selected)
        self.worker.progress.connect(lambda t: self.line_progress.setText(t))
        self.worker.finished.connect(self._on_use_line_finished)
        self.worker.start()

    def _on_use_line_finished(self, ok, msg):
        self._update_active_line()
        if ok:
            self.line_progress.setText(msg)
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
                self.app_combo.itemData(i) for i in range(self.app_combo.count())
            ]
            save_settings(self.settings)
            # 重新注入规则（添加新程序的 PROCESS-NAME 规则）
            if is_proxy_running():
                self._inject_all_rules()
                self.custom_restart_hint.setText("⚠ 添加程序已应用，重启服务后生效")
            else:
                self.custom_restart_hint.setText("⚠ 设置已保存，将在下次启动服务时生效")
            self.custom_restart_hint.setVisible(True)

    def _on_remove_app(self):
        idx = self.app_combo.currentIndex()
        if idx < 0:
            QMessageBox.information(self, "提示", "请先选择要删除的程序")
            return
        app_name = self.app_combo.itemText(idx)
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除「{app_name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.app_combo.removeItem(idx)
            self.settings["custom_apps"] = [
                self.app_combo.itemData(i) for i in range(self.app_combo.count())
            ]
            save_settings(self.settings)
            # 重新注入规则（移除程序的 PROCESS-NAME 规则）
            if is_proxy_running():
                self._inject_all_rules()
                self.custom_restart_hint.setText("⚠ 删除程序已应用，重启服务后生效")
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
            self.btn_edit_proxy.setText("✓  确认")
            self.btn_edit_proxy.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_GREEN}; color: #FFFFFF; "
                f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 4px 14px; }}"
                f"QPushButton:hover {{ background-color: #388E3C; }}"
            )
            self.btn_copy_proxy.setText("✕  取消")
            self.btn_copy_proxy.setStyleSheet(
                f"QPushButton {{ background-color: #666; color: #FFFFFF; "
                f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 4px 14px; }}"
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
        self.btn_edit_proxy.setText("✏  修改")
        self.btn_edit_proxy.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 4px 14px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        self.btn_copy_proxy.setText("📋  复制")
        self.btn_copy_proxy.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #FFFFFF; "
            f"font-size: 8pt; font-weight: bold; border-radius: 4px; border: none; padding: 4px 14px; }}"
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
        self.btn_copy_proxy.setText("✓  已复制")
        QTimer.singleShot(1500, lambda: self.btn_copy_proxy.setText("📋  复制"))

    def _on_browse_browser(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择浏览器", "", "可执行文件 (*.exe);;所有文件 (*.*)")
        if path:
            self._save_setting("browser_path", path)
            self.custom_browser_input.setText(path)
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
        self._update_browser_row_visibility()
        log.info(f"浏览器类型切换为: {browser_type}")

    def _update_browser_row_visibility(self):
        is_custom = self.settings.get("browser_type", "system") == "custom"
        self.system_browser_row_widget.setVisible(not is_custom)
        self.custom_browser_row_widget.setVisible(is_custom)

    def _on_custom_browser_input_changed(self, text):
        self._save_setting("browser_path", text.strip())

    def _on_system_browser_changed(self, idx):
        if idx >= 0:
            path = self.browser_combo.itemData(idx)
            self._save_setting("system_browser_path", path)

    def _on_export_log(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "保存日志", f"yunji_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "文本文件 (*.txt)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                log.info(f"日志已保存到: {path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存日志失败: {e}")

    def _on_copy_log(self):
        clipboard = QApplication.clipboard()
        text = self.log_text.toPlainText()
        if text:
            clipboard.setText(text)
            log.info("日志已复制到剪贴板")

    def _on_auto_scroll_toggled(self, checked):
        self._log_auto_scroll = checked
        if checked:
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _on_debug_mode_toggled(self, checked):
        self._save_setting("debug_mode", checked)
        if checked:
            self._start_debug_log()
            log.info("调试模式已开启，日志将实时写入文件")
        else:
            self._stop_debug_log()
            log.info("调试模式已关闭")

    def _start_debug_log(self):
        """开启调试模式：日志实时写入temp/log目录"""
        if not hasattr(self, '_debug_log_dir'):
            self._debug_log_dir = os.path.join(get_app_dir(), "temp", "log")
        os.makedirs(self._debug_log_dir, exist_ok=True)
        log_file = os.path.join(self._debug_log_dir, f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        try:
            self._debug_file_handler = logging.FileHandler(log_file, encoding='utf-8')
            self._debug_file_handler.setFormatter(_formatter)
            log.addHandler(self._debug_file_handler)
            self._debug_log_path = log_file
        except Exception as e:
            log.error(f"创建调试日志文件失败: {e}")

    def _stop_debug_log(self):
        """关闭调试模式：移除文件日志handler"""
        if hasattr(self, '_debug_file_handler') and self._debug_file_handler:
            try:
                log.removeHandler(self._debug_file_handler)
                self._debug_file_handler.close()
            except Exception:
                pass
            self._debug_file_handler = None

    def _startup_download_config(self):
        if not self.quick_dir:
            return
        current_line = self.current_line
        quick_dir = self.quick_dir
        proxy_enabled = self.settings.get("proxy_enabled", False)
        def do_download():
            try:
                _cfg_valid = _is_config_yaml_valid(quick_dir)
                if _cfg_valid:
                    # 本地配置合法 → 不自动覆盖（保留打包内置/上次可用的活节点配置）。
                    # 内置免费源(gitlabip / free9999/ipupdate)节点已全部失效，若启动期盲目用
                    # downloaded[0]（即死节点 线路1）覆盖，会把活配置换成死节点 → “代理未就绪/线路不通”。
                    # 需要更新请手动点击「更新配置 / 检测线路」。
                    log.info("本地配置合法，跳过启动时配置覆盖（如需更新请手动点击“更新配置/检测线路”）")
                    return
                # 本地配置缺失/损坏 → 才下载一份合法配置覆盖
                # 配置已损坏但代理在运行：先停掉旧内核，避免残留坏配置占着 7890，
                # 然后重新下载一份合法配置覆盖（否则坏配置会被持续复用 → 内核 fatal）。
                if (not _cfg_valid) and is_proxy_running():
                    log.warning("启动时检测到本地配置损坏，先停止旧内核并重新下载")
                    try:
                        stop_quick()
                    except Exception:
                        pass
                downloaded = download_all_configs()
                if downloaded:
                    selected = None
                    if current_line:
                        for n, d, _src in downloaded:
                            if n == current_line:
                                selected = (n, d)
                                break
                    if not selected:
                        selected = (downloaded[0][0], downloaded[0][1])
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
            f"QPushButton {{ background-color: #333; color: #888; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED}; color: #fff; }}"
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

    def _show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("关于")
        dlg.setFixedSize(500, 640)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.FramelessWindowHint)
        dlg._drag_pos = None
        def _dlg_mouse_press(event):
            if event.button() == Qt.MouseButton.LeftButton:
                dlg._drag_pos = event.globalPosition().toPoint() - dlg.pos()
        def _dlg_mouse_move(event):
            if dlg._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
                dlg.move(event.globalPosition().toPoint() - dlg._drag_pos)
        def _dlg_mouse_release(event):
            dlg._drag_pos = None
        dlg.mousePressEvent = _dlg_mouse_press
        dlg.mouseMoveEvent = _dlg_mouse_move
        dlg.mouseReleaseEvent = _dlg_mouse_release
        dlg.setStyleSheet(f"background-color: {COLOR_BG}; color: {COLOR_TEXT}; border-radius: 12px;")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(f"background-color: #111111; border: none; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 18, 24, 14)
        header_layout.setSpacing(4)

        icon_path = ""
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, "icon.png")
        else:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        if os.path.isfile(icon_path):
            icon_pixmap = QPixmap(icon_path)
            if not icon_pixmap.isNull():
                icon_scaled = icon_pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon_label = QLabel()
                icon_label.setPixmap(icon_scaled)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                header_layout.addWidget(icon_label)

        title = QLabel(BRAND_NAME)
        title.setStyleSheet("font-size: 17pt; font-weight: bold; color: #FFFFFF; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)

        subtitle = QLabel("一键智能代理 · 多线路自动切换 · 深色极简设计")
        subtitle.setStyleSheet("font-size: 9pt; color: rgba(255,255,255,0.75); border: none;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle)

        ver_label = QLabel(f"v{VERSION}")
        ver_label.setStyleSheet("font-size: 8pt; color: rgba(255,255,255,0.5); border: none;")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(ver_label)

        layout.addWidget(header)

        body = QFrame()
        body.setStyleSheet(f"background-color: {COLOR_BG}; border: none;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 12, 16, 10)
        body_layout.setSpacing(8)

        desc_frame = QFrame()
        desc_frame.setStyleSheet("background-color: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;")
        desc_layout = QVBoxLayout(desc_frame)
        desc_layout.setContentsMargins(14, 10, 14, 10)
        desc_layout.setSpacing(4)

        desc_text = QLabel(
            "基于 Clash (mihomo) 内核的 Windows 网络代理管理工具，零配置开箱即用。"
            "支持多线路智能切换、定时优化、浏览器代理，内置版本管理与自动更新。"
            "采用 Windows 硬链接实现多版本共存与秒级切换，GitHub/Gitee 双源并行分发确保下载稳定。"
            "EXE 自部署机制让新用户双击即可使用，首次运行自动下载最新代理内核。"
        )
        desc_text.setWordWrap(True)
        desc_text.setStyleSheet("font-size: 9pt; color: #bbb; border: none;")
        desc_layout.addWidget(desc_text)
        body_layout.addWidget(desc_frame)

        features_frame = QFrame()
        features_frame.setStyleSheet("background-color: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;")
        features_layout = QVBoxLayout(features_frame)
        features_layout.setContentsMargins(14, 10, 14, 10)
        features_layout.setSpacing(6)

        features_header = QLabel("核心功能")
        features_header.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_RED}; border: none;")
        features_layout.addWidget(features_header)

        feature_items = [
            ("一键启停", "开关代理只需一键，自动配置系统代理，支持全局代理与指定浏览器代理两种模式"),
            ("多线路智能切换", "并行测速自动选择最快线路，定时检测线路质量，网络波动时自动切换至最优节点"),
            ("定时优化", "可配置定时检测间隔，持续监控线路质量，确保始终使用最佳线路"),
            ("浏览器代理", "自动检测系统已安装浏览器，支持全局代理或仅对指定浏览器启用代理"),
            ("版本管理", "内置软件更新检查与下载，多版本共存，硬链接秒级切换，双源并行下载"),
            ("深色主题", "暗黑界面红色点缀，圆角卡片式布局，护眼专业，信息层次清晰"),
        ]
        for name, desc_text in feature_items:
            row = QHBoxLayout()
            row.setSpacing(6)
            name_label = QLabel(name)
            name_label.setFixedWidth(90)
            name_label.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_TEXT}; border: none;")
            row.addWidget(name_label)
            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("font-size: 8pt; color: #888; border: none;")
            row.addWidget(desc_label, stretch=1)
            features_layout.addLayout(row)

        body_layout.addWidget(features_frame)

        tech_frame = QFrame()
        tech_frame.setStyleSheet("background-color: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;")
        tech_layout = QVBoxLayout(tech_frame)
        tech_layout.setContentsMargins(14, 8, 14, 8)
        tech_layout.setSpacing(4)

        tech_row1 = QHBoxLayout()
        tech_row1.setSpacing(6)
        for label, value in [("内核", "Clash (mihomo)"), ("框架", "PyQt6"), ("协议", "GPL-3.0"), ("平台", "Windows")]:
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(f"font-size: 8pt; color: {COLOR_DIM}; border: none;")
            tech_row1.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet("font-size: 8pt; color: #bbb; border: none; font-weight: bold;")
            tech_row1.addWidget(val)
        tech_row1.addStretch()
        tech_layout.addLayout(tech_row1)

        arch_label = QLabel("架构: 硬链接版本切换 · 双源并行分发 · EXE 自部署 · 自动下载内核")
        arch_label.setStyleSheet(f"font-size: 8pt; color: #666; border: none;")
        tech_layout.addWidget(arch_label)

        body_layout.addWidget(tech_frame)

        body_layout.addStretch()

        bottom_frame = QFrame()
        bottom_frame.setStyleSheet("background-color: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;")
        bottom_layout = QVBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(14, 8, 14, 8)
        bottom_layout.setSpacing(6)

        copyright_label = QLabel("Copyright © 2026 云集智能 (yunjii). All rights reserved.")
        copyright_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_DIM}; border: none;")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(copyright_label)

        link_row = QHBoxLayout()
        link_row.setSpacing(4)
        link_row.addStretch()
        for text, url in [("官方网站", "https://yunjii.cn"), ("GitHub", "https://github.com/yunjii-cn/ip"), ("Gitee", "https://gitee.com/yunjii/ip"), ("问题反馈", "https://github.com/yunjii-cn/ip/issues")]:
            link = QLabel(f'<a href="{url}" style="color: #4a9eff; text-decoration: none; font-size: 9pt;">{text}</a>')
            link.setStyleSheet("border: none;")
            link.setOpenExternalLinks(True)
            link_row.addWidget(link)
            if text != "问题反馈":
                sep = QLabel("|")
                sep.setStyleSheet(f"font-size: 8pt; color: #333; border: none;")
                link_row.addWidget(sep)
        link_row.addStretch()
        bottom_layout.addLayout(link_row)

        body_layout.addWidget(bottom_frame)

        btn_close = QPushButton("关闭")
        btn_close.setFixedSize(80, 30)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_RED}; color: #fff; border: none; border-radius: 6px; "
            f"font-size: 9pt; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
        )
        btn_close.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        body_layout.addLayout(btn_row)

        layout.addWidget(body, stretch=1)

        dlg.exec()

    def _toggle_expand_all(self):
        if self._ver_display_mode == "list":
            self._ver_display_mode = "detail"
            if self._ver_expand_btn is not None:
                self._ver_expand_btn.setText("列表模式")
        else:
            self._ver_display_mode = "list"
            if self._ver_expand_btn is not None:
                self._ver_expand_btn.setText("详情模式")
        self._render_active_tab()

    def _render_stable_tab(self):
        self._render_stable_versions(self._ver_stable_data, self._ver_current_version)

    def _render_git_tab(self):
        git_header = QFrame()
        git_header.setStyleSheet(f"background-color: transparent; border: none;")
        git_header_layout = QHBoxLayout(git_header)
        git_header_layout.setContentsMargins(4, 6, 4, 2)
        git_title = QLabel("🔧 Git版本历史")
        git_title.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_BLUE_LIGHT}; border: none;")
        git_header_layout.addWidget(git_title)
        git_header_layout.addStretch()
        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedSize(60, 24)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(
            f"QPushButton {{ background-color: #333; color: #ccc; border: 1px solid #444; border-radius: 4px; "
            f"font-size: 9pt; }}"
            f"QPushButton:hover {{ background-color: #444; color: #fff; border-color: #555; }}"
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
            self._update_ver_scroll_geometry()
            return

        detail = QFrame()
        detail.setObjectName("_detail")
        detail.setStyleSheet("background-color: #111; border: none; border-top: 1px solid #2a2a2a;")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(36, 6, 12, 8)
        detail_layout.setSpacing(3)

        if card_type == "stable":
            git_commit = data.get("git_commit", "")
            if git_commit:
                lbl = QLabel(f"commit: {git_commit}")
                lbl.setStyleSheet(f"font-family: Consolas; font-size: 9pt; color: #aaa; border: none;")
                detail_layout.addWidget(lbl)
            changes = data.get("changes", [])
            if changes:
                for idx, ch in enumerate(changes, 1):
                    lbl = QLabel(f"{idx}. {ch}")
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet(f"font-size: 9pt; color: #bbb; border: none;")
                    detail_layout.addWidget(lbl)
            else:
                lbl = QLabel("暂无修改记录")
                lbl.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM}; border: none;")
                detail_layout.addWidget(lbl)
        else:
            message = data.get("message", "")
            msg_lines = message.split("\n") if message else []
            for idx, line in enumerate(msg_lines, 1):
                line = line.strip()
                if line:
                    lbl = QLabel(f"{idx}. {line}")
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet(f"font-size: 9pt; color: #bbb; border: none;")
                    detail_layout.addWidget(lbl)
            author = data.get("author", "")
            if author:
                lbl2 = QLabel(f"author: {author}")
                lbl2.setStyleSheet(f"font-size: 9pt; color: #aaa; border: none;")
                detail_layout.addWidget(lbl2)

        card_layout = card.layout()
        card_layout.addWidget(detail)
        self._update_ver_scroll_geometry()

    def _toggle_current_card_detail(self, card, changes):
        detail_widget = card.findChild(QWidget, "_detail")
        if detail_widget is not None:
            detail_widget.deleteLater()
            self._update_ver_scroll_geometry()
            return

        detail = QFrame()
        detail.setObjectName("_detail")
        detail.setStyleSheet("background-color: #0d2d1a; border: none; border-top: 1px solid #1a4a2a;")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(36, 6, 12, 8)
        detail_layout.setSpacing(3)

        if changes:
            for idx, ch in enumerate(changes, 1):
                lbl = QLabel(f"{idx}. {ch}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet("font-size: 9pt; color: #8a8; border: none;")
                detail_layout.addWidget(lbl)
        else:
            lbl = QLabel("暂无修改记录")
            lbl.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM}; border: none;")
            detail_layout.addWidget(lbl)

        card_layout = card.layout()
        card_layout.addWidget(detail)
        self._update_ver_scroll_geometry()

    def _update_ver_scroll_geometry(self):
        """版本展开/收起后更新滚动区域内容几何信息，确保滚动条正确显示。"""
        if hasattr(self, '_ver_scroll') and self._ver_scroll:
            content = self._ver_scroll.widget()
            if content:
                content.updateGeometry()
                content.adjustSize()

    def _render_stable_versions(self, all_versions, current_version):
        self._ver_all_versions = all_versions
        is_detail = self._ver_display_mode == "detail"

        current_in_list = any(v["version"] == current_version for v in all_versions)
        if not current_in_list and current_version:
            current_changes = []
            vh_path = os.path.join(get_app_dir(), "versions.json")
            if os.path.isfile(vh_path):
                try:
                    with open(vh_path, "r", encoding="utf-8") as f:
                        vh = json.load(f)
                    for entry in vh:
                        if entry.get("version") == current_version:
                            current_changes = entry.get("changes", [])
                            break
                except Exception:
                    pass

            card = QFrame()
            card.setStyleSheet("background-color: #1a4a2a; border: 1px solid #2a6a3a; border-radius: 8px;")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(0)

            row = QFrame()
            row.setStyleSheet("background-color: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(8)

            ver_label = QLabel(f"v{current_version}")
            ver_label.setStyleSheet(f"font-family: Consolas; font-size: 11pt; font-weight: bold; color: #4CAF50; border: none;")
            row_layout.addWidget(ver_label)

            row_layout.addStretch(1)

            status_label = QLabel("● 使用中")
            status_label.setFixedWidth(90)
            status_label.setStyleSheet(f"font-size: 8pt; color: #4CAF50; border: none; font-weight: bold;")
            row_layout.addWidget(status_label)

            card_layout.addWidget(row)

            has_detail = bool(current_changes)
            if has_detail:
                row.setCursor(Qt.CursorShape.PointingHandCursor)
                row.mousePressEvent = lambda event, c=card, ch=current_changes: self._toggle_current_card_detail(c, ch)

            if is_detail and has_detail:
                detail = QFrame()
                detail.setObjectName("_detail")
                detail.setStyleSheet("background-color: #0d2d1a; border: none; border-top: 1px solid #1a4a2a;")
                detail_layout = QVBoxLayout(detail)
                detail_layout.setContentsMargins(36, 6, 12, 8)
                detail_layout.setSpacing(3)
                for idx, ch in enumerate(current_changes, 1):
                    lbl = QLabel(f"{idx}. {ch}")
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet("font-size: 9pt; color: #8a8; border: none;")
                    detail_layout.addWidget(lbl)
                card_layout.addWidget(detail)

            self._ver_scroll_layout.addWidget(card)

        if not all_versions:
            lbl = QLabel("暂无版本信息")
            lbl.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM}; border: none;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._ver_scroll_layout.addWidget(lbl)
            return

        is_detail = self._ver_display_mode == "detail"

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
                row_bg = "#1a1a1a"
                border_color = "#333"
            elif is_available:
                row_bg = "#1a1a1a"
                border_color = "#2d2d2d"
            else:
                row_bg = "#141414"
                border_color = "#222"

            card = QFrame()
            card.setProperty("card_bg", row_bg)
            card.setStyleSheet(
                f"background-color: {row_bg}; border: 1px solid {border_color}; border-radius: 8px;"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(0)

            row = QFrame()
            row.setStyleSheet(f"background-color: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(8)

            ver_color = "#4CAF50" if is_current else (COLOR_TEXT if (is_remote_new or is_available) else COLOR_DIM)
            ver_label = QLabel(f"v{ver}")
            ver_label.setStyleSheet(f"font-family: Consolas; font-size: 11pt; font-weight: bold; color: {ver_color}; border: none;")
            row_layout.addWidget(ver_label)

            row_layout.addStretch(1)

            status_label = QLabel("")
            status_label.setFixedWidth(90)
            if is_current:
                status_label.setText("● 当前版本")
                status_label.setStyleSheet(f"font-size: 8pt; color: #4CAF50; border: none; font-weight: bold;")
            elif is_remote_new:
                status_label.setText("远程新版")
                status_label.setStyleSheet(f"font-size: 8pt; color: #42A5F5; border: none;")
            elif is_available and exe_info:
                size_text = f" {exe_info.get('size_mb', '')}MB" if exe_info.get("size_mb") else ""
                status_label.setText(f"已下载{size_text}")
                status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_ORANGE}; border: none;")
            elif v.get("remote_info", {}).get("filename"):
                status_label.setText("可下载")
                status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_BLUE_LIGHT}; border: none;")
            else:
                status_label.setText("未提供")
                status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_DIM}; border: none;")
            row_layout.addWidget(status_label)

            btn_style_blue = (
                f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; border: none; border-radius: 4px; "
                f"font-size: 8pt; font-weight: bold; padding: 3px 8px; }}"
                f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
            )

            btn_style_red = (
                f"QPushButton {{ background-color: {COLOR_RED}; color: #fff; border: none; border-radius: 4px; "
                f"font-size: 8pt; font-weight: bold; padding: 3px 8px; }}"
                f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
            )

            if is_available and exe_info and not is_current:
                switch_btn = QPushButton("切换")
                switch_btn.setFixedSize(50, 24)
                switch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                switch_btn.setStyleSheet(btn_style_red)
                exe_path = exe_info["path"]
                git_commit = v.get("git_commit", "")
                switch_btn.clicked.connect(lambda checked, p=exe_path, gc=git_commit: self._switch_to_exe(p, gc))
                row_layout.addWidget(switch_btn)
            elif is_remote_new or (v.get("remote_info", {}).get("filename") and not is_available):
                dl_btn = QPushButton("下载")
                dl_btn.setFixedSize(50, 24)
                dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                dl_btn.setStyleSheet(btn_style_red)
                rinfo = v.get("remote_info")
                dl_btn.clicked.connect(lambda checked, ri=rinfo: self._on_download_version(ri))
                row_layout.addWidget(dl_btn)
                cancel_btn = QPushButton("取消")
                cancel_btn.setFixedSize(50, 24)
                cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                cancel_btn.setStyleSheet(btn_style_red)
                cancel_btn.hide()
                cancel_btn.clicked.connect(self._on_cancel_download)
                row_layout.addWidget(cancel_btn)
                v["_dl_btn"] = dl_btn
                v["_cancel_btn"] = cancel_btn

            card_layout.addWidget(row)

            has_detail = bool(changes) or bool(v.get("git_commit", ""))
            if has_detail:
                v_data = v
                row.setCursor(Qt.CursorShape.PointingHandCursor)
                row.mousePressEvent = lambda event, c=card, d=v_data: self._toggle_card_detail(c, d, "stable")

            if is_detail and has_detail:
                detail = QFrame()
                detail.setObjectName("_detail")
                detail.setStyleSheet("background-color: #111; border: none; border-top: 1px solid #2a2a2a;")
                detail_layout = QVBoxLayout(detail)
                detail_layout.setContentsMargins(36, 6, 12, 8)
                detail_layout.setSpacing(3)

                git_commit = v.get("git_commit", "")
                if git_commit:
                    lbl = QLabel(f"commit: {git_commit}")
                    lbl.setStyleSheet(f"font-family: Consolas; font-size: 9pt; color: #aaa; border: none;")
                    detail_layout.addWidget(lbl)

                if changes:
                    for idx, ch in enumerate(changes, 1):
                        lbl = QLabel(f"{idx}. {ch}")
                        lbl.setWordWrap(True)
                        lbl.setStyleSheet(f"font-size: 9pt; color: #bbb; border: none;")
                        detail_layout.addWidget(lbl)
                else:
                    lbl = QLabel("暂无修改记录")
                    lbl.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM}; border: none;")
                    detail_layout.addWidget(lbl)

                card_layout.addWidget(detail)

            self._ver_scroll_layout.addWidget(card)

    def _render_git_history(self, commits):
        if not commits:
            lbl = QLabel("暂无开发动态")
            lbl.setStyleSheet(f"font-size: 9pt; color: {COLOR_DIM}; border: none;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._ver_scroll_layout.addWidget(lbl)
            return

        is_detail = self._ver_display_mode == "detail"
        stable_exes = self._list_stable_exes()
        exe_versions = {e["version"]: e for e in stable_exes}

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

            row_bg = "#1a1a1a"
            border_color = "#2d2d2d"

            card = QFrame()
            card.setProperty("card_bg", row_bg)
            card.setStyleSheet(
                f"background-color: {row_bg}; border: 1px solid {border_color}; border-radius: 8px;"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(0)

            row = QFrame()
            row.setStyleSheet(f"background-color: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(8)

            ver_label = QLabel(sha)
            ver_label.setFixedWidth(120)
            ver_label.setStyleSheet(f"font-family: Consolas; font-size: 9pt; font-weight: bold; color: #42A5F5; border: none;")
            row_layout.addWidget(ver_label)

            desc_text = msg_first_line
            if not is_detail and len(desc_text) > 40:
                desc_text = desc_text[:37] + "..."

            desc_label = QLabel(desc_text if desc_text else "暂无描述")
            if not is_detail:
                desc_label.setWordWrap(False)
            else:
                desc_label.setWordWrap(True)
            desc_color = "#ccc" if desc_text else COLOR_DIM
            desc_label.setStyleSheet(f"font-size: 9pt; color: {desc_color}; border: none;")
            row_layout.addWidget(desc_label, stretch=1)

            status_label = QLabel("")
            status_label.setFixedWidth(90)
            if date_str:
                status_label.setText(date_str)
                status_label.setStyleSheet(f"font-size: 8pt; color: #aaa; border: none;")
            else:
                status_label.setText("—")
                status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_DIM}; border: none;")
            row_layout.addWidget(status_label)

            btn_style_red = (
                f"QPushButton {{ background-color: {COLOR_RED}; color: #fff; border: none; border-radius: 4px; "
                f"font-size: 8pt; font-weight: bold; padding: 3px 8px; }}"
                f"QPushButton:hover {{ background-color: {COLOR_RED_LIGHT}; }}"
            )

            if matched_exe:
                switch_btn = QPushButton("切换")
                switch_btn.setFixedSize(50, 24)
                switch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                switch_btn.setStyleSheet(btn_style_red)
                exe_path = matched_exe["path"]
                switch_btn.clicked.connect(lambda checked, p=exe_path: self._switch_to_exe(p, ""))
                row_layout.addWidget(switch_btn)

            card_layout.addWidget(row)

            has_detail = len(message.split("\n")) > 1 or bool(author)
            if has_detail:
                row.setCursor(Qt.CursorShape.PointingHandCursor)
                row.mousePressEvent = lambda event, c=card, d=commit: self._toggle_card_detail(c, d, "git")

            if is_detail and has_detail:
                detail = QFrame()
                detail.setObjectName("_detail")
                detail.setStyleSheet("background-color: #111; border: none; border-top: 1px solid #2a2a2a;")
                detail_layout = QVBoxLayout(detail)
                detail_layout.setContentsMargins(132, 6, 12, 8)
                detail_layout.setSpacing(3)

                msg_lines = message.split("\n") if message else []
                for line in msg_lines:
                    line = line.strip()
                    if line:
                        lbl = QLabel(f"· {line}")
                        lbl.setWordWrap(True)
                        lbl.setStyleSheet(f"font-size: 9pt; color: #bbb; border: none;")
                        detail_layout.addWidget(lbl)

                if author:
                    lbl2 = QLabel(f"author: {author}")
                    lbl2.setStyleSheet(f"font-size: 9pt; color: #aaa; border: none;")
                    detail_layout.addWidget(lbl2)

                card_layout.addWidget(detail)

            self._ver_scroll_layout.addWidget(card)

    def _get_local_gitlog(self):
        """读取本地开发动态，优先从本地文件，回退到内嵌资源。"""
        path = os.path.join(get_app_dir(), "gitlog.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        # 回退到内嵌资源
        try:
            base = getattr(sys, '_MEIPASS', '')
            if base:
                bundled = os.path.join(base, "gitlog.json")
                if os.path.exists(bundled):
                    with open(bundled, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception:
            pass
        # 开发模式：从本地git log读取
        if not getattr(sys, 'frozen', False):
            try:
                project_root = os.path.dirname(_find_dev_dir())
                result = subprocess.run(
                    ["git", "log", "--pretty=format:%H|%an|%ai|%s", "--no-merges", "-100"],
                    capture_output=True, text=True, cwd=project_root, timeout=10
                )
                if result.returncode == 0:
                    commits = []
                    for line in result.stdout.strip().split("\n"):
                        if not line.strip():
                            continue
                        parts = line.split("|", 3)
                        if len(parts) == 4:
                            sha, author, date, message = parts
                            commits.append({
                                "sha": sha[:7],
                                "author": author,
                                "date": date[:10],
                                "message": message,
                            })
                    if commits:
                        return commits
            except Exception:
                pass
        return []

    def _fetch_remote_commits(self):
        """加载开发动态数据。优先从本地gitlog.json读取，回退到内嵌资源。
        检查更新时从远程获取覆盖本地。
        """
        def do_fetch():
            commits = self._get_local_gitlog()
            self._ver_git_data = commits
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
        ver_dir = os.path.join(dev_dir, _CFG["paths"]["ver"])
        if not os.path.isdir(ver_dir):
            return []
        exes = []
        for f in os.listdir(ver_dir):
            if f.endswith(".exe") and BRAND_NAME in f:
                path = os.path.join(ver_dir, f)
                m = re.search(r'v(\d+\.\d+\.\d+\.\d+)', f)
                ver = m.group(1) if m else "unknown"
                size_mb = round(os.path.getsize(path) / (1024 * 1024), 1)
                exes.append({"filename": f, "path": path, "version": ver, "size_mb": size_mb})
        exes.sort(key=lambda x: x["version"], reverse=True)
        return exes

    def _get_local_version_history(self):
        path = os.path.join(get_app_dir(), "versions.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        try:
            base = sys._MEIPASS
            bundled = os.path.join(base, "versions.json")
            if os.path.exists(bundled):
                with open(bundled, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _on_version_data_ready(self):
        self._render_active_tab()
        if self._ver_status_label is not None:
            count = len(self._ver_stable_data)
            hist = len(self._ver_git_data)
            self._ver_status_label.setText(f"版本 {count} 个 | 版本历史 {hist} 条")

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

            def _urlopen_with_proxy(req, timeout=6):
                if is_proxy_running():
                    try:
                        proxy_handler = urllib.request.ProxyHandler({
                            'http': f'http://{PROXY_URL}',
                            'https': f'http://{PROXY_URL}',
                        })
                        opener = urllib.request.build_opener(
                            urllib.request.HTTPSHandler(context=ctx),
                            proxy_handler,
                        )
                        return opener.open(req, timeout=timeout)
                    except Exception:
                        pass
                try:
                    return urllib.request.urlopen(req, timeout=timeout, context=ctx)
                except Exception:
                    pass
                proxy_handler = urllib.request.ProxyHandler({
                    'http': f'http://{PROXY_URL}',
                    'https': f'http://{PROXY_URL}',
                })
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx),
                    proxy_handler,
                )
                return opener.open(req, timeout=timeout)

            _fallback_paths = [VERSION_JSON_PATH]
            fallback_dir = os.path.dirname(VERSION_JSON_PATH)
            if fallback_dir != "ver":
                _fallback_paths.append(VERSION_JSON_PATH.replace(fallback_dir, "ver", 1))

            result = [None, None]

            def try_gitee():
                for vj_path in _fallback_paths:
                    try:
                        gitee_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/contents/{vj_path}?ref=main"
                        if GITEE_TOKEN:
                            gitee_url += f"&access_token={GITEE_TOKEN}"
                        req = urllib.request.Request(gitee_url, headers={"User-Agent": "Mozilla/5.0"})
                        with _urlopen_with_proxy(req, timeout=6) as resp:
                            raw = resp.read().decode()
                        api_data = json.loads(raw)
                        if isinstance(api_data, list):
                            file_data = api_data[0] if api_data else {}
                        else:
                            file_data = api_data
                        import base64
                        content_b64 = file_data.get("content", "")
                        result[0] = (json.loads(base64.b64decode(content_b64).decode("utf-8")), "gitee")
                        return
                    except Exception:
                        continue
                result[0] = (None, None)

            def try_github():
                for vj_path in _fallback_paths:
                    try:
                        github_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{vj_path}?ref=main"
                        gh_headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"}
                        if GITHUB_TOKEN:
                            gh_headers["Authorization"] = f"token {GITHUB_TOKEN}"
                        req = urllib.request.Request(github_url, headers=gh_headers)
                        with _urlopen_with_proxy(req, timeout=6) as resp:
                            raw = resp.read().decode()
                        api_data = json.loads(raw)
                        import base64
                        content_b64 = api_data.get("content", "")
                        result[1] = (json.loads(base64.b64decode(content_b64).decode("utf-8")), "github")
                        return
                    except Exception:
                        pass
                    try:
                        github_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{vj_path}"
                        req = urllib.request.Request(github_url, headers={"User-Agent": "Mozilla/5.0"})
                        with _urlopen_with_proxy(req, timeout=6) as resp:
                            result[1] = (json.loads(resp.read().decode()), "github")
                            return
                    except Exception:
                        continue
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
                    self._ver_info_text = "❌ 无法连接远程仓库，请检查网络或开启代理后重试"
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
                    is_new = (ver_num != current_version and ver_num not in exe_versions and bool(rinfo.get("filename")))
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
        ver_dir = os.path.join(dev_dir, _CFG["paths"]["ver"])
        os.makedirs(ver_dir, exist_ok=True)
        save_path = os.path.join(ver_dir, filename)
        if os.path.isfile(save_path):
            self._switch_to_exe(save_path, remote_info.get("git_commit", ""))
            return
        ver = remote_info.get('version', '')
        urls = []
        github_filename = re.sub(r'[^\x00-\x7F]+', '', filename)
        if not github_filename:
            github_filename = f"YunjiIP-v{ver}.exe"
        urls.append(f"https://github.com/{GITHUB_REPO}/releases/download/v{ver}/{urllib.parse.quote(github_filename)}")
        gitee_url = f"https://gitee.com/{GITEE_REPO}/releases/download/v{ver}/{urllib.parse.quote(filename)}"
        if GITEE_TOKEN:
            gitee_url += f"?access_token={GITEE_TOKEN}"
        urls.append(gitee_url)
        if hasattr(self, '_download_worker') and self._download_worker is not None and self._download_worker.isRunning():
            if hasattr(self, '_download_paused') and self._download_paused:
                self._download_paused = False
                self._set_dl_btn_state(True, remote_info)
                self._download_worker.resume()
                return
            else:
                self._download_paused = True
                self._set_dl_btn_state(False, remote_info)
                if self._ver_status_label is not None:
                    self._ver_status_label.setText("下载已暂停")
                self._download_worker.pause()
                return
        self._download_paused = False
        self._downloading_version = ver
        self._download_worker = DownloadWorker(urls, save_path)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        self._set_dl_btn_state(True, remote_info)
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
        self._set_dl_btn_state(False)
        self._download_paused = False
        self._downloading_version = None
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

    def _set_dl_btn_state(self, downloading, remote_info=None):
        if not hasattr(self, '_ver_all_versions'):
            return
        target_ver = None
        if remote_info:
            target_ver = remote_info.get("version", "")
        elif hasattr(self, '_downloading_version'):
            target_ver = self._downloading_version
        for v in self._ver_all_versions:
            dl_btn = v.get("_dl_btn")
            cancel_btn = v.get("_cancel_btn")
            if dl_btn is None:
                continue
            v_ver = v.get("remote_info", {}).get("version", "") if v.get("remote_info") else ""
            is_target = (target_ver and v_ver == target_ver)
            if downloading and is_target:
                dl_btn.setText("暂停")
                try:
                    dl_btn.clicked.disconnect()
                except Exception:
                    pass
                dl_btn.clicked.connect(lambda checked: self._on_download_version(v.get("remote_info")))
                if cancel_btn:
                    cancel_btn.show()
            elif not downloading and is_target:
                dl_btn.setText("下载")
                try:
                    dl_btn.clicked.disconnect()
                except Exception:
                    pass
                rinfo = v.get("remote_info")
                dl_btn.clicked.connect(lambda checked, ri=rinfo: self._on_download_version(ri))
                if cancel_btn:
                    cancel_btn.hide()

    def _on_cancel_download(self):
        if hasattr(self, '_download_worker') and self._download_worker is not None and self._download_worker.isRunning():
            self._download_worker.cancel()
            self._download_worker.wait(3000)
        self._set_dl_btn_state(False)
        self._download_paused = False
        self._downloading_version = None
        if self._ver_status_label is not None:
            self._ver_status_label.setText("下载已取消")

    def _switch_to_exe(self, exe_path, git_commit=""):
        if not os.path.exists(exe_path):
            QMessageBox.critical(self, "错误", f"版本文件不存在:\n{exe_path}")
            return

        dev_dir = self._get_dev_dir()
        ver_dir = os.path.join(dev_dir, _CFG["paths"]["ver"])
        os.makedirs(ver_dir, exist_ok=True)

        target_filename = os.path.basename(exe_path)
        target_in_ver = os.path.join(ver_dir, target_filename)
        if os.path.normpath(exe_path) != os.path.normpath(target_in_ver):
            if not os.path.isfile(target_in_ver):
                shutil.copy2(exe_path, target_in_ver)

        tag = target_filename
        for prefix in (f"{APP_NAME}-v", f"{APP_NAME}-"):
            if tag.startswith(prefix):
                tag = tag[len(prefix):]
        if tag.endswith(".exe"):
            tag = tag[:-4]

        settings_path = os.path.join(get_app_dir(), "launcher_settings.json")
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            settings = {}
        settings["current_app_version"] = tag
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

        stub_path = os.path.join(dev_dir, f"{BRAND_NAME}.exe")
        my_pid = os.getpid()

        bat_path = os.path.join(dev_dir, "_switch_version.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write("chcp 65001 >nul 2>&1\n")
            f.write(f"set MY_PID={my_pid}\n")
            f.write(f"set STUB_EXE={stub_path}\n")
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
            f.write("if exist \"%STUB_EXE%\" del /f /q \"%STUB_EXE%\"\n")
            f.write("mklink /H \"%STUB_EXE%\" \"%TARGET_EXE%\" >nul 2>&1\n")
            f.write("if exist \"%STUB_EXE%\" (\n")
            f.write("    start \"\" \"%STUB_EXE%\"\n")
            f.write(") else (\n")
            f.write("    start \"\" \"%TARGET_EXE%\"\n")
            f.write(")\n")
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
        # 同时从远程获取最新开发动态，覆盖本地gitlog.json
        self._fetch_remote_gitlog()

    def _fetch_remote_gitlog(self):
        """从远程GitHub/Gitee获取最新提交记录，覆盖本地gitlog.json。"""
        def do_fetch():
            commits = []
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                def _urlopen_with_proxy(req, timeout=10):
                    if is_proxy_running():
                        try:
                            proxy_handler = urllib.request.ProxyHandler({
                                'http': f'http://{PROXY_URL}',
                                'https': f'http://{PROXY_URL}',
                            })
                            opener = urllib.request.build_opener(
                                urllib.request.HTTPSHandler(context=ctx),
                                proxy_handler,
                            )
                            return opener.open(req, timeout=timeout)
                        except Exception:
                            pass
                    return urllib.request.urlopen(req, timeout=timeout, context=ctx)

                data = None
                gitee_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/commits?per_page=100"
                if GITEE_TOKEN:
                    gitee_url += f"&access_token={GITEE_TOKEN}"
                try:
                    req = urllib.request.Request(gitee_url, headers={"User-Agent": "Mozilla/5.0"})
                    with _urlopen_with_proxy(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode())
                except Exception:
                    pass

                if data is None:
                    github_url = f"https://api.github.com/repos/{GITHUB_REPO}/commits?per_page=100"
                    headers = {"User-Agent": "Mozilla/5.0"}
                    if GITHUB_TOKEN:
                        headers["Authorization"] = f"token {GITHUB_TOKEN}"
                    req = urllib.request.Request(github_url, headers=headers)
                    with _urlopen_with_proxy(req, timeout=8) as resp:
                        data = json.loads(resp.read().decode())

                for c in data:
                    commit_info = c.get("commit", {})
                    commits.append({
                        "sha": (c.get("sha", ""))[:7],
                        "author": commit_info.get("author", {}).get("name", ""),
                        "date": (commit_info.get("author", {}).get("date", ""))[:10],
                        "message": commit_info.get("message", ""),
                    })
            except Exception:
                pass

            if commits:
                # 覆盖本地gitlog.json
                gitlog_path = os.path.join(get_app_dir(), "gitlog.json")
                try:
                    os.makedirs(os.path.dirname(gitlog_path), exist_ok=True)
                    with open(gitlog_path, "w", encoding="utf-8") as f:
                        json.dump(commits, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                self._ver_git_data = commits
                self._version_data_ready.emit()

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_download_update(self):
        if not hasattr(self, '_latest_info') or not self._latest_info:
            return
        if not self._latest_info.get("filename"):
            QMessageBox.warning(self, "提示", "该版本暂无下载资源")
            return
        self._on_download_version(self._latest_info)

    def _get_kernel_cache_path(self):
        return os.path.join(get_app_dir(), "kernel_versions_cache.json")

    def _get_kernel_cache_last_check(self):
        try:
            with open(self._get_kernel_cache_path(), "r", encoding="utf-8") as f:
                return json.load(f).get("last_check", "")
        except Exception:
            return ""

    def _load_kernel_versions_cache(self):
        try:
            with open(self._get_kernel_cache_path(), "r", encoding="utf-8") as f:
                cache = json.load(f)
            releases = cache.get("releases", [])
            if releases and isinstance(releases, list):
                # 仅把缓存数据加载到内存，不主动展开列表
                self._kernel_releases = releases
                self._kernel_current_ver = self._get_mihomo_version()
                return True
        except Exception:
            pass
        return False

    def _init_kernel_list(self):
        """初始化内核列表：
          1. 默认尝试加载本地缓存（kernel_versions_cache.json）
          2. 如果缓存存在且有效 → 直接渲染版本行 + 展开滚动区
             （首次启动也能看到下载列表，用户体验更好）
          3. 无缓存时 → 仅记录本地内核版本号，列表保持收起
        """
        loaded = self._load_kernel_versions_cache()
        if not loaded:
            # 无缓存，记录本地内核版本号备用（不渲染）
            self._kernel_releases = []
            self._kernel_current_ver = self._get_mihomo_version()
            return
        # 有缓存：直接渲染 + 展开（与点检查更新后效果一致）
        try:
            self._show_kernel_list()
        except Exception:
            # 渲染失败也不影响后续检查更新流程
            pass
        try:
            self._kernel_versions_ready.emit()
        except Exception:
            pass

    def _show_kernel_list(self):
        """展开内核版本列表（点检查更新获取到结果后/首次启动加载缓存后调用）

        默认只显示5行内容（约160px），用户可通过拖拽手柄增加高度。
        不再硬卡 kernel_card 高度，让卡片随滚动区自然伸缩。
        """
        self._kernel_scroll_visible = True
        self._kernel_scroll.setVisible(True)
        if hasattr(self, '_kernel_hint_label'):
            self._kernel_hint_label.setVisible(False)
        # 表头同步显示（首次展开 / 重新展开都生效）
        if hasattr(self, '_kernel_header_row') and self._kernel_header_row is not None:
            self._kernel_header_row.setVisible(True)
        # 默认5行高度（约160px），用户可拖拽调整
        default_h = 160
        self._kernel_scroll.setMinimumHeight(default_h)
        self._kernel_scroll.setMaximumHeight(default_h)
        # 强制刷新 size hint，让卡片随列表内容自然伸缩
        if hasattr(self, 'kernel_card') and self.kernel_card is not None:
            self.kernel_card.updateGeometry()
        if hasattr(self, '_kernel_scroll') and self._kernel_scroll is not None:
            self._kernel_scroll.updateGeometry()

    def _on_check_kernel_btn(self):
        if hasattr(self, '_kernel_ver_worker') and self._kernel_ver_worker and self._kernel_ver_worker.isRunning():
            self._kernel_ver_worker.requestInterruption()
            self._kernel_ver_worker.quit()
            self._kernel_ver_worker.wait(3000)
            self.btn_check_kernel.setText("🔄 检查更新")
            self.kernel_status.setText("已取消")
            self.kernel_status.setStyleSheet(f"color: {COLOR_ORANGE};")
            return
        if not self.quick_dir:
            QMessageBox.warning(self, "提示", "未找到代理内核目录")
            return
        self.btn_check_kernel.setText("⏹ 取消")
        self.kernel_status.setText("正在检查内核版本...")
        self.kernel_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        self._kernel_ver_worker = KernelVersionWorker(self.quick_dir)
        self._kernel_ver_worker.progress.connect(lambda t: (
            self.kernel_status.setText(t),
            self.kernel_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        ))
        self._kernel_ver_worker.finished.connect(self._on_kernel_versions_fetched)
        self._kernel_ver_worker.start()

    def _on_kernel_versions_fetched(self, releases, current_ver):
        self.btn_check_kernel.setText("🔄 检查更新")
        if not releases:
            self.kernel_status.setText(current_ver if current_ver.startswith("获取") or current_ver.startswith("无法") else "获取版本列表失败")
            self.kernel_status.setStyleSheet("color: #FF6B80;")
            return
        self._kernel_releases = releases
        self._kernel_current_ver = current_ver
        cache_path = os.path.join(get_app_dir(), "kernel_versions_cache.json")
        try:
            cache_data = {
                "releases": releases,
                "current_ver": current_ver,
                "last_check": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        # 用户点检查更新后，获取到内核列表后再展开显示下载列表框
        self._show_kernel_list()
        self._kernel_versions_ready.emit()

    def _on_kernel_versions_ready(self):
        releases = getattr(self, '_kernel_releases', [])
        current_ver = getattr(self, '_kernel_current_ver', '')

        local_kernels = self._list_local_kernels()
        local_map = {k["tag"]: k for k in local_kernels}

        if not releases and not local_kernels:
            self.kernel_status.setText("暂无可用版本")
            self.kernel_status.setStyleSheet(f"color: {COLOR_DIM};")
            # 清空数量描述
            if hasattr(self, 'kernel_count_label'):
                self.kernel_count_label.setText("")
            # 无版本时显示提示标签，隐藏表头
            if hasattr(self, '_kernel_hint_label'):
                self._kernel_hint_label.setVisible(True)
            if hasattr(self, '_kernel_header_row'):
                self._kernel_header_row.setVisible(False)
            return

        # 有版本数据，隐藏提示标签
        if hasattr(self, '_kernel_hint_label'):
            self._kernel_hint_label.setVisible(False)

        stable_releases = [r for r in releases if not r.get("prerelease", False)]
        latest_tag = stable_releases[0]["tag"] if stable_releases else (releases[0]["tag"] if releases else "")
        is_latest = current_ver and latest_tag and current_ver == latest_tag.lstrip("v")

        if current_ver:
            self.kernel_current_label.setText(f"当前版本: v{current_ver}")
            self.kernel_current_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_GREEN}; font-weight: bold;")
        else:
            self.kernel_current_label.setText("当前版本: 未知")
            self.kernel_current_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_ORANGE}; font-weight: bold;")

        if is_latest:
            self.kernel_latest_label.setText("✅ 已是最新版本")
            self.kernel_latest_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_GREEN};")
        elif latest_tag:
            self.kernel_latest_label.setText(f"最新版本: {latest_tag}")
            self.kernel_latest_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_BLUE_LIGHT};")

        last_check = self._get_kernel_cache_last_check()

        # 清理旧的版本行 / 提示行
        # 固定保留：index 0 = hint_label（提示文案），index 1 = _kernel_header_row（列标题表头）
        # 清理 index 2 及之后的所有项（即 cards 和 tip_row）
        # 关键修复：旧的写法用 takeAt(1) 会把表头也一起删掉，
        # 而且 insertWidget(1, header) + insertWidget(count-1, card) 会让表头随每张 card 一起下移，
        # 最终被挤到下载列表最底部。
        while self._kernel_scroll_layout.count() > 2:
            item = self._kernel_scroll_layout.takeAt(2)
            w = item.widget()
            if w:
                w.deleteLater()

        # 拿到版本列表后显示表头（之前是隐藏的）
        if hasattr(self, '_kernel_header_row') and self._kernel_header_row is not None:
            self._kernel_header_row.setVisible(True)

        # 当只有本地内核时，添加一个柔和的提示行
        # 位置：表头之后（index 2），即 [hint, header, tip, card1, card2, ...]
        if not releases and local_kernels:
            tip_row = QFrame()
            tip_row.setStyleSheet("background-color: #0f1a1f; border: none; border-bottom: 1px dashed #1f2a30;")
            tip_layout = QHBoxLayout(tip_row)
            tip_layout.setContentsMargins(10, 6, 10, 6)
            tip_icon = QLabel("💡")
            tip_icon.setFixedWidth(20)
            tip_icon.setStyleSheet("font-size: 9pt; border: none;")
            tip_layout.addWidget(tip_icon)
            tip_text = QLabel("下方为本地已下载的代理内核。点击右上「检查更新」可联网获取更多版本。")
            tip_text.setStyleSheet(f"font-size: 8pt; color: {COLOR_DIM}; border: none;")
            tip_layout.addWidget(tip_text, stretch=1)
            # 始终插入到表头之后（index 2），这样 cards 紧跟其后
            self._kernel_scroll_layout.insertWidget(2, tip_row)

        stable_rels = sorted([r for r in releases if not r.get("prerelease", False)], key=lambda r: r.get("published_at", ""), reverse=True)
        pre_rels = sorted([r for r in releases if r.get("prerelease", False)], key=lambda r: r.get("published_at", ""), reverse=True)
        sorted_releases = stable_rels

        # 添加本地已下载但不在远程列表中的内核版本
        remote_tags = {r["tag"] for r in sorted_releases}
        for local_k in local_kernels:
            if local_k["tag"] not in remote_tags:
                sorted_releases.append({
                    "tag": local_k["tag"],
                    "name": f"mihomo {local_k['tag']}",
                    "published_at": "",
                    "body": "",
                    "asset_name": None,
                    "download_url": "",
                    "prerelease": False,
                })

        # 版本数量描述：放在"已是最新版本"右侧（info_row 内）
        # 区别于 kernel_status（瞬时状态提示），这里是持久化信息
        if releases:
            self.kernel_count_label.setText(f"共 {len(sorted_releases)} 个版本可用")
        else:
            self.kernel_count_label.setText(f"共 {len(sorted_releases)} 个本地版本（点击检查更新获取更多）")
        if last_check:
            self.kernel_count_label.setText(
                self.kernel_count_label.text() + f"  |  上次检查: {last_check}"
            )
        for rel in sorted_releases:
            tag = rel["tag"]
            tag_num = tag.lstrip("v")
            is_current = (current_ver == tag_num)
            is_local = tag in local_map
            has_asset = bool(rel.get("download_url"))
            is_prerelease = rel.get("prerelease", False)

            if is_current:
                row_bg = "#1a4a2a"
                border_color = "#2a6a3a"
            elif is_prerelease:
                row_bg = "#1a1a10"
                border_color = "#2a2a1a"
            elif is_local:
                row_bg = "#161616"
                border_color = "#222"
            else:
                row_bg = "#111"
                border_color = "#1a1a1a"

            card = QFrame()
            card.setStyleSheet(
                f"background-color: {row_bg}; border: 1px solid {border_color}; border-radius: 0px;"
            )
            # 卡片采用单行 5 列结构（描述作为表格项，节省纵向高度）：
            #   版本 | 发布日期 | 更新说明(stretch) | 状态 | 操作
            # 注：状态列和更新说明列已互换位置（状态原本在第 3 列，更新说明原本在第 4 列）
            #   互换后视觉重心更平衡：左边"标识+时间+详情"是一组连贯的元信息，
            #   右边"状态+操作"是用户操作区，分组更清晰。
            # 描述列占满剩余宽度，垂直居中对齐，整张卡片只有一行。
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 5, 10, 5)
            card_layout.setSpacing(6)

            ver_color = "#4CAF50" if is_current else (COLOR_TEXT if is_local else COLOR_DIM)
            ver_label = QLabel(tag)
            ver_label.setFixedWidth(70)
            ver_font_size = "10pt" if is_current else "9pt"
            ver_label.setStyleSheet(f"font-family: Consolas; font-size: {ver_font_size}; font-weight: bold; color: {ver_color}; border: none;")
            ver_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            card_layout.addWidget(ver_label)

            # 发布日期：宽度 105px，容纳 "2026-06-07 04:45" 完整时间戳不被截断
            # 原始 GitHub 格式 "2026-06-07T04:45:17Z" 太长（20 字符），
            # 清洗为 "2026-06-07 04:45"（16 字符），保留日期+小时:分钟，信息密度高
            date_str = rel.get("published_at", "")
            if date_str:
                # 清洗 ISO 8601 → "YYYY-MM-DD HH:MM"（去秒去 Z，替换 T 为空格）
                date_str = date_str.replace("T", " ").rstrip("Z")[:16]
            date_label = QLabel(date_str)
            date_label.setFixedWidth(105)
            date_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_DIM}; border: none; font-family: Consolas;")
            date_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            card_layout.addWidget(date_label)

            # === 更新说明（5 列中第 3 列，stretch 占据剩余宽度）===
            # 默认只显示一行（取第一个有意义的非空行），宽度不足时自动在右侧省略…
            # 鼠标悬停时显示完整 cleaned body（tooltip），不需要展开/折叠模式
            raw_body = (rel.get("body") or "").strip()
            preview_text = ""
            full_body_for_tooltip = ""
            if raw_body:
                clean_body = _clean_release_body(raw_body)
                if clean_body:
                    # 取第一个有意义的非空行（跳过 "What's Changed" / "Full Changelog" 之类章节标题）
                    non_empty_lines = [l.strip() for l in clean_body.split("\n") if l.strip()]
                    meaningful = [l for l in non_empty_lines if not l.endswith("Changed") and not l.startswith("Full Changelog")]
                    if not meaningful:
                        meaningful = non_empty_lines
                    if meaningful:
                        preview_text = meaningful[0]  # 单行预览（首行）
                    # tooltip 用完整 cleaned body（截前 500 字符防过长）
                    if len(clean_body) > 500:
                        full_body_for_tooltip = clean_body[:500] + "…"
                    else:
                        full_body_for_tooltip = clean_body

            # 单行省略号标签：固定 18px 高（容纳 8pt 一行），宽度不足自动…
            # 相比 CopyableLabel 的 2 行模式，整体卡片高度从 38px 降到 32px
            desc_label = ElidedLabel(preview_text)
            desc_label.setFixedHeight(18)
            desc_label.setStyleSheet(
                f"QLabel {{ color: {COLOR_DIM}; font-size: 8pt; background: transparent; "
                f"border: none; border-radius: 0px; padding: 0px; margin: 0px; }}"
            )
            if full_body_for_tooltip:
                desc_label.setToolTip(full_body_for_tooltip)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            # stretch=1 让更新说明列占满剩余宽度
            card_layout.addWidget(desc_label, stretch=1)

            # === 状态（5 列中第 4 列，与更新说明互换位置） ===
            # 从第 3 列移到第 4 列：左边"版本+日期+说明"是元信息组，右边"状态+操作"是操作组
            status_label = QLabel("")
            status_label.setFixedWidth(90)
            if is_current:
                status_label.setText("● 当前版本")
                status_label.setStyleSheet(f"font-size: 8pt; color: #4CAF50; border: none; font-weight: bold;")
            elif is_prerelease and is_local:
                size_text = f" {local_map[tag]['size_mb']}MB"
                status_label.setText(f"🧪 预发布{size_text}")
                status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_ORANGE}; border: none;")
            elif is_prerelease and has_asset:
                status_label.setText("🧪 预发布")
                status_label.setStyleSheet(f"font-size: 8pt; color: #888; border: none;")
            elif is_prerelease:
                status_label.setText("🧪 预发布")
                status_label.setStyleSheet(f"font-size: 8pt; color: #666; border: none;")
            elif is_local:
                size_text = f" {local_map[tag]['size_mb']}MB"
                status_label.setText(f"📦 已下载{size_text}")
                status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_ORANGE}; border: none;")
            elif has_asset:
                status_label.setText("🆕 可下载")
                status_label.setStyleSheet(f"font-size: 8pt; color: {COLOR_BLUE_LIGHT}; border: none;")
            else:
                status_label.setText("—")
                status_label.setStyleSheet(f"font-size: 8pt; color: #555; border: none;")
            status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            card_layout.addWidget(status_label)

            action_frame = QFrame()
            action_frame.setFixedWidth(100)
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
            btn_style_green = (
                f"QPushButton {{ background-color: {COLOR_GREEN}; color: #fff; border: none; border-radius: 3px; "
                f"font-size: 8pt; font-weight: bold; padding: 2px 8px; }}"
                f"QPushButton:hover {{ background-color: #5CBF72; }}"
            )

            if is_current:
                using_label = QLabel("使用中")
                using_label.setFixedSize(50, 22)
                using_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                using_label.setStyleSheet(
                    f"background-color: #2a5a3a; color: #4CAF50; border: 1px solid #3a7a4a; border-radius: 3px; "
                    f"font-size: 8pt; font-weight: bold;"
                )
                action_layout.addWidget(using_label)

            if is_local and not is_current:
                switch_btn = QPushButton("🔄 切换")
                switch_btn.setFixedSize(60, 22)
                switch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                switch_btn.setStyleSheet(btn_style_green)
                kernel_path = local_map[tag]["path"]
                switch_btn.clicked.connect(lambda checked, p=kernel_path, t=tag: self._on_switch_kernel(p, t))
                action_layout.addWidget(switch_btn)

            if not is_local and has_asset:
                dl_btn = QPushButton("📥 下载")
                dl_btn.setFixedSize(60, 22)
                dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                dl_btn.setStyleSheet(btn_style_blue)
                dl_btn.clicked.connect(lambda checked, r=rel: self._on_download_kernel(r))
                action_layout.addWidget(dl_btn)

            if is_local and not is_current and len(local_kernels) > 1:
                del_btn = QPushButton("🗑")
                del_btn.setFixedSize(26, 22)
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setStyleSheet(btn_style_red)
                kernel_path = local_map[tag]["path"]
                del_btn.clicked.connect(lambda checked, p=kernel_path: self._on_delete_kernel(p))
                action_layout.addWidget(del_btn)

            action_layout.addStretch()
            card_layout.addWidget(action_frame)

            # 直接 addWidget 追加到尾部：
            #   布局结构稳定为 [hint, header, tip?, card1, card2, ...]
            #   表头永远在 index=1，不会被 cards 挤到下方
            self._kernel_scroll_layout.addWidget(card)

        # 强制刷新 size hint，确保卡片高度能跟随列表内容增长
        if hasattr(self, '_kernel_scroll') and self._kernel_scroll is not None:
            self._kernel_scroll.updateGeometry()
        if hasattr(self, 'kernel_card') and self.kernel_card is not None:
            self.kernel_card.updateGeometry()

    def _auto_download_latest_kernel(self):
        if not self.quick_dir:
            return
        self.kernel_status.setText("首次运行，正在获取最新内核...")
        self.kernel_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        self._set_home_kernel_status("initializing", "⏳ 获取代理内核信息...")
        self._auto_kernel_ver_worker = KernelVersionWorker(self.quick_dir)
        self._auto_kernel_ver_worker.progress.connect(lambda t: (
            self.kernel_status.setText(t),
            self.kernel_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        ))
        self._auto_kernel_ver_worker.finished.connect(self._on_auto_kernel_versions_fetched)
        self._auto_kernel_ver_worker.start()

    def _on_auto_kernel_versions_fetched(self, releases, current_ver):
        if not releases:
            self.kernel_status.setText("自动下载内核失败，请手动检查更新")
            self.kernel_status.setStyleSheet("color: #FF6B80;")
            self._set_home_kernel_status("failed", "⚠ 代理内核下载失败，请在代理设置中获取更新")
            return
        stable = [r for r in releases if not r.get("prerelease", False)]
        target = stable[0] if stable else (releases[0] if releases else None)
        if not target:
            self.kernel_status.setText("未找到可用内核版本")
            self.kernel_status.setStyleSheet("color: #FF6B80;")
            self._set_home_kernel_status("failed", "⚠ 代理内核下载失败，请在代理设置中获取更新")
            return
        tag = target.get("tag", "")
        download_url = target.get("download_url", "")
        asset_name = target.get("asset_name", "")
        if not download_url:
            self.kernel_status.setText("内核下载链接不可用")
            self.kernel_status.setStyleSheet("color: #FF6B80;")
            self._set_home_kernel_status("failed", "⚠ 代理内核下载失败，请在代理设置中获取更新")
            return
        self.kernel_status.setText(f"正在下载内核 mihomo {tag}...")
        self.kernel_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        self._set_home_kernel_status("downloading", f"⏳ 下载代理内核 {tag}...")
        self._kernel_dl_worker = KernelDownloadWorker(self.quick_dir, tag, download_url, asset_name)
        self._kernel_dl_worker.progress.connect(lambda t: (
            self.kernel_status.setText(t),
            self.kernel_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        ))
        self._kernel_dl_worker.download_percent.connect(self._on_home_kernel_download_percent)
        self._kernel_dl_worker.finished.connect(self._on_auto_kernel_download_finished)
        self._kernel_dl_worker.start()

    def _on_auto_kernel_download_finished(self, ok, msg, path):
        if ok and path and os.path.isfile(path):
            tag = ""
            m = re.search(r'mihomo_(v?[\d.]+)\.exe', os.path.basename(path))
            if m:
                tag = m.group(1)
                if not tag.startswith("v"):
                    tag = "v" + tag
            self._on_switch_kernel(path, tag)
            self.kernel_status.setText("内核下载完成，代理服务已就绪")
            self.kernel_status.setStyleSheet(f"color: {COLOR_GREEN};")
            self._set_home_kernel_status("ready")
        else:
            self.kernel_status.setText(f"内核下载失败: {msg}")
            self.kernel_status.setStyleSheet("color: #FF6B80;")
            self._set_home_kernel_status("failed", "⚠ 代理内核下载失败，请在代理设置中获取更新")

    def _on_download_kernel(self, release_info):
        tag = release_info.get("tag", "")
        download_url = release_info.get("download_url", "")
        asset_name = release_info.get("asset_name", "")
        if not download_url:
            QMessageBox.warning(self, "提示", "该版本无可用下载链接")
            return
        if not self.quick_dir:
            return
        if hasattr(self, '_kernel_dl_worker') and self._kernel_dl_worker and self._kernel_dl_worker.isRunning():
            QMessageBox.information(self, "提示", "已有下载任务进行中")
            return
        self.kernel_status.setText(f"正在下载 mihomo {tag}...")
        self.kernel_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        self._set_home_kernel_status("downloading", f"⏳ 下载代理内核 {tag}...")
        self._kernel_dl_worker = KernelDownloadWorker(self.quick_dir, tag, download_url, asset_name)
        self._kernel_dl_worker.progress.connect(lambda t: (
            self.kernel_status.setText(t),
            self.kernel_status.setStyleSheet(f"color: {COLOR_ORANGE};")
        ))
        self._kernel_dl_worker.download_percent.connect(self._on_home_kernel_download_percent)
        self._kernel_dl_worker.finished.connect(self._on_kernel_download_finished)
        self._kernel_dl_worker.start()

    def _on_kernel_download_finished(self, ok, msg, path):
        if ok:
            self.kernel_status.setText(msg)
            self.kernel_status.setStyleSheet(f"color: {COLOR_GREEN};")
            if path and os.path.isfile(path):
                reply = QMessageBox.question(
                    self, "下载完成",
                    f"{msg}\n\n是否立即切换到该版本？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    tag = ""
                    m = re.search(r'mihomo_(v?[\d.]+)\.exe', os.path.basename(path))
                    if m:
                        tag = m.group(1)
                        if not tag.startswith("v"):
                            tag = "v" + tag
                    self._on_switch_kernel(path, tag)
                else:
                    self._kernel_current_ver = self._get_mihomo_version()
                    self._on_kernel_versions_ready()
            else:
                self._kernel_current_ver = self._get_mihomo_version()
                self._on_kernel_versions_ready()
            self._update_kernel_status()
        else:
            self.kernel_status.setText(msg)
            self.kernel_status.setStyleSheet("color: #FF6B80;")
            self._set_home_kernel_status("failed", "⚠ 代理内核下载失败，请在代理设置中获取更新")

    def _on_switch_kernel(self, kernel_path, tag):
        if not os.path.isfile(kernel_path):
            QMessageBox.critical(self, "错误", f"内核文件不存在:\n{kernel_path}")
            return
        was_running = is_proxy_running()
        if was_running:
            stop_quick()
            time.sleep(0.5)

        current_exe = os.path.join(self.quick_dir, "quick.exe")
        backup_path = current_exe + ".bak"
        tag_num = tag.lstrip("v")

        try:
            if os.path.isfile(backup_path):
                os.remove(backup_path)
            if os.path.isfile(current_exe):
                os.rename(current_exe, backup_path)
            shutil.copy2(kernel_path, current_exe)
            try:
                os.remove(backup_path)
            except Exception:
                pass
            ver_file = os.path.join(self.quick_dir, "_kernel_version.txt")
            try:
                with open(ver_file, "w", encoding="utf-8") as f:
                    f.write(tag_num)
            except Exception:
                pass
            self.kernel_current_label.setText(f"当前版本: v{tag_num}")
            self.kernel_current_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_GREEN}; font-weight: bold;")
            self.svc_kernel_label.setText(f"内核: {self._get_quick_version() or '未知'}")
            self._update_kernel_status()
            self.kernel_status.setText(f"已切换到 mihomo {tag}")
            self.kernel_status.setStyleSheet(f"color: {COLOR_GREEN};")
            if was_running and self.settings.get("proxy_enabled", False):
                self._on_start()
            self._kernel_current_ver = tag_num
            self._on_kernel_versions_ready()
        except PermissionError:
            bat_path = current_exe + "_replace.bat"
            new_exe_src = kernel_path
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                f.write("chcp 65001 >nul 2>&1\n")
                f.write("timeout /t 3 /nobreak >nul\n")
                f.write(f'del /f /q "{current_exe}" 2>nul\n')
                f.write(f'copy /y "{new_exe_src}" "{current_exe}" >nul\n')
                f.write(f'if exist "{backup_path}" del /f /q "{backup_path}" 2>nul\n')
                f.write('del /f /q "%~f0" 2>nul\n')
            subprocess.Popen(
                f'cmd /c "{bat_path}"',
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=os.path.dirname(current_exe),
            )
            ver_file = os.path.join(self.quick_dir, "_kernel_version.txt")
            try:
                with open(ver_file, "w", encoding="utf-8") as f:
                    f.write(tag_num)
            except Exception:
                pass
            self.kernel_current_label.setText(f"当前版本: v{tag_num}")
            self.kernel_current_label.setStyleSheet(f"font-size: 9pt; color: {COLOR_GREEN}; font-weight: bold;")
            self.svc_kernel_label.setText(f"内核: mihomo v{tag_num}")
            self._update_kernel_status()
            self.kernel_status.setText(f"已切换到 mihomo {tag}（将在后台完成替换）")
            self.kernel_status.setStyleSheet(f"color: {COLOR_GREEN};")
            self._kernel_current_ver = tag_num
            self._on_kernel_versions_ready()

    def _on_delete_kernel(self, kernel_path):
        tag = ""
        m = re.search(r'mihomo_(v?[\d.]+)\.exe', os.path.basename(kernel_path))
        if m:
            tag = m.group(1)
            if not tag.startswith("v"):
                tag = "v" + tag
        # 至少保留一个内核
        local_kernels = self._list_local_kernels()
        if len(local_kernels) <= 1:
            QMessageBox.warning(self, "无法删除", "至少需要保留一个代理内核")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 mihomo {tag} 内核文件吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(kernel_path)
                self.kernel_status.setText(f"已删除 mihomo {tag}")
                self.kernel_status.setStyleSheet(f"color: {COLOR_DIM};")
                self._kernel_current_ver = self._get_mihomo_version()
                self._on_kernel_versions_ready()
            except Exception as e:
                self.kernel_status.setText(f"删除失败: {e}")
                self.kernel_status.setStyleSheet("color: #FF6B80;")

    def closeEvent(self, event):
        """关闭按钮默认最小化到托盘，不退出进程。

        真正退出走托盘菜单的「退出」按钮，会调用 _quit_app() 走完整的资源清理流程。
        系统不支持托盘时（如 Windows server core）才走原退出流程。
        """
        if self._tray_available:
            # 隐藏窗口到托盘
            event.ignore()
            self.hide()
            # 第一次最小化到托盘时弹个气泡提示，告知用户软件还在后台运行
            if not self._tray_notified:
                self._tray_notified = True
                if self._tray and self._tray.supportsMessages():
                    self._tray.showMessage(
                        APP_NAME,
                        "已最小化到系统托盘，点击托盘图标可重新打开主窗口。",
                        QSystemTrayIcon.MessageIcon.Information,
                        3000,
                    )
        else:
            # 兜底：系统不支持托盘时走原退出流程
            self._quit_app()
            event.accept()

    def _setup_tray(self):
        """初始化系统托盘图标 + 右键菜单。

        菜单：
            - 显示主窗口 / 隐藏主窗口（根据当前窗口显隐状态自动切换文案）
            - 退出
        行为：
            - 双击托盘图标：切换主窗口显隐
            - 左键单击（Windows 上 QSystemTrayIcon 默认是激活菜单，依赖于 .activated 信号）
        """
        self._tray = None
        self._tray_available = False
        self._tray_notified = False  # 第一次最小化时是否已提示过

        # 检查系统是否支持托盘
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        # 加载图标：优先用主图标，没有就降级用内置 style icon
        # 搜索顺序与 _set_icon / _SplashScreen 保持一致：ico.png → icon.png → icon.ico
        if hasattr(sys, '_MEIPASS'):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        tray_icon = None
        for name in ('ico.png', 'icon.png', 'icon.ico'):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                tray_icon = QIcon(p)
                if not tray_icon.isNull():
                    break
                tray_icon = None
        if tray_icon is None:
            tray_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(tray_icon)

        self._tray = QSystemTrayIcon(tray_icon, self)
        self._tray.setToolTip(APP_NAME)

        # 右键菜单
        menu = QMenu(self)
        self._tray_toggle_action = QAction("显示主窗口", self)
        self._tray_toggle_action.triggered.connect(self._toggle_main_window)
        menu.addAction(self._tray_toggle_action)
        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)

        # 双击托盘图标：切换主窗口
        self._tray.activated.connect(self._on_tray_activated)
        # 托盘菜单显示时刷新「显示/隐藏」文案
        self._tray_menu = menu

        self._tray.show()
        self._tray_available = True

    def _on_tray_activated(self, reason):
        """托盘图标被点击时响应。"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_main_window()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            # 左键单击：在 Windows 上通常弹出菜单，这里直接走 toggle，体感更顺
            self._toggle_main_window()

    def _toggle_main_window(self):
        """切换主窗口的显隐状态。"""
        if self.isVisible():
            self.hide()
        else:
            self._show_from_tray()

    def _show_from_tray(self):
        """从托盘恢复主窗口。"""
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.activateWindow()
        self.raise_()
        # 唤起前台（绕过 Windows 前台锁）
        self._force_foreground()

    def _refresh_tray_menu_text(self):
        """根据主窗口当前显隐状态刷新托盘菜单的「显示/隐藏」文案。"""
        if not self._tray_available or not hasattr(self, '_tray_toggle_action'):
            return
        if self.isVisible():
            self._tray_toggle_action.setText("隐藏主窗口")
        else:
            self._tray_toggle_action.setText("显示主窗口")

    def _quit_app(self):
        """真正退出：清理资源 + 关闭后台监控 + 退出 app。"""
        # 清理逻辑从原 closeEvent 搬过来
        try:
            self._stop_auto_line_timer()
            self._stop_realtime_monitor()
            self._stop_debug_log()
        except Exception:
            pass
        try:
            if self.monitor:
                self.monitor.stop()
                self.monitor.wait()
        except Exception:
            pass
        # 真正退出：先停止代理内核（强杀 quick.exe 及其子进程），避免关闭程序后
        # 内核进程残留占用 7890/9090 端口、并在后台持续运行。
        try:
            stop_quick()
        except Exception:
            pass
        # 隐藏托盘图标，避免退出后托盘残留
        if self._tray:
            self._tray.hide()
        # 真正退出时释放单实例互斥体（最小化到托盘不释放，新进程要杀的就是隐藏态的我们）
        _cleanup_single_instance()
        QApplication.instance().quit()

    def _finish_splash(self):
        if self._splash and self._splash.isVisible():
            self.show()
            self._splash.finish(self)
            self._splash = None
        self._force_foreground()

    def _force_foreground(self):
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            foreground = ctypes.windll.user32.GetForegroundWindow()
            if foreground != hwnd:
                fg_tid = ctypes.windll.user32.GetWindowThreadProcessId(foreground, None)
                my_tid = ctypes.windll.kernel32.GetCurrentThreadId()
                ctypes.windll.user32.AttachThreadInput(my_tid, fg_tid, True)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.AttachThreadInput(my_tid, fg_tid, False)
            ctypes.windll.user32.BringWindowToTop(hwnd)
            self.raise_()
            self.activateWindow()
        except Exception:
            self.raise_()
            self.activateWindow()


class HealthDetailDialog(QDialog):
    """线路健康度详情对话框

    - 顶部：所有线路 7d 健康度汇总表（按成功率排序）
    - 选中线路后：下方显示该线路 30 天历史（每日一行：成功率 + 平均延迟）
    - 底部：清空所有健康度数据按钮
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("线路健康度详情")
        self.setMinimumSize(820, 580)
        self.resize(900, 660)
        self.setStyleSheet(
            f"QDialog {{ background-color: {COLOR_BG}; color: {COLOR_TEXT}; }}"
            f"QLabel {{ color: {COLOR_TEXT}; }}"
        )
        self._selected_line: Optional[str] = None
        self._build_ui()
        self._load_summary()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # 顶部说明
        tip = QLabel("近 7 天所有线路的成功率与平均延迟。点选线路可查看 30 天历史。")
        tip.setStyleSheet("color: #aaa; font-size: 8pt;")
        tip.setWordWrap(True)
        root.addWidget(tip)

        # 上半：7d 汇总表
        header = QHBoxLayout()
        h = QLabel("📊 7 天健康度")
        h.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_GREEN};")
        header.addWidget(h)
        header.addStretch()
        clear_btn = QPushButton("🗑 清空所有记录")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFixedHeight(24)
        clear_btn.setStyleSheet(
            f"QPushButton {{ background-color: #2a1a1a; color: #FF6B80; "
            f"font-size: 8pt; border-radius: 3px; border: 1px solid #5a2a2a; padding: 0 10px; }}"
            f"QPushButton:hover {{ background-color: #5a2020; }}"
        )
        clear_btn.clicked.connect(self._on_clear_all)
        header.addWidget(clear_btn)
        root.addLayout(header)

        self.summary_list = QListWidget()
        self.summary_list.setStyleSheet(
            f"QListWidget {{ background-color: {COLOR_CARD}; color: {COLOR_TEXT}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 4px; font-size: 9pt; }}"
            f"QListWidget::item {{ padding: 6px 10px; border-bottom: 1px solid #222; }}"
            f"QListWidget::item:selected {{ background-color: #1a3a5a; color: #fff; }}"
            f"QListWidget::item:hover {{ background-color: #1a2a3a; }}"
        )
        self.summary_list.currentItemChanged.connect(self._on_line_selected)
        root.addWidget(self.summary_list, stretch=1)

        # 下半：30d 历史
        h2 = QLabel("📅 30 天历史")
        h2.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_BLUE_LIGHT};")
        root.addWidget(h2)
        self.history_list = QListWidget()
        self.history_list.setStyleSheet(
            f"QListWidget {{ background-color: {COLOR_CARD}; color: {COLOR_TEXT}; "
            f"border: 1px solid {COLOR_BORDER}; border-radius: 4px; font-family: Consolas; font-size: 8pt; }}"
            f"QListWidget::item {{ padding: 4px 10px; }}"
        )
        self.history_list.setMaximumHeight(200)
        root.addWidget(self.history_list)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; font-size: 9pt; "
            f"font-weight: bold; border-radius: 4px; border: none; padding: 0 24px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    def _load_summary(self):
        """加载 7d 汇总"""
        self.summary_list.clear()
        self.history_list.clear()
        db = get_health_db()
        summary = db.get_health_summary()
        # 合并 7d 数据 + 内置/订阅名单（即使没数据也显示）
        all_names = set()
        for name, _, _ in CONFIG_URLS:
            all_names.add(name)
        try:
            for sub in get_subscription_manager().get_all():
                all_names.add(sub.name)
        except Exception:
            pass
        all_names.update(summary.keys())

        if not all_names:
            empty = QListWidgetItem("（暂无任何线路，检测一次线路即可开始记录健康度）")
            empty.setForeground(QColor("#888"))
            self.summary_list.addItem(empty)
            return

        # 按 7d 成功率排序（无数据排后面）
        def sort_key(name):
            data = summary.get(name)
            if data is None:
                return (1, 0, name)
            return (0, -data["rate"], name)
        sorted_names = sorted(all_names, key=sort_key)
        for name in sorted_names:
            data = summary.get(name)
            if data is None:
                txt = f"  {name:30s}  ⬜ 尚无记录"
                color = "#888"
            else:
                rate = data["rate"]
                avg = data.get("avg_latency")
                samples = data["samples"]
                bar = format_health_bar(rate, width=6).split(" ")[0]
                avg_txt = f"延迟 {avg:.2f}s" if avg is not None else "无延迟数据"
                txt = f"  {name:24s}  {bar}  {int(rate*100):3d}%  ({samples}次)  {avg_txt}"
                color = get_health_label(rate)[1]
            item = QListWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setForeground(QColor(color))
            self.summary_list.addItem(item)
        # 默认选中第一行
        if self.summary_list.count() > 0:
            self.summary_list.setCurrentRow(0)

    def _on_line_selected(self, current, previous):
        if current is None:
            self.history_list.clear()
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        if not name:
            return
        self._selected_line = name
        self._load_history(name)

    def _load_history(self, name: str):
        self.history_list.clear()
        records = get_health_db().get_30d_history(name)
        if not records:
            empty = QListWidgetItem(f"（{name} 暂无历史记录）")
            empty.setForeground(QColor("#888"))
            self.history_list.addItem(empty)
            return
        # 按日期聚合（多条同日的取最后一条）
        by_day: Dict[str, Dict] = {}
        for r in records:
            day = r.get("ts", "")[:10]
            if not day:
                continue
            # 后写入的覆盖先写入的（已经按时间正序）
            by_day[day] = r
        if not by_day:
            return
        # 按日期倒序显示
        for day in sorted(by_day.keys(), reverse=True):
            r = by_day[day]
            if r.get("success"):
                avg = r.get("avg", -1)
                avg_txt = f"{avg:.2f}s" if avg > 0 else "n/a"
                line = f"  {day}  ✅ 成功  延迟 {avg_txt}  ({r.get('count',0)}/{r.get('total',0)} URL)"
                color = COLOR_GREEN
            else:
                line = f"  {day}  ❌ 失败  (0/{r.get('total',0)} URL)"
                color = "#FF6B80"
            item = QListWidgetItem(line)
            item.setForeground(QColor(color))
            self.history_list.addItem(item)

    def _on_clear_all(self):
        ret = QMessageBox.question(
            self, "确认清空",
            "确定要清空所有线路的健康度数据吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            db = get_health_db()
            for name in list(db.get_all_line_names()):
                db._data[name] = []
            db._save()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"清空失败: {e}")
            return
        self._load_summary()
        # 通知主窗口刷新
        try:
            if self.parent() and hasattr(self.parent(), "_refresh_line_health_badges"):
                self.parent()._refresh_line_health_badges()
        except Exception:
            pass
        QMessageBox.information(self, "已清空", "已清空所有健康度数据。")


class CountryFilterDialog(QDialog):
    """国家多选对话框：搜索 + 全选/清空 + 5 列网格 + 确认/取消

    Batch 2
    """

    # 热门国家放前面（按用户使用频率排序）
    HOT_COUNTRIES = [
        "CN", "HK", "TW", "JP", "KR", "SG", "US", "GB", "DE", "FR",
        "CA", "AU", "MY", "TH", "PH", "VN", "ID", "IN", "RU", "BR",
        "NL", "IT", "ES", "SE", "NO", "FI", "CH", "AT", "BE", "IE",
        "PL", "TR", "AE", "SA", "IL", "EG", "ZA", "MX", "AR", "CL",
        "NZ", "UA", "CZ", "PT", "GR", "HU", "DK", "RO", "BG", "NG",
    ]

    def __init__(self, current: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择国家/地区")
        self.setMinimumSize(720, 560)
        self.resize(780, 620)
        # 暗黑风格
        self.setStyleSheet(
            f"QDialog {{ background-color: {COLOR_BG}; color: {COLOR_TEXT}; }}"
            f"QLineEdit {{ background-color: #111; color: {COLOR_TEXT}; border: 1px solid {COLOR_BORDER}; "
            f"border-radius: 4px; padding: 5px 8px; font-size: 9pt; }}"
            f"QLabel {{ color: {COLOR_TEXT}; }}"
        )
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._selected: set = set(c.upper() for c in current if c)
        self._build_ui()
        self._sync_checkboxes()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # 顶部说明
        tip = QLabel("勾选你需要的代理出口国家/地区，保存后下次使用线路时自动按白名单过滤节点。")
        tip.setStyleSheet("color: #aaa; font-size: 8pt;")
        tip.setWordWrap(True)
        root.addWidget(tip)

        # 搜索 + 计数 + 全选/清空
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索国家 / 地区 (中文/英文/代码)")
        self.search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_edit, stretch=1)
        # 计数
        self.count_lbl = QLabel("已选 0")
        self.count_lbl.setStyleSheet(f"color: {COLOR_GREEN}; font-size: 8pt; font-weight: bold; padding: 0 4px;")
        toolbar.addWidget(self.count_lbl)
        # 全选
        all_btn = QPushButton("全选")
        all_btn.setFixedHeight(26)
        all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        all_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_BLUE}; color: #fff; font-size: 8pt; "
            f"border-radius: 4px; border: none; padding: 0 10px; }}"
            f"QPushButton:hover {{ background-color: {COLOR_BLUE_LIGHT}; }}"
        )
        all_btn.clicked.connect(self._on_select_all_visible)
        toolbar.addWidget(all_btn)
        # 清空
        none_btn = QPushButton("清空")
        none_btn.setFixedHeight(26)
        none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        none_btn.setStyleSheet(
            f"QPushButton {{ background-color: #2a2a2a; color: {COLOR_TEXT}; font-size: 8pt; "
            f"border-radius: 4px; border: 1px solid {COLOR_BORDER}; padding: 0 10px; }}"
            f"QPushButton:hover {{ background-color: #3a3a3a; }}"
        )
        none_btn.clicked.connect(self._on_clear_all)
        toolbar.addWidget(none_btn)
        root.addLayout(toolbar)

        # 滚动区 + 5 列网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {COLOR_BG}; border: 1px solid {COLOR_BORDER}; border-radius: 4px; }}"
            f"QScrollArea > QWidget > QWidget {{ background-color: {COLOR_BG}; }}"
        )
        grid_widget = QWidget()
        grid_widget.setStyleSheet(f"background-color: {COLOR_BG};")
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setHorizontalSpacing(8)
        self.grid_layout.setVerticalSpacing(4)
        scroll.setWidget(grid_widget)
        root.addWidget(scroll, stretch=1)

        # 顺序：热门国家 → 全部国家
        all_codes = self.HOT_COUNTRIES + sorted(
            c for c in COUNTRY_NAMES.keys() if c not in self.HOT_COUNTRIES
        )
        # 去重
        seen = set()
        self._ordered_codes = []
        for c in all_codes:
            if c and c not in seen:
                seen.add(c)
                self._ordered_codes.append(c)
        for code in self._ordered_codes:
            name = COUNTRY_NAMES.get(code, code)
            flag = country_flag(code)
            chk = QCheckBox(f"{flag}  {name}  ({code})")
            chk.setCursor(Qt.CursorShape.PointingHandCursor)
            chk.setStyleSheet(
                f"QCheckBox {{ color: {COLOR_TEXT}; spacing: 6px; font-size: 9pt; padding: 2px 4px; }}"
                f"QCheckBox:hover {{ color: {COLOR_GREEN}; }}"
                f"QCheckBox::indicator {{ width: 14px; height: 14px; }}"
            )
            chk.toggled.connect(lambda checked, c=code: self._on_item_toggled(c, checked))
            self._checkboxes[code] = chk

        # 5 列布局
        self._relayout_grid("")

        # 确认/取消
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(28)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background-color: #2a2a2a; color: {COLOR_TEXT}; font-size: 9pt; "
            f"border-radius: 4px; border: 1px solid {COLOR_BORDER}; padding: 0 20px; }}"
            f"QPushButton:hover {{ background-color: #3a3a3a; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("确认选择")
        ok_btn.setFixedHeight(28)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_GREEN}; color: #fff; font-size: 9pt; "
            f"font-weight: bold; border-radius: 4px; border: none; padding: 0 20px; }}"
            f"QPushButton:hover {{ background-color: #2E7D32; }}"
        )
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

    def _relayout_grid(self, keyword: str):
        """按 keyword 过滤后重新摆放到 5 列网格里"""
        # 清空旧位置
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                # 立即重新加入下方（不能 deleteLater，会失去引用）
        kw = (keyword or "").strip().lower()
        cols = 5
        row = 0
        col = 0
        for code in self._ordered_codes:
            chk = self._checkboxes.get(code)
            if not chk:
                continue
            name = COUNTRY_NAMES.get(code, code)
            label_text = f"{country_flag(code)}  {name}  ({code})".lower()
            if kw and kw not in label_text and kw not in code.lower():
                chk.hide()
                continue
            chk.show()
            self.grid_layout.addWidget(chk, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1
        # 如果全部被过滤，添加一个占位提示
        if self.grid_layout.count() == 0:
            placeholder = QLabel("（无匹配的国家）")
            placeholder.setStyleSheet("color: #666; font-size: 9pt; padding: 20px;")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(placeholder, 0, 0, 1, cols)
        # 占位
        self.grid_layout.setRowStretch(self.grid_layout.rowCount(), 1)

    def _on_search_changed(self, text: str):
        self._relayout_grid(text)

    def _on_item_toggled(self, code: str, checked: bool):
        if checked:
            self._selected.add(code)
        else:
            self._selected.discard(code)
        self._update_count()

    def _on_select_all_visible(self):
        # 仅勾选当前可见项
        for code, chk in self._checkboxes.items():
            if chk.isVisible():
                chk.setChecked(True)
        self._update_count()

    def _on_clear_all(self):
        for chk in self._checkboxes.values():
            chk.setChecked(False)
        self._update_count()

    def _sync_checkboxes(self):
        """根据已选集合同步勾选状态"""
        for code, chk in self._checkboxes.items():
            chk.setChecked(code in self._selected)
        self._update_count()

    def _update_count(self):
        n = len(self._selected)
        self.count_lbl.setText(f"已选 {n}")
        if n == 0:
            self.count_lbl.setStyleSheet("color: #888; font-size: 8pt; font-weight: bold; padding: 0 4px;")
        else:
            self.count_lbl.setStyleSheet(f"color: {COLOR_GREEN}; font-size: 8pt; font-weight: bold; padding: 0 4px;")

    def get_selected(self) -> List[str]:
        return sorted(self._selected)


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


# ══════════════════════════════════════════════════════════════
# 单实例控制（架构参照 云集智能编程工作站/1.PC v2.0）
# 杀同名前缀的旧 EXE / 旧 python main.py 进程 → 创建命名 mutex 占位
# ══════════════════════════════════════════════════════════════

_k32 = ctypes.windll.kernel32
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_TH32CS_SNAPPROCESS = 0x00000002

# 固定字符串 mutex 名（不带版本号）：升级是"关旧开新"，不存在同时跑
_MUTEX_NAME = "YunJi_NetworkProxy_SingleInstance"
_instance_mutex = None


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("cntUsage", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("cntThreads", ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def _kill_same_name_processes():
    """杀掉所有同名旧进程，确保单实例。

    - 冻结模式（运行的是 .exe）：按 EXE 文件名前缀匹配 BRAND_NAME
    - 开发模式（运行的是 python.exe / pythonw.exe）：用 psutil 取命令行，
      包含 main.py 即视为本项目进程

    同时跳过「当前进程 + 祖先链」，防止杀到自己的父/祖父导致自己被连带结束。
    """
    if sys.platform != 'win32':
        return

    my_pid = _k32.GetCurrentProcessId()
    is_frozen = getattr(sys, 'frozen', False)
    # 关键：用 BRAND_NAME（不含版本号）作前缀，因为 EXE 文件名可能是
    #   云集智能网联代理专家.exe                    （简化名）
    #   云集智能网联代理专家-v2026.06.17.2025.exe  （带版本号，-v 不是 " v"）
    #   云集智能网联代理专家 v2026.06.17.2025.exe  （理论上不会出现）
    # APP_NAME 形如 "云集智能网联代理专家 v2026.06.17.2025" 永远 startswith 不上。
    base_prefix = BRAND_NAME.lower()
    # 本项目 app 目录（dev 模式判定基准）：只有工作目录/命令行指向此目录的
    # python 进程才视为本项目旧实例，避免误杀 ComfyUI、视频创意站等 python 应用
    app_dir = os.path.dirname(os.path.abspath(__file__)).lower()

    # 1. 收集当前进程的祖先链（防止杀到自己的父进程把自己也带走）
    my_ancestor_pids = set()
    try:
        import psutil as _ps_anc
        cur = _ps_anc.Process(my_pid)
        while True:
            par = cur.parent()
            if par is None or par.pid == 0:
                break
            my_ancestor_pids.add(par.pid)
            cur = par
    except Exception:
        pass

    # 2. 创建进程快照
    snap = _k32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if snap == _INVALID_HANDLE_VALUE:
        return

    entry = _PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
    pids_to_kill = []

    if _k32.Process32FirstW(snap, ctypes.byref(entry)):
        while True:
            pid = entry.th32ProcessID
            if pid != my_pid and pid not in my_ancestor_pids:
                exe_name = (entry.szExeFile or "").lower()
                should_kill = False
                if is_frozen:
                    # 冻结模式：按 EXE 文件名前缀匹配
                    should_kill = (
                        exe_name.startswith(base_prefix)
                        and exe_name.endswith('.exe')
                    )
                else:
                    # 开发模式：python.exe / pythonw.exe + 命令行/工作目录指向本项目 dev/app
                    # 关键：不能只匹配 'main.py'（ComfyUI、视频创意站等都是 python main.py 启动），
                    # 必须限定到本项目目录，否则会误杀其它 python 应用。
                    if exe_name in ('python.exe', 'pythonw.exe'):
                        try:
                            import psutil
                            p = psutil.Process(pid)
                            cl = ' '.join(p.cmdline()).lower()
                            cwd = (p.cwd() or '').lower()
                            if 'main.py' in cl and (app_dir in cl or app_dir == cwd or app_dir in cwd):
                                should_kill = True
                        except Exception:
                            pass
                if should_kill:
                    pids_to_kill.append(pid)

            entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
            if not _k32.Process32NextW(snap, ctypes.byref(entry)):
                break

    _k32.CloseHandle(snap)

    # 3. 杀进程（TerminateProcess 是异步的，调用后立即返回）
    PROCESS_TERMINATE = 0x0001
    for pid in pids_to_kill:
        h = _k32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if h:
            _k32.TerminateProcess(h, 0)
            _k32.CloseHandle(h)

    # 4. 等被杀进程真正退出（≤2s），否则 mutex 占位会冲突
    if pids_to_kill:
        STILL_ACTIVE = 259
        for _ in range(20):
            time.sleep(0.1)
            still_alive = []
            for pid in pids_to_kill:
                h = _k32.OpenProcess(0x00100000, False, pid)
                if h:
                    exit_code = ctypes.c_ulong()
                    if _k32.GetExitCodeProcess(h, ctypes.byref(exit_code)) and exit_code.value == STILL_ACTIVE:
                        still_alive.append(pid)
                    _k32.CloseHandle(h)
            if not still_alive:
                break


def _ensure_single_instance():
    """单实例控制：杀同名进程 → mutex 占位（防 race）。"""
    global _instance_mutex
    if sys.platform != 'win32':
        return

    # 1. 杀所有同名旧进程
    _kill_same_name_processes()

    # 2. 创建 mutex 占位
    _instance_mutex = _k32.CreateMutexW(None, True, _MUTEX_NAME)
    ERROR_ALREADY_EXISTS = 183
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        # 兜底：race 时再杀一次
        _k32.CloseHandle(_instance_mutex)
        _instance_mutex = None
        _kill_same_name_processes()
        _instance_mutex = _k32.CreateMutexW(None, True, _MUTEX_NAME)
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            _k32.CloseHandle(_instance_mutex)
            _instance_mutex = None
            ctypes.windll.user32.MessageBoxW(
                0,
                f"{APP_NAME} 旧实例未能退出，请手动结束进程后重试。",
                "提示",
                0x40
            )
            sys.exit(0)


def _cleanup_single_instance():
    """清理单实例资源（仅在真正退出时调用，最小化到托盘不释放）。"""
    global _instance_mutex
    if _instance_mutex:
        try:
            _k32.ReleaseMutex(_instance_mutex)
        except Exception:
            pass
        try:
            _k32.CloseHandle(_instance_mutex)
        except Exception:
            pass
        _instance_mutex = None


def _kill_stale_kernels():
    """启动硬防护：清空上一会话遗留的 quick.exe 孤儿内核。

    关闭窗口(X)默认最小化到托盘而非真正退出，旧内核进程不会随窗口关闭而被
    stop_quick() 终止，会一直占用 7890/9090。单实例机制在启动早期会杀掉旧 EXE，
    但被杀 EXE 的子进程 quick.exe 会变成孤儿继续占端口；下次启动新内核因子端口被占
    无法绑定 → “代理未就绪”。

    单实例已保证当前只有本 app 一个实例，故启动初期尚不存在任何“本实例”内核，
    此时全盘 taskkill quick.exe 是安全的（不会误杀正在用的内核）。
    """
    try:
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0
        _r = subprocess.run(
            ["taskkill", "/f", "/im", "quick.exe"],
            capture_output=True, startupinfo=_si,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
        )
        _out = (_r.stdout or b"").decode("gbk", "ignore")
        if "SUCCESS" in _out:
            log.info("启动清理：已终止上一会话遗留的 quick.exe 孤儿进程")
    except Exception as e:
        log.debug(f"启动清理遗留内核失败（可忽略）: {e}")


def main():
    # 自动部署（首跑建品牌文件夹+入口并 os._exit 切换到入口；已部署态清理/切版本）。
    # 必须放在单实例之前：便携 exe 部署阶段不持有互斥体，避免入口（子进程）被
    # 自身 mutex 误判“已运行”而退出（见 _ensure_single_instance 的祖先链跳过逻辑）。
    if getattr(sys, 'frozen', False):
        _self_deploy()

    # 单实例控制：杀同名前缀的旧 EXE / 旧 python main.py → mutex 占位
    # 这是整个进程生命周期的第一步，必须在任何 QApplication 资源创建之前完成
    _ensure_single_instance()

    # 启动硬防护：单实例刚杀掉旧 EXE，其遗留的 quick.exe 孤儿仍占 7890/9090。
    # 在启动任何内核之前先清空，避免新内核因端口被占绑不上 → “代理未就绪”。
    _kill_stale_kernels()

    # 清除残留的代理环境变量（上次关闭时未清理会导致所有网络请求指向死代理）
    _DEFAULT_PROXY_ENVS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy")
    for _k in _DEFAULT_PROXY_ENVS:
        try:
            del os.environ[_k]
        except KeyError:
            pass

    sys.excepthook = _global_exception_handler

    # 退出兜底：任何退出路径（正常退出、未捕获异常）都强杀代理内核，
    # 杜绝 quick.exe 进程残留（_self_deploy 的 os._exit 不经过 atexit，故不影响部署切换）。
    import atexit
    def _atexit_kill_kernel():
        try:
            _si = subprocess.STARTUPINFO()
            _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            _si.wShowWindow = 0
            subprocess.run(
                ["taskkill", "/f", "/im", "quick.exe"],
                capture_output=True, startupinfo=_si,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
            )
        except Exception:
            pass
    atexit.register(_atexit_kill_kernel)

    # 启动时确保内置默认备选上游仓库存在（首次启动自动写入 backup_sources.json）
    ensure_builtin_backup_sources()

    # 高精度DPI缩放：PassThrough不取整缩放因子，保证各分辨率下界面比例一致
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

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
