/*
 * ykt_hooks.js — 雨课堂 APK 本地测试样本 Frida 观测脚本（只读观测，默认不改数据）
 *
 * 样本: 雨课堂.apk  sha256 bb777dee2d3bb4f313179e4dd30c6bb05592ea650ab26fa7417503b0715b2c61
 * 包名: com.xuetangx.ykt   versionName 1.3.6   versionCode 1900
 * 目标: libapp.so (Dart AOT)  sha256 0277169865af6b0dad103f443a236d7111c6dfa88f63ea40c996629d776a1a26
 *        Dart 3.11.5  snapshot 78da37fed6bf1489361a312568249f3f  android arm64  product
 * 地址: blutter 反汇编里的 addr 就是 libapp.so 的 RVA（.text vaddr=0x760000 与文件偏移恒等），
 *       运行时地址 = Process.findModuleByName("libapp.so").base.add(RVA)
 *
 * 用法（两条脚本一起加载，blutter_frida.js 提供 Dart 对象解码器 getTaggedObjectValue/getArg/init）:
 *   frida -U -f com.xuetangx.ykt -l blutter_out/blutter_frida.js -l hooks/ykt_hooks.js --no-pause
 *   frida -U -n 雨课堂        -l blutter_out/blutter_frida.js -l hooks/ykt_hooks.js
 *
 * 纪律：attach 之前先校验每个函数的前 12 字节（首 4 字节 + 帧大小指令）。校验不过就跳过该函数并告警，
 *       绝不"猜地址硬挂"（地址错=诊断错，而不是继续打补丁）。
 *       guard 用字节十六进制字符串比较（readByteArray 原始顺序），不用 readU32()，避免大小端歧义。
 */

const CFG = {
  module: "libapp.so",
  expectDartVersion: "3.11.5",
  silent: false,
};

/* name / RVA / guard: ["函数首 4 字节", "第 3 条指令(sub x15,x15,#imm) 4 字节"]，均为 libapp.so 文件字节顺序 */
const TARGETS = [
  { name: "签到·课堂签到 YuKetang::checkin",                  rva: 0xc521fc,  guard: ["fd79bfa9", "efe100d1"], args: 2, mod: "签到" },
  { name: "签到·列表 YuKetang::fetchCheckinList",              rva: 0xc5687c,  guard: ["fd79bfa9", "efe100d1"], args: 2, mod: "签到" },
  { name: "签到·定位提交 _LocationCheckInPageState::_submit",  rva: 0xdee0b0,  guard: ["fd79bfa9", "efa101d1"], args: 2, mod: "签到" },
  { name: "签到·范围重算 _updateRangeState",                    rva: 0xc62da8,  guard: ["fd79bfa9", "efa100d1"], args: 3, mod: "签到" },
  { name: "签到·资格拉取 _loadEligibility",                     rva: 0xc64f04,  guard: ["fd79bfa9", "ef6101d1"], args: 2, mod: "签到" },
  { name: "签到·范围预览 _fetchRangePreview",                   rva: 0xc62e20,  guard: ["fd79bfa9", "efc101d1"], args: 3, mod: "签到" },
  { name: "签到·WS 延长 _onLocationCheckinExt",                 rva: 0xc627fc,  guard: ["fd79bfa9", "ef0101d1"], args: 2, mod: "签到" },
  { name: "签到·WS 结束 _onLocationCheckinEnd",                 rva: 0xc61da4,  guard: ["fd79bfa9", "efe100d1"], args: 2, mod: "签到" },
  { name: "签到·课堂页上报 _ReceiverClassPageState::_postLessonCheckin", rva: 0xc196cc, guard: ["fd79bfa9", "ef6101d1"], args: 3, mod: "签到" },
  { name: "签到·扫码上报 _HmsScanPageState::_postLessonCheckin", rva: 0xcd042c, guard: ["fd79bfa9", "ef6101d1"], args: 3, mod: "签到" },
  { name: "签到·手输入口 _JoinClassroomDialogState::join",      rva: 0xf9e3ac,  guard: ["fd79bfa9", "efc101d1"], args: 3, mod: "签到" },

  { name: "作答·单选提交 _SingleChoiceQuestionPageState::_submitAnswer", rva: 0xdf5a34, guard: ["fd79bfa9", "ef6101d1"], args: 3, mod: "作答" },
  { name: "作答·主观题提交 _SubjectiveQuestionPageState::_submit",        rva: 0xe0164c, guard: ["fd79bfa9", "ef6101d1"], args: 3, mod: "作答" },
  { name: "作答·抢答提交 _ReceiverClassPageState::_submitRapidAnswer",    rva: 0xbd9088, guard: ["fd79bfa9", "ef6101d1"], args: 4, mod: "作答" },
  { name: "作答·弹幕 YuKetang::sendDanmu",                 rva: 0xd7ccdc,  guard: ["fd79bfa9", "ef0101d1"], args: 11, mod: "作答" },
  { name: "作答·答案详情 YuKetang::getLessonProblemRemark(/problem/fetch-answer)", rva: null, guard: null, args: 2, mod: "作答" },

  { name: "成绩·教师给分详情 YuKetang::scoreDetail",       rva: 0xd59ed0,  guard: ["fd79bfa9", "ef6101d1"], args: 4, mod: "成绩" },
  { name: "成绩·教师给分/互评 YuKetang::giveHupingScore",  rva: 0x10c0acc, guard: ["fd79bfa9", "efc101d1"], args: 6, mod: "成绩" },
  { name: "成绩·学生互评提交 _ScoreEachOtherPageState::_submitScore", rva: 0x1041308, guard: ["fd79bfa9", "ef8101d1"], args: 6, mod: "成绩" },

  { name: "作业·H5 桥 dispatchAction",                     rva: 0xba725c,  guard: ["fd79bfa9", "ef4104d1"], args: 3, mod: "作业" },
  { name: "作业·原生回调 H5 postHomeworkDataToJS",         rva: 0xbc6004,  guard: ["fd79bfa9", "ef0101d1"], args: 3, mod: "作业" },
  { name: "作业·打开作业文件 openHomeworkFile",            rva: 0xbd3814,  guard: ["fd79bfa9", "ef8101d1"], args: 5, mod: "作业" },

  { name: "反作弊·考试上报 ExamPage::reprotExam",          rva: 0x93d76c,  guard: ["fd79bfa9", "ef8101d1"], args: 3, mod: "反作弊" },
  { name: "反作弊·上报并弹提示 reprotExamShowToast",       rva: 0x93dce4,  guard: ["fd79bfa9", "efa101d1"], args: 3, mod: "反作弊" },

  { name: "网络·统一 POST 出口 BaseNet::requestPost",      rva: 0x923178,  guard: ["fd79bfa9", "ef4105d1"], args: 8, mod: "网络" },
  { name: "网络·统一加头 BaseNet::addHeader",              rva: 0xbde930,  guard: ["fd79bfa9", "ef8100d1"], args: 2, mod: "网络" },
];

const HAS_BLUTTER_HELPERS = (typeof getTaggedObjectValue === "function") && (typeof getArg === "function");
let base = null;

function resolveBase() {
  const _m = Process.findModuleByName(CFG.module); base = _m ? _m.base : null;
  return base;
}

function hexBytes(addr, n) {
  const b = new Uint8Array(addr.readByteArray(n));
  // guard 与 libapp.so 文件字节同序（readByteArray 原始顺序），勿倒序
  let s = "";
  for (let i = 0; i < b.length; i++) s += b[i].toString(16).padStart(2, "0");
  return s;
}

function guardOk(addr, guard) {
  if (!guard) return true;
  try {
    return hexBytes(addr, 4) === guard[0] && hexBytes(addr.add(8), 4) === guard[1];
  } catch (e) { return false; }
}

function dumpArgs(ctx, count) {
  const out = [];
  if (!HAS_BLUTTER_HELPERS) {
    for (let i = 0; i < count; i++) out.push("x" + (i + 1) + "=" + ctx["x" + (i + 1)]);
    return out.join(" ");
  }
  try { init(ctx); } catch (e) {}
  for (let i = 0; i < count; i++) {
    try {
      const [tptr, cls, values] = getTaggedObjectValue(getArg(ctx, i));
      out.push("arg" + i + " " + (cls && cls.name ? cls.name : "?") + "=" + JSON.stringify(values));
    } catch (e) { out.push("arg" + i + "=?"); }
  }
  return out.join("\n      ");
}

function attachOne(t) {
  if (t.rva == null) return;
  let addr;
  try { addr = base.add(t.rva); } catch (e) { console.log("[skip] " + t.name + " bad rva"); return; }
  if (!guardOk(addr, t.guard)) {
    console.log("[GUARD-FAIL] " + t.name + " @base+0x" + t.rva.toString(16) +
      "  实际: " + hexBytes(addr, 4) + ", " + hexBytes(addr.add(8), 4) +
      "  期望: " + (t.guard ? t.guard.join(", ") : "-") +
      " —— 版本/地址不符，跳过硬挂");
    return;
  }
  Interceptor.attach(addr, {
    onEnter() {
      const ctx = this.context;
      console.log("[ENTER][" + t.mod + "] " + t.name + " @x" + ctx.pc.sub(base).toString(16) +
        "\n      " + dumpArgs(ctx, t.args));
    },
    onLeave(retval) {
      if (CFG.silent) return;
      let r = retval.toString();
      if (HAS_BLUTTER_HELPERS) {
        try {
          const [tptr, cls, values] = getTaggedObjectValue(retval);
          r = (cls && cls.name ? cls.name : "?") + "=" + JSON.stringify(values);
        } catch (e) {}
      }
      console.log("[LEAVE][" + t.mod + "] " + t.name + " -> " + r);
    }
  });
}

function main() {
  if (!resolveBase()) { console.log("[ERR] " + CFG.module + " 未加载，改名/加固后请先确认模块名"); return; }
  console.log("[ykt] " + CFG.module + " base = " + base + "  dart=" + CFG.expectDartVersion +
    "  helpers=" + (HAS_BLUTTER_HELPERS ? "blutter" : "raw(仅打印寄存器)"));
  TARGETS.forEach(attachOne);
  console.log("[ykt] 已挂载 " + TARGETS.filter(t => t.rva != null).length + " 个观测点。");
}

if (resolveBase()) main();
else {
  const t = setInterval(() => { if (resolveBase()) { clearInterval(t); main(); } }, 200);
}
