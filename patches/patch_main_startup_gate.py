"""把「欢迎页上的环境启动闸门」从 decode 树里撤掉（页面恢复原样）。

上一版（2026-09-16 第 62 节）在 `WelcomeVRActivity.initView()` 末尾插了一条
静态调用，由页面负责拉起 Runtime 与 vrservice，并把原「进入 VR」按钮挡住，
直到两个服务就绪 —— 状态行是运行时插进页面里的。

用户口径（2026-09-16 定稿）：

  * 不做开机自启；
  * 打开华为 VR 就自动启动环境（启动点在兼容层的进程入口
    `HvrContextProvider`，见 shared/java/com/huawei/vrframework/compat）；
  * 页面上那几行「正在启动 X」和按钮禁用**彻底去掉**，页面恢复原样。

所以本脚本现在的职责是**反向**的：断言插进去的那一条存在（不存在说明已经撤过），
然后删掉它，其余 smali 一个字不动。脚本保持幂等，重复运行不会报错。

用法：python patches/patch_main_startup_gate.py [仓库根]
"""

import sys
from pathlib import Path

MODULE = "com.huawei.appmarket.vr"
SMALI = "smali/com/huawei/hwmarket/vr/framework/activity/WelcomeVRActivity.smali"

INJECTED = (
    "\n"
    "    invoke-static {p0}, Lcom/huawei/vrframework/compat/VrStartupGate;"
    "->attach(Landroid/app/Activity;)V\n"
    "\n"
)


def main(root):
    path = Path(root) / "decode" / MODULE / SMALI
    if not path.exists():
        raise SystemExit("missing %s" % path)
    raw = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    if "VrStartupGate;->attach" not in text:
        print("欢迎页上没有启动闸门，无需撤回")
        return
    if text.count(INJECTED) != 1:
        raise SystemExit("锚点匹配 %d 次，期望 1 次" % text.count(INJECTED))
    patched = text.replace(INJECTED, "\n")
    if eol != "\n":
        patched = patched.replace("\n", eol)
    path.write_text(patched, encoding="utf-8", newline="")
    print("已撤回欢迎页启动闸门：%s" % SMALI)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
