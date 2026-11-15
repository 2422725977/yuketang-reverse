#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h5callers.py -- 反向调用点定位: 给定目标 RVA, 在 blutter_out/asm 中找出所有 "bl #0xRVA" 调用点,
输出 (文件:行 | 调用者类::函数 | 调用者 RVA)。用于回答"H5 页面由哪个 Dart 函数打开"。

用法:
    python3 tools/h5callers.py 0xbd121c 0xe2b8f4 0xe953cc
    python3 tools/h5callers.py --out artifacts/h5callers.txt 0xbd121c
blutter 打印的 addr 即 libapp.so RVA (.text vaddr == 文件偏移 0x760000)。
"""
import argparse
import glob
import os
import re
import sys
from h5asm_ctx import ASM, ROOT, context_map

CALL_RE = re.compile(r"bl\s+#(0x[0-9a-fA-F]+)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rvas", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--lits", action="store_true",
                    help="额外打印每个调用点上方最近的字面量行 (推参数)")
    a = ap.parse_args()
    targets = set(x.lower() for x in a.rvas)
    files = sorted(glob.glob(os.path.join(ASM, "**", "*.dart"), recursive=True))
    rows = []
    for f in files:
        try:
            txt = open(f, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if not any(t in txt for t in targets):
            continue
        lines = txt.split("\n")
        cm = None
        rel = os.path.relpath(f, ROOT)
        for i, line in enumerate(lines, 1):
            for mt in CALL_RE.finditer(line):
                t = mt.group(1).lower()
                if t not in targets:
                    continue
                if cm is None:
                    cm = context_map(lines)
                rva, cls, fn = cm[i]
                lit = ""
                if a.lits:
                    for j in range(i - 2, max(-1, i - 40), -1):
                        s = lines[j]
                        if "\"" in s:
                            lit = s.strip()
                            break
                rows.append((t, rel, i, rva, cls or "-", fn or "-", lit))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    out = ["# h5callers.py -- 目标 RVA 的调用点 (文件:行 | 调用者 RVA | 调用者)",
           "# 目标 RVA: %s ; 调用点总数: %d ; asm 文件数: %d" % (", ".join(sorted(targets)), len(rows), len(files)),
           ""]
    for r in rows:
        t, rel, i, rva, cls, fn = r[:6]
        line = "%s <- %s:%d | caller_rva=%s | %s::%s" % (t, rel, i, rva, cls, fn)
        if a.lits:
            line += " | arg_lit: %s" % (r[6] if len(r) > 6 else "")
        out.append(line)
    txt = "\n".join(out) + "\n"
    if a.out:
        open(a.out, "w").write(txt)
        print("wrote %s rows=%d" % (os.path.relpath(a.out, ROOT), len(rows)))
    else:
        sys.stdout.write(txt)


if __name__ == "__main__":
    main()
