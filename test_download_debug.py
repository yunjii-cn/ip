"""测试配置文件下载 - 诊断脚本"""
import urllib.request, ssl, socket, time, sys, os

sys.path.insert(0, r'e:\软件开发\云集智能网联代理专家\dev\app')

CONFIG_URLS = [
    ("线路1", "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/1/config.yaml",
     "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/1/config.yaml"),
    ("线路2", "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/2/config.yaml",
     "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/2/config.yaml"),
]

def test_download(name, url, timeout=10):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""

    # Level 0: check DNS
    print(f"\n  [{name}] 测试: {host}")
    try:
        ips = socket.getaddrinfo(host, 443, socket.AF_INET)
        print(f"    DNS 解析: {ips[0][4][0]}")
    except socket.gaierror as e:
        print(f"    DNS 解析: FAIL ({e})")

    # Level 1: 直连
    for label, handler in [
        ("直连", urllib.request.ProxyHandler({})),
        ("环境代理", None),
    ]:
        try:
            if handler is not None:
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ctx), handler)
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                t0 = time.time()
                with opener.open(req, timeout=timeout) as resp:
                    data = resp.read()
                    print(f"    {label}: OK {len(data)}B ({time.time()-t0:.1f}s)")
                    return data
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                t0 = time.time()
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    data = resp.read()
                    print(f"    {label}: OK {len(data)}B ({time.time()-t0:.1f}s)")
                    return data
        except Exception as e:
            print(f"    {label}: FAIL ({type(e).__name__}: {e})")
    return None

print("=" * 60)
print("线路配置下载诊断")
print("=" * 60)

for name, primary, fallback in CONFIG_URLS:
    for url in [primary, fallback]:
        result = test_download(name, url)
        if result:
            print(f"  => {name}: SUCCESS")
            break
    else:
        print(f"  => {name}: ALL FAILED")

print("\n" + "=" * 60)
print("诊断完成")