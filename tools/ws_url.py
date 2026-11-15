
import glob, re, collections
hits=collections.defaultdict(list)
for p in glob.glob("blutter_out/asm/**/*.dart", recursive=True):
    s=open(p,encoding="utf-8",errors="replace").read()
    if "wssUrl" not in s: continue
    for i,ln in enumerate(s.split("\n")):
        if "wssUrl" in ln: hits[p].append((i+1, ln.strip()[:150]))
for p,v in hits.items():
    print("#### %s (%d)" % (p, len(v)))
    for i,l in v[:8]: print("   %d: %s" % (i,l))
