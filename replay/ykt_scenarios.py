#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""雨课堂四模块场景库 —— 把报告 §10 的接口转成可直接重放的请求行

每个场景 = (标签, method, path, body)。占位符统一写 @@{NAME}（脚本内会渲染成 美元符+花括号 形式），
用 --set NAME=值 填。
  python3 ykt_scenarios.py list
  python3 ykt_scenarios.py show E1-late-localsubmit
  python3 ykt_scenarios.py emit E1-late-localsubmit --set LESSON_ID=123 --set LAT=39.9 --set LNG=116.3
  python3 ykt_scenarios.py jsonl replay/out.jsonl --group E     # 生成回放文件给 ykt_client.py replay

对照实验组（与报告 §11 一致）：
  E 签到(基线/迟到窗口/地址/重放/教师总览) / A 四条签到入口 / B 身份绑定
  H 作业(JS 桥) / C 课程作答 / D 成绩写入 / W WebSocket op 注入
"""
import argparse
import json
import sys

SCENARIOS = []


def sc(name, group, method, path, body=None, note=""):
    SCENARIOS.append({"name": name, "group": group, "method": method,
                      "path": path, "json": body, "note": note})


# ---------- 签到 ----------
sc("E0-checkin-plain", "E", "POST", "/api/v3/lesson/checkin",
   {"lessonId": "@@{LESSON_ID}", "source": 46, "joinIfNotIn": True},
   "普通签到（YuKetang::checkin 0xc521fc，source 写死 46）")
sc("A-checkin-scan", "A", "POST", "/api/v3/lesson/checkin",
   {"lessonId": "@@{LESSON_ID}", "source": 42, "joinIfNotIn": True},
   "扫码入口（_HmsScanPageState::_postLessonCheckin 0xcd042c，source=42）")
sc("A-checkin-manual", "A", "POST", "/api/v3/lesson/checkin",
   {"inviteCode": "@@{INVITE_CODE}", "source": 44, "joinIfNotIn": True},
   "手动输入数字码（_JoinClassroomDialogState::join 0xf9e3ac，source=44）")
sc("A-checkin-web", "A", "POST", "/api/lesson/web_check_in",
   {"invite_code": "@@{INVITE_CODE}", "source": 46},
   "web_check_in（同函数另一分支）")
sc("A-checkin-list", "A", "GET", "/api/v3/lesson/checkin-list?lesson_id=@@{LESSON_ID}",
   None, "教师端名单（YuKetang::fetchCheckinList 0xc5687c）")
sc("E4-loc-overview", "E", "GET",
   "/api/v3/lesson/location-checkin/overview?lessonId=@@{LESSON_ID}&session=@@{SESSION}",
   None, "教师端定位签到总览（含 isLate/lat/lng/time/address，反序列化 0x1183c14）")
sc("E2-loc-eligibility", "E", "GET",
   "/api/v3/lesson/location-checkin/eligibility?lessonId=@@{LESSON_ID}",
   None, "服务端裁决面：canSign/reason/pastOfficialEnd/wouldBeLate/lateAfterMs（0xc64f04）")
sc("E1-late-localsubmit", "E", "POST", "/api/v3/lesson/location-checkin/submit",
   {"lat": "@@{LAT}", "lng": "@@{LNG}", "lessonId": "@@{LESSON_ID}", "source": 54, "address": "@@{ADDRESS}"},
   "定位签到提交（_LocationCheckInPageState::_submit 0xdee0b0；body 无时间字段，source=54）")
sc("E3-replay-twice", "E", "POST", "/api/v3/lesson/location-checkin/submit",
   {"lat": "@@{LAT}", "lng": "@@{LNG}", "lessonId": "@@{LESSON_ID}", "source": 54, "address": "@@{ADDRESS}"},
   "同一请求重放（判定幂等/覆盖/去重）")

# ---------- 身份绑定 ----------
sc("B0-user-status", "B", "GET", "/v/course_meta/user_info", None,
   "user_status_bean: no_bind/phone_status/email_status")
sc("B2-school-query", "B", "POST", "/school_name/school_name_query", {"query": "@@{SCHOOL}"},
   "_SearchInputWidgetState::postSearchSchool 0xc9054c")
sc("B3-write-user-info", "B", "POST", "/v/course_meta/edit_user_info",
   {"avatar_96": "", "avatar": "", "name": "@@{NAME}", "role": "@@{ROLE}",
    "school": "@@{SCHOOL}", "school_number": "@@{SCHOOL_NUMBER}", "email": "@@{EMAIL}"},
   "_MyInfoPageState::_postUserInfo 0xfd37ac（客户端唯一的身份写入通道）")
sc("B4-rejoin-class", "B", "POST", "/api/v3/lesson/checkin",
   {"inviteCode": "@@{INVITE_CODE}", "source": 44, "joinIfNotIn": True},
   "裁决点：code=100038 表示服务端仍认为未绑定")

# ---------- 作业（客户端无实现：JS 桥 + OSS 直传） ----------
sc("H-callhomeworkjs", "H", "BRIDGE", "callHomeworkJS",
   {"fileUrl": "@@{FILE_URL}", "fileName": "@@{FILE_NAME}", "fileType": "@@{FILE_TYPE}",
    "fileSize": "@@{FILE_SIZE}", "uploader": "@@{UPLOADER}"},
   "JsCallFlutter::postHomeworkDataToJS 0xbc6004 回调（JS 桥，不是 HTTP）")
sc("H-token", "H", "BRIDGE", "getTokenData",
   {"problem_id": "@@{PROBLEM_ID}", "exercise_id": "@@{EXERCISE_ID}"},
   "JsCallFlutter::getTokenData 0xbc5024 → OSS 直传凭据")
sc("H-upload", "H", "BRIDGE", "uploadFile",
   {"from": "@@{FROM}", "tokenUrl": "@@{TOKEN_URL}", "problem_id": "@@{PROBLEM_ID}",
    "exercise_id": "@@{EXERCISE_ID}"},
   "JsCallFlutter::uploadFile 0xbc676c")

# ---------- 课程作答 ----------
sc("C-answer-subjective", "C", "POST", "/api/v3/lesson/problem/answer",
   {"problemId": "@@{PROBLEM_ID}", "problemType": "@@{PROBLEM_TYPE}", "result": "@@{RESULT}"},
   "_SubjectiveQuestionPageState::_submit 0xe0164c")
sc("C-answer-choice", "C", "POST", "/api/v3/lesson/problem/answer",
   {"problemId": "@@{PROBLEM_ID}", "problemType": "@@{PROBLEM_TYPE}", "result": "@@{RESULT}", "dt": "@@{DT}"},
   "_SingleChoiceQuestionPageState::_submitAnswer 0xdf5a34（POST 调用点 0xdf5c84；dt 客户端自报耗时）")
sc("C-answer-fetch", "C", "POST", "/api/v3/lesson/problem/fetch-answer", {"problem_id": "@@{PROBLEM_ID}"},
   "看答案（客户端只做展示）")
sc("C-rapid-participate", "C", "POST", "/api/v3/lesson/rapid-answer/participate",
   {"lessonId": "@@{LESSON_ID}"}, "_ReceiverClassPageState::_submitRapidAnswer 0xbd9088")
sc("C-rapid-score", "C", "POST", "/api/v3/lesson/rapid-answer/score",
   {"qiangda_add_score": "@@{SCORE}", "score": "@@{SCORE}", "lessonId": "@@{LESSON_ID}"},
   "教师加分（qiangda_add_score_dialog.dart）")
sc("C-danmu-send", "C", "POST", "/api/v3/lesson/danmu/send",
   {"lessonId": "@@{LESSON_ID}", "message": "@@{MESSAGE}", "extra": "", "target": "",
    "userName": "@@{NAME}", "fromStart": False, "requiredCensor": 1, "showStatus": 0, "wordCloud": 0},
   "YuKetang::sendDanmu 0xd7ccdc（requiredCensor/showStatus 是客户端参数）")
sc("C-video-problem-reply", "C", "POST",
   "/mooc-api/v1/lms/exercise/leaf_video/problem/reply/@@{LEAF_ID}/@@{EXERCISE_ID}/",
   {"answer": "@@{ANSWER}"}, "课程视频 AI 习题作答（aiproblem/*.dart）")

# ---------- 成绩 ----------
sc("D-give-huping", "D", "POST",
   "/api/v3/lesson/problem/grade?userId=@@{UID}&groupId=@@{GID}&teamId=@@{TID}&reviewScore=@@{REVIEW_SCORE}",
   {"problemId": "@@{PROBLEM_ID}", "score": "@@{SCORE}", "content": "@@{CONTENT}", "comment": "@@{COMMENT}"},
   "YuKetang::giveHupingScore 0x10c0acc（互评分/教师评分均为客户端参数）")
sc("D-submit-review-score", "D", "POST", "/api/v3/lesson/review/submit-review-score",
   {"reviewId": "@@{REVIEW_ID}", "score": "@@{SCORE}"}, "互评打分写入点")
sc("D-teacher-score-detail", "D", "POST", "/api/v3/lesson/problem/teacher/score-detail",
   {"problem_id": "@@{PROBLEM_ID}", "userId": "@@{UID}"}, "教师评分明细查看")
sc("D-score-detail", "D", "GET", "/api/v3/lesson/problem/score-detail?problem_id=@@{PROBLEM_ID}",
   None, "YuKetang::scoreDetail 0xd59ed0")

# ---------- WebSocket 注入（报告 §12 的 unverified 项） ----------
sc("W-hello-student", "W", "WS", "hello",
   {"op": "hello", "lessonid": "@@{LESSON_ID}", "userid": "@@{UID}", "role": "student", "auth": "@@{AUTH}"},
   "学生握手帧（握手无鉴权头，身份全靠这一帧）")
sc("W-hello-lecturer", "W", "WS", "hello",
   {"op": "hello", "lessonid": "@@{LESSON_ID}", "userid": "@@{UID}", "role": "lecturer",
    "auth": "@@{AUTH}", "avatar": ""}, "教师握手帧")
for _name, _op in [
    ("W-inject-detectlesson", {"op": "detectlesson", "lessonid": "@@{LESSON_ID}"}),
    ("W-inject-sendpost", {"op": "sendpost", "postid": "@@{POST_ID}", "msgid": 1234}),
    ("W-inject-launchreview", {"op": "launchreview",
                               "review": {"type": 1, "sid": "@@{SID}", "prob": "@@{PROBLEM_ID}",
                                          "reviewid": "@@{REVIEW_ID}"}}),
    ("W-inject-showpresentation", {"op": "showpresentation", "presentation": "@@{PRESENTATION}",
                                   "slideid": 1, "slideindex": 1, "step": 1, "total": 1, "title": ""}),
    ("W-inject-rollcall", {"op": "rollcall", "range": "@@{RANGE}"}),
    ("W-inject-closemask", {"op": "closemask", "msgid": 1234, "type": "subjective"}),
]:
    sc(_name, "W", "WS", _op["op"], _op,
       "教师专属 op 注入：判定服务端是否按 role 过滤（学生连接发它是否生效）")

# 渲染：脚本内部把 @@{ 还原成 美元符+花括号
RENDER = {"@@{": "$" + "{"}


def render(s):
    for k, v in RENDER.items():
        s = s.replace(k, v)
    return s


def fill(obj, sets):
    if isinstance(obj, dict):
        return {k: fill(v, sets) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fill(v, sets) for v in obj]
    if isinstance(obj, str):
        out = render(obj)
        for k, v in sets.items():
            out = out.replace("$" + "{" + k + "}", v)
        return out
    return obj


def main():
    ap = argparse.ArgumentParser(description="雨课堂场景库")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("show"); p.add_argument("name"); p.add_argument("--set", action="append", default=[])
    p = sub.add_parser("emit"); p.add_argument("name"); p.add_argument("--set", action="append", default=[])
    p = sub.add_parser("jsonl"); p.add_argument("out"); p.add_argument("--group", default=None)
    a = ap.parse_args()
    sets = dict(x.split("=", 1) for x in getattr(a, "set", []))
    if a.cmd == "list":
        for s in SCENARIOS:
            print("%-26s [%s] %-5s %-62s  %s" % (s["name"], s["group"], s["method"],
                                                 s["path"][:62], s["note"][:46]))
    elif a.cmd in ("show", "emit"):
        for s in SCENARIOS:
            if s["name"] == a.name:
                print(json.dumps(fill(s, sets), ensure_ascii=False, indent=2))
                return 0
        print("no such scenario: " + a.name, file=sys.stderr)
        return 1
    elif a.cmd == "jsonl":
        n = 0
        with open(a.out, "w", encoding="utf-8") as fh:
            for s in SCENARIOS:
                if s["method"] in ("BRIDGE", "WS"):
                    continue
                if a.group and s["group"] != a.group:
                    continue
                fh.write(json.dumps({"name": s["name"], "method": s["method"],
                                     "path": render(s["path"]), "json": fill(s["json"], {})},
                                    ensure_ascii=False) + "\n")
                n += 1
        print("%s: %d lines" % (a.out, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
