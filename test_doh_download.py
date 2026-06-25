"""测试 DoH+IP 方式下载 GitHub raw 配置"""
import urllib.request, ssl, socket, time, json, http.client

_DOH_SERVERS = [
    "https://dns.alidns.com/resolve",
    "https://doh.pub/dns-query",
]

def _resolve_via_doh(host):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for doh_url in _DOH_SERVERS:
        try:
            query_url = f"{doh_url}?name={host}&type=A"
            req = urllib.request.Request(query_url, headers={
                "Accept": "application/dns-json",
                "User-Agent": "Mozilla/5.0",
            })
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                result = json.loads(resp.read())
                answers = result.get("Answer", [])
                ips = [a["data"] for a in answers if a.get("type") == 1]
                if ips:
                    print(f"  DoH OK: {host} -> {ips}")
                    return ips
        except Exception as e:
            print(f"  DoH fail ({doh_url}): {type(e).__name__}: {e}")
    return []

def _try_doh_ip_download(url, host, ips, timeout=10):
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
            data = resp.read()
            conn.close()
            print(f"  DoH+IP: {host} via {ip} OK {len(data)}B ({resp.status})")
            return data
        except Exception as e:
            print(f"  DoH+IP {ip} fail: {type(e).__name__}: {e}")
    return None

urls = [
    ("free-nodes/clashfree", "https://raw.githubusercontent.com/free-nodes/clashfree/main/clash20260622.yml"),
    ("mfuu/v2ray", "https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml"),
    ("ripaojiedian/freenode", "https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash"),
]

print("=" * 60)
print("DoH+IP 下载诊断")
print("=" * 60)

for name, url in urls:
    print(f"\n[{name}] {url}")
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname

    # 直连 DNS
    try:
        ips = socket.getaddrinfo(host, 443, socket.AF_INET)
        print(f"  直连 DNS: {ips[0][4][0]}")
        direct_ok = True
    except:
        print(f"  直连 DNS: FAIL")
        direct_ok = False

    # 直连下载
    if direct_ok:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx),
                urllib.request.ProxyHandler({}))
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            t0 = time.time()
            with opener.open(req, timeout=8) as resp:
                data = resp.read()
                print(f"  直连: OK {len(data)}B ({time.time()-t0:.1f}s)")
        except Exception as e:
            print(f"  直连: FAIL ({type(e).__name__}: {e})")
            direct_ok = False

    # DoH+IP 回退
    if not direct_ok:
        ips = _resolve_via_doh(host)
        if ips:
            data = _try_doh_ip_download(url, host, ips)
            if data:
                print(f"  => SUCCESS via DoH+IP")

print("\n" + "=" * 60)
print("诊断完成")