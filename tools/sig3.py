d=open("/Users/xi/Documents/deepseek-harness/ctf/ykt/applibs/libapp.so","rb").read()
rows=[("YuKetang.checkin",0xc521fc),("LCIPS._submit",0xdee0b0),("LCIPS._updateRangeState",0xc62da8),("LCIPS._loadEligibility",0xc64f04),("LCIPS._fetchRangePreview",0xc62e20),("RCP._postLessonCheckin",0xc196cc),("RCP._submitRapidAnswer",0xbd9088),("SEOP._submitScore",0x1041308),("SCQP._submitAnswer",0xdf5a34),("JsCallFlutter.dispatchAction",0xba725c),("JsCallFlutter.postHomeworkDataToJS",0xbc6004),("JsCallFlutter.openHomeworkFile",0xbd3814),("ExamPage.reprotExam",0x93d76c),("YuKetang.scoreDetail",0xd59ed0),("YuKetang.giveHupingScore",0x10c0acc),("BaseNet.requestPost",0x923178)]
for n,a in rows:
    print('  { name: "%s", rva: 0x%x, guard: [0x%s, 0x%s] },' % (n,a,d[a:a+4].hex(),d[a+8:a+12].hex()))
