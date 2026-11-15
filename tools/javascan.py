#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫 Java/原生层：WebView 配置、JS 桥、证书校验、加固/反调试面。"""
import os, re, json, collections

ROOT = "/Users/xi/Documents/deepseek-harness/ctf/ykt/jadx"
PATTERNS = {
    "addJavascriptInterface": re.compile(r"addJavascriptInterface\s*\("),
    "removeJavascriptInterface": re.compile(r"removeJavascriptInterface\s*\("),
    "setJavaScriptEnabled": re.compile(r"setJavaScriptEnabled\s*\("),
    "setAllowFileAccess": re.compile(r"setAllowFileAccess(FromFileURLs|FromFileURLs)?\s*\("),
    "setAllowUniversalAccess": re.compile(r"setAllowUniversalAccessFromFileURLs\s*\("),
    "setAllowContentAccess": re.compile(r"setAllowContentAccess\s*\("),
    "setDomStorageEnabled": re.compile(r"setDomStorageEnabled\s*\("),
    "setMixedContent": re.compile(r"setMixedContentMode\s*\("),
    "setSavePassword": re.compile(r"setSavePassword\s*\("),
    "onReceivedSslError": re.compile(r"onReceivedSslError\s*\("),
    "proceed_ssl": re.compile(r"\.proceed\s*\(\s*\)"),
    "TrustManager": re.compile(r"X509TrustManager|TrustManagerFactory|checkServerTrusted"),
    "HostnameVerifier": re.compile(r"HostnameVerifier|setDefaultHostnameVerifier|ALLOW_ALL_HOSTNAME"),
    "CertificatePinner": re.compile(r"CertificatePinner|sha256/"),
    "SSLContext_init": re.compile(r"SSLContext\.getInstance"),
    "NetworkSecurityConfig": re.compile(r"networkSecurityConfig|network_security_config"),
    "debuggable_check": re.compile(r"ApplicationInfo\.FLAG_DEBUGGABLE|isDebuggerConnected|waitingForDebugger"),
    "root_check": re.compile(r"su\b.*(/system/bin/su|/sbin/su)|Superuser\.apk|test-keys|isRooted|RootBeer"),
    "emulator_check": re.compile(r"goldfish|ranchu|EmulatorDetector|isEmulator|Build\.FINGERPRINT.*generic"),
    "frida_check": re.compile(r"frida|FRIDA|gum-js-loop|linjector"),
    "xposed_check": re.compile(r"Xposed|de\.robv\.android\.xposed|getXposedBridge"),
    "JNI_RegisterNatives": re.compile(r"RegisterNatives|JNI_OnLoad"),
    "System_loadLibrary": re.compile(r"System\.loadLibrary\s*\("),
    "getRunningAppProcesses": re.compile(r"getRunningAppProcesses\s*\("),
    "reflection_calls": re.compile(r"Class\.forName\s*\("),
    "shell_hint": re.compile(r"360|Qihoo|jiagu|libjiagu|bangcle|SecShell|tencent.*stub|libshell|apktool|签名校验"),
}

hits = collections.defaultdict(list)
files_scanned = 0
for dirpath, dirnames, filenames in os.walk(ROOT):
    for fn in filenames:
        if not fn.endswith((".java", ".kt", ".xml")):
            continue
        p = os.path.join(dirpath, fn)
        files_scanned += 1
        try:
            text = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for name, rx in PATTERNS.items():
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                hits[name].append("%s:%d" % (os.path.relpath(p, ROOT), line))

print("scanned files:", files_scanned)
for name in PATTERNS:
    lst = hits.get(name, [])
    print("\n## %s  (%d hits)" % (name, len(lst)))
    for h in lst[:14]:
        print("   ", h)
    if len(lst) > 14:
        print("    ... +%d more" % (len(lst) - 14))
