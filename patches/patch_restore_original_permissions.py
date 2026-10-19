"""逐包把「原包声明过、当前清单缺失」的权限补回来。

口径（用户 2026-09-16）：

    原版跑在 system UID / EMUI 框架下，很多权限是隐式持有的；换成通用安卓的
    普通应用之后必须显式声明，否则原代码会因为权限被拒而走错分支（不是崩溃就是
    功能缺失）。所以：**以原包声明的权限为准，逐包补齐**，运行期权限再在
    install-six.ps1 里 pm grant / appops。

做法：
  1. 用 aapt2 dump permissions 读 原包/<包名>.apk 的权限集合；
  2. 读 decode/<包名>/AndroidManifest.xml（文本或二进制 AXML）；
  3. 缺哪条补哪条（文本直接插 <uses-permission>；vrservice 走 axml_edit）。

只补不删：华为专有权限的声明保留（没有声明方就是不被授予，不影响功能），
真正要拦的是发往华为服务器的请求，那是代码层的事（见 patch_offline.py）。
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from sdk_path import find_aapt2  # noqa: E402

AAPT2 = find_aapt2()
PERMISSION_RE = re.compile(r"name='([^']+)'")

PACKAGES = [
    "com.huawei.appmarket.vr",
    "com.huawei.vrlauncherx",
    "com.huawei.himovie.vr",
    "com.huawei.vrvirtualscreen",
    "com.huawei.vrhandle",
    "com.huawei.hvrsdkserverapp",
    "com.huawei.vrservice",
]


def original_permissions(package):
    apk = REPO / "原包" / (package + ".apk")
    if not apk.exists():
        raise SystemExit("missing original apk: %s" % apk)
    out = subprocess.run([str(AAPT2), "dump", "permissions", str(apk)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    permissions = []
    for line in out.stdout.splitlines():
        if not line.startswith("uses-permission"):
            continue
        match = PERMISSION_RE.search(line)
        if match and match.group(1) not in permissions:
            permissions.append(match.group(1))
    return permissions


def patch_text(path, permissions):
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")
    added = []
    for permission in permissions:
        if 'android:name="%s"' % permission in body:
            continue
        index = body.find("<application")
        if index < 0:
            raise SystemExit("%s: <application> not found" % path)
        body = body[:index] + '    <uses-permission android:name="%s"/>\n' % permission + body[index:]
        added.append(permission)
    if added:
        if eol != "\n":
            body = body.replace("\n", eol)
        path.write_text(body, encoding="utf-8", newline="")
    return added


def main():
    for package in PACKAGES:
        wanted = original_permissions(package)
        path = REPO / "decode" / package / "AndroidManifest.xml"
        if not path.exists():
            raise SystemExit("missing manifest: %s" % path)
        if path.read_bytes()[:2] == b"\x03\x00":
            print("%-28s 二进制清单：由 patch_vrservice_manifest.py 负责" % package)
            continue
        added = patch_text(path, wanted)
        print("%-28s +%d  %s" % (package, len(added),
                                 ", ".join(a.split(".")[-1] for a in added) or "(none)"))


if __name__ == "__main__":
    main()
