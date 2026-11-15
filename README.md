# 雨课堂 Android 客户端逆向分析

对 **雨课堂 Android（com.xuetangx.ykt，1.3.6）** 的静态逆向与接口取证，重点是四个功能区：**签到 / 作业 / 成绩 / 课程作答**，并附带一套可复跑的 Frida 观测脚本与 HTTP 重放工具。

样本指纹（用于对照你自己的样本）：

| 文件 | sha256 |
| --- | --- |
| `雨课堂.apk` | `bb777dee2d3bb4f313179e4dd30c6bb05592ea650ab26fa7417503b0715b2c61` |
| `lib/arm64-v8a/libapp.so` | `0277169865af6b0dad103f443a236d7111c6dfa88f63ea40c996629d776a1a26` |
| `lib/arm64-v8a/libflutter.so` | `0c56c4a468224beb2336c7bacaee6d5885047a0075d613fe421871b4dceafdce` |

技术画像（observed）：Flutter 外壳 + **未混淆的 Dart AOT 快照**（Dart 3.11.5 stable，`libapp.so` product 构建，无调试信息，字段名缺失但字符串完整，中文以 **UTF-16LE** 存储）；Java 层基本只是插件外壳，唯一的手写原生逻辑是**光速虚拟机检测**。鉴权是 Django 会话 cookie + `X-CSRFToken` + `X-UID` + `Bearer`，**没有任何请求签名**。

## 核心结论（浓缩版，全文见报告 §12）

1. **签到**：普通签到与定位签到两条链路；服务端下发 `isLate/wouldBeLate/radiusM/serverTime/startMs/endMs/lateAfterMs`，客户端只做展示型本地 gate。客户端可控字段只有 `lat/lng/address` 与入口 `source`（42 扫码 / 44 手输 / 46 通用 / 54 定位）；提交体里**没有时间字段**，`checkInTime` 由服务端回填。
2. **作业**：App 内没有作业实现，作业是云侧 H5 + OSS 直传 + `callHomeworkJS` 回调桥；客户端可构造 `fileUrl/fileName/uploader`。
3. **成绩**：三个写入点（`review/submit-review-score`、`problem/grade`、`problem/teacher/score-detail`）的分数与身份全是客户端参数；最终成绩单在云侧 H5。
4. **课程作答**：`problem/answer` 的 `result/problemType/dt`、视频 AI 题的 `answer`、抢答 `rapid-answer/participate`、弹幕 `sendDanmu` 全部由客户端构造 —— 四个模块里最直接的输入信任缺口。
5. **反作弊面**：光速虚拟机规则集（Titan GLES/Vulkan、isulad overlay、csaic）+ 分屏/截屏回调 + 考试监考 action 码（24/16/20，客户端驱动）；`GuangsuRuntimeRules` 里**没有** frida/xposed 关键字。
6. **身份绑定**：`100030`（扫码未绑定）/`100038`（加入班级未绑定）是**服务端业务码**，客户端只把它显示成 toast；绑定界面是两个 H5（`/v/index/bindSchool_list`、`/static/html/tsinghua_bind.html`），客户端唯一的原生写入通道是 `POST /v/course_meta/edit_user_info`。

完整字段级证据、错误码、RVA 表与接口全表见 [report/雨课堂_逆向分析报告.md](report/雨课堂_逆向分析报告.md)。

## 仓库结构

```
report/   雨课堂_逆向分析报告.md        # 主交付物：12 章，全部结论标注 observed/inferred/unverified
hooks/    ykt_hooks.js                 # 25 个只读观测挂点（含 4 字节 guard，防版本错配误挂）
          ykt_checkin_probe.js         # 签到专项取证：请求侧 8 点 + 响应侧 5 点，JSONL 落盘
          README.md                    # 挂点表、A-G / E0-E4 / B0-B4 实验表、加载命令
replay/   checkin_replay.sh            # 四种签到端点重放（plain|web|loc-get|loc-submit|all）
          checkin_diff.py              # 两次实验的响应字段差异对比（白名单键）
          bind_replay.sh               # 身份绑定 B0-B4 实验（状态/学校库/写入/裁决点）
tools/    kwscan.py                    # libapp.so 字节级字符串扫描（UTF-16LE 中文可命中）
          u16scan.py                   # UTF-16LE 字符串批量导出
          addr_extract*.py / sig*.py   # 从 blutter 反汇编提取函数 RVA、签名、prologue guard 字节
          verify_prologue.py           # capstone 校验文件偏移处的指令与 asm 是否逐条一致
          fj_guard.py                  # 反编译产物完整性辅助
artifacts/ paths.txt                   # 从样本中提取的接口路径全集（156 条）
          dartfiles.txt                # Dart 源码路径全集（2880 条），用于确认"模块是否存在"
```

## 复现路径

```bash
# 1) 字符串级侦察（不需要任何工具链）
python3 tools/kwscan.py 补签 签到 学号 弹幕     # 直接读 lib/arm64-v8a/libapp.so

# 2) Dart AOT 反编译（Route B: blutter，需 cmake3.20+/ninja/C++20）
#    产物 asm/ 目录按库 URI 每文件一个，是最富的反汇编源；addr 即 RVA
#    RVA → 运行时地址：Process.findModuleByName("libapp.so").base + RVA

# 3) Frida 观测（只读，不改内存）
frida -U -f com.xuetangx.ykt -l blutter_out/blutter_frida.js -l hooks/ykt_hooks.js --no-pause

# 4) 接口重放（需要自己的测试账号 Cookie）
cd replay && BASE_URL=https://www.yuketang.cn COOKIE='csrftoken=..; sessionid=..' X_CSRF=.. X_UID=.. ./checkin_replay.sh all
```

**本仓库不含 APK、不含 `libapp.so`、不含反编译产物树**（版权与体积原因）：只放分析报告、脚本与路径清单，样本请自备并用上表 sha256 对照。

## 方法论备注（踩过的坑）

- Dart AOT 函数**首 8 字节全部相同**（`fd 79 bf a9 fd 03 0f aa`），不能用来定位；判别位在 `+8` 的帧大小指令（`sub x15,x15,#imm`），本仓库 hooks 里的 guard 用的就是这 8 字节。
- Frida 里比较字节要用 `readByteArray` 的**字节序字符串**，用 `readU32()` 比 `0xfd79bfa9` 会因大小端全部误报。
- `libapp.so` 段表中 `.text` 的 vaddr 与文件偏移恒等（0x760000），所以 blutter 打印的 `addr` 就是 RVA。
- 「反汇编里没有调用点」**不等于**「不存在」：路径常由 `_StringBase::_interpolate` 拼接，字面量不落在指令上；判断要用响应 bean 类型反证 + 抓包。
- 报告全文区分 `observed / inferred / unverified / unknown`，不要把 inferred 当结论用。

## 用途

学习与研究用途，作者不对使用者的行为负责。

