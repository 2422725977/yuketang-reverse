import sys,re
p="/Users/xi/Documents/deepseek-harness/ctf/ykt/so/lib/arm64-v8a/libapp.so"
data=open(p,'rb').read()
n=len(data)
def valid(cp):
    if 0x20<=cp<=0x7e: return True
    if cp in (9,10,13): return True
    if 0x4e00<=cp<=0x9fff: return True
    if 0x3000<=cp<=0x303f: return True
    if 0xff00<=cp<=0xffef: return True
    if 0x2000<=cp<=0x27bf: return True
    if 0x00b7==cp or 0x00a0==cp: return True
    if 0x1f000<=cp<=0x1faff: return True
    if 0x0400<=cp<=0x04ff: return True
    return False
def decode_at(off):
    # expand to run
    a=off
    while a-2>=0:
        cp=data[a-2]|(data[a-1]<<8)
        if valid(cp): a-=2
        else: break
    b=off
    while b+2<=n:
        cp=data[b]|(data[b+1]<<8)
        if valid(cp): b+=2
        else: break
    try:
        s=data[a:b].decode('utf-16-le')
    except Exception:
        return None,a
    return s,a
kws=sys.argv[1:]
seen=set()
for kw in kws:
    b=kw.encode('utf-16-le')
    idx=0
    cnt=0
    while True:
        i=data.find(b,idx)
        if i<0: break
        idx=i+1
        if i%2: continue
        s,a=decode_at(i)
        if s is None: continue
        if not (2<=len(s)<=160): continue
        key=(a,s)
        if key in seen: continue
        seen.add(key)
        cnt+=1
        print("["+kw+"] 0x%x %s"%(a,s.replace("\\n"," ")))
        if cnt>60: break
