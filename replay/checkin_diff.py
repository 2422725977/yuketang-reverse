#!/usr/bin/env python3
"""checkin_diff.py — 两次签到实验的关键字段对照（E0 对照 vs E1/E3/E4）

用法:
    ./checkin_diff.py runs/E0-20261115-200000 runs/E3-20261115-201000
它会读取每个目录里的 *.res.json，抽出判定字段并排成表。
"""
import json
import os
import sys

# 判定字段：普通签到响应 / 定位签到资格 / 定位签到提交 / 老师端总览
KEYS = ["success", "error_code", "status_code", "msg", "message",
        "isLate", "wouldBeLate", "pastOfficialEnd", "canSign", "signed",
        "reason", "checkInTime", "serverTime", "startMs", "endMs",
        "lateAfterMs", "timeoutMode", "session", "address", "lat", "lng",
        "time", "signedCount", "totalStudentCount", "lessonToken", "identityId", "role"]


def flatten(obj, out, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in KEYS:
                out[prefix + k] = v
            if isinstance(v, (dict, list)):
                flatten(v, out, prefix + k + ".")
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):          # 名单类只取前 3 条
            flatten(v, out, prefix + "[%d]." % i)


def load_run(d):
    merged = {}
    for f in sorted(os.listdir(d)):
        if not f.endswith(".res.json"):
            continue
        try:
            body = json.load(open(os.path.join(d, f), encoding="utf-8"))
        except Exception as e:
            merged[f] = "<unparsable: %s>" % e
            continue
        part = {}
        flatten(body, part)
        for k, v in part.items():
            merged["%s :: %s" % (f[:-9], k)] = v
    return merged


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    a, b = sys.argv[1], sys.argv[2]
    ra, rb = load_run(a), load_run(b)
    keys = sorted(set(ra) | set(rb))
    w = max(len(k) for k in keys) if keys else 10
    print("%-*s | %-28s | %-28s |" % (w, "field", os.path.basename(a), os.path.basename(b)))
    print("-" * (w + 66))
    diffs = 0
    for k in keys:
        va, vb = ra.get(k, "-"), rb.get(k, "-")
        mark = "  <<< 不同" if va != vb else ""
        if va != vb:
            diffs += 1
        print("%-*s | %-28s | %-28s |%s" % (w, k, str(va)[:28], str(vb)[:28], mark))
    print("\n差异字段数：%d" % diffs)
    print("读法：isLate/checkInTime/time 出现差异 → 服务端按自己时钟记了迟到/补签；"
          "canSign=false + reason → 该时间点服务端已拒绝；两者都不变 → 该变量不影响服务端记录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
