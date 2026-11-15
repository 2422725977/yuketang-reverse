# replay/ — 雨课堂重放与实验工具

会话语义全部来自 `report/雨课堂_逆向分析报告.md` §2.4（HTTP 头与会话生命周期），
实验编号与 §11 的对照实验一致。所有脚本只用 Python 标准库，不需要 pip。

## 1. ykt_client.py — 会话客户端（HTTP + WebSocket）

```bash
# 单次请求（自动跟随 Set-Cookie 轮换，自动补 X-CSRFToken / X-UID / Authorization）
python3 ykt_client.py --base https://www.yuketang.cn \
    --cookie "csrftoken=CSRF; sessionid=SESS; sid=SID" --uid 123456 --trace runs/trace.jsonl \
    http GET /api/v3/lesson/checkin-list?lesson_id=999

# 账号密码登录（拿新会话；cookie 会写进 trace）
python3 ykt_client.py --trace runs/login.jsonl login --phone PHONE --password PASS

# 按场景库生成的 jsonl 回放（每步打印状态码与会话是否被判 100000 失效）
python3 ykt_client.py --cookie "..." --uid 123456 replay runs/E.jsonl

# WebSocket：握手（只带 User-Agent，与原客户端一致）→ 发 hello → 听 20 秒
python3 ykt_client.py --uid 123456 ws --lesson-id 999 --auth TOKEN --send-hello --listen 20

# WebSocket 注入教师专属 op（判定服务端是否按 role 过滤，报告 §12 未验证项）
python3 ykt_client.py --uid 123456 ws --lesson-id 999 --send-hello \
    --op '{"op":"detectlesson","lessonid":"999"}' \
    --op '{"op":"sendpost","postid":"111","msgid":1234}' --listen 30
```

要点（observed，见报告 §2.4）：
* 请求头基线 = `Accept / Content-Type / xtbz:ykt / x-client:app / User-Agent`（`App::initNet` 0x1450b14）；
* 每请求补 `X-UID`、`X-CSRFToken`，若有 `Set-Auth` 则补 `Authorization: Bearer <值>`；
* Cookie 形如 `csrftoken=..; sessionid=..; sid=..`，**服务端随时可轮换**——脚本每个响应后自动吸收；
* 响应业务码 **100000** = 会话失效（`setReLoginCode` 0x145137c），脚本会打印 `!! 业务码 100000` 并中止回放。

## 2. ykt_scenarios.py — 35 个场景（四模块 + 实验组）

```bash
python3 ykt_scenarios.py list
python3 ykt_scenarios.py emit E1-late-localsubmit --set LESSON_ID=999 --set LAT=39.9 --set LNG=116.3 --set ADDRESS=教学楼下
python3 ykt_scenarios.py jsonl runs/E.jsonl --group E     # E/A/B/C/D 组可直接生成回放文件
```

| 组 | 内容 |
|---|---|
| E | 签到实验：E0 基线 / E1 窗口外提交 / E2 地址 / E3 重放 / E4 教师端总览（需教师号） |
| A | 四条签到入口（扫码 42 / 手动 44 / web_check_in 46 / 教师名单） |
| B | 身份绑定：读状态 / 学校搜索 / 写身份 / 加入班级裁决 |
| H | 作业（JS 桥 `callHomeworkJS`、`getTokenData`、`uploadFile`，不是 HTTP） |
| C | 课程作答：问题作答 / 抢答 / 弹幕 / 视频题 |
| D | 成绩写入：互评分 / 教师评分 / 明细 |
| W | WebSocket `hello`（学生/教师）与 6 个教师专属 op 注入 |

## 3. checkin_replay.sh / checkin_diff.py（早期脚本，shell + 差异比对）

```bash
bash checkin_replay.sh all            # plain|web|loc-get|loc-submit|all，走 curl
python3 checkin_diff.py runs/A runs/B # 按白名单字段并排比较两次实验
```

## 4. 纪律（与报告 §11 同）

* 单变量：一次只改一个字段，其余固定；每组留原始基线做 control。
* 每个结论标注 observed / inferred / unverified / unknown；服务端未确认生效前，不写"已绕过"。
* 只用自己的测试账号与自己的测试课；教师端接口（overview / checkin-list / score-detail）需要教师号。
