# 板块 H5：雨课堂云侧 H5 路径全表（ykt / libapp.so）

样本：so/lib/arm64-v8a/libapp.so 21431216 字节，sha256 0277169865af6b0dad103f443a236d7111c6dfa88f63ea40c996629d776a1a26（observed）。
反汇编：blutter_out/asm（2356 个 .dart，blutter 打印的 addr 即 RVA，.text vaddr == 文件偏移 0x760000）。

工具与复跑命令（全部 python3 标准库，只读样本）：

    python3 tools/h5paths.py                       # 提取器: ASCII+UTF-16LE 双解码扫路径型字面量
    python3 tools/h5asm_ctx.py --file artifacts/h5paths_lits.txt --out artifacts/h5asm_ctx.txt
    python3 tools/h5callers.py --lits --out artifacts/h5callers_lits.txt 0xe953cc 0xbd121c 0xbd028c 0xe2b8f4
    python3 tools/h5stats.py                       # 分类计数 / REST 前缀分布

产物：artifacts/h5paths.txt(464 行) · artifacts/h5asm_ctx.txt(154) · artifacts/h5callers.txt(50) · artifacts/h5callers_lits.txt(50) · artifacts/h5paths_lits.txt(58)。
提取统计（observed，h5paths.py 运行时打印）：lines=464 tokens=140988 unique_paths=355 urls=48 hosts=38，耗时 0.486s。

## 1 分类全表

### 1.1 总览（9 类）

| 类别 | 条数 | 判定口径 | 证据 |
|---|---|---|---|
| REST端点 | 183 | 以 /api 开头或 /v/{module}/{verb} 形态 | artifacts/h5paths.txt:6-190 |
| 云侧H5页面 | 18 | .html 结尾，或 /v/index/ · /h5/ · /static/html/ | artifacts/h5paths.txt:191-210 |
| PC端 | 13 | /pc/ 前缀（含 PC 端 SSO 与注册/绑定接口） | artifacts/h5paths.txt:225-239 |
| bindmobile/身份绑定 | 13 | /bindmobile/ 前缀 + /school_name/ + /v/index/bindSchool_list | artifacts/h5paths.txt:240-254 |
| 静态资源 | 12 | 图片/资源前缀（含 8 个七牛 o_1fl5…png） | artifacts/h5paths.txt:211-224 |
| 其他接口(/v、/group、/c27 等旧前缀) | 94 | 旧版 /v/ 业务接口、/group/、/c27/、/m/v2、/mooc-api | artifacts/h5paths.txt:255-350 |
| 非应用噪音(库/命名空间) | 22 | api.flutter.dev / pub.dev / w3.org 等 | artifacts/h5paths.txt:351-374 |
| 域名/主机 | 38 | 独立 host 字面量 | artifacts/h5paths.txt:375-414 |
| 完整URL | 48 | 带 scheme 的整串字面量 | artifacts/h5paths.txt:415-464 |

### 1.2 云侧 H5 页面（18/18 全列，偏移=样本内首次出现字节偏移）

| 路径 | 偏移 | 备注 |
|---|---|---|
| /v/index/course/normalcourse/teaching_lesson_detail/ | 0x001ad66a | 教师课次详情 |
| /v/index/course/normalcourse/learning_lesson_detail/ | 0x0012eebf | 学生课次详情 |
| /v/index/course/normalcourse/teaching_cards_detail/ | 0x00176bab | 教师学习卡片 |
| /v/index/course/normalcourse/learning_cards_detail/ | 0x0008f465 | 学生学习卡片 |
| /v/index/course/normalcourse/teacher_quiz_detail/ | 0x000c2f39 | 云习题详情(教师) |
| /v/index/course/normalcourse/exam/ | 0x0018c5d4 | 考试 |
| /v/index/course/normalcourse/examcover/ | 0x0017e060 | 考试封面 |
| /v/index/course/openplatform/teacher_sydetail/ | 0x000f229e | 开放平台实验(教师) |
| /v/index/course/openplatform/student_sydetail/ | 0x000edadc | 开放平台实验(学生) |
| /v/index/course_v/notice_view/ | 0x001a26d2 | 通知详情 |
| /v/index/course_v/notice_notice_up/ | 0x000ce945 | 通知发布 |
| /v/index/letter/ | 0x000a480a | 私信 |
| /v/index/my_collections?flutterHome=true | 0x001528ba | 我的收藏 |
| /v/index/my_papers?flutterHome=true | 0x001ac574 | 我的试卷 |
| /v/index/mystore | 0x000b521d | 我的资源库 |
| /static/html/tsinghua_bind.html | 0x00097e87 | 清华身份绑定页 |
| /h5/appexam/ | 0x000fcdbe | 考试 H5 |
| /download-android.html | 0x000ee238 | ascii/url（出自完整 URL 的路径部分） |

### 1.3 PC 端（13/13）

| 路径 | 偏移 | 发起函数（文件:行 RVA） |
|---|---|---|
| /pc/webview_sso?session_id= | 0x001b5a3a（artifacts/h5paths.txt:238） | rain/core/utils_function.dart:156 RVA 0x92f6d8 |
| /pc/bind_phone | 0x000e7593 | YuKetang::bindPhone rain/network/yuketang.dart:2901 RVA 0xd1d7d4 |
| /pc/register/bind_email/ | 0x001a4b26 | YuKetang::bindEmail yuketang.dart:2666 RVA 0xd1bb6c |
| /pc/register/send_email_code/ | 0x00139f27 | YuKetang::sendEmailCode yuketang.dart:2779 RVA 0xd1c29c |
| /pc/send_sms_code | 0x000bc7e0 | YuKetang::sendSmsCode yuketang.dart:3154 RVA 0xd1e5f8 |
| /pc/register/set_password/ | 0x0014175f | _ModifyPasswordState::setNewPassword rain/mine/user_modify_password.dart:337 RVA 0xaa5d28 |
| /pc/register/get_user_bind_status/ | 0x00068d6f | 5 处 getAccountStatus()（见 4.3） |
| /pc/apply_close_account?user_id= | 0x001012d0 | _UserDeletePageState::applyCloseAccount rain/mine/user_delete_page.dart:1506 RVA 0xfdd770 |
| /pc/cancel_close_account | 0x001201ab | 3 处（wechat.dart:3566 / check_code_page.dart:7830 / user_account_login.dart:885） |
| /pc/generate_qiniu_token | 0x000841b5 | 4 处（group_discuss_page.dart:14841 等；JsCallFlutter::getToken :18433 RVA 0xbcbabc） |
| /pc/hole_service_notice/ | 0x000c49ef | _HomePageState::getHoleServiceNotice rain/home/lesson/home_page.dart:1953 RVA 0xc75ac8 |
| /pc/user_information | 0x000c4763 | 见 artifacts/h5asm_ctx.txt |
| /pc/web_ppt_config | 0x001b901d | 见 artifacts/h5asm_ctx.txt |

### 1.4 bindmobile / 身份绑定（13/13）

| 路径 | 偏移 | 出现位置（首次） |
|---|---|---|
| /bindmobile/audio-student-unit/ | 0x0013d87f | DataUtil::getJournalH5Url rain/util/data_util.dart:5699 RVA 0xe953cc |
| /bindmobile/video-student-unit/ | 0x0017d3ae | data_util.dart:5583；另 my_receive_page.dart:4582 RVA 0xe96728 |
| /bindmobile/teaching-video-detail/ | 0x000bee43 | data_util.dart:5524 |
| /bindmobile/teaching-audio-detail/* | 0x0014af51 | 仅样本存在，asm 无引用（unverified，见 5.3） |
| /bindmobile/cloud/teacher/exercise/ | 0x001b6c4c | data_util.dart:5285（云习题·教师） |
| /bindmobile/cloud/exercise/cover/ | 0x0018b043 | data_util.dart:5345（云习题封面） |
| /bindmobile/teacher/forum/ | 0x001c26db | data_util.dart:5877 |
| /bindmobile/student/forum/ | 0x001b6ce8 | data_util.dart:5937 |
| /bindmobile/teacher/graph/ | 0x0013cd70 | data_util.dart:5753 |
| /bindmobile/student/graph/ | 0x000b2a67 | data_util.dart:5813 |
| /bindmobile/paperpreview?paperid= | 0x001b509d | courseware_page.dart:9187 RVA 0xe2b4f0 / search_courseware_page.dart:7767 RVA 0xf657dc |
| /school_name/school_name_query | 0x001729c6 | _SearchInputWidgetState::postSearchSchool rain/mine/widget/search_input_widget.dart:440 RVA 0xc9054c |
| /v/index/bindSchool_list | 0x001834e0 | 5 处（见 3.4） |

### 1.5 静态资源（12/12）

| 路径 | 偏移 |
|---|---|
| /uploads/ | 0x001b4ae1 |
| /idphoto/upload/token | 0x000eaa91 |
| /image_cropper.png | 0x00158e30 |
| /fe-proxtassets/onlineexam/nocamera1.png | 0x0006d7f1 |
| /o_1fl5tm537kvl10esc9dhbc1a06t.png | 0x00167aed |
| /o_1fl5tm5373mrjrpaf29sa1f77r.png | 0x000bd2f6 |
| /o_1fl5tm5371uhuidb1kg91jpj9kc10.png | 0x000ddcc2 |
| /o_1fl5tm5371q5bqcl15r8g0bfuhv.png | 0x0014e86b |
| /o_1fl5tm5371iv85gffbok7u1jupu.png | 0x001af638 |
| /o_1fl5tm5371chsp651b4pej01ub11.png | 0x000841ce |
| /o_1fl5tm537174erv9bersva1rdgs.png | 0x000f7a85 |
| /o_1fl5tm5361skdeuu1dgr1apr1vedq.png | 0x00199145 |

### 1.6 REST 端点 183 条：前缀分布（tools/h5stats.py）

| 前缀 | 条数 | 代表条目 |
|---|---|---|
| /api/v3 | 137 | /api/v3/lesson/checkin、/api/v3/lesson/group-event/list、/api/v3/classroom/basic-info?classroom_id= |
| /v/course_meta | 26 | /course_meta/manage_collection_info/ |
| /group/student | 10 | /group/get_classroom_group_list |
| /v/discussion | 8 | /comment/list/ |
| /c27/online_courseware | 6 | /c27/online_courseware/ykt/agent/ |
| /v/quiz | 5 | /api/quiz/quiz_results_detail/ |
| /m/v2 · /v2/api · /mobile-app/api · /mooc-api/v1 · /v1/lms · /v/lesson · /v/exam · /v/user · /online_proctor/stu | 2-4 各 | /mooc-api/v1、/online_proctor/stu… |

### 1.7 其他接口 94 条（旧前缀）代表

| 路径 | 偏移 |
|---|---|
| /c27/online_courseware/ykt/system_message/?client_type=1 | 0x000d6516 |
| /ai-workspace/chatbot-mobile/ | 0x0007faf8 |
| /authorize/bind?id= | 0x001770eb |
| /authorize/account?from=setting | 0x000b0685 |
| /exam_room/answer_problem | 0x001a5a9d |
| 其余 89 条 | 见 artifacts/h5paths.txt:255-350 |

### 1.8 域名/主机 38 条（全列，来自 artifacts/h5paths.txt:375-414）

yuketang.cn 系：www(×3) · changjiang · pro · proexam · changjiang-exam · tsinghua-exam · huanghe · huanghe-exam · qn-scd0 · qn-sfe(×8) · qn-st0(×2) · qn-v · qn-help
xuetangx.com 系：www(×6) · qn-next(×2) · qn-c27 · proxt-cdn · examination
对象存储/其它：oss-cn-beijing.aliyuncs.com · oss-cn-shenzhen.aliyuncs.com · upload.qiniup.com · view.officeapps.live.com · meeting.tencent.com · beian.miit.gov.cn
环境域名（rainclassroom.com）：ykt-envning · ykt-env-example · exam-envning · exam-env-example · xt-envning
噪音：api.flutter.dev · dart.io · docs.flutter.dev · github.com · pub.dev · www.w3.org(×7) · www.ibm.com · www.youtube.com · n

## 2 H5 的加载机制（基址 → 包装 → 路由 → WebView → JS 桥）

### 2.1 基址（observed）

| 事实 | 证据 |
|---|---|
| 全局基址 = 插值 https:// + baseUrlHost，函数 baseUrl() | blutter_out/asm/rain/core/app_constants.dart:35，RVA 0x86f108；:53 处 r16 = https://，:64-68 处加载 Field baseUrlHost(offset 0xd20)，:74-75 调 _StringBase::_interpolate |
| 主机取值函数 baseUrlHost() | app_constants.dart:85，RVA 0x86f184；:93 返回 www.yuketang.cn，:97 返回 ykt-envning.rainclassroom.com（环境开关） |
| 同一主机字面量另在 DataUtil::initServerData | blutter_out/asm/rain/util/data_util.dart:228，RVA 0x7dad1c |
| H5/资源专用 CDN 基址字面量 | app_constants.dart:755 https://qn-scd0.yuketang.cn/ · :2962 https://www.xuetangx.com/rain/ · :3060 https://qn-next.xuetangx.com/ · :3064 https://qn-c27.xuetangx.com/ |

结论（inferred）：1.2/1.4 中的 H5 相对路径在运行时由 https://{baseUrlHost} + path 拼成；domain 常量只是同一批主机的多环境副本。

### 2.2 PC 端 SSO 包装（observed，H5 抓包最关键的入口）

rain/core/utils_function.dart:156 RVA 0x92f6d8 的 getUrl() 单调拼接：

    0x92f784 r16 = "https://" ; 0x92f798 r16 = "/pc/webview_sso?session_id=" ; 0x92f7b0 r16 = "&sid=" ; 0x92f7c8 r16 = "&next="

即 完整 URL = https://{host}/pc/webview_sso?session_id=…&sid=…&next={原始 H5 地址}。调用点 86 处（python3 tools/h5callers.py 0x92f6d8），覆盖 wechat.dart:3952、app_tab_frame.dart:2718/2984/18505、player_detail.dart:14880/14938、audio_player_detail.dart:5748、my_publish_page.dart:10394、chapter_widget.dart:3462 等。

### 2.3 路由与 WebView 承载链（observed）

| 环节 | 证据 |
|---|---|
| 路由表注册 /webview（64 项数组） | rain/core/app_constants.dart:3200 argumentsRoutes() 首行 addr RVA 0x11c1e9c；:3200-3201 写入 \"/webview\"（指令 0x11c1ec4，[pp+0xcc00]） |
| 该路由 builder 闭包调 getWebViewPageWidget | app_constants.dart:6023 RVA 0x11c3e80 处 bl #0xbd121c |
| getWebViewPageWidget 定义 | app_constants.dart:1887 声明、:1888 addr 头 RVA 0xbd121c size 0xad0（内部闭包 0xbd11a0） |
| 统一跳转入口 NavigatorUtils.goH5Detail | rain/util/navigator_utils.dart:3973 RVA 0xe2b8f4，:4000 处 bl #0xbd121c |
| WebView 组件自身 | rain/xuetang_webview/xuetang_webview.dart:1333 _WebViewState.initState RVA 0xb992e0 |
| 课堂日志 H5 widget | getClassroomLogH5Widget app_constants.dart:1710 RVA 0xbd028c；打开者 navigator_utils.dart:2471 goClassroomLogH5Page RVA 0xbcfdfc |

### 2.4 JS 桥：H5 回调原生的能力面（observed）

rain/ui_widget/app_js_call_flutter.dart 内以字符串注册 handler 名，再分发到 Dart 方法：

| JS handler 名（字符串位置） | Dart 方法 RVA |
|---|---|
| closePage（:721） | JsCallFlutter::closePage 0xbd2b5c（调用点 :894/:1123） |
| getTokenData（:2099） | JsCallFlutter::getTokenData 0xbc5024（调用点 :2474） |
| getAppDeviceInfo（:3300） | JsCallFlutter::getAppDeviceInfo 0xbae964（调用点 :3310；定义 :6318） |
| uploadFile（:1742） | JsCallFlutter::uploadFile 0xbc676c |
| uploadFilesChatbotMobile（:2476） | postGetChatbotMobileDataToJS 0xbc2f08 |
| _sendAgentChunkToH5 | 定义 :7270 RVA 0xbb0324（调用点 :7201/:7637） |
| passToH5（闭包 :6179） | JsCallFlutter::passToH5 0xbae398 |
| postImageDataToJS | 0xbc11a4（调用点 :13205） |
| postMultipleImagesDataToJS / postHomeworkDataToJS / appGetLocatonInfo | 0xbb2328 / 0xbc6004 / 0xe89c34 |
| ShareJsCallFlutter（rain/home/course/share_webview_page.dart）nativeCallJs / bindSuccess / closePage | 0xbcc210 / 0xc7e4ec / 0xc7e868（_WebViewState.initState 0xc7d9d8） |

## 3 五类功能面的 H5 打开函数

### 3.1 作业 / 云习题（作业类功能确实以 H5 承载）

| H5 路径（生成处） | 打开（调用点） |
|---|---|
| /bindmobile/cloud/teacher/exercise/（data_util.dart:5285 RVA 0xe953cc） | _MyPublishPageState::goDetailPage my_publish_page.dart:10391/10650/11203/11456 RVA 0xe94334；_ChapterWidgetState::goDetailPage chapter_widget.dart:3459/3766 RVA 0xf4df1c |
| /bindmobile/cloud/exercise/cover/（data_util.dart:5345） | _MyReceivePageState::goDetailPage my_receive_page.dart:5987/6448/7547/7912 RVA 0xe9709c；_SearchPageState::goDetailPage search_page.dart:4188/4641 RVA 0xf53408 |
| /bindmobile/paperpreview?paperid=（非 getJournalH5Url） | _CourseWarePageState::clickItemUpload courseware_page.dart:9187 RVA 0xe2b4f0 → goH5Detail 0xe2b8f4（:9315） |
| 作业详情与原生互传 | JsCallFlutter::postHomeworkDataToJS 0xbc6004；postImageDataToJS 0xbc11a4；uploadFile 0xbc676c |

### 3.2 成绩 / 成绩单

| 结论 | 证据 |
|---|---|
| 未找到成绩/成绩单的 H5 路径字面量（355 条唯一路径中无 score/grade 型路径） | artifacts/h5paths.txt 全文；grep -icE score|grade|assess 仅命中 9 条且全为 REST（/api/v3/lesson/assess/score/changed 等） |
| 成绩相关为原生页面 | asm 文件：rain/receiver_page/score_main_points.dart · score_each_other_page.dart · rain/remote_control/page/exams_storage_page/exams_score_detail_page.dart |
| 中文“成绩单”字面量存在但非路径上下文 | 样本偏移 0x1af51a 前后为混排文本，非 /v/index 形态（观察） |

### 3.3 考试

| H5 路径 | 打开（调用点） |
|---|---|
| /v/index/course/normalcourse/exam/（data_util.dart:4915） | _CurrentLessonWidgetState::_onCurClassItemTap current_lesson_widget.dart:399 RVA 0xcd0ec4；_TopAppBarState 闭包 top_app_bar.dart:2388 RVA 0x10e9538；TabFrameState 闭包 app_tab_frame.dart:2849 RVA 0x92de98 |
| /v/index/course/normalcourse/examcover/（data_util.dart:4967） | current_lesson_widget.dart:464 RVA 0xcd0ec4；top_app_bar.dart:2453；app_tab_frame.dart:2914 |
| /h5/appexam/（exam_info_page.dart:3607 RVA 0xfff7c8） | _ExamInfoPageState 匿名闭包（ExamGetTokenBean 回调，取 token 后拼 H5） |
| /pc/webview_sso?session_id=（utils_function.dart:156） | _ExamPaperPageState::enterExam exam_paper_page.dart:767 RVA 0x1013180；_ExamInfoPageState::examinationIntegrityOnventionCallback exam_info_page.dart:7265 RVA 0x100272c |
| 考试身份认证照片上传 | /idphoto/upload/token：_ExamPageState::_getExamUploadToken exam_page.dart:2991 RVA 0xc92db8；exam_authentication_album_page.dart:133 RVA 0xd21e84 |

### 3.4 身份绑定

| 入口 | 打开（调用点） |
|---|---|
| /v/index/bindSchool_list | _MinePageState::bindType mine.dart:4900 RVA 0xfcfbd4 → getWebViewPageWidget（:5013 RVA 0xfcfbd4）；_PageState::bindType personal_information_detail_page.dart:1671 RVA 0xfd7394（widget 调用 :1784）；_JoinClassroomDialogState::bindType join_classroom_dialog.dart:3037 RVA 0xf9da40 |
| 绑定成功回流 | ShareJsCallFlutter::bindSuccess share_webview_page.dart:844 RVA 0xc7e4ec（且 :945 走 /webview）；JsCallFlutter::closePage app_js_call_flutter.dart:19912 RVA 0xbd2b5c |
| /static/html/tsinghua_bind.html | _CheckCodePageState::goBindPage check_code_page.dart:100 RVA 0xaa7f64（:203 走 /webview）；WechatService::goBindPage wechat.dart:3942 RVA 0xc06514（:3952 走 goH5Detail 0xe2b8f4、:4033 走 /webview） |
| /school_name/school_name_query | _SearchInputWidgetState::postSearchSchool search_input_widget.dart:440 RVA 0xc9054c |

### 3.5 课程回放

| 事实 | 证据 |
|---|---|
| 回放/课次详情 H5：学生 /v/index/course/normalcourse/learning_lesson_detail/ | data_util.dart:4595 RVA 0xe953cc；打开者 join_classroom_dialog.dart:3466 RVA 0xf9dc88、join_classroom_page.dart:2959 RVA 0xfa15d8 |
| 教师侧 /v/index/course/normalcourse/teaching_lesson_detail/ | data_util.dart:4560；join_classroom_dialog.dart:3412、join_classroom_page.dart:2905 |
| “观看回放/直播回放”文案属 i18n key CourseAction_LiveUnit_ReturnWatch | rain/generated/intl/messages_zh_CN.dart:18690（key）/:18695（值 观看回放），同文件 :19981/:34597 为 直播回放 |
| 视频播放本身为原生实现（非 H5） | rain/course/play/player_detail.dart:7848 RVA 0xc4c0d8 处回调文案 LivePlayBack currentPlayUrl；同文件 :14880/:14938 用 SSO getUrl；asm/flutter_video_player/** 为独立播放器库 |
| 直播参数接口 | /api/v3/lesson/live/get-info?live_id=（REST 表）；/api/v3/lesson/live/new/get-params-after-class |

（3.5 中「learning/teaching_lesson_detail 承载回放内容」为 inferred：仅证明该 H5 由课次详情的打开函数发起。observed 部分为路径、i18n key 与原生回调。）

## 4 H5 开页调用点明细

### 4.1 getWebViewPageWidget（0xbd121c）29 个调用点中可直接归因的入口

| 文件:行 | 调用者 RVA | 调用者 |
|---|---|---|
| core/utils_function.dart:1587 | 0xc269b0 | SafeArea 闭包（userAgent 注入，:1587 arg_lit [pp+0xcbf8] userAgent） |
| mine/mine.dart:3697 | 0xfceea0 | _MinePageState::help |
| mine/mine.dart:4567 | 0xfcf708 | _MinePageState::myCollect |
| mine/user_set.dart:2801/3057/3425 | 0xfe9228/0xfe94c4/0xfe9874 | privateProtocol / protocol / Shared_Information_List |
| message/widget/pm_list_widget.dart:3468 | 0xe85298 | _PmListWidgetState::goWebPage |
| message/widget/comment_list_widget.dart:5079 | 0xe7ed98 | _CommentListWidgetState::goWebPage |
| message/widget/notification_list_widget_new.dart:6848 | 0xe82f68 | _NotificationListWidgetState::goWebPage |
| home/lesson/more_widget.dart:3328/3774 | 0xe6d588 | MoreWidget 闭包 |
| dongtai/pages/my_receive_page.dart:5143 | 0xe96d64 | _MyReceivePageState::goWebPage |
| dongtai/pages/chapter_widget.dart:2526/3575/4834 | 0xf4db24/0xf4df1c/0xf4f374 | _ChapterWidgetState |
| mine/personal_information_detail_page.dart:1784 | 0xfd7394 | _PageState::bindType |
| mine/user_security_set.dart:4070 | 0xfe6de8 | enterTencentMeeting |
| util/navigator_utils.dart:4000 | 0xe2b8f4 | NavigatorUtils::goH5Detail |
| 其余（dongtai 详情页、app_constants 路由 builder） | — | 见 artifacts/h5callers_lits.txt |

### 4.2 getJournalH5Url（0xe953cc）15 个调用点（全部是列表页的 goDetailPage 系）

| 文件:行（调用者 RVA） | 函数 |
|---|---|
| dongtai/pages/my_publish_page.dart:10391/10650/11203/11456（0xe94334） | _MyPublishPageState::goDetailPage |
| dongtai/pages/my_receive_page.dart:5987/6448/7547/7912（0xe9709c） | _MyReceivePageState::goDetailPage |
| dongtai/pages/chapter_widget.dart:3459/3766（0xf4df1c） | _ChapterWidgetState::goDetailPage |
| dongtai/pages/search_page.dart:4188/4641（0xf53408） | _SearchPageState::goDetailPage |
| home/teach_journal/lot_page.dart:1972（0xfb8f74） | _LotPageState 闭包；同类 :2129（0xfb91d8）走 goH5Detail |

### 4.3 其它可复用的锚点

| 目标 | RVA | 文件:行 |
|---|---|---|
| NavigatorUtils::goH5Detail | 0xe2b8f4 | rain/util/navigator_utils.dart:3973（调用点 2 处：courseware_page.dart:9315、search_courseware_page.dart:7902） |
| getClassroomLogH5Widget | 0xbd028c | rain/core/app_constants.dart:1710（调用者 3 处见 artifacts/h5callers.txt） |
| yuketang.dart 账号类接口宿主 | 0xd1bb6c/0xd1c29c/0xd1d7d4/0xd1e5f8 | bindEmail:2666 / sendEmailCode:2779 / bindPhone:2901 / sendSmsCode:3154 |

## 5 结论

### 5.1 完全落在 H5 的功能面（客户端无原生实现）

判据：这些页面的地址只由 DataUtil::getJournalH5Url（data_util.dart:4351 RVA 0xe953cc）在运行时生成，客户端侧没有对应原生页面文件；打开动作一律经 getWebViewPageWidget（0xbd121c）。

| 功能面 | H5 路径 |
|---|---|
| 云习题（教师/学生）+ 封面 | /bindmobile/cloud/teacher/exercise/ · /bindmobile/cloud/exercise/cover/ |
| 教学/学习单元（视频、音频、卡片、课次详情） | /bindmobile/teaching-video-detail/ · /bindmobile/audio-student-unit/ · /bindmobile/video-student-unit/ · /v/index/course/normalcourse/{teaching,learning}_cards_detail/ · {teaching,learning}_lesson_detail/ |
| 考试与考试封面 | /v/index/course/normalcourse/exam/ · examcover/ · /h5/appexam/ |
| 通知（查看/发布） | /v/index/course_v/notice_view/ · notice_notice_up/ |
| 论坛（教师/学生）与知识图谱 | /bindmobile/{teacher,student}/forum/ · {teacher,student}/graph/ |
| 开放平台实验 | /v/index/course/openplatform/{teacher,student}_sydetail/ |
| 我的收藏 / 我的试卷 / 资源库 / 私信 | /v/index/my_collections · my_papers（均带 flutterHome=true） · mystore · letter/ |
| 身份绑定 | /v/index/bindSchool_list · /static/html/tsinghua_bind.html |
| PC 端能力（SSO 与账号） | /pc/webview_sso?session_id= 及 1.3 其余 12 条 |

### 5.2 抓包 / 重放应盯的 URL

拼接规则（observed 组成件）：完整 URL = https://{baseUrlHost} + {H5 相对路径}，或外层再套 PC SSO：https://{host}/pc/webview_sso?session_id=SESSION&sid=SID&next={urlencode(H5 URL)}（utils_function.dart:156）。
baseUrlHost 取值 www.yuketang.cn（默认）或环境域名（app_constants.dart:85-98）。

| 优先级 | URL 模板 | 说明 |
|---|---|---|
| P0 | https://www.yuketang.cn/v/index/course/normalcourse/{teaching,learning}_lesson_detail/?... | 课次详情（作业/回放内容入口） |
| P0 | https://www.yuketang.cn/bindmobile/cloud/{teacher/exercise,exercise/cover}/... | 云习题 |
| P0 | https://www.yuketang.cn/pc/webview_sso?session_id=SESSION&sid=SID&next=NEXT | 所有 H5 的统一 SSO 起点，最容易观察 session 语义 |
| P1 | https://www.yuketang.cn/v/index/course/normalcourse/{exam,examcover}/... 与 /h5/appexam/ | 考试链路（配合 /idphoto/upload/token） |
| P1 | https://www.yuketang.cn/v/index/bindSchool_list · /school_name/school_name_query · /static/html/tsinghua_bind.html | 身份绑定三件套 |
| P1 | https://www.yuketang.cn/v/index/{my_collections,my_papers,mystore,letter/} | 个人资产页 |
| P2 | https://{base}/bindmobile/{teacher,student}/{forum,graph}/、/bindmobile/paperpreview?paperid= | 论坛/图谱/试卷预览 |
| P2 | https://{base}/pc/{bind_phone,register/bind_email,send_sms_code,register/get_user_bind_status,generate_qiniu_token,apply_close_account,cancel_close_account,hole_service_notice} | PC 账号面 |
| REST 侧 | https://{base}/api/v3/lesson/**（137 条主体）、/v/course_meta/**（26）、/group/student/**（10） | 见 artifacts/h5paths.txt:6-190 |

抓包要点（inferred from 2.4）：H5 内的 XHR 走 WebView cookie 而非 App 的 Authorization；H5 需要 token/设备信息时会回调 getTokenData/getAppDeviceInfo/uploadFile，因此只重放 H5 的 XHR 可能需要先用 /pc/webview_sso 换到 session。

### 5.3 未找到 / 未验证

| 项 | 状态 | 说明 |
|---|---|---|
| 成绩/成绩单 H5 路径 | 未找到 | 355 条唯一路径中无 score/grade 型 H5；成绩走原生页面 + /api/v3/lesson/assess/** |
| /bindmobile/teaching-audio-detail/* | unverified | 字符串存在于样本偏移 0x0014af51，但 blutter_out/asm 内无任何引用（h5asm_ctx.py 双通道 58 条中唯一未命中） |
| /pc/user_information · /pc/web_ppt_config | observed | 命中 asm，但报告未展开其调用链（见 artifacts/h5asm_ctx.txt） |
| snapshots/hash 之外的私有域 | 未找到 | 未发现 *.yuketang.cn 之外的业务域承载 H5（38 个 host 已全列） |

## 6 复核用最小命令集

    cd /Users/xi/Documents/deepseek-harness/ctf/ykt
    python3 tools/h5paths.py
    python3 tools/h5stats.py
    python3 tools/h5asm_ctx.py --file artifacts/h5paths_lits.txt --out artifacts/h5asm_ctx.txt
    python3 tools/h5callers.py --lits --out artifacts/h5callers_lits.txt 0xe953cc 0xbd121c 0xbd028c 0xe2b8f4 0x92f6d8
    grep -n 'www.yuketang.cn' blutter_out/asm/rain/core/app_constants.dart
