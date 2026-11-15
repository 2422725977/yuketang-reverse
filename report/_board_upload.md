# 雨课堂 APK 上传链路板块报告（文件直传 / 头像 / 考试抓拍）

- 样本：/Users/xi/Documents/deepseek-harness/ctf/ykt/so/lib/arm64-v8a/libapp.so（Dart AOT）
- 反汇编：blutter_out/asm/**（blutter 打印的 addr 即 RVA，.text vaddr==文件偏移 0x760000）
- 证据标注：observed = 本报告从 asm/pp/字符串中直接读到；inferred = 由多处 observed 推出；unverified = 未找到直接证据
- 证据粒度：`文件:行号` + `RVA 0x…`（必要时加 `字符串 pp+0x…`）

## 0. 结论摘要（先看这里）

| # | 结论 | 证据 | 置信 |
|---|---|---|---|
| 1 | 作业附件的 OSS 直传**完全依赖 H5 先取 STS**：Flutter 只把 `{"upload": bean.data.upload}` 交给 WebView 的 `callTokenJS`，H5 去 `tokenUrl` 取 `credentials{AccessKeyId,AccessKeySecret,SecurityToken,Expiration,BucketName,UploadDir}` 再回调 `getTokenData` | app_js_call_flutter.dart:17912-17986（RVA 0xbc676c/0xbae4f0）、:2097-2475 | observed |
| 2 | 客户端**能自定对象 Key（文件名）**但**不能自定 Bucket/Endpoint/AK/SK**：Key = 本地文件路径最后一段（不 sanitize，不追加随机数）；bucket 来自服务端下发，endpoint 硬编码 | file_upload_manager.dart:93-101、aliyunoss_config.dart:178 | observed |
| 3 | 考试抓拍走**七牛**而非 OSS：token 由 `/mobile-app/api/qiniu-token` 下发，上传后拼 `CDN前缀 + "/" + key` 再经 WebView `callH5Methods` 回报 `/exam_room/answer_problem` | exam_page.dart:3401-3537、19383-19633、19656-19930 | observed |

---

## 1. JS 桥调用契约（app_js_call_flutter.dart）

### 1.1 `JsCallFlutter::getTokenData` RVA 0xbc5024（size 0x884，行 15793-16490）

**签名**（6 参 + this，async → Future<void?>）：

| 位置 | 寄存器 | 形参 | 来源（H5 消息体 msg） | 字符串锚点 |
|---|---|---|---|---|
| this | r1 | JsCallFlutter | — | — |
| p1 | r2 | AccessKeyId | msg["credentials"]["AccessKeyId"] | 行 2130 |
| p2 | r3 | AccessKeySecret | msg["credentials"]["AccessKeySecret"] | 行 2182 |
| p3 | r5 | BucketName | msg["credentials"]["BucketName"] | 行 2286 |
| p4 | r6 | cdn_host | msg["cdn_host"] | 行 2430（键） |
| p5 | r7 | SecurityToken | msg["credentials"]["SecurityToken"] | 行 2390 |
| p6 | stack(fp+0x10) | UploadDir | msg["credentials"]["UploadDir"] | 行 2338 |

- 调用点唯一：app_js_call_flutter.dart:2465-2474（RVA 0xba8a88），寄存器序 x1=this, x2=AK, x3=SK, x5=Bucket, x6=cdn_host, x7=SecurityToken, 栈=UploadDir — observed。
- `Expiration`（行 2234）被读出存 fp-0xd0，**未进入 getTokenData 实参**；`cdn_host` 存 fp-0xf0 后作为 r6 传入，但 fp-0x110 在 RVA 0xbc5134 被匿名闭包覆盖，uploader 的 r6 实际取自 fp-0xe8（=UploadDir）→ **cdn_host 未进入 AliyunOssConfig**（inferred，见 §2.3）。
- 内部流程：
  1. 0xbc50a8 `closeLoadingDialog()`（RVA 0xbb23f8）。
  2. 0xbbec74 `AllocateOSSFileUploaderStub` → 0xbb22dc 构造；0xbc5124 现场建匿名闭包 0xbc61e4 作 OSS 事件回调。
  3. 0xbc51b0 `OSSFileUploader::pickFile`（0xbc4ad8），allowTypes 字面量（行 15935，pp+0x388a8）：
     `.pdf,.doc,.docx,.wps,.pages,.xls,.xlsx,.et,.csv,.numbers,.ppt,.pptx,.key,.txt,.rtf,.bmp,.tif,.gif,.zip,.mp3,.wav,.mov,.mp4,.wmv`
  4. `XFile::length` 取长度；<=0 → print "请求完成" → dispose 返回。
  5. 扩展名判定（行 16101-16131）取 "`.` 切分最后一段" 与 mp4/mov/wmv 比较；**比较结果未被后续分支消费**（inferred：死代码）。
  6. 上限：this.field_37==1 → 0x40000000=1GiB，超出 toast "附件大小超过1G"（0xbc5434, pp+0x388c8）；否则 0x6400000=100MiB，超出 toast "附件大小超过100M"（0xbc54c0, pp+0x388d0）。两者都先 dispose 再 print "请求完成"。
  7. 分派阈值（行 16259）：`cmp x1, #0xa00, lsl #12` = 0xA00000 = 10 MiB
     - `>10MiB` → showLoadingDialog → `uploadMultipartFile`(0xbb2460)（不 await，this.field_47=false，回调标志 true）
     - `<=10MiB` → showLoadingDialog → `await uploadCurrentFile`(0xbc35bc) → `processEvent(this, result, ctx.field_13)`（0xbc5674）
  8. 异常：print("普通上传失败: "+e)（0xbc56a4, pp+0x38778）→ closeLoadingDialog → toast "上传失败，请重试"（0xbc56f8, pp+0x38780）→ dispose；另有 print("uploadFile - e = ")（0xbc5754, pp+0x38788）。
- 多处 LateError 字面量 "uploader"（pp+0x36210，行 16487-16562）→ 未初始化 late 字段会抛错。

### 1.2 `JsCallFlutter::uploadFile` RVA 0xbc676c（size 0x10c，行 17889-17986）

| 项 | 内容 | 证据 |
|---|---|---|
| 入参 | this, bean:AliossSignConfigBean（fromJson 见 §4.1） | 行 17889 |
| 出参 | Future<void>（无返回数据） | 行 17986 ReturnAsync |
| body | `Map{"upload": bean.field_23.field_7}`（String，缺省 ""） → JsonCodec.encode | 行 17912-17951 |
| 动作 | 拼 `"callTokenJS(" + json + ")"` → `WebViewController::runJavaScript`（RVA 0xbae4f0） | 行 17968-17986 |
| 调用点 | 唯一：app_js_call_flutter.dart:17808（0xbc6694） | grep |

**契约**：Flutter 不持有 STS；它只把服务端给的 `data.upload` 字段转交 H5，H5 用该字段（`tokenUrl`）换阿里云 STS，回调 `getTokenData`（observed）。

### 1.3 `JsCallFlutter::getAliOssConfig` RVA 0xbc630c（size 0x160）

- 签名 (this, r2, r3, x5)；先 showLoadingDialog("加载中..."，pp+0x1e178)。
- `BaseNet::_instance`(offset 0xe90) → `BaseNet::requestGet`（RVA 0x840454，xuetang_base/xuetang_base_net.dart），URL = `x5 + "?exercise_id=" + r2 + "&problem_id=" + r3`（pp+0x388f8 / pp+0x38900）。
- 返回 TypeArguments <AliossSignConfigBean>（`AllocateAliossSignConfigBeanStub` RVA 0xbc646c）；默认 field_b=true、field_f=0、field_13=""。
- 成功回调 0xbc664c：bean.field_b 为假 → closeLoadingDialog + toast "获取阿里云信息失败"（pp+0x36140）；否则转调 `uploadFile`(0xbc676c)。
- 失败回调 0xbc6590：print("getAliOssConfig - e = " + e) → closeLoadingDialog → 同一 toast。调用点唯一 app_js_call_flutter.dart:2095。

### 1.4 `getTokenData` 内的 OSS 事件闭包 RVA 0xbc61e4（行 17451-17568）

- 闭包 ctx[0].field_f 为假 → 直接返回；print("OSS Event: " + event)。
- event 类 id == 0xfb6（AliyunOssResult）→ 调 `processEvent`（0xbc62c8：x1=ctx.field_f, x3=ctx.field_1b, x5=ctx.field_13）；否则 print "event 不是 AliyunOssResult"（pp+0x386b8）。

---

## 2. OSS 上传实现

### 2.1 `rain/util/file_upload_manager.dart`

class `OSSFileUploader`（class id 603, size 0x24）late 字段：_client(0x8) / _config(0xc) / _eventSubscription(0x14)。

| 方法 | RVA | 行 | 要点 |
|---|---|---|---|
| ctor | 0xbb22dc | 14-46 | 三个 late 置 sentinel 后透传给 `_initialize` |
| `_initialize` | 0xbbe84c | 189-303 | p1→client.accessKeyId(0x8)、p2→client.accessKeySecret(0x10)、p6(栈)→client.securityToken(0xc)；p3→Config ctor#1(bucket)、p4→Config ctor#2(directory)、p5→client.eventStream().listen 回调 |
| `uploadMultipartFile` | 0xbb2460 | 47-188 | 对象名 = 文件路径按 "/" 切分取 last（行 93-101，pp+0xe50）；`DateTime::_getCurrentMicros` → GDT[cid+0x52ce] 转时间戳片段（118-135）；调 `AliyunOssClient::uploadMultipart`(0xbb25e8)。无文件抛 `Exception("No file selected or invalid file path")`（行 166, pp+0x36308） |
| `uploadCurrentFile` | 0xbc35bc | 475-664 | 同 "/" 切分 + 时间戳；调 `AliyunOssClient::upload`(0xbc3708)；成功 print "result:"+toString；无文件同 Exception（0xbc3790） |
| `pickFile` | 0xbc4ad8 | 696-1022 | MethodChannel::invokeMethod，参数 Map 含 "allowTypes"(0xbc4c0c)、"pickLargeFile"(0xbc4c40)；扩展名按 "," split→toList；返回 Map{"path"(0xbc4c84),"name"(0xbc4da4)}；失败 toast "文件选择失败"(0xbc4e4c) |
| 事件闭包 | 0xbbeb64 | 304-410 | print("OSS Event: "+AliyunOssResult) → ctx.field_13(result)；state 命中 `@11e1ad1`/`@11e1b1` 时 `Future.delayed` → `_deleteMultipartCopy`（分片清理） |
| rememberFileLength / dispose / clearSelection | 0xbc4a78 / 0xbc0220 / 0xbc02a0 | 665-695 / — | — |

**Key 生成（关键）**：`uploadMultipartFile`/`uploadCurrentFile` 均把**本地文件路径最后一段**直接当对象名再与时间戳片段组合（行 93-101 / 526-539）——客户端可控、无 sanitize（observed）。

### 2.2 `aliyunoss_plus_flutter` 字面量

- `AliyunOssClient`（class id 4024, size 0x14）：字段 accessKeyId 0x8 / securityToken 0xc / accessKeySecret 0x10；static late final `_controller`(StreamController<AliyunOssResult>, 0x1104)、`_taskMap`(Map<String,CancelToken>, 0x1108)；`uploadMultipart` RVA 0xbb25e8 (size 0xa80)、`upload` 行 3923 区；文件 aliyunoss_client.dart（4955 行）。
- `AliyunOssConfig`（aliyunoss_config.dart:154-268）：
  * **默认 endpoint 字面量 `"oss-cn-beijing.aliyuncs.com"`**（行 178，pp+0x38670）
  * 净化：`replaceFirst("https://","")` → `replaceFirst("http://","")`（字面量 pp+0xa748 / pp+0x33a00），结果 → field_b(0xc)
  * field_7(0x8)=bucket（第1参）；field_13(0x13) = `"https://" + bucket + "." + endpointClean`（行 222-239）；field_f(0x10)=directory（第3参）
- `AliyunOssResult`（class id 4022, size 0x24）：toString 模板 "AliyunOssResult{id: "、", state: "、", url: "（RVA 0x12ac370）；enum `AliyunOssResultState`（class id 8904, size 0x14）_enumToString RVA 0x131002c。

### 2.3 Endpoint / Region / Bucket / Key 前缀 / 回调 URL 汇总

| 项 | 值 / 来源 | 类型 |
|---|---|---|
| OSS Endpoint | `oss-cn-beijing.aliyuncs.com`（硬编码默认，aliyunoss_config.dart:178）；调用方未见覆盖 endpoint 的证据 | observed |
| Region | 未找到独立 region 字段/字面量（未找到）；仅能从 endpoint 推断 cn-beijing | unverified |
| Bucket | 服务端下发 `credentials.BucketName` → AliyunOssConfig.field_7 | observed |
| Key 前缀 | 服务端下发 `credentials.UploadDir` → AliyunOssConfig.field_f(0x10)=directory；uploader 侧再拼 "文件名 + 时间戳片段" | observed |
| cdn_host | H5 消息里的 `cdn_host` 被读出但未进入 Config（§1.1） | inferred |
| 回调 URL | 未找到 OSS 回调（callback）参数拼装逻辑；未见 callback/notify 字面量 | 未找到 |

### 2.4 相关端点（so/paths.txt + pp.txt）

| 端点 | 位置 | 用途 |
|---|---|---|
| `/mobile-app/api/qiniu-token` | pp.txt:53996；Api::urlTokenQiniu offset 0x1864（rain/home/teach_journal/constant/api.dart:7） | 取七牛 token |
| `/pc/generate_qiniu_token` | pp.txt:43619（pp+0x38980）；app_js_call_flutter.dart:18433、subjective_question_page.dart:7647、group_discuss_page.dart:14841/21879、send_draft_page.dart:5079 | 取七牛 token（H5 侧） |
| `/idphoto/upload/token` | exam_page.dart:2991（pp+0x42740） | 考试抓拍 token |
| `/v/api/tougao/pic_upload` | yuketang.dart:3389（RVA 0xd20d34）；paths.txt 记 `/api/tougao/pic_upload` | 头像/投稿 base64 上传 |
| `/exam/gen_token`、`/exam_authentication_page/bean/upload_exam_token.dart` | so/paths.txt | 考试认证图 token bean |

---

## 3. 考试抓拍（qiniu 链路）

### 3.1 `_ExamPageState::postAutoPhotoUpload` RVA 0xc9ec8c（size 0x2dc，exam_page.dart:19383）

- 唯一调用点 exam_page.dart:9131-9132（RVA 0xc97ed8）。
- 依赖：qiniu_sdk_base `Storage` 0xbd251c、`CancelToken` 0x86eebc、`PutController` 0xbcd048、`PutOptions` 0xbccf74、qiniu_flutter_sdk `Storage::putFile` 0xbcc36c。
- 流程（observed）：
  1. 读 this.field_6b（_autoUploadPicModel）.field_f = 本地文件路径；空 → print "_autoUploadPicModel不存在"（pp+0x49b98，行 19635）。
  2. `DataUtil::getUploadImageKey(path)` RVA 0xc94fd8（data_util.dart:2488）→ key。
  3. `Uri.parse`(0x790fdc) → `File.fromUri`(0xc9f254)。
  4. `PutOptions{ field_7=key, field_b=false, field_f=4, [0]=5, field_23=CancelToken }`（行 19579-19599）。
  5. `await Storage::putFile` → 成功拼 `this.field_67 + "/" + key` → `_uploadImageCallH5Methods(url)`（行 19621-19633，`_StringBase::+` RVA 0x778db8）。**field_67 赋值处未定位（unverified）**；由 §3.3 的 CDN 常量推断是 qiniu CDN 前缀（inferred）。

### 3.2 key 生成 `DataUtil::getUploadImageKey` RVA 0xc94fd8（data_util.dart:2488）

`时间戳(ms, 经 GDT[cid+0x52ce](60)) + getRandomString() + "." + path.split(".").last`；`getRandomString` RVA 0xc950d0 循环 `cmp x0,#6` → 6 字符随机串（data_util.dart:2580-2601）→ **不可自定 key 前缀，仅扩展名可控**（observed）。

### 3.3 token 请求与上传回报

| 步骤 | 位置 | 端点/键 |
|---|---|---|
| token（考试页） | exam_page.dart:3401-3537（RVA 0xc93230-0xc933cc） | showLoadingDialog → BaseNet::requestGet(urlTokenQiniu) → 结果存 this.field_c3 |
| token（认证抓拍） | exam_page.dart:2976-3058（RVA 0xc92de8，调用点 2942） | `{method:"get", url:"/idphoto/upload/token", params:{…}}` + print "----_getExamUploadToken----" |
| multipart 上传 | exam_page.dart:4100-4230 | dio `multipartFileFromPath`(0xc94de4) + `FormData.fromMap`(0xc9496c)，Map 键 `token`(4130) / `action`(4142，取 urlTokenQiniu) / `file`(4161)；同时用 getUploadImageKey(4110) |
| 回报 H5 | `_uploadImageCallH5Methods` RVA 0xc9ef68（行 19656-19947） | Map{method:"post", url:"/exam_room/answer_problem", params:{exam_id=this.field_b[0], image_url=入参, label:0, event_group_id:0, operator_id:0, action:64, t, p, app_version=App._getInstance().field_a3, terminal=App::terminal()(0xc154ac), is_app:true}} → JsonCodec.encode → print "----_listenAutoCameraEvent----"+json+" - controller = "+field_13 → runJavaScript("callH5Methods("+json+")")(0xbae4f0) |

- CDN 常量：`AppConstants::serverDomainQiniu()` RVA 0xbcf034（app_constants.dart:748-765）= `https://qn-scd0.yuketang.cn/`（pp+0x33ef0，行 755）；字段 serverDomainQiniu 0xd40 / serverDomainQiniuDiscuss 0xd44 / upDomainQiniu 0xd48。
- `UrlUtil::urlThumbnail` RVA 0xc3c0bc（url_util.dart:10-95）：URL 以 `https://qn-scd0.yuketang.cn/` 开头且不含 "`?imageView`" → 追加 "`?imageView2/0/h/500`"。

### 3.4 JS 桥内的七牛 token 方法（app_js_call_flutter.dart:18383-18499）

- 字面量 "bucket_name"(行 18383) / 值 "cms-attachment"(18388) / "expired_time"(18393) / URL "/pc/generate_qiniu_token"(18433) → `BaseNet::requestPost`（RVA 0x923178，行 18445）。
- 失败闭包 `[closure] void (dynamic, String)` RVA 0xbcbd10（行 18457），打印 `"GetQiNiuTokenBean  -- e = "`（行 18474）；成功闭包 `[closure] void (dynamic, GetQiNiuTokenBean)`（行 18499）。

---

## 4. Bean 契约（fromJson 字段全表）

公共布局（对照 get_qiniu_token_bean.dart:67-343）：`success→field_b`、`error_code→field_f`、`msg→field_13`、`code→field_17([0])`、`message→field_1b`、`status_code→field_1f`、`data→field_23`。

### 4.1 `rain/model/alioss_sign_config_bean.dart`

| 类 | class id / size | RVA | 字段 |
|---|---|---|---|
| `AliossSignConfigBean extends BaseBean<dynamic>` | 2531 / 0x28 | fromJson 0x1160974；toJson 0xbc6540；_$FromJson 0x11609b4(0x3f0) | 上述公共 7 字段 |
| `Data extends Object` | 1138 / 0xc | _$DataFromJson 0x1160da4；_$DataToJson 0xbc64c0 → {"upload": field_7} | field_7 = `"upload"`（行 446） |

JSON 键序：success、error_code、msg、code、message、status_code、data(379)、upload(413)。**upload 由客户端原样转交 H5（§1.2）**，非客户端提交给服务端。

### 4.2 `rain/mine/bean/upload_token_model.dart`（495 行）

| 类 | class id / size | RVA | 字段 |
|---|---|---|---|
| `UploadToken extends BaseBean<dynamic>` | 2538 / 0x28, field 0x24 | _$FromJson 0x115c6f4(0x3e0) | 公共 7 字段 |
| `Data extends Object` | 1154 / 0xc | Data::fromJson 区 0x115caf0+（行 355-459） | **只有 1 个字段 field_7**；读 `"token"`(行 366, pp+0xa7e0, String) 与 `"expire_at"`(行 400, pp+0x57820, num?)，最终 StoreField r0->field_7 = token 派生值（行 449；token 经 GDT[cid+0x52ce] 处理 行 389-394） |

键序：success(21)、error_code(60)、msg(93)、code(151)、message(191)、status_code(238)、data(279/297) → Data{token(366), expire_at(400)}。
**注意**：`expire_at` 被解析（类型 num?）但不落字段 → `Data` 只剩 token 一个槽（observed）。**token 由服务端下发，客户端不生成**。

### 4.3 `rain/mine/bean/upload_image_model.dart`（401 行）

| 类 | class id / size | RVA | 字段 |
|---|---|---|---|
| `UploadImage extends BaseBean<dynamic>` | 2539 / 0x28, field 0x24 | _$FromJson 0x115c290(0x424) | 公共 7 字段 + `key` |

键序：success(21)、error_code(60)、msg(93)、code(151)、message(191)、status_code(238)、error(279)、key(314)；`StoreField r1->field_23 = r0`（行 352）= 服务端返回的 key。**无外部调用方（未找到）**。

### 4.4 `rain/mine/bean/update_model.dart`（462 行）

| 类 | class id / size | RVA | 字段 |
|---|---|---|---|
| `UpdateModel extends BaseBean<dynamic>` | 2540 / 0x2c, field 0x24 | _$FromJson（文件头） | 公共 7 字段 + `status` |
| `Data extends Object` | 1156 / 0xc | AllocateDataStub 行 414 | field_7 = `"ok"` 值（行 416） |

键序：success(21)、error_code(60)、msg(93)、code(151)、status_code(191 区)、status(232)、message(261)、data(308/326) → Data{ok(391)}；`StoreField r1->field_27 = r0`（行 359）。

### 4.5 其它相关 bean

| 文件 | 类 | id / RVA | 字段 |
|---|---|---|---|
| rain/receiver_page/bean/get_qiniu_token_bean.dart | `GetQiNiuTokenBean extends BaseBean<dynamic>` | 2526 / fromJson 0x11647e8, toJson 0xbcbcc0, _$FromJson 0x1164828 | 公共 7 字段 |
| 同上 | `Data extends Object` | 986 / Data::fromJson 0x1164c08 | field_7 = `"token"`；_$DataToJson 0xbcbc40 → {"token": field_7} |

---

## 5. `JsCallFlutter::openHomeworkFile` RVA 0xbd3814（size 0x520，行 20517-20993）

入参：arg1（fileUrl, fp-0x10）、arg2（fp-0x18）、arg3（fp-0x20 → ctx.field_13）。

- 0xbd3868 `file_url_util.dart::ensureFileUrlScheme(arg2)`（RVA 0xbc34e8）→ ctx[0]。
- 0xbd3894：对 arg3 动态单参调用（实参字面量 `"false"`，pp+0x75f8）→ bool；**非 true → toast "该文件可在网页端查看,下载"（pp+0x38aa0，行 20589）并 return**。
- 扩展名判定（末段小写）：图片 any()（fp-0x30，行 20646-20701，闭包 0xbd41f8）、`contains(".pdf")`（fp-0x20，0xbd3960）、`contains(".txt")`（fp-0x18，行 20705-20718）、办公 any()（w1，行 20722-20773）。

| 守卫 | 条件 | body / 页面（stub 名） | 页面闭包 RVA |
|---|---|---|---|
| 0xbd3adc | 图片(jpg/jpeg/png/gif/bmp/webp) | `PhotoViewGalleryScreen`（app_js_call_flutter.dart:21264，显式 `bl`） | 0xbd3fdc |
| 0xbd3b4c | `contains(".pdf")` | `PdfDownloadPreviewPage` | 0xbd3ef4 |
| 0xbd3bbc | `contains(".txt")` | `TxtDownloadPreviewPage` | 0xbd3e30 |
| 0xbd3c28 | 办公(doc/docx/xls/xlsx/ppt/pptx) | `OfficePreviewInAppWebViewPage` | 0xbd3d34 |
| else 0xbd3c94 | ctx.field_13 == "false" | 真 → toast 同文案（0xbd3ce8，行 20960）；假 → `_launchURL`（RVA 0xba9c64，行 20972） | — |

- 页面闭包创建点：20789(0xbd3afc→0xbd3fdc)、20828(0xbd3b6c→0xbd3ef4)、20867(0xbd3bdc→0xbd3e30)、20905(0xbd3c48→0xbd3d34) — 均为 `[pp+0x38b28/0x38b30/0x38b38/0x38b40] AnonymousClosure … in JsCallFlutter::openHomeworkFile (0xbd3814)`。
- 分支语义：本样本 `tbnz w,#4` = **条件为假时跳过 body**（inferred：由 body 内容与页面语义一致性推得；body 执行 = 条件为真）。
- 结构：`Navigator::of`(0x906460) → `MaterialPageRoute`(0xbab35c) → `NavigatorState::push`(0x7b5d74)。
- 未验证：arg3 的确切语义（疑为"是否可原生打开"的字符串开关）；ctx.field_13 与 "false" 的两次比较在源码中对应哪个业务变量（未找到）。

---

## 6. 结论：客户端能否自造上传（逐字段判据）

| 字段 | 客户端能否自定 | 判据（证据） | 缺失环节 |
|---|---|---|---|
| fileName / OSS 对象 Key | **能**（作业附件） | 对象名 = 本地路径最后一段（file_upload_manager.dart:93-101 / 526-539），随后仅额外拼时间戳片段；无 sanitize | — |
| Key（考试抓拍） | **仅扩展名可控** | getUploadImageKey = 时间戳 + 6 随机字符 + "." + 原扩展名（data_util.dart:2488/2580-2601） | 时间戳与随机数由客户端生成，但前缀不可控 |
| Bucket | **不能** | BucketName 来自 H5 消息 `credentials.BucketName` → AliyunOssConfig.field_7（app_js_call_flutter.dart:2286） | 需服务端/H5 下发 |
| Endpoint / Region | **不能** | 硬编码 `oss-cn-beijing.aliyuncs.com`（aliyunoss_config.dart:178）；无覆盖路径（cdn_host 未生效，§1.1 inferred） | — |
| UploadDir（Key 前缀） | **不能** | `credentials.UploadDir` → Config.field_f(0x10) | 需服务端下发 |
| AccessKeyId / AccessKeySecret / SecurityToken | **不能** | 三字段全部来自 `credentials.*`（app_js_call_flutter.dart:2130/2182/2390）；客户端无本地密钥字面量（so/u16strings.txt、pp.txt 中未出现 AK/SK 形态串） | **STS 必须由服务端（或服务端指定的 tokenUrl 经 H5）下发** |
| uploader / 上传者身份 | **不能** | 抓拍回报 `operator_id:0`、`exam_id` 取自 this.field_b[0]（服务端数据）；其余字段为常量（exam_page.dart:19711-19813）；无用户可填 uploader 字段 | 身份由登录态/服务端决定 |
| fileUrl（最终可访问 URL） | 半可控 | 抓拍：CDN 前缀（服务端/常量 `qn-scd0.yuketang.cn`）+ client key（exam_page.dart:19621-19633）；OSS：由 bucket.endpoint/directory + key 构成（aliyunoss_config.dart:222-239） | 前缀需服务端/常量，key 可自定 → 只能改后缀段 |
| 回调 URL / 通知地址 | 未找到 | 未见 callback/notify 拼装 | — |

**总体判据**：客户端**不能**独立自造一次合法上传——OSS 直传的 AK/SK/STS/Bucket/UploadDir 全部要求服务端（或服务端给的 tokenUrl）下发，且 uploadFile 只做"H5 换凭证"的转发；客户端唯一自定空间是**对象名的最后一段（文件名）**（作业附件路径）与文件名扩展名（抓拍）。若把 STS 换成客户端已知凭证，则 §2.1 的 Key 组合逻辑即可被任意调用（uploader 无身份校验逻辑，inferred）。

---

## 7. 覆盖率与缺口

- 已覆盖：getTokenData / uploadFile / getAliOssConfig / processEvent / OSSFileUploader 全方法 / AliyunOssConfig/Client/Result / postAutoPhotoUpload / _uploadImageCallH5Methods / getUploadImageKey / getRandomString / openHomeworkFile 全分支 / 4 个 bean / 七牛常量与端点 / 头像上传（`_AvatarUpdateWidgetState::postBase64Image` RVA 0xd20a6c → `YuKetang::uploadImage` RVA 0xd20c74 → POST `/v/api/tougao/pic_upload`，body `{"pic_data":…, "pic_type":"png"}`（yuketang.dart:3336-3401），非 OSS/七牛）。
- 未验证/未找到：`ExamPageState.field_67` 赋值点；OSS 回调 URL；Region 独立字段；`upload` 字段服务端语义（是 tokenUrl 还是内嵌 JS）；arg3 语义；`UploadImage.key` 的实际消费方（无调用点）。
