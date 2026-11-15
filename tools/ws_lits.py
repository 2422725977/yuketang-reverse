
import re, sys, json, collections
p = "blutter_out/asm/rain/websocket/ws_connector.dart"
src = open(p, encoding="utf-8").read().split("\n")
# function blocks
funcs = []
cur = None
for i, ln in enumerate(src):
    m = re.match(r"^  \S.*\(/\* No info \*/\)", ln)
    a = re.search(r"// \*\* addr: (0x[0-9a-f]+), size: (0x[0-9a-f]+)", ln)
    if m and not a:
        cur = {"name": ln.strip().rstrip(" {"), "line": i+1, "lit": []}
        funcs.append(cur)
        continue
    if cur is not None:
        a2 = re.search(r'\[pp\+0x[0-9a-f]+\] "([^"]*)"', ln)
        if a2:
            cur["lit"].append(a2.group(1))
        a3 = re.search(r"// \*\* addr: (0x[0-9a-f]+), size: (0x[0-9a-f]+)", ln)
        if a3 and "addr" not in cur:
            cur["addr"] = a3.group(1); cur["size"] = a3.group(2)
        if ln.startswith("  }"):
            cur = None
for f in funcs:
    print(f"{f['name']:<40} {f.get('addr','?')} {f.get('size','')} lits={f['lit']}")
