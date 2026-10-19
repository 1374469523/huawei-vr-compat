"""List the JNI surface of each original package against its own native libs.

A method declared ``native`` only works if some library that implements it is
loaded into the class loader - either one shipped inside the APK or a platform
library the code loads by absolute path. Anything else throws
``UnsatisfiedLinkError`` the first time it is called, which on this port killed
the original handle service:

    java.lang.UnsatisfiedLinkError: No implementation found for void
        com.huawei.vrhandle.VrPoseJni.helmetPoseStart()
      at com.huawei.vrhandle.service.VRHandleService.e3(VRHandleService.java:23)

Run from the repository root:  python tools/native-audit.py
"""
import os
import re
import zipfile

PACKAGES = (
    "com.huawei.appmarket.vr",
    "com.huawei.vrlauncherx",
    "com.huawei.himovie.vr",
    "com.huawei.vrvirtualscreen",
    "com.huawei.vrhandle",
    "com.huawei.hvrsdkserverapp",
)

NATIVE_METHOD = re.compile(
    r"\.method (?:public |protected |private )?native ([^\s(]+)\(([^)]*)\)(\S+)")
CLASS_NAME = re.compile(r"\.class .*?(L[^;\s]+;)")
SO_NAME = re.compile(r'const-string [vp0-9]+, "(lib[^"]+\.so)"')


def scan(decode_root, apk_path):
    with zipfile.ZipFile(apk_path) as archive:
        libs = sorted({name.split("/")[-1] for name in archive.namelist()
                       if name.startswith("lib/")})
    natives = {}
    loads = set()
    for directory, _, files in os.walk(decode_root):
        for name in files:
            if not name.endswith(".smali"):
                continue
            with open(os.path.join(directory, name), encoding="utf-8",
                      errors="ignore") as handle:
                text = handle.read()
            for match in NATIVE_METHOD.finditer(text):
                owner = CLASS_NAME.search(text)
                key = owner.group(1) if owner else name
                natives.setdefault(key, []).append(
                    "%s(%s)%s" % (match.group(1), match.group(2), match.group(3)))
            loads.update(SO_NAME.findall(text))
    return libs, natives, loads


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for package in PACKAGES:
        apk = os.path.join(root, "原包", package + ".apk")
        decode = os.path.join(root, "decode", package, "smali")
        if not os.path.isdir(decode):
            print("== %s: decode tree missing" % package)
            continue
        libs, natives, loads = scan(decode, apk)
        print("== %s" % package)
        print("   apk libs   : %s" % (", ".join(libs) if libs else "(none)"))
        print("   loads      : %s" % (", ".join(sorted(loads)) if loads else "(none)"))
        if not natives:
            print("   native     : (none)")
            continue
        for owner in sorted(natives):
            missing = sorted({method for method in natives[owner]})
            print("   native     : %s -> %s" % (owner, ", ".join(missing)))


if __name__ == "__main__":
    main()
