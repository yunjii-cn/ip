"""测试国内可达的配置来源"""
import os, urllib.request, ssl, time

for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(k, None)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

SOURCES = [
    ("cdn.jsdelivr.net (gh)", "https://cdn.jsdelivr.net/gh/free-nodes/clashfree@main/clash20260622.yml"),
    ("cdn.jsdelivr.net (mfuu)", "https://cdn.jsdelivr.net/gh/mfuu/v2ray@master/clash.yaml"),
    ("fastly.jsdelivr.net (gh)", "https://fastly.jsdelivr.net/gh/free-nodes/clashfree@main/clash20260622.yml"),
    ("gcore.jsdelivr.net (gh)", "https://gcore.jsdelivr.net/gh/free-nodes/clashfree@main/clash20260622.yml"),
    ("testingcf.jsdelivr.net", "https://testingcf.jsdelivr.net/gh/free-nodes/clashfree@main/clash20260622.yml"),
    ("gitee.com (raw)", "https://gitee.com/yunjii/ip/raw/main/release/version.json"),
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
print("国内源可达性测试")
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