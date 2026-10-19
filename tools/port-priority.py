#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「要按官方实现移植」的类按实际调用点数量排序。

输入：docs/OFFICIAL_SOURCE_AUDIT.md 里判定为「改：按官方移植」的类 + decode 树。
输出：类名、调用点总数、涉及几个包、每个包几处。

    python tools/port-priority.py [数量]
"""
import collections
import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def classes_to_port():
    path = os.path.join(REPO, "docs", "OFFICIAL_SOURCE_AUDIT.md")
    wanted = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "| 改：按官方移植 |" not in line:
                continue
            match = re.match(r"\|\s*`([^`]+)`", line)
            if match:
                wanted.append(match.group(1))
    return wanted


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    wanted = classes_to_port()
    usage = collections.defaultdict(collections.Counter)
    patterns = {name: re.compile(r"\bL%s;->" % name.replace(".", "/"))
                for name in wanted}
    for path in glob.glob(os.path.join(REPO, "decode", "*", "smali*", "**", "*.smali"),
                          recursive=True):
        parts = path.split(os.sep)
        package = parts[parts.index("decode") + 1]
        with open(path, encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        for name, pattern in patterns.items():
            count = len(pattern.findall(text))
            if count:
                usage[name][package] += count

    rows = []
    for name in wanted:
        counter = usage.get(name)
        if not counter:
            continue
        rows.append((sum(counter.values()), len(counter), name, counter))
    rows.sort(reverse=True)
    print("要按官方移植的类：%d 个（有调用点的 %d 个）" % (len(wanted), len(rows)))
    for total, packages, name, counter in rows[:limit]:
        detail = ", ".join("%s×%d" % (pkg.replace("com.huawei.", ""), n)
                           for pkg, n in counter.most_common())
        print("%4d 处  %2d 个包  %-58s %s" % (total, packages, name, detail))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
