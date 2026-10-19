"""原版调试开关：com.huawei.android.vr.sensor.mode = mobile

华为 VR Engine 官方指南（09-Unity-AndroidManifest配置）写明：

    如果开发者需要不连接头盔看到手机上的显示，需要在 application 下包含
    <meta-data android:name="com.huawei.android.vr.sensor.mode" android:value="mobile"/>
    但是，正式发布的应用程序中必须去掉该标签，此功能仅用于调试。

这是**原版自带**的调试开关，不是本移植新造的入口。谁在读它：

  * 原生库：libvrsdk.so / libvrunityplugin.so 按名字读这条 meta-data；
  * Java 侧：com.huawei.vrframework.VrMonitor#isConfigMobileMode() 读到 "mobile"
    会打日志 "in mobile mode, exit monitor"，让 VR 监视器不启动。

原版还留了第二条等价路径：系统属性 hvr.imm.mobile == "enable"
（被 libHVRSDKServerApp.so / libvrunityplugin.so 读取），不需要改 manifest：
    adb shell su -c 'setprop hvr.imm.mobile enable'

**作用范围**：本脚本只操作传给它的那一个 AndroidManifest.xml。
调试开关由构建期开关触发（build-module.ps1 -DebugMobileMode），
作用在 stage 出来的构建副本上，decode 树永远不带它 —— 这样「正式发布必须去掉」
是构建流程本身保证的，而不是靠人记得改回来。

用法：
    python patches/patch_debug_mobile_mode.py verify  <AndroidManifest.xml> [...]
    python patches/patch_debug_mobile_mode.py enable  <AndroidManifest.xml>
    python patches/patch_debug_mobile_mode.py disable <AndroidManifest.xml>

支持文本 manifest（apktool 全量解码）与二进制 manifest（apktool -r）。
二进制 manifest 一旦重建就不是逐字节可逆的了，所以请只在构建副本上 enable。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import axml_edit  # noqa: E402

NAME = "com.huawei.android.vr.sensor.mode"
VALUE = "mobile"


def is_binary(path):
    return path.read_bytes()[:1] != b"<"


# ----------------------------------------------------------------- 二进制 manifest
def elements_named(document, name):
    out = []
    for position, (ctype, payload) in enumerate(document.entries):
        if ctype != axml_edit.RES_XML_START_ELEMENT_TYPE:
            continue
        if document.pool.strings[payload.name_index] == name:
            out.append((position, payload))
    return out


def attribute_of(document, element, name):
    for _ns, aname, _raw, _size, _res0, data_type, data in element.attributes:
        if document.pool.strings[aname] != name:
            continue
        return document.pool.strings[data] if data_type == axml_edit.TYPE_STRING else data
    return None


def binary_has(path):
    document = axml_edit.BinaryXml(path.read_bytes())
    for _, element in elements_named(document, "meta-data"):
        if attribute_of(document, element, "name") == NAME:
            return True
    return False


def binary_enable(path):
    document = axml_edit.BinaryXml(path.read_bytes())
    for _, element in elements_named(document, "meta-data"):
        if attribute_of(document, element, "name") == NAME:
            return False
    applications = elements_named(document, "application")
    if len(applications) != 1:
        raise SystemExit("expected exactly one <application> element")
    android_ns = document.pool.index_of("http://schemas.android.com/apk/res/android")
    document.append_children(applications[0][0], [axml_edit.ElementTree(
        document.pool.add("meta-data"),
        [(android_ns, document.pool.add("name"), document.pool.add(NAME)),
         (android_ns, document.pool.add("value"), document.pool.add(VALUE))])])
    path.write_bytes(document.build())
    return True


def binary_disable(path):
    document = axml_edit.BinaryXml(path.read_bytes())
    removed = 0
    for position, element in reversed(elements_named(document, "meta-data")):
        if attribute_of(document, element, "name") != NAME:
            continue
        end = document.find_matching_end(position)
        del document.entries[position:end + 1]
        removed += 1
    if removed:
        path.write_bytes(document.build())
    return removed > 0


# ----------------------------------------------------------------- 文本 manifest
def text_has(path):
    return NAME in path.read_text(encoding="utf-8")


def text_enable(path):
    text = path.read_text(encoding="utf-8")
    if NAME in text:
        return False
    import re
    # 必须插在 <application ...> 开标签之后：写在 <application> 外面
    # （<manifest> 的子节点）会被 PackageParser 忽略，开关就不生效。
    anchor = re.search(r"\n(\s*)<application[^>]*>", text)
    if anchor is None:
        raise SystemExit("<application> not found")
    indent = anchor.group(1)
    block = ('\n%s    <meta-data android:name="%s" android:value="%s"/>'
             % (indent, NAME, VALUE))
    at = anchor.end()
    path.write_text(text[:at] + block + text[at:], encoding="utf-8")
    return True


def text_disable(path):
    import re
    text = path.read_text(encoding="utf-8")
    # 只删整行的那条 meta-data，避免破坏别的标签
    pattern = re.compile(r'\n[ \t]*<meta-data[^>]*android:name\s*=\s*"%s"[^>]*/>'
                         % re.escape(NAME))
    new = pattern.sub("", text)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def has_switch(path):
    return binary_has(path) if is_binary(path) else text_has(path)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    action = argv[1]
    paths = [Path(p) for p in argv[2:]]
    for path in paths:
        if not path.exists():
            raise SystemExit("缺少 %s" % path)
    if action == "verify":
        bad = [str(p) for p in paths if has_switch(p)]
        for path in paths:
            print("  %-60s %s" % (path, "带调试开关" if has_switch(path) else "无"))
        if bad:
            raise SystemExit("这些 manifest 带上了调试开关，正式构建必须去掉：%s"
                             % ", ".join(bad))
        return 0
    if len(paths) != 1:
        raise SystemExit("enable/disable 一次只处理一个 manifest")
    path = paths[0]
    binary = is_binary(path)
    if action == "enable":
        changed = binary_enable(path) if binary else text_enable(path)
        print("调试开关：%s" % ("已加上" if changed else "本来就有"))
    elif action == "disable":
        changed = binary_disable(path) if binary else text_disable(path)
        print("调试开关：%s" % ("已去掉" if changed else "本来就没有"))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))