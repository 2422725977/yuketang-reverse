# 雨课堂 —— 原生层 / Manifest / WebView / TLS 姿态 板块报告

样本：/Users/xi/Downloads/雨课堂.apk（sha256 bb777dee…5b2c61），包名 com.xuetangx.ykt
反编译源：jadx/sources（18800 个 .java/.kt/.xml）、jadx/resources（AndroidManifest.xml、res/）
Dart 侧坐标：blutter_out/asm/**（RVA = 文件偏移，运行时地址 = module base + RVA）
所有条目按 **observed / inferred / unverified** 标注；本节断言可用 tools/javascan.py、tools/manifest_export.py 复现。

---

## 1. AndroidManifest 事实表（observed）

| 项 | 值 |
|---|---|
| package | com.xuetangx.ykt |
| versionName / versionCode | 1.3.6 / 1900 |
| minSdk / targetSdk / compileSdk | 29 / 36 / 34 |
| usesCleartextTraffic | **true**（AndroidManifest.xml:136） |
| networkSecurityConfig | @xml/network_security_config（:137） |
| 主入口 | com.xuetangx.ykt.MainActivity，exported=true，scheme **app://yuketang** |
| exported 组件总数 | 9（1 activity + 4 receiver/service + 华为推送 provider；余为友盟/极光/OPPO/vivo 推送组件） |
| 敏感权限 | REQUEST_INSTALL_PACKAGES、SYSTEM_ALERT_WINDOW、CAMERA、RECORD_AUDIO、MODIFY_AUDIO_SETTINGS、WIFI/CHANGE_WIFI_STATE、READ_MEDIA_IMAGES/VIDEO、READ/WRITE_EXTERNAL_STORAGE |

res/xml/network_security_config.xml 全文（observed；只列 system 信任锚，无 user 锚）：

    <network-security-config>
      <base-config cleartextTrafficPermitted="true">
        <trust-anchors><certificates src="system"/></trust-anchors>
      </base-config>
    </network-security-config>

## 2. 网络与 TLS 姿态 —— 对测试的含义（observed）

* Java 侧全树搜索：X509TrustManager / HostnameVerifier 命中 396 / 179 处，**全部落在第三方 SDK**（cn.jiguang.*、cn.jpush.*、com.umeng.*、com.huawei.secure.*、okhttp3 内部），**com.xuetangx.ykt 自身代码 0 命中**。
* okhttp3.CertificatePinner 在 sources 下 74 处，全部在该类自身与 androidx；**无任何 app 包代码引用** → 客户端未启用证书锁定（pinning）。
* Dart 侧（libapp.so 反汇编）搜索 onBadCertificate / badCertificateCallback / SecurityContext / setTrustedCertificates：**全部 0 命中** → Flutter 侧没有自定义信任链或"忽略证书错误"逻辑。
* HttpClient 出现在 dio/src/adapters/io_adapter.dart、http/src/io_client.dart、extended_image_library、rain/websocket/ws_connector.dart、rain/remote_control/page/location/location_sign_page.dart —— 业务流量全走默认 Dart HttpClient（系统信任链）。

**结论（inferred）**：本 App 既没有 pinning，也没有自签信任或"忽略错误"逻辑，且 Manifest 显式放行明文。因此对**抓包与中间人观测**：

1. 装上系统级 CA 即可解密全部 HTTPS（原生 + H5 + wss），**不需要 Frida unpinning、不需要改证书校验代码**；
2. 明文 http 端点与 WebView 内非 TLS 资源也被允许；
3. 反向含义：app 端不存在任何"环境可信"的密码学前提，服务端不能依赖客户端做完整性保证（与主报告 §1 信任边界一致：所有裁决都在服务端）。

## 3. WebView 栈与桥注入点（observed）

| 组件 | 出现位置 | 说明 |
|---|---|---|
| webview_flutter（WebViewWidget / WebViewController） | blutter_out/asm/rain/receiver_page/exam_page.dart(38 引用)、xuetang_webview/xuetang_webview.dart(34)、rain/ui_widget/study_partner_webview.dart(30)、rain/home/course/share_webview_page.dart(24)、rain/home/teach_journal/classroomlog_h5_page.dart(37) | 主力 WebView 实现 |
| flutter_inappwebview（InAppWebView + InAppWebViewSettings） | rain/home/teach_journal/office_preview_page_new.dart（5 处 InAppWebView、6 处 Settings） | 仅办公文档预览页 |
| flutter_tencent_captcha | sources/org/leanflutter/plugins/flutter_tencent_captcha/TencentCaptchaActivity.java:82/85（addJavascriptInterface + setJavaScriptEnabled） | 腾讯验证码原生层 |
| 华为安全 WebView | sources/com/huawei/secure/android/common/webview/{SafeWebView,SafeWebSettings}.java（onReceivedSslError → WebViewSSLCheckThread.proceed） | 华为 SDK 自带"继续 SSL 错误"实现 |

注入口与桥名见 report/_board_jsbridge.md（通道名唯一 JsCallFlutter，6 处注入，四个独立 dispatcher）。原生层只有插件默认配置（javaScriptEnabled=true），**业务桥面完全由 Dart 侧建立**（observed：Java 侧 addJavascriptInterface 仅 4 处，均在插件/SDK 内）。

## 4. Deeplink / App Links 面（observed）

_MyHomePageState::initUniLink **RVA 0xc204f4**（rain/main.dart:2247）：

    0xc2051c  bl 0xc20b68   [package:uni_links/uni_links.dart] ::linkStream
    0xc20580  bl 0xc20ac8   ::getInitialLink
    0xc205d8  bl 0x790fdc   [dart:core] Uri::parse
    0xc205e8  bl 0xc20698   _MyHomePageState::processLinkParams

_MyHomePageState::processLinkParams **RVA 0xc20698**（rain/main.dart:2397）—— 唯一的外来 URI 解析点：

* 接受条件（0xc20c38 / 0xc20c50 两次 _StringBase::startsWith）：**"app://yuketang"** 或 **"https://www.xuetangx.com/rain"**；
* 打印 "got link: "、"+++++++++++initial link App().h5toAppParams: "；
* 读取的 query 键只有三个（pp 字面量实测）：**server**、**serverUrl**、**code**；
* server/serverUrl 分支调用链（observed）：TabFrameState::getServerUrl → xuetang_base_utils::saveData（持久化）→ App::initCurrentServerData；
* code 分支：构造 H5ToAppParams（size=0x10）→ EventBus::fire（交回 H5→App 通道）；
* 分支先后顺序与 App::isLogin 前置条件：**unverified**（需动态单步确认）。

**含义（inferred）**：app://yuketang?serverUrl=<任意域名> 可让客户端把 baseUrl 指向任意外部域（与 _board_jsbridge.md 的 bind_other_env 同源能力），随后 App::initCurrentServerData 重建网络层。这是"环境重绑"的第二个入口，也是测试自建服务端时最省事的开关。

## 5. 反调试 / 反注入姿态（observed 为"未命中"）

| 检测面 | Java 层结果 | Dart 层结果 |
|---|---|---|
| Frida（frida / gum-js-loop / linjector） | **0 命中** | GuangsuRuntimeRules 内无 frida 关键字 |
| Xposed（de.robv.android.xposed 等） | **0 命中** | 同上无 |
| 调试器（FLAG_DEBUGGABLE / isDebuggerConnected / waitingForDebugger） | 仅 cn/jiguang/ak/a.java:106（极光 SDK） | — |
| root（su 路径 / test-keys / RootBeer） | 19 命中，全部在 cn.jiguang.*、com.umeng.*、com.tencent.bugly.*、kotlin.io.* | — |
| 模拟器（goldfish / ranchu / isEmulator） | 34 命中，全部在 cn.jiguang.*、androidx.camera.* | — |
| 光速虚拟机 / 容器 | — | _detectGuangsuVirtualMachine RVA 0xc96f90 size 0x168（采 Build.* 与 /proc/*） |
| getRunningAppProcesses | 10 命中，全在 huawei HMS / tencent liteav | — |

**结论（observed + inferred）**：App 自身没有反调试、反注入、反 Frida 代码；仅存的 root/模拟器判定来自推送与统计 SDK（风控打分用），以及 Dart 侧针对"光速虚拟机"这一种容器的检测。因此 Frida 只读探针（hooks/ykt_hooks.js、ykt_checkin_probe.js、ykt_ws_probe.js）在本样本上**不需要绕过任何自研检测**即可加载；实际限制来自第三方 SDK 与服务端行为风控（埋点/异常登录），不是客户端反注入。

## 6. 原生库清单（jadx/sources + lib/，observed）

业务相关：libapp.so（Dart AOT，全部业务逻辑）、libflutter.so（banner 3.11.5 stable，决定 blutter/aotopsy 版本选择）、图片与音视频（tencent liteav、thumbplayer、ijk）、扫码（huawei scankit + opencv）、推送（jiguang/jpush、华为、友盟）、umeng 统计、bugly 崩溃。**无商业加固痕迹**（无 360/梆梆/SecShell/libjiagu，observed）。

## 7. 工具（本板块新增，均已跑通）

* tools/javascan.py —— 扫 jadx 全树 25 类正则（WebView 配置、SSL/TrustManager、加固、反调试、反注入、root/模拟器），输出 文件:行。18800 文件全扫约 20 秒。
* tools/manifest_export.py —— 解析 AndroidManifest.xml，导出 exported / 带 scheme 的组件表。

## 8. 待验证（unverified）

1. 服务端是否对自定义 User-Agent（非 "Android flexApp Mobile"）做风控 —— 影响自建客户端可行性；
2. deeplink 的 code 参数是否真能换会话（扫码登录回调链路，见主报告 §2.4 登录端点表）；
3. app://yuketang?serverUrl= 重绑后是否有域名白名单（客户端未见白名单，服务端未测）。
