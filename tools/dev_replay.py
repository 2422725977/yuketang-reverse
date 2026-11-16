#!/usr/bin/env python3
"""dev_replay.py - 在模拟器内部用静态 curl 复现雨课堂 App 的已鉴权请求（受控实验用）。

两个必须遵守的事实（都是实测得出的）：
1. 网关对 /api/v3/** 要求同名明文头 "sessionid: <值>"（与 Cookie 里的 sessionid 同值）。
   缺它一律 {"code":50000,"msg":"UNAUTHENTICATED"}，宿主 curl 补齐多少头都不行。
2. 服务端会在响应里轮换 sessionid，App 的 Cookie 在内存里，落盘的
   /data/data/com.xuetangx.ykt/app_flutter/.cookies/ie1_ps1/www.yuketang.cn 常常是旧值。
   所以要从 mitm 抓包 flows 里取**最近一条 App 自带请求**的头来做模板。

用法：
  python3 tools/dev_replay.py --path /api/v3/lesson/location-checkin/eligibility
  python3 tools/dev_replay.py --path /api/v3/lesson/checkin --method POST \
      --body '{"lessonId":"1820276486008339584","source":42,"joinIfNotIn":true}'
  python3 tools/dev_replay.py --path /v/course_meta/learning_list/ --template-dump

前提：设备已 root、/data/local/tmp/curl 存在、mitmproxy reverse:8888 在跑、
      iptables DNAT 输出到 10.0.2.2:8888（见 README 抓包装置一节）。
"""
import argparse, json, os, subprocess, sys, time

ADB = ["/opt/homebrew/bin/adb", "-s", os.environ.get("SERIAL", "emulator-5556")]
BASE = "https://www.yuketang.cn"
FLOWS = os.environ.get("FLOWS", "/tmp/mitm/flows.mitm")
DROP = {"accept-encoding", "host", "content-length", "connection"}


def adb(*args, **kw):
    return subprocess.run(ADB + list(args), capture_output=True, text=True, **kw)


def latest_headers(prefix="/api/v3", flows=FLOWS):
    """从 mitm dump 里取最近一条匹配 prefix 的请求的完整头。"""
    from mitmproxy import io
    try:
        from mitmproxy.exceptions import FlowReadException
    except Exception:
        FlowReadException = Exception
    hdrs, url = None, None
    try:
        with open(flows, "rb") as f:
            rd = io.FlowReader(f)
            for fl in rd.stream():
                req = getattr(fl, "request", None)
                if not req:
                    continue
                if req.path.startswith(prefix):
                    hdrs = dict(req.headers)
                    url = req.pretty_url
    except FlowReadException:
        pass
    if not hdrs:
        raise SystemExit("no flow matching %s in %s" % (prefix, flows))
    return hdrs, url


def to_curl_config(url, method, hdrs, body=None, timeout=25):
    cfg = [
        'url = "%s"' % url,
        "insecure",
        "max-time %d" % timeout,
        "silent",
        "show-error",
        'output = "/data/local/tmp/replay.out"',
        'write-out = "%{http_code}"',
        'request = "%s"' % method,
        'connect-to = "www.yuketang.cn:443:10.0.2.2:8888"',
    ]
    hdrs = dict(hdrs)
    if body is not None:
        hdrs = {k: v for k, v in hdrs.items() if k.lower() != "content-type"}
        hdrs["content-type"] = "application/json; charset=UTF-8"
    for k, v in hdrs.items():
        if k.lower() in DROP:
            continue
        cfg.append('header = "%s: %s"' % (k, v.replace(chr(34), chr(92) + chr(34))))
    if body is not None:
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        cfg.append('data = "' + raw.replace(chr(34), chr(92) + chr(34)) + '"')
    return "\n".join(cfg) + "\n"


def run(path, method="GET", body=None, timeout=25, wait=0, flows=FLOWS, prefix="/api/v3", host=False):
    """host=False: 在模拟器内部发（推荐，环境最接近 App）；host=True: 宿主直连。

    实测结论：只要把头带全（尤其明文 sessionid 头），宿主直连同样 200 + code:0，
    说明网关没有绑定 IP/设备指纹；401/50000 的唯一原因就是缺那个头。
    """
    hdrs, tmpl_url = latest_headers(prefix, flows)
    if wait:
        time.sleep(wait)
    url = BASE + path
    cfg = to_curl_config(url, method, hdrs, body, timeout)
    if host:
        args = ["curl", "-s", "-o", "/tmp/replay.out", "-w", "%{http_code}", "--max-time", str(timeout),
                "-X", method]
        h = dict(hdrs)
        if body is not None:
            h = {k: v for k, v in h.items() if k.lower() != "content-type"}
            h["content-type"] = "application/json; charset=UTF-8"
        for k, v in h.items():
            if k.lower() in DROP:
                continue
            args += ["-H", "%s: %s" % (k, v)]
        if body is not None:
            args += ["--data-raw", json.dumps(body, ensure_ascii=False, separators=(",", ":"))]
        args.append(url)
        r = subprocess.run(args, capture_output=True, text=True)
        code = (r.stdout or "").strip() or "???"
        out = open("/tmp/replay.out", "r", errors="replace").read()
    else:
        local = "/tmp/dev_replay.cfg"
        open(local, "w").write(cfg)
        adb("push", local, "/data/local/tmp/dev_replay.cfg")
        r = adb("shell", "/data/local/tmp/curl -K /data/local/tmp/dev_replay.cfg")
        code = r.stdout.strip() or "???"
        out = adb("shell", "cat /data/local/tmp/replay.out").stdout
    shown = dict(hdrs)
    for k in list(shown):
        if k.lower() in ("cookie", "x-csrftoken", "sessionid", "sid"):
            shown[k] = "<REDACTED>"
    return {"url": url, "method": method, "body": body, "status": code,
            "template": tmpl_url, "headers_sent": shown, "resp": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--method", default="GET")
    ap.add_argument("--body")
    ap.add_argument("--wait", type=int, default=0)
    ap.add_argument("--flows", default=FLOWS)
    ap.add_argument("--prefix", default="/api/v3")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--host", action="store_true", help="从宿主直连（需带全头，含明文 sessionid）")
    ap.add_argument("--out", default="live/replay")
    a = ap.parse_args()
    body = json.loads(a.body) if a.body else None
    if a.dry_run:
        hdrs, tmpl = latest_headers(a.prefix, a.flows)
        shown = dict(hdrs)
        for k in list(shown):
            if k.lower() in ("cookie", "x-csrftoken", "sessionid", "sid"):
                shown[k] = "<REDACTED>"
        print(json.dumps({"template": tmpl, "headers": shown, "target": BASE + a.path,
                          "method": a.method, "body": body}, indent=2, ensure_ascii=False))
        return
    res = run(a.path, a.method, body, wait=a.wait, flows=a.flows, prefix=a.prefix, host=a.host)
    os.makedirs(a.out, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    tag = "%s_%s_%s" % (ts, a.method, a.path.strip("/").replace("/", "_") or "root")
    with open(os.path.join(a.out, tag + ".json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("status", res["status"], "| template:", res["template"])
    print(res["resp"][:1500])


if __name__ == "__main__":
    main()
