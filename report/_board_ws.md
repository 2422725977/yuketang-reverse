# 雨课堂 WebSocket 协议逆向（板块报告）

> 证据口径：每条标注 **observed**（asm 直接读到）/ **inferred**（由 observed 推导）/ **unverified**（需运行期实验）。
> 地址均为 libapp.so 的 RVA（该样本 .text 段 vaddr == 文件偏移，见 \`report/雨课堂_逆向分析报告.md\` §9）。
> 运行时地址 = \`Process.findModuleByName("libapp.so").base + RVA\`。

## 1. 代码位置

| 角色 | 文件 | 说明 |
|---|---|---|
| 连接/收发 | \`blutter_out/asm/rain/websocket/ws_connector.dart\`（6683 行） | \`WSConnector\` 全部收发方法 |
| 分派基类 | \`.../processer/ws_message_processer.dart\`（221 B） | \`ReceiverProcesser extends Object implements WSMessageProcesser\`（observed，文件头 class 注释） |
| 学生侧分派 | \`.../processer/receiver_processer.dart\`（242925 B，1 个函数） | \`ReceiverProcesser::process\` RVA 0x142515c size 0x312c |
| 教师侧分派 | \`.../processer/remote_control_processer.dart\`（179632 B，1 个函数） | \`RemoteControlProcesser::process\` RVA 0x143a028 size 0x2400 |
| 载荷模型 | \`blutter_out/asm/rain/model/wss_operation_model.dart\`（1546384 B） | 103 个 \`XxxOp/XxxBean.fromMap/fromJson\` |

## 2. 端点与握手（**observed**）

\`\`\`dart
// rain/core/app_constants.dart
static String baseUrlHost() {           // RVA 0x86f184 size 0x38
  // 环境位（static field offset 0xd14）为真 → "ykt-envning.rainclassroom.com"（测试）
  // 否则                      → "www.yuketang.cn"（生产）
}
static String baseUrl()     { "https://" + baseUrlHost }               // RVA 0x86f108 size 0x7c
static String wssUrl()      { "wss://"   + baseUrlHost + "/wsapp/" }   // RVA 0xc19644 size 0x88
\`\`\`

**结论**：WebSocket 端点 = \`wss://www.yuketang.cn/wsapp/\`（生产）。字面量池：\`"wss://"\` pp+0xe9b8、\`"/wsapp/"\` pp+0xe9c0、\`"www.yuketang.cn"\` pp+0xa758、\`"ykt-envning.rainclassroom.com"\` pp+0xa758 邻位。

握手只有 **一个自定义 header**（**observed**，\`WSConnector::connect\` 0xc15220 size 0x28c）：

\`\`\`dart
// 0xc15318 "User-Agent"；0xc15344 "Android-pad" / 0xc15350 "Android-mobile"（按 Device.get() 分支）
// 0xc15390 Map._fromLiteral({ "User-Agent": <pad|mobile> })
// 0xc153a4 IOWebSocketChannel.connect(url, headers: <map>, ...)
\`\`\`

- **握手不带 Cookie / Token / csrf / 自定义签名头** → 连接本身匿名；身份靠连接后的首条 \`hello\` 消息（**observed**）。
- 连接成功后 \`EventBus::fire(SocketConnectSuccess)\`（0xc153ec / 0xc153f8），三个流回调：
  - onData 闭包 **0xc194e0**：读 \`conn.field_b\`（processer），\`conn.field_13 != 0\` 时**直接丢包**（暂停标志，见 §5）→ 动态派发 \`process(payload)\`
  - onError 闭包 **0xc190e4**：打印 \`"=============WS onError:"\` → \`_scheduleReconnect\`
  - onDone 闭包 **0xc19458**：→ \`_scheduleReconnect\`

## 3. 连接建立链路（学生端）

| 调用点 | RVA | 说明（observed） |
|---|---|---|
| \`_ReceiverClassPageState::_connectSocket\` | **0xc15048** size 0xec | 打印 \`"****_connectSocket******"\`；取全局静态 \`wssUrl\`（\`static late String wssUrl\`，offset 0xd28）；\`ReceiverProcesser()\`（0xc195a0）→ 闭包 0xc195ac → \`WSConnector(url, …)\`（0xc15134）；存 \`this.field_37\` |
| \`_ReceiverClassPageState::_reConnectSocket\` | **0xd3bfd0** size 0x138（async） | 同构，闭包 0xd3c108，重连时重建连接器 |
| \`WSConnector::WSConnector\` | 0xc15134 size 0xec | 校验 \`url.startsWith(...)\`（0xc151e0）后立即 \`connect()\`（0xc15204） |
| 教师端构造点 | \`remote_control/remote_control_tab_page.dart:835\`（0xc50144） | 同 3 参构造 |

## 4. 发送路径（**observed**）

\`WSConnector::send\` **RVA 0x91e988 size 0x100**：
1. 打印 \`"=============WS send: " + content\`；
2. \`channel.field_f\`（\`_CompleterSink\`）\`add(content)\`（0x91ea68 → \`_CompleterSink::add\` 0x9550bc）。

各业务方法（如 \`sendDetectLesson\` 0xc50218）先 \`Map\` + \`JsonCodec::encode\`（0xc502b8）再 \`send\`。→ **线上帧 = 明文 JSON 文本**（observed）。

## 5. 消息信封与暂停开关

- 信封固定键：\`op\`（动作）、\`lessonid\`（课堂）、可选 \`msgid\`（回执/次序，多处硬编码 \`"1234"\`）；计数：\`"op"\` 与 \`"lessonid"\` 在 ws_connector.dart 各出现 **49** 次（observed）。
- 回执字段 \`isReply\`：\`WssNavtoslideOp / WssShowGroupEventOp / WssCloseMaskOp / WssSlidenowOp\` 等模型含 \`isReply\`（observed）。
- 暂停/恢复：\`pauseProcessing\` 0xc534c0（写 \`field_13\`）/ \`resumeProcessing\` 0xfade34；暂停期间 onData 闭包直接 return（**observed**，0xc19520 \`cbnz x1\` 分支）。

## 6. 出站 op 全表（**observed**，\`tools/ws_lits.py\` 逐函数提取）

| 方法 | RVA | op | 附带键 |
|---|---|---|---|
| sendLeaveLesson | 0x91e8c0 | leavelesson | lessonid |
| sendHelloFromStudent | 0x929dd0 | hello | userid, role=student, auth, lessonid |
| sendRequestProbleminfo | 0x933f00 | probleminfo | lessonid, problemid, msgid |
| acceptvc | 0xbe93d4 | acceptvc | lessonid |
| rejectvc | 0xbe9550 | rejectvc | lessonid |
| sendFetchTimeline | 0xc0a3f0 | fetchtimeline | lessonid |
| sendDetectLesson | 0xc50218 | detectlesson | lessonid |
| sendEndshow | 0xc54188 | endshow | presentation |
| sendShowfinished | 0xc54268 | showfinished | presentation, title |
| jumpinwakeup | 0xc567b4 | jumpinwakeup | lessonid |
| jumpinwokeup | 0xc56cb4 | jumpinwokeup | sc |
| slidenav | 0xc58fd0 | slidenav | presentation, slideid, to, step, total, im |
| sendHelloFromTeacher | 0xc5e6c4 | hello | userid, role=lecturer, lessonid, avatar, auth |
| sendWakelesson | 0xc5f2a8 | wakelesson | title, clone, role |
| sendTryZoomQrcode | 0xd02ec0 | tryzoomqrcode | qrcode |
| endvc | 0xd27f08 | endvc | — |
| cancelvc | 0xd28bf0 | cancelvc | — |
| teacherHideDanmu | 0xd3db8c | closemask | danmu |
| teacherShowDanmu | 0xd3dda0 | showdanmu | — |
| calledlist | 0xd4cca0 | calledlist | page, size |
| callwakeup | 0xd4cd90 | callwakeup | — |
| callwokeup | 0xd4d060 | callwokeup | msgid, sc |
| callpaused | 0xd4da00 | callpaused | uid, dt, msgid |
| sendPresentationCreated | 0xdddde0 | presentationcreated | presentation, datacompleted, clone |
| closeJumpin | 0xe524dc | closemask | type=jumpin |
| sendVideocontrol | 0xea3514 | videocontrol | pptsahapeid, pres, sid, status, change |
| sendPageTurn | 0xea3f8c | next / prev | presentation, msgid |
| sendDepriveRemote | 0xfadd6c | depriveremote | — |
| requestvc | 0x1026064 | requestvc | uid, name, avatar |
| sendCloseRemarkMask | 0x10711bc | closemask | msgid=1234, type=remark |
| closeWordCloud | 0x1072848 | closemask | wordcloud |
| showWordCloud | 0x10728e0 | showwordcloud | danmu |
| teacherTurnOffDanmu | 0x1072b8c | turnoffdanmu | event=DANMU_OFF |
| teacherTurnOnDanmu | 0x1072cbc | turnondanmu | event=DANMU_ON |
| sendShowExams | 0x1073d68 | postquizresult | quizid |
| sendCloseShowExams | 0x1073e48 | closequizresult | quizid |
| sendGroupDiscussScreen | 0x108e048 | showgroupevent | eventid, teamid, msgid |
| sendGroupCloseMask | 0x108e198 | closemask | type=groupevent, eventid, teamid, msgid |
| callpause | 0x109936c | callpause | type=call, msgid |
| callstart | 0x1099464 | callstart | type=call, msgid |
| callstarted | 0x1099550 | callstarted | msgid |
| closeDraftCastScreen | 0x109b120 | closemask | type=post, msgid |
| sendWholeClass | 0x109b448 | sendpost | postid, msgid |
| showDraftWordCloud | 0x109bf0c | showwordcloud | post |
| sendScreenCast | 0x10a862c | blankIndex/closeproblemresult/postproblemresult/showresult/blank | problemid |
| sendShowsproblem | 0x10adddc | showsproblem | msgid=1234, spid |
| sendShowsGroupproblem | 0x10aded4 | showsproblem | spid, teamid, resultindex |
| sendClosemask | 0x10ae8b4 | closemask | type=subjective |
| sendSendsproblem | 0x10aebb4 | sendsproblem | spid, pid |
| navtoslide | 0x10c54e4 | navtoslide | presentation, to |
| closedmask | 0x10fd33c | closedmask | type=jumpin, msgid |
| showpresentation | 0x1108938 | showpresentation | presentation, slideid, slideindex, step, total, title |
| sendTryShowPresentation | 0x1108a90 | tryshowpresentation | — |
| closeNaming | 0x110b888 | closemask | type=call |
| sendSendremark | 0x11d4dd4 | sendremark | prob, pres, sid |
| sendShowproblemremark | 0x11d5078 | showproblemremark | msgid=1234, prob |

发出者分布（**observed**，\`WSConnector::send\` 被 57 处调用；调用最密的文件）：
\`remote_control/danmu/remote_danmu.dart\`(1)、\`remote_control_tab_page.dart\`(多条)、\`receiver_page/receiver_class_page.dart\`（学生：hello/leave/acceptvc/rejectvc/fetchtimeline）、\`kuaishou/widgets/ks_connect_state_widget.dart\`（endvc/cancelvc/requestvc）。

## 7. 入站分派（**observed**）

\`ReceiverProcesser::process(payload)\` 0x142515c：
1. \`print("========接收器数据:" + payload)\`（0x1425188）；
2. \`JsonCodec::decode(payload)\`（0x14251d0）→ \`IsType_Map\` 断言（0x14251f0）；
3. \`map["op"]\` 取值（0x1425204）→ 与字面量逐一比较 → 构造对应模型 \`XxxOp.fromMap(map)\` → \`EventBus::fire(事件对象)\`。

教师端 \`RemoteControlProcesser::process\` 0x143a028 同构，首行打印 \`"========遥控器，接收到数据:"\`。

**→ 客户端对入站帧不做任何签名/完整性校验、不校验发送者身份**（observed；服务端是否按角色过滤属于 **unverified**，需运行期实验）。

### 7.1 学生侧（ReceiverProcesser，86 个 op；op → 模型 → EventBus 事件类）

\`hello\`→HelloOp | \`showfinished\`→MessageEventOp | \`slidenav\`→WssSlidenavOp | \`unlockproblem\`→WssUnlockProblemOp | \`probleminfo\`→WssProbleminfoOp | \`extendtime\`→WssExtenttimeOp | \`sproblemshown\`→WssSproblemshownOp | \`sendsproblem\`→WssSendsproblemOp | \`redpacket\`→WssRedpacketOp | \`closedmask\`→WssCloseMaskOp | \`problemremark\`→WssProblemrearkOp | \`remotedeprived\`→WssRemoteDeprivedOp | \`launchgroup\`→WssReceiverGroup | \`newdanmu\`→WssNewDanmu | \`turnondanmu\`→DanmuOnOp | \`turnoffdanmu\`→DanmuOffOp | \`danmushown\`→(本地) | \`wordcloudshown\`→ProductWordCloudBean | \`touchdata\`→WhiteBoardBean | \`boardclear\`→WhiteBoardClearBean | \`newboard\`→WhiteBoardCreateBean | \`shareboard\`→WhiteBoardShareBean | \`boardnav\`→WhiteBoardNavBean | \`boardclose\`→WhiteBoardCloseBean | \`showpresentation\`→WssShowPresentationOp | \`presentationupdated\`→WssPresentationUpdatedOp | \`fetchtimeline\`→HelloOp | \`startlive\`→WssStartLiveOp | \`livestatus\`→WssLiveStatus | \`endlive\`→WssEndLive | \`lessonfinished\`/\`quizfinished\`/\`paperfinished\`/\`callpaused\`→MessageEventOp | \`newquiz\`→WssNewQuiz | \`newpaper\`→WssNewPaper | \`sendpost\`→WssSendPost | \`sendcapture\`→WssSendCapture | \`cancelgroup\`→WssCancelGroup | \`launchreview\`→WssLaunchReview | \`problemfinished\`→WssProblemFinishedOp | \`userjoin\`/\`userleave\`/\`changedevice\`→Meeting*Bean | \`startinteractive\`→WssStartInteractive | \`endinteractive\`→WssEndInteractive | \`sharescreen\`→WssShareScreen | \`endsharescreen\`→WssEndShareScreen | \`controldevice\`→WssAllMute | \`bandevice\`→WssBanDevice | \`openaudio\`→WssOpenAudio | \`starttencentinteractive\`/\`endtencentinteractive\`→WssStart/EndTencentMeet | \`creatertc\`→Creatertc | \`requestvc\`/\`cancelvc\`/\`acceptvc\`/\`rejectvc\`/\`vctimeout\`/\`endvc\`/\`rtcroomfull\`/\`canrequestvc\`/\`leavevc\`→同名模型 | \`mute\`→KsMute | \`unmute\`→KsUnMute | \`sendinstr\`→WssInstruction | \`instrfinished\`→InstructionFinished | \`companion\`→WssCompanion | \`notification\`→WssNotification | \`sendagent\`→WssSendagent | \`agentfinished\`→WssAgentFinished | \`sendagentnew\`→WssNewagent | \`jumpinstart\`/\`jumpinend\`→Jumpin*Op | \`groupevent\`→WssGroupEvent | \`gefinished\`→WssGroupEventFinished | \`geext\`→WssGroupEventExtend | \`geshare\`→WssGeShare | \`locationcheckinext\`→WssLocationCheckinExt | \`locationcheckinend\`→WssLocationCheckinEnd | \`groupanswerupdate\`→WssGroupAnswerUpdate | \`groupresult\`→WssGroupResult | \`aisummary\`→WssAiSummary | \`groupchat\`→WssGroupChat | \`sendaitool\`→WssSendAITool

### 7.2 教师侧（RemoteControlProcesser，62 个 op）独有

\`detectlesson\`→DetectLessonBean | \`addinnews\`→AddinNewsBean | \`navtoslide\`→WssNavtoslideOp | \`showsproblem\` | \`showproblemremark\`→WssShowproblemremarkOp | \`rollcall\`→WssRemoteRollcallOp | \`calledlist\`→NamedListBean | \`callwokeup\`→NamedCountBean | \`callpause\`→NamingPausedBean | \`callstarted\`→NamingStartedBean | \`presentationcreated\` | \`depriveremote\` | \`tryzoomqrcode\`→TryzoomQrcodeOp | \`postshown\`→WssPostShown | \`unreadpost\`→WssUnreadPost | \`jumpinwokeup\` | \`signin\`→**WssLocationCheckinSignin** | \`showgroupevent\`→WssShowGroupEventOp | \`closemask\`

## 8. 载荷 schema 抽样（**observed**，\`rain/model/wss_operation_model.dart\` 逐 ctor 提取）

| 模型 | 键 |
|---|---|
| WssLocationCheckinSignin | uid, name, avatar, total, lat, lng, **isLate**, dt |
| WssLocationCheckinExt | op, lessonid, changeKind, version, serverTime, startMs, endMs, lateAfterMs, extend, radiusM, centerLat, centerLng |
| WssLocationCheckinEnd | op, lessonid, endMs, endedAt, version, serverTime |
| WssSendsproblemOp | op, msgid, lessonid, to, problem（problem: type,cat,spid,pid,anon,dt） |
| WssUnlockProblemOp | op, lessonid, problem, unlockedproblem |
| WssProbleminfoOp | op, msgid, lessonid, problemid, dt, limit, now |
| WssExtenttimeOp | op, lessonid, problem（problem 含 extend, now, limit） |
| WssShowPresentationOp / WssSlidenavOp | op, lessonid, presentation/slide, to, step, total, danmu, shownow, isReply |
| WssNewQuiz / WssNewPaper | op, lessonid, quiz / paper（quiz: type,title,quiz,paperid,total,dt） |
| WssRemoteRollcallOp | op, range |
| WssSendPost | op, msgid, lessonid, to, post（post: type,cat,postid,anon,dt） |
| WssLaunchReview | op, lessonid, review（type,sid,prob,reviewid,dt） |
| WssNotification / WssCompanion / WssNewagent / WssSendAITool / WssInstruction | op, lessonid, contents/it/… |
| HelloOp | op, msgid, lessonid, liveid, livestatus, livevoice, isAlive, state, message, shownow, addinversion, mask, rtc, presentation |

## 9. 与四大功能区的交叉点

- **签到**：学生只收到 \`locationcheckinext\` / \`locationcheckinend\`（签到窗口开/关），**不含**个人签到结果；教师端收到 \`signin\` 推送（\`WssLocationCheckinSignin\`，含 **isLate / lat / lng / dt**），消费点 \`rain/remote_control/page/location/location_sign_page.dart:9445\` 的闭包 \`(dynamic, WssLocationCheckinSignin)\` 与 \`remote_course_dynamic_page.dart:1764\`（observed）。→ 再次印证报告 §3.6：迟到/坐标是**服务端实时推送给教师的**，客户端无处篡改。
- **作业**：\`sendpost\`/\`postshown\`/\`unreadpost\`（投稿与已读）、\`launchreview\`（互评开启）、\`sendcapture\`（截图上报）、\`problemfinished\`。
- **成绩/考试**：\`newquiz\`/\`newpaper\`（题目/试卷下发）、\`quizfinished\`/\`paperfinished\`（交卷结束）、\`sendShowExams\`/\`sendCloseShowExams\`（教师端 \`postquizresult\`/\`closequizresult\` 展示成绩）。
- **课堂作答**：\`sendsproblem\`（下发题目）、\`sproblemshown\`（公布）、\`probleminfo\`、\`extendtime\`、\`unlockproblem\`、\`sendremark\`/\`showproblemremark\`（批注）、\`redpacket\`（抢答红包）、\`rollcall\`/\`calledlist\`/\`callwakeup\`（随机点名）。

## 10. 协议层安全观察

1. **握手无鉴权头**（observed）+ 首帧 \`hello\` 携带 \`auth\` → 身份建立完全依赖该帧（unverified：服务端是否校验 \`userid\` 与 \`auth\` 一致、是否按 role 过滤 op）。
2. **无签名 / 无 MAC / 无时间戳防重放**（observed）；帧为明文 JSON，客户端仅按 \`op\` 字符串分派。
3. **入站不做身份与来源校验**（observed）：任何能把帧写进本地连接的对端都能触发完整 UI 行为（白板、题目公布、弹幕、点名、成绩展示）。
4. **重连窗口**：错误/完成 → \`_scheduleReconnect\`（0xc19190）→ \`_tryReconnectAfterDelay\`（0xc191f8，\`Duration(1000000µs)\` = **1 秒**定时器，observed），断线重连不带退避抖动。
5. 暂停开关（\`field_13\`）仅影响**本地处理**，不影响服务端投递（observed/inferred）。

## 11. 工具与复现

\`\`\`bash
# 静态：逐函数提取 op 字面量 / 入站分派表
python3 tools/ws_lits.py      # ws_connector.dart → 方法/op/键
python3 tools/ws_inbound.py   # 两个 process → op → 模型类
python3 tools/ws_inbound2.py  # op → Allocate*Stub → EventBus 事件类
python3 tools/ws_model.py     # wss_operation_model.dart → 每模型键顺序
python3 tools/ws_callers.py   # WSConnector 各方法调用点
python3 tools/ws_url.py       # wssUrl 定义/使用点
python3 tools/ws_guard.py     # 各挂点前 12 字节 + Frida guard 字节对

# 动态：一条命令抓全双工 WS 帧
frida -U -f com.xuetangx.ykt -l hooks/ykt_ws_probe.js --no-pause
# → /data/local/tmp/ykt_ws.jsonl 每行 {ts,dir(IN|OUT|META),fn,op,raw,url}
\`\`\`

Frida 挂点与 guard（libapp.so 文件字节，前 4 字节恒为 \`fd79bfa9\`）：

| 挂点 | RVA | guard[1]（+8 帧指令） |
|---|---|---|
| WSConnector::WSConnector | 0xc15134 | ef2100d1 |
| WSConnector::connect | 0xc15220 | efe100d1 |
| WSConnector::send | 0x91e988 | ef6100d1 |
| ReceiverProcesser::process | 0x142515c | ef8100d1 |
| RemoteControlProcesser::process | 0x143a028 | efa100d1 |
| _tryReconnectAfterDelay | 0xc191f8 | ef8100d1 |
| _teardownChannel | 0xc1905c | ef6101d1 |

## 12. 待验证（unverified，需运行期实验）

1. 服务端是否校验 \`hello.auth\` 与 \`userid\` 绑定；跨账号冒用是否被拒。
2. 学生连接注入教师专属 op（如 \`sendpost\`/\`launchreview\`/\`showpresentation\`）是否生效 —— 用 \`ykt_ws_probe.js\` 记录基线后，用自定义客户端重放。
3. \`signin\` 推送的 \`dt\`/\`isLate\` 与服务端 checkin 记录一致性（同 §3.6 的 E 组实验合并跑）。
4. 重连 1 秒定时器是否造成服务端会话风暴（抓服务端行为）。
