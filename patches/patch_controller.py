"""Port the handle app's known-good compatibility fixes (from the old tree).

The handle's own Bluetooth state query is rejected on common Android, so its UI
concludes Bluetooth is off and keeps asking the user to enable it (the user
reported exactly that with Bluetooth already on).

Evidence: decode/com.huawei.vrhandle/smali/r0/y0.smali has

    .method public static W(I)I
        ...
        const-string v3, "com.huawei.android.permission.VR"
        invoke-virtual {v0, v3, p0}, Landroid/content/pm/PackageManager;->checkPermission(...)

`com.huawei.android.permission.VR` is a Huawei platform permission that does not
exist on a common Android device, so every caller - including the app itself -
is rejected. The fix does NOT touch the app's code: the very same permission
name is *implemented* by the compatibility layer, i.e. declared (and requested)
in the manifest with protectionLevel signature. All six packages are signed with
the same key, so they hold it and the original check passes unchanged.

The same patch disables the analytics base whose constructor reads
BuildEx.VERSION and crashes during pairing; the pairing UI itself is untouched.
"""
import re
import sys
from pathlib import Path

MODULE = "com.huawei.vrhandle"
# The Huawei platform permission the original code already asks for. The port
# supplies the implementation of this name instead of renaming it.
PLATFORM_PERMISSION = "com.huawei.android.permission.VR"
BINDER_FILE = "smali/r0/y0.smali"
BINDER_METHOD = r"(^\.method public static W\(I\)I\n.*?^\.end method)"
ANALYTICS_FILE = "smali/k0/d.smali"


def read(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def edit(path, function):
    """Run function on an LF copy, then write it back with the file's endings."""
    text = read(path)
    eol = "\r\n" if "\r\n" in text else "\n"
    updated = function(text.replace("\r\n", "\n"))
    if eol != "\n":
        updated = updated.replace("\n", eol)
    write(path, updated)


def replace_method_body(text, signature, body):
    pattern = re.compile(r"(^\.method[^\n]* " + re.escape(signature) +
                         r"\n).*?^\.end method", re.M | re.S)
    updated, count = pattern.subn(lambda m: m.group(1) + body + "\n.end method",
                                  text, count=1)
    if count != 1:
        raise SystemExit("method not found: %s" % signature)
    return updated


def main(root):
    decode = Path(root) / "decode" / MODULE

    # 1) the Bluetooth state check stays exactly as the original wrote it; its
    #    permission is provided by the compat layer further down.
    binder = decode / BINDER_FILE
    def fix_binder(text):
        method = re.search(BINDER_METHOD, text, re.M | re.S)
        if method is None:
            raise SystemExit("Binder check method missing")
        if method.group(1).count('"com.huawei.android.permission.VR"') != 1:
            raise SystemExit("Binder check permission changed")
        return text
    edit(binder, fix_binder)
    print("%-28s 蓝牙状态检查保持原样（权限由兼容层实现）" % binder.name)

    # 2) the analytics base crashes on BuildEx.VERSION; keep the pairing flow
    analytics = decode / ANALYTICS_FILE
    if analytics.is_file():
        def fix_analytics(text):
            text = replace_method_body(
                text, "<init>(II)V",
                "    .locals 0\n\n"
                "    invoke-direct {p0}, Ljava/lang/Object;-><init>()V\n\n"
                "    iput p1, p0, Lk0/d;->b:I\n\n"
                "    iput p2, p0, Lk0/d;->a:I\n\n"
                "    return-void")
            text = replace_method_body(text, "d(Ljava/lang/String;Ljava/lang/Object;)V",
                                       "    .locals 0\n\n    return-void")
            return replace_method_body(text, "h(Landroid/content/Context;)V",
                                       "    .locals 0\n\n    return-void")
        edit(analytics, fix_analytics)
        print("%-28s 分析与 BuildEx.VERSION 依赖关闭" % analytics.name)

    # 3) manifest: declare and request the compat permission
    manifest = decode / "AndroidManifest.xml"
    def fix_manifest(text):
        if 'android:name="%s" android:protectionLevel' % PLATFORM_PERMISSION in text:
            return text
        anchor = re.search(r"<manifest[^>]*>\n", text)
        if anchor is None:
            raise SystemExit("manifest header not found")
        insertion = (
            '    <permission android:name="%s" android:protectionLevel="signature"/>\n'
            % PLATFORM_PERMISSION)
        if 'android:name="%s"' % PLATFORM_PERMISSION not in text:
            insertion += ('    <uses-permission android:name="%s"/>\n'
                          % PLATFORM_PERMISSION)
        return text[:anchor.end()] + insertion + text[anchor.end():]
    edit(manifest, fix_manifest)
    print("%-28s 声明并申请 %s" % (manifest.name, PLATFORM_PERMISSION))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
