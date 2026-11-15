
import re, collections, glob, os, json
def models():
    f="blutter_out/asm/rain/model/wss_operation_model.dart"
    src=open(f,encoding="utf-8",errors="replace").read().split("\n")
    cur=None;buf=[];res=collections.OrderedDict()
    for ln in src:
        m=re.match(r"^  (\S.*?)\(/\* No info \*/\)", ln)
        a=re.search(r"// \*\* addr: (0x[0-9a-f]+), size: (0x[0-9a-f]+)", ln)
        if m and not a:
            if cur: res[cur]=buf
            cur=ln.strip().rstrip(" {"); buf=[]; continue
        lit=re.findall(r'\[pp\+0x[0-9a-f]+\] "([^"]*)"', ln)
        if lit and cur: buf+=[x for x in lit if not x.startswith("========")]
    if cur: res[cur]=buf
    return res
res=models()
ks=[k for k in res if "FromMap" in k or "fromMap" in k or "fromJson" in k or "From(" in k]
print("TOTAL model ctors:", len(ks))
for k in ks[80:]:
    v=[]; [v.append(x) for x in res[k] if x not in v]
    print("  %-46s %s" % (k[:46], v[:14]))
print()
# callers of WSConnector::connect and wss url strings
hits=[]
for p in glob.glob("blutter_out/asm/**/*.dart", recursive=True):
    try: s=open(p,encoding="utf-8",errors="replace").read()
    except: continue
    if "WSConnector::connect" in s: hits.append(p)
print("connect callers:", hits[:20])
