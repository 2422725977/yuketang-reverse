
import glob, collections, re
c=collections.Counter()
locs=collections.defaultdict(list)
for p in glob.glob("blutter_out/asm/**/*.dart", recursive=True):
    s=open(p,encoding="utf-8",errors="replace").read()
    n=s.count("WSConnector")
    if n: c[p]=n
for p,n in c.most_common(14): print("%4d %s" % (n,p))
print()
# show ctor call sites
for p,n in c.most_common(8):
    s=open(p,encoding="utf-8",errors="replace").read().split("\n")
    for i,ln in enumerate(s):
        if re.search(r";\s*\[[^\]]*ws_connector\.dart\]\s+WSConnector::WSConnector", ln):
            print("CTOR", p+":"+str(i+1))
            print("   ", "\n    ".join(x.strip()[:110] for x in s[max(0,i-14):i+2]))
            break
