
import re, collections, glob, os
# rest of remote_control ops
lines = open("blutter_out/asm/rain/websocket/processer/remote_control_processer.dart", encoding="utf-8", errors="replace").read().split("\n")
out = collections.OrderedDict(); cur=None
for i, ln in enumerate(lines):
    if "r16 = " in ln and i+1 < len(lines):
        m = re.search(r'\[pp\+0x[0-9a-f]+\] "([^"]*)"', lines[i+1])
        if m: cur = m.group(1); out.setdefault(cur, []); continue
    if cur is None: continue
    a = re.search(r";\s*\[[^\]]+\]\s+(\S+)\s*$", ln)
    if a:
        s=a.group(1)
        if ("Op" in s or "Bean" in s or "Event" in s) and s not in out[cur]: out[cur].append(s)
keys=list(out)
print("remote_control ops 30..:", " | ".join(keys[30:]))
print()
# model file literals
for f in glob.glob("blutter_out/asm/rain/model/wss_operation_model.dart"):
    print("####", f, os.path.getsize(f))
    src=open(f,encoding="utf-8",errors="replace").read().split("\n")
    cur=None; buf=[]
    res=collections.OrderedDict()
    for i,ln in enumerate(src):
        m=re.match(r"^  (\S.*?)\(/\* No info \*/\)", ln)
        a=re.search(r"// \*\* addr: (0x[0-9a-f]+), size: (0x[0-9a-f]+)", ln)
        if m and not a:
            if cur: res[cur]=buf
            cur=ln.strip().rstrip(" {"); buf=[]; continue
        lit=re.findall(r'\[pp\+0x[0-9a-f]+\] "([^"]*)"', ln)
        if lit and cur:
            buf+= [x for x in lit if not x.startswith("========")]
    if cur: res[cur]=buf
    for k,v in res.items():
        seen=[]; [seen.append(x) for x in v if x not in seen]
        print("  %-46s %s" % (k[:46], seen[:16]))
