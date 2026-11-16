#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""loc_session.py —— 定位签到会话的只读观测 / 授权写入工具（雨课堂 /api/v3）

设计原则
- 默认只做读：state / watch / preview
- 写操作（start / end / extend）必须同时给 --yes，并在 --dry-run 下只打印不发送
- 请求头从 mitm 抓包里取"最新一条 /api/v3 且 authorization 长度==279"的原生会话，避免手工粘贴
- 所有输出走 --json 或表格，方便与上次实验 diff

用法
  # 1) 看当前会话状态（只读）
  python3 loc_session.py state --lesson 1820394971807984000

  # 2) 用坐标测围栏（只读）
  python3 loc_session.py preview --lat 29.5586 --lng 106.4630

  # 3) 观察 canSign/wouldBeLate/pastOfficialEnd 跳变（只读，默认 45s 一次共 26 次）
  python3 loc_session.py watch --interval 45 --count 26

  # 4) 开一个会话（写，必须 --yes）
  python3 loc_session.py start --lat 29.5586 --lng 106.4630 --radius 500 \
      --duration 600 --timeout-mode 1 --name 测试点 --yes

  # 5) 结束会话（写，必须 --yes）
  python3 loc_session.py end --yes

  # 6) 学生端提交（写，必须 --yes；需 role=2 的会话，教师会话会被 51210 拒绝）
  python3 loc_session.py submit --lesson 1820394971807984000 --lat 29.5586 --lng 106.4630 \
      --address 测试点 --source 54 --yes

环境变量
  YKT_BASE_URL   默认 https://www.yuketang.cn
  YKT_FLOWS      默认 /tmp/mitm/flows.mitm
  YKT_CA_INSECURE=1  跳过证书校验（走 mitm 代理时必须开）
"""
import argparse, json, os, ssl, sys, time, datetime, urllib.request

BASE = os.environ.get("YKT_BASE_URL", "https://www.yuketang.cn")
FLOWS = os.environ.get("YKT_FLOWS", "/tmp/mitm/flows.mitm")
CTX = ssl._create_unverified_context() if os.environ.get("YKT_CA_INSECURE", "1") == "1" else None

READ = [
    "/api/v3/lesson/location-checkin/session",
    "/api/v3/lesson/location-checkin/eligibility",
    "/api/v3/lesson/location-checkin/overview",
]
FIELDS = ["canSign", "reason", "wouldBeLate", "pastOfficialEnd", "isLate", "signed",
          "checkInTime", "serverTime", "message", "sessionActive", "inRange",
          "distanceMeters", "radiusMeters", "address"]


def native_headers():
    """从 mitm flows 里取最近一条原生 /api/v3 会话头（authorization 长度 279 = App 会话）。"""
    try:
        from mitmproxy import io as mio
    except Exception:
        sys.exit("需要 mitmproxy 才能自动取会话头；或设置 YKT_AUTH/YKT_COOKIE 手工提供")
    best = None
    with open(FLOWS, "rb") as f:
        try:
            for fl in mio.FlowReader(f).stream():
                r = getattr(fl, "request", None)
                if not r or not r.path.startswith("/api/v3"):
                    continue
                if len(r.headers.get("authorization") or "") == 279:
                    best = dict(r.headers)
        except Exception:
            pass
    if not best:
        sys.exit("flows 里没有 App 会话头；请先在模拟器里做一次 App 请求")
    best.pop("content-length", None)
    best.pop("host", None)
    return best


def with_lesson(path, lesson):
    """把 lesson_id 拼进查询串：课堂级接口（session/eligibility/overview/start/end）
    在不带 lesson_id 时按「当前授课」解析，常回 50004 LESSON_END。"""
    if not lesson:
        return path
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}lesson_id={lesson}"


def req(path, body=None, method=None, headers=None):
    h = headers or native_headers()
    data = json.dumps(body).encode() if body is not None else None
    m = method or ("POST" if data else "GET")
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=m)
    try:
        resp = urllib.request.urlopen(r, timeout=25, context=CTX)
        st, raw = resp.status, resp.read()
    except Exception as e:
        st = getattr(e, "code", None)
        raw = getattr(e, "read", lambda: b"")()
    try:
        j = json.loads(raw)
    except Exception:
        j = {"raw": raw[:300].decode("utf8", "replace")}
    return st, j


def show(tag, st, j):
    d = j.get("data")
    if isinstance(d, dict):
        sub = {k: d[k] for k in FIELDS if k in d}
        if "session" in d:
            sub["session"] = d["session"]
        print(f"[{tag}] http={st} code={j.get('code')} msg={j.get('msg')} {json.dumps(sub, ensure_ascii=False)}")
    else:
        print(f"[{tag}] http={st} code={j.get('code')} msg={j.get('msg')} data={json.dumps(d, ensure_ascii=False)}")


def cmd_state(a):
    for p in READ:
        show(p.rsplit("/", 1)[-1], *req(with_lesson(p, a.lesson)))
        time.sleep(args_gap(a))


def cmd_preview(a):
    st, j = req("/api/v3/lesson/location-checkin/preview", {"lat": a.lat, "lng": a.lng})
    show("preview", st, j)


def cmd_watch(a):
    log = a.log
    f = open(log, "a")
    n = 0
    while n < a.count:
        st, j = req(with_lesson("/api/v3/lesson/location-checkin/eligibility", a.lesson))
        d = j.get("data") or {}
        rec = {"t": datetime.datetime.now().strftime("%H:%M:%S"), "code": j.get("code")}
        for k in ("canSign", "reason", "wouldBeLate", "pastOfficialEnd", "isLate", "serverTime", "message"):
            if k in d:
                rec[k] = d[k]
        line = json.dumps(rec, ensure_ascii=False)
        f.write(line + "\n")
        f.flush()
        print(line)
        n += 1
        if n < a.count:
            time.sleep(a.interval)


def cmd_start(a):
    body = {"centerLat": a.lat, "centerLng": a.lng, "radiusM": a.radius,
            "durationSec": a.duration, "timeoutMode": a.timeout_mode,
            "locationName": a.name}
    if a.dry_run:
        print("[dry-run] POST /api/v3/lesson/location-checkin/start", json.dumps(body, ensure_ascii=False))
        return
    if not a.yes:
        sys.exit("写操作需要 --yes（会话一旦开启，服务端会向课堂内全部学生推送定位签到）")
    st, j = req("/api/v3/lesson/location-checkin/start", body)
    show("start", st, j)
    time.sleep(2)
    show("session", *req("/api/v3/lesson/location-checkin/session"))


def cmd_end(a):
    if a.dry_run:
        print("[dry-run] POST /api/v3/lesson/location-checkin/end {}")
        return
    if not a.yes:
        sys.exit("写操作需要 --yes")
    show("end", *req("/api/v3/lesson/location-checkin/end", {}))
    time.sleep(2)
    show("session", *req("/api/v3/lesson/location-checkin/session"))


def cmd_submit(a):
    body = {"lat": a.lat, "lng": a.lng, "address": a.address, "lessonId": a.lesson, "source": a.source}
    if a.dry_run:
        print("[dry-run] POST /api/v3/lesson/location-checkin/submit", json.dumps(body, ensure_ascii=False))
        return
    if not a.yes:
        sys.exit("写操作需要 --yes；且注意教师账号（role=1）提交会被 51210 拒绝")
    show("submit", *req("/api/v3/lesson/location-checkin/submit", body))


def args_gap(a):
    return getattr(a, "gap", 3)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("state"); s.add_argument("--lesson", default=""); s.set_defaults(f=cmd_state)
    s = sub.add_parser("preview"); s.add_argument("--lat", type=float, required=True); s.add_argument("--lng", type=float, required=True); s.set_defaults(f=cmd_preview)
    s = sub.add_parser("watch")
    s.add_argument("--interval", type=int, default=45); s.add_argument("--count", type=int, default=26)
    s.add_argument("--log", default="/tmp/elig_watch.jsonl"); s.set_defaults(f=cmd_watch)

    s = sub.add_parser("start")
    s.add_argument("--lat", type=float, required=True); s.add_argument("--lng", type=float, required=True)
    s.add_argument("--radius", type=int, default=500); s.add_argument("--duration", type=int, default=600)
    s.add_argument("--timeout-mode", type=int, default=1); s.add_argument("--name", default="测试点")
    s.add_argument("--dry-run", action="store_true"); s.add_argument("--yes", action="store_true")
    s.set_defaults(f=cmd_start)

    s = sub.add_parser("end"); s.add_argument("--dry-run", action="store_true"); s.add_argument("--yes", action="store_true"); s.set_defaults(f=cmd_end)

    s = sub.add_parser("submit")
    s.add_argument("--lesson", required=True); s.add_argument("--lat", type=float, required=True)
    s.add_argument("--lng", type=float, required=True); s.add_argument("--address", default="")
    s.add_argument("--source", type=int, default=54)
    s.add_argument("--dry-run", action="store_true"); s.add_argument("--yes", action="store_true")
    s.set_defaults(f=cmd_submit)

    for s_ in sub.choices.values():
        s_.add_argument("--gap", type=float, default=3)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
