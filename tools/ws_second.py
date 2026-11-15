
import re
s=open("blutter_out/asm/rain/receiver_page/receiver_class_page.dart",encoding="utf-8",errors="replace").read().split("\n")
target=54224
# find nearest preceding function header and addr
for i in range(target-1, 0, -1):
    m=re.match(r"^  (\S.*?)\(/\* No info \*/\)", s[i])
    if m:
        print("function:", s[i].strip()); 
        for j in range(i, min(i+6, len(s))):
            a=re.search(r"// \*\* addr: (0x[0-9a-f]+), size: (0x[0-9a-f]+)", s[j])
            if a: print("  addr", a.group(1), "size", a.group(2)); break
        break
print("--- context ---")
print("\n".join(x.strip()[:130] for x in s[54200:54270] if re.search(r"addr: 0x|r0 = \"|r16 = \"|LoadField|\[package:rain", x)))
