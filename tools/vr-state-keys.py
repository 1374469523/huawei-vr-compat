#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出让七个包真正读写的 SystemPropertiesEx 键（模块 / 方法 / 键 / 次数）。

用途：EMUI 上这层是对 android.os.SystemProperties 的直接封装，而 VR 各模块之间
就是靠这些键互相通知状态的（例如 sys.glass.state）。通用安卓禁止普通应用写系统
属性，所以要先看清到底用了哪些键，再决定兼容层要接管哪些。

    python tools/vr-state-keys.py
"""
import collections
import glob
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALL = re.compile(r"invoke-static \{([^}]*)\}, "
                  r"Lcom/huawei/android/os/SystemPropertiesEx;->"
                  r"(get|set|getBoolean|getInt)\(")
CONST = re.compile(r'const-string[^,]*, "(.*)"')


def main():
    owners = collections.defaultdict(collections.Counter)
    pattern = os.path.join(REPO, "decode", "*", "smali*", "**", "*.smali")
    for path in glob.glob(pattern, recursive=True):
        package = path.split(os.sep)[-4] if path.split(os.sep)[-4] != "decode" else "?"
        parts = path.split(os.sep)
        try:
            package = parts[parts.index("decode") + 1]
        except (ValueError, IndexError):
            continue
        with open(path, encoding="utf-8", errors="ignore") as handle:
            lines = handle.read().splitlines()
        for index, line in enumerate(lines):
            hit = CALL.search(line)
            if not hit:
                continue
            key = None
            for back in range(index - 1, max(-1, index - 9), -1):
                found = CONST.search(lines[back])
                if found:
                    key = found.group(1)
                    break
            owners[package][(hit.group(2), key)] += 1

    for package in sorted(owners):
        print("== %s" % package)
        for (method, key), count in owners[package].most_common():
            print("   %-11s %-34s x%d" % (method, key, count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
