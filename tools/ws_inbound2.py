
import re, collections
def analyze(path, tag):
    lines=open(path,encoding="utf-8",errors="replace").read().split("\n")
    blocks=[]; cur=None
    for i,ln in enumerate(lines):
        if "r16 = " in ln and i+1<len(lines):
            m=re.search(r'\[pp\+0x[0-9a-f]+\] "([^"]*)"', lines[i+1])
            if m:
                cur={"op":m.group(1),"start":i,"txt":[]}; blocks.append(cur); continue
        if cur is not None: cur["txt"].append(ln)
    print("####", tag)
    for b in blocks:
        t="\n".join(b["txt"])
        alloc=re.findall(r"Allocate\w*Stub -> (\w+) \(size=", t)
        frm=re.findall(r";\s*\[[^\]]+\]\s+(\S+)", t)
        models=[x for x in frm if re.search(r"(Op|Bean|Model|Event)::", x) or "From" in x]
        ev=[x for x in frm if "EventBus" in x]
        seen=[]
        for x in alloc+models:
            if x not in seen: seen.append(x)
        print("  %-22s -> %s" % (b["op"], " | ".join(seen[:5]) if seen else "(none)"))
analyze("blutter_out/asm/rain/websocket/processer/receiver_processer.dart","receiver: op -> event/bean")
