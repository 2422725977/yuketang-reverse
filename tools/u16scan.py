import re,sys
p=sys.argv[1]
data=open(p,'rb').read()
# scan UTF-16LE: collect runs where the high byte is 0 and low byte printable-ish, or CJK pairs 0x4E00-0x9FFF
runs=[]
i=0
n=len(data)
cur=bytearray()
start=0
def flush():
    global cur
    if len(cur)>=6:
        try:
            s=cur.decode('utf-16-le')
        except Exception:
            s=None
        if s:
            runs.append(s)
    cur=bytearray()
while i+1 < n:
    lo=data[i]; hi=data[i+1]
    cp=lo | (hi<<8)
    ok=False
    if hi==0 and (0x20<=lo<=0x7e or lo==9):
        ok=True
    elif 0x2000<=cp<=0x9fff or 0xff00<=cp<=0xffef or cp in (0x2018,0x2019,0x201c,0x201d,0x2026,0x3001,0x3002,0x00b7):
        ok=True
    elif 0x4e00<=cp<=0x9fff:
        ok=True
    if ok:
        if not cur: start=i
        cur.append(lo); cur.append(hi)
        i+=2
    else:
        flush(); i+=2
flush()
print(len(runs))
import io
with open(sys.argv[2],'w',encoding='utf-8') as f:
    for r in runs:
        f.write(r+"\n")
