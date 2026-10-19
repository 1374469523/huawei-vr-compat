"""摘掉桌面包里那个依赖华为 Nearby 的手柄重连服务。

背景（真机证据，2026-09-16）：

手柄掉线后，手柄模块自己的重连链是这样的（原版逻辑，未改动）：

    VRHandleService -> VrHandleReconnectController.C(context)
        -> bindService(com.huawei.vrlauncherx/com.huawei.vrhandle.VrHandleReconnectService)
    绑定失败 -> "bind fail, directly trigger reconnect" -> 直接 connectGatt 重连
    绑定成功 -> 等远端初始化（Messenger 握手）-> 现在永远等不到

而桌面那个服务只是华为 Nearby SDK 的壳：

    VrHandleReconnectService.e(messenger) -> Ls1/b;->d(context, messenger)
    Ls1/b 内部走 com.huawei.nearbysdk.NearbyAdapter

通用安卓上没有华为 Nearby 平台服务，`NearbyAdapter.createInstance` 必然失败，
所以绑定“成功”但握手永远完不成。手柄端于是停在：

    W/VrHandleReconnectController: service not init finish, cannot notify scan
    I/vrhandle_VrDeviceService: not retry connect
    I/vrhandle_VrSdkApi: device connect fail in vr environment

老仓（porting/analysis/CONTROLLER_RECONNECT.md）的做法与真机结论一致：这条路
在非华为设备上不可移植，摘掉它，让手柄走它自己的兜底（直接重连）。本脚本只删
这一个 <service> 声明，不动其它组件、不动代码。

注意：这是「移除依赖缺席平台（Huawei Nearby）的组件」，不是「整体删 service」。
脚本断言原始行存在且只出现一次，不匹配即报错停止。
"""
import sys
from pathlib import Path

MODULE = "com.huawei.vrlauncherx"
MANIFEST = "AndroidManifest.xml"
SERVICE_NAME = "com.huawei.vrhandle.VrHandleReconnectService"


def main(root):
    path = Path(root) / "decode" / MODULE / MANIFEST
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")

    if SERVICE_NAME not in body:
        raise SystemExit("VrHandleReconnectService not found in %s" % path)

    kept = []
    removed = 0
    for line in body.split("\n"):
        if "<service" in line and SERVICE_NAME in line:
            removed += 1
            print("remove: %s" % line.strip())
            continue
        kept.append(line)
    if removed != 1:
        raise SystemExit("expected exactly one <service> line, found %d" % removed)
    if SERVICE_NAME in "\n".join(kept):
        raise SystemExit("service still referenced after removal: %s" % SERVICE_NAME)

    updated = "\n".join(kept)
    if eol != "\n":
        updated = updated.replace("\n", eol)
    path.write_text(updated, encoding="utf-8", newline="")
    print("patched: %s (removed 1 service)" % path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
