"""把 vrservice 里「眼镜接近 / 电量」的取值换成 Android 自己的源。

真机日志（com.huawei.vrservice）：

    E/UpgradeGlass: [UpgradeGlass.cpp:...VRHelmetUtils_getProximityNative]: proximity value -1
    E/VRService_System_DeviceNodeMonitor: get glass proximity fail!
    E/UpgradeGlass: [UpgradeGlass.cpp:...VRHelmetUtils_getBatteryNative]: battery info 0, 0, 0
    E/UpgradeGlass: [UpgradeGlass.cpp:...readGlassNodeNative]: open node /dev/ttyUSB1 error

原版这两项由 native 读 EMUI 专有节点（`/dev/ttyUSB1`/眼镜 HID 特性报告）。取证结论
（docs/evidence/proximity-battery-2026-09-16.md）：CV10 眼镜的 HID 报告描述符里
没有接近(report 4)与电量(report 8)，native 只能回 -1 / 0。用户口径是「目标是通用
安卓，可以直接用 Android 的」，所以：

    getProximityNativeJNI()  -> VrAndroidSensors.proximity()      （Sensor.TYPE_PROXIMITY）
    getBatteryNativeJNI()    -> VrAndroidSensors.batteryPercent()  （BatteryManager）

只替换这两个 **Java 包装方法**（消费者调用的就是它们，私有 native 原样保留），
返回语义不变：取不到仍然返回 -1。
"""
import re
import sys
from pathlib import Path

MODULE = "com.huawei.vrservice"
TARGET = "smali/com/huawei/vrservice/utils/VRHelmetUtils.smali"

TARGETS = {
    "getProximityNativeJNI()I": ("getProximityNative", "proximity"),
    "getBatteryNativeJNI()I": ("getBatteryNative", "batteryPercent"),
}

HELPER = "Lcom/huawei/vrframework/compat/VrAndroidSensors;->%s()I"


def main(root):
    path = Path(root) / "decode" / MODULE / TARGET
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")

    if "VrAndroidSensors" in body:
        raise SystemExit("already patched")

    for signature, (native_name, helper_name) in TARGETS.items():
        anchor = "invoke-static {}, Lcom/huawei/vrservice/utils/VRHelmetUtils;->%s()I" % native_name
        if body.count(anchor) != 1:
            raise SystemExit("anchor count != 1 for %s: %d" % (native_name, body.count(anchor)))
        pattern = re.compile(
            r"(^\.method public static " + re.escape(signature) + r"\n).*?^\.end method",
            re.M | re.S)
        replacement = (
            r"\1"
            "    .locals 1\n"
            "\n"
            "    # 通用安卓数据源（见 patches/patch_helmet_proximity_battery_android.py）\n"
            "    invoke-static {}, " + (HELPER % helper_name) + "\n"
            "\n"
            "    move-result v0\n"
            "\n"
            "    return v0\n"
            ".end method")
        body, count = pattern.subn(replacement, body, count=1)
        if count != 1:
            raise SystemExit("method not found: %s" % signature)
        print("patched: %s -> VrAndroidSensors.%s()" % (signature, helper_name))

    if eol != "\n":
        body = body.replace("\n", eol)
    path.write_text(body, encoding="utf-8", newline="")
    print("done: %s" % path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
