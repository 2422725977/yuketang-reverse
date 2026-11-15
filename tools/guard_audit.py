#!/usr/bin/env python3
# guard_audit.py —— 审计 hooks/ykt_*.js 里所有挂点的 Dart AOT prologue guard
# 用法: python3 tools/guard_audit.py [--so applibs/libapp.so] [--hooks hooks]
# 输出: 每个挂点 (文件, name, rva, guard声明, 实测字节, 结论)；末尾统计与不一致清单。
import argparse, glob, os, re, sys

def parse_hooks(hooks_dir):
    pat = re.compile(r"name\s*:\s*[\"']([^\"']+)[\"'][^}]*?rva\s*:\s*(0x[0-9a-fA-F]+)[^}]*?guard\s*:\s*\[([^\]]*)\]", re.S)
    out = []
    for fp in sorted(glob.glob(os.path.join(hooks_dir, "ykt_*.js"))):
        txt = open(fp, encoding="utf-8", errors="replace").read()
        for m in pat.finditer(txt):
            name, rva, g = m.group(1), int(m.group(2), 16), m.group(3)
            gs = re.findall(r"[\"']([0-9a-fA-F]{8,})[\"']", g)
            out.append((os.path.basename(fp), name, rva, gs))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", default="applibs/libapp.so")
    ap.add_argument("--hooks", default="hooks")
    a = ap.parse_args()
    data = open(a.so, "rb").read()
    pts = parse_hooks(a.hooks)
    ok = bad = 0
    rows = []
    for fn, name, rva, gs in pts:
        if rva + 16 > len(data):
            rows.append((fn, name, rva, gs, ["OOR"], "rva 越界"))
            bad += 1
            continue
        # guard 与 libapp.so 文件字节同序（小端存放的原始字节），审计同序比较
        got = [data[rva + i * 4: rva + i * 4 + 4].hex() for i in (0, 2)]
        want = gs[:2]
        same = (got == want)
        ok += same; bad += (not same)
        rows.append((fn, name, rva, want, got, "OK" if same else "MISMATCH"))
    w = max(len(r[1]) for r in rows)
    print("挂点 guard 审计（libapp.so 文件字节序，地址=文件偏移=RVA for .text）")
    print(f"{'文件':<26} {'name':<{w}} {'rva':>10}  {'声明':<20} {'实测':<20} 结论")
    for fn, name, rva, want, got, verdict in rows:
        print(f"{fn:<26} {name:<{w}} 0x{rva:08x}  {','.join(want):<20} {','.join(got):<20} {verdict}")
    print(f"\n合计 {len(rows)} 点：OK {ok} / 不一致 {bad}")
    if bad:
        print("不一致清单：")
        for fn, name, rva, want, got, verdict in rows:
            if verdict != "OK":
                print(f"  - {fn} :: {name} @0x{rva:x} 声明={','.join(want)} 实测={','.join(got)}")
    return 0 if bad == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
