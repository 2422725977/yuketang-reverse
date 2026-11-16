
import sys, os, json, re
from mitmproxy import io, http
from mitmproxy.exceptions import FlowReadException

src = sys.argv[1]
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
idx = []
n = 0
with open(src, "rb") as f:
    reader = io.FlowReader(f)
    for fl in reader.stream():
        if not isinstance(fl, http.HTTPFlow):
            continue
        n += 1
        req = fl.request
        res = fl.response
        name = "%03d" % n
        u = req.pretty_url
        safe = re.sub(r'[^A-Za-z0-9]+', '_', u.split('://',1)[-1])[:90]
        base = os.path.join(out, name + "_" + safe)
        with open(base + ".req.txt", "w") as fh:
            fh.write("%s %s %s\n" % (req.method, u, req.http_version))
            for k, v in req.headers.items():
                fh.write("%s: %s\n" % (k, v))
            fh.write("\n")
            if req.content:
                try: fh.write(req.content.decode("utf-8", "replace"))
                except Exception: pass
        if res is not None:
            with open(base + ".res.txt", "w") as fh:
                fh.write("%d %s\n" % (res.status_code, res.reason))
                for k, v in res.headers.items():
                    fh.write("%s: %s\n" % (k, v))
                fh.write("\n")
                ct = res.headers.get("content-type", "")
                if "json" in ct or "text" in ct:
                    try: fh.write(res.content.decode("utf-8", "replace")[:20000])
                    except Exception: pass
        idx.append("\t".join([name, req.method, u, str(res.status_code if res else "-"), str(len(res.content) if res and res.content else 0)]))
with open(os.path.join(out, "index.tsv"), "w") as fh:
    fh.write("\n".join(idx) + "\n")
print("flows:", n)
