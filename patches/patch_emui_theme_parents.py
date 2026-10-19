"""把样式里指向 EMUI 资源包 `androidhwext` 的父级，改成通用安卓同源主题。

日志里反复出现的

    E/…: Failed to find parent 0x020600cd of bag 0x7f100123.

不是重打包丢了资源：`0x02` 是 **EMUI 的扩展框架资源包**，真机固件里就是
`/system/framework/framework-res-hwext.apk`，包名 `androidhwext`，条目如下
（用 aapt2 dump 过，见 docs/evidence/emui-theme-parent-2026-09-16.md）：

    0x02060008 androidhwext:style/Theme.Emui                 parent @android:style/Theme.Holo
    0x020600cd androidhwext:style/Theme.Emui.Dark            parent androidhwext:Theme.Emui
    0x02060189 androidhwext:style/Theme.Emui.Dark.Emphasize  parent androidhwext:Theme.Emui.Dark

原包（`原包/*.apk`，未改动）里这些样式**本来就是这么写的**，通用安卓手机上没装
`androidhwext`，父级就解析不了，样式退化成「只有自己那几条 item」。

本补丁只改「指向」：把父级换成原厂主题底下的那层 AOSP 主题（`Theme.Holo` 系列），
样式名、条目、使用它的 Activity 一律不动。深浅色与原厂一致；统一带 `NoActionBar`，
因为这些样式在原包里都不带 AOSP 动作栏，避免凭空多出一条系统动作栏。

解码树里 apktool 把父级写成占位名 `@com.huawei.fakeframework:style/…`
（`tools/framework/2.apk` 就是那张 name->id 的存根表），对应关系：

    huawei_base          = androidhwext:style/Theme.Emui                 (0x02060008)
    huawei_default       = androidhwext:style/Theme.Emui.Dark            (0x020600cd)
    huawei_action_button = androidhwext:style/Theme.Emui.Dark.Emphasize  (0x02060189)
"""

import re
import sys
from pathlib import Path

# 占位名 -> 通用安卓等价主题
REPLACE = {
    "huawei_base": "@android:style/Theme.Holo.Light.NoActionBar",
    "huawei_default": "@android:style/Theme.Holo.NoActionBar",
    "huawei_action_button": "@android:style/Theme.Holo.NoActionBar",
}

# 模块 -> {相对路径: {占位名: 该文件里的处数}}
TARGETS = {
    "com.huawei.vrlauncherx": {
        "res/values/styles.xml": {
            "huawei_base": 1,           # AppBaseTheme
            "huawei_default": 1,        # Theme_NoTitle（MainActivity + 6 个提示页）
            "huawei_action_button": 2,  # ThemeBlack / Theme_Dark_NoTitle
        },
    },
    "com.huawei.vrhandle": {
        "res/values/styles.xml": {
            "huawei_base": 2,           # SplashTheme / SubBgTheme
        },
        "res/values-v29/styles.xml": {
            "huawei_default": 1,        # SplashTheme(v29)
            "huawei_action_button": 1,  # ThemeBlack(v29)
        },
    },
    "com.huawei.vrvirtualscreen": {
        "res/values/styles.xml": {
            "huawei_base": 1,           # AppHwTheme
            "huawei_action_button": 1,  # ThemeBlack
        },
    },
}

PATTERN = re.compile(
    r'parent="@com\.huawei\.fakeframework:style/([A-Za-z0-9_]+)"')


def read(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def main(root):
    for module, files in TARGETS.items():
        for relative, expected in files.items():
            path = Path(root) / "decode" / module / relative
            text = read(path)
            eol = "\r\n" if "\r\n" in text else "\n"
            body = text.replace("\r\n", "\n")
            found = {}

            def replace(match, module=module, relative=relative, found=found):
                name = match.group(1)
                if name not in REPLACE:
                    raise SystemExit("%s/%s: 没见过的占位父级 %s，先补对照表"
                                     % (module, relative, name))
                found[name] = found.get(name, 0) + 1
                return 'parent="%s"' % REPLACE[name]

            updated = PATTERN.sub(replace, body)
            if found:
                if found != expected:
                    raise SystemExit("%s/%s: 站点数与预期不符，实际 %s，预期 %s"
                                     % (module, relative, found, expected))
                if eol != "\n":
                    updated = updated.replace("\n", eol)
                write(path, updated)
                print("%-46s %s" % (module + "/" + relative,
                                    ", ".join("%s x%d" % kv for kv in sorted(found.items()))))
                continue

            # 没有占位父级了：要么已经打过，要么文件认错了。
            applied = sum(body.count('parent="%s"' % repl) for repl in REPLACE.values())
            if applied >= sum(expected.values()):
                print("%-46s 已应用，跳过" % (module + "/" + relative))
                continue
            raise SystemExit("%s/%s: 既没有占位父级，也找不到替代后的父级"
                             % (module, relative))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
