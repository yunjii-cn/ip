import os
import sys
import re
import json
import ssl
import urllib.request
import urllib.parse
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV_DIR = os.path.join(PROJECT_ROOT, "dev")
APP_DIR = os.path.join(DEV_DIR, "app")
VER_DIR = os.path.join(DEV_DIR, "ver")

GITHUB_REPO = "yunjii-cn/ip"
GITEE_REPO = "yunjii/ip"

EXISTING_RELEASES = [
    "2026.05.21.0228",
    "2026.05.20.2223",
    "2026.05.20.2057",
]

TARGET_VERSIONS = [
    "2026.05.11.0109",
    "2026.05.10.0148",
]


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
    headers["User-Agent"] = "YunjiBatchRelease/1.0"
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


def _load_version_history():
    vh_path = os.path.join(APP_DIR, "versions.json")
    if not os.path.isfile(vh_path):
        return {}
    try:
        with open(vh_path, "r", encoding="utf-8") as f:
            vh = json.load(f)
        return {v["version"]: v for v in vh if isinstance(v, dict)}
    except Exception:
        return {}


def _scan_local_exes():
    exes = {}
    if not os.path.isdir(VER_DIR):
        return exes
    for f in os.listdir(VER_DIR):
        if (f.startswith("云集代理-v") or f.startswith("云集智能网联代理专家-v")) and f.endswith(".exe"):
            m = re.search(r'v(\d+\.\d+\.\d+\.\d+)', f)
            if m:
                version = m.group(1)
                exes[version] = os.path.join(VER_DIR, f)
    return exes


def _check_existing_github_releases(github_token):
    existing = set()
    page = 1
    while True:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=100&page={page}"
        headers = {"Accept": "application/vnd.github+json"}
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        resp, status = _api_request(url, headers=headers)
        if status != 200 or not isinstance(resp, list) or not resp:
            break
        for rel in resp:
            tag = rel.get("tag_name", "")
            m = re.search(r'v(\d+\.\d+\.\d+\.\d+)', tag)
            if m:
                existing.add(m.group(1))
        if len(resp) < 100:
            break
        page += 1
    return existing


def _check_existing_gitee_releases(gitee_token):
    existing = set()
    url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/releases?access_token={gitee_token}&per_page=100"
    resp, status = _api_request(url)
    if status != 200 or not isinstance(resp, list):
        return existing
    for rel in resp:
        tag = rel.get("tag_name", "")
        m = re.search(r'v(\d+\.\d+\.\d+\.\d+)', tag)
        if m:
            existing.add(m.group(1))
    return existing


def _create_github_release(version, exe_path, changes, github_token):
    tag = f"v{version}"
    filename = os.path.basename(exe_path)
    github_filename = re.sub(r'[^\x00-\x7F]+', '', filename)
    if not github_filename:
        github_filename = f"YunjiIP-v{version}.exe"

    release_body = "## 更新内容\n\n"
    if changes:
        for i, c in enumerate(changes, 1):
            release_body += f"{i}. {c}\n"
    else:
        release_body += "历史版本补充分发\n"
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

    print(f"  创建 GitHub Release {tag}...")
    resp, status = _api_request(create_url, "POST", create_data, create_headers, timeout=30)

    if status == 422:
        print(f"  Release {tag} 已存在，跳过创建")
        list_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{tag}"
        resp, status = _api_request(list_url, headers=create_headers)
        if status != 200:
            print(f"  获取已有Release失败: {status}")
            return False
        release_id = resp.get("id")
        assets = resp.get("assets", [])
        exe_assets = [a for a in assets if a.get("name", "").endswith(".exe")]
        if exe_assets:
            print(f"  已有EXE附件，跳过上传")
            return True
    elif status != 201:
        print(f"  创建失败 (HTTP {status}): {json.dumps(resp, ensure_ascii=False)[:200]}")
        return False
    else:
        release_id = resp.get("id")
        print(f"  Release 已创建, ID: {release_id}")

    upload_url_base = f"https://uploads.github.com/repos/{GITHUB_REPO}/releases/{release_id}/assets"
    upload_headers = {
        "Accept": "application/vnd.github+json",
    }
    if github_token:
        upload_headers["Authorization"] = f"token {github_token}"

    print(f"  上传 EXE: {github_filename} ({os.path.getsize(exe_path) / 1024 / 1024:.1f} MB)...")
    upload_url = f"{upload_url_base}?name={urllib.parse.quote(github_filename)}"
    with open(exe_path, "rb") as f:
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
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  上传失败 (HTTP {e.code}): {err_body[:200]}")
        return False
    except Exception as e:
        print(f"  上传失败: {e}")
        return False


def _create_gitee_release(version, exe_path, changes, gitee_token):
    tag = f"v{version}"
    filename = os.path.basename(exe_path)

    release_body = "## 更新内容\n\n"
    if changes:
        for i, c in enumerate(changes, 1):
            release_body += f"{i}. {c}\n"
    else:
        release_body += "历史版本补充分发\n"

    create_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/releases"
    create_data = {
        "access_token": gitee_token,
        "tag_name": tag,
        "name": f"云集代理 {tag}",
        "body": release_body,
        "target_commitish": "main",
        "prerelease": False,
    }

    print(f"  创建 Gitee Release {tag}...")
    resp, status = _api_request(create_url, "POST", create_data, timeout=30)

    if status not in (200, 201):
        print(f"  创建失败 (HTTP {status}): {json.dumps(resp, ensure_ascii=False)[:200]}")
        return False

    release_id = resp.get("id")
    print(f"  Release 已创建, ID: {release_id}")

    print(f"  上传 EXE: {filename} ({os.path.getsize(exe_path) / 1024 / 1024:.1f} MB)...")
    upload_url = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/releases/{release_id}/attach_files"
    boundary = "----YunjiBatchBoundary7MA4YWxkTrZu0gW"
    with open(exe_path, "rb") as f:
        file_data = f.read()
    body_parts = []
    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(f'Content-Disposition: form-data; name="access_token"\r\n\r\n'.encode())
    body_parts.append(f"{gitee_token}\r\n".encode())
    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    body_parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
    body_parts.append(file_data)
    body_parts.append(f"\r\n--{boundary}--\r\n".encode())
    multipart_body = b"".join(body_parts)

    req = urllib.request.Request(
        upload_url, data=multipart_body, headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "YunjiBatchRelease/1.0",
        }, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=300, context=_ssl_ctx()) as resp_up:
            print(f"  上传成功 ({resp_up.status})")
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  上传失败 (HTTP {e.code}): {err_body[:200]}")
        return False
    except Exception as e:
        print(f"  上传失败: {e}")
        return False


def _update_version_json_has_release(released_versions):
    vj_path = os.path.join(PROJECT_ROOT, "ver", "version.json")
    if not os.path.isfile(vj_path):
        print(f"警告: {vj_path} 不存在")
        return

    with open(vj_path, "r", encoding="utf-8") as f:
        vj = json.load(f)

    updated = 0
    for v in vj.get("versions", []):
        ver = v.get("version", "")
        if ver in released_versions:
            if not v.get("has_release", False):
                v["has_release"] = True
                updated += 1

    with open(vj_path, "w", encoding="utf-8") as f:
        json.dump(vj, f, ensure_ascii=False, indent=4)

    print(f"已更新 version.json: {updated} 个版本标记 has_release=true")


def main():
    print("=" * 60)
    print("  云集代理 - 历史版本批量分发")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    github_token = _load_token(".github_token")
    gitee_token = _load_token(".gitee_token")

    if not gitee_token:
        print("\n错误: 未找到 .gitee_token，无法创建Gitee Release")
        print("请在 dev/app/.gitee_token 中配置Gitee个人访问令牌")
        sys.exit(1)

    if not github_token:
        print("\n警告: 未找到 .github_token，GitHub Release可能失败")

    vh = _load_version_history()
    local_exes = _scan_local_exes()

    print(f"\n本地EXE文件: {len(local_exes)} 个")
    for ver in sorted(local_exes.keys()):
        print(f"  v{ver}")

    print("\n检查已有 GitHub Release...")
    gh_releases = _check_existing_github_releases(github_token)
    print(f"  已有 {len(gh_releases)} 个 GitHub Release")

    print("检查已有 Gitee Release...")
    gitee_releases = _check_existing_gitee_releases(gitee_token)
    print(f"  已有 {len(gitee_releases)} 个 Gitee Release")

    need_gh = sorted([v for v in TARGET_VERSIONS if v in local_exes and v not in gh_releases])
    need_gitee = sorted([v for v in TARGET_VERSIONS if v in local_exes and v not in gitee_releases])

    print(f"\n需要补充 GitHub Release: {len(need_gh)} 个")
    for v in need_gh:
        print(f"  v{v}")

    print(f"\n需要补充 Gitee Release: {len(need_gitee)} 个")
    for v in need_gitee:
        print(f"  v{v}")

    if not need_gh and not need_gitee:
        print("\n所有版本已有Release，无需补充")
        return

    all_need = sorted(set(need_gh + need_gitee))
    total_size = sum(os.path.getsize(local_exes[v]) for v in all_need) / 1024 / 1024
    print(f"\n总计需上传: {len(all_need)} 个版本, 约 {total_size:.0f} MB")
    print(f"  GitHub: {len(need_gh)} 个 × ~35 MB (无空间限制)")
    print(f"  Gitee: {len(need_gitee)} 个 × ~35 MB (1GB空间限制)")

    gitee_total_mb = len(need_gitee) * 35 + len(gitee_releases) * 35
    if gitee_total_mb > 900:
        print(f"\n警告: Gitee预计总占用 ~{gitee_total_mb} MB，接近1GB限制")
        print("建议只上传最近的几个版本到Gitee")

    if "--auto" not in sys.argv:
        print("\n是否继续? (y/n): ", end="")
        try:
            confirm = input().strip().lower()
        except EOFError:
            confirm = "n"
        if confirm != "y":
            print("已取消")
            return

    released_versions = set()
    gh_ok_count = 0
    gh_fail_count = 0
    gitee_ok_count = 0
    gitee_fail_count = 0

    for i, version in enumerate(all_need, 1):
        exe_path = local_exes.get(version)
        if not exe_path or not os.path.isfile(exe_path):
            print(f"\n[{i}/{len(all_need)}] v{version}: EXE不存在，跳过")
            continue

        vh_entry = vh.get(version, {})
        changes = vh_entry.get("changes", [])

        print(f"\n[{i}/{len(all_need)}] v{version} ({os.path.getsize(exe_path) / 1024 / 1024:.1f} MB)")
        if changes:
            print(f"  更新内容: {len(changes)} 条")
        else:
            print(f"  更新内容: 无（历史版本补充分发）")

        if version in need_gh:
            if _create_github_release(version, exe_path, changes, github_token):
                gh_ok_count += 1
                released_versions.add(version)
            else:
                gh_fail_count += 1

        if version in need_gitee:
            if _create_gitee_release(version, exe_path, changes, gitee_token):
                gitee_ok_count += 1
                released_versions.add(version)
            else:
                gitee_fail_count += 1

    if released_versions:
        print("\n更新 version.json has_release 字段...")
        _update_version_json_has_release(released_versions)

    print("\n" + "=" * 60)
    print("批量分发完成!")
    print("=" * 60)
    print(f"GitHub: {gh_ok_count} 成功, {gh_fail_count} 失败")
    print(f"Gitee: {gitee_ok_count} 成功, {gitee_fail_count} 失败")
    print(f"version.json 已更新 {len(released_versions)} 个版本的 has_release 字段")


if __name__ == "__main__":
    main()
