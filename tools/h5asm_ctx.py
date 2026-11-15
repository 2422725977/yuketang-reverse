#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h5asm_ctx.py -- 在 blutter_out/asm 中定位字符串字面量, 给出所属 Dart 类/函数 + RVA。

用法:
    python3 tools/h5asm_ctx.py /v/index/bindSchool_list /webview ...
    python3 tools/h5asm_ctx.py --file artifacts/h5paths_lits.txt --out artifacts/h5asm_ctx.txt
优先按 "字面量" (带引号) 精确匹配, 未命中的字面量回退到裸串匹配。
输出按 (字面量, 文件, 行) 排序并去重: 每个 (文件, 字面量) 只保留首次出现行。
blutter 打印的 addr 即 libapp.so 的 RVA (.text vaddr == 文件偏移 0x760000)。
"""
import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASM = os.path.join(ROOT, "blutter_out", "asm")

ADDR_RE = re.compile(r"^\s*// \*\* addr: (0x[0-9a-fA-F]+), size: (0x[0-9a-fA-F]+)")
CLS_RE = re.compile(r"^(?:abstract |final |sealed |base |interface )*class\s+([^\s{]+)")
LIB_RE = re.compile(r"^// lib: (.*), url: (.*)$")


def context_map(lines):
    """返回 {行号: (rva, cls, func)}"""
    m = {}
    cls, fn, rva = "", "", "-"
    for i, line in enumerate(lines, 1):
        a = ADDR_RE.match(line)
        if a:
            rva = a.group(1)
            for j in range(i - 2, max(-1, i - 6), -1):
                s = lines[j].strip()
                if s and not s.startswith("//"):
                    fn = s
                    break
        c = CLS_RE.match(line)
        if c:
            cls = c.group(1)
        m[i] = (rva, cls, fn)
    return m


def variants(l):
    """blutter 会把 ? 打印成 \\? , * 打印成 \\* , 两形都试。"""
    vs = {l}
    if "?" in l:
        vs.add(l.replace("?", "\\?"))
    if "*" in l:
        vs.add(l.replace("*", "\\*"))
    return vs


def scan(files, lits, quoted=True):
    pairs = []
    for l in lits:
        for v in variants(l):
            pairs.append((('"' + v + '"') if quoted else v, l))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    vmap = dict(pairs)
    pat = re.compile("|".join(re.escape(p[0]) for p in pairs))
    hits = {}
    for f in files:
        try:
            txt = open(f, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if not pat.search(txt):
            continue
        lines = txt.split("\n")
        cm = None
        rel = os.path.relpath(f, ROOT)
        for i, line in enumerate(lines, 1):
            for mt in pat.finditer(line):
                raw = mt.group()
                if quoted:
                    raw = raw[1:-1]
                norm = raw.replace("\\?", "?").replace("\\*", "*")
                lit = vmap.get(raw) or vmap.get(norm) or norm
                k = (lit, rel)
                if k in hits:
                    continue
                if cm is None:
                    cm = context_map(lines)
                hits[k] = (i,) + cm[i]
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lits", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--out")
    a = ap.parse_args()
    lits = list(a.lits)
    if a.file:
        for ln in open(a.file, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                lits.append(ln)
    lits = sorted(set(lits))
    files = sorted(glob.glob(os.path.join(ASM, "**", "*.dart"), recursive=True))

    hits = scan(files, lits, quoted=True)
    found = set(k[0] for k in hits)
    missing = [l for l in lits if l not in found]
    if missing:
        hits.update(scan(files, missing, quoted=False))
    found |= set(k[0] for k in hits)
    missing = [l for l in lits if l not in found]

    rows = sorted(hits.items(), key=lambda kv: (kv[0][0], kv[1][1], kv[0][1]))
    out = ["# h5asm_ctx.py -- 字面量 -> Dart 类/函数 + RVA 交叉取证 (每 (文件,字面量) 一条)",
           "# asm 文件数=%d ; 查询字面量=%d ; 命中行=%d" % (len(files), len(lits), len(rows)),
           "# 双通道均未命中的字面量: %s" % (", ".join(missing) if missing else "无"),
           ""]
    for (lit, rel), (i, rva, cls, fn) in rows:
        out.append("%s | %s:%d | rva=%s | %s::%s" % (lit, rel, i, rva, cls or "-", fn or "-"))
    txt = "\n".join(out) + "\n"
    if a.out:
        open(a.out, "w").write(txt)
        print("wrote %s rows=%d missing=%d" % (os.path.relpath(a.out, ROOT), len(rows), len(missing)))
    else:
        sys.stdout.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
