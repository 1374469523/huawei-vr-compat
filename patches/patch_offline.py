"""平台身份处理：去掉系统 UID，并摘掉通用安卓没有的华为平台库依赖。

用户口径（2026-09-16 定稿）：**完全 1:1，含在线**。所以这个脚本现在只做两件
与「在线/离线」无关的事，都是平台身份问题：

1. 去掉 `android:sharedUserId="android.uid.system"`。跑在系统用户下需要平台签名，
   移植版是普通应用；它保留的跨进程调用全部走显式组件 + 签名级权限。
2. 去掉 `nearbysdk` 的 `<uses-library>`。这是华为平台共享库，通用安卓没有；
   `required` 的 uses-library 缺失会让安装直接失败。同名类由兼容层提供。

**在线链一律不动**：INTERNET 等权限、华为账号/商城/更新/分析组件、在线入口
（主应用的「进入应用」、桌面云货架、vrservice 的云端配置任务）全部保持原包状态。
之前这个脚本按「离线版」口径摘过权限与组件，现在由
`patches/patch_online_restore.py` 负责把它们装回去，本脚本不再碰它们。

脚本对锚点做断言，解码树一变就会报错，不会静默产出一半状态的清单。
"""
import re
import sys
from pathlib import Path

# android:sharedUserId="android.uid.system" must be present exactly here.
SHARED_UID_MODULES = {
    "com.huawei.vrlauncherx",
    "com.huawei.vrvirtualscreen",
}

# 没有任何权限或组件会在这里被摘掉（用户口径：完全 1:1 含在线）。
ONLINE_PERMISSIONS = ()
ONLINE_COMPONENTS = ()

# Huawei ships these as platform shared libraries. A common Android device has
# none of them, and a required uses-library makes the install fail outright; the
# compat layer provides the classes itself, so the declaration is dropped.
REQUIRED_HUAWEI_LIBRARIES = ("nearbysdk",)
EXPECTED_REQUIRED_LIBRARIES = {
    "com.huawei.vrlauncherx": 1,
}


def patch_manifest(path, module):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    eol = "\r\n" if "\r\n" in text.split("\n", 1)[0] else "\n"
    lines = text.splitlines(keepends=True)

    out = []
    shared_removed = 0
    permission_removed = 0
    component_removed = 0
    library_removed = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.search(r'\sandroid:sharedUserId="[^"]*"', line):
            line = re.sub(r'\sandroid:sharedUserId="[^"]*"', "", line)
            shared_removed += 1
        match = re.search(r'<uses-permission[^>]*android:name="([^"]+)"', line)
        if match and match.group(1) in ONLINE_PERMISSIONS:
            permission_removed += 1
            index += 1
            continue
        opening = re.search(r'<([a-z-]+)\b', line)
        library = re.search(r'<uses-library[^>]*android:name="([^"]+)"', line)
        if library and library.group(1) in REQUIRED_HUAWEI_LIBRARIES:
            library_removed += 1
            index += 1
            continue
        if opening and opening.group(1) in (
                "activity", "activity-alias", "service", "receiver", "provider") and \
                any(re.search(pattern, line) for pattern in ONLINE_COMPONENTS):
            component_removed += 1
            tag = opening.group(1)
            if not line.rstrip().endswith("/>"):
                # A multi-line element: drop its children and the closing tag
                # with it, otherwise the manifest stops being well formed.
                index += 1
                closing = re.compile(r'^\s*</%s\s*>' % tag)
                while index < len(lines) and not closing.match(lines[index]):
                    index += 1
                # Skip the closing tag itself as well.
                index += 1
            else:
                index += 1
            continue
        out.append(line)
        index += 1

    expected_uid = 1 if module in SHARED_UID_MODULES else 0
    if shared_removed != expected_uid:
        raise SystemExit("%s: sharedUserId removed %d, expected %d"
                         % (module, shared_removed, expected_uid))
    expected_library = EXPECTED_REQUIRED_LIBRARIES.get(module, 0)
    if library_removed != expected_library:
        raise SystemExit("%s: required uses-library removed %d, expected %d"
                         % (module, library_removed, expected_library))
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("".join(out))
    return shared_removed, permission_removed, component_removed, library_removed


def main(root):
    decode = Path(root) / "decode"
    total = [0, 0, 0, 0]
    for directory in sorted(p for p in decode.iterdir() if p.is_dir()):
        manifest = directory / "AndroidManifest.xml"
        if not manifest.is_file():
            continue
        head = manifest.read_bytes()[:16]
        if not head.startswith(b"<?xml"):
            print("%-32s 二进制 manifest，跳过（该包无联网权限）" % directory.name)
            continue
        shared, permissions, components, libraries = patch_manifest(
            manifest, directory.name)
        total = [total[0] + shared, total[1] + permissions,
                 total[2] + components, total[3] + libraries]
        print("%-32s 去 UID %d，去在线权限 %d，去在线组件 %d，去必装库 %d"
              % (directory.name, shared, permissions, components, libraries))
    print("合计：UID %d，权限 %d，组件 %d，必装库 %d" % tuple(total))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
