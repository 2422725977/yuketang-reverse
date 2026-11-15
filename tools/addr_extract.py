import re, sys
specs=[("receiver_page/location/location_check_in_page.dart",["_submit","_updateRangeState","_loadEligibility","_applyRangeStateInPlace"]),
("receiver_page/receiver_class_page.dart",["_postLessonCheckin","_submitRapidAnswer"]),
("receiver_page/score_each_other_page.dart",["_submitScore"]),
("ui_widget/app_js_call_flutter.dart",["openHomeworkFile","postHomeworkDataToJS"]),
("network/yuketang.dart",["checkin","sendDanmu"])]
base="/Users/xi/Documents/deepseek-harness/ctf/ykt/blutter_out/asm/rain/"
for f,names in specs:
    lines=open(base+f,encoding="utf-8",errors="ignore").read().split("\n")
    for n in names:
        for i,l in enumerate(lines):
            s=l.strip()
            if s.startswith("_ "+n+"("):
                for j in range(i,min(i+600,len(lines))):
                    m=re.search(r"0x([0-9a-f]{5,9}):",lines[j])
                    if m:
                        print("%-55s %-26s entry=0x%s" % (f,n,m.group(1))); break
                break
