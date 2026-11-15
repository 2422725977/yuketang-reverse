#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出 AndroidManifest 的 exported 组件表 + scheme 表。"""
import re, sys
p = "/Users/xi/Documents/deepseek-harness/ctf/ykt/jadx/resources/AndroidManifest.xml"
t = open(p, encoding="utf-8", errors="replace").read()

TAG = re.compile(r"<(activity|activity-alias|service|receiver|provider)\b(.*?)</\1>|<(activity|activity-alias|service|receiver|provider)\b([^>]*?)/>", re.S)
NAME = re.compile(r'android:name="([^"]+)"')
EXP = re.compile(r'android:exported="([^"]+)"')
DATA = re.compile(r"<data\b[^>]*>")
rows = []
for m in TAG.finditer(t):
    attrs = m.group(2) or m.group(4) or ""
    kind = m.group(1) or m.group(3)
    nm = NAME.search(attrs)
    ex = EXP.search(attrs)
    body = t[m.start():m.end()]
    datas = []
    for d in DATA.finditer(body):
        s = d.group(0)
        sch = re.search(r'android:scheme="([^"]+)"', s)
        host = re.search(r'android:host="([^"]+)"', s)
        path = re.search(r'android:path(?:Prefix|Pattern)?="([^"]+)"', s)
        datas.append("://".join(x for x in [sch.group(1) if sch else None,
                                            host.group(1) if host else None] if x) + (path.group(1) if path else ""))
    if (ex and ex.group(1) == "true") or datas:
        rows.append((kind, nm.group(1) if nm else "?", ex.group(1) if ex else "-", ",".join(sorted(set(datas)))[:110]))

print("EXPORTED / SCHEME-BEARING COMPONENTS: %d" % len(rows))
for k, n, e, d in rows:
    print("%-14s exp=%-5s %-62s %s" % (k, e, n[:62], d))
