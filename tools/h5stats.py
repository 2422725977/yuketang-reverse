#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""h5stats.py -- 统计 artifacts/h5paths.txt 的分类计数与 REST 前缀分布。"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "artifacts", "h5paths.txt")


def main(path=SRC):
    sec = None
    counts = collections.Counter()
    buckets = collections.Counter()
    for ln in open(path, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if ln.startswith("## "):
            sec = ln[3:].strip()
            continue
        if not ln.strip() or ln.startswith("#"):
            continue
        parts = ln.split()
        tok = parts[-1]
        counts[sec] += 1
        if sec and ("REST" in sec or "其他" in sec) and tok.startswith("/"):
            seg = [s for s in tok.split("/") if s][:2]
            buckets["/" + "/".join(seg)] += 1
    print("分类计数:")
    for k, v in counts.most_common():
        print("  %-28s %d" % (k, v))
    print("REST/其他接口 前缀 Top20:")
    for k, v in buckets.most_common(20):
        print("  %-34s %d" % (k, v))


if __name__ == "__main__":
    main(*sys.argv[1:])
