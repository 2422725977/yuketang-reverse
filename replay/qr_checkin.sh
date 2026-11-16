#!/usr/bin/env bash
# qr_checkin.sh - 扫码/暗号签到端点探测（受控实验，一次只发一个请求）
#
# 依赖：tools/dev_replay.py（从 mitm flows 取最新 App 请求头做模板；--host 或设备内发均可）
# 用法：
#   ./replay/qr_checkin.sh eligibility                 # 只读：定位签到资格
#   ./replay/qr_checkin.sh expired   --yes             # 旧 lessonId 扫码签到（写）
#   ./replay/qr_checkin.sh legacy-web --yes --code X   # 老接口 /api/lesson/web_check_in（写）
#   ./replay/qr_checkin.sh legacy-wx  --yes           # 老接口 /wxapi/lesson_check_in（写）
#   ./replay/qr_checkin.sh dynamic    --yes --code Y   # 用有效暗号/短码走扫码分支（写）
set -u
MODE=${1:-}
shift || true
YES=0; CODE=""; LESSON="1820276486008339584"; HOSTFLAG="--host"
while [ $# -gt 0 ]; do
  case "$1" in
    --yes) YES=1 ;;
    --code) CODE="${2:-}"; shift ;;
    --lesson) LESSON="${2:-}"; shift ;;
    --device) HOSTFLAG="" ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done
cd "$(dirname "$0")/.." || exit 1
PY=/usr/local/bin/python3.13
R() { echo "--- $*"; $PY tools/dev_replay.py "$@" | head -4; echo; sleep 15; }
need_yes() { [ "$YES" = 1 ] || { echo "写请求需要 --yes（会真的打到服务端）"; exit 3; }; }

case "$MODE" in
  eligibility)
    R $HOSTFLAG --path /api/v3/lesson/location-checkin/eligibility ;;
  expired)
    need_yes
    R $HOSTFLAG --method POST --path /api/v3/lesson/checkin \
      --body "{\"lessonId\":\"$LESSON\",\"source\":42,\"joinIfNotIn\":true}" ;;
  legacy-wx)
    need_yes
    R $HOSTFLAG --method POST --path /wxapi/lesson_check_in \
      --body "{\"lesson_id\":\"${CODE:-$LESSON}\",\"source\":42,\"action\":\"scan\"}" ;;
  legacy-web)
    need_yes
    [ -n "$CODE" ] || { echo "需要 --code <课堂暗号>"; exit 3; }
    R $HOSTFLAG --method POST --path /api/lesson/web_check_in \
      --body "{\"invite_code\":\"$CODE\",\"source\":46}" ;;
  dynamic)
    need_yes
    [ -n "$CODE" ] || { echo "需要 --code <动态码/短码，长度<=11 走老接口，>11 走新接口>"; exit 3; }
    R $HOSTFLAG --method POST --path /api/v3/lesson/checkin \
      --body "{\"lessonId\":\"$CODE\",\"source\":42,\"joinIfNotIn\":true}" ;;
  *)
    sed -n '2,12p' "$0"; exit 1 ;;
esac
