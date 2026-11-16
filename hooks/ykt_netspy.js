// ykt_netspy.js —— 只读：打印 BaseNet requestGet/requestPost 的 URL 实参
// 依赖 blutter_out/blutter_frida_patched.js 先加载（提供 init/getTaggedObjectValue）
// 用法：frida -D emulator-5556 -p PID -l blutter_out/blutter_frida_patched.js -l hooks/ykt_netspy.js -q
var CFG = { module: "libapp.so", out: "/data/data/com.xuetangx.ykt/files/ykt_netspy.log" };

const POINTS = [
  { name: "requestGet", rva: 0x840454, guard: ["fd79bfa9", "efa104d1"] },
  { name: "requestPost", rva: 0x923178, guard: ["fd79bfa9", "ef4105d1"] },
  { name: "requestGetCache", rva: 0x92a58c, guard: ["fd79bfa9", "ef2105d1"] },
  { name: "requestPostCache", rva: 0xbed604, guard: ["fd79bfa9", "ef6104d1"] },
  { name: "createGetUrl", rva: 0x86ec18, guard: ["fd79bfa9", "efe100d1"] },
  { name: "createPostUrl", rva: 0x923784, guard: ["fd79bfa9", "efc100d1"] },
];

function hexBytes(p, n) {
  const b = new Uint8Array(p.readByteArray(n)); let s = "";
  for (let i = 0; i < b.length; i++) s += b[i].toString(16).padStart(2, "0");
  return s;
}

function describe(tptr) {
  try {
    if (!isHeapObject(tptr)) return null;
    const r = getTaggedObjectValue(tptr, 1);
    if (!r) return null;
    const cls = r[1], val = r[2];
    if (cls && /String/.test(cls.name) && typeof val === "string") return { cls: cls.name, val: val };
    if (typeof val === "string") return { cls: cls ? cls.name : "?", val: val };
  } catch (e) {}
  return null;
}

function emit(line) { console.log(line); }

let _tries = 0;
function main() {
  const m = Process.findModuleByName(CFG.module);
  if (!m) {
    if (++_tries > 6000) { emit("[netspy] libapp.so 未加载，放弃"); return; }
    setImmediate(main);   // frida 17 下 setTimeout 不可靠，改用 setImmediate 轮询
    return;
  }
  emit("[netspy] base=" + m.base);
  for (const p of POINTS) {
    const addr = m.base.add(p.rva);
    let ok = false;
    try { ok = hexBytes(addr, 4) === p.guard[0] && hexBytes(addr.add(8), 4) === p.guard[1]; } catch (e) {}
    if (!ok) { emit("[netspy] GUARD-FAIL " + p.name); continue; }
    Interceptor.attach(addr, {
      onEnter: function (ctx) {
        try { init(ctx); } catch (e) {}
        const cands = [];
        for (const reg of ["x1", "x2", "x3", "x4", "x5", "x6", "x7"]) {
          if (!ctx[reg]) continue;
          const d = describe(ctx[reg]);
          if (d) cands.push(reg + "=" + JSON.stringify(d.val).slice(0, 300));
        }
        emit("[" + p.name + "] " + cands.join(" | "));
      }
    });
    emit("[netspy] hooked " + p.name + " @" + p.rva.toString(16));
  }
}
main();
