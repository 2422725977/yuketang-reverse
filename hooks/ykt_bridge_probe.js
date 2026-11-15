// ykt_bridge_probe.js — 雨课堂 H5↔原生 桥面 / H5 URL 生成 / Deeplink 取证探针（只读）
// 目标: libapp.so (Dart AOT)。用法:
//   frida -U -f com.xuetangx.ykt -l ykt_bridge_probe.js --no-pause
// 依赖: 无（不加载 blutter_frida.js）。内建最小 Dart 解码: HEAP=ctx.x28<<32,
//       参数 i = ctx.x15.add(8*i).readPointer(); 字符串 cid 94/95, len@+8, data@+16。
// 产出: /data/local/tmp/ykt_bridge.jsonl，每行 {ts, fn, a1, a2, ret}（字符串直接解码，其余打 cid）。
// 覆盖: 4 个 JS 桥 dispatcher / H5 URL 生成 / WebView 打开 / OSS 直传三件套 / deeplink 解析 / LogUtils。

const CFG = {
  module: "libapp.so",
  logPath: "/data/local/tmp/ykt_bridge.jsonl",
  maxChars: 3000,
  alsoConsole: true,
};

const TARGETS = [
  { name: "JsCallFlutter::dispatchAction",         rva: 0xba725c,  guard: ["fd79bfa9", "ef4104d1"], nargs: 2, ret: false },
  { name: "ShareJsCallFlutter::dispatchAction",    rva: 0xc7de84,  guard: ["fd79bfa9", "efa102d1"], nargs: 2, ret: false },
  { name: "_ExamPageState::dispatch(js)",          rva: 0xc97744,  guard: ["fd79bfa9", "efe103d1"], nargs: 2, ret: false },
  { name: "_StudyPartnerWebviewState::dispatch",   rva: 0xd5e07c,  guard: ["fd79bfa9", "efc103d1"], nargs: 2, ret: false },
  { name: "DataUtil::getJournalH5Url",             rva: 0xe953cc,  guard: ["fd79bfa9", "ef8101d1"], nargs: 2, ret: true  },
  { name: "getWebViewPageWidget",                  rva: 0xbd121c,  guard: ["fd79bfa9", "ef8105d1"], nargs: 3, ret: false },
  { name: "JsCallFlutter::getTokenData",           rva: 0xbc5024,  guard: ["fd79bfa9", "ef6105d1"], nargs: 2, ret: false },
  { name: "JsCallFlutter::uploadFile",             rva: 0xbc676c,  guard: ["fd79bfa9", "efc100d1"], nargs: 2, ret: false },
  { name: "JsCallFlutter::getAliOssConfig",        rva: 0xbc630c,  guard: ["fd79bfa9", "ef8101d1"], nargs: 2, ret: false },
  { name: "JsCallFlutter::postHomeworkDataToJS",   rva: 0xbc6004,  guard: ["fd79bfa9", "ef0101d1"], nargs: 2, ret: false },
  { name: "_MyHomePageState::processLinkParams",   rva: 0xc20698,  guard: ["fd79bfa9", "efc100d1"], nargs: 2, ret: false },
  { name: "LogUtils::i",                           rva: 0x7da6f4,  guard: ["fd79bfa9", "ef2100d1"], nargs: 2, ret: false },
];

/* ---------- 最小 Dart AOT 解码 ---------- */
let HEAP = null;
var CID_STRING = 94, CID_TWO_BYTE = 95;
function initHeap(ctx) { if (HEAP === null && ctx.x28) HEAP = ctx.x28.shl(32); }
function isHeapObj(p) { return (p.toInt32() & 1) === 1; }
function deref(p) { return HEAP.add(p.toInt32()); }
function readVal(tp) {
  try {
    if (tp.isNull()) return { t: "null", v: "null" };
    if (!isHeapObj(tp)) return { t: "smi", v: String(tp.toInt32() >> 1) };
    var o = deref(tp).sub(1);
    var cid = (o.readU32() >>> 12) & 0xfffff;
    if (cid === CID_STRING || cid === CID_TWO_BYTE) {
      var len = o.add(8).readU32() >>> 1;
      if (len < 0 || len > (1 << 20)) return { t: "str?", v: "<bad len " + len + ">" };
      var d = o.add(16);
      var s = (cid === CID_STRING) ? d.readUtf8String(len) : d.readUtf16String(len);
      if (s && s.length > CFG.maxChars) s = s.slice(0, CFG.maxChars) + "…";
      return { t: "str", v: s };
    }
    if (cid === 77 || cid === 78) return { t: "list", v: "<cid=" + cid + ">" };
    return { t: "obj", v: "<cid=" + cid + ">" };
  } catch (e) { return { t: "err", v: String(e) }; }
}
function argVal(ctx, idx) { return readVal(ctx.x15.add(8 * idx).readPointer()); }
function valStr(v) { return v.v; }

/* ---------- 落盘 ---------- */
var logFile = null;
try { logFile = new File(CFG.logPath, "a"); } catch (e) { logFile = null; }
var expTag = "B0";
function emit(ev) {
  ev.exp = expTag;
  var line = JSON.stringify(ev);
  if (logFile) { try { logFile.write(line + "\n"); logFile.flush(); } catch (e) {} }
  if (CFG.alsoConsole) console.log("[BRIDGE] " + (line.length > 700 ? line.slice(0, 700) + "…" : line));
}

/* ---------- 挂点 ---------- */
var base = null;
function guardOk(addr, guard) {
  try {
    var a = addr.readByteArray(4), b = addr.add(8).readByteArray(4);
    function hex(buf) {
      var u = new Uint8Array(buf), s = "";
      for (var i = 0; i < u.length; i++) { s += ("0" + u[i].toString(16)).slice(-2); }
      return s;
    }
    return hex(a) === guard[0] && hex(b) === guard[1];
  } catch (e) { return false; }
}

var attached = 0, failed = 0;
function attachOne(t) {
  var addr = base.add(t.rva);
  if (!guardOk(addr, t.guard)) {
    failed++;
    console.log("[GUARD-FAIL] " + t.name + " @base+0x" + t.rva.toString(16) +
                " 实际: " + (function () { try { var u = new Uint8Array(addr.readByteArray(12)), s = ""; for (var i = 0; i < u.length; i++) { s += ("0" + u[i].toString(16)).slice(-2); } return s; } catch (e) { return "?"; } })() +
                " 期望: " + t.guard.join("") + " —— 版本/地址不符，跳过硬挂");
    return;
  }
  try {
    Interceptor.attach(addr, {
      onEnter: function (ctx) {
        initHeap(ctx);
        try {
          var ev = { ts: Date.now(), fn: t.name };
          for (var i = 1; i < t.nargs; i++) {
            var v = argVal(ctx, i);
            ev["a" + i] = valStr(v);
          }
          this.ev = ev;
        } catch (e) {
          this.ev = { ts: Date.now(), fn: t.name, a1: "<enter-err " + e + ">" };
        }
      },
      onLeave: function (retval) {
        try {
          if (t.ret) {
            var ctx = this.context;
            initHeap(ctx);
            this.ev["ret"] = valStr(readVal(ctx.x0));
          }
        } catch (e) { if (this.ev) this.ev["ret"] = "<leave-err " + e + ">"; }
        if (this.ev) emit(this.ev);
      },
    });
    attached++;
    console.log("[OK] " + t.name + " @base+0x" + t.rva.toString(16));
  } catch (e) {
    failed++;
    console.log("[ATTACH-FAIL] " + t.name + ": " + e);
  }
}

function onLibapp(m) {
  base = m.base;
  console.log("[i] libapp.so base = " + base + "  size = 0x" + m.size.toString(16));
  for (var i = 0; i < TARGETS.length; i++) attachOne(TARGETS[i]);
  console.log("[i] 挂点成功 " + attached + " / 失败 " + failed + "；日志 " + CFG.logPath);
  try {
    if (logFile) logFile.write(JSON.stringify({ ts: Date.now(), dir: "META", fn: "attach", ok: attached, fail: failed }) + "\n");
  } catch (e) {}
}

function main() {
  var m = Process.findModuleByName(CFG.module);
  if (m) { onLibapp(m); return; }
  var tries = 0;
  var iv = setInterval(function () {
    tries++;
    var mm = Process.findModuleByName(CFG.module);
    if (mm) { clearInterval(iv); onLibapp(mm); }
    else if (tries > 600) { clearInterval(iv); console.log("[!] 等不到 " + CFG.module); }
  }, 200);
}

rpc.exports = {
  markExp: function (tag) { expTag = tag; emit({ ts: Date.now(), dir: "META", fn: "markExp", tag: tag }); return tag; },
  path: function () { return CFG.logPath; },
  attached: function () { return { ok: attached, fail: failed }; },
};

main();
