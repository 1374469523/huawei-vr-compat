"""在 VR 活动里补上 SDK 的 init(Activity) 触发点。

见 shared/java/com/huawei/vrframework/compat/VrFrameworkBootstrap.java 的注释：
EMUI 上由系统/框架在 VR 应用起来时调用 `VrFramework.init(activity)` /
`VrHelmetExt.init(activity)`；通用安卓上没人调，于是

    VrFramework.isHW6DoFHeaderAvailable()  -> "App activity is null" -> false
    VrHelmetExt.isEnable()                 -> "mVRDeviceExt is null"

造成 `CallStaticBooleanMethodV == false`（7 万次）与 `mVRDeviceExt is null`（8 千次）。

本脚本在 `com/huawei/vrlab/HVRActivity;->onCreate` 末尾（`LibUpdateClient.runUpdate()`
之后，SDK 的代码已经装载）插入一次兼容层调用，把真实 Activity 交给 SDK。
只插入一处，原方法其余部分不动；脚本断言原始片段存在且唯一。
"""
import sys
from pathlib import Path

MODULE = "com.huawei.vrlauncherx"
TARGET = "smali/com/huawei/vrlab/HVRActivity.smali"
ANCHOR = "invoke-virtual {p1}, Lcom/huawei/hvr/LibUpdateClient;->runUpdate()Z"
INJECT = ("    invoke-static {p0}, Lcom/huawei/vrframework/compat/"
          "VrFrameworkBootstrap;->init(Landroid/app/Activity;)V")


def main(root):
    path = Path(root) / "decode" / MODULE / TARGET
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")

    if "VrFrameworkBootstrap" in body:
        raise SystemExit("already patched")
    if body.count(ANCHOR) != 1:
        raise SystemExit("anchor count != 1: %d" % body.count(ANCHOR))

    updated = body.replace(ANCHOR, ANCHOR + "\n\n" + INJECT, 1)
    if eol != "\n":
        updated = updated.replace("\n", eol)
    path.write_text(updated, encoding="utf-8", newline="")
    print("patched: %s (injected VrFrameworkBootstrap.init)" % TARGET)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
