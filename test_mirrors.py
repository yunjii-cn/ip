"""测试各种 GitHub 加速镜像"""
import urllib.request, ssl, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

MIRRORS = [
    "https://ghproxy.net/",
    "https://ghfast.top/",
    "https://gh-proxy.com/",
    "https://mirror.ghproxy.com/",
    "https://ghproxy.homeboyc.cn/",
]

# free-nodes/clashfree repo
PATH = "https://raw.githubusercontent.com/free-nodes/clashfree/main/clash20260622.yml"

print("=" * 60)
print("GitHub 加速镜像测试")
print("=" * 60)

for prefix in MIRRORS:
    url = prefix + PATH
    print(f"\n[{prefix}]")
    try:
        handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            handler)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        t0 = time.time()
        with opener.open(req, timeout=10) as resp:
            data = resp.read()
            print(f"  OK: {len(data)}B ({time.time()-t0:.1f}s)")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")

# Also test without mirror — with env/cached proxy
print(f"\n[direct no-mirror]")
try:
    req = urllib.request.Request(PATH, headers={"User-Agent": "Mozilla/5.0"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        data = resp.read()
        print(f"  OK: {len(data)}B ({time.time()-t0:.1f}s)")
except Exception as e:
    print(f"  FAIL: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("完成")