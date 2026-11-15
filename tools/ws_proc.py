
import re, os, glob, collections
asm = "blutter_out/asm"
# 1. processer function headers + literals
for f in sorted(glob.glob(asm + "/rain/websocket/processer/*.dart")):
    print("#### ", f, os.path.getsize(f))
    src = open(f, encoding="utf-8", errors="replace").read().split("\n")
    for i, ln in enumerate(src):
        m = re.search(r"// \*\* addr: (0x[0-9a-f]+), size: (0x[0-9a-f]+)", ln)
        if m:
            print("   fn@%d %s size %s" % (i+1, m.group(1), m.group(2)), src[i-1].strip()[:70])
    lits = collections.Counter(re.findall(r'\[pp\+0x[0-9a-f]+\] "([^"]*)"', "\n".join(src)))
    print("   TOPLITS:", lits.most_common(30))
