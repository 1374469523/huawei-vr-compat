"""恢复投屏包里两个对话框 Activity 的主题（原为 EMUI 的 `Theme.Emui.Dialog.Alert`）。

原包 `com.huawei.vrvirtualscreen.apk` 里这两条 Activity 写的是

    android:theme="@androidhwext:style/Theme.Emui.Dialog.Alert"   (0x0206002b)

apktool 解不出这个外来包引用，把值直接写成了 `@null`；重建后进包的就是
`@null`——主题被丢掉，两个对话框会落到应用默认主题上（不再悬浮、没有对话框
窗口背景与按钮栏），这是**功能性的丢失**，不是观感问题。

按 `docs/PORTING_METHOD.md` 的口径只换「指向」：EMUI 的对话框主题继承链是

    Theme.Emui.Dialog.Alert -> Theme.Emui.Dialog -> Theme.Emui -> @android:style/Theme.Holo

（three 条都 dump 过，见 docs/evidence/emui-hwext-attrs-2026-09-16.md），
所以通用安卓一侧的等价物就是 AOSP 自己的对话框主题 `Theme.Holo.Dialog.Alert`
——同样继承 `Theme.Holo`、同样悬浮窗口 + alert 按钮栏。Activity、名字、其它
属性一个都不动。

用法：python patches/patch_hwext_dialog_themes.py [仓库根]
"""

import re
import sys
from pathlib import Path

REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]

TARGET = REPO / "decode/com.huawei.vrvirtualscreen/AndroidManifest.xml"

ACTIVITIES = [
    "com.huawei.vrvirtualscreen.vr6dof.nolo6dof.NoloDialogActivity",
    "com.huawei.vrvirtualscreen.vr6dof.hw6dof.Hw6dofDialogActivity",
]

NEW_THEME = "@android:style/Theme.Holo.Dialog.Alert"
OLD_THEME = '@null'


def main():
    text = TARGET.read_text(encoding="utf-8", newline="")
    original = text
    changed = 0
    for activity in ACTIVITIES:
        pattern = re.compile(
            r'(<activity\b[^>]*android:name="%s"[^>]*android:theme=")%s(")'
            % (re.escape(activity), re.escape(OLD_THEME)))
        if not pattern.search(text):
            already = re.compile(
                r'<activity\b[^>]*android:name="%s"[^>]*android:theme="%s"'
                % (re.escape(activity), re.escape(NEW_THEME)))
            if already.search(text):
                print(f"  {activity}: 已是 {NEW_THEME}，跳过")
                continue
            raise SystemExit(f"{activity}: 找不到 android:theme=\"{OLD_THEME}\"")
        text = pattern.sub(lambda m: m.group(1) + NEW_THEME + m.group(2), text)
        changed += 1
        print(f"  {activity}: {OLD_THEME} -> {NEW_THEME}")

    left = text.count('android:theme="@null"')
    if left:
        raise SystemExit(f"改完还剩 {left} 处 android:theme=\"@null\"，先确认是不是同一个问题")
    if changed and text != original:
        TARGET.write_text(text, encoding="utf-8", newline="")
        print(f"  已写回 {TARGET}")
    print(f"共改 {changed} 处")


if __name__ == "__main__":
    main()
