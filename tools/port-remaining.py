#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出审计表里「改：按官方移植」但还没有逐类判定的类。

    python tools/port-remaining.py

判定标准改成直接读生成的审计表：每一行都必须写明「官方依赖什么 / 换了哪一步」；
还写着「待逐类判定」的就是没做完的。这样不会因为漏更新某份清单而误报。
（DONE 只用于显示进度：这些类已经按官方改写过。）
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DONE = {
    "com.huawei.android.os.SystemPropertiesEx",
    "com.huawei.android.util.HwNotchSizeUtil",
    "com.huawei.android.vrsystem.IVRSystemServiceManagerEx",
    "com.huawei.android.os.PowerManagerEx",
    "com.huawei.android.os.UserHandleEx",
    "com.huawei.android.media.AudioSystemEx",
    "com.huawei.android.media.AudioServiceEx",
    "com.huawei.android.hardware.input.InputManagerEx",
    "com.huawei.android.telephony.PhoneStateListenerEx",
    "com.huawei.android.telephony.PreciseCallStateEx",
    "com.huawei.android.app.ActivityManagerEx",
    "android.telephony.MSimTelephonyManager",
    "com.huawei.systemmanager.notificationmanager.restrictedlock.HwLockPatternUtilsEx",
    "com.huawei.systemmanager.notificationmanager.HwNotificationListenerEx",
    "com.huawei.android.iawareperf.UniPerfEx",
    "com.huawei.android.app.HiViewEx",
    "com.huawei.android.app.HiEventEx",
}

ROW = re.compile(r"^\|\s*`([^`]+)`.*\|\s*改：按官方移植\s*\|")


def main():
    path = os.path.join(REPO, "docs", "OFFICIAL_SOURCE_AUDIT.md")
    rows = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            match = ROW.match(line)
            if match:
                rows.append((match.group(1), "待逐类判定" in line))
    remaining = [name for name, undecided in rows if undecided]
    rewritten = [name for name, _ in rows if name in DONE]
    print("按官方移植 %d 个：已按官方改写 %d 个，其余已核对并写明替换点；还缺判定 %d 个"
          % (len(rows), len(rewritten), len(remaining)))
    for row in remaining:
        print("   待判定：", row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
