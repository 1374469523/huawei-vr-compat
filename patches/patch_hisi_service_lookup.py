"""去掉麒麟 VRAR 服务的 hidden API 反射查找。

`HisiVsyncThread.getHivrarService()` 原版先用反射调
`android.os.ServiceManager.getService("hisi.vrar")`，拿不到再调
`ServiceManager.waitForService("hisi.vrar")`（hidden API，真机被拒：
`E/wei.vrlauncherx: hiddenapi: Accessing hidden method ... waitForService ... denied`）。
高通平台上没有 `hisi.vrar` 这个 HAL，两次查找注定失败。

vsync 取值已由 patches/patch_hisi_vsync_to_android.py 换成
`VrVsyncCompat.timestamp(int)`（公开 Android 等价来源），所以这里把整个查找方法
替换成「直接返回已缓存的服务引用」：行为等价（现在也是 null），但不再触碰 hidden API。
其它调用点（vrInit/vrMode/vrSetSchedFifo…）原本就有 null 判空分支，行为不变。
"""
import re
import sys
from pathlib import Path

MODULE = "com.huawei.hvrsdkserverapp"
TARGET = "smali/com/huawei/vrframework/VrFramework$VrDisplay$HisiVsyncThread.smali"
SIGNATURE = "getHivrarService()Landroid/hardware/hivrar/IHivrarService;"
ANCHOR = 'const-string v1, "android.os.ServiceManager"'


def main(root):
    path = Path(root) / "decode" / MODULE / TARGET
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")

    if ANCHOR not in body:
        raise SystemExit("anchor not found (already patched?): %s" % ANCHOR)

    pattern = re.compile(
        r"(^\.method private static " + re.escape(SIGNATURE) + r"\n).*?^\.end method",
        re.M | re.S)
    replacement = (
        r"\1"
        "    .locals 1\n"
        "\n"
        "    # 高通平台没有 hisi.vrar HAL；vsync 已由 VrVsyncCompat 提供，\n"
        "    # 这里只返回已缓存的引用，不再用 hidden API 反射查找\n"
        "    # （见 patches/patch_hisi_service_lookup.py）\n"
        "    sget-object v0, Lcom/huawei/vrframework/VrFramework$VrDisplay$HisiVsyncThread;->"
        "mHivrarService:Landroid/hardware/hivrar/IHivrarService;\n"
        "\n"
        "    return-object v0\n"
        ".end method")
    updated, count = pattern.subn(replacement, body, count=1)
    if count != 1:
        raise SystemExit("method not found: %s" % SIGNATURE)
    if ANCHOR in updated:
        raise SystemExit("ServiceManager reflection still present")

    if eol != "\n":
        updated = updated.replace("\n", eol)
    path.write_text(updated, encoding="utf-8", newline="")
    print("patched: %s -> returns cached service (no hidden API)" % SIGNATURE)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
