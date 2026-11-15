#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""雨课堂会话客户端（仅标准库）

实现 report/雨课堂_逆向分析报告.md §2.4 记录的全部会话语义：
  * 默认头: Accept / Content-Type / xtbz:ykt / x-client:app / User-Agent
  * 逐请求头: X-UID = <用户 id>;  Authorization = "Bearer " + <Set-Auth 值>
  * Cookie: csrftoken=<...>; sessionid=<...>; sid=<...>   (逐响应吸收 Set-Cookie, 支持轮换)
  * 业务码 100000 = 会话失效(客户端会跳 /userLogin)
  * WebSocket: wss://<host>/wsapp/  握手只带 User-Agent; 鉴权靠首帧 hello

本工具只发你自己账号的请求；所有目标/凭据用参数或环境变量给出。
用法见 --help，或看 replay/README.md。
"""
import argparse
import base64
import http.client
import json
import os
import random
import socket
import ssl
import struct
import sys
import time
import urllib.parse

DEFAULT_BASE = os.environ.get("YKT_BASE", "https://www.yuketang.cn")
RELOGIN_CODE = 100000   # BaseNet::setReLoginCode 0x145137c
DEFAULT_HEADERS = {     # App::initNet 0x1450b14
    "Accept": "application/json",
    "Content-Type": "application/json; charset=UTF-8",
    "xtbz": "ykt",
    "x-client": "app",
    "User-Agent": "Android",
}


def _log(trace, obj):
    if not trace:
        return
    obj = dict(obj)
    obj["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(trace, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


class Session:
    def __init__(self, base=DEFAULT_BASE, cookie=None, uid=None, auth=None,
                 insecure=False, trace=None, timeout=15):
        self.base = base.rstrip("/")
        u = urllib.parse.urlsplit(self.base)
        self.host = u.hostname
        self.port = u.port or (443 if u.scheme == "https" else 80)
        self.tls = u.scheme == "https"
        self.uid = uid
        self.auth = auth
        self.cookies = {}
        self.extra_cookies = {}
        self.trace = trace
        self.timeout = timeout
        self.ctx = ssl.create_default_context()
        if insecure:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        if cookie:
            for part in cookie.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    self.cookies[k] = v

    # ---------- HTTP ----------
    def cookie_header(self):
        # utils_function.dart 0x92f180 段
        parts = []
        if self.cookies.get("csrftoken"):
            parts.append("csrftoken=" + self.cookies["csrftoken"])
        if self.cookies.get("sessionid"):
            parts.append("sessionid=" + self.cookies["sessionid"])
        if self.cookies.get("sid"):
            parts.append("sid=" + self.cookies["sid"])
        parts.append("xtbbz=ykt")
        for k, v in self.extra_cookies.items():
            parts.append("%s=%s" % (k, v))
        return "; ".join(parts)

    def _apply_response(self, msg, body_text):
        changed = []
        for sc in (msg.get_all("Set-Cookie") or []):
            kv = sc.split(";")[0]
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in ("csrftoken", "sessionid", "sid"):
                if self.cookies.get(k) != v:
                    changed.append(k)
                self.cookies[k] = v
            else:
                self.extra_cookies[k] = v
                changed.append(k)
        set_auth = msg.get("Set-Auth")
        if set_auth:
            self.auth = set_auth
            changed.append("Set-Auth")
        self._last_changed = changed
        rl = None
        try:
            obj = json.loads(body_text) if body_text else None
            if isinstance(obj, dict):
                rl = obj.get("code") if obj.get("code") == RELOGIN_CODE else None
                if rl is None and obj.get("error_code") == RELOGIN_CODE:
                    rl = RELOGIN_CODE
        except Exception:
            pass
        return rl

    def request(self, method, path, body=None, headers=None, raw=None):
        hdrs = dict(DEFAULT_HEADERS)
        hdrs["Cookie"] = self.cookie_header()
        if self.uid:
            hdrs["X-UID"] = str(self.uid)
        if self.cookies.get("csrftoken"):
            hdrs["X-CSRFToken"] = self.cookies["csrftoken"]
        if self.auth:
            hdrs["Authorization"] = "Bearer " + self.auth
        if headers:
            hdrs.update(headers)
        payload = None
        if raw is not None:
            payload = raw.encode("utf-8") if isinstance(raw, str) else raw
        elif body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if self.tls:
            conn = http.client.HTTPSConnection(self.host, self.port, context=self.ctx, timeout=self.timeout)
        else:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        _log(self.trace, {"dir": "REQ", "method": method, "path": path, "headers": hdrs, "body": body})
        conn.request(method, path, body=payload, headers=hdrs)
        resp = conn.getresponse()
        text = resp.read().decode("utf-8", "replace")
        relogin = self._apply_response(resp.msg, text)
        out = {
            "status": resp.status,
            "changed": list(self._last_changed),
            "cookie": dict(self.cookies),
            "json": None,
            "text": text[:4000],
        }
        try:
            out["json"] = json.loads(text)
        except Exception:
            pass
        if relogin == RELOGIN_CODE:
            out["relogin_required"] = True
        # 会话轮换后 cookie 变了 -> 下一个请求必须用新 cookie（本类自动处理）
        self.cookies = dict(self.cookies)
        conn.close()
        _log(self.trace, {"dir": "RES", "status": resp.status, "changed": out["changed"],
                          "relogin": bool(out.get("relogin_required")), "body": out["text"][:2000]})
        return out

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body=body, **kw)

    # ---------- WebSocket (RFC6455, stdlib) ----------
    def ws_connect(self, path="/wsapp/", ua="Android-mobile", with_cookie=False):
        host = self.host
        if self.tls:
            s = self.ctx.wrap_socket(socket.create_connection((host, self.port), timeout=self.timeout),
                                    server_hostname=host)
        else:
            s = socket.create_connection((host, self.port), timeout=self.timeout)
        key = base64.b64encode(bytes(random.getrandbits(8) for _ in range(16))).decode()
        req = ["GET %s HTTP/1.1" % path, "Host: %s:%d" % (host, self.port),
               "Upgrade: websocket", "Connection: Upgrade",
               "Sec-WebSocket-Key: " + key, "Sec-WebSocket-Version: 13",
               "User-Agent: " + ua]
        if with_cookie:   # 原客户端握手不带 cookie（observed）；需要时显式打开
            req.append("Cookie: " + self.cookie_header())
        s.sendall(("\r\n".join(req) + "\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                raise RuntimeError("WS handshake closed")
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        status = head.split(b"\r\n")[0].decode()
        _log(self.trace, {"dir": "WS", "event": "handshake", "status": status})
        if "101" not in status:
            raise RuntimeError("WS handshake failed: " + status)
        self._ws = s
        self._ws_buf = rest
        return status

    def _ws_send_frame(self, data, opcode=0x1):
        if isinstance(data, str):
            data = data.encode("utf-8")
        mask = bytes(random.getrandbits(8) for _ in range(4))
        n = len(data)
        header = bytes([0x80 | opcode])
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self._ws.sendall(header + mask + masked)

    def ws_send_op(self, op, **fields):
        msg = {"op": op}
        msg.update(fields)
        payload = json.dumps(msg, ensure_ascii=False)
        _log(self.trace, {"dir": "WS-OUT", "op": op, "raw": payload})
        self._ws_send_frame(payload)
        return payload

    def _ws_recv_exact(self, n):
        buf = self._ws_buf
        while len(buf) < n:
            chunk = self._ws.recv(65536)
            if not chunk:
                raise RuntimeError("WS closed")
            buf += chunk
        out, self._ws_buf = buf[:n], buf[n:]
        return out

    def ws_recv(self, timeout=1.0):
        self._ws.settimeout(timeout)
        h = self._ws_recv_exact(2)
        opcode = h[0] & 0x0F
        masked = bool(h[1] & 0x80)
        ln = h[1] & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", self._ws_recv_exact(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", self._ws_recv_exact(8))[0]
        mask = self._ws_recv_exact(4) if masked else None
        data = self._ws_recv_exact(ln) if ln else b""
        if mask:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode == 0x9:   # ping
            self._ws_send_frame(data, 0xA)
            return self.ws_recv(timeout)
        if opcode == 0xA:
            return self.ws_recv(timeout)
        if opcode == 0x8:
            raise RuntimeError("WS close frame")
        return data.decode("utf-8", "replace")


# ---------- 便利封装（模块场景，端点见报告 §10） ----------
def login_app(s, phone, password, type_=1, extra=None):
    body = {"type": type_, "phoneNumber": phone, "password": password,
            "email": "", "code": "", "pushDeviceId": ""}
    if extra:
        body.update(extra)
    return s.post("/api/v3/user/login/app", body)


def checkin_plain(s, lesson_id, source=46):
    return s.post("/api/v3/lesson/checkin",
                  {"lessonId": lesson_id, "source": source, "joinIfNotIn": True})


def checkin_web(s, invite_code, source=46):
    return s.post("/api/lesson/web_check_in", {"invite_code": invite_code, "source": source})


def checkin_loc_eligibility(s, lesson_id):
    return s.get("/api/v3/lesson/location-checkin/eligibility?lessonId=" + urllib.parse.quote(str(lesson_id)))


def checkin_loc_submit(s, lesson_id, lat, lng, address="", source=54):
    return s.post("/api/v3/lesson/location-checkin/submit",
                  {"lat": lat, "lng": lng, "lessonId": lesson_id, "source": source, "address": address})


def answer_problem(s, problem_id, problem_type, result, dt=None, extra=None):
    body = {"problemId": problem_id, "problemType": problem_type, "result": result}
    if dt is not None:
        body["dt"] = dt
    if extra:
        body.update(extra)
    return s.post("/api/v3/lesson/problem/answer", body)


def rapid_answer(s, lesson_id, extra=None):
    body = {"lessonId": lesson_id}
    if extra:
        body.update(extra)
    return s.post("/api/v3/lesson/rapid-answer/participate", body)


def danmu_send(s, lesson_id, message, extra="", target="", user_name="", from_start=False,
               required_censor=1, show_status=0, word_cloud=0):
    return s.post("/api/v3/lesson/danmu/send",
                  {"lessonId": lesson_id, "message": message, "extra": extra, "target": target,
                   "userName": user_name, "fromStart": from_start, "requiredCensor": required_censor,
                   "showStatus": show_status, "wordCloud": word_cloud})


def ws_hello(s, lesson_id, uid, auth, role="student", avatar=""):
    op = {"op": "hello", "lessonid": lesson_id, "userid": uid, "role": role, "auth": auth}
    if role == "lecturer":
        op["avatar"] = avatar
    return s.ws_send_op(**{"op": op.get("op")}) if False else s.ws_send_op(
        "hello", lessonid=lesson_id, userid=uid, role=role, auth=auth, **({"avatar": avatar} if avatar else {}))


# ---------- CLI ----------
def _mk(args):
    return Session(base=args.base, cookie=args.cookie, uid=args.uid, auth=args.auth,
                   insecure=args.insecure, trace=args.trace, timeout=args.timeout)


def main(argv=None):
    ap = argparse.ArgumentParser(description="雨课堂会话客户端（stdlib）")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--cookie", help='如 "csrftoken=..; sessionid=..; sid=.."')
    ap.add_argument("--uid")
    ap.add_argument("--auth", help="Set-Auth 值（Bearer 后面的部分）")
    ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--trace", help="把每个请求/响应写成 jsonl")
    ap.add_argument("--timeout", type=float, default=15)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("http", help="单次请求")
    p.add_argument("method")
    p.add_argument("path")
    p.add_argument("--json", dest="json_body")
    p.add_argument("--file", help="从文件读 body")
    p.add_argument("--header", action="append", default=[])

    p = sub.add_parser("replay", help="按 jsonl 回放（每行 {method,path,json}）")
    p.add_argument("file")
    p.add_argument("--sleep", type=float, default=0.5)

    p = sub.add_parser("login", help="账号密码登录 /api/v3/user/login/app")
    p.add_argument("--phone", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--type", type=int, default=1)

    p = sub.add_parser("ws", help="连 WebSocket 并发 op（默认 hello）")
    p.add_argument("--lesson-id", required=True)
    p.add_argument("--user-id")
    p.add_argument("--auth-token")
    p.add_argument("--role", default="student", choices=["student", "lecturer"])
    p.add_argument("--ws-path", default="/wsapp/")
    p.add_argument("--ua", default="Android-mobile")
    p.add_argument("--with-cookie", action="store_true", help="握手带 Cookie（原客户端不带）")
    p.add_argument("--send-hello", action="store_true")
    p.add_argument("--op", action="append", default=[],
                   help='额外注入的 op，JSON 形式，如 {"op":"detectlesson","lessonid":"..."}')
    p.add_argument("--listen", type=float, default=20)

    a = ap.parse_args(argv)
    s = _mk(a)

    if a.cmd == "http":
        body = None
        if a.json_body:
            body = json.loads(a.json_body)
        elif a.file:
            body = json.loads(open(a.file, encoding="utf-8").read())
        hdrs = {}
        for h in a.header:
            if ":" in h:
                k, v = h.split(":", 1)
                hdrs[k.strip()] = v.strip()
        print(json.dumps(s.request(a.method.upper(), a.path, body=body, headers=hdrs),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "replay":
        n = 0
        for line in open(a.file, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            item = json.loads(line)
            r = s.request(item.get("method", "POST"), item["path"], body=item.get("json"))
            n += 1
            print("[%d] %s %s -> %s %s" % (n, item.get("method", "POST"), item["path"],
                                           r["status"], r.get("text", "")[:200]))
            if r.get("relogin_required"):
                print("!! 业务码 100000：会话已失效，需要重新登录")
                break
            time.sleep(a.sleep)
    elif a.cmd == "login":
        r = login_app(s, a.phone, a.password, a.type)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif a.cmd == "ws":
        print(s.ws_connect(a.ws_path, ua=a.ua, with_cookie=a.with_cookie))
        if a.send_hello or not a.op:
            print("->", ws_hello(s, a.lesson_id, a.user_id or s.uid, a.auth_token or s.auth or "", a.role))
        for opjson in a.op:
            op = json.loads(opjson)
            print("->", s.ws_send_op(**op))
        end = time.time() + a.listen
        while time.time() < end:
            try:
                print("<-", s.ws_recv(1.0))
            except socket.timeout:
                continue
            except RuntimeError as e:
                print("!!", e)
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
