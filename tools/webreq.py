
import sys, json, subprocess
sys.path.insert(0,'/Users/xi/Documents/deepseek-harness/ctf/ykt/tools')
from mitmproxy import io

def pick():
    best=None
    with open('/tmp/mitm/flows.mitm','rb') as f:
        for fl in io.FlowReader(f).stream():
            r=getattr(fl,'request',None)
            if not r: continue
            h=dict(r.headers)
            if h.get('x-client')!='web': continue
            ck=h.get('cookie','')
            if 'sessionid=' not in ck: continue
            best=(h, r.pretty_url)
    return best

def send(path, hdrs, tmpl, method='GET', body=None):
    args=['curl','-s','-o','/tmp/replay.out','-w','%{http_code}','--max-time','25','-X',method]
    for k,v in hdrs.items():
        if k.lower() in ('accept-encoding','host','content-length','connection'): continue
        args+=['-H','%s: %s'%(k,v)]
    if body is not None:
        args+=['--data-raw', json.dumps(body,ensure_ascii=False,separators=(',',':'))]
    args.append('https://www.yuketang.cn'+path)
    r=subprocess.run(args,capture_output=True,text=True)
    code=(r.stdout or '').strip()
    out=open('/tmp/replay.out',errors='replace').read()
    return code,out,tmpl

h,t=pick()
print('template:',t)
print('has sessionid hdr:', 'sessionid' in h, 'cookie len', len(h.get('cookie','')))
paths=sys.argv[1:]
for p in paths:
    code,out,tmpl=send(p,h,t)
    print('==',p,'->',code)
    print(out[:600])
    print()
