import os
import sys
import re
import json
import ssl
import shutil
import urllib.request
import urllib.parse
import subprocess
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load_project_config():
    _cfg_path = os.path.join(PROJECT_ROOT, "project.json")
    _defaults = {
        "brand_name": "云集代理",
        "repos": {"github": "yunjii-cn/ip", "gitee": "yunjii/ip"},
        "paths": {"version_json": "release/version.json", "dev": "dev", "app": "app", "ver": "ver", "build": "build", "release": "release"}
    }
    try:
        with open(_cfg_path, "r", encoding="utf-8") as f:
            import copy
            cfg = copy.deepcopy(_defaults)
            loaded = json.load(f)
            for k, v in loaded.items():
                if k in cfg and isinstance(cfg[k], dict) and isinstance(v, dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
            return cfg
    except Exception:
        return _defaults

_CFG = _load_project_config()

DEV_DIR = os.path.join(PROJECT_ROOT, _CFG["paths"]["dev"])
APP_DIR = os.path.join(DEV_DIR, _CFG["paths"]["app"])
VER_DIR = os.path.join(DEV_DIR, _CFG["paths"]["ver"])
BUILD_ROOT = os.path.join(PROJECT_ROOT, _CFG["paths"]["build"])

GITHUB_REPO = _CFG["repos"]["github"]
GITEE_REPO = _CFG["repos"]["gitee"]
BRAND_NAME = _CFG["brand_name"]


def _load_token(filename):
    token_path = os.path.join(APP_DIR, filename)
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


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _api_request(url, method="GET", data=None, headers=None, timeout=30):
    if headers is None:
        headers = {}
    headers["User-Agent"] = "YunjiRelease/1.0"
    if data is not None and isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}, resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(body)
        except Exception:
            err_json = {"raw": body}
        return err_json, e.code
    except Exception as e:
        return {"error": str(e)}, 0


def _get_last_release_tag():
    try:
        r = subprocess.run(
            ["git", "tag", "--list", "v*", "--sort=-version:refname"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    return ""


def _check_bundled_kernel():
    """发布前校验：Quick 目录必须包含完整的内核文件。
    与 build.py 内的校验逻辑保持一致——确保用户在 main() 第一步就发现问题，
    避免在收集版本描述、调用 build.py 之后才发现要修补内核。
    返回 (ok, version_str)：ok=True 时 version_str 是当前内核版本号。
    """
    quick_src = os.path.join(APP_DIR, "Quick")
    if not os.path.isdir(quick_src):
        print(f"❌ Quick 目录不存在: {quick_src}")
        print(f"   请先创建 dev/app/Quick/ 目录并放入内核文件")
        return False, ""
    missing = []
    quick_exe_path = os.path.join(quick_src, "quick.exe")
    if not os.path.isfile(quick_exe_path):
        missing.append("Quick/quick.exe (当前使用内核的硬链接入口)")
    ver_file = os.path.join(quick_src, "_kernel_version.txt")
    if not os.path.isfile(ver_file):
        missing.append("Quick/_kernel_version.txt (内核版本号标记)")
    kernels_dir = os.path.join(quick_src, "kernels")
    if not os.path.isdir(kernels_dir):
        missing.append("Quick/kernels/ (内核版本仓库目录)")
    else:
        kernel_exes = [f for f in os.listdir(kernels_dir)
                       if f.lower().endswith('.exe') and os.path.isfile(os.path.join(kernels_dir, f))]
        if not kernel_exes:
            missing.append("Quick/kernels/*.exe (至少一个 mihomo 内核可执行文件)")
    if missing:
        print(f"❌ Quick 目录内核不完整，发布中止：")
        for m in missing:
            print(f"   缺失: {m}")
        print(f"\n修复步骤：")
        print(f"   1. 把 mihomo 内核(如 mihomo_v1.19.27.exe)放到 {kernels_dir}/")
        print(f"   2. 在 {quick_src}/ 下执行 mklink /H quick.exe kernels\\mihomo_v1.19.27.exe")
        print(f"   3. 在 {ver_file} 写入当前版本号(如 1.19.27)")
        return False, ""
    with open(ver_file, "r", encoding="utf-8") as _f:
        current_kernel_ver = _f.read().strip()
    print(f"内核校验通过: quick.exe → {os.path.realpath(quick_exe_path)} (v{current_kernel_ver})")
    return True, current_kernel_ver


def _auto_detect_changes():
    changes = []

    last_tag = _get_last_release_tag()
    if last_tag:
        try:
            r = subprocess.run(
                ["git", "log", "--oneline", f"{last_tag}..HEAD"],
                cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0 and r.stdout.strip():
                for line in r.stdout.strip().split("\n"):
                    msg = line.split(" ", 1)[-1].strip() if " " in line else line.strip()
                    if msg and msg not in changes:
                        changes.append(msg)
        except Exception:
            pass

    if not changes:
        try:
            r = subprocess.run(
                ["git", "log", "--oneline", "-20"],
                cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0 and r.stdout.strip():
                for line in r.stdout.strip().split("\n"):
                    msg = line.split(" ", 1)[-1].strip() if " " in line else line.strip()
                    if msg and msg not in changes:
                        changes.append(msg)
        except Exception:
            pass

    if not changes:
        try:
            r = subprocess.run(
                ["git", "diff", "--stat", "HEAD~5"],
                cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0 and r.stdout.strip():
                for line in r.stdout.strip().split("\n"):
                    if "|" in line:
                        fname = line.split("|")[0].strip()
                        if fname:
                            changes.append(f"更新 {fname}")
        except Exception:
            pass

    if not changes:
        changes = ["常规更新与优化"]

    return changes[:10]


def _manual_input_changes():
    print("\n无法自动检测变更，请手动输入更新内容。")
    print("每行输入一条，输入空行结束:")
    changes = []
    while True:
        try:
            line = input(f"  {len(changes) + 1}. ").strip()
        except EOFError:
            break
        if not line:
            break
        changes.append(line)
    if not changes:
        changes = ["常规更新与优化"]
    return changes


def step_collect_changes():
    print("\n" + "=" * 60)
    print("步骤 1/7: 收集变更描述")
    print("=" * 60)

    vh_path = os.path.join(APP_DIR, "versions.json")
    existing_changes = []
    if os.path.isfile(vh_path):
        try:
            with open(vh_path, "r", encoding="utf-8") as f:
                vh = json.load(f)
            if vh and isinstance(vh, list):
                existing_changes = vh[0].get("changes", [])
        except Exception:
            pass

    if existing_changes:
        print(f"从 versions.json 读取到 {len(existing_changes)} 条变更:")
        for i, c in enumerate(existing_changes, 1):
            print(f"  {i}. {c}")
        return existing_changes

    auto_changes = _auto_detect_changes()
    is_generic = (len(auto_changes) == 1 and auto_changes[0] == "常规更新与优化")

    if is_generic:
        print("未能自动检测变更（可能没有Git提交记录）")
        final_changes = _manual_input_changes()
        print(f"\n最终变更描述 ({len(final_changes)} 条):")
        for i, c in enumerate(final_changes, 1):
            print(f"  {i}. {c}")
        return final_changes

    print(f"自动检测到 {len(auto_changes)} 条变更:")
    for i, c in enumerate(auto_changes, 1):
        print(f"  {i}. {c}")

    changes_file = os.path.join(BUILD_ROOT, "_release_changes.txt")
    with open(changes_file, "w", encoding="utf-8") as f:
        f.write("# 请在下方填写本版本的更新内容，每行一条\n")
        f.write("# 以 # 开头的行为注释，空行会被忽略\n")
        f.write("# 保存后关闭编辑器，发布脚本将自动读取\n")
        f.write("# ====== 自动检测的变更（可修改/删除/补充）======\n")
        for c in auto_changes:
            f.write(f"{c}\n")

    print(f"\n已生成变更描述文件: {changes_file}")
    print("请在编辑器中修改后保存关闭...")

    editor = os.environ.get("EDITOR", "")
    if not editor:
        for candidate in ["code", "notepad", "notepad++"]:
            try:
                r = subprocess.run(
                    ["where", candidate],
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0:
                    editor = candidate
                    break
            except Exception:
                continue
    if not editor:
        editor = "notepad"

    try:
        subprocess.run([editor, changes_file], cwd=BUILD_ROOT)
    except Exception:
        print(f"无法启动编辑器，请手动编辑: {changes_file}")
        input("编辑完成后按回车继续...")

    final_changes = []
    if os.path.isfile(changes_file):
        with open(changes_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    final_changes.append(line)
        try:
            os.remove(changes_file)
        except Exception:
            pass

    if not final_changes:
        final_changes = auto_changes

    print(f"\n最终变更描述 ({len(final_changes)} 条):")
    for i, c in enumerate(final_changes, 1):
        print(f"  {i}. {c}")
    return final_changes


def step_build():
    print("\n" + "=" * 60)
    print("步骤 2/7: 构建 EXE 和整合包")
    print("=" * 60)
    build_script = os.path.join(BUILD_ROOT, "build.py")
    if not os.path.isfile(build_script):
        print(f"错误: 构建脚本不存在 {build_script}")
        return False
    result = subprocess.run([sys.executable, build_script], cwd=BUILD_ROOT)
    if result.returncode != 0:
        print("构建失败!")
        return False
    print("构建成功!")
    return True


def step_stabilize():
    print("\n" + "=" * 60)
    print("步骤 2.5/7: 稳定化（dist → ver）")
    print("=" * 60)

    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    if not os.path.isdir(dist_dir):
        print("dist目录不存在，跳过稳定化")
        return True

    latest_exe = None
    latest_mtime = 0
    for f in os.listdir(dist_dir):
        if (f.startswith("云集代理-v") or f.startswith("云集智能网联代理专家-v")) and f.endswith(".exe"):
            fpath = os.path.join(dist_dir, f)
            mtime = os.path.getmtime(fpath)
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_exe = fpath

    if not latest_exe:
        print("dist目录中未找到新构建的EXE，跳过稳定化")
        return True

    ver_already = os.path.join(VER_DIR, os.path.basename(latest_exe))
    if os.path.isfile(ver_already):
        print(f"ver目录中已存在: {os.path.basename(latest_exe)}")
        return True

    os.makedirs(VER_DIR, exist_ok=True)
    shutil.move(latest_exe, ver_already)
    print(f"EXE已移入稳定版仓库: {ver_already}")

    entry_exe = os.path.join(DEV_DIR, "云集代理.exe")
    if os.path.isfile(entry_exe):
        try:
            os.remove(entry_exe)
        except PermissionError:
            print(f"警告: 无法删除旧入口EXE（可能正在运行）: {entry_exe}")
    try:
        subprocess.run(
            ['cmd', '/c', 'mklink', '/H', entry_exe, ver_already],
            check=True, capture_output=True
        )
        print(f"硬链接已重建: {entry_exe} → {ver_already}")
    except Exception as e:
        print(f"警告: 无法创建硬链接: {e}")

    return True


def step_get_version(changes):
    print("\n" + "=" * 60)
    print("步骤 3/7: 获取版本信息")
    print("=" * 60)

    latest_exe = None
    latest_mtime = 0
    for search_dir in [VER_DIR, os.path.join(PROJECT_ROOT, "dist")]:
        if not os.path.isdir(search_dir):
            continue
        for f in os.listdir(search_dir):
            if (f.startswith("云集代理-v") or f.startswith("云集智能网联代理专家-v")) and f.endswith(".exe"):
                fpath = os.path.join(search_dir, f)
                mtime = os.path.getmtime(fpath)
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_exe = fpath

    if not latest_exe:
        print("错误: ver/ 和 dist/ 中均未找到EXE")
        return None

    m = re.search(r'v(\d+\.\d+\.\d+\.\d+)', os.path.basename(latest_exe))
    version = m.group(1) if m else datetime.now().strftime("%Y.%m.%d.%H%M")
    ver_exe = latest_exe

    exe_name = f"云集代理-v{version}"
    zip_path = os.path.join(BUILD_ROOT, f"v{version}", f"云集代理-v{version}.zip")

    if not os.path.isfile(ver_exe):
        print(f"错误: EXE不存在 {ver_exe}")
        return None
    if not os.path.isfile(zip_path):
        print(f"错误: 整合包不存在 {zip_path}")
        return None

    info = {
        "version": version,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "exe_name": exe_name,
        "exe_path": ver_exe,
        "zip_path": zip_path,
        "filename": f"{exe_name}.exe",
        "zip_filename": f"云集代理-v{version}.zip",
        "size_mb": round(os.path.getsize(ver_exe) / 1024 / 1024, 1),
        "zip_size_mb": round(os.path.getsize(zip_path) / 1024 / 1024, 1),
        "changes": changes,
    }
    print(f"版本号: {version}")
    print(f"EXE: {ver_exe} ({info['size_mb']} MB)")
    print(f"整合包: {zip_path} ({info['zip_size_mb']} MB)")
    print(f"更新内容: {len(changes)} 条")
    return info


def step_update_version_json(info):
    print("\n" + "=" * 60)
    print(f"步骤 4/7: 更新 {_CFG['paths']['version_json']} + versions.json")
    print("=" * 60)

    # 1. 更新 versions.json（版本历史，只记录正式发布版本）
    vh_path = os.path.join(APP_DIR, "versions.json")
    vh = []
    if os.path.isfile(vh_path):
        try:
            with open(vh_path, "r", encoding="utf-8") as f:
                vh = json.load(f)
        except Exception:
            pass

    existing_vh_versions = [v.get("version", "") for v in vh if isinstance(v, dict)]
    if info["version"] not in existing_vh_versions:
        vh.insert(0, {
            "version": info["version"],
            "date": info["date"],
            "changes": info["changes"],
        })
        with open(vh_path, "w", encoding="utf-8") as f:
            json.dump(vh, f, ensure_ascii=False, indent=4)
        print(f"已更新: {vh_path}")

    # 2. 从 versions.json 生成 release/version.json（远程更新检查用）
    vj_path = os.path.join(PROJECT_ROOT, *_CFG["paths"]["version_json"].split("/"))
    os.makedirs(os.path.dirname(vj_path), exist_ok=True)

    vj = {"latest": info["version"], "versions": []}
    for v in vh:
        if isinstance(v, dict) and v.get("version"):
            vj["versions"].append({
                "version": v["version"],
                "date": v.get("date", ""),
                "filename": f"{BRAND_NAME}-v{v['version']}.exe",
                "size_mb": v.get("size_mb", 0),
                "changes": v.get("changes", []),
            })

    with open(vj_path, "w", encoding="utf-8") as f:
        json.dump(vj, f, ensure_ascii=False, indent=4)
    print(f"已更新: {vj_path} ({len(vj['versions'])} 个版本)")


def _build_commit_message(info):
    version = info["version"]
    changes = info.get("changes", [])

    if not changes:
        return f"v{version}: 常规更新"

    first = changes[0]
    if len(changes) == 1:
        return f"v{version}: {first}"

    summary = first
    if len(first) > 40:
        summary = first[:37] + "..."

    return f"v{version}: {summary} 等{len(changes)}项更新"


def step_git_push(info):
    print("\n" + "=" * 60)
    print("步骤 5/7: Git 提交并推送到 GitHub + Gitee")
    print("=" * 60)

    git_dir = PROJECT_ROOT
    git_cmd = "git"
    try:
        r = subprocess.run(["where", "git"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            git_cmd = r"D:\Program Files\Git\cmd\git.exe"
    except Exception:
        git_cmd = r"D:\Program Files\Git\cmd\git.exe"

    try:
        subprocess.run([git_cmd, "status"], cwd=git_dir, capture_output=True, check=True)
    except Exception:
        print("未检测到Git仓库，跳过Git推送")
        print("如需推送，请先初始化Git仓库并添加远程地址")
        return False

    subprocess.run([git_cmd, "add", "-A"], cwd=git_dir)

    commit_msg = _build_commit_message(info)
    result = subprocess.run(
        [git_cmd, "commit", "-m", commit_msg],
        cwd=git_dir, capture_output=True, text=True
    )
    if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
        print("没有需要提交的更改")
    else:
        print(f"已提交: {commit_msg}")
        for c in info.get("changes", []):
            print(f"  - {c}")

    result = subprocess.run([git_cmd, "push", "origin", "main"], cwd=git_dir, capture_output=True, text=True)
    if result.returncode == 0:
        print("已推送到 GitHub (origin)")
    else:
        print(f"推送到 GitHub 失败: {result.stderr.strip()}")

    result2 = subprocess.run([git_cmd, "push", "gitee", "main"], cwd=git_dir, capture_output=True, text=True)
    if result2.returncode == 0:
        print("已推送到 Gitee (gitee)")
    else:
        print(f"推送到 Gitee 失败: {result2.stderr.strip()}")

    return True


def step_github_release(info):
    print("\n" + "=" * 60)
    print("步骤 6/7: 创建 GitHub Release 并上传文件")
    print("=" * 60)

    github_token = _load_token(".github_token")
    if not github_token:
        print("警告: 未找到 .github_token，尝试匿名发布（公开仓库可能仍可创建Release）")
        print("建议在 dev/app/.github_token 中配置GitHub令牌以获得完整权限")

    tag = f"v{info['version']}"
    release_body = "## 更新内容\n\n"
    for i, c in enumerate(info["changes"], 1):
        release_body += f"{i}. {c}\n"
    release_body += f"\n---\n*发布时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*"

    create_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    create_data = {
        "tag_name": tag,
        "target_commitish": "main",
        "name": f"云集代理 {tag}",
        "body": release_body,
        "draft": False,
        "prerelease": False,
    }
    create_headers = {
        "Accept": "application/vnd.github+json",
    }
    if github_token:
        create_headers["Authorization"] = f"token {github_token}"

    print(f"创建 Release {tag}...")
    resp, status = _api_request(create_url, "POST", create_data, create_headers, timeout=30)

    if status != 201:
        print(f"创建 GitHub Release 失败 (HTTP {status}): {json.dumps(resp, ensure_ascii=False)}")
        return False

    release_id = resp.get("id")
    upload_url_template = resp.get("upload_url", "")
    print(f"Release 已创建, ID: {release_id}")

    if not upload_url_template:
        print("警告: 未获取到上传URL，尝试手动构建")
        upload_url_base = f"https://uploads.github.com/repos/{GITHUB_REPO}/releases/{release_id}/assets"
    else:
        upload_url_base = upload_url_template.replace("{?name,label}", "")

    upload_headers = {
        "Accept": "application/vnd.github+json",
    }
    if github_token:
        upload_headers["Authorization"] = f"token {github_token}"

    for label, fpath, fname in [
        ("EXE", info["exe_path"], info["filename"]),
        ("整合包", info["zip_path"], info["zip_filename"]),
    ]:
        print(f"上传 {label}: {fname} ({os.path.getsize(fpath) / 1024 / 1024:.1f} MB)...")
        upload_url = f"{upload_url_base}?name={urllib.parse.quote(fname)}"
        with open(fpath, "rb") as f:
            file_data = f.read()
        req = urllib.request.Request(
            upload_url, data=file_data, headers={
                **upload_headers,
                "Content-Type": "application/octet-stream",
            }, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=300, context=_ssl_ctx()) as resp_up:
                print(f"  上传成功 ({resp_up.status})")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"  上传失败 (HTTP {e.code}): {err_body[:200]}")
        except Exception as e:
            print(f"  上传失败: {e}")

    print("GitHub Release 完成!")
    return True


def _gitee_cleanup_old_assets(gitee_token, keep_count=5):
    GITEE_ASSET_LIMIT_MB = 900

    list_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/releases?access_token={gitee_token}&per_page=50"
    resp, status = _api_request(list_url, headers={"User-Agent": "YunjiRelease/1.0"})
    if status != 200 or not isinstance(resp, list):
        print("  无法获取Gitee Release列表，跳过清理")
        return

    total_size = 0
    release_assets = []
    for rel in resp:
        assets = rel.get("assets", [])
        rel_size = 0
        for a in assets:
            sz = a.get("size", 0)
            total_size += sz
            rel_size += sz
        release_assets.append({
            "id": rel.get("id"),
            "tag": rel.get("tag_name", ""),
            "assets": assets,
            "total_size": rel_size,
        })

    total_mb = total_size / 1024 / 1024
    print(f"  Gitee附件总占用: {total_mb:.1f} MB / {GITEE_ASSET_LIMIT_MB} MB")

    if total_mb < GITEE_ASSET_LIMIT_MB:
        print(f"  空间充足，无需清理")
        return

    release_assets.sort(key=lambda x: x["tag"], reverse=True)

    deleted_count = 0
    for rel in reversed(release_assets):
        if total_mb < GITEE_ASSET_LIMIT_MB:
            break
        kept = [r for r in release_assets if r["id"] != rel["id"]]
        if len(kept) < keep_count:
            print(f"  保留 {rel['tag']}（至少保留{keep_count}个版本）")
            break
        for a in rel["assets"]:
            aid = a.get("id")
            aname = a.get("name", "")
            del_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/releases/{rel['id']}/attach_files/{aid}?access_token={gitee_token}"
            del_resp, del_status = _api_request(del_url, "DELETE", headers={"User-Agent": "YunjiRelease/1.0"})
            if del_status in (200, 204):
                sz_mb = a.get("size", 0) / 1024 / 1024
                total_mb -= sz_mb
                deleted_count += 1
                print(f"  删除旧附件: {aname} ({sz_mb:.1f} MB)")
            else:
                print(f"  删除失败: {aname} (HTTP {del_status})")

    if deleted_count:
        print(f"  清理完成，已删除{deleted_count}个旧附件，当前占用 {total_mb:.1f} MB")
    else:
        print(f"  无法释放更多空间")


def step_gitee_release(info):
    print("\n" + "=" * 60)
    print("步骤 7/7: 创建 Gitee Release 并上传文件")
    print("=" * 60)

    gitee_token = _load_token(".gitee_token")
    if not gitee_token:
        print("错误: 未找到 .gitee_token，无法创建Gitee Release")
        print("请在 dev/app/.gitee_token 中配置Gitee个人访问令牌")
        return False

    tag = f"v{info['version']}"
    release_body = "## 更新内容\n\n"
    for i, c in enumerate(info["changes"], 1):
        release_body += f"{i}. {c}\n"

    create_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/releases"
    create_data = {
        "access_token": gitee_token,
        "tag_name": tag,
        "name": f"云集代理 {tag}",
        "body": release_body,
        "target_commitish": "main",
        "prerelease": False,
    }

    print(f"创建 Gitee Release {tag}...")

    print("检查Gitee附件空间...")
    _gitee_cleanup_old_assets(gitee_token, keep_count=5)

    resp, status = _api_request(create_url, "POST", create_data, timeout=30)

    if status not in (200, 201):
        print(f"创建 Gitee Release 失败 (HTTP {status}): {json.dumps(resp, ensure_ascii=False)}")
        return False

    release_id = resp.get("id")
    print(f"Release 已创建, ID: {release_id}")

    for label, fpath, fname in [
        ("EXE", info["exe_path"], info["filename"]),
    ]:
        print(f"上传 {label}: {fname} ({os.path.getsize(fpath) / 1024 / 1024:.1f} MB)...")
        upload_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/releases/{release_id}/attach_files"
        boundary = "----YunjiReleaseBoundary7MA4YWxkTrZu0gW"
        with open(fpath, "rb") as f:
            file_data = f.read()
        body_parts = []
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="access_token"\r\n\r\n'.encode())
        body_parts.append(f"{gitee_token}\r\n".encode())
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(
            f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'.encode()
        )
        body_parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
        body_parts.append(file_data)
        body_parts.append(f"\r\n--{boundary}--\r\n".encode())
        multipart_body = b"".join(body_parts)

        req = urllib.request.Request(
            upload_url, data=multipart_body, headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "YunjiRelease/1.0",
            }, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=300, context=_ssl_ctx()) as resp_up:
                print(f"  上传成功 ({resp_up.status})")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"  上传失败 (HTTP {e.code}): {err_body[:200]}")
        except Exception as e:
            print(f"  上传失败: {e}")

    print("Gitee Release 完成!")
    return True


def main():
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(
        description="云集代理 - 全自动发布脚本",
    )
    parser.add_argument(
        "--use-ver", action="store_true",
        help="跳过 build/stabilize 步骤，直接以 dev/ver/ 中已有 EXE 作为发布版本"
             "（适用于已手动将稳定版移入 ver/ 后再发布的场景）"
    )
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════╗")
    print("║     云集代理 - 全自动发布脚本            ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.use_ver:
        print("模式: --use-ver（跳过构建与稳定化，以 dev/ver/ 已有 EXE 为准）")

    # 步骤 0/7：发布前内核校验（比收集版本描述更早 fail-fast）
    ok, kernel_ver = _check_bundled_kernel()
    if not ok:
        sys.exit(1)

    changes = step_collect_changes()

    if args.use_ver:
        # 跳过 build + stabilize，直接以 ver/ 中最新 EXE 为发布版本
        print("\n" + "=" * 60)
        print("--use-ver 模式：跳过步骤 2/7 (构建) 和 2.5/7 (稳定化)")
        print("=" * 60)
    else:
        if not step_build():
            print("\n发布中止: 构建失败")
            sys.exit(1)
        step_stabilize()

    info = step_get_version(changes)
    if not info:
        print("\n发布中止: 获取版本信息失败")
        sys.exit(1)

    step_update_version_json(info)

    git_ok = step_git_push(info)
    if not git_ok:
        print("\n警告: Git推送失败，继续尝试创建Release...")
        print("（Release需要Git标签和代码已推送才能正确关联）")

    gh_ok = step_github_release(info)
    if not gh_ok:
        print("\n警告: GitHub Release创建失败")

    gitee_ok = step_gitee_release(info)
    if not gitee_ok:
        print("\n警告: Gitee Release创建失败")

    print("\n" + "=" * 60)
    print("发布流程完成!")
    print("=" * 60)
    print(f"版本: {info['version']}")
    print(f"GitHub Release: {'成功' if gh_ok else '失败'}")
    print(f"Gitee Release: {'成功' if gitee_ok else '失败'}")
    print(f"Git推送: {'成功' if git_ok else '失败/跳过'}")
    print(f"\n用户可通过软件更新页面检测并下载新版本")


if __name__ == "__main__":
    main()
