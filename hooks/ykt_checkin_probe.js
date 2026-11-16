/*
 * ykt_checkin_probe.js — 签到/迟到/补签 取证探针（本地测试样本，只读）
 *
 * 目的：把"签到请求体 → 服务端响应体"整条链路的字段落盘，用来回答
 *       「窗口外提交是否被服务端接受」「服务端是否回传 isLate / checkInTime」「老师端名单里能看到什么」。
 *
 * 加载：
 *   frida -U -f com.xuetangx.ykt -l blutter_out/blutter_frida.js -l hooks/ykt_checkin_probe.js --no-pause
 * 打点：每次实验前 setExp("E1")（或在 frida REPL 里调 rpc.exports.setExp("E1")），日志按实验号分组。
 * 落盘：/data/local/tmp/ykt_checkin.jsonl（每行一条 JSON），拉回：adb pull /data/local/tmp/ykt_checkin.jsonl
 *
 * guard 用字节十六进制串比较（文件字节顺序），地址=base+RVA，RVA 已由 capstone 逐条校验过。
 */
const CFG_CI = { module: "libapp.so", out: "/data/local/tmp/ykt_checkin.jsonl" };

/* 请求侧：谁把签到请求发出去 */
const REQ = [
  { name: "BaseNet::requestPost",                         rva: 0x923178, guard: ["fd79bfa9", "ef4105d1"], args: 8 },
  { name: "YuKetang::checkin",                            rva: 0xc521fc, guard: ["fd79bfa9", "efe100d1"], args: 2 },
  { name: "YuKetang::fetchCheckinList",                   rva: 0xc5687c, guard: ["fd79bfa9", "efe100d1"], args: 2 },
  { name: "_ReceiverClassPageState::_postLessonCheckin",  rva: 0xc196cc, guard: ["fd79bfa9", "ef6101d1"], args: 3 },
  { name: "_HmsScanPageState::_postLessonCheckin",        rva: 0xcd042c, guard: ["fd79bfa9", "ef6101d1"], args: 3 },
  { name: "_JoinClassroomDialogState::join",              rva: 0xf9e3ac, guard: ["fd79bfa9", "efc101d1"], args: 3 },
  { name: "_LocationCheckInPageState::_loadEligibility",  rva: 0xc64f04, guard: ["fd79bfa9", "ef6101d1"], args: 2 },
  { name: "_LocationCheckInPageState::_submit",           rva: 0xdee0b0, guard: ["fd79bfa9", "efa101d1"], args: 2 },
];

/* 响应侧：服务端回的 JSON 被解析进哪个 bean（静态 _$XxxFromJson 收原始 map） */
const RES = [
  { name: "JoinLessonBean.fromJson(普通/网页签到响应)",          rva: 0x114cb3c, guard: ["fd79bfa9", "efc100d1"], args: 2 },
  { name: "LocationCheckinSubmitBean.fromJson(定位签到响应)",    rva: 0x1171334, guard: ["fd79bfa9", "efc100d1"], args: 2 },
  { name: "LocationCheckinEligibilityData.fromJson(资格:isLate/wouldBeLate/pastOfficialEnd)", rva: 0x116faa0, guard: ["fd79bfa9", "ef8100d1"], args: 2 },
  { name: "LocationCheckinOverviewData.fromJson(老师端总览:isLate/time/lat/lng/address)",     rva: 0x1183c14, guard: ["fd79bfa9", "efc100d1"], args: 2 },
  { name: "LessonCheckinBean.fromJson",                          rva: 0x116d7bc, guard: ["fd79bfa9", "efc100d1"], args: 2 },
];

const HAS_BLUTTER_HELPERS = (typeof getTaggedObjectValue === "function") && (typeof getArg === "function");
let base = null;
let exp = "E0";
let fd = null;
let seq = 0;

function resolveBase() {
  const _m = Process.findModuleByName(CFG_CI.module); base = _m ? _m.base : null;
  return base;
}
function hexBytes(a, n) {
  const b = new Uint8Array(a.readByteArray(n));
  let s = "";
  for (let i = 0; i < b.length; i++) s += b[i].toString(16).padStart(2, "0");
  return s;
}
function guardOk(a, g) {
  if (!g) return true;
  try { return hexBytes(a, 4) === g[0] && hexBytes(a.add(8), 4) === g[1]; } catch (e) { return false; }
}
function openLog() {
  if (fd) return;
  try { fd = new File(CFG_CI.out, "a"); } catch (e) { console.log("[warn] 无法写 " + CFG_CI.out + "：" + e); }
}
function record(side, name, values, ret) {
  const line = { seq: ++seq, t: Date.now(), exp: exp, side: side, fn: name, args: values };
  if (ret !== undefined) line.ret = ret;
  const s = JSON.stringify(line);
  console.log("[PROBE] " + s);
  try { openLog(); if (fd) { fd.write(s + "\n"); fd.flush(); } } catch (e) {}
}
function readArgs(ctx, count) {
  const out = [];
  if (!HAS_BLUTTER_HELPERS) {
    for (let i = 0; i < count; i++) out.push("x" + (i + 1) + "=" + ctx["x" + (i + 1)]);
    return out;
  }
  try { init(ctx); } catch (e) {}
  for (let i = 0; i < count; i++) {
    try {
      const [, cls, values] = getTaggedObjectValue(getArg(ctx, i));
      out.push({ cls: cls && cls.name ? cls.name : "?", value: values });
    } catch (e) { out.push({ cls: "?", value: "<decode-fail>" }); }
  }
  return out;
}
function attach(t, side) {
  const addr = base.add(t.rva);
  if (!guardOk(addr, t.guard)) {
    console.log("[GUARD-FAIL] " + side + " " + t.name + " @0x" + t.rva.toString(16) +
      " 实际=" + hexBytes(addr, 4) + "/" + hexBytes(addr.add(8), 4) + " 期望=" + t.guard.join("/") + " —— 跳过");
    return;
  }
  Interceptor.attach(addr, {
    onEnter() { this.__v = readArgs(this.context, t.args); },
    onLeave(rv) {
      let ret;
      if (HAS_BLUTTER_HELPERS) {
        try { const [, cls, values] = getTaggedObjectValue(rv); ret = { cls: cls && cls.name ? cls.name : "?", value: values }; }
        catch (e) { ret = rv.toString(); }
      } else ret = rv.toString();
      record(side, t.name, this.__v, ret);
    }
  });
}
function main() {
  console.log("[probe] base=" + base + " helpers=" + (HAS_BLUTTER_HELPERS ? "blutter" : "raw") + " out=" + CFG_CI.out);
  console.log("[probe] 当前实验号 exp=" + exp + "（REPL 里 setExp(\"E1\") 可切换）");
  REQ.forEach(t => attach(t, "REQ"));
  RES.forEach(t => attach(t, "RES"));
  console.log("[probe] 已挂载 " + (REQ.length + RES.length) + " 个点。");
}
globalThis.setExp = function (e) { exp = e; console.log("[probe] exp -> " + e); };
rpc.exports = { setExp: function (e) { exp = e; return exp; }, getExp: function () { return exp; } };

if (resolveBase()) main();
else { const t = setInterval(() => { if (resolveBase()) { clearInterval(t); main(); } }, 200); }
