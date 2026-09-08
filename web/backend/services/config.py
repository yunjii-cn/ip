import os
import sys
import json
import logging
from datetime import datetime

log = logging.getLogger("yunji")


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

BRAND_NAME = _CFG["brand_name"]
# 冻结（PyInstaller 单文件 exe）模式下，版本号必须固定，否则每次启动都变。
# 由 build_web.py 注入 _build_version.txt（含构建时间戳），运行时从 MEIPASS 读取。
if getattr(sys, 'frozen', False):
    try:
        with open(os.path.join(getattr(sys, '_MEIPASS', ''), '_build_version.txt'),
                  'r', encoding='utf-8') as _bvf:
            VERSION = (_bvf.read().strip() or datetime.now().strftime(_CFG["version_format"]))
    except Exception:
        VERSION = datetime.now().strftime(_CFG["version_format"])
else:
    VERSION = datetime.now().strftime(_CFG["version_format"])
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


def get_base_dir():
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        for _ in range(3):
            if os.path.isfile(os.path.join(exe_dir, _CFG["paths"]["lock_file"])):
                return exe_dir
            parent = os.path.dirname(exe_dir)
            if parent == exe_dir:
                break
            exe_dir = parent
        if os.path.isdir(os.path.join(exe_dir, _CFG["paths"]["app"])):
            return exe_dir
        return os.path.dirname(sys.executable)
    search_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _ in range(4):
        if os.path.isfile(os.path.join(search_dir, _CFG["paths"]["lock_file"])):
            return search_dir
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            break
        search_dir = parent
    search_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _ in range(4):
        if os.path.isdir(os.path.join(search_dir, _CFG["paths"]["app"])):
            return search_dir
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            break
        search_dir = parent
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_dir():
    d = os.path.join(get_base_dir(), _CFG["paths"]["app"])
    os.makedirs(d, exist_ok=True)
    return d


def get_ver_dir():
    d = os.path.join(get_base_dir(), _CFG["paths"]["ver"])
    os.makedirs(d, exist_ok=True)
    return d


def get_dist_dir():
    d = os.path.join(get_base_dir(), _CFG["paths"]["dist"])
    os.makedirs(d, exist_ok=True)
    return d


SETTINGS_FILE = os.path.join(get_app_dir(), "settings.json")


def load_settings():
    try:
        if os.path.isfile(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"保存设置失败: {e}")


settings = load_settings()

PROXY_HOST = settings.get("proxy_host", "127.0.0.1")
PROXY_PORT = settings.get("proxy_port", 7890)

_GITLAB_MIRROR = "https://www.gitlabip.xyz"
_GITLAB_RAW_TPL = "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/{n}/config.yaml"
_GITLAB_MIRROR_TPL = _GITLAB_MIRROR + "/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/{n}/config.yaml"

# 线路配置下载源：与桌面端完全一致，走 GitLab 镜像链路（gitlabip.xyz / gitlab.com），
# 国内直连可达，规避 GitHub raw 被 GFW 封锁导致"只测到部分线路 / 全失败"。
# 4 条线路映射到 free9999/ipupdate 的 quick/1..4，内容同源。
CONFIG_URLS = [
    ("线路1", _GITLAB_MIRROR_TPL.format(n=1), _GITLAB_RAW_TPL.format(n=1)),
    ("线路2", _GITLAB_MIRROR_TPL.format(n=2), _GITLAB_RAW_TPL.format(n=2)),
    ("线路3", _GITLAB_MIRROR_TPL.format(n=3), _GITLAB_RAW_TPL.format(n=3)),
    ("线路4", _GITLAB_MIRROR_TPL.format(n=4), _GITLAB_RAW_TPL.format(n=4)),
]

# 内置存活默认节点（烤进包的 config.default.yaml，anytls2 真实可用节点）。
# 作为一条保底竞速线路参与检测，保证开箱即有一条可用线路，
# 避免内置免费源(gitlabip)节点集体失效时"检测线路"整页超时、用户误以为软件坏掉。
BUILTIN_DEFAULT_LINE_NAME = "默认节点(anytls2)"


def _update_proxy_url():
    global PROXY_HOST, PROXY_PORT
    PROXY_URL = f"{PROXY_HOST}:{PROXY_PORT}"
    return PROXY_URL


def find_system_browsers():
    import winreg as _winreg
    browsers = []
    paths = [
        ("Chrome", os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe")),
        ("Chrome (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe")),
        ("Chrome User", os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")),
        ("Edge", os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")),
        ("Edge (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")),
        ("Firefox", os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe")),
        ("Firefox (x86)", os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe")),
    ]

    def _reg_enum(hive):
        results = []
        for root_key in [
            r"SOFTWARE\Clients\StartMenuInternet",
            r"SOFTWARE\WOW6432Node\Clients\StartMenuInternet",
        ]:
            try:
                key = _winreg.OpenKey(hive, root_key, 0, _winreg.KEY_READ | _winreg.KEY_WOW64_64KEY)
                i = 0
                while True:
                    try:
                        subkey_name = _winreg.EnumKey(key, i)
                        i += 1
                        try:
                            sk = _winreg.OpenKey(key, fr"{subkey_name}\shell\open\command")
                            cmd, _ = _winreg.QueryValueEx(sk, "")
                            _winreg.CloseKey(sk)
                            if cmd:
                                exe_path = cmd.strip('"').split('"')[0] if '"' in cmd else cmd.split()[0]
                                if os.path.isfile(exe_path):
                                    results.append((subkey_name, exe_path))
                        except Exception:
                            pass
                    except Exception:
                        break
                _winreg.CloseKey(key)
            except Exception:
                pass
        return results

    browsers.extend(_reg_enum(_winreg.HKEY_LOCAL_MACHINE))
    browsers.extend(_reg_enum(_winreg.HKEY_CURRENT_USER))

    seen = set()
    unique = []
    for name, path in browsers + paths:
        if path not in seen and os.path.isfile(path):
            seen.add(path)
            unique.append((name, path))
    return unique
