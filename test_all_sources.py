"""测试所有可能的配置来源"""
import os, urllib.request, ssl, socket, time

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

SOURCES = [
    ("gitlab.com (free9999/1)", "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/1/config.yaml"),
    ("gitlab.com (free9999/2)", "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/2/config.yaml"),
    ("libg.org mirror(1)", "https://raw.libg.org/free-nodes/clashfree/main/clash20260622.yml"),
    ("fastgit.org mirror(1)", "https://raw.fastgit.org/free-nodes/clashfree/main/clash20260622.yml"),
    ("github.com raw(1)", "https://raw.githubusercontent.com/free-nodes/clashfree/main/clash20260622.yml"),
    ("github.com raw(2)", "https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml"),
]

def try_download(url, timeout=8):
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx), handler)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    t0 = time.time()
    with opener.open(req, timeout=timeout) as resp:
        data = resp.read()
        return len(data), time.time() - t0

print("=" * 60)
print("配置来源可达性测试 (清除代理环境变量)")
print("=" * 60)

for name, url in SOURCES:
    print(f"\n[{name}]")
    try:
        size, elapsed = try_download(url)
        print(f"  OK: {size}B ({elapsed:.1f}s)")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("完成")