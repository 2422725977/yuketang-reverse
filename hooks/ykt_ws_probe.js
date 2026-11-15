// ykt_ws_probe.js — 雨课堂 WebSocket 协议取证探针（只读观测，不改行为）
// 目标: libapp.so (Dart AOT)。用法:
//   frida -U -f com.xuetangx.ykt -l ykt_ws_probe.js --no-pause
// 说明: 不依赖 blutter_frida.js（其 onLibappLoaded 含未定义函数会抛错），
//       内建最小 Dart 对象解码器（压缩指针, heap=ctx.x28<<32, 字符串 len@+8 data@+16）。
// 产出: /data/local/tmp/ykt_ws.jsonl 每行一个 JSON 事件 {ts, dir, fn, url|op|raw}

const CFG = {
  module: "libapp.so",
  logPath: "/data/local/tmp/ykt_ws.jsonl",
  maxChars: 4000,
  alsoConsole: true,
};

const TARGETS = [
  { name: "WSConnector::WSConnector",          rva: 0xc15134,  guard: ["fd79bfa9", "ef2100d1"], kind: "ctor"    },
  { name: "WSConnector::connect",              rva: 0xc15220,  guard: ["fd79bfa9", "efe100d1"], kind: "connect" },
  { name: "WSConnector::send",                 rva: 0x91e988,  guard: ["fd79bfa9", "ef6100d1"], kind: "send"    },
  { name: "ReceiverProcesser::process",        rva: 0x142515c, guard: ["fd79bfa9", "ef8100d1"], kind: "recv"    },
  { name: "RemoteControlProcesser::process",   rva: 0x143a028, guard: ["fd79bfa9", "efa100d1"], kind: "recv"    },
  { name: "WSConnector::_tryReconnectAfterDelay", rva: 0xc191f8, guard: ["fd79bfa9", "ef8100d1"], kind: "reconnect" },
  { name: "WSConnector::_teardownChannel",     rva: 0xc1905c,  guard: ["fd79bfa9", "ef6101d1"], kind: "teardown" },
];

/* ---------- 最小 Dart AOT 对象解码 ---------- */
let HEAP = null;
const CidString = 94, CidTwoByteString = 95, CidSmi = 60;
function initHeap(ctx) { if (HEAP === null && ctx.x28) HEAP = ctx.x28.shl(32); }
function argOf(ctx, idx) { return ctx.x15.add(8 * idx).readPointer(); }
function isHeapObj(p) { return (p.toInt32() & 1) === 1; }
function deref(p) { return HEAP.add(p.toInt32()); }
function cidOf(tp) { return (deref(tp).sub(1).readU32() >>> 12) & 0xfffff; }
function readVal(tp) {
  try {
    if (!isHeapObj(tp)) return { t: "smi", v: tp.toInt32() >> 1 };
    const o = deref(tp).sub(1);
    const cid = (o.readU32() >>> 12) & 0xfffff;
    if (cid === CidString || cid === CidTwoByteString) {
      const len = o.add(8).readU32() >>> 1;
      if (len < 0 || len > 1 << 20) return { t: "str?", v: "<bad len " + len + ">" };
      const d = o.add(16);
      return { t: "str", v: cid === CidString ? d.readUtf8String(len) : d.readUtf16String(len) };
    }
    return { t: "obj", v: "<cid=" + cid + ">" };
  } catch (e) { return { t: "err", v: String(e) }; }
}
function argText(ctx, idx) {
  const v = readVal(argOf(ctx, idx));
  return v.t === "obj" ? v.v : String(v.v);
}

/* ---------- 落盘 ---------- */
let logFile = null;
try { logFile = new File(CFG.logPath, "a"); } catch (e) { logFile = null; }
function emit(ev) {
  const line = JSON.stringify(ev);
  if (logFile) { try { logFile.write(line + "\n"); logFile.flush(); } catch (e) {} }
  if (CFG.alsoConsole) console.log("[WS] " + (line.length > 600 ? line.slice(0, 600) + "…" : line));
}
const directCap = 0; // 保留字段

/* ---------- 挂点 ---------- */
let base = null;
function guardOk(addr, guard) {
  try {
    const a = addr.readByteArray(4), b = addr.add(8).readByteArray(4);
    const hex = (buf) => Array.from(new Uint8Array(buf)).map(x => x.toString(16).padStart(2, "0")).join("");
    return hex(a) === guard[0] && hex(b) === guard[1];
  } catch (e) { return false; }
}
function attachOne(t) {
  const addr = base.add(t.rva);
  if (!guardOk(addr, t.guard)) {
    console.log("[GUARD-FAIL] " + t.name + " @base+0x" + t.rva.toString(16) +
      " 版本/地址不符，跳过硬挂");
    return;
  }
  Interceptor.attach(addr, {
    onEnter(args) {
      initHeap(this.context);
      let payload = null;
      try {
        if (t.kind === "send")      payload = { dir: "OUT", fn: t.name, raw: argText(this.context, 1).slice(0, CFG.maxChars) };
        else if (t.kind === "recv") payload = { dir: "IN",  fn: t.name, raw: argText(this.context, 1).slice(0, CFG.maxChars) };
        else if (t.kind === "connect" || t.kind === "ctor")
                                    payload = { dir: "META", fn: t.name, url: argText(this.context, 1).slice(0, 1024) };
        else                        payload = { dir: "META", fn: t.name };
      } catch (e) { payload = { dir: "ERR", fn: t.name, e: String(e) }; }
      payload.ts = Date.now();
      if (payload.raw) {
        const m = payload.raw.match(/"op"\s*:\s*"([^"]+)"/);
        if (m) payload.op = m[1];
      }
      emit(payload);
    }
  });
  console.log("[HOOK] " + t.name + " @base+0x" + t.rva.toString(16) + " (" + t.kind + ")");
}
function tryAttach() {
  const m = Process.findModuleByName(CFG.module);
  if (!m) { setTimeout(tryAttach, 200); return; }
  base = m.base;
  console.log("[WS] " + CFG.module + " base = " + base);
  for (const t of TARGETS) attachOne(t);
  console.log("[WS] 探针就绪，日志: " + CFG.logPath);
}
setTimeout(tryAttach, 0);

rpc.exports = {
  markExp(tag) { emit({ dir: "META", fn: "markExp", tag: String(tag), ts: Date.now() }); return tag; },
  path() { return CFG.logPath; },
};
