
import re, glob, collections
for p in glob.glob("blutter_out/asm/**/*.dart", recursive=True):
    s=open(p,encoding="utf-8",errors="replace").read()
    if "WssLocationCheckinSignin" in s:
        print("SIGNIN MODEL REF:", p)
        for i,ln in enumerate(s.split("\n")):
            if "WssLocationCheckinSignin" in ln: print("   %d %s" % (i+1, ln.strip()[:120]))
print()
for p in ["blutter_out/asm/rain/websocket/processer/receiver_processer.dart","blutter_out/asm/rain/websocket/processer/remote_control_processer.dart"]:
    s=open(p,encoding="utf-8",errors="replace").read().split("\n")
    n=[ (i+1,ln.strip()[:100]) for i,ln in enumerate(s) if re.search(r'"(signin|locationcheckinext|locationcheckinend|rollcall|calledlist)"', ln)]
    print("OP LITS", p, n)
