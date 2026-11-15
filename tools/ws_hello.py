
import re
fil = re.compile(r"addr: 0x|LoadField|r0 = \"|r16 = \"|\[package:rain|\[package:xuetang")
def show(path, pat, before=90, after=4, label=""):
    s=open(path,encoding="utf-8",errors="replace").read().split("\n")
    for i,ln in enumerate(s):
        if re.search(pat, ln):
            print("=== %s %s:%d ===" % (label, path, i+1))
            seg=s[max(0,i-before):i+after]
            print("\n".join(x.strip()[:135] for x in seg if fil.search(x)))
            print(); return
show("blutter_out/asm/rain/receiver_page/receiver_class_page.dart", r"WSConnector::sendHelloFromStudent", 200, 4, "student hello")
show("blutter_out/asm/rain/remote_control/remote_control_tab_page.dart", r"WSConnector::sendHelloFromTeacher", 120, 4, "teacher hello")
