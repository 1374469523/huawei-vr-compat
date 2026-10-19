"""把 Cardboard 的 DisplayCutout 读取从 hidden API 反射换成公开 API。

真机日志（com.huawei.appmarket.vr，2026-09-16）：

    E/AndroidPCompat: Failed to fetch DisplayCutout from Display:
        java.lang.NoSuchMethodException: android.view.DisplayInfo.<init> []
    E/huawei.appmarket.vr: hiddenapi: Accessing hidden method
        Landroid/view/DisplayInfo;-><init>()V ...
    E/CutoutSpecification: According to SVG definition, it shouldn't happen

原版 `com.google.vr.cardboard.AndroidPCompat.getDisplayCutout(Display)` 为了拿
刘海信息，反射构造 `android.view.DisplayInfo`，而 `<init>` 在 Android 9+ 是
hidden API，被平台拦截 → 拿不到刘海 → 后续 cutout 计算告警。

Android 9(API 28) 起有公开 API `Display.getCutout()`，返回同一份数据
（`DisplayCutout`，`DisplayCutoutCompat` 已经能包装它）。本脚本只把该方法换成
公开调用，其余方法（`doesWindowExtendIntoCutoutArea` / `getDisplayRect`）不动。
"""
import re
import sys
from pathlib import Path

MODULE = "com.huawei.appmarket.vr"
TARGET = "smali/com/google/vr/cardboard/AndroidPCompat.smali"
SIGNATURE = "getDisplayCutout(Landroid/view/Display;)Lcom/google/vr/cardboard/AndroidPCompat$DisplayCutoutCompat;"
ANCHOR = "android.view.DisplayInfo"


def main(root):
    path = Path(root) / "decode" / MODULE / TARGET
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")

    if "getCutout()" in body:
        raise SystemExit("already patched")
    if ANCHOR not in body:
        raise SystemExit("anchor not found: %s" % ANCHOR)

    pattern = re.compile(
        r"(^\.method public " + re.escape(SIGNATURE) + r"\n).*?^\.end method",
        re.M | re.S)
    replacement = (
        r"\1"
        "    .locals 1\n"
        "\n"
        "    # Android 9+ 公开 API：Display.getCutout()\n"
        "    # （原版反射构造被 hidden API 拦截的显示信息类；\n"
        "    #   见 patches/patch_cardboard_cutout_api.py）\n"
        "    invoke-static {}, Lcom/google/vr/cardboard/AndroidPCompat;->isAtLeastP()Z\n"
        "\n"
        "    move-result v0\n"
        "\n"
        "    if-eqz v0, :cond_0\n"
        "\n"
        "    invoke-virtual {p1}, Landroid/view/Display;->getCutout()Landroid/view/DisplayCutout;\n"
        "\n"
        "    move-result-object p1\n"
        "\n"
        "    if-eqz p1, :cond_0\n"
        "\n"
        "    invoke-static {p1}, Lcom/google/vr/cardboard/AndroidPCompat$DisplayCutoutCompat;->create(Ljava/lang/Object;)Lcom/google/vr/cardboard/AndroidPCompat$DisplayCutoutCompat;\n"
        "\n"
        "    move-result-object p1\n"
        "\n"
        "    return-object p1\n"
        "\n"
        "    :cond_0\n"
        "    const/4 p1, 0x0\n"
        "\n"
        "    return-object p1\n"
        ".end method")
    updated, count = pattern.subn(replacement, body, count=1)
    if count != 1:
        raise SystemExit("method not found: %s" % SIGNATURE)
    # 只检查被替换的那个方法（同文件其它方法可能仍合法地用到 DisplayInfo）。
    replaced = pattern.search(updated)
    if replaced is None or "getCutout()" not in replaced.group(0):
        raise SystemExit("replacement did not take effect")
    if ANCHOR in replaced.group(0):
        raise SystemExit("DisplayInfo reflection still present in getDisplayCutout")

    if eol != "\n":
        updated = updated.replace("\n", eol)
    path.write_text(updated, encoding="utf-8", newline="")
    print("patched: %s -> %s uses Display.getCutout()" % (TARGET, SIGNATURE))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
