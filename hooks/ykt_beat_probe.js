// ykt_beat_probe.js —— 雨课堂 学习时长心跳（/mobile-app/video-log/heartbeat/）只读取证探针
// 用法：frida -U -f com.xuetangx.ykt -l hooks/ykt_beat_probe.js --no-pause
// 日志：/data/local/tmp/ykt_beat.jsonl  每行 {ts,exp,fn,rva,args,ret}
// 纪律：只读；不改内存、不改返回值。所有挂点带 Dart AOT prologue guard 校验。
'use strict';

const CFG = { module: 'libapp.so', log: '/data/local/tmp/ykt_beat.jsonl' };

// rva -> guard[首4字节, 第3条指令4字节]（libapp.so 文件字节序；Dart AOT 首 4 字节恒 fd79bfa9）
const POINTS = [
  { name: 'HeartBeatUtil::postBeat',              rva: 0xbdec24, guard: ['fd79bfa9', 'efe100d1'] },
  { name: 'HeartBeatUtil::getHeartBeatData',      rva: 0xc46bf4, guard: ['fd79bfa9', 'ef6100d1'] },
  { name: 'HeartBeatUtil::heartBeatUpload',       rva: 0xc45d90, guard: ['fd79bfa9', 'efa100d1'] },
  { name: 'HeartBeatUtil::localBeatUploadUnLock', rva: 0xc25d3c, guard: ['fd79bfa9', 'ef8100d1'] },
  { name: 'HeartBeatUtil::heartBeatUploadAudio',  rva: 0xdd4834, guard: ['fd79bfa9', 'efc100d1'] },
  { name: 'BeatDBHelper::insertHeartBeat',        rva: 0xbdff84, guard: ['fd79bfa9', 'ef8100d1'] },
  { name: 'BeatDBHelper::selectHeartBeats',       rva: 0xbdcdf8, guard: ['fd79bfa9', 'ef6101d1'] },
  { name: 'LiveHeartBeatUtil::postLiveBeat',      rva: 0xbde484, guard: ['fd79bfa9', 'efe100d1'] },
];

const P = Process.pointerSize;
let LOGF = null;
let EXP = 'T0';
function openLog() { try { LOGF = new File(CFG.log, 'a'); } catch (e) { LOGF = null; } }
function emit(obj) {
  const line = JSON.stringify(obj);
  if (LOGF) { try { LOGF.write(line + '\n'); LOGF.flush(); return; } catch (e) {} }
  console.log('[beat] ' + line);
}

function modBase() { const m = Process.findModuleByName(CFG.module); return m ? m.base : null; }
function argOf(ctx, idx) { return ctx.x15.add(P * idx).readPointer(); }
function cidOf(tagged) { try { return (tagged.sub(1).readU32() >>> 12) & 0xfffff; } catch (e) { return -1; } }
function tryStr(tagged) {
  try {
    const cid = cidOf(tagged);
    if (cid !== 94 && cid !== 95) return null;
    const o = tagged.sub(1);
    const len = o.add(8).readU32() >>> 1;
    if (len <= 0 || len > 4096) return null;
    return cid === 94 ? o.add(16).readUtf8String(len) : o.add(16).readUtf16String(len);
  } catch (e) { return null; }
}
function describe(tagged) {
  if (!tagged || tagged.isNull()) return null;
  const s = tryStr(tagged);
  return s !== null ? s : '<cid=' + cidOf(tagged) + '>';
}
function hexAt(addr, off) {
  try {
    const buf = addr.add(off).readByteArray(4);
    return Array.from(new Uint8Array(buf)).map((x) => ('0' + x.toString(16)).slice(-2)).join('');
  } catch (e) { return '????'; }
}

function attachOne(mod, pt) {
  const addr = mod.base.add(pt.rva);
  const g0 = hexAt(addr, 0), g1 = hexAt(addr, 8);
  if (g0 !== pt.guard[0] || g1 !== pt.guard[1]) {
    emit({ ts: Date.now(), exp: EXP, fn: pt.name, guardFail: true, rva: '0x' + pt.rva.toString(16), got: g0 + ',' + g1, want: pt.guard.join(',') });
    return false;
  }
  Interceptor.attach(addr, {
    onEnter: function () {
      this.pt = pt;
      this.a = [describe(argOf(this.context, 1)), describe(argOf(this.context, 2)), describe(argOf(this.context, 3))];
    },
    onLeave: function (ret) {
      emit({ ts: Date.now(), exp: EXP, fn: this.pt.name, rva: '0x' + this.pt.rva.toString(16),
             args: this.a.filter((x) => x !== null), ret: describe(ret) });
    },
  });
  return true;
}

let attached = 0;
function onLibLoaded() {
  const mod = Process.findModuleByName(CFG.module);
  if (!mod) return false;
  openLog();
  POINTS.forEach((pt) => { if (attachOne(mod, pt)) attached++; });
  emit({ ts: Date.now(), exp: EXP, attached: attached, total: POINTS.length, log: CFG.log });
  console.log('[beat] attached ' + attached + '/' + POINTS.length + ' -> ' + CFG.log);
  return true;
}
(function main() {
  if (onLibLoaded()) return;
  const iv = setInterval(() => { if (onLibLoaded()) clearInterval(iv); }, 200);
})();

rpc.exports = {
  markExp: function (tag) { EXP = String(tag); emit({ ts: Date.now(), fn: 'markExp', exp: EXP }); return EXP; },
  path: function () { return CFG.log; },
  attached: function () { return attached; },
  points: function () { return POINTS.map((p) => p.name + ' @0x' + p.rva.toString(16)); },
};
