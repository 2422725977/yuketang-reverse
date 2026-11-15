# 雨课堂（ykt）考试监考上报 + 反作弊检测项 全枚举

样本：`so/lib/arm64-v8a/libapp.so`（Dart AOT）+ `jadx/sources`（Java 层）。
证据约定：`文件:行号`（blutter 反汇编行号）、`RVA 0x…`（= blutter 打印的 addr；libapp.so .text vaddr==文件偏移 0x760000，故 addr 即 RVA）、`@0x…`（字符串/对象池偏移）。
标注：**observed**＝反汇编/源码直读；**inferred**＝由多处 observed 推得；**unverified**＝未找到支撑。只读样本，本文件为分析产物。

---

## 板块一 监考 action 码全表

### 1.1 全库 action 常量穷举（observed）

穷举方法：全 `blutter_out/asm` 扫描 action 键位点（7 处）＋三个上报函数的全部调用点＋`grep answer_problem`（3 处）＋`grep monitor/feed/add`（仅 exam_page.dart）。

| 码 | 触发条件（客户端事件） | 通道 | 端点 | 提示文案 | 证据 |
|---|---|---|---|---|---|
| **24** | ① 退出考试页 `examQuitCallBack`（生命周期非 resumed）；② H5 切答题页 `ChangePageEvent` | HTTP POST | `baseUrl+/online_proctor/stu/monitor/feed/add` | 无（静默） | exam_page.dart:332 / 0x93d6fc；exam_page.dart:1988 / 0xc9213c；体构造 exam_page.dart:413-419（`mov x16,#0x18`） |
| **16** | App 回到前台 `examResumeCallBack`（`didChangeAppLifecycleState`==resumed） | HTTP POST | 同上 | 服务端 msg，否则硬编码 学生试卷被系统暂时收回 | exam_page.dart:639 / 0x93dc74（`mov x2,#0x10`）；回调闭包 0x93df48 / exam_page.dart:1102（@pp+0x49590） |
| **20** | ① `MultiWindowEvent`（分屏/多窗口变化，100ms 防抖）；② `ReportExamQuitEvent`→`examSplitScreenResumeCallBack` | HTTP POST | 同上 | `Cut_Screen_Alert` 等（l10n） | exam_page.dart:1847 / 0xc91fd4；exam_page.dart:8002 / 0xc96f14（均 `mov x2,#0x14`） |
| **60** | 截屏事件（`DisableScreenshots.onScreenShots` 流） | H5 JS 桥 | `/exam_room/answer_problem`（`callH5Methods`） | `exam_forbid_shot`＝考试中禁止截图，此行为将报告给你的老师 | 闭包 0xc92474；action 赋值 exam_page.dart:2173-2180；runJavaScript 2366-2367；toast 2383-2394 |
| **62** | 相机无权限事件 `CameraNoPermissionEvent` | H5 JS 桥 | 同上 | 无（静默上报） | 闭包 0xc92914；action exam_page.dart:2592-2597（`mov x16,#0x3e`）；runJavaScript 2785-2786 |
| **64** | 随机抓拍照片七牛直传成功后 | H5 JS 桥 | 同上 | 无 | `_uploadImageCallH5Methods` 0xc9ef68；action exam_page.dart:19711-19765（`mov x16,#0x40`）；url 19694 |
| **96** | 光速虚拟机检测 status∈{detected,suspected} | HTTP POST | `baseUrl+/online_proctor/stu/monitor/feed/add` | 无 | `reprotExamByVm` 0xc970f8；调用点 exam_page.dart:8178 / 0xc970e0、exam_page.dart:8772 / 0xc97acc；体构造 8329 |

**无「多指」码**（observed）：`python3 so/kwscan.py 多指` 0 命中，全 asm 无 multi-touch 相关 action 分支。`reprotExamShowToast` 全库仅 3 个调用点（16/20/20）、`reprotExam` 仅 2 个（24/24）、`reprotExamByVm` 仅 2 个（96/96）→ 码集合封闭。

### 1.2 上报体字段（observed）

HTTP 直发（24/16/20/96）：`BaseNet::requestPost`(0x923178)，路由＝`App._getInstance().field_bb.field_1b`(baseUrl) 与路径 `_interpolate` 拼接。

| 码 | 请求体键 | 来源 |
|---|---|---|
| 24 | `exam_id`（= `App.field_b[0]` 考试 id）、`action`=24 | 全客户端 |
| 16 / 20 | `exam_id`、`action`=参数 r2 | 全客户端 |
| 96 | `exam_id`、`action`=96、`vm_report`=jsonEncode(原生报告) | exam_id 客户端；vm_report 来自 Java |

H5 桥（60/62/64）：构造 `{"method":"post","url":"/exam_room/answer_problem","params":{…}}` → `JsonCodec::encode` → 拼 `callH5Methods(<json>)` → `WebViewController::runJavaScript`(0xbae4f0) 注入考试 H5。
params 公共字段：`exam_id`、`label:0`、`event_group_id:0`、`operator_id:0`、`action`、`t:"f"`、`app_version:<App.field_a3>`、`terminal:("Android-pad"|"Android-mobile"，由 Device.get().field_7 决定)`、`is_app:true`；64 追加 `image_url`（七牛 key 拼域名）。→ 60/62/64 的实际落库请求由 H5（服务端页面）发出，APK 只转交事件（observed：三处位点均无 HTTP 客户端调用，只有 runJavaScript）。

### 1.3 监考端点全路径（observed，全库穷举）

| 端点 | 出现位置 |
|---|---|
| `/online_proctor/stu/monitor/feed/add`（@pp+0x494d0） | exam_page.dart:463 / 779 / 8329 |
| `/online_proctor/stu/face-compare`（@pp+0x42750） | exam_authentication_album_special_page.dart:221 |
| `/exam_room/answer_problem` | exam_page.dart:2117 / 2532 / 19694（JS 桥） |
| `/idphoto/upload/token` | exam_page.dart:2991、album_special:137、album_page:133 等 6 处 |
| `/idphoto/create` | album_page:175、album_special:179 等 4 处 |
| `/v/exam/cover?exam_id=` | exam_info_page.dart:668、album_special:348 |
| `/v/exam/gen_token` | exam_info_page.dart:3523/5776、album_special:941/5283 等 12 处 |
| `/login/app` | 22 处，含 `/login/app_version_log?exam_id=`（exam_info_page.dart:4193）、`/api/v3/user/login/app/wechat`（rain/common/wechat.dart:792） |
| 平台通道 | Dart `MethodChannel("com.xuetangx.ykt/ykt")`：`multiWin`/`isSplitScreen`/`isMultiWindow`/`isRotateScreen`/`getSdkInt`/`detectGuangsuVirtualMachine`/`pickLargeFile`（Java MainActivity.java:153/177/219/232；Dart handler main.dart:7493-8067） |

孤立字符串 `online_proctor`（@pp+0x3a4f0）在 asm 中无引用点（**unverified**）。

---

## 板块二 `_listenAppSizeChange` 与 `postAutoPhotoUpload`

### 2.1 `_listenAppSizeChange` RVA 0xc91d90（exam_page.dart:1622-1699）

| 项 | 内容 | 证据 |
|---|---|---|
| 订阅对象 | `EventBus::on<MultiWindowEvent>`（0x905030）→ 存 `this.field_5f` | exam_page.dart:1658 / 1680 |
| 闭包签名 | `[closure] (dynamic, MultiWindowEvent)` —— 名字与实现不符，它监听多窗口而非窗口尺寸 | exam_page.dart:1701-1702（0xc91e64） |
| 防抖 | `Future.delayed(Duration(microseconds:100000)=100ms)`（0xc91e94 `mov x0,#0x86a0` + `movk x0,#1,lsl#16`） | exam_page.dart:1691-1695 |
| 门禁 | ① `if (!this.field_1b) return`；② `this.field_b`(widget) 为 null → NullCast；③ `if (!this.field_b.field_1b) return` | 0xc91f10 / 0xc91f24 / 0xc91f34 |
| 节流 | `field_77`（上次时间）＋`field_7b`=1s（`Duration(microseconds:1000000)`，构造 0x112f8c4） | 0xc91f84-0xc91fac；exam_page.dart:23107-23116 |
| 动作 | `field_77 = now`；`reprotExamShowToast(20)`（`mov x2,#0x14`） | 0xc91fb8 / 0xc91fd4 |

**inferred**：`_listenAppSizeChange` 实为「分屏/多窗口 → action 20」通道；真正窗口尺寸事件 `AppSizeChangeEvent` 由 main.dart 转屏分支发出，考试页不监听（observed：AppSizeChangeEvent 监听文件列表无 exam_page.dart）。

### 2.2 分屏状态链路（client-driven，observed）

| 环节 | 内容 | 证据 |
|---|---|---|
| Java 推送源 | `onMultiWindowModeChanged`/`onPictureInPictureModeChanged` → `invokeMethod("isSplitScreen",{isSplit:bool})`；`onConfigurationChanged`（orientation!=2）→ `invokeMethod("isRotateScreen",{appWidth})`；Handler `msg.what==1001` → `invokeMethod("isMultiWindow",{isMultiWindow:true})`；查询方法 `multiWin`→`isInMultiWindowMode()||isInPictureInPictureMode()` | MainActivity.java:279-294 / 297-312 / 315-327 / 71-84 / 219-231 |
| Dart 处理 | `isSplitScreen`：写全局静态 `0xe44`=isSplit，为真→`EventBus.fire(ReportExamQuitEvent())`，随后 `fire(SplitModeChangeEvent())`；`isMultiWindow`：`fire(MultiWindowEvent())`；`isRotateScreen`：两次 `Navigator.pop` + `fire(AppSizeChangeEvent)`×2 | main.dart:7994 / 8017-8052 / 8085-8089 / 7815-7929 |
| 考试页接收 | `ReportExamQuitEvent` 唯一考试侧监听＝闭包 0xc96dc8→`examSplitScreenResumeCallBack`(0xc96e10)→action 20；`MultiWindowEvent` 唯一考试侧监听＝`_listenAppSizeChange`→action 20 | exam_page.dart:7867-7896；grep MultiWindowEvent 仅 main.dart/exam_page.dart |
| 全局标志 0xe44 | 写：main.dart:7507（启动查 `multiWin`）、main.dart:7994（推送）、exam_info_page.dart:2587（进考试前重查 `multiWin`）、exam_page.dart:536/917（监考上报 `code==0` → 置 false）。读：main.dart:8017、exam_page.dart:8784/8798（`postAccessToken` 分支：仍真→分屏回调，否则普通前后台回调） | 见左 |

### 2.3 `postAutoPhotoUpload` RVA 0xc9ec8c（exam_page.dart:19384-19656，async）

开启条件（observed，exam_page.dart:1519-1538）：`widget.field_b.field_1b` 为真 **且** `field_33==1`（app_front_random_snap）**且** `field_1f!=2` → `print("有自动拍照")` → `_listenAutoCameraEvent` + `_listenNoPermissionEvent`；`build()` 内同条件构造 `AutoCameraPage`（exam_page.dart:20930-20960）。

| 步骤 | 内容 | 证据 |
|---|---|---|
| 抓拍完成 | `_AutoCameraPageState` 用照片路径建 `UploadPicModel`(0x94410c, field_f=路径) → `EventBus.fire(AutoCameraEvent)` | auto_camera.dart:811-855 |
| 收事件 | `(dynamic, AutoCameraEvent)` 0xc92cfc → `this.field_6b`=路径 → `_getExamUploadToken()` | exam_page.dart:2885-2956 |
| 取上传 token | 不直接调后端：JS 桥 `{'method':'get','url':'/idphoto/upload/token','params':{}}` → `callH5Methods` → runJavaScript；H5 回调 `dispatchAction` 的 `getH5Data` 分支把 token 写入 `this.field_63` | exam_page.dart:2956-3108 / 9054 |
| 七牛直传 | `Storage().putFile(path, PutOptions, token)`（qiniu_flutter_sdk 0xbcc36c）→ 成功后拼 key+"/" | exam_page.dart:19384-19656 |
| 上报 H5 | `_uploadImageCallH5Methods` → action=64 的 JS 桥 payload（含 `image_url`） | exam_page.dart:19694-19765 |
| VM 上报补发 | `dispatchAction` 的 `postAccessToken` 分支：`field_b7`（被节流挂起的 VM 上报）非空 → 补发 `reprotExamByVm` | exam_page.dart:8772 |

### 2.4 截屏检测（两个第三方插件，observed）

| 插件 | Dart 通道 | Java 实现 | 检测方式 |
|---|---|---|---|
| `disable_screenshots` | MethodChannel `com.devlxx.DisableScreenshots/disableScreenshots`（方法 `disableScreenshots`，参数 `{"disable":bool}`）；EventChannel `com.devlxx.DisableScreenshots/observer`＝`onScreenShots` | DisableScreenshotsPlugin.java:57；ScreenShotListenManager.java | `ContentObserver` 注册于 `MediaStore.Images.Media.INTERNAL/EXTERNAL_CONTENT_URI`（:61-64）；`KEYWORDS={screenshot,screen_shot,screen-shot,screen shot,screencapture,…}`（:30）；`checkScreenShot()` 路径关键字＋尺寸＋时间戳启发式（:164）；`sHasCallbackPaths` 去重（:178-189） |
| `no_screenshot` | MethodChannel `com.flutterplaza.no_screenshot_methods`（`screenshotOff`/`screenshotOn`）；EventChannel `…/no_screenshot_streams` | NoScreenshotPlugin.java / NoScreenshotPluginKt.java | `ContentObserver(EXTERNAL_CONTENT_URI)`（:996）；**API 34+ 另有系统级 `Activity.ScreenCaptureCallback`**（:869-891）；状态落 SharedPreferences（`screenshot_pref`/`is_screenshot_on`/`screenshot_path`/`was_screenshot_taken`，:1213-1215）；EventChannel 每 1s 轮询（:319） |

考试页调用：`_listenScreenshotEvent`(0xc92358, exam_page.dart:2029) 订阅 `DisableScreenshots.onScreenShots`（存 `field_53`）；initState:1566 `DisableScreenshots.disableScreenshots(true)`（0xc91d00 `r3=true`）、1573 `NoScreenshot.screenshotOff()`；`dispose`(exam_page.dart:22653) 于 22720/22732 恢复。
**inferred**：截屏判定为「MediaStore 启发式监听 + 插件流」，非内核级；`adb screencap`、写入非 MediaStore 目录、或让 Android 34+ `onScreenCaptured` 不触发/取消订阅即可绕过；被绕过时服务端无第二来源（observed：action 60 唯一触发点）。

---

## 板块三 光速虚拟机检测（GuangsuDetector）全项枚举

### 3.1 调用链（observed）

`_detectGuangsuVirtualMachine` RVA 0xc96f90（exam_page.dart:8055，async）→ 守卫 `field_af`（每场考试只检一次）、`field_1b` 为真直接返回 → `await collectVirtualEnvironmentReport()`（virtual_environment_report.dart 0xc972f8）→ `MethodChannel.invokeMapMethod("detectGuangsuVirtualMachine")`（带超时）→ 校验 `schemaVersion==2` → status∈{detected,suspected} 时 `jsonEncode` 全量报告并 `reprotExamByVm`（action 96）。

### 3.2 Java 侧采集项（GuangsuDetector.detect(Context)，GuangsuDetector.java:35-116）（observed）

| # | 采集项 | 内容 | 是否进入判定 |
|---|---|---|---|
| ① | appPaths（:40） | `sourceDir`、`nativeLibraryDir`、`filesDir`、`dataDir` | 否（未传 evaluate，也未进上报体） |
| ② | Build.*（:41-51） | `BRAND`、`MANUFACTURER`、`MODEL`、`DEVICE`、`PRODUCT`、`HARDWARE`、`FINGERPRINT`、`VERSION.SDK_INT`、`SUPPORTED_ABIS` | 否 |
| ③ | 文件读取（:52，单文件上限 131072B） | `/proc/self/maps`、`/proc/self/mountinfo`、`/proc/version`、`/proc/self/cgroup`、`/system/build.prop`、`/vendor/build.prop` | 仅 maps/mountinfo/version；cgroup 与两个 build.prop 未用 |
| ④ | getprop（:59-82） | `ProcessBuilder("/system/bin/getprop")`，1500ms 看门狗线程 `destroy()`（:162-168），stdout `take 65536` | 是 |
| ⑤ | 上报 | `GuangsuReport.build(Match, errors)` 仅吃 Match+errors | — |

### 3.3 规则集（GuangsuRuntimeRules.evaluate(getprop, maps, mountinfo, kernelVersion)，:173-385）（observed）

| 规则 id | 命中条件 | 依据文案 |
|---|---|---|
| `guangsu_titan_graphics` | `ro.hardware.{egl,gralloc,power,vulkan}` 中值==`titan` 的项 **≥3** 且 maps 含 /vendor/lib64|lib/hw/vulkan.titan.so 且含 /vendor/lib64|lib/egl/libGLES_titan.so | 至少3项Titan HAL属性且当前进程加载两项Titan图形库 |
| `guangsu_android10_6816` | `/proc/version` release 匹配 `^[0-9]+\.[0-9]+\.[0-9]+-titan([-+].*)?$` 且 `ro.build.version.sdk`==29 且 `ro.config.version_code`==6816 | Titan内核release、SDK29、版本码6816同时成立 |
| `android_container_csaic` | mountinfo 根挂载（split[4]=="/"）为 `overlay` 且含 `lowerdir=/var/lib/isulad/storage/overlay/`，且 `csaic.ready`==1 且 `init.svc.csaicd`==running | iSulad overlay根挂载且CSAIC就绪并运行 |

environment：命中前两条→`guangsu_titan`；否则第三条→`android_container`；否则 `unknown`（:306-312）。status：`detected` / 有证据→`suspected` / 无→`unknown`（GuangsuReport.java:32）。
上报体 8 键（GuangsuReport.java:26-60）：`schemaVersion=1`、`ruleVersion=5`、`status`、`environment`、`matchedRules`、`rules`（3 条全量含 checks）、`raw`（properties=9 键截断 128、valuesTruncated、kernelRelease、loadedLibraries、rootMount）、`errors`（distinct，≤12 条×160 字符）。

### 3.4 版本号不一致 → action 96 实际不可达（observed + inferred）

Dart 侧 `collectVirtualEnvironmentReport` 要求 `map["schemaVersion"]==2`（virtual_environment_report.dart:64-85），Java 侧恒为 **1**（GuangsuReport.java:30）→ 必走 `INVALID_NATIVE_REPORT` 兜底报告（ruleVersion=10），status 永不落在 {detected,suspected} → `reprotExamByVm` 不触发。
**inferred**：结论依赖「MainActivity 是唯一 `detectGuangsuVirtualMachine` handler」——全 jadx grep `Guangsu` 仅 32 处且集中在 MainActivity 与 3 个 Guangsu* 类，未见第二处注册；Dart asm 中未见自定义通道名（高置信但非绝对）。

### 3.5 frida/xposed 复核（observed）

`grep -rniE "\bfrida\b" jadx/sources` = 0；`\bxposed\b` = 0；`\bptrace\b|/data/adb` = 0（无词边界时 `frida` 6 处、`xposed` 79 处均为 androidx/patterns 噪声与 `Exposed*`）。
GuangsuDetector 读取的 6 个 /proc + 2 个 build.prop 无 frida 相关项；`GuangsuRuntimeRules` 匹配串只有 titan/isulad/csaic 三类 → **确认本项目反作弊规则集不含 frida/xposed 关键字**。
附带（非自研）：极光推送 SDK 自带 root 检测 `cn/jiguang/commons/a/kl.java:18`（11 个 root 包名含 magisk/kingroot/supersu + 17 条 su 路径 + `Build.TAGS` 含 test-keys），唯一调用点 `cn/jiguang/commons/a/bw.java:180`，用于设备信息字段，不参与监考判定（observed）。

---

## 板块四 人脸认证链路（exam_authentication_page/**）

目录仅 3 个 dart（exam_authentication_album_special_page.dart 15193 行、exam_authentication_album_page.dart 7909 行、bx_line_widget.dart 126 行）+ 4 bean；`initState`(0xd22058, exam_authentication_album_special_page.dart:51-308) 预拼 4 个 URL（baseUrl 取 `App.field_bb.field_1b`）。

| 步骤 | 端点 | 方法/体 | 证据 |
|---|---|---|---|
| 拉考试信息 | `/v/exam/cover?exam_id=&classroom_id=` | GET | :308-428 / 0xd22324 |
| 取认证令牌 | `/v/exam/gen_token` | POST `{"exam_id":field_b.field_f,"classroom_id":field_13}` | :842-966 / 0x1003ad8 |
| 证件照登录取 session | `field_43 = baseUrl+"/login/app"` | GET `?exam_id=&user_id=<App.field_7>&crypt=<App.field_43>&language=zh-cn` | :1078-1248 / 0x1003d38 |
| 取七牛上传 token | `field_47 = baseUrl+"/idphoto/upload/token"` | GET（先 `BaseNet::addHeader(App.field_7)`） | :1367-1557 / 0x100423c |
| 上传证件照 | 七牛直传（PutResponse 闭包 0x1004ad4） | putFile | :1674-1939 / 0x100479c |
| **人脸比对校验** | `field_4f = baseUrl+"/online_proctor/stu/face-compare"` | POST `{"exam_id":field_b.field_f,"has_camera":"1","image_url":field_1f}` | :2062-2291 / 0x1004ba4；URL 拼接 :221-230 |
| 结果处理 | `ExamOnlineProctorFaceBean` → `setState`×2 + 重新 `_loadData()` | — | 闭包 0x1005060 / :2333-2404 |

返回体键（observed）：`exam_online_proctor_face_bean`＝status/image_url/errcode/errmsg/data；`exam_idphoto_create_bean`＝photo_id/idphoto_limit/photo_url/errcode/errmsg/data；`exam_login_app_bean`＝x_access_token/xt_lang/status/data；`upload_exam_token`＝domain/bucket_name/expires/token/errcode/errmsg/data。
其它：水印 `watermark_photo`（:14691）、`?xt=exam`（:14702）、无摄像头提示图 `https://proxt-cdn.xuetangx.com/fe-proxtassets/onlineexam/nocamera1.png`（@pp+0x425c8）。
`/v/exam/cover` 中与认证/监考相关键（exam_cover_bean.dart）：`online_proctor`、`face_auth_status`、`face_status`、`has_idphoto`、`idphoto_img`、`face_img`、`is_manual_review`、`max_retry`、`force_confirm`、`monitor_status`、`screen_capture_verify_status`、`page_switch_detection`、`app_front_random_snap`、`app_capture_screen`、`open_screen_cuts`、`max_screen_cuts_num`、`cut_count`、`open_access_restriction`、`access_restrictions_is_ok`。

---

## 板块五 结论：客户端驱动 + 服务端留痕

### 5.1 判定开关（observed）

`ExamPage` 构造实参来自 `/v/exam/cover` 嵌套对象：`app_capture_screen`→`field_3b`、`app_front_random_snap`→`field_33`、`page_switch_detection`→`field_43`；总开关 `field_1b`＝`(state.field_1b.field_23.field_2f == 2)`（考试进行中）（exam_info_page.dart:4360-4440、4423；ExamPage 构造 0x100013c；bean 字段映射 exam_cover_bean.dart:1599-1779）。
门禁表达式：自动拍照 `field_1b && field_33==1 && field_1f!=2`；截屏 `field_3b==1 && field_1f!=2`；切页/多窗口 `field_1b`（exam_page.dart:1509-1595）。

### 5.2 客户端可控点（逐条）

| 可控点 | 客户端可改对象 | 能否阻断 | 服务端兜底判据 |
|---|---|---|---|
| 切页上报 24 | `reprotExam`(0x93d76c) 调用点、`field_73` 节流、`ChangePageEvent` 订阅 | 可 | **无兜底**（observed：全库仅 2 调用点，无第二来源） |
| 前后台上报 16 | `examResumeCallBack`(0x93db84)、`field_6f` | 可 | 无兜底 |
| 分屏上报 20 | `_listenAppSizeChange`(0xc91d90)、`MultiWindowEvent`、`ReportExamQuitEvent` 闭包、静态 `0xe44` | 可（把 `0xe44` 恒置 false 后 `isSplitScreen(true)` 不再 fire，main.dart:8017） | 无兜底；`open_screen_cuts`/`max_screen_cuts_num`/`cut_count` 由客户端上报驱动（**inferred**） |
| 截屏上报 60 | `DisableScreenshots.onScreenShots` 流、插件 ContentObserver、`field_53` | 可（adb screencap／改目录／取消订阅） | 无兜底（observed：action 60 唯一触发点） |
| 相机无权限 62 | `_listenNoPermissionEvent`(0xc92840)、`CameraNoPermissionEvent` | 可 | 无兜底 |
| 抓拍上报 64 | `AutoCameraPage` 构造条件、`_getExamUploadToken`、`postAutoPhotoUpload`、`field_63`（七牛 token，H5 下发） | 可（三条门禁任一为假即不抓拍；或改写 `field_63`） | 无兜底；服务端以 `app_front_random_snap` 下发期望 |
| VM 上报 96 | `_detectGuangsuVirtualMachine`、`field_af` 守卫、Dart 侧 schemaVersion 校验 | 可；现状已被版本号不一致天然阻断（Java 1 vs Dart 2） | 无兜底（无第二处 VM 上报点） |
| 人脸比对 | `postPhotoImg` 的 `image_url`、硬编码 `has_camera:"1"`、`field_1f` | 可（可传任意已上传图片 URL） | 服务端比对留痕（`face_img`/`face_status`/`is_manual_review`/`max_retry` 由服务端返回） |
| `exam_id`/`terminal`/`app_version`/`is_app` | 上报体字段全部本地构造 | 可改写 | 无签名、无 nonce（observed：请求体无防篡改字段） |
| 60/62/64 的实际落库 | 由考试 H5 发往 `/exam_room/answer_problem` | 可（改 JS 桥 payload／拦截 runJavaScript） | H5 逻辑在服务端页面，APK 内无法证伪（**unverified**） |

### 5.3 明确「未找到」项（observed）

| 项 | 结论 |
|---|---|
| 多指/多点触控检测 | 未找到（`kwscan 多指` 0 命中；无对应 action） |
| 键盘记录/剪贴板监控 | 未找到（jadx 无相关类；Dart 无对应事件） |
| 模拟器检测（除光速） | 未找到（GuangsuRuntimeRules 仅 titan/isulad/csaic 三规则） |
| frida/xposed/root 检测（雨课堂自研） | 未找到（3.5 节；仅极光 SDK 自带 root 字段，不用于监考） |
| 反调试/反注入/完整性校验 | 未找到（MainActivity.java 832 行内无对应逻辑） |
| 本地持久化的监考证据 | 未找到（仅 no_screenshot 插件写 SharedPreferences `screenshot_pref`，含 `screenshot_path`/`was_screenshot_taken`） |
