"""把原厂件里的官方类按字节码原样搬进各模块（不重写实现）。

口径（docs/PORTING_METHOD.md）：和系统不兼容的那一层，能用官方原件就
用官方原件。华为的框架类（hwframework.jar / hwPartVr.jar）本来就是
EMUI 挂在 boot classpath 上的，通用安卓上没有；这些类不该由我们手写，
应当把官方字节码原样搬进模块。

做法：
  1. 从解码树里收集该模块引用到的类型；
  2. 与「原厂件」的类定义取交集，并对这些类做引用闭包；
  3. 跳过模块自己已经有的类（原包索引，含 Runtime 的 assets/*.dex）；
  4. 其余按原厂反汇编结果复制到 decode/<包名>/smali/ 下，apktool 重建时
     会和原代码一起汇编进 classes.dex。

在线链路（okhttp3 / networkit-grs / vrinstaller / hianalytics / hms 等）不搬：
局域网离线版没有 INTERNET，这些类的调用方已按计划摘掉。

    python patches/patch_official_platform_classes.py [包名 ...]
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# (反汇编目录, 只允许搬的包前缀；None = 不限制)
POOLS = [
    (REPO / "build/official-pool/hwframework/classes", None),
    (REPO / "build/official-pool/hwPartVr/classes", None),
    # android.vrsystem.* 这一族在 EMUI 上是 boot classpath 提供的，原件就在
    # 提供方应用里（vrlauncherx 有 IVRSystemService/$Stub/$Stub$Proxy +
    # IVRListener 全族）。只取 android/ 下的类，避免把别的应用的类搬进来。
    (REPO / "build/official-smali/com.huawei.vrlauncherx/classes", ("Landroid/",)),
]
MODULES = [
    "com.huawei.appmarket.vr",
    "com.huawei.vrlauncherx",
    "com.huawei.himovie.vr",
    "com.huawei.vrvirtualscreen",
    "com.huawei.vrhandle",
    "com.huawei.hvrsdkserverapp",
    "com.huawei.vrservice",
]

# 2026-09-16 用户口径纠正：不做「完全离线」，只拦发往华为服务器的请求。
# 因此这里的判定改为「是不是通用库」：
#   * 通用网络/工具库 —— 按官方字节码搬（okhttp3、networkit 是 HTTP 与
#     DNS/连接状态库，原包本来就用它们，不搬会让原代码缺类）；
#   * 华为服务 SDK（账号/推送/更新/分析/设备协同）—— 仍然不搬：它们的存在
#     意义就是访问华为服务器，搬进来只会发起被拦的请求；这些调用方已按
#     「摘在线入口」处理（见 patches/patch_offline.py 与各模块的在线入口补丁）。
EXCLUDE = (
    "Lcom/huawei/vrinstaller/",
    "Lcom/huawei/hianalytics/",
    "Lcom/huawei/hms/",
    "Lcom/huawei/agconnect/",
    "Lcom/huawei/updatesdk/",
    "Lcom/huawei/hwid/",
    "Lcom/huawei/phoneservice/",
    "Lcom/huawei/deviceshare/",
)

# 只搬「官方实现能在通用安卓上直接跑」的类族。判定标准：官方实现只依赖
# 公开 AOSP API 或自身（纯库），搬过来语义不变。
#
# 其余原厂类虽然官方也有原件，但实现里依赖华为系统设施（服务注册表、麒麟
# 节点、EMUI 私有服务），原样搬到三星上会走错分支或直接抛异常，所以保留
# 兼容实现 —— 例外逐条记在 docs/OFFICIAL_SOURCE_AUDIT.md，写明替换点。
COPY_PREFIXES = (
    "Landroid/vrsystem/",                        # 应用直接调的 AIDL 全族
    "Lcom/huawei/gson/",                         # 官方 shadow 版 Gson（纯库）
    "Lcom/huawei/libcore/io/ExternalStorage",    # 文件封装（纯库）
)

TYPE_RE = re.compile(r"L[A-Za-z0-9_/$]{2,};")
IMPORT_RE = re.compile(r"^import\s+(?:static\s+)?([\w.]+)\s*;", re.M)
COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)

# 官方 smali 里的 hiddenapi 访问标记（whitelist/blacklist/greylist...）。
# 它们只在系统镜像里有意义：普通应用 dex 里既不需要、apktool 在 api<29
# 时还会拒绝汇编（报 "Hidden API restrictions are only supported on api 29
# and above"）。去掉标记不影响任何字节码语义，所以复制时统一剥掉。
HIDDENAPI_RE = re.compile(
    r"\b(?:whitelist|blacklist|greylist(?:-max-[opqr])?|core-platform-api|test-api)\b")


def strip_hiddenapi(text):
    return HIDDENAPI_RE.sub("", text)


def strip_comments(text):
    """注释里出现的类名不算引用（否则 javadoc 会拖进一大堆无关类）。"""
    return COMMENT_RE.sub(" ", text)


def pool_classes():
    """返回 {类描述符: smali 路径}。"""
    pool = {}
    for root, allow in POOLS:
        if not root.is_dir():
            raise SystemExit("缺少官方字节码池：%s（先跑 tools/official-index.ps1 与反汇编）" % root)
        for path in root.rglob("*.smali"):
            rel = path.relative_to(root).as_posix()[:-len(".smali")]
            desc = "L%s;" % rel
            if allow and not desc.startswith(allow):
                continue
            pool.setdefault(desc, path)
    return pool


def compat_references():
    """共享兼容层（会注入进模块）引用到的类型，也算模块的引用。

    Java 源码里没有 smali 的 `L...;` 描述符，所以要自己还原：
      import a.b.C;            -> La/b/C;
      用到 C.Inner（嵌套类）   -> La/b/C$Inner;
    """
    refs = set()
    for path in REPO.glob("shared/**/*.java"):
        text = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        fqcns = IMPORT_RE.findall(text)
        own = re.search(r"^package\s+([\w.]+);", text, re.M)
        for fqcn in fqcns:
            desc = "L%s;" % fqcn.replace(".", "/")
            refs.add(desc)
            simple = fqcn.rsplit(".", 1)[-1]
            for nested in set(re.findall(r"\b%s\.([A-Z]\w*)" % re.escape(simple), text)):
                refs.add("L%s$%s;" % (fqcn.replace(".", "/"), nested))
        # 同包类（例如 android.vrsystem 里的 IVRSystemService）没有 import，
        # 用「本包 + 大写开头的标识符」还原。
        if own:
            pkg = own.group(1).replace(".", "/")
            for token in set(re.findall(r"\b([A-Z]\w*)\b", text)):
                refs.add("L%s/%s;" % (pkg, token))
    return refs


def module_references(module):
    """模块解码树里出现过的所有类型引用。"""
    decode = REPO / "decode" / module
    refs = set()
    for path in decode.glob("smali*/**/*.smali"):
        refs.update(TYPE_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return refs


def module_own_classes(module):
    """模块自己（含 assets 里的 dex）已经定义的类。"""
    index = REPO / "build/official-index" / ("%s.txt" % module)
    if not index.exists():
        return set()
    return set(line.strip() for line in index.read_text(encoding="utf-8", errors="ignore").splitlines()
               if line.strip())


def excluded(desc):
    return desc.startswith(EXCLUDE)


def copyable(desc):
    return desc.startswith(COPY_PREFIXES)


def patch_module(module, pool):
    own = module_own_classes(module)
    wanted = set()
    refs = module_references(module) | compat_references()
    pending = [d for d in refs
               if d in pool and copyable(d) and not excluded(d) and d not in own]
    while pending:
        desc = pending.pop()
        if desc in wanted:
            continue
        wanted.add(desc)
        text = pool[desc].read_text(encoding="utf-8", errors="ignore")
        for ref in TYPE_RE.findall(text):
            if (ref in pool and ref not in wanted and ref not in own
                    and copyable(ref) and not excluded(ref)):
                pending.append(ref)

    decode = REPO / "decode" / module
    # 官方类不能塞进第一个 dex：主应用/视频本来就是多 dex，塞进去会撞
    # 64K 方法数上限（实测 appmarket 报 "Unsigned short value out of range"）。
    # apktool 会按 smali_classesN 目录名把每个目录汇编成一个独立 dex，
    # 所以这里固定占用「下一个空号」。
    used = []
    for child in decode.iterdir():
        if child.is_dir():
            match = re.fullmatch(r"smali(?:_classes(\d+))?", child.name)
            if match:
                used.append(int(match.group(1) or 1))
    target_dir = "smali_classes%d" % ((max(used) if used else 1) + 1)
    copied = 0
    updated = 0
    for desc in sorted(wanted):
        rel = desc[1:-1] + ".smali"
        target = decode / target_dir / rel
        content = strip_hiddenapi(pool[desc].read_text(encoding="utf-8", errors="ignore"))
        existed = target.exists()
        if existed and target.read_text(encoding="utf-8", errors="ignore") == content:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        if existed:
            updated += 1
        else:
            copied += 1
    return copied, updated, len(wanted)


def main():
    pool = pool_classes()
    targets = sys.argv[1:] or MODULES
    print("官方字节码池：%d 个类" % len(pool))
    for module in targets:
        copied, updated, wanted = patch_module(module, pool)
        print("%-32s 命中 %3d 个官方类，新增 %3d，改写 %3d"
              % (module, wanted, copied, updated))
    return 0


if __name__ == "__main__":
    sys.exit(main())
