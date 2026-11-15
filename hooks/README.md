# 雨课堂测试样本：观测与对照实验手册

样本 `雨课堂.apk` sha256 `bb777dee2d3bb4f313179e4dd30c6bb05592ea650ab26fa7417503b0715b2c61`，libapp.so sha256 `0277169865af6b0dad103f443a236d7111c6dfa88f63ea40c996629d776a1a26`。

## 0. 前提
- 需要一台 root 或可跑 frida-server 的设备；`frida-server` 版本要与 frida-tools 14.13.1 / frida 17.26.3 匹配。
- 只读观测优先：`ykt_hooks.js` 默认不改任何寄存器和内存，只打印。
- 地址纪律：blutter 的 `addr` 就是 libapp.so RVA，运行时 = `Module.findBaseAddress("libapp.so") + RVA`；脚本用「首 4 字节 + 帧大小指令」双重 guard，不匹配就跳过，避免"挂错地址还往下改"。

## 1. 只读观测
```bash
# 一条命令加载两个脚本：blutter_frida.js 提供 Dart 对象解码（getTaggedObjectValue）
frida -U -f com.xuetangx.ykt \
      -l blutter_out/blutter_frida.js \
      -l hooks/ykt_hooks.js --no-pause

# 只盯已启动的进程
frida -U -n 雨课堂 -l blutter_out/blutter_frida.js -l hooks/ykt_hooks.js
```
输出形如：
```
[ykt] libapp.so base = 0x7a3c100000  dart=3.11.5  helpers=blutter
[ENTER][签到] 签到·定位提交 _LocationCheckInPageState::_submit @xdee0b0
      arg0 _LocationCheckInPageState=…  arg1 {lat: …, lng: …}
[LEAVE][签到] 签到·定位提交 _LocationCheckInPageState::_submit -> …
```

## 2. 单变量实验（对应报告 §11）
每条实验只改一个变量，control（原始 APK）与改包各跑一次，留请求/响应原文 + hook 日志。

| 实验 | 变量 | 怎么做 | 判定标准 |
|---|---|---|---|
| A 坐标 | `lat/lng` | 代理层改写 submit body 或 hook 后手动重放 | 服务端回 `isLate:true`/报错 → 服务端复算；照常成功 → 判定权在客户端证据不足 |
| B 迟到 | 本机时钟 | 系统时间前/后移 | UI 放行且服务端记录一致 → 本地判定；不一致 → 服务端判定 |
| C 互评分 | `reviewScore` | 改成满分后回读明细 | 回读等于满分 → 未夹取；被夹到区间/被拒 → 服务端校验 |
| D 作答 | `result / dt` | 同一 `problemId` 重放两次、`dt` 改小 | 第二次被拒/覆盖规则 → 有服务端状态；照收 → 可重放 |
| E 监考 | `action` 码 | 阻断/改写 `/online_proctor/stu/monitor/feed/add` | 服务端有旁路兜底（另发事件/心跳）→ 单点阻断无效 |
| F 弹幕 | `requiredCensor` | 置 false 发敏感词 | 仍被过滤 → 服务端强制；直通 → 开关在客户端 |
| G H5 回参 | `fileUrl/uploader` | 改 `callHomeworkJS` 的参数 | H5 侧接口拒绝/接受，判定作业附件归属校验 |

## 3. 签到取证探针（`ykt_checkin_probe.js`）

把"请求体 → 响应体"整条链路落盘，专门用于判定 §11 的 E0-E4（迟到 / 补签 / 成绩单一致性）：

```bash
frida -U -f com.xuetangx.ykt -l blutter_out/blutter_frida.js -l hooks/ykt_checkin_probe.js --no-pause
# REPL 里按实验号分组：setExp("E1")  或  rpc.exports.setExp("E1")
adb pull /data/local/tmp/ykt_checkin.jsonl
```

挂载点（请求侧 8 个 / 响应侧 5 个，全部带字节级 guard）：

| 侧 | 函数 | RVA | 拿到什么 |
|---|---|---|---|
| REQ | `BaseNet::requestPost` | 0x923178 | 所有 POST 的 url/body/header 实参 |
| REQ | `YuKetang::checkin` | 0xc521fc | 普通签到入参（source=46 写死） |
| REQ | `_ReceiverClassPageState::_postLessonCheckin` | 0xc196cc | 课堂页自动签到（source 由入参传） |
| REQ | `_HmsScanPageState::_postLessonCheckin` | 0xcd042c | 扫码签到（source=42） |
| REQ | `_JoinClassroomDialogState::join` | 0xf9e3ac | 手输入口（44 / web_check_in 46） |
| REQ | `_LocationCheckInPageState::_loadEligibility` | 0xc64f04 | 签到前资格拉取（GET） |
| REQ | `_LocationCheckInPageState::_submit` | 0xdee0b0 | 定位签到提交体 `{lat,lng,lessonId,source=54,address}` |
| RES | `_$JoinLessonBeanFromJson` | 0x114cb3c | 普通/网页签到响应 |
| RES | `_$LocationCheckinSubmitBeanFromJson` | 0x1171334 | 定位签到响应（`isLate/checkInTime`） |
| RES | `_$LocationCheckinEligibilityDataFromJson` | 0x116faa0 | 资格（`canSign/wouldBeLate/pastOfficialEnd/reason`） |
| RES | `_$LocationCheckinOverviewDataFromJson` | 0x1183c14 | 老师端总览（`isLate/time/address/lat/lng`） |
| RES | `_$LessonCheckinBeanFromJson` | 0x116d7bc | 课堂签到身份/角色 |

**guard 约定（已修正）**：guard 存**字节十六进制串**（如 `["fd79bfa9","efe100d1"]`，即 `stp x29,x30,[sp,#-16]!` 与 `sub x15,x15,#imm`），比较时用 `readByteArray` 的原始字节，不再用 `readU32()`（大小端会反，导致全部误报 GUARD-FAIL）。

## 4. 补签 / 迟到 专项实验（E0-E4）

| 编号 | 变量 | 操作 | 判定 |
|---|---|---|---|
| E0 | 对照 | 窗口内正常签 | `checkInTime ∈ [startMs,endMs]`、`isLate=false` |
| E1 | 坐标 | submit 的 `lat/lng` 挪出范围、`address` 保持可信 | 服务端是否复算距离 / 老师端 overview 是否展示坐标 |
| E2 | 入口 | 同 lesson 走 source=42/44/46/54 | 四条入口记录是否等价 |
| E3 | 窗口外但 late 窗内 | 结束后立刻提交 | `isLate/pastOfficialEnd/canSign/reason` 组合 → 补签是否被接受 |
| E4 | 彻底过期 | 超过 `endMs+lateAfterMs` 重放 | `canSign=false` 的 `reason` 值域 |

判读：E3 若返回成功且带 `isLate=true` → "补签成功但老师端能看到迟到与真实时间"；若直接拒 → **客户端没有补签路径**（客户端无"补签"字样，改签接口 `checkin/revise` 无调用点，全在云侧）。

## 5. 产物路径
- 报告：`../report/雨课堂_逆向分析报告.md`
- Frida 脚本：`./ykt_hooks.js`（只读观测，25 个点）、`./ykt_checkin_probe.js`（签到取证，13 个点）
- blutter 产物：`../blutter_out/{asm,pp.txt,objs.txt,blutter_frida.js,ida_script}`
- 字符串/路径：`../so/{app_strings.txt,dartfiles.txt,paths.txt,kwscan.py}`
- 重放/对照：`../replay/checkin_replay.sh`、`../replay/checkin_diff.py`

## 6. 身份绑定实验（B0-B4，见报告 §3.7 / §11）

脚本：`../replay/bind_replay.sh`（模式 `status|school|write|verdict|all`），产物 `../runs/<TAG>-<时间戳>/`。

| 编号 | 端点 | 变量 | 判定 |
| --- | --- | --- | --- |
| B1 | `GET /v/course_meta/user_info` | — | `school`/`school_number` 为空 → 未绑定；客户端只是回显 |
| B2 | `POST /school_name/school_name_query` `{query}` | 学校名 | 必须命中服务端学校库，否则绑定必失败 |
| B3 | `POST /v/course_meta/edit_user_info` `{name,role,school,school_number,email}` | 学校+学号 | 等价于"我的信息"页保存；是否 200 |
| B4 | `POST /api/v3/lesson/checkin` `{inviteCode,source:44,joinIfNotIn:true}` | — | **裁决点**：仍 100038/100030 → 服务端不承认绑定 |

客户端绑定入口（全部只是 WebView 壳）：`/v/index/bindSchool_list`（mine/personal_information_detail/join_classroom_dialog/app_js_call_flutter）、`/static/html/tsinghua_bind.html`（check_code_page::goBindPage 0xaa7f64、wechat::goBindPage 0xc06514）。

若要看运行时值，可挂：`_MyInfoPageState::_postUserInfo` RVA 0xfd37ac（请求侧）、`_SearchInputWidgetState::postSearchSchool` RVA 0xc9054c（请求侧）、`_$UserInfoDetailDataFromJson`（响应侧，解析 `school/school_number`）。

## 7. JS 桥 / H5 URL / Deeplink 探针 `hooks/ykt_bridge_probe.js`

```bash
frida -U -f com.xuetangx.ykt -l ykt_bridge_probe.js --no-pause
# 分组（写进日志的 exp 字段）：rpc.exports.markExp("H1")
# 日志：/data/local/tmp/ykt_bridge.jsonl  每行 {ts, exp, fn, a1, a2, ret}
adb shell "run-as com.xuetangx.ykt cat /data/local/tmp/ykt_bridge.jsonl" 2>/dev/null || adb pull /data/local/tmp/ykt_bridge.jsonl
```

12 个挂点（全部带 Dart AOT prologue guard 双字节校验，版本不符即打印 `[GUARD-FAIL]` 并跳过）：

| 挂点 | RVA | guard | 作用 |
| --- | --- | --- | --- |
| `JsCallFlutter::dispatchAction` | 0xba725c | ef4104d1 | 主 JS 桥入口，a1 = H5 送来的整包 JSON |
| `ShareJsCallFlutter::dispatchAction` | 0xc7de84 | efa102d1 | 分享页桥 |
| `_ExamPageState::dispatch(js)` | 0xc97744 | efe103d1 | 考试页桥（16 action） |
| `_StudyPartnerWebviewState::dispatch` | 0xd5e07c | efc103d1 | 学伴页桥（10 action） |
| `DataUtil::getJournalH5Url` | 0xe953cc | ef8101d1 | 每次打开云侧 H5 生成的 URL（**返回值**已解码） |
| `getWebViewPageWidget` | 0xbd121c | ef8105d1 | 真正打开 WebView 的参数 |
| `JsCallFlutter::getTokenData` | 0xbc5024 | ef6105d1 | OSS 直传凭据 |
| `JsCallFlutter::uploadFile` | 0xbc676c | efc100d1 | 上传回调 |
| `JsCallFlutter::getAliOssConfig` | 0xbc630c | ef8101d1 | ALI OSS 配置（tokenUrl 来自 H5） |
| `JsCallFlutter::postHomeworkDataToJS` | 0xbc6004 | ef0101d1 | 作业回填 |
| `_MyHomePageState::processLinkParams` | 0xc20698 | efc100d1 | deeplink `app://yuketang` 解析 |
| `LogUtils::i` | 0x7da6f4 | ef2100d1 | 判 `LogUtils._debug` 是否开着（开着则 logcat 里就有 `======js调用========` 原文） |

读数要点：`a1`/`a2` 是字符串时直接给出文本；是对象时打印 `<cid=N>`（Dart 类型 id）。**若 `LogUtils._debug` 为 true，直接 `adb logcat | grep "js调用"` 即可拿到同一份 H5 包，不必上 Frida。**

## 8. WebSocket 探针 `hooks/ykt_ws_probe.js`

```bash
frida -U -f com.xuetangx.ykt -l ykt_ws_probe.js --no-pause
# 日志：/data/local/tmp/ykt_ws.jsonl  每行 {ts, dir(IN|OUT|META), fn, op, raw, url}
```

7 个挂点：`WSConnector` 构造 0xc15134 / `connect` 0xc15220 / `send` 0x91e988 / `ReceiverProcesser::process` 0x142515c / `RemoteControlProcesser::process` 0x143a028 / `_tryReconnectAfterDelay` 0xc191f8 / `_teardownChannel` 0xc1905c。
配合 `../replay/ykt_client.py ws`（纯 Python 侧，可注入教师专属 op）可交叉验证"服务端是否按角色过滤"（报告 §13/§19 的 unverified 1-2）。

## 9. 四个探针的分工

| 探针 | 点数 | 覆盖 |
| --- | --- | --- |
| `ykt_hooks.js` | 25 | 四模块全景（签到/作业/成绩/作答 + 监考 + 反作弊） |
| `ykt_checkin_probe.js` | 13 | 签到：请求侧入口与裁决字段 + 响应 bean |
| `ykt_bridge_probe.js` | 12 | H5↔原生桥、H5 URL、deeplink、OSS 直传 |
| `ykt_ws_probe.js` | 7 | WebSocket 双向帧 |
| `ykt_beat_probe.js` | 8 | 学习时长心跳（/mobile-app/video-log/heartbeat/）：组包、本地库、补传、直播与音频通道 |
| `ykt_proctor_probe.js` | 10 | 考试监考/反作弊：七个 action 码上报、分屏监听、抓拍上传、光速虚拟机检测 |