#!/usr/bin/env bash
# eligibility_probe.sh —— 只读：签到资格/窗口判定单次观测
# 纪律：只发 GET；两次请求之间 sleep；任一步返回 50000/UNAUTHENTICATED 立刻停。
# 用法：
#   export COOKIE='<sessionid=...; csrftoken=...>'
#   export CSRF='<csrftoken>'
#   export UID_=100254372
#   export LESSON_ID=1820276486008339584
#   bash replay/eligibility_probe.sh
set -uo pipefail

BASE="${BASE:-https://www.yuketang.cn}"
COOKIE="${COOKIE:?need COOKIE}"
CSRF="${CSRF:?need CSRF}"
UID_="${UID_:?need UID_}"
LESSON_ID="${LESSON_ID:?need LESSON_ID}"
OUT="${OUT:-live/elig-$(date +%Y%m%d-%H%M%S)}"
UA='Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36 yuketang/1.3.6'
SLEEP="${SLEEP:-15}"

mkdir -p "$OUT"
echo "[out] $OUT"

get() { # $1=name $2=url
  local name="$1" url="$2"
  local code
  code=$(curl -sS -o "$OUT/$name.json" -w '%{http_code}' --max-time 30 \
    -H 'Accept: application/json' -H 'Content-Type: application/json; charset=UTF-8' \
    -H 'xtbz: ykt' -H 'x-client: app' -H "X-UID: $UID_" \
    -H "Cookie: $COOKIE" -H "X-CSRFToken: $CSRF" -H "User-Agent: $UA" "$url")
  echo "--- $name  HTTP $code"
  head -c 2000 "$OUT/$name.json"; echo
  return 0
}

echo "== 0) 会话探活（/v/ 族）"
get alive "$BASE/v/course_meta/user_info"
if grep -q '"code": *50000' "$OUT/alive.json" 2>/dev/null; then
  echo "[STOP] /v/ 会话无效（code 50000 = 会话失效），先换新 sessionid 再跑。"
  exit 2
fi

echo "== 1) 课程列表（拿 classroom_id，可选）"
sleep "$SLEEP"
get learning_list "$BASE/v/course_meta/learning_list/"

echo "== 2) 签到资格（只读，核心观测点）"
sleep "$SLEEP"
get eligibility "$BASE/api/v3/lesson/location-checkin/eligibility?lessonId=$LESSON_ID"
if grep -q 'UNAUTHENTICATED' "$OUT/eligibility.json" 2>/dev/null; then
  echo "[STOP] /api/v3 族不吃网页会话，需要 App 会话（X-UID + 轮换 X-CSRFToken + sessionid）或改用 Frida 只读探针。"
  exit 3
fi

echo "== 3) 结果摘要（只打印判定字段）"
python3 - "$OUT/eligibility.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
data=d.get('data') or d
keys=['canSign','signed','wouldBeLate','isLate','pastOfficialEnd','reason','mode','timeoutMode',
      'startMs','endMs','lateAfterMs','serverTime','checkInTime','radiusM','centerLat','centerLng',
      'lat','lng','address','locationName','session','version','needLocationSignIn']
for k in keys:
    if k in data: print(f"{k:20} = {data[k]}")
PY
