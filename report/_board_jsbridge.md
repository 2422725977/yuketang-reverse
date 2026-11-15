# 板块：H5 ↔ 原生 JS 桥全表（雨课堂 APK / Flutter Dart AOT）

样本：`so/lib/arm64-v8a/libapp.so`（注释反汇编 `blutter_out/asm/**`，函数头 "** addr: 0x…" 即 RVA）。
证据格式：`文件:行号` 或 `RVA 0x…` 或 `字符串偏移 0x…`。标注：**observed** = 反汇编直接可见；**inferred** = 由调用关系推断；**unverified** = 未复核。
所有 §2 行号均指 `blutter_out/asm/rain/ui_widget/app_js_call_flutter.dart`；§3/§4 各自标注文件。

## 0. 结论速览（observed）

| # | 事实 | 证据 |
|---|---|---|
| 1 | 桥对象名唯一为 `"JsCallFlutter"`（pp+0x31238），全 app 共 **6 处**注册；另有并列通道 `"enterExamPage"`（pp+0x49548，仅 exam_page） | `blutter_out/pp.txt`；`rain/ui_widget/app_js_call_flutter.dart:301` 入口日志 `"======js调用========"` |
| 2 | 全 app 有 **4 个独立派发器**（同名 `dispatchAction`，均为内联 if 链，用 `_OneByteString::==` 0x13a5b84 比较）：主派发器 **39** action、ShareJsCallFlutter **8**、_ExamPageState **16**、_StudyPartnerWebviewState **10** | `rain/ui_widget/app_js_call_flutter.dart:279`(0xba725c) / `rain/home/course/share_webview_page.dart:161`(0xc7de84) / `rain/receiver_page/exam_page.dart:8429`(0xc97744) / `rain/ui_widget/study_partner_webview.dart:495`(0xd5e07c) |
| 3 | action 名与其入参 `data` 全部来自 H5 传入的 JSON 串，原生只做「键存在 + 可空类型」检查，**无签名、无来源、无一次性 token 校验** | `app_js_call_flutter.dart:362` JsBean.fromJson(0xbd4a28) → 分支内 IsType_String?/IsType_int?/IsType_bool?（如 :382–:505） |

## 1. 桥对象名与注入点（observed）

注册 API：`WebViewController::addJavaScriptChannel`（实现 0xb9c50c，声明处 `webview_flutter/src/webview_controller.dart:160`）。

| 通道名 | 字符串偏移 | 注册文件:行（RVA） | onMessage 闭包 | 闭包→派发器 |
|---|---|---|---|---|
| JsCallFlutter | pp+0x31238 | `xuetang_webview/xuetang_webview.dart:1399,1402-1403`（initState 0xb992e0） | 0xba71ec（该文件 :1701，:1734 调用） | JsCallFlutter::dispatchAction **0xba725c** |
| JsCallFlutter | pp+0x31238 | `rain/home/teach_journal/classroomlog_h5_page.dart:730,733-734`（initState 0xc7f060） | 复用上行的 0xba71ec（:723-724 `AnonymousClosure: (0xba71ec), in [package:xuetang_webview/…]`） | 同上 0xba725c |
| JsCallFlutter | pp+0x31238 | `rain/home/course/share_webview_page.dart:2011,2014-2015`（initState 0xc7d9d8） | 0xc7de14（同文件 :2155） | ShareJsCallFlutter::dispatchAction **0xc7de84** |
| JsCallFlutter | pp+0x31238 | `rain/receiver_page/exam_page.dart:1363,1366-1367`（initState 0xc91908） | 0xc976f0（同文件 :8417） | _ExamPageState::dispatchAction **0xc97744** |
| enterExamPage | pp+0x49548 | `rain/receiver_page/exam_page.dart:1350,1353-1354` | 同上 0xc976f0（**同一闭包**） | 同上 0xc97744（inferred：两条通道共用一个闭包，observed 于 :1344 与 :1357） |
| JsCallFlutter | pp+0x31238 | `rain/ui_widget/study_partner_webview.dart:382,385-386`（initState 0xd5de30） | 0xd5e028（同文件 :483） | _StudyPartnerWebviewState::dispatchAction **0xd5e07c** |
| JsCallFlutter | pp+0x31238 | `rain/mine/hCaptcha_page.dart:137,140-141`（initState 0xd16d54） | 0xd16f80 | **不派发**：闭包内仅 `print("JsCallFlutter…")`（:242-246）、`"onPageFinished = "`(:311)、`"onPageStarted = "`(:383) 与 `WebViewController::reload` 0xc84684（:345） |

注销：`exam_page.dart:22891/22903` 两处 `removeJavaScriptChannel`（0x10fdffc / 0x10fe01c，dispose 0x10fdd78）分别注销 `"JsCallFlutter"` 与 `"enterExamPage"`。

**负结论（observed）**：全 asm 树未见 `window.jsBridge` / `"javascript:"` scheme / `addJavaScriptHandler` / `evaluateJavascript`（全仓仅 webview_flutter 平台实现）；Flutter 侧出站只走 `runJavaScript`。

## 2. 主派发器 JsCallFlutter::dispatchAction 全表（0xba725c, size 0x2958, :279–4028）

入口链（observed）：H5 `JsCallFlutter.postMessage(...)` → :365 取 `message.field_7` 字符串 → :1734 闭包 → `bl #0xba725c`；函数体先 :301 `"======js调用========"`、:321 `"JsCallFlutter ======js调用========"` 日志，再 :362 `JsBean.fromJson`(0xbd4a28) 解析出 `method`(:365 field_f) 为 action、`data`(:378 field_13) 为参数 Map。
分派形态：线性 if 链，每项 `bl #0x13a5b84 (_OneByteString::==)` 后 `tbnz w0,#4,<下一项字面量>`（bit4 置位=false）。**所有分支相同**：action 与参数均取自 H5 JSON。

| # | action | 比较 RVA | 比较行 | 失配下一跳 | 分派处理（RVA / 定义行） | data 键（键名@取键行） |
|---|---|---|---|---|---|---|
| 1 | openFile | 0xba7348 | L375 | 0xba7548 | openFile 0xbd4274 :21324 | fileType@382 file_name@423 fileUrl@464 canDownload@505 |
| 2 | openHomeworkFile | 0xba7558 | L554 | 0xba7744 | openHomeworkFile 0xbd3814 :20517 | fileType@561 fileName@597 fileUrl@638 canDownload@679 |
| 3 | closePage | 0xba7754 | L727 | 0xba7928 | closePage 0xbd2b5c :19624 | hasbind@734 quitClassroom@773 delete_type@812 from@850 |
| 4 | toPage | 0xba7938 | L903 | 0xba7b90 | toPage 0xbcfca0 :19394 | courseId@916 classroomId@967 courseName@1018 type@1068 |
| 5 | backAppRefresh | 0xba7ba0 | L1113 | 0xba7bec | 无自有 handler：closePage 0xbd2b5c @L1124 + App::_getInstance @L1126 + EventBus::fire(UpdateJournalList) | — |
| 6 | getPlatform | 0xba7bfc | L1147 | 0xba7c10 | getPlatform 0xbcfb48 :19333 | — |
| 7 | getSession | 0xba7c20 | L1159 | 0xba7c34 | getSession 0xbcf8e8 :19201 | — |
| 8 | bindSuccess | 0xba7c44 | L1171 | 0xba7c58 | bindSuccess 0xbcf7ec :19104 | — |
| 9 | startRecord | 0xba7c68 | L1183 | 0xba7c7c | startRecord 0xbcf05c :18934 | — |
| 10 | stopRecord | 0xba7c8c | L1195 | 0xba7d0c | stopRecord 0xbcb9b8 :18242 | upload@1202 |
| 11 | nativeCover | 0xba7d1c | L1246 | 0xba7ed8 | enterExam 0xbcb454 :17996（复用录制页入口） | classroomId@1253 title@1291 examId@1331 |
| 12 | bind_other_env | 0xba7ee8 | L1411 | 0xba80a0 | 无 handler：读 host@1424 / link@1463 → `xuetang_base_utils::saveData` 写 serverUrl/bindServerUrl/bindLink@1503,1509 → `rain/core/utils_function.dart::logout` | host / link |
| 13 | close_account | 0xba80b4 | L1581 | 0xba80c4 | 无 handler：`utils_function.dart::logout` @L1584 | — |
| 14 | backJournalPage | 0xba80d4 | L1592 | 0xba8258 | 无 handler：isDelete@1599 → EventBus::fire(UpdateJournalList)@1649 → Navigator::pop@1660 等 | isDelete |
| 15 | closeMemoPage | 0xba8268 | L1740 | 0xba9b6c | **空实现**：`tbz w0,#4,#0xba9b6c`（命中即跳函数尾 0xba9b6c = `mov x0,NULL; ret`，:3994） | — |
| 16 | uploadFile | 0xba8280 | L1748 | 0xba8670 | getAliOssConfig 0xbc630c :17571 | from@1844 tokenUrl@1879 problem_id@1920 exercise_id@1961 video_1g@2005（另 :2044 `"----uploadFile---- "` 计时日志） |
| 17 | getTokenData | 0xba8684 | L2105 | 0xba8a90 | getTokenData 0xbc5024 :15793 | credentials.AccessKeyId@2130 AccessKeySecret@2182 Expiration@2234 BucketName@2286 UploadDir@2338 SecurityToken@2390 cdn_host@2430 |
| 18 | uploadFilesChatbotMobile | 0xba8aa0 | L2482 | 0xba8da0 | getStudyAliOssConfig 0xbc1dc0 :13903（超限时 _ExamPageState::showMaxNumToast 0xbc4fb8 @L2638） | tokenUrl@2489 maxSize@2530 maxNum@2549 currentNum@2568 allowTypes@2587 |
| 19 | openCameraChatbotMobile | 0xba8db0 | L2760 | 0xba9064 | getAliOssConfigCamera 0xbb0954 :7850（showMaxNumToast@2902） | tokenUrl@2773 maxSize@2814 maxNum@2833 currentNum@2852 |
| 20 | openPhotoChatbotMobile | 0xba9074 | L3009 | 0xba9328 | getAliOssConfigCamera 0xbb0954（showMaxNumToast@3145） | tokenUrl@3016 maxSize@3057 maxNum@3076 currentNum@3095 |
| 21 | startAgentRecord | 0xba9338 | L3258 | 0xba934c | startAgentRecord 0xbb0760 :7658 | — |
| 22 | passAudioStream | 0xba935c | L3270 | 0xba9370 | passAudioStream 0xbaf344 :6681 | — |
| 23 | stopAgentRecord | 0xba9380 | L3282 | 0xba9394 | stopAgentRecord 0xbaf2c8 :6629 | — |
| 24 | stopRecordStream | 0xba93a4 | L3294 | 0xba93b8 | stopRecordStream 0xbaec58 :6550 | — |
| 25 | getAppDeviceInfo | 0xba93c8 | L3306 | 0xba93dc | getAppDeviceInfo 0xbae964 :6319 | — |
| 26 | checkAudioPermission | 0xba93ec | L3318 | 0xba9400 | _checkAudioPermissionOnInit 0xbad844 :6055 | — |
| 27 | wakeLesson | 0xba9410 | L3330 | 0xba94d8 | 无 handler：lessonId@3337 → Navigator::pop@3389 + `rain/util/navigator_utils.dart::NavigatorUtils::goRemoteControlPage`@3400 | lessonId |
| 28 | enterUnitVideo | 0xba94e8 | L3408 | 0xba9508 | enterUnitVideo 0xbacf1c :5761 | — |
| 29 | enterUnitArtical | 0xba9518 | L3425 | 0xba9538 | enterUnitArtical 0xbac594 :5560 | — |
| 30 | enterUnitAudio | 0xba9548 | L3442 | 0xba9568 | enterUnitAudio 0xbabdf4 :5259 | — |
| 31 | enterExam | 0xba9578 | L3459 | 0xba9718 | enterExam 0xbcb454 :17996 | classroomId@3466 name@3507 examId@3546（缺省 ""） |
| 32 | enterReceiver | 0xba9728 | L3607 | 0xba9748 | enterReceiver 0xbabb9c :5028 | — |
| 33 | enterRemote | 0xba9758 | L3624 | 0xba9778 | enterRemote 0xbaba70 :4916 | — |
| 34 | sendAnnounce | 0xba9788 | L3641 | 0xba97a8 | sendAnnounce 0xbab204 :4571 | — |
| 35 | enterAnnounceDetail | 0xba97b8 | L3658 | 0xba97d8 | enterAnnounceDetail 0xbaa4f4 :4310 | — |
| 36 | setH5Title | 0xba97e8 | L3675 | 0xba98a0 | 无 handler：title@3682 → EventBus::fire(WebViewPageTitleEvent)@3738 | title |
| 37 | showH5Share | 0xba98b0 | L3746 | 0xba9a78 | 无 handler：title@3753 url@3793 isShow@3833 → EventBus::fire(WebViewShareEvent)@3908 | title / url / isShow |
| 38 | enterLocationConfig | 0xba9a88 | L3916 | 0xba9aa8 | enterLocationConfig 0xbaa264 :4096（内读 classroomId@4108 universityId@4144 lessonId@4175） | 分支不取键（handler 内直读） |
| 39 | downloadAgentFile | 0xba9ab8 | L3933 | 0xba9b6c | downloadAgentFile 0xba9bb4 :4030（内读 fileUrl@4042；该分支 :3993 打 `"json解析失败："`） | 分支不取键 |

合计 39 条比较（`bl #0x13a5b84` 计数 = 39，observed）。

## 3. 兄弟派发器（同一通道名 "JsCallFlutter"，不同类）

### 3.1 ShareJsCallFlutter::dispatchAction 0xc7de84（`rain/home/course/share_webview_page.dart:161`，size 0x440，8 action）

| action | 比较 RVA | 比较行 | 失配下一跳 | 分派处理 |
|---|---|---|---|---|
| closePage | 0xc7df40 | L237 | 0xc7dfd4 | ShareJsCallFlutter::closePage 0xc7e868 @L287 |
| backAppRefresh | 0xc7dfe4 | L295 | 0xc7e024 | closePage 0xc7e868 @L301 + App::_getInstance 0x904ca0 @L303 + EventBus::fire(UpdateJournalList)@316 |
| getSession | 0xc7e034 | L324 | 0xc7e048 | getSession 0xc7e6f4 @L328 |
| bindSuccess | 0xc7e058 | L336 | 0xc7e06c | bindSuccess 0xc7e4ec @L340 |
| backHome | 0xc7e07c | L348 | 0xc7e090 | backHome 0xc7e454 @L352 |
| isLetter | 0xc7e0a0 | L360 | 0xc7e0b4 | **isReport** 0xc7e3ec @L364（action 名与方法名不一致，observed） |
| hideKeyboard | 0xc7e0c4 | L372 | 0xc7e0d8 | hideKeyboard 0xc7e3a4 @L376 |
| nativeCover | 0xc7e0e8 | L384 | 0xc7e2a8 | enterExam 0xc7e2c4 @L541 |

### 3.2 _ExamPageState::dispatchAction 0xc97744（`rain/receiver_page/exam_page.dart:8429`，size 0x1214，16 action）

| action | 比较 RVA | 比较行 | 失配下一跳 | 分派处理 |
|---|---|---|---|---|
| closePage | 0xc978e0 | L8590 | 0xc97910 | Navigator::pop 0x929664 @L8605（无自定义 handler） |
| postAccessToken | 0xc97920 | L8613 | 0xc97b3c | 无 bl 分派：内联 `Map._fromLiteral`@L8742 + App::_getInstance@L8745 + addHeader@L8753（**把 H5 给的 token 写进后续请求头**，inferred） |
| onClickImage | 0xc97b50 | L8816 | 0xc97d4c | 无 bl 分派：LogUtils::i@L8823 + 内联 `_interpolate`@L8964 |
| getH5Data | 0xc97d5c | L9002 | 0xc97ee0 | _ExamPageState::postAutoPhotoUpload 0xc9ec8c @L9132 |
| automaticSubmit | 0xc97ef0 | L9140 | 0xc97f20 | Navigator::pop @L9155 |
| otherDeviceEnterExam | 0xc97f30 | L9163 | 0xc97f44 | _ExamPageState::_stopAutoPhotoUpload 0xc9ec18 @L9167 |
| uploadFilesChatbotMobile | 0xc97f54 | L9175 | 0xc98254 | showMaxNumToast 0xbc4fb8 @L9331（其余为内联解析/间接调用，未捕获 bl） |
| openCameraChatbotMobile | 0xc98264 | L9453 | 0xc98518 | showMaxNumToast @L9595（同上） |
| openPhotoChatbotMobile | 0xc98528 | L9702 | 0xc987dc | showMaxNumToast @L9838（同上） |
| startAgentRecord | 0xc987ec | L9951 | 0xc98800 | _ExamPageState::startRecord 0xc999a4 @L9955 |
| passAudioStream | 0xc98810 | L9963 | 0xc98824 | _ExamPageState::passAudioStream 0xc99004 @L9967 |
| stopAgentRecord | 0xc98834 | L9975 | 0xc98848 | _ExamPageState::stopRecord 0xc98f94 @L9979 |
| stopRecordStream | 0xc98858 | L9987 | 0xc9886c | _ExamPageState::stopRecordStream 0xc98ec8 @L9991 |
| getAppDeviceInfo | 0xc9887c | L9999 | 0xc98890 | _ExamPageState::getAppDeviceInfo 0xc98c98 @L10003 |
| checkAudioPermission | 0xc988a0 | L10011 | 0xc988b4 | _ExamPageState::_checkAudioPermissionOnInit 0xc98a08 @L10015 |
| downloadAgentFile | 0xc988c4 | L10023 | 0xc9891c | _ExamPageState::downloadAgentFile 0xc98958 @L10032 |

### 3.3 _StudyPartnerWebviewState::dispatchAction 0xd5e07c（`rain/ui_widget/study_partner_webview.dart:495`，size 0xab4，10 action）

| action | 比较 RVA | 比较行 | 失配下一跳 | 分派处理 |
|---|---|---|---|---|
| uploadFilesChatbotMobile | 0xd5e150 | L581 | 0xd5e450 | showMaxNumToast 0xbc4fb8 @L737（其余内联） |
| openCameraChatbotMobile | 0xd5e460 | L859 | 0xd5e714 | showMaxNumToast @L1001 |
| openPhotoChatbotMobile | 0xd5e724 | L1108 | 0xd5e9d8 | showMaxNumToast @L1244 |
| startAgentRecord | 0xd5e9e8 | L1357 | 0xd5e9fc | _StudyPartnerWebviewState::startRecord 0xd5fcb0 @L1361 |
| stopAgentRecord | 0xd5ea0c | L1369 | 0xd5ea20 | stopRecord 0xd5fc40 @L1373 |
| passAudioStream | 0xd5ea30 | L1381 | 0xd5ea44 | passAudioStream 0xd5f184 @L1385 |
| stopRecordStream | 0xd5ea54 | L1393 | 0xd5ea68 | stopRecordStream 0xd5f0b8 @L1397 |
| getAppDeviceInfo | 0xd5ea78 | L1405 | 0xd5ea8c | getAppDeviceInfo 0xd5ee7c @L1409 |
| checkAudioPermission | 0xd5ea9c | L1417 | 0xd5eab0 | _checkAudioPermissionOnInit 0xd5ebe0 @L1421 |
| downloadAgentFile | 0xd5eac0 | L1429 | 0xd5eb18 | downloadAgentFile 0xd5eb30 @L1438 |

## 4. Dart → JS 调用名清单（出站，全部经 `WebViewController::runJavaScript` 0xbae4f0）

拼接方式（observed）：`<方法名>(" + jsonEncode(payload) + ")` → `dart:core _StringBase::_interpolate`（0x778abc）→ `runJavaScript`。全 app 共 **35 个** runJavaScript 调用点。

| JS 方法名 | 字符串偏移 | 发出 Dart 函数（RVA） | runJavaScript 行 | 负载要点 |
|---|---|---|---|---|
| `callJS(` | pp+0x31340 | ShareJsCallFlutter::nativeCallJs 0xbcc210（`share_webview_page.dart:102`） | :147 | 通用出站口，被 getPlatform/getSession/sendRecordUrl/stopRecord 复用 |
| `callJS(` | pp+0x31340 | _ExamPageState::postDataToJS 0xc96884（`exam_page.dart:7412`） | :7614 | exam 页出站口 |
| `callHomeworkJS(` | pp+0x388e8 | JsCallFlutter::postHomeworkDataToJS 0xbc6004 | :17427 | `{fileUrl,fileName,fileType,fileSize,_fileSize}`（键 :17299-:17334） |
| `callTokenJS(` | pp+0x38920 | JsCallFlutter::uploadFile 0xbc676c（async） | :17986 | `{"upload": field_23?.field_7 ?? ""}`（:17912-:17938） |
| `callGetChatbotMobileFilesInfo(` | pp+0x36300 | postMultipleImagesDataToJS 0xbb2328 / postImageDataToJS 0xbc11a4 / postGetChatbotMobileDataToJS 0xbc2f08（`app_js_call_flutter.dart`） | :10140 / :13513 / :15681 | 图片/文件回传结果 |
| `callGetChatbotMobileFilesInfo(` | pp+0x36300 | exam_page: postMultipleImagesDataToJS 0xc9b0bc / postImageDataToJS 0xc9d3d0 / postHomeworkDataToJS 0xc9e964 | :13910 / :17256 / :19228 | 同上（exam 页副本） |
| `callGetChatbotMobileFilesInfo(` | pp+0x36300 | study_partner: postMultipleImagesDataToJS 0xd615e0 / postImageDataToJS 0xd63900 / postHomeworkDataToJS 0xd64ea0 | :5636 / :8987 / :10964 | 同上 |
| `callH5Methods(` | pp+0x49be0 | exam_page 闭包 0xc92474 / 0xc92914 / _getExamUploadToken 0xc92db8 / _uploadImageCallH5Methods 0xc9ef68 | :2367 / :2786 / :3095 / :19930 | 截图监听、相机无权限、上传 token |
| `passAudioPermissionToH5(` | pp+0x35e90 | [closure] passToH5 0xbae398 / 0xc98b40 / 0xd5ed18（三处同构） | :6309 / exam:10396 / study:1784 | 麦克风权限结果 |
| `passAppDeviceInfoToH5(` | pp+0x35f00 | getAppDeviceInfo 0xbae964 / 0xc98c98 / 0xd5ee7c | :6531 / :10593 / :1986 | 设备信息 |
| `passAudioStream(` | pp+0x35f98 | _sendAgentChunkToH5 0xbb0324（另 exam 0xc995ac / study 0xd5f838） | :7384 / :11403 / :2875 | `passAudioStream("<chunk>","<…>");`（字面量 :7332 / "," :7344 / ");" :7364） |
| `passAudioStreamToH5(` | pp+0x46d28 | study_partner _StudyPartnerWebviewState::passAudioStream 0xd5f184 | :2203 | 同上（该页变体名） |
| `passAudioStreamEnd();` | pp+0x35f80 | _onAgentPcmStreamDone 0xbb0174（exam 0xc993fc / study 0xd5f68c） | :7233 / :11252 / :2719 | 无参收尾 |
| `passExpandInfoToH5(` | pp+0x49f70 | classroomlog_h5_page 闭包 0xe30eb8 | :5441 | 日志页扩展信息 |
| `appGetLocatonInfo()` | — | JsCallFlutter::appGetLocatonInfo 0xe89c34（字面量 :22033） | :22037 | 定位回调触发 |
| `document.querySelector('video')?.pause();` | — | study_partner dispose 0x110c8d4 | :11482 | 页面销毁静音 |
| `document.querySelector('audio')?.pause();` | — | study_partner dispose 0x110c8d4 | :11492 | 同上 |
| `document.querySelectorAll('audio, video')?.forEach(media => {if(!media.paused){media.pause()}});` | — | exam_page dispose 0x10fdd78 | :22919 | 同上 |

有回调但非 runJavaScript 的出站（observed，走 `ShareJsCallFlutter::nativeCallJs` 0xbcc210 = `callJS(` 包装）：getPlatform 0xbcfb48（`{"platform":"app"}`，`JsBean{method:"getPlatform",…:"success"}`，:19345-:19380）、getSession 0xbcf8e8（payload `sessionid/type/csrftoken/userid/version` :205-:263 → nativeCallJs 0xbcfbbc）、sendRecordUrl 0xbcc174（`JsRecordUrlBean{bucket:"yuketang"}` + `method:"stopRecord"` → nativeCallJs :18920）、uploadFile 的响应（`:18888`）。
> 注：`nativeCallJs` 的实际实现地址被编译器折叠为 `share_webview_page.dart` 的 `ShareJsCallFlutter::nativeCallJs` 0xbcc210（blutter 将同源同构方法归并；JsCallFlutter 与 ShareJsCallFlutter 均继承 `JsCallFunction`，见 `share_webview_page.dart:94` / `xuetang_webview.dart:364`）——**inferred**。

## 5. 桥的输入信任边界

共同点（observed）：四个派发器的 action 与参数都来自 H5 字符串 → `JsonCodec.decode` → `JsBean.fromJson`，原生侧只有 `IsType_String?` / `IsType_int?` / `IsType_bool?` 可空类型判定与个别长度/上限判断，**没有任何签名、nonce、来源域名或会话绑定校验**。

| 类别 | action（证据） | 原生二次校验 | 页面可伪造的影响 |
|---|---|---|---|
| 纯入参放任（最常见） | openFile :382-:505、openHomeworkFile :561-:679、openFile/openHomeworkFile 的 canDownload="false" 字符串比较（:20567 / :21381）、closePage hasbind/quitClassroom/delete_type/from :734-:850、toPage :916-:1068、enterExam :3466-:3546、nativeCover :1253-:1331、enterUnitVideo/Artical/Audio（无参）、enterReceiver/enterRemote/sendAnnounce/enterAnnounceDetail（无参）、setH5Title :3682、showH5Share :3753-:3833、wakeLesson lessonId :3337 | 仅可空类型 | 直接驱动原生页面跳转、弹窗标题/分享项、通知发送与公告详情（UI 欺骗与越权跳转面） |
| 原生用 H5 给的 URL 发起请求（**最高风险**） | uploadFile/getAliOssConfig 0xbc630c：`[tokenUrl, "?exercise_id=", …, "&problem_id=", …]` 拼接（:17631-:17649）后调 `BaseNet::requestGet` 0x840454（:17694）；同构：getStudyAliOssConfig 0xbc1dc0（:13999）、getAliOssConfigCamera 0xbb0954；三个 chatbot action 与 uploadFile 的 tokenUrl 均取自 H5（:2489/:2773/:3016/:1879） | 无（仅空值兜底 `""` :6404） | tokenUrl 完全可控 → 原生携带 App 网络栈（同一 `DioMixin::get`，:259 0x84064c；是否附带登录态取决于拦截器 —— **inferred**）请求任意地址；返回的 OSS 配置再被用于上传 |
| 原生直接接受 H5 授予的云凭证 | getTokenData :2130-:2390（AccessKeyId/AccessKeySecret/SecurityToken/BucketName/UploadDir/Expiration + cdn_host） | 仅 String 可空校验 | 上传目标 bucket/目录/凭证全由页面决定 → 可让 App 把本地文件写进页面指定的 OSS 桶 |
| 改写全局服务器地址 + 强制登出 | bind_other_env :1424/:1463 → saveData(serverUrl/bindServerUrl/bindLink) :1503,:1509 → logout；close_account :1584 直接 logout | 无（host/link 仅 String 校验） | 页面可将 App 服务器地址重绑定到任意域名并触发登出（会话劫持/持久化重定向面） |
| 本地文件与摄像头/麦克风 | downloadAgentFile fileUrl :4042、openFile/openHomeworkFile fileUrl（:464/:638）、startRecord/stopRecord/uploadRecord/uploadFile、openCameraChatbotMobile/openPhotoChatbotMobile/uploadFilesChatbotMobile（maxSize/maxNum/currentNum/allowTypes :2489-:2587 等） | 数量上限校验（超出 → `showMaxNumToast`，如 :2638）；文件类型仅字符串后缀比对（openFile 扩展名白名单 :20629-:20759） | 页面可触发任意 URL 下载/打开、录音与相册/相机选取并上传（如需用户授权则被系统弹窗阻断 —— inferred） |
| 会写请求头 | exam_page postAccessToken：`addHeader` @L8753 使用 H5 提交的 access token（:8613 分支） | 未捕获校验 | 页面可注入/替换后续请求头凭据（inferred：请求对象来自 H5 数据 + App::_getInstance） |
| 空实现（无影响） | closeMemoPage :1740（命中即 ret null，:3994） | — | 无 |
| 只打印（不派发） | hCaptcha_page 通道 `"JsCallFlutter"` 闭包 0xd16f80（:242-:246、:311、:383） | — | 无（仅日志与 reload） |

## 6. 未找到 / 存疑

1. **未找到**：`window.jsBridge`、`javascript:` scheme、Flutter `addJavaScriptHandler` / `onCallJsHandler` 在 rain 包内的实际注册（`onCallJsHandler` pp+0x62a90 仅见于 `flutter_inappwebview … in_app_webview_controller.dart:637 _handleMethod 0xf1eb64`，未被本 APK 业务代码使用）。
2. **未找到**：action 白名单/签名校验、桥消息的 nonce 或时间戳字段（JsBean 仅 code/method/data/msg 四字段，`xuetang_webview.dart:50-52`）。
3. **存疑（unverified）**：`uploadFile` 分支内 `:2044` 的计时统计与 `:1782` `DateTime::difference` 日志是否另有上报；三个 chatbot action 在 exam_page/study_partner 中的真正 Dart 处理函数（分支内仅见内联解析 + `showMaxNumToast`，疑为 IC 间接调用 `blr lr`，未解析目标）。
4. **存疑（unverified）**：`enterExamPage` 通道与 `JsCallFlutter` 共用闭包 0xc976f0（`:1344` 与 `:1357` 均引用同一地址），JS 侧向任一通道发消息都会进同一 16-action 派发器。
5. 方法折叠（inferred）：`nativeCallJs` 在 `JsCallFlutter` 上的实现被归并到 `share_webview_page.dart:102` 的 `ShareJsCallFlutter::nativeCallJs` 0xbcc210，源码层面应为两个类的同构实现。
