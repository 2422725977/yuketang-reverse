#!/usr/bin/env python3
"""雨课堂 WS 客户端（只读观测 / 单条 op 发送）

关键事实（observed，2026-11-17）：
  * 握手不需要鉴权头，仅 User-Agent（App 用 Android-pad / Android-mobile）；
    带上 Cookie / sessionid / x-uid 也能握手成功，但不影响鉴权结果。
  * 信封 {op, lessonid, ...}；hello 的 auth 字段必须是 lessonToken（lesson/add 或
    lesson/detail 返回的 231 字符 JWT），不是 App 的 authorization JWT（275 字符）——
    传 App JWT 会收到 {op:hello, message:authorize failed}。
  * hello 通过后服务端回 isAlive/isClone/state；但 wakelesson 只是被 ack，
    **不会**把 lesson 变成 live：随后 /api/v3/lesson/location-checkin/* 仍回 50004。
"""
import argparse, base64, json, os, socket, ssl, struct, sys, time

FLOWS = os.environ.get('YKT_FLOWS', '/tmp/mitm/flows.mitm')


def native_headers():
    from mitmproxy import io as mio
    best = None
    with open(FLOWS, 'rb') as f:
        for fl in mio.FlowReader(f).stream():
            r = getattr(fl, 'request', None)
            if r and r.path.startswith('/api/v3') and len(r.headers.get('authorization') or '') == 279:
                best = dict(r.headers)
    if not best:
        sys.exit('flows 里没有 App 会话头')
    return best


class WS:
    def __init__(self, host='www.yuketang.cn', path='/wsapp/', ua='Android-pad', headers=None):
        ctx = ssl._create_unverified_context()
        s = socket.create_connection((host, 443), timeout=20)
        self.ss = ctx.wrap_socket(s, server_hostname=host)
        key = base64.b64encode(os.urandom(16)).decode()
        hdr = ['GET ' + path + ' HTTP/1.1', 'Host: ' + host, 'Upgrade: websocket',
               'Connection: Upgrade', 'Sec-WebSocket-Key: ' + key,
               'Sec-WebSocket-Version: 13', 'User-Agent: ' + ua]
        h = headers or {}
        if h.get('cookie'):
            hdr.append('Cookie: ' + h['cookie'])
        if h.get('sessionid'):
            hdr.append('sessionid: ' + h['sessionid'])
        if h.get('x-uid'):
            hdr.append('x-uid: ' + h['x-uid'])
        self.ss.sendall(('\r\n'.join(hdr) + '\r\n\r\n').encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            chunk = self.ss.recv(4096)
            if not chunk:
                raise RuntimeError('handshake closed')
            buf += chunk
        head, self.rest = buf.split(b'\r\n\r\n', 1)
        if b'101' not in head.split(b'\r\n')[0]:
            raise RuntimeError('handshake failed: ' + head[:200].decode('utf8', 'replace'))

    def send(self, obj):
        p = json.dumps(obj, ensure_ascii=False).encode()
        mask = os.urandom(4)
        n = len(p)
        h = bytearray([0x81])
        if n < 126:
            h.append(0x80 | n)
        elif n < 65536:
            h.append(0x80 | 126); h += struct.pack('>H', n)
        else:
            h.append(0x80 | 127); h += struct.pack('>Q', n)
        self.ss.sendall(bytes(h) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(p)))

    def recv(self, timeout=8):
        self.ss.settimeout(timeout)

        def need(n, buf):
            while len(buf) < n:
                c = self.ss.recv(65536)
                if not c:
                    raise RuntimeError('closed')
                buf += c
            return buf

        buf = need(2, self.rest)
        ln = buf[1] & 0x7F
        off = 2
        if ln == 126:
            buf = need(4, buf); ln = struct.unpack('>H', buf[2:4])[0]; off = 4
        elif ln == 127:
            buf = need(10, buf); ln = struct.unpack('>Q', buf[2:10])[0]; off = 10
        buf = need(off + ln, buf)
        self.rest = buf[off + ln:]
        return buf[off:off + ln].decode('utf8', 'replace')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--lesson-id', required=True)
    p.add_argument('--lesson-token', required=True)
    p.add_argument('--user-id', default=None)
    p.add_argument('--role', default='lecturer')
    p.add_argument('--avatar', default='')
    p.add_argument('ops', nargs='*', default=['hello'])
    a = p.parse_args()
    h = native_headers()
    uid = a.user_id or h.get('x-uid') or '0'
    ws = WS(headers=h)
    print('[ws] handshake ok (ua=Android-pad)')
    for op in a.ops:
        if op == 'hello':
            ws.send({'op': 'hello', 'userid': uid, 'role': a.role,
                     'lessonid': a.lesson_id, 'avatar': a.avatar, 'auth': a.lesson_token})
        elif op == 'wake':
            ws.send({'op': 'wakelesson', 'lessonid': a.lesson_id, 'title': 'ws_client',
                     'clone': False, 'role': a.role})
        elif op == 'detect':
            ws.send({'op': 'detectlesson', 'lessonid': a.lesson_id})
        else:
            print('unknown op', op); continue
        print('[send]', op)
        for _ in range(3):
            try:
                print('[recv]', ws.recv()[:300])
            except Exception as e:
                print('[recv-err]', e); break
        time.sleep(0.3)


if __name__ == '__main__':
    main()
