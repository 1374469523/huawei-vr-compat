"""把 APK 清单里每个组件的主题打印成一行，用来和原包逐条对照。

用法：
    python tools/manifest-themes.py <apk或清单文件> [...]

输出：`组件路径<TAB>theme=值`，冒号分隔层级，例如
    application/activity:com.huawei.x.Y   theme=@0x7f0a000c

aapt2 解不出的外来引用（EMUI 的 `androidhwext` 主题）会写成 `@null`，
这一类就是「原包有主题、通用安卓上没了」的丢项，比对时一眼能看出来。
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sdk_path import find_aapt2  # noqa: E402

AAPT2 = find_aapt2()
TAG = re.compile(r"^(\s*)E: (\S+) \(line=\d+\)")
NAME = re.compile(r'A: http://schemas\.android\.com/apk/res/android:name\(0x01010003\)="([^"]*)"')
THEME = re.compile(r"theme\(0x01010000\)=(.*)$")
COMPONENTS = {"manifest", "application", "activity", "activity-alias", "service",
              "receiver", "provider"}


def dump(path):
    if path.suffix.lower() == ".apk":
        command = [str(AAPT2), "dump", "xmltree", "--file", "AndroidManifest.xml", str(path)]
    else:
        command = [str(AAPT2), "dump", "xmltree", str(path)]
    return subprocess.run(command, capture_output=True, text=True,
                          errors="replace").stdout.splitlines()


def walk(path):
    stack = []
    name = None
    theme = None
    for line in dump(path):
        found = TAG.match(line)
        if found:
            if name is not None or theme is not None:
                yield stack[:], name, theme
            depth = len(found.group(1))
            while stack and stack[-1][1] >= depth:
                stack.pop()
            stack.append((found.group(2), depth))
            name, theme = None, None
        elif NAME.search(line):
            name = NAME.search(line).group(1)
        elif THEME.search(line):
            theme = THEME.search(line).group(1).strip()
    if name is not None or theme is not None:
        yield stack[:], name, theme


def components(path):
    out = []
    for stack, name, theme in walk(path):
        if not stack or stack[-1][0] not in COMPONENTS:
            continue
        chain = ":".join(tag for tag, _ in stack)
        if stack[-1][0] == "manifest":
            continue
        out.append((f"{chain}:{name or '?'}", theme))
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    left = components(Path(sys.argv[1]))
    right = dict(components(Path(sys.argv[2])))
    right_order = [key for key, _ in components(Path(sys.argv[2]))]
    names = set(right_order)
    problems = 0
    for key, theme in left:
        if key not in names:
            print(f"缺组件\t{key}\t原主题={theme}")
            problems += 1
            continue
        got = right[key]
        if theme == got:
            continue
        print(f"主题不一致\t{key}\t原={theme}\t现={got}")
        problems += 1
    for key in right_order:
        if key not in {k for k, _ in left}:
            print(f"多出组件\t{key}\t现={right[key]}")
            problems += 1
    print(f"共 {len(left)} 个组件，差异 {problems} 处")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
