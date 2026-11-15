# 雨课堂 —— 路由表 / 环境开关 / 域名面 板块报告

样本：/Users/xi/Downloads/雨课堂.apk（v1.3.6，com.xuetangx.ykt）
坐标：blutter_out/asm/**（RVA = 文件偏移）；全部条目 observed，除标注外。

---

## 1. 路由表（observed：app_constants.dart 注册的字面量）

| 行号 | 路由 | 说明 |
| --- | --- | --- |
| 181 | `/userLogin` | 登录页（业务码 100000 时 `pushNamedAndRemoveUntil` 到此） |
| 205 | `/userAccountLogin` | 账号/验证码登录 |
| 229 | `/tabHome` | 主页 Tab 框架 |
| 253 | `/userSet` / 277 `/userAbout` / 301 `/msgSet` / 325 `/securitySet` | 设置族 |
| 349 | `/findPasswordPage` | 找回密码 |
| 373 | `/pmMessage` | 私信 |
| 397 | `/courseWarePage` | 课件 |
| 421 | `/examsPage` | 考试列表 |
| 3200 | `/webview` | **所有云侧 H5 的容器**（18 个 H5 全经此页） |
| 3224 | `/shareWebview` | 分享内嵌页 |
| 3248 | `/recordWebview` | 录播内嵌页 |
| 3272 | `/exam` | **考试页**（监考、抓拍、答题都在这里） |
| 3296 | `/danmu` | 弹幕页 |
| 3320 | `/cropAvatar` / 3344 `/receiverCode` / 3368 `/receiverSelfSelect` / 3416 `/receiverJoinFree` / 3440 `/receiverMyGroup` / 3488 `/receiverGroupDetail` / 3560 `/teamMembers` | 课堂扫码/分组族 |
| 3392 | `/message` / 3512 `/msgItemSelect` / 3536 `/tabChangeList` | 消息族 |
| 3464 | `/modifyPassword` | 改密 |

注：注册行号是字面量出现位置，注册函数本体在 app_constants.dart 1900-3550 区间（observed）；不在本表的页面均以 `Navigator.push(MaterialPageRoute)` 直接构造，无命名路由。

## 2. 环境域名族（observed：libapp.so 字符串池全量扫描，29 个 host）

| 域名 | 归属 |
| --- | --- |
| `www.yuketang.cn` | 生产 baseUrl（`baseUrlHost()` 0x86f184 的默认分支） |
| `ykt-envning.rainclassroom.com` / `exam-envning.rainclassroom.com` / `exam-env-example.rainclassroom.com` / `xt-envning.rainclassroom.com` | **测试/联调环境族**（`envning` 关键字 4 命中，全在此族） |
| `changjiang-exam.yuketang.cn` / `huanghe-exam.yuketang.cn` / `tsinghua-exam.yuketang.cn` / `proexam.yuketang.cn` / `examination.xuetangx.com` | **校级/线考试专用域**（考试页与监考回调走这些域） |
| `www.xuetangx.com` | 学堂在线主站（deeplink 白名单之一：`https://www.xuetangx.com/rain`） |
| `qn-sfe.yuketang.cn` / `qn-help.yuketang.cn` / `qn-scd0.yuketang.cn` / `qn-st0.yuketang.cn` / `qn-next.xuetangx.com` / `qn-c27.xuetangx.com` / `proxt-cdn.xuetangx.com` / `upload.qiniup.com` | 七牛上传与静态 CDN（考试抓拍走此族） |
| `view.officeapps.live.com` | 办公文档在线预览（office_preview_page_new.dart 的 InAppWebView） |

## 3. 环境切换与"重绑服务器"的全部入口（observed）

1. **环境位**：`baseUrlHost()`（app_constants.dart:85，RVA 0x86f184 size 0x38）读静态字段 offset 0xd14，真 → `ykt-envning.rainclassroom.com`，假 → `www.yuketang.cn`；该位只在编译期/调试入口被置位（未见运行期 UI 开关）。
2. **代理开关**：`App::initNet` 0x1450b14 段：静态开关 offset 0x178c 为真且代理地址 offset 0x1788 非空 → `BaseNet::setProxy()` 0x1443584（observed）。
3. **deeplink 重绑**：`_MyHomePageState::processLinkParams` 0xc20698 接受 `app://yuketang` / `https://www.xuetangx.com/rain`，读取 `server / serverUrl / code`；serverUrl 分支 → `saveData` → `App::initCurrentServerData`（见 `_board_native.md` §4）。
4. **JS 桥重绑**：`bind_other_env`（app_js_call_flutter.dart:1503/1509）可把 serverUrl 改成任意域名并 logout（见 `_board_jsbridge.md`）。

**含义（inferred）**：1 与 2 是编译期/调试面；**3 与 4 是运行期可达的**，且都不做域名白名单 —— 这是"自建服务端 + 不改包"的唯一路径，也是客户端把会话与身份交给任意域的风险点。

## 4. 调试/内部面清单（observed）

| 面 | 证据 | 现状 |
| --- | --- | --- |
| 调试日志 | `LogUtils._debug`（静态 offset 0x17b0）+ `LogUtils::i` 0x7da6f4 | release 下应为 false；`ykt_bridge_probe.js` 挂 `LogUtils::i` 可直接判 |
| 服务器基址打印 | 字符串 `----serverUrl baseUrl:` | 打印点存在，受 `_debug` 门控 |
| 静态开关 | `LogUtils._debug`(0x17b0)、环境位(0xd14)、代理开关(0x178c)、代理地址(0x1788) | 全在 Dart 静态字段表（THR field_table）；运行期可读不可写（本报告只读立场） |
| 测试包痕迹 | `envning` 域族、`exam-env-example` | 说明同一份代码可在测试环境跑；不影响生产包行为 |

## 5. 与四模块的关系

* 签到：`/receiverJoinFree`、`/receiverCode`（课堂加入）与 `/receiverGroupDetail` 是正常入口；签到本体走接口（见 §3）。
* 作业：`/webview` 容器 + `getJournalH5Url`（见 `_board_h5.md`）。
* 成绩：`/examsPage`、`/exam` + 原生成绩页（见 §5）。
* 作答：`/exam`（考试）、弹幕 `/danmu`。

## 6. 待验证（unverified）

1. `/exam` 页面下监考 action 的完整枚举（由 proctor 板块补齐）；
2. 环境位 0xd14 是否被任何运行期入口（含 deeplink `code` 分支）间接置位；
3. 校级考试域（`*-exam.yuketang.cn`）与主域是否共享同一会话 cookie（影响跨域重放）。
