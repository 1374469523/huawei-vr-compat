"""把麒麟 VRAR HAL 的 vsync 调用换成通用安卓的等价实现。

真机日志（com.huawei.vrlauncherx 进程里跑的是 SDK 的类）：

    E/wei.vrlauncherx: hiddenapi: Accessing hidden method
        Landroid/os/ServiceManager;->waitForService(Ljava/lang/String;)Landroid/os/IBinder;
        using reflection: denied

来源：`com.huawei.vrframework.VrFramework$VrDisplay$HisiVsyncThread` 通过反射去取
麒麟专有的 `hisi.vrar` 服务（`IHivrarService`），再在渲染线程里调
`vrGetVsyncTimeStamp(int)D` 取硬件 vsync 计数。高通平台上没有这个 HAL，
`ServiceManager.getService("hisi.vrar")` 返回 null，接着的 `waitForService` 又被
hidden API 直接拒绝 —— 线程只能拿到 0。

按「高通平台上要可用」的口径：把**唯一那个 vsync 取值调用**换成兼容层实现
`VrVsyncCompat.timestamp(int)`（真实显示刷新率 + System.nanoTime() 推算下一个
vsync 边界，与 Choreographer 同基准）。只改 `getVsyncTimeStamp(int)D` 里的
两行取值指令，外层的 try/catch 与返回值语义原样保留；
`hisi.vrar` 的其它能力（vrInit/vrMode/...）在 null 时本就有各自的判空分支。
"""
import sys
from pathlib import Path

MODULE = "com.huawei.hvrsdkserverapp"
TARGET = "smali/com/huawei/vrframework/VrFramework$VrDisplay$HisiVsyncThread.smali"
ANCHOR = ('    sget-object v4, Lcom/huawei/vrframework/VrFramework$VrDisplay$HisiVsyncThread;->'
          'mHivrarService:Landroid/hardware/hivrar/IHivrarService;\n'
          '\n'
          '    invoke-interface {v4, p0}, Landroid/hardware/hivrar/IHivrarService;->'
          'vrGetVsyncTimeStamp(I)D')
REPLACEMENT = ('    # 通用安卓等价来源（见 patches/patch_hisi_vsync_to_android.py）：\n'
               '    # 真实显示刷新率 + System.nanoTime() 推算的 vsync 边界\n'
               '    invoke-static {p0}, Lcom/huawei/vrframework/compat/VrVsyncCompat;->timestamp(I)D')


def main(root):
    path = Path(root) / "decode" / MODULE / TARGET.replace("$", "$")
    text = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")

    if "VrVsyncCompat" in body:
        raise SystemExit("already patched")
    if body.count(ANCHOR) != 1:
        raise SystemExit("anchor count != 1: %d" % body.count(ANCHOR))

    body = body.replace(ANCHOR, REPLACEMENT, 1)
    if eol != "\n":
        body = body.replace("\n", eol)
    path.write_text(body, encoding="utf-8", newline="")
    print("patched: %s -> VrVsyncCompat.timestamp(int)" % TARGET)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
