// ykt_proctor_probe.js —— 雨课堂 考试监考/反作弊 上报面 只读取证探针
// 目标: libapp.so (Dart AOT)。用法:
//   frida -U -f com.xuetangx.ykt -l hooks/ykt_proctor_probe.js --no-pause
// 依赖: 无（自包含）。内建最小 Dart 解码: HEAP=ctx.x28<<32,
//       参数 i = ctx.x15.add(8*i).readPointer(); 字符串 cid 94/95, len@+8(>>1), data@+16。
// 日志: /data/local/tmp/ykt_proctor.jsonl 每行 {ts, exp, fn, rva, args, ret}
// 纪律: 只读；guard 与 libapp.so 文件字节同序，逐点校验，不符即跳过硬挂。
// 覆盖: 监考 HTTP 上报(reprotExam/reprotExamShowToast/reprotExamByVm) / 分屏监听 /
//       抓拍与上传(postAutoPhotoUpload/_uploadImageCallH5Methods/接收闭包) /
//       光速虚拟机检测(collectVirtualEnvironmentReport/_detectGuangsuVirtualMachine)。

const CFG = { module: 'libapp.so', log: '/data/local/tmp/ykt_proctor.jsonl' };

// rva -> guard[前 4 字节, +8 处 4 字节]（文件字节序；Dart AOT 首 4 字节恒 fd79bfa9）
const POINTS = [
  { name: 'ExamPage::reprotExam(action, exam_id)',        rva: 0x93d76c, guard: ['fd79bfa9', 'ef8101d1'], args: 3 },
  { name: 'ExamPage::reprotExamShowToast(action)',        rva: 0x93dce4, guard: ['fd79bfa9', 'efa101d1'], args: 2 },
  { name: 'ExamPage::reprotExamByVm(vm_report)',          rva: 0xc970f8, guard: ['fd79bfa9', 'ef8101d1'], args: 2 },
  { name: 'ExamPage::_listenAppSizeChange',               rva: 0xc91d90, guard: ['fd79bfa9', 'ef8100d1'], args: 2 },
  { name: 'ExamPage::examSplitScreenResumeCallBack',      rva: 0xc96e10, guard: ['fd79bfa9', 'ef4100d1'], args: 2 },
  { name: 'ExamPage::_detectGuangsuVirtualMachine',       rva: 0xc96f90, guard: ['fd79bfa9', 'efc100d1'], args: 2 },
  { name: 'collectVirtualEnvironmentReport',              rva: 0xc972f8, guard: ['fd79bfa9', 'ef0102d1'], args: 1 },
  { name: 'ExamPage::postAutoPhotoUpload(path)',          rva: 0xc9ec8c, guard: ['fd79bfa9', 'ef4101d1'], args: 2 },
  { name: 'ExamPage::_uploadImageCallH5Methods(url)',     rva: 0xc9ef68, guard: ['fd79bfa9', 'efc100d1'], args: 2 },
  { name: 'ExamPage::closure_AutoCameraEvent',            rva: 0xc92cfc, guard: ['fd79bfa9', 'a00f40f9'], args: 2 },
];

const P = Process.pointerSize;
let LOGF = null;
let EXP = 'P0';
function openLog() { try { LOGF = new File(CFG.log, 'a'); } catch (e) { LOGF = null; } }
function emit(o) {
  const line = JSON.stringify(o);
  if (LOGF) { try { LOGF.write(line + '\n'); LOGF.flush(); return; } catch (e) {} }
  console.log('[proctor] ' + line);
}
function modBase() { const m = Process.findModuleByName(CFG.module); return m ? m.base : null; }
function argOf(ctx, idx) { return ctx.x15.add(P * idx).readPointer(); }
function cidOf(t) { try { return (t.sub(1).readU32() >>> 12) & 0xfffff; } catch (e) { return -1; } }
function tryStr(t) {
  try {
    const cid = cidOf(t);
    if (cid !== 94 && cid !== 95) return null;
    const o = t.sub(1), len = o.add(8).readU32() >>> 1;
    if (len <= 0 || len > 8192) return null;
    return cid === 94 ? o.add(16).readUtf8String(len) : o.add(16).readUtf16String(len);
  } catch (e) { return null; }
}
function val(t) {
  if (!t || t.isNull()) return 'null';
  if ((t.toInt32() & 1) === 0) return t.toInt32() >> 1;           // Smi
  const s = tryStr(t);
  return s === null ? '<obj cid=' + cidOf(t) + '>' : s;
}
function hexAt(a, off) {
  try { return Array.from(new Uint8Array(a.add(off).readByteArray(4))).map((x) => ('0' + x.toString(16)).slice(-2)).join(''); }
  catch (e) { return '????'; }
}
function attachOne(mod, pt) {
  const addr = mod.base.add(pt.rva);
  const g0 = hexAt(addr, 0), g1 = hexAt(addr, 8);
  if (g0 !== pt.guard[0] || g1 !== pt.guard[1]) {
    emit({ ts: Date.now(), exp: EXP, fn: pt.name, guardFail: true, rva: '0x' + pt.rva.toString(16), got: g0 + ',' + g1, want: pt.guard.join(',') });
    return;
  }
  try {
    Interceptor.attach(addr, {
      onEnter(args) {
        const ctx = this.context;
        const a = [];
        for (let i = 1; i < (pt.args || 2); i++) a.push(val(argOf(ctx, i)));
        this._a = a;
      },
      onLeave(ret) {
        emit({ ts: Date.now(), exp: EXP, fn: pt.name, rva: '0x' + pt.rva.toString(16), args: this._a, ret: val(ret) });
      },
    });
    console.log('[proctor] 已挂 ' + pt.name + ' @base+0x' + pt.rva.toString(16));
  } catch (e) { console.log('[proctor] 挂载失败 ' + pt.name + ': ' + e); }
}
function main() {
  const m = Process.findModuleByName(CFG.module);
  if (!m) { setTimeout(main, 200); return; }
  for (const pt of POINTS) attachOne(m, pt);
  console.log('[proctor] 就绪，日志 ' + CFG.log + '，实验号 EXP=' + EXP);
}
openLog();
rpc.exports = {
  markExp(tag) { EXP = String(tag); emit({ ts: Date.now(), exp: EXP, fn: '<markExp>' }); return EXP; },
  path() { return CFG.log; },
  points() { return POINTS.map((p) => p.name + ' @0x' + p.rva.toString(16)); },
};
main();
