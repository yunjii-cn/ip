import json
with open(r"e:\软件开发\云集智能网联代理专家\dev\app\versions.json", "r", encoding="utf-8") as f:
    data = json.load(f)
for d in data[:10]:
    ver = d.get("version", "?")
    ch = d.get("changes", [])
    print(f"{ver}: {len(ch)} changes")
    for c in ch:
        print(f"  - {c}")