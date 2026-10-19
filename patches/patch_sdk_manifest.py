"""Patch the binary AndroidManifest.xml of the Runtime package.

``com.huawei.hvrsdkserverapp`` cannot be decoded to text: apktool stops on a
duplicated resource (``spec=0x7f070009 string/Hvr_wifi``), so the tree keeps the
original binary manifest (``apktool d -r``). The two changes the port needs are
made directly on that binary file:

1. Drop ``android:sharedUserId="android.uid.system"``. Running inside the system
   UID needs a platform signature; the port keeps the original component set and
   the original cross-package contracts instead, which is what every other
   module already does.
2. Add the ``uses-permission`` entries the original relied on the system UID for.
   On EMUI the Runtime was uid 0 and therefore held these implicitly; a normal
   application has to request them. The declaring packages hand them out at
   ``signature`` level and all six modules share the port's signing key.
3. Add one boot receiver. On EMUI the framework watched the helmet and started
   the environment; on a generic device nothing does. The receiver is the entry
   point that starts that same supervision, and it is the only component added
   by the port (it delegates to the original ``ArvrRuntimeService``).

The script asserts what it expects to find so a re-decode cannot silently
produce a half-patched manifest.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import axml_edit  # noqa: E402

PACKAGE = "com.huawei.hvrsdkserverapp"

# 布尔属性的正确编码：aapt 写 data=0xFFFFFFFF 为真、0 为假。
# 写成字符串（"true"/"false"）或整数 1 都不可靠：实测平台按"假"处理，
# 于是 provider/receiver 的 exported 会被判成 false。
TYPE_INT_BOOLEAN = 0x12
BOOL_TRUE = 0xFFFFFFFF
BOOL_FALSE = 0
NO_RAW_VALUE = 0xFFFFFFFF


def bool_attribute(ns_index, name_index, value):
    return (ns_index, name_index, NO_RAW_VALUE, 8, 0, TYPE_INT_BOOLEAN,
            BOOL_TRUE if value else BOOL_FALSE)


def normalize_bool_attribute(document, element, name, value):
    """把布尔属性规范成 aapt 的整数编码；已经正确就返回 False。"""
    android_ns = document.pool.index_of(
        "http://schemas.android.com/apk/res/android")
    wanted = document.pool.add(name)
    expected = BOOL_TRUE if value else BOOL_FALSE
    kept = []
    changed = False
    for attribute in element.attributes:
        if document.pool.strings[attribute[1]] != name:
            kept.append(attribute)
            continue
        if attribute[5] == TYPE_INT_BOOLEAN and attribute[6] == expected:
            kept.append(attribute)
            continue
        kept.append(bool_attribute(android_ns, wanted, value))
        changed = True
    if changed:
        element.attributes = kept
    return changed

# Original contract: the Runtime binds the launcher's VR services. On EMUI the
# system UID satisfied the checks; here the same permissions are requested.
PATTERN_PERMISSIONS = (
    "com.huawei.vrservice.CLIENT_SERVICE",
    "com.huawei.android.permission.VR",
    "com.huawei.android.permission.VR.DEVICE_MESSAGE",
    # 系统侧 actor 在眼镜在位时把显示锁到横屏（EMUI 的 VR 模式同样这么做）。
    # 写 Settings.System 需要这条权限 + install-six.ps1 里的 appop。
    # 实测差异：不锁时 VR 窗口是 1588x1080 塞在 1080x2640 竖屏里，眼镜只收到
    # 按 0.6061 缩放的竖屏镜像；显示转横屏后同一路镜像缩放变成 1.2121
    # （2640 * 1.2121 = 3200），铺满面板宽度。
    "android.permission.WRITE_SETTINGS",
)

# 系统侧谁来看守眼镜：EMUI 上是框架开机常驻，通用安卓没有这个角色。
#
# 2026-09-16 用户口径：**不做开机自启**，改成「用户打开华为 VR 时把它拉起来」
# （见 HvrContextProvider 里的注释）。所以这里
#   * 把早前加的 BOOT_COMPLETED receiver 与 RECEIVE_BOOT_COMPLETED 权限摘掉
#     （原厂清单里本来就没有这两项，属于我们自己加的框架替身）；
#   * 监督服务改成「导出 + 本应用自己声明的签名级权限」——这是通用安卓里
#     跨应用启动组件的标准做法，权限就是原厂清单里已有的
#     `com.huawei.hvrsdkserverapp.permission.RUNTIME_ALLOW`（signatureOrSystem），
#     六个原包的清单里本来就在申请它。
LEGACY_BOOT_RECEIVER = ".compat.VrGlassBootReceiver"
LEGACY_BOOT_PERMISSION = "android.permission.RECEIVE_BOOT_COMPLETED"
WATCH_SERVICE = ".compat.VrGlassWatchService"
WATCH_PERMISSION = "com.huawei.hvrsdkserverapp.permission.RUNTIME_ALLOW"
# 在 EMUI 下系统会拉起，通用安卓需要应用自己声明。它的 onCreate 调
# startNative()，触发 libHVRSDKServerApp.so 加载与 VrHelmetExt.init()，
# 接着姿态链路才能起。详见 docs/PATCH_AUDIT.md 第 14 节。
MY_SERVICE = ".MyService"
MY_SERVICE_PERMISSION = "android.permission.FOREGROUND_SERVICE"

# 兼容层的上下文 provider（见 HvrContextProvider 注释）：不导出，只让平台在
# 进程启动时把 application context 交给兼容层。
CONTEXT_PROVIDER = "com.huawei.vrframework.compat.HvrContextProvider"
CONTEXT_AUTHORITY = "com.huawei.hvrsdkserverapp.hvrcompat.ctx"

# 声明了 android:process 的组件各自跑在独立进程里，每个进程都要有自己的
# provider 实例（authority 依次为 <CONTEXT_AUTHORITY>1、2…）。
CONTEXT_CHILD_PROCESSES = (
    "com.huawei.hvrsdkserverapp.service.ArvrRuntimeService",
    "com.huawei.hvrsdkserverapp.WlStrmActivity",
)


# The Runtime resolves sibling packages with createPackageContext/getPackageInfo;
# Android 11+ hides them unless they are declared (see patch_platform_permissions).
QUERIED_PACKAGES = (
    "com.huawei.appmarket.vr",
    "com.huawei.vrhandle",
    "com.huawei.vrlauncherx",
    "com.huawei.vrvirtualscreen",
    # Android 11+ 包可见性：本包要 call 它的 registry provider 才能拿到 vr_system。
    "com.huawei.vrservice",
)


def patch(path):
    document = axml_edit.BinaryXml(path.read_bytes())
    manifest = document.find_start_elements("manifest")
    if len(manifest) != 1:
        raise SystemExit("expected exactly one <manifest> element")
    position, element = manifest[0]

    shared_uid = document.attribute(element, "sharedUserId")
    if shared_uid is None:
        print("sharedUserId: already removed")
    elif shared_uid != "android.uid.system":
        raise SystemExit(
            "expected android:sharedUserId=\"android.uid.system\", found %r"
            % (shared_uid,))
    else:
        removed = document.drop_attribute(element, "sharedUserId")
        print("sharedUserId removed: %d" % removed)

    added = []
    for permission in PATTERN_PERMISSIONS:
        if any(document.attribute(child, "name") == permission
               for _, child in document.find_start_elements("uses-permission")):
            continue
        document.insert_child_after(
            position, axml_edit.StartElement(
                document.pool.add("uses-permission"),
                [axml_edit.StartElement.string_attribute(
                    document.pool.index_of(
                        "http://schemas.android.com/apk/res/android"),
                    document.pool.add("name"),
                    document.pool.add(permission))]))
        added.append(permission)
    print("uses-permission added: %s" % (", ".join(added) if added else "(none)"))

    # Components belong to <application>, not to <manifest>; PackageParser
    # silently ignores unknown children of <manifest>.
    application = document.find_start_elements("application")
    if len(application) != 1:
        raise SystemExit("expected exactly one <application> element")
    application_position = application[0][0]

    # 摘掉早前加的「开机自启」入口（用户 2026-09-16 口径：不需要）。
    # 从后往前删，前面的下标才不会失效。
    for position, element in reversed(document.find_start_elements("receiver")):
        if document.attribute(element, "name") == LEGACY_BOOT_RECEIVER:
            document.drop_element(position)
            print("receiver removed: %s" % LEGACY_BOOT_RECEIVER)
    for position, element in reversed(document.find_start_elements("uses-permission")):
        if document.attribute(element, "name") == LEGACY_BOOT_PERMISSION:
            document.drop_element(position)
            print("uses-permission removed: %s" % LEGACY_BOOT_PERMISSION)

    if not document.find_start_elements("queries"):
        android_ns = document.pool.index_of(
            "http://schemas.android.com/apk/res/android")
        queries = axml_edit.ElementTree(document.pool.add("queries"))
        for package in QUERIED_PACKAGES:
            queries.append(axml_edit.ElementTree(
                document.pool.add("package"),
                [(android_ns, document.pool.add("name"),
                  document.pool.add(package))]))
        document.insert_before(application_position, [queries])
        print("queries added: %s" % ", ".join(QUERIED_PACKAGES))

    # android.R.attr.permission：新写的属性名要在资源映射里有条目，
    # 否则平台不认这个属性（同 authorities 那处的处理）。
    document.ensure_resource_id(0x01010006, "permission")
    if not any(document.attribute(child, "name") == WATCH_SERVICE
               for _, child in document.find_start_elements("service")):
        android_ns = document.pool.index_of(
            "http://schemas.android.com/apk/res/android")
        document.append_children(application_position, [axml_edit.ElementTree(
            document.pool.add("service"),
            [(android_ns, document.pool.add("name"),
              document.pool.add(WATCH_SERVICE)),
             bool_attribute(android_ns, document.pool.add("exported"), True),
             (android_ns, document.pool.add("permission"),
              document.pool.add(WATCH_PERMISSION))])])
        print("service added: %s (exported, %s)" % (WATCH_SERVICE, WATCH_PERMISSION))

    if not any(document.attribute(child, "name") == MY_SERVICE
               for _, child in document.find_start_elements("service")):
        android_ns = document.pool.index_of(
            "http://schemas.android.com/apk/res/android")
        document.append_children(application_position, [axml_edit.ElementTree(
            document.pool.add("service"),
            [(android_ns, document.pool.add("name"),
              document.pool.add(MY_SERVICE)),
             bool_attribute(android_ns, document.pool.add("exported"), False),
             (android_ns, document.pool.add("permission"),
              document.pool.add(MY_SERVICE_PERMISSION))])])
        print("service added: %s" % MY_SERVICE)

    # Ensure the resource map contains the authorities attribute ID (0x01010018).
    # Without this, the platform will not recognize the attribute and installation
    # will fail with "<provider> does not include authorities attribute".
    # This must be done even if the provider already exists.
    document.ensure_resource_id(0x01010018, "authorities")  # android.R.attr.authorities

    if not any(document.attribute(child, "name") == CONTEXT_PROVIDER
               for _, child in document.find_start_elements("provider")):
        android_ns = document.pool.index_of(
            "http://schemas.android.com/apk/res/android")
        document.append_children(application_position, [axml_edit.ElementTree(
            document.pool.add("provider"),
            [(android_ns, document.pool.add("name"),
              document.pool.add(CONTEXT_PROVIDER)),
             (android_ns, document.pool.add("authorities"),
              document.pool.add(CONTEXT_AUTHORITY)),
             bool_attribute(android_ns, document.pool.add("exported"), False)])])
        print("provider added: %s" % CONTEXT_PROVIDER)

    # 子进程各自也要一个上下文 provider：provider 只在它被声明的进程里实例化。
    # 本包的两个组件跑在独立进程（见 docs/PATCH_AUDIT.md 第 39 节），没有它
    # ContextEx 在那两个进程里拿不到 application context。
    document.ensure_resource_id(0x01010011, "process")  # android.R.attr.process
    for index, process in enumerate(CONTEXT_CHILD_PROCESSES, start=1):
        authority = "%s%d" % (CONTEXT_AUTHORITY, index)
        if any(document.attribute(child, "authorities") == authority
               for _, child in document.find_start_elements("provider")):
            continue
        android_ns = document.pool.index_of(
            "http://schemas.android.com/apk/res/android")
        document.append_children(application_position, [axml_edit.ElementTree(
            document.pool.add("provider"),
            [(android_ns, document.pool.add("name"),
              document.pool.add(CONTEXT_PROVIDER)),
             (android_ns, document.pool.add("authorities"),
              document.pool.add(authority)),
             bool_attribute(android_ns, document.pool.add("exported"), False),
             (android_ns, document.pool.add("process"),
              document.pool.add(process))])])
        print("child-process provider added: %s -> %s" % (authority, process))

    # 早前一轮这些组件是用字符串写 exported 的，这里统一规范成整数布尔。
    expected_exported = {
        WATCH_SERVICE: True,     # 主应用要显式启动它（跨应用启动的标准做法）
        MY_SERVICE: False,
    }
    for kind in ("receiver", "service"):
        for _, element in document.find_start_elements(kind):
            name = document.attribute(element, "name")
            if name not in expected_exported:
                continue
            if normalize_bool_attribute(document, element, "exported",
                                        expected_exported[name]):
                print("exported normalised: %s" % name)

    # 监督服务导出，但用本应用自己的签名级权限保护：只有同签名的华为 VR 包
    # 能启动它（原厂六个包的清单里本来就在申请这条权限）。
    android_ns = document.pool.index_of(
        "http://schemas.android.com/apk/res/android")
    for _, element in document.find_start_elements("service"):
        if document.attribute(element, "name") != WATCH_SERVICE:
            continue
        if document.attribute(element, "permission") == WATCH_PERMISSION:
            continue
        element.attributes.append(axml_edit.StartElement.string_attribute(
            android_ns, document.pool.add("permission"),
            document.pool.add(WATCH_PERMISSION)))
        print("watch service permission set: %s" % WATCH_PERMISSION)

    path.write_bytes(document.build())


def verify(path):
    document = axml_edit.BinaryXml(path.read_bytes())
    manifest = document.find_start_elements("manifest")[0][1]
    if document.attribute(manifest, "sharedUserId") is not None:
        raise SystemExit("sharedUserId still present after patch")
    names = sorted(document.attribute(child, "name")
                   for _, child in document.find_start_elements("uses-permission"))
    print("verify: sharedUserId absent; %d uses-permission entries" % len(names))
    for name in names:
        print("  %s" % name)
    receivers = sorted(document.attribute(child, "name")
                       for _, child in document.find_start_elements("receiver"))
    print("verify: receivers = %s" % (receivers,))
    services = sorted(document.attribute(child, "name")
                      for _, child in document.find_start_elements("service"))
    print("verify: services = %s" % (services,))


def main():
    repo = Path(__file__).resolve().parent.parent
    path = repo / "decode" / PACKAGE / "AndroidManifest.xml"
    if not path.exists():
        raise SystemExit("missing %s" % path)
    patch(path)
    verify(path)


if __name__ == "__main__":
    main()
