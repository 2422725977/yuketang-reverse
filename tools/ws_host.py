
import re
def ctx(path, pat, before=6, after=26, label=""):
    s=open(path,encoding="utf-8",errors="replace").read().split("\n")
    for i,ln in enumerate(s):
        if re.search(pat, ln):
            print("=== %s %s:%d ===" % (label, path, i+1))
            print("\n".join(x.strip()[:120] for x in s[max(0,i-before):i+after]))
            print()
            return
ctx("blutter_out/asm/rain/core/app_constants.dart", r"baseUrlHost.*static late", 2, 30, "baseUrlHost decl")
ctx("blutter_out/asm/rain/core/app_constants.dart", r"static String baseUrlHost|baseUrlHost\\(\\)", 2, 40, "baseUrlHost getter")
