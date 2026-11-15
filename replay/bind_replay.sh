#!/usr/bin/env bash
# 雨课堂「身份绑定」实验组 B0-B4 —— 验证绑定到底是客户端流程还是服务端裁决
# 用法: BASE_URL=https://www.yuketang.cn COOKIE='csrftoken=..; sessionid=..' X_CSRF=.. X_UID=.. \
#        SCHOOL='示例大学' SCHOOL_NO='20250001' INVITE_CODE=ABCD \
#        ./bind_replay.sh [status|school|write|verdict|all]
# 产物: runs/<TAG>-<时间戳>/<name>.{req.json,res.json,code}
set -euo pipefail

MODE="${1:-all}"
BASE_URL="${BASE_URL:-https://www.yuketang.cn}"
COOKIE="${COOKIE:-}"
X_CSRF="${X_CSRF:-}"
X_UID="${X_UID:-}"
UA="${UA:-Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 RainClassroom}"
SCHOOL="${SCHOOL:-[SCHOOL]}"
SCHOOL_NO="${SCHOOL_NO:-[SCHOOL_NO]}"
SCHOOL_NAME="${SCHOOL_NAME:-${SCHOOL}}"
NAME="${NAME:-[NAME]}"
ROLE="${ROLE:-1}"
EMAIL="${EMAIL:-}"
INVITE_CODE="${INVITE_CODE:-[INVITE_CODE]}"
TAG="${TAG:-bind}"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="runs/${TAG}-${TS}"
mkdir -p "$OUT"

if [[ -z "$COOKIE" ]]; then echo '[!] 需要 COOKIE（csrftoken=..; sessionid=..）' >&2; exit 2; fi

hdr=(-H "Cookie: ${COOKIE}" -H "X-CSRFToken: ${X_CSRF}" -H "X-UID: ${X_UID}" -H "User-Agent: ${UA}")
hdr_json=(-H 'Content-Type: application/json' -H 'Accept: application/json')

save() { # save <name> <body-file-or->
  local name="$1"; shift
  local body; body="$1"
  if [[ "$body" == "-" ]]; then cat > "$OUT/$name.res.json"; else printf '%s' "$body" > "$OUT/$name.res.json"; fi
  echo "  -> $OUT/$name.res.json"
}

run() { # run <name> <method> <path> [json-body]
  local name="$1" method="$2" path="$3" data="${4:-}"
  echo "[B] $name $method $path"
  printf '%s' "${data:-{}}" > "$OUT/$name.req.json"
  local code
  if [[ -n "$data" ]]; then
    code=$(curl -sS -o "$OUT/$name.res.json" -w '%{http_code}' -X "$method" "${BASE_URL}${path}" "${hdr[@]}" "${hdr_json[@]}" -d "$data" || echo 000)
  else
    code=$(curl -sS -o "$OUT/$name.res.json" -w '%{http_code}' -X "$method" "${BASE_URL}${path}" "${hdr[@]}" "${hdr_json[@]}" || echo 000)
  fi
  printf '%s' "$code" > "$OUT/$name.code"
  echo "  HTTP $code  -> $OUT/$name.res.json"
  if command -v jq >/dev/null 2>&1; then
    jq -c '{code:(.code//.error_code),msg:(.msg//.message),school,school_number,role,data:(.data|type)}' "$OUT/$name.res.json" 2>/dev/null || head -c 300 "$OUT/$name.res.json"; echo
  else
    head -c 300 "$OUT/$name.res.json"; echo
  fi
}

do_status()  { run B1-status GET  /v/course_meta/user_info; }
do_school()  { run B2-school POST /school_name/school_name_query "{\"query\":\"${SCHOOL_NAME}\"}"; }
do_write()   { run B3-write  POST /v/course_meta/edit_user_info "{\"name\":\"${NAME}\",\"role\":${ROLE},\"school\":\"${SCHOOL}\",\"school_number\":\"${SCHOOL_NO}\",\"email\":\"${EMAIL}\"}"; }
do_verdict() { run B4-verdict POST /api/v3/lesson/checkin "{\"inviteCode\":\"${INVITE_CODE}\",\"source\":44,\"joinIfNotIn\":true}"; }

case "$MODE" in
  status)  do_status ;;
  school)  do_school ;;
  write)   do_write ;;
  verdict) do_verdict ;;
  all)     do_status; do_school; do_write; do_status; do_verdict ;;
  *) echo "用法: $0 [status|school|write|verdict|all]" >&2; exit 2 ;;
esac

echo
echo "[判定] B4 返回 code=100038/100030 → 服务端仍认为未绑定（任何客户端 patch 都只是半状态）"
echo "[判定] B4 返回 200 且 success=true → 该账号已被服务端承认绑定，B3 就是绑定通道本身"
echo "[产物] $OUT"
