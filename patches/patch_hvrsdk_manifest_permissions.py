"""给 hvrsdkserverapp 的二进制清单补「通用安卓必须显式声明」的权限。

真机现象（2026-09-16）：`appops set com.huawei.hvrsdkserverapp SYSTEM_ALERT_WINDOW allow`
一直是 `default`，授不进去 —— 因为该权限没有写进它的清单。这个包的清单是
apktool `-r` 解出来的二进制 AXML，所以按 vrservice 那套（axml_edit）处理。

口径：原版靠 EMUI/系统 UID 隐式持有，通用安卓必须显式声明 + appops 授予。
先补这两条：

  * SYSTEM_ALERT_WINDOW —— Android 10+ 后台启动 Activity 的公开豁免途径
    （Runtime 监督服务在眼镜插入后要拉 Activity，缺它会 BAL_BLOCK）；
  * FOREGROUND_SERVICE —— 它的常驻服务 startForeground 需要。

只补不删，幂等。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import axml_edit  # noqa: E402
import patch_vrservice_manifest as helpers  # noqa: E402

MODULE = "com.huawei.hvrsdkserverapp"
ADDED_PERMISSIONS = (
    "android.permission.SYSTEM_ALERT_WINDOW",
    "android.permission.FOREGROUND_SERVICE",
)


def main(root):
    path = Path(root) / "decode" / MODULE / "AndroidManifest.xml"
    document = axml_edit.BinaryXml(path.read_bytes())

    manifests = helpers.elements_named(document, "manifest")
    if len(manifests) != 1:
        raise SystemExit("expected exactly one <manifest> element")
    position = manifests[0][0]

    existing = {helpers.attribute_of(document, element, "name")
                for _, element in helpers.elements_named(document, "uses-permission")}
    added = []
    for permission in ADDED_PERMISSIONS:
        if permission in existing:
            continue
        android_ns = document.pool.index_of("http://schemas.android.com/apk/res/android")
        document.insert_child_after(position, axml_edit.StartElement(
            document.pool.add("uses-permission"),
            [axml_edit.StartElement.string_attribute(
                android_ns, document.pool.add("name"), document.pool.add(permission))]))
        added.append(permission)

    if added:
        path.write_bytes(document.build())
    print("%s: +%s" % (MODULE, ", ".join(added) or "(none)"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
