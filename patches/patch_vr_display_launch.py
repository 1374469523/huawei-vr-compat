"""把桌面「启动 VR 页面」的统一入口补上虚拟屏路由。

桌面所有 VR 页面（准备页、Unity 空间、视频、投屏……）都走同一个函数：

    z0/c.B(Landroid/content/Context;Ljava/lang/Class;)V
        Intent i = new Intent(context, cls);
        i.addFlags(FLAG_ACTIVITY_NEW_TASK);
        ActivityOptions opts = ActivityOptions.makeCustomAnimation(context, 0, 0);
        context.startActivity(i, opts.toBundle());

EMUI 上这一步由框架的 VR 模式负责把 VR 应用放到「HUAWEI VR Display」那块虚拟屏上；
通用安卓没有这个机制，于是 VR 应用都落在手机默认屏上 —— 投屏模块因此直接判
「app start on default display error, finish!」（见 docs/PATCH_AUDIT.md 第 65 节）。

本补丁只加**两条指令**：拿到 ActivityOptions 之后调用一次兼容层的
`HvrDisplayRouter.applyVrDisplay`，由它按屏名找到虚拟屏并补 setLaunchDisplayId。
原来的构造、flag、异常分支一个字不动；虚拟屏不在位时 applyVrDisplay 原样返回，
行为与改之前完全一致。

用法：python patches/patch_vr_display_launch.py [仓库根]
"""

import sys
from pathlib import Path

MODULE = "com.huawei.vrlauncherx"
SMALI = "smali/z0/c.smali"

ANCHOR = (
    "    invoke-static {p0, p1, p1}, Landroid/app/ActivityOptions;"
    "->makeCustomAnimation(Landroid/content/Context;II)Landroid/app/ActivityOptions;\n"
    "\n"
    "    move-result-object p1\n"
)

INJECTED = (
    "    invoke-static {p0, p1, p1}, Landroid/app/ActivityOptions;"
    "->makeCustomAnimation(Landroid/content/Context;II)Landroid/app/ActivityOptions;\n"
    "\n"
    "    move-result-object p1\n"
    "\n"
    "    invoke-static {p1}, Lcom/huawei/vrframework/compat/HvrDisplayRouter;"
    "->applyVrDisplay(Landroid/app/ActivityOptions;)Landroid/app/ActivityOptions;\n"
    "\n"
    "    move-result-object p1\n"
)


def main(root):
    path = Path(root) / "decode" / MODULE / SMALI
    if not path.exists():
        raise SystemExit("missing %s" % path)
    raw = path.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    if "HvrDisplayRouter;->applyVrDisplay" in text:
        print("已经补过虚拟屏路由，跳过")
        return
    if text.count(ANCHOR) != 1:
        raise SystemExit("锚点匹配 %d 次，期望 1 次" % text.count(ANCHOR))
    patched = text.replace(ANCHOR, INJECTED)
    if eol != "\n":
        patched = patched.replace("\n", eol)
    path.write_text(patched, encoding="utf-8", newline="")
    print("已补上虚拟屏路由：%s" % SMALI)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
