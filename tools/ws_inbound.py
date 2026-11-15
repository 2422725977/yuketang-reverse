
import re, collections
def walk(path, tag):
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    out = collections.OrderedDict(); cur = None
    for i, ln in enumerate(lines):
        if "r16 = " in ln and i+1 < len(lines):
            m = re.search(r'\[pp\+0x[0-9a-f]+\] "([^"]*)"', lines[i+1])
            if m:
                cur = m.group(1); out.setdefault(cur, []); continue
        if cur is None: continue
        a = re.search(r";\s*\[[^\]]+\]\s+(\S+)\s*$", ln)
        if a:
            s = a.group(1)
            if ("Op" in s or "Bean" in s or "Event" in s) and s not in out[cur]:
                out[cur].append(s)
    print("#### %s (%d ops)" % (tag, len(out)))
    for k, v in out.items():
        print("  %-22s -> %s" % (k, " | ".join(v[:5])))
walk("blutter_out/asm/rain/websocket/processer/receiver_processer.dart", "receiver")
walk("blutter_out/asm/rain/websocket/processer/remote_control_processer.dart", "remote_control")
