#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验「七个包实际调用的兼容层方法」在**构建产物**里都有同描述符实现。

    python tools/compat-signature-check.py [某个已构建的 APK]

为什么需要它：ART 按「方法名 + 描述符」链接。参数个数相同但类型不同、返回类型
不同，我们的源码编译期都看不出来（不是对着原包编译的），运行期就是
NoSuchMethodError。参数顺序写反（同类型）它查不出来，但「缺方法 / 描述符不一致」
一查一个准。

做法：
  1. 用 tools/dexdump/DexDump 的 --methods 读某个构建产物里**定义**的方法表
     （只有兼容层那个 dex 定义这些类）；
  2. 从 decode 树的 smali 里收集所有对兼容层类的 invoke 调用点；
  3. 报告「被调用但没有同描述符实现」的条目。
"""
import glob
import os
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sdk_path import find_android_sdk  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# java.lang.Object / Throwable 上就有的方法：调用点写在我们的子类上，
# 但实现来自平台，dex 里当然找不到，属正常情况。
INHERITED = {
    "getMessage()Ljava/lang/String;",
    "getCause()Ljava/lang/Throwable;",
    "getLocalizedMessage()Ljava/lang/String;",
    "toString()Ljava/lang/String;",
    "hashCode()I",
    "equals(Ljava/lang/Object;)Z",
    "getClass()Ljava/lang/Class;",
    "asBinder()Landroid/os/IBinder;",
    "attachInterface(Landroid/os/IInterface;Ljava/lang/String;)V",
    "queryLocalInterface(Ljava/lang/String;)Landroid/os/IInterface;",
    "onTransact(ILandroid/os/Parcel;Landroid/os/Parcel;I)Z",
}


CALL = re.compile(
    r"invoke-(?:static|virtual|direct|interface|super)\s*\{[^}]*\},\s*"
    r"(?P<ref>L[\w/$]+;->[\w$<>]+\([^)]*\)[^\s]+)")

def java_tool():
    tools = os.path.join(REPO, "build", "dexdump")
    return os.path.join(REPO, "tools", "apktool_2.10.0.jar") + os.pathsep + tools


def compat_classes():
    """shared/java 里我们自己写的类（含嵌套类），返回 smali 描述符集合。"""
    names = set()
    for path in glob.glob(os.path.join(REPO, "shared", "java", "**", "*.java"),
                          recursive=True):
        with open(path, encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        package = re.search(r"^package\s+([\w.]+);", text, re.M)
        if not package:
            continue
        prefix = package.group(1).replace(".", "/")
        for name in re.findall(
                r"^\s*(?:public\s+)?(?:final\s+|abstract\s+|static\s+)*"
                r"(?:class|interface|enum)\s+(\w+)", text, re.M):
            names.add("L%s/%s;" % (prefix, name))
    return names


def defined_methods(apk):
    """APK 里**所有** dex 定义的方法描述符集合。

    兼容层 dex 与「按官方字节码复制进模块树」的 dex 都算在内 —— 对 ART 来说
    它们同属一个应用，引用能在其中任何一个 dex 里解析到就行。
    """
    sdk = find_android_sdk()
    jdk_root = sdk / "jdk17tmp"
    jdk_dirs = sorted(p for p in jdk_root.iterdir() if p.is_dir()) if jdk_root.is_dir() else []
    if not jdk_dirs:
        raise SystemExit("SDK 里没有 jdk17tmp：%s" % sdk)
    java = str(jdk_dirs[0] / "bin" / "java.exe")
    if not os.path.exists(java):
        raise SystemExit("找不到 javac/java（%s）" % java)
    defined = set()
    any_dex = False
    with zipfile.ZipFile(apk) as archive:
        for name in archive.namelist():
            if not name.endswith(".dex"):
                continue
            data = archive.read(name)
            temp = os.path.join(REPO, "build", "compat-dex", name.replace("/", "_"))
            os.makedirs(os.path.dirname(temp), exist_ok=True)
            with open(temp, "wb") as handle:
                handle.write(data)
            result = subprocess.run(
                [java, "-cp", java_tool(), "DexDump", "--methods", temp, "35"],
                capture_output=True, text=True)
            defined |= set(result.stdout.splitlines())
            any_dex = True
    if not any_dex:
        raise SystemExit("APK 里没有 dex：%s" % apk)
    return defined


def call_sites(module, compat):
    calls = {}
    pattern = os.path.join(REPO, "decode", module, "smali*", "**", "*.smali")
    for path in glob.glob(pattern, recursive=True):
        with open(path, encoding="utf-8", errors="ignore") as handle:
            for match in CALL.finditer(handle.read()):
                ref = match.group("ref")
                cls = ref[1:ref.index(";")]
                if ("L%s;" % cls) not in compat:
                    continue
                calls.setdefault(ref, set()).add(path)
    return calls


def main():
    compat = compat_classes()
    print("兼容层类 %d 个" % len(compat))
    failures = 0
    for apk in sorted(glob.glob(os.path.join(REPO, "build", "out", "*.apk"))):
        name = os.path.basename(apk)
        match = re.match(r"(.+)-r\d+\.apk$", name)
        if not match:
            continue
        module = match.group(1)
        if not os.path.isdir(os.path.join(REPO, "decode", module)):
            continue
        defined = defined_methods(apk)
        calls = call_sites(module, compat)
        missing = sorted(ref for ref in calls
                         if ref not in defined and ref.split(";->", 1)[1] not in INHERITED)
        status = "通过" if not missing else "缺 %d 个" % len(missing)
        print("%-34s 调用点 %3d  %s" % (name, len(calls), status))
        for ref in missing:
            failures += 1
            where = sorted(os.path.relpath(p, REPO) for p in calls[ref])[:2]
            print("   %s\n        被 %s 调用" % (ref, "、".join(where)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
