import lief, re
so="/Users/xi/Documents/deepseek-harness/ctf/ykt/applibs/libapp.so"
b=lief.parse(so)
print("format",b.header.file_type if hasattr(b.header,'file_type') else '?')
for s in b.sections:
    print("%-16s vaddr=0x%-10x off=0x%-10x size=0x%-10x flags=%s" % (s.name, s.virtual_address, s.file_offset, s.size, str(s.flags)))
open("/tmp/x.txt","w").write("")
