#!/usr/bin/env bash
# checkin_replay.sh — 签到端点重放/对照（本地测试样本专用，只打自己的测试账号）
#
# 三组实验共用（对应报告 §11 E0-E4）：
#   E0 窗口内正常签 / E2 换入口 source / E3 窗口外(late 窗内)重放 / E4 完全过期后重放
#
# 用法：
#   BASE_URL=https://TARGET_HOST COOKIE='sessionid=...; csrftoken=...' X_CSRF=... X_UID=... \
#   LESSON_ID=1234567 SOURCE=46 TAG=E0 \
#   ./checkin_replay.sh plain
#
#   ... ./checkin_replay.sh web          # /api/lesson/web_check_in (invite_code)
#   ... ./checkin_replay.sh loc-get      # 定位签到资格 GET（先看 canSign/isLate/pastOfficialEnd/reason）
#   ... ./checkin_replay.sh loc-submit   # 定位签到提交（LAT/LNG/ADDRESS 可覆盖）
#   ... ./checkin_replay.sh all          # 全跑一遍，结果落 runs/<TAG>-<时间戳>/
set -uo pipefail

BASE_URL=${BASE_URL:?need BASE_URL}
COOKIE=${COOKIE:?need COOKIE}
X_CSRF=${X_CSRF:-}
X_UID=${X_UID:-}
LESSON_ID=${LESSON_ID:-}
INVITE_CODE=${INVITE_CODE:-}
SOURCE=${SOURCE:-46}
LAT=${LAT:-0.0}
LNG=${LNG:-0.0}
ADDRESS=${ADDRESS:-UNKNOWN}
TAG=${TAG:-E0}
SESSION=${SESSION:-}
OUT_DIR="runs/${TAG}-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT_DIR"

hdrs=(-H "Cookie: $COOKIE" -H "Content-Type: application/json" -H "Accept: application/json")
[ -n "$X_CSRF" ] && hdrs+=(-H "X-CSRFToken: $X_CSRF")
[ -n "$X_UID" ]  && hdrs+=(-H "X-UID: $X_UID")
hdrs+=(-H "Referer: $BASE_URL/" -H "X-Requested-With: XMLHttpRequest")

post() { # $1=name $2=path $3=body
  local name="$1" path="$2" body="$3"
  echo "### $name  POST $path"
  echo "$body" > "$OUT_DIR/$name.req.json"
  curl -sS -o "$OUT_DIR/$name.res.json" -w 'HTTP %{http_code}\n' \
       -X POST "${BASE_URL}${path}" "${hdrs[@]}" --data-binary "$body" | tee "$OUT_DIR/$name.code"
  head -c 800 "$OUT_DIR/$name.res.json"; echo; echo
}
get() { # $1=name $2=path
  local name="$1" path="$2"
  echo "### $name  GET $path"
  curl -sS -o "$OUT_DIR/$name.res.json" -w 'HTTP %{http_code}\n' \
       -X GET "${BASE_URL}${path}" "${hdrs[@]}" | tee "$OUT_DIR/$name.code"
  head -c 800 "$OUT_DIR/$name.res.json"; echo; echo
}

do_plain() { post plain /api/v3/lesson/checkin "{\"lessonId\":${LESSON_ID:-\"\$INVITE_CODE\"},\"source\":$SOURCE,\"joinIfNotIn\":true}"; }
do_web()   { post web   /api/lesson/web_check_in   "{\"invite_code\":\"$INVITE_CODE\",\"source\":46}"; }
do_locget(){ get  loc-eligibility "/api/v3/lesson/location-checkin/eligibility?lessonId=${LESSON_ID}${SESSION:+&session=$SESSION}"; }
do_locsub(){ post loc-submit /api/v3/lesson/location-checkin/submit \
             "{\"lat\":$LAT,\"lng\":$LNG,\"lessonId\":${LESSON_ID},\"source\":54,\"address\":\"$ADDRESS\"${SESSION:+,\"session\":\"$SESSION\"}}"; }

case "${1:-all}" in
  plain) do_plain ;;
  web)   do_web ;;
  loc-get) do_locget ;;
  loc-submit) do_locsubmit ;;
  all) do_plain; do_web; do_locget; do_locsubmit ;;
  *) echo "usage: $0 {plain|web|loc-get|loc-submit|all}"; exit 2 ;;
esac
echo "== 结果目录：$OUT_DIR（配合 checkin_diff.py 对比两次实验）"
