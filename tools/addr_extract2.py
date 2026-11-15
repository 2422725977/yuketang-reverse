import re
specs=[("receiver_page/exam_page.dart",["reprotExam","reprotExamShowToast","_detectGuangsuVirtualMachine","_listenAppSizeChange","postAutoPhotoUpload"]),
("receiver_page/single_choice_question_page.dart",["_submitAnswer","submitAnswer"]),
("ui_widget/app_js_call_flutter.dart",["dispatchAction","uploadFile","getTokenData"]),
("network/yuketang.dart",["scoreDetail","giveHupingScore","fetchCheckinList"]),
("receiver_page/subjective_question_page.dart",["_submit","_postAnswer"]),
("core/app.dart",["_getInterceptor"]),
("xuetang_base/xuetang_base_net.dart",["requestPost","addHeader"]),
("receiver_page/location/location_check_in_page.dart",["_fetchRangePreview","_onLocationCheckinExt","_onLocationCheckinEnd"])]
base="/Users/xi/Documents/deepseek-harness/ctf/ykt/blutter_out/asm/"
files={}
import os
for root,d,fns in os.walk(base):
    for fn in fns:
        files.setdefault(fn, os.path.join(root,fn))
for f,names in specs:
    p=files.get(f)
    if not p: print("MISSING",f); continue
    lines=open(p,encoding="utf-8",errors="ignore").read().split("\n")
    for n in names:
        hit=False
        for i,l in enumerate(lines):
            s=l.strip()
            if s.startswith("_ "+n+"(") or s.startswith("static _ "+n+"(") or (n in s and s.endswith("(/* No info */) {") and s.split("(")[0].endswith(n)):
                for j in range(i,min(i+800,len(lines))):
                    m=re.search(r"addr: 0x([0-9a-f]{5,9})",lines[j])
                    if m: print("%-52s %-26s addr=0x%s" % (f,n,m.group(1))); hit=True; break
                if hit: break
        if not hit: print("%-52s %-26s NOTFOUND" % (f,n))
