#!/usr/bin/env bash
# checkin_matrix.sh - 签到路径矩阵探测（默认只打印，不发送）
#
# 背景（报告 §26）：社区实现在 source 枚举与端点上与我们的 1.3.6 样本不同，
# 本脚本把"候选路径 × source 值"排成矩阵，逐条单变量发送，用于判定哪一条在
# www.yuketang.cn 上真被接受。
#
# 用法：
#   ./replay/checkin_matrix.sh                        # 只打印矩阵（dry-run）
#   ./replay/checkin_matrix.sh --yes                  # 真发（每条间隔 15s，注意配额）
#   ./replay/checkin_matrix.sh --yes --sources 42,21  # 只测指定 source
#   ./replay/checkin_matrix.sh --yes --device         # 在模拟器内发（默认宿主直连）
set -u
YES=0; DEVICE="--host"; SOURCES="1,5,14,21,22,23,42,44,46"; LESSON="1820276486008339584"
while [ $# -gt 0 ]; do
  case "$1" in
    --yes) YES=1 ;;
    --device) DEVICE="" ;;
    --sources) SOURCES="${2:-}"; shift ;;
    --lesson) LESSON="${2:-}"; shift ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac; shift
done
cd "$(dirname "$0")/.." || exit 1
PY=/usr/local/bin/python3.13

run() {  # run <label> <method> <path> <body-json-or-empty>
  local label="$1" m="$2" p="$3" b="${4:-}"
  if [ "$YES" = 0 ]; then
    printf '[dry] %-28s %s %s %s\n' "$label" "$m" "$p" "$b"
    return
  fi
  printf '\n=== %s\n' "$label"
  if [ -n "$b" ]; then
    $PY tools/dev_replay.py $DEVICE --method "$m" --path "$p" --body "$b" 2>&1 | tail -2
  else
    $PY tools/dev_replay.py $DEVICE --method "$m" --path "$p" 2>&1 | tail -2
  fi
  sleep 15
}

echo "# 目标 lessonId=$LESSON  device_mode=${DEVICE:-device}  yes=$YES"

# 0) 只读：先确认这门课是否还在进行中（LESSON_END 之后一切免谈）
run "on-lesson(只读)" GET "/api/v3/classroom/on-lesson"

# 1) 动态二维码验证口：客户端扫码后就是把这个原文 POST 过来
run "app/scan(原文=lessonId)" POST "/api/v3/app/scan" "{\"url\":\"$LESSON\"}"

# 2) 主签到端点 × source 矩阵
IFS=',' read -ra SRC <<< "$SOURCES"
for s in "${SRC[@]}"; do
  run "checkin source=$s" POST "/api/v3/lesson/checkin" \
    "{\"lessonId\":\"$LESSON\",\"source\":$s,\"joinIfNotIn\":true}"
done

# 3) 暗号类老接口（需要真实暗号，占位 <INVITE_CODE>）
run "web_check_in(暗号)" POST "/api/lesson/web_check_in" '{"invite_code":"<INVITE_CODE>","source":46}'
# 4) 社区脚本里出现的变体（我们的 1.3.6 样本里没有这个字符串）
run "notkn/checkin(变体)" POST "/api/v3/lesson/notkn/checkin" \
  "{\"lessonId\":\"$LESSON\",\"source\":5}"

echo
echo "# 判读：code 0=成功 / 50004=LESSON_END / 10037=暗号错 / 10030|10038=未绑定/未入班 / 50033=QR_CODE_NOT_FOUND"
