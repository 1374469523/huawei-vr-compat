"""严格 1:1：把之前「按离线口径摘掉」的在线链原样装回去。

用户口径（2026-09-16 定稿）：**完全 1:1，含在线** —— 华为账号、商城入口、
更新/分析组件、INTERNET 权限全部恢复原样；华为服务器已经停服这件事由原版
自己的失败分支处理，不由我们代答。

本脚本处理三处：

1. 代码级「摘在线入口」的补丁全部撤回。这些改动是上一轮为离线包做的，逐字
   还原到 `22297941`（apktool 全量反编译六个原包那次提交）的原文：

     - 主应用 `MainActivity.canEnterMarket()`：`startMarketFrame()` 被换成了
       跳欢迎页；这里还原成原版的市场入口；
     - 主应用 `MainActivity.mainLayout()`：被加写了
       `is_entryhome_button_clicked = true`；还原成原版；
     - 主应用 `WelcomeVRActivity.initView()`：原「进入应用」按钮被
       `setVisibility(8)` 隐藏；还原成原版（按钮可见、点击进商城）。

   这几个文件只被上述补丁改过，所以整文件还原不会覆盖别的移植改动；脚本会
   先比对内容，已经还原过的文件跳过，保证幂等。

   另一处同类改动（vrservice 的 `ThermalConfigUpdateTask.run()` 空实现）在
   `c1c8a1d6`（回退在线入口拦截）时已经还原，本脚本只需对它做一次核对，见
   `ALREADY_PRISTINE`。

2. 清单里被摘掉的在线组件，逐字搬回来（同样取自 `22297941` 的原始解码）：

     - `com.huawei.appmarket.vr`：`com.huawei.hwid.api.common.apkimpl.DummyActivity`
     - `com.huawei.himovie.vr`：同一个 DummyActivity + 12 个
       `com.huawei.phoneservice.feedback.*` 活动

3. 不动的两项（不是「在线链」，是平台身份）：

     - `android:sharedUserId="android.uid.system"` 仍不恢复（通用安卓拿不到平台签名）；
     - `nearbysdk` 的 `<uses-library>` 仍不恢复（由兼容层提供同名类）。

用法：python patches/patch_online_restore.py [仓库根]
"""

import re
import subprocess
import sys
from pathlib import Path

# apktool 全量反编译六个原包那次提交：原厂文件的唯一可信来源。
PRISTINE = "22297941"

FILE_RESTORES = (
    ("com.huawei.appmarket.vr",
     "smali/com/huawei/hwmarket/vr/MainActivity.smali"),
    ("com.huawei.appmarket.vr",
     "smali/com/huawei/hwmarket/vr/framework/activity/WelcomeVRActivity.smali"),
)

# 已在 c1c8a1d6 还原、这里只做存在性核对的站点（vrservice 不在 22297941 里，
# 它的原始解码来自 58c013c6；该提交与当前文件逐字相同）。
ALREADY_PRISTINE = (
    ("com.huawei.vrservice",
     "smali/com/huawei/vrinstaller/task/thermalconfig/ThermalConfigUpdateTask.smali",
     "updateThermalConfig"),
)

ONLINE_COMPONENTS = (
    r"com\.huawei\.hwid\.api\.common\.apkimpl\.DummyActivity",
    r"com\.huawei\.phoneservice\.feedback\.[A-Za-z0-9_.$]*",
)

COMPONENT_RESTORES = (
    "com.huawei.appmarket.vr",
    "com.huawei.himovie.vr",
)

NAME_ATTRIBUTE = re.compile(r'android:name="([^"]+)"')


def git_show(repo, relative):
    result = subprocess.run(
        ["git", "-C", str(repo), "show", "%s:%s" % (PRISTINE, relative)],
        capture_output=True)
    if result.returncode != 0:
        raise SystemExit("git show %s:%s 失败：%s"
                         % (PRISTINE, relative, result.stderr.decode("utf-8", "replace")))
    return result.stdout


def restore_files(repo):
    for package, relative in FILE_RESTORES:
        path = repo / "decode" / package / relative
        if not path.exists():
            raise SystemExit("missing %s" % path)
        original = git_show(repo, "decode/%s/%s" % (package, relative))
        current = path.read_bytes()
        if current == original:
            print("%-28s %s 已是原版" % (package, Path(relative).name))
            continue
        path.write_bytes(original)
        print("%-28s %s 已还原为原版" % (package, Path(relative).name))


def top_level_elements(text, tag):
    """Yield (name, source) for every <tag ...> element in a manifest."""
    pattern = re.compile(r"^\s*<%s\b[^>]*?/?>\s*$" % tag, re.M)
    index = 0
    while True:
        match = pattern.search(text, index)
        if not match:
            return
        start = match.start()
        end = match.end()
        chunk = text[start:end]
        if chunk.rstrip().endswith("/>"):
            yield start, end, chunk
            index = end
            continue
        closing = re.compile(r"^\s*</%s>\s*$" % tag, re.M).search(text, end)
        if not closing:
            raise SystemExit("<%s> at %d has no closing tag" % (tag, start))
        end = closing.end()
        yield start, end, text[start:end]
        index = end


def restore_components(repo):
    for package in COMPONENT_RESTORES:
        relative = "decode/%s/AndroidManifest.xml" % package
        path = repo / relative
        original = git_show(repo, relative).decode("utf-8")
        text = path.read_text(encoding="utf-8", newline="")
        eol = "\r\n" if "\r\n" in text else "\n"
        body = text.replace("\r\n", "\n")
        added = []
        for tag in ("activity", "service", "receiver", "provider"):
            for _, _, element in top_level_elements(original, tag):
                match = NAME_ATTRIBUTE.search(element)
                if not match:
                    continue
                name = match.group(1)
                if not any(re.fullmatch(pattern, name)
                           for pattern in ONLINE_COMPONENTS):
                    continue
                if 'android:name="%s"' % name in body:
                    continue
                anchor = body.rfind("</application>")
                if anchor < 0:
                    raise SystemExit("%s: </application> not found" % path)
                body = body[:anchor] + element.strip("\n") + "\n    " + body[anchor:]
                added.append(name)
        if added:
            if eol != "\n":
                body = body.replace("\n", eol)
            path.write_text(body, encoding="utf-8", newline="")
        print("%-28s 在线组件 +%d %s"
              % (package, len(added), ", ".join(added) if added else "(none)"))


def verify_already_pristine(repo):
    for package, relative, marker in ALREADY_PRISTINE:
        path = repo / "decode" / package / relative
        if not path.exists():
            raise SystemExit("missing %s" % path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if marker not in text:
            raise SystemExit(
                "%s 里找不到 %s：在线链没有还原干净" % (path, marker))
        print("%-28s %s 已含 %s（在线链完整）"
              % (package, Path(relative).name, marker))


def main(root):
    repo = Path(root)
    restore_files(repo)
    verify_already_pristine(repo)
    restore_components(repo)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
