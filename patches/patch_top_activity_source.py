"""把原版取「前台 activity」的数据来源换成公开 API。

`z0/c.g(Context)`（日志名 getForeActivity）用
`ActivityManager.getRunningTasks(1)` 读 topActivity。Android 5 起这个方法只返回
调用者自己的任务，看别人的任务要 `android.permission.REAL_GET_TASKS`（签名级，
通用安卓拿不到），真机上经常拿到空列表/空 topActivity，于是原版日志：

    I/VRService_Client_VRManager: top activity is null
    E/VRService_Client_VRManager: error, RunningTaskInfo wrong.

调用方（VRManager）关心的是本应用自己的栈顶，公开 API
`ActivityManager.getAppTasks()` 正好给出这个信息，且不需要任何权限。
本脚本把该方法整体换成一次兼容层查询，语义不变：取不到返回 null。
"""
import re
import sys
from pathlib import Path

MODULE = "com.huawei.vrlauncherx"
TARGET = "smali/z0/c.smali"
SIGNATURE = "g(Landroid/content/Context;)Landroid/content/ComponentName;"
ANCHOR = "getRunningTasks(I)Ljava/util/List;"
HELPER = ("Lcom/huawei/vrframework/compat/VrTopActivity;->"
          "current(Landroid/content/Context;)Landroid/content/ComponentName;")


def main(root):
    path = Path(root) / "decode" / MODULE / TARGET
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")

    if ANCHOR not in body:
        raise SystemExit("anchor not found (already patched?): %s" % ANCHOR)

    pattern = re.compile(
        r"(^\.method public static " + re.escape(SIGNATURE) + r"\n).*?^\.end method",
        re.M | re.S)
    replacement = (
        r"\1"
        "    .locals 1\n"
        "\n"
        "    # 通用安卓：getRunningTasks 只返回调用者自己的任务且常为空；\n"
        "    # 换成公开的 getAppTasks()，见 patches/patch_top_activity_source.py\n"
        "    invoke-static {p0}, " + HELPER + "\n"
        "\n"
        "    move-result-object v0\n"
        "\n"
        "    return-object v0\n"
        ".end method")
    updated, count = pattern.subn(replacement, body, count=1)
    if count != 1:
        raise SystemExit("method not found: %s" % SIGNATURE)
    if ANCHOR in updated:
        raise SystemExit("getRunningTasks still present after patch")

    if eol != "\n":
        updated = updated.replace("\n", eol)
    path.write_text(updated, encoding="utf-8", newline="")
    print("patched: %s -> %s uses VrTopActivity.current()" % (TARGET, SIGNATURE))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
