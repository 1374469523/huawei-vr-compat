"""把原版的 "HUAWEI VR Display" 常量换成「本机真实 VR 屏名」。

原版（官方 smali，未改动逻辑）用

    display.getName().equals("HUAWEI VR Display")

判断 VR 屏在不在。这个字符串是 EMUI 框架虚拟屏的名字；通用安卓上眼镜是普通
外接屏（历史上按 EDID 名找，现已改成按 USB 身份 + 外接屏状态判定），判断恒 false，桌面于是打印
`should not wake up when vr display is off.` 并跳过唤醒面板，眼镜黑屏。

本补丁只把那个 const-string 换成一次兼容层查询（同寄存器），后面的 equals
保持原样：查到真实眼镜屏就返回它的名字，查不到返回原常量。

同一个判断在第七个模块 `com.huawei.vrservice` 里也有三处：

- `VRService.checkVrDisplayState` / `onDisplayAdded`：拿不到真名就倒计时 latch
  不放开，准备页那条链断在这里；
- `VRUtils.getVrDisplayMetrics`：拿不到真名就返回 null，取不到 VR 屏分辨率。

`VRConstant.HW_VR_DISPLAY_NAME` 这个静态常量**不动**：六个反编译树里没有任何
一处 sget-object 读它（javac 早已把常量内联进调用点），改它反而要动 <clinit>。
"""

import re
import sys
from pathlib import Path

ORIGINAL = '"HUAWEI VR Display"'
HELPER = "Lcom/huawei/vrframework/compat/VrDisplayCompat;->vrDisplayName()Ljava/lang/String;"
HELPER_CALL = "invoke-static {}, %s" % HELPER
TARGETS = {
    "com.huawei.vrlauncherx": {
        "smali/z0/c.smali": 2,
        "smali/x2/a.smali": 1,
        "smali/u2/b.smali": 1,
    },
    "com.huawei.vrservice": {
        "smali/com/huawei/vrservice/VRService.smali": 2,
        "smali/com/huawei/vrservice/utils/VRUtils.smali": 1,
    },
}

PATTERN = re.compile(r'^(\s*)const-string (v\d+), "HUAWEI VR Display"\s*$', re.M)


def read(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def main(root):
    decode = Path(root) / "decode"
    for module, targets in TARGETS.items():
        for relative, expected in targets.items():
            path = decode / module / relative
            text = read(path)
            eol = "\r\n" if "\r\n" in text else "\n"
            body = text.replace("\r\n", "\n")

            def replace(match):
                indent, register = match.group(1), match.group(2)
                return ("%s%s\n\n%smove-result-object %s"
                        % (indent, HELPER_CALL, indent, register))

            updated, count = PATTERN.subn(replace, body)
            if count == 0 and body.count(HELPER_CALL) == expected:
                # 已经打过了：解码树是补丁的落地结果，重复执行必须幂等。
                print("%s:%-52s already patched (%d site)"
                      % (module, relative, expected))
                continue
            if count != expected:
                raise SystemExit("%s:%s: expected %d site(s), found %d"
                                 % (module, relative, expected, count))
            if eol != "\n":
                updated = updated.replace("\n", eol)
            write(path, updated)
            print("%s:%-52s %d site(s) -> VrDisplayCompat.vrDisplayName()"
                  % (module, relative, count))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
