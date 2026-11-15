#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h5paths.py -- 从 libapp.so 提取"路径型字面量"(ASCII + UTF-16LE 双解码), 去重排序并分类。

用法:
    python3 tools/h5paths.py                # 默认: so/lib/arm64-v8a/libapp.so -> artifacts/h5paths.txt
    python3 tools/h5paths.py --so X.so --out Y.txt
    python3 tools/h5paths.py --stdout       # 只打印统计

样本只读; 输出确定性(按分类 + 字面量排序), 可复跑。
"""
import argparse
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SO = os.path.join(ROOT, "so", "lib", "arm64-v8a", "libapp.so")
DEFAULT_OUT = os.path.join(ROOT, "artifacts", "h5paths.txt")

ASCII_RUN = re.compile(rb"[\x20-\x7e]{4,}")
U16_RUN = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")
DELIM = re.compile(r"[\s\"\'\`<>()\[\]{},;|\\^]+")

PATH_RE = re.compile(r"^/{1,2}[A-Za-z0-9_\-./~%?=&#+@:!$*]*$")
URL_RE = re.compile(r"^https?://[A-Za-z0-9\-._~%:/?#@!$&*+,;=\[\]]+$")
HOST_RE = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+(?:com\.cn|com|cn|net|org|io|dev|top|xyz|tv|cc)(?::\d+)?$")

BIND_KW = ("bindmobile", "bind_mobile", "bindschool", "bind_school", "school_name", "bind-school", "bindschool_list")
H5_KW = ("/v/index/", "/h5/", "/webview/")
STATIC_EXT = (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
              ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".m3u8", ".json", ".xml", ".map")
API_MARK = ("/api/", "/mooc-api/", "/api-", "/graphql", "/v3/", "/v1/", "/v2/",
            "/mobile-app/api", "/c27/api", "/nodeapi", "/wxapi", "/video-log", "/wsapp")
PC_MARK = ("/pc/", "/web/", "/c/", "/desktop/")
LEGACY_PREFIX = ("/v/", "/group/", "/quiz/", "/topic/", "/comment/", "/reply/", "/c27/",
                 "/remotor/", "/online_proctor/", "/mobile-app/", "/ai-workspace/",
                 "/authorize/", "/login/", "/exposure/", "/hits/", "/likes", "/liked/",
                 "/progress/", "/idphoto/", "/exam_room/", "/course_meta/", "/top/")
NOISE_PREFIX = ("/1998/", "/1999/", "/2000/", "/XML/", "/data/dtd", "/dart-lang/",
                "/release/", "/2.0x/", "/3.0x/", "/9/r", "/.cookies/", "/rain", "/objects/",
                "/buckets/", "/interlace/")
NOISE_KW = ("/flutter/", "w3.org", "ibm.com")


def iter_tokens(data):
    """产出 (token, file_offset, encoding) ; 双解码: ASCII 与 UTF-16LE。"""
    for m in ASCII_RUN.finditer(data):
        run = m.group().decode("latin-1")
        base = m.start()
        pos = 0
        for dm in re.finditer(DELIM, run):
            tok = run[pos:dm.start()]
            if tok:
                yield tok, base + pos, "ascii"
            pos = dm.end()
        tok = run[pos:]
        if tok:
            yield tok, base + pos, "ascii"
    for m in U16_RUN.finditer(data):
        run = m.group().decode("utf-16-le")
        base = m.start()
        pos = 0
        for dm in re.finditer(DELIM, run):
            tok = run[pos:dm.start()]
            if tok:
                yield tok, base + 2 * pos, "u16"
            pos = dm.end()
        tok = run[pos:]
        if tok:
            yield tok, base + 2 * pos, "u16"


def classify_path(t):
    low = t.lower()
    if low.startswith(NOISE_PREFIX) or any(k in low for k in NOISE_KW):
        return "非应用噪音(库/命名空间)"
    if any(k in low for k in BIND_KW):
        return "bindmobile/身份绑定"
    if low.endswith((".html", ".htm")) or any(k in low for k in H5_KW):
        return "云侧H5页面"
    if ("/static/" in low or low.startswith("/qn-") or "/assets/" in low
            or low.endswith(STATIC_EXT) or "/oss/" in low or "/img/" in low
            or "/font" in low or "/upload" in low):
        return "静态资源"
    if any(k in low for k in API_MARK) or low.startswith("/api"):
        return "REST端点"
    if any(k in low for k in PC_MARK) or low.startswith("/pc"):
        return "PC端"
    if low.startswith(LEGACY_PREFIX):
        return "其他接口(/v、/group、/c27 等旧前缀)"
    return "非应用噪音(库/命名空间)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", default=DEFAULT_SO)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()

    data = open(a.so, "rb").read()
    paths = Counter()      # token -> count
    poff = {}              # token -> (first_offset, encoding)
    urls = Counter()
    uoff = {}
    urlsrc = {}            # url -> encoding
    hosts = Counter()

    n_tok = 0
    for tok, off, enc in iter_tokens(data):
        n_tok += 1
        tok = tok.rstrip(".,;")
        if len(tok) < 4:
            continue
        if URL_RE.match(tok):
            urls[tok] += 1
            uoff.setdefault(tok, (off, enc))
            u = tok.split("://", 1)[1]
            p = u.find("/")
            host = u if p < 0 else u[:p]
            hosts[host] += 1
            if p >= 0:
                sub = u[p:]
                if PATH_RE.match(sub) and any(c.isalpha() for c in sub):
                    paths[sub] += 1
                    poff.setdefault(sub, (off, enc + "/url"))
            continue
        if HOST_RE.match(tok):
            hosts[tok] += 1
            continue
        if tok.startswith("//"):
            seg = tok[2:].split("/")
            if len(seg) > 1 and "." in seg[0]:
                hosts[seg[0]] += 1
                sub = "/" + "/".join(seg[1:])
                if PATH_RE.match(sub) and any(c.isalpha() for c in sub):
                    paths[sub] += 1
                    poff.setdefault(sub, (off, enc + "/url"))
                continue
        if PATH_RE.match(tok) and any(c.isalpha() for c in tok):
            if tok.count("/") >= 2 or tok.lower().endswith(STATIC_EXT) or tok.startswith("/v/"):
                paths[tok] += 1
                poff.setdefault(tok, (off, enc))

    groups = {}
    for t, c in paths.items():
        groups.setdefault(classify_path(t), []).append(t)
    for g in groups:
        groups[g].sort()

    L = []
    L.append("# h5paths.txt -- 雨课堂 libapp.so 路径型字面量全表 (ASCII + UTF-16LE 双解码)")
    L.append("# 生成器: tools/h5paths.py  样本: %s (%d bytes)" % (os.path.relpath(a.so, ROOT), len(data)))
    L.append("# token 扫描总数=%d ; 唯一路径型字面量=%d ; 唯一URL=%d ; 唯一host=%d" % (n_tok, len(paths), len(urls), len(hosts)))
    L.append("# 偏移 = 该字面量在文件内首次出现的字节偏移 (ascii=字节, u16=字节, /url 表示来自完整URL)")
    L.append("")
    order = ["REST端点", "云侧H5页面", "静态资源", "PC端", "bindmobile/身份绑定",
             "其他接口(/v、/group、/c27 等旧前缀)", "非应用噪音(库/命名空间)"]
    for g in order:
        items = groups.get(g, [])
        L.append("## [%s] 共 %d 条" % (g, len(items)))
        for t in items:
            off, enc = poff[t]
            L.append("0x%08x  x%-4d %-8s %s" % (off, paths[t], enc, t))
        L.append("")
    L.append("## [域名/主机] 共 %d 条" % len(hosts))
    for h, c in sorted(hosts.items()):
        L.append("x%-4d %s" % (c, h))
    L.append("")
    L.append("## [完整 URL] 共 %d 条" % len(urls))
    for u, c in sorted(urls.items()):
        off, enc = uoff[u]
        L.append("0x%08x  x%-4d %-8s %s" % (off, c, enc, u))
    L.append("")
    txt = "\n".join(L) + "\n"

    if a.stdout:
        sys.stdout.write("\n".join(L[:6]) + "\n")
    else:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        open(a.out, "w").write(txt)
        sys.stdout.write("wrote %s lines=%d tokens=%d unique_paths=%d urls=%d hosts=%d\n"
                         % (os.path.relpath(a.out, ROOT), len(L), n_tok, len(paths), len(urls), len(hosts)))
        for g in order:
            sys.stdout.write("  %-16s %d\n" % (g, len(groups.get(g, []))))


if __name__ == "__main__":
    main()
