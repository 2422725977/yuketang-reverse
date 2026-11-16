# live/ —— 只读实测记录（雨课堂）

时间：2026-11-16 20:0x–20:1x（本地时区）。凭证：用户提供的微信扫码网页会话（sessionid + csrftoken）。
纪律：只发 GET、串行、间隔 ≥6s、每次只改一个变量、不并发、不改 UA/IP。

## 请求流水（7 次）

| # | 端点 | 方法 | 结果 | 判读 |
|---|------|------|------|------|
| 0 | /v/course_meta/user_info | GET | 200 `{"msg":"0.0.1","data":{"user_profile":{...}},"success":true}` | 会话有效，拿到 user_id=100254372 / school=重庆理工大学 / school_number=2025450020 / role=2 |
| 1 | /v/course_meta/learning_list/ | GET | 200 `{"msg":"","code":50000,"data":{}}` | 疑似会话/参数被拒 |
| 2 | /v/course_meta/my_courses_top | GET | 200 `{"msg":"","code":50000,"data":{}}` | 同上 |
| 3 | /v/course_meta/learning_list/?page=1&page_size=20 | GET | 50000 | 分页参数不是原因 |
| 4 | /api/v3/user/basic-info | GET | 200 `{"code":50000,"msg":"UNAUTHENTICATED","data":""}` | /api/v3 族要另一套会话 |
| 5 | /api/v3/user/config | GET | 50000 UNAUTHENTICATED | 同上 |
| 6 | /api/v3/user/config（Cookie 追加 csrftoken=） | GET | 50000 UNAUTHENTICATED | 补 csrftoken cookie 无效 |
| 7 | /v/course_meta/user_info（复测，与 #0 同请求头） | GET | **50000**（#0 是 200） | **会话在这期间失效/被轮换** |
| 8 | /v/course_meta/learning_list/ + xtua 头 | GET | 50000 | xtua 不是原因 |

## 结论（observed）

1. `code:50000` + `msg:""` 是 **/v/ 族的“会话无效”返回**，同请求头在 #0 时是 200、在 #7 时变 50000，说明会话在两次请求之间失效（微信扫码会话短命或被服务端轮换）。
2. `/api/v3/*` 族即使会话有效也返回显式 `UNAUTHENTICATED`：网页扫码 cookie 只覆盖 `/v/` 族。App 侧 /api/v3 的会话来自登录流 + 拦截器维护：
   - App::getInterceptor RVA 0x1450ddc：从响应 `set-cookie` 里解析 `csrftoken`，回填请求头 `X-CSRFToken`（0x1450fcc / 0x1451018 / BaseNet::addHeader 0xbde930），并 `saveData("token")`（0x1451074）。
   - 全局头（App::initNet 0x1450b60 起 + 0xc08260 起两处同构 Map）：`Accept: application/json`、`Content-Type: application/json; charset=UTF-8`、`xtbz: ykt`、`x-client: app`、`User-Agent: Android`、`xtua: client=app&tag=<tag>&platform=Android&brand=…&model=…&systemVersion=…&isPhysicalDevice=…&uuid=…&incremental=…&version=…&buildNumber=…`、条件加 `X-UID`（0x145128c）。
3. 因此“拿 lesson_id 走只读 eligibility”这一步在纯网页会话下不成立，需要：a) 新的 App 会话（会话值 + 轮换后的 csrftoken），或 b) 直接用 Frida 只读探针在 App 内观测（零写入，最稳）。

## 需要的输入（任选其一）

- 网页版 https://www.yuketang.cn 打开“我听的课”→ 语文课页面 URL（里面有 classroom_id），或
- 课程内某一节课的 URL / 入场二维码里解出的 lessonId，或
- 重新扫码后的新 sessionid + csrftoken（并允许我以 15s 间隔做 ≤5 次只读 GET）。

## 下一步（拿到输入后）

1. `GET /v/course_meta/learning_list/` 取 classroom_id（该端点返回 LearnLessonBean，字段含 classroom_id/classroom_name/course_id/course_name/role/teacher）。
2. 由 classroom 定位已结束的语文 lesson → lessonId。
3. `GET /api/v3/lesson/location-checkin/eligibility`（只读）观测 canSign / wouldBeLate / pastOfficialEnd / startMs / endMs / lateAfterMs / timeoutMode。
4. 全程不碰 /location-checkin/submit 与 /checkin。

## 追加：用户提供课程页 URL（2026-11-16 20:17）

- URL: https://www.yuketang.cn/lesson/fullscreen/v3/<PHONE>08339584
- 解析：**lessonId = <PHONE>08339584**（19 位雪花号，URL 第四段即 lesson 主键）；该路径是网页版全屏课堂页，v3 为版本号。
- 会话状态：再次探活 /v/course_meta/user_info → 仍为 {"msg":"","code":50000,"data":{}}，**会话仍是死的**，/api/v3/lesson/location-checkin/eligibility 无法调用。
- 已备好只读探针脚本 replay/eligibility_probe.sh（三步：/v/ 探活 → learning_list 取 classroom_id → eligibility?lessonId=…；任一步 50000/UNAUTHENTICATED 立即退出；末尾按白名单字段打印摘要）。
- 待用户提供：重新扫码后的 sessionid（+ csrftoken），或连 adb 走 Frida 只读探针。

