"""把原包的通用联网权限还回去（用户口径：只拦发往华为服务器的请求，不是断网）。

前几轮按「离线版」口径把六个包的 INTERNET 等权限摘掉了。用户明确纠正：
**不要把应用做成完全离线，只要拦住发往华为服务器的请求**——断网会让原版
在线代码走异常分支（真机上就出现过主应用 `HuaweiCloudModule` 因 DNS 被拒
抛 FATAL 打死进程、WiFi 名称取空导致 `Substring` 负长度等）。

本脚本按**原包实际拥有的权限**逐包补回（对照 `aapt2 dump permissions 原包/*.apk`）：

    com.huawei.appmarket.vr      INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE / CHANGE_WIFI_STATE
    com.huawei.himovie.vr        INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE
    com.huawei.vrhandle          INTERNET / ACCESS_NETWORK_STATE
    com.huawei.vrlauncherx       INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE
    com.huawei.vrservice         INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE

（hvrsdkserverapp / vrvirtualscreen 原包就没有这些权限，不动。）

文本 manifest 直接插入 <uses-permission>；vrservice 是二进制 manifest（apktool -r
解的），用 axml_edit 插入。脚本幂等：已有该权限就跳过。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import axml_edit  # noqa: E402

PACKAGES = {
    # vrservice 原包带 INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE
    # （它要向 cloudbackup 拉 VRApkListConfig 与固件升级文件）。之前只恢复了
    # 另外四个包，这一条是漏的，2026-09-16「严格 1:1」对账时补上。
    # 该包的清单是二进制 AXML，走 axml_edit。
    "com.huawei.vrservice": [
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.ACCESS_WIFI_STATE",
    ],
    "com.huawei.appmarket.vr": [
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.ACCESS_WIFI_STATE",
        "android.permission.CHANGE_WIFI_STATE",
    ],
    "com.huawei.himovie.vr": [
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.ACCESS_WIFI_STATE",
    ],
    "com.huawei.vrhandle": [
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
    ],
    "com.huawei.vrlauncherx": [
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.ACCESS_WIFI_STATE",
    ],
}


def patch_text(path, permissions):
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")
    added = []
    for permission in permissions:
        if 'android:name="%s"' % permission in body:
            continue
        anchor = "<application"
        index = body.find(anchor)
        if index < 0:
            raise SystemExit("%s: <application> not found" % path)
        insert = '    <uses-permission android:name="%s"/>\n' % permission
        body = body[:index] + insert + body[index:]
        added.append(permission)
    if added:
        if eol != "\n":
            body = body.replace("\n", eol)
        path.write_text(body, encoding="utf-8", newline="")
    return added


def patch_binary(path, permissions):
    raw = path.read_bytes()
    document = axml_edit.BinaryXml(raw)
    strings = document.pool.strings
    added = []
    android_ns = document.pool.index_of("http://schemas.android.com/apk/res/android")
    for permission in permissions:
        present = False
        for ctype, payload in document.entries:
            if ctype != axml_edit.RES_XML_START_ELEMENT_TYPE:
                continue
            if strings[payload.name_index] != "uses-permission":
                continue
            for attribute in payload.attributes:
                if strings[attribute[1]] == "name" and \
                        strings[attribute[6]] == permission:
                    present = True
                    break
            if present:
                break
        if present:
            continue
        position = document.find_first_child_of("manifest")
        document.insert_child_after(position, axml_edit.StartElement(
            document.pool.add("uses-permission"),
            [axml_edit.StartElement.string_attribute(
                android_ns, document.pool.add("name"),
                document.pool.add(permission))]))
        added.append(permission)
    if added:
        path.write_bytes(document.to_bytes())
    return added


def main(root):
    repo = Path(root)
    for package, permissions in PACKAGES.items():
        path = repo / "decode" / package / "AndroidManifest.xml"
        if not path.exists():
            raise SystemExit("missing %s" % path)
        head = path.read_bytes()[:4]
        if head[:2] == b"\x03\x00":
            added = patch_binary(path, permissions)
        else:
            added = patch_text(path, permissions)
        print("%-28s +%s" % (package, ", ".join(added) or "(none)"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
