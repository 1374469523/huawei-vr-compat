"""把原版的 `Context.registerReceiver` 调用换到兼容层，补上 Android 14+ 要求的导出标志位。

背景（真机崩溃，SM-F731U1 / Android 16，2026-09-16）：

    Caused by: java.lang.SecurityException: com.huawei.himovie.vr:
      One of RECEIVER_EXPORTED or RECEIVER_NOT_EXPORTED should be specified
      when a receiver isn't being registered exclusively for system broadcasts
        at android.app.ContextImpl.registerReceiver
        at com.huawei.vrlab.VrPlayerApplication.onCreate

原版代码（targetSdk 30）用两参数/五参数的 `registerReceiver`，Android 14 起平台
强制要求显式导出属性，否则抛异常。视频包因此在 Application.onCreate 就崩，
桌面点「VR 视频」没有任何反应。

本脚本只改调用指向，不改任何参数与后续逻辑：

    invoke-virtual {v0, v1, v2}, Landroid/content/Context;->registerReceiver(
        Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;
        )Landroid/content/Intent;
  →
    invoke-static {v0, v1, v2}, Lcom/huawei/vrframework/compat/HvrReceiverCompat;
        ->registerReceiver(Landroid/content/Context;Landroid/content/BroadcastReceiver;
        Landroid/content/IntentFilter;)Landroid/content/Intent;

五参数（带权限 + Handler）同理。带 int flags 的调用**不动**——那种原版已经自己
给了标志位，替换反而会丢语义。

幂等：已经是兼容层调用的行跳过。脚本对每个模块统计改写条数并打印，便于对账。

用法：python patches/patch_receiver_exports.py [仓库根]
"""

import re
import sys
from pathlib import Path

OWNER = "Lcom/huawei/vrframework/compat/HvrReceiverCompat;"
CONTEXTS = ("Landroid/content/Context;", "Landroid/content/ContextWrapper;")

OWNER_PATTERN = r"(?:Landroid/content/Context;|Landroid/content/ContextWrapper;)"

TWO_ARG = re.compile(
    r"(?P<indent>\s*)invoke-virtual \{(?P<regs>[^}]*)\}, " + OWNER_PATTERN +
    r"->registerReceiver\(Landroid/content/BroadcastReceiver;"
    r"Landroid/content/IntentFilter;\)Landroid/content/Intent;")

FIVE_ARG = re.compile(
    r"(?P<indent>\s*)invoke-virtual \{(?P<regs>[^}]*)\}, " + OWNER_PATTERN +
    r"->registerReceiver\(Landroid/content/BroadcastReceiver;"
    r"Landroid/content/IntentFilter;Ljava/lang/String;"
    r"Landroid/os/Handler;\)Landroid/content/Intent;")

TWO_REPLACEMENT = (
    r"\g<indent>invoke-static {\g<regs>}, " + OWNER +
    "->registerReceiver(Landroid/content/Context;Landroid/content/BroadcastReceiver;"
    "Landroid/content/IntentFilter;)Landroid/content/Intent;")

FIVE_REPLACEMENT = (
    r"\g<indent>invoke-static {\g<regs>}, " + OWNER +
    "->registerReceiver(Landroid/content/Context;Landroid/content/BroadcastReceiver;"
    "Landroid/content/IntentFilter;Ljava/lang/String;"
    "Landroid/os/Handler;)Landroid/content/Intent;")


def patch(text):
    two = 0
    five = 0

    def replace_two(match):
        nonlocal two
        if match.group("regs").count(",") != 2:
            return match.group(0)
        two += 1
        return TWO_ARG.sub(TWO_REPLACEMENT, match.group(0))

    def replace_five(match):
        nonlocal five
        if match.group("regs").count(",") != 4:
            return match.group(0)
        five += 1
        return FIVE_ARG.sub(FIVE_REPLACEMENT, match.group(0))

    text = TWO_ARG.sub(replace_two, text)
    text = FIVE_ARG.sub(replace_five, text)
    return text, two, five


def main(root):
    decode = Path(root) / "decode"
    total_two = 0
    total_five = 0
    for module in sorted(p for p in decode.iterdir() if p.is_dir()):
        module_two = 0
        module_five = 0
        for smali in sorted(module.glob("smali*/**/*.smali")):
            raw = smali.read_text(encoding="utf-8", errors="ignore")
            if "->registerReceiver(" not in raw:
                continue
            patched, two, five = patch(raw)
            if not (two or five):
                continue
            smali.write_text(patched, encoding="utf-8", newline="")
            module_two += two
            module_five += five
        total_two += module_two
        total_five += module_five
        print("%-32s 两参数 %d / 五参数 %d"
              % (module.name, module_two, module_five))
    print("合计：两参数 %d 处、五参数 %d 处" % (total_two, total_five))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
