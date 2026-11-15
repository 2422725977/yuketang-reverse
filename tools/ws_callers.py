
import re, glob, collections
pat=re.compile(r"WSConnector[::\.\w]*")
usages=collections.defaultdict(list)
urlish=collections.defaultdict(list)
for p in glob.glob("blutter_out/asm/**/*.dart", recursive=True):
    s=open(p,encoding="utf-8",errors="replace").read()
    if "ws_connector.dart" not in s: continue
    for i,ln in enumerate(s.split("\n")):
        m=re.search(r";\s*\[[^\]]*ws_connector\.dart\]\s+(\S+)", ln)
        if m: usages[m.group(1)].append(p+":"+str(i+1))
print("=== ws_connector referenced symbols ===")
for k,v in sorted(usages.items(), key=lambda x:-len(x[1])):
    print(" %-44s %2d  %s" % (k, len(v), v[0]+ (" (+%d)"%(len(v)-1) if len(v)>1 else "")))
print()
print("=== ws:// or wss:// literal occurrences ===")
for p in glob.glob("blutter_out/asm/**/*.dart", recursive=True):
    s=open(p,encoding="utf-8",errors="replace").read()
    for i,ln in enumerate(s.split("\n")):
        m=re.search(r'\[pp\+0x[0-9a-f]+\] "([^"]*ws[^"]*)"', ln)
        if m: urlish[m.group(1)].append(p+":"+str(i+1))
for k,v in urlish.items(): print(" ", k, "->", v[:4])
