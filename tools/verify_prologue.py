import capstone, re
so="/Users/xi/Documents/deepseek-harness/ctf/ykt/applibs/libapp.so"
asm="/Users/xi/Documents/deepseek-harness/ctf/ykt/blutter_out/asm/rain/receiver_page/location/location_check_in_page.dart"
addrs={"0xdee0b0 (submit)":0xdee0b0,"0xc62da8 (updateRangeState)":0xc62da8,"0xc64f04 (loadEligibility)":0xc64f04}
data=open(so,"rb").read()
md=capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
lines=open(asm,encoding="utf-8",errors="ignore").read().split("\n")
def asm_at(a):
    out=[]
    for l in lines:
        m=re.match(r"\s*//\s*0x([0-9a-f]+):\s*(.*)",l)
        if m and int(m.group(1),16)>=a: out.append((int(m.group(1),16),m.group(2).strip()))
        if len(out)>=4: break
    return out
for k,a in addrs.items():
    print("==",k)
    code=data[a:a+16]
    for i in md.disasm(code, a):
        print("   file: 0x%x %s %s" % (i.address,i.mnemonic,i.op_str))
    for ad,txt in asm_at(a): print("   asm : 0x%x %s" % (ad,txt))
