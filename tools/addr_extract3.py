import re
R="/Users/xi/Documents/deepseek-harness/ctf/ykt/blutter_out/asm/rain/"
X="/Users/xi/Documents/deepseek-harness/ctf/ykt/blutter_out/asm/"
specs=[(R+"receiver_page/exam_page.dart",["reprotExam","reprotExamShowToast","_detectGuangsuVirtualMachine","_listenAppSizeChange","postAutoPhotoUpload"]),
(R+"receiver_page/single_choice_question_page.dart",["_submit","_answer","_post"]),
(R+"ui_widget/app_js_call_flutter.dart",["dispatchAction","uploadFile","getTokenData","postHomeworkDataToJS"]),
(R+"network/yuketang.dart",["scoreDetail","giveHupingScore","fetchCheckinList"]),
(R+"receiver_page/subjective_question_page.dart",["_submit","_answer","_post"]),
(R+"core/app.dart",["_getInterceptor"]),
(X+"xuetang_base/xuetang_base_net.dart",["requestPost","addHeader"]),
(R+"receiver_page/location/location_check_in_page.dart",["_fetchRangePreview","_onLocationCheckinExt","_onLocationCheckinEnd"])]
for p,names in specs:
    lines=open(p,encoding="utf-8",errors="ignore").read().split("\n")
    print("### "+p.split("/asm/")[-1])
    for n in names:
        found=[]
        for i,l in enumerate(lines):
            if re.match(r"^\s*(static )?_ "+re.escape(n)+r"\(",l):
                for j in range(i,min(i+900,len(lines))):
                    m=re.search(r"addr: 0x([0-9a-f]{5,9})",lines[j])
                    if m: found.append((n,m.group(1))); break
                break
        print("   ", found if found else n+" NOTFOUND")
