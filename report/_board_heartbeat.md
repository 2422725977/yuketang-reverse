# 雨课堂 —— 学习时长心跳上报面（成绩/进度的时间侧）板块报告

样本：/Users/xi/Downloads/雨课堂.apk（com.xuetangx.ykt v1.3.6）
坐标：blutter_out/asm/**，RVA = 文件偏移（.text 段 vaddr 与文件偏移恒等）。全部 observed，除标注 inferred。

---

## 1. 为什么单列这个面

成绩单里"平时分/进度/观看时长"这类**时间侧数据**没有任何服务端可验证的物理量 —— 客户端按自己的节拍上报心跳，服务端只做累加。这是四模块之外、但直接影响成绩的第 5 个输入面，且**完全由客户端构造**。

## 2. 端点与信封（observed）

| 项 | 值 |
| --- | --- |
| 端点 | `POST /mobile-app/video-log/heartbeat/`（字面量 pp+0x165c0，构造点 heartbeat_util.dart:383 0xbdee00 / live_heartbeat_util.dart:810 0xbde5d8 与 :1513 0xbe4a20） |
| 请求体 | `{"heart_data": [ HeartBeat, ... ]}` —— HeartBeatParamsModel 唯一字段 `heart_data`（heart_beat_params_modal.dart:26，@_$HeartBeatParamsModelToJson` 0xbde8bc） |
| 单条结构 | HeartBeat（size 0x60 = 22 字段），模型文件 rain/course/play/model/heart_beat_model.dart |
| 发送路径 | HeartBeatUtil::postBeat 0xbdec24（async，size 0x254）→ HeartBeatParamsModel → JSON → BaseNet::requestPost；批内多条时逐条失败重试 |
| 音频通道 | `heartBeatUploadAudio` 0xdd4834 / `getHeartBeatDataAudio` 0xdd4984，类型字面量 `video_audio`（heartbeat_util.dart:4009） |

## 3. 22 字段全表（observed：模型 fromJson/toJson 键名与顺序；inferred：字段语义与默认值来源）

| # | 键 | 类型线索 | 默认值 / 赋值点（observed） | 语义（inferred） |
| --- | --- | --- | --- | --- |
| 1 | `id` | int | initBeatData 0xc46ae0 起：`int.parse(当前秒内随机数 + DataUtil.getRandomNumString())` | 单条心跳本地标识 |
| 2 | `ts` | int | 0xc46a5c（init）与 0xc46e5c（getHeartBeatData）：`DateTime._getCurrentMicros()/1000` | **秒级时间戳 = 客户端本地时钟** |
| 3 | `i` | int | initBeatData 0xc46b3c 默认 `5` | 间隔 / 序号步长 |
| 4 | `et` | TEXT | getHeartBeatData 0xc46ca8 ← util.field_7（非空对象，其 field_7 非 0 才上报） | 事件/实体上下文 |
| 5 | `cp` | int | 0xc46df8 ← util.field_f（默认 0） | 当前进度位 |
| 6 | `fp` | int | 0xc46d9c ← util.field_13 | 首次位 |
| 7 | `tp` | int | 0xc46d64 ← util.field_1b（可空 → 0） | 总位/末位 |
| 8 | `sp` | **REAL** | 0xc46d0c ← util.field_1f（可空 double → 0.0） | 播放位置（秒，浮点） |
| 9 | `c` | TEXT | 模型默认 `""`（0xc46c88 段） | 客户端标识 |
| 10 | `v` | TEXT | 同上 | 版本 |
| 11 | `cc` | TEXT | 0xc46c88 ← util.field_23（可空 → ""） | 渠道/客户端补充 |
| 12 | `d` | int | — | 时长 |
| 13 | `pg` | TEXT | — | 页面/来源页 |
| 14 | `sq` | int | — | 批次序号 |
| 15 | `u` | TEXT | — | 用户标识 |
| 16 | `classroomid` | TEXT | — | 课堂 id |
| 17 | `lesson_id` | TEXT | — | 课次 id |
| 18 | `t` | TEXT | initBeatData 0xc46bbc 默认 `video`（音频通道字面量 `video_audio`） | 媒体类型 |
| 19 | `p` | TEXT | initBeatData 0xc46bd8 固定 `android` | 平台 |
| 20 | `lob` | TEXT | initBeatData 0xc46b7c 默认 `ykt` | 业务线 |
| 21 | `n` | TEXT | — | 网络/节点 |
| 22 | `skuid` | TEXT | — | 课程叶子（视频）资源 id |

字段偏移映射依据（**observed**）：`_$HeartBeatToJson` 里每个键字面量前的 `LoadField` 已逐条配对 —— field_7→id, field_b→ts, field_f→i, field_13→et, field_17→cp, field_1b→fp, field_1f→tp, field_23→sp, field_27→c, field_2b→v, field_2f→cc, field_33→d, field_37→pg, field_3b→sq, field_3f→u, field_43→classroomid, field_47→lesson_id, field_4b→t, field_4f→p, field_53→lob, field_57→n, field_5b→skuid（HeartBeat 实例 size 0x60 = 头部 7 + 22×4，键序表见 heart_beat_model.dart:1080–1310）。

## 4. 本地队列：失败不高丢，落 sqlite 后补传（observed）

* 库文件 `heartbeat.db`（beat_db_helper.dart:38 0x7d083c），表 `HeartBeatTable`。
* 建表语句（_onCreate 0x7d8b20，字面量 0x7d8b98–0x7d8dc4 拼接）：
`CREATE TABLE IF NOT EXISTS HeartBeatTable (id INTEGER PRIMARY KEY, ts INTEGER, i INTEGER, et TEXT, cp INTEGER, fp INTEGER, tp INTEGER, sp REAL, c TEXT, v TEXT, cc TEXT, d INTEGER, pg TEXT, sq INTEGER, t TEXT, p TEXT, lob TEXT, n TEXT , u TEXT, classroomid TEXT, lesson_id TEXT, skuid TEXT )`
* 关键函数：`initServerDBHelper` 0x7d075c、`BeatDBHelper::initDb` 0x7d07fc、`_onCreate` 0x7d8b20、`_onUpgrade` 0x7d8a50（升级时先 `delete` 旧表）、`insertHeartBeat` 0xbdff84、`selectHeartBeats` 0xbdcdf8、`deleteHeartBeat` 0xbdfcb4、`getCount` 0xc25f18。
* 失败路径（HeartBeatUtil）：`saveHeartBeatFailData` 0xbdf068（打印 `---saveHeartBeatFailData:` 与整条 HeartBeat --- 即 `HeartBeat{id: … ,ts: … , skuid: …}` 全字段）、`addErrorHeartBeats` 0xc461a0、`deleteLocalBeatData` 0xbdfacc（`deleteHeartBeat`）、`localBeatUpload` 0xc25cf8 / `localBeatUploadUnLock` 0xc25d3c（打印 `------进入localBeatUpload()` 等进度日志）、`getCount` → 全批删完后打印 `该批次心跳数据已经全部删除`。
* 时钟/节拍：`cancleHeartBeatTimer` 0xc45ae4、`heartBeatUpload` 0xc45d90（打印 `----HeartBeatTimer...`）、`heartBeatLocal` 0xc46eac（监听 `heartBeatLocal` 事件）、`postBeat` 0xbdec24；启动/停止调用点在 rain/main.dart:1350/1355/1378/1383（HeartBeatUtil::… 0x7da4b8 / 0xc25cf8）。
* 直播通道：rain/util/live_heartbeat_util.dart —— `postLiveBeat` 0xbde484、`postLiveHeartBeat` 0xbe48c0、`receiverUpload` 0xbdbd6c、`livelocalBeatUpload` 0xbde388、`deleteLiveLocalBeat` 0xbe0934、`saveLiveHeartBeata` 0xbe2b70、`cancleLocalHeartBeatTimer` 0xbdbd0c。

## 5. 客户端可控性（observed 结构 → inferred 影响）

1. **时间由客户端给**：ts 是 `DateTime.now()` 的秒级值，sp/cp/tp/fp 是播放器状态，d 是时长 —— 服务端没有独立时钟比对（客户端侧无任何 serverTime 校准代码，区别于签到族有 `_currentServerTimeMs()`）。
2. **批与节奏由客户端定**：i（默认 5）、sq、批大小、重试全部本地决定；失败数据落 `heartbeat.db` 后可跨会话补传。
3. **唯一强绑定字段是 u / classroomid / lesson_id / skuid**，它们决定这条时长记到谁、哪节课、哪个视频上 —— 伪造时长必须先有合法会话（cookie）与合法 lesson/sku 关系。
4. **服务端是否做交叉校验（播放器事件的合理性、单位时间上限、去重）为 unverified** —— 判定方式见 §6。

## 6. 判定实验（新增实验组 T，脚本沿用 replay/ykt_client.py）

| 编号 | 单变量 | 观测点 | 判定 |
| --- | --- | --- | --- |
| T0 | 基线：正常播放 60 秒 | 抓包 `/mobile-app/video-log/heartbeat/` 请求与响应 | 记录批大小、ts 间隔、sp 递增步长 |
| T1 | 只改 ts（回拨 1 小时） | 同上 | 接受则说明服务端不校验本地时钟 |
| T2 | 只改 sp/d（放大 10 倍） | 同上 | 接受则时长完全由客户端决定 |
| T3 | 重放同一批（sq 不变） | 同上 | 去重与否 |
| T4 | 高频连发（1 秒 10 批） | 同上 | 是否有速率限制/风控 |
| T5 | 伪造 classroomid/lesson_id | 教师端/成绩页 | 是否写进他人记录（越权面） |

判定脚本：`replay/ykt_client.py http --method POST --path /mobile-app/video-log/heartbeat/ --body @beat.json`；取证：`hooks/ykt_beat_probe.js`（本轮新增，日志 `/data/local/tmp/ykt_beat.jsonl`）。

## 7. 探针挂点（hooks/ykt_beat_probe.js，guard 双字节校验）

| 挂点 | RVA | guard（首4字节,第3条指令4字节） |
| --- | --- | --- |
| HeartBeatUtil::postBeat | 0xbdec24 | fd79bfa9, efe100d1 |
| HeartBeatUtil::getHeartBeatData | 0xc46bf4 | fd79bfa9, ef6100d1 |
| HeartBeatUtil::heartBeatUpload | 0xc45d90 | fd79bfa9, efa100d1 |
| HeartBeatUtil::localBeatUploadUnLock | 0xc25d3c | fd79bfa9, ef8100d1 |
| HeartBeatUtil::heartBeatUploadAudio | 0xdd4834 | fd79bfa9, efc100d1 |
| BeatDBHelper::insertHeartBeat | 0xbdff84 | fd79bfa9, ef8100d1 |
| BeatDBHelper::selectHeartBeats | 0xbdcdf8 | fd79bfa9, ef6101d1 |
| LiveHeartBeatUtil::postLiveBeat | 0xbde484 | fd79bfa9, efe100d1 |

## 8. 待验证（unverified）

1. 服务端对 ts/sp/d 的合理性校验与单位时间上限；
2. heartbeat 是否参与成绩单中"观看时长/进度"的分值计算（客户端侧只能看到上报，看不到计分规则）；
3. `heartbeat.db` 中残留数据是否在下次启动无条件补传（insertHeartBeat 0xbdff84 与 localBeatUploadUnLock 0xc25d3c 的调用顺序）；
4. 直播心跳（live_heartbeat_util）与点播心跳是否共用同一计分口径。
