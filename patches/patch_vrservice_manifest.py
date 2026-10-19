"""Patch the binary AndroidManifest.xml of com.huawei.vrservice.

为什么是二进制 manifest：这个包的 resources.arsc 里有重复资源项
（``spec=0x7f09000a string/download_first_set_wifi_network``），apktool 解不动，
所以解码时用了 ``apktool d -r``，树里保留的是原始二进制 AndroidManifest.xml。
这与 ``com.huawei.hvrsdkserverapp`` 是同一情况，处理方式也一致：直接改二进制。

按用户已批准的「只换系统层 + 去联网」口径，本脚本只做四件事：

1. 去掉 ``android:sharedUserId="android.uid.system"``。
   原版跑在 system UID 下（EMUI 预装 + 平台签名），通用安卓不可能给；
   保留原包名、原组件、原流程，改为普通应用 + 同签名兼容层。
2. 去掉纯在线权限：INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE /
   REQUEST_INSTALL_PACKAGES。蓝牙、存储、FOREGROUND_SERVICE 等一律保留。
3. 摘掉纯在线的更新组件：``com.huawei.updatesdk.*`` 的两个 Activity。
   其余组件（VRPromptActivity / VrParamsInitializeService / VrParamsProviderService
   / UsbReceiver / SharedPreferenceProvider ...）全部原样保留。
4. 补 ``<queries>``：Android 11+ 下它要绑定 ``com.huawei.vrlauncherx/.VRService``，
   不声明同级包会被包可见性挡住。
5. 补声明 ``com.huawei.vrservice.CLIENT_SERVICE``。
   桌面的 ``com.huawei.client.vrservice.VRService`` 用这个权限保护
   （``android:permission="com.huawei.vrservice.CLIENT_SERVICE"``），
   而 EMUI 上它是**框架**定义的，通用安卓没人定义 —— 未定义的权限一律判定为拒绝，
   于是本包绑定桌面那个服务会被 SecurityException 挡掉，准备流程根本起不来。
   这个权限本来就属于本包的名字空间（本包已经声明了 ``.permission.VR`` 与
   ``.VRSystemApp`` 两个），把它一起声明为 signature 级即可：七个模块同一签名，
   互相授予，契约与名字都不变。

注意：本包的 manifest 字符串池里有重复字符串，``axml_edit`` 的
``index_of`` 只返回首次出现的下标，所以这里按「解析后的字符串」比较，
不用下标比较。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import axml_edit  # noqa: E402

PACKAGE = "com.huawei.vrservice"

DROP_PERMISSIONS = (
    # INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE 不再摘除：
    # 用户口径是「拦华为服务器请求」，不是断网（见 ADDED_PERMISSIONS 注释）。
    "android.permission.REQUEST_INSTALL_PACKAGES",
)

# 纯在线组件：华为更新 SDK。原版靠它在线检查升级，离线版必须摘掉。
DROP_COMPONENTS = (
    "com.huawei.updatesdk.service.otaupdate.AppUpdateActivity",
    "com.huawei.updatesdk.support.pm.PackageInstallerActivity",
)

# Android 11+ 包可见性：它要 bind 桌面的 VRService。
QUERIED_PACKAGES = (
    "com.huawei.vrlauncherx",
    "com.huawei.hvrsdkserverapp",
    "com.huawei.appmarket.vr",
)

# 曾经在这里补声明 com.huawei.vrservice.CLIENT_SERVICE，**那是错的**，已撤回：
# 反编译原始 manifest 后看到，这个权限本来就是
#   com.huawei.vrlauncherx 声明的
#   <permission android:name="com.huawei.vrservice.CLIENT_SERVICE"
#               android:protectionLevel="signatureOrSystem" .../>
# 名字挂着 vrservice 的命名空间，声明方却是桌面。本包（vrservice）原版只是
# **申请**它（uses-permission），不声明。我们**多声明一份**会造成同名权限双定义，
# 可能把原来的 signatureOrSystem 覆盖掉，属于改接口，所以撤回。
# 需要补的是"消费者要申请它"，那在 patch_platform_permissions.py 里做。
RETRACTED_DECLARATIONS = (
    "com.huawei.vrservice.CLIENT_SERVICE",
)

# 原版靠系统 UID（uid 0）白拿、普通应用必须自己申请的权限。
# VRService.increaseProcessPriority() 在 onCreate 里调用
#   startForeground(1, notification)
# targetSdk 28 起 startForeground 需要 android.permission.FOREGROUND_SERVICE，
# 缺了会在 onCreate 直接抛 SecurityException，服务起不来、vr_system 也就注册不上。
# 桌面（com.huawei.vrlauncherx）的 VRService 是同一个原因补的这条权限。
ADDED_PERMISSIONS = (
    # 用户口径纠正（2026-09-16）：**保留通用安卓联网能力，只拦发往华为服务器的请求**，
    # 不再整体断网。原包这三条本来就有，前几轮被当「纯在线权限」摘掉了，现在补回。
    "android.permission.INTERNET",
    "android.permission.ACCESS_NETWORK_STATE",
    "android.permission.ACCESS_WIFI_STATE",
    "android.permission.FOREGROUND_SERVICE",
    # Android 10+ 起后台启动 Activity 会被 BAL 规则拦住。真机日志（2026-09-16）：
    #   E/ActivityTaskManager: Background activity launch blocked!
    #     cmp=com.huawei.vrservice/.activity.VRPromptActivity
    #       callerProcState: FOREGROUND_SERVICE  -> BAL_BLOCK
    # 也就是「插入眼镜后的进入提示」这个原版界面根本起不来。
    # 公开的豁免途径是持有 SYSTEM_ALERT_WINDOW（桌面/手柄同一条路，见
    # install-six.ps1）。这条权限必须先写进 manifest，AppOps 才允许授予：
    # 未声明的 op 用 `appops set ... allow` 会静默失败（实测本包一直停在 default）。
    "android.permission.SYSTEM_ALERT_WINDOW",
    # AndroidAdapterManager 用 WindowManagerEx 在进 VR 时把动画关掉、退出时恢复，
    # 走的是 Settings.Global：读不需要权限，写需要 WRITE_SECURE_SETTINGS。
    # 桌面包当年是同一个原因声明 + `pm grant` 的（见 install-six.ps1）。
    "android.permission.WRITE_SECURE_SETTINGS",
    # 本包通过桌面托管的注册表读写 VR 状态（sys.glass.state /
    # hw.vr.environment.status，见 SystemPropertiesEx 与 VrPropertyStore），
    # 那个 provider 由这条签名级权限保护，所以要申请它。
    "com.huawei.vrservice.CLIENT_SERVICE",
)

# 兼容层的上下文 provider（见 HvrContextProvider 注释）：不导出，只让平台在
# 进程启动时把 application context 交给兼容层。
CONTEXT_PROVIDER = "com.huawei.vrframework.compat.HvrContextProvider"
CONTEXT_AUTHORITY = "com.huawei.vrservice.hvrcompat.ctx"

# 兼容层组件：把本包注册的 "vr_system" 跨进程暴露出去。
# EMUI 上这一步由平台服务注册表承担（ServiceManagerEx 只是它的壳），
# 通用安卓的应用不能往平台注册表里加名字，所以改由本包托管一个 registry
# provider；消费方用 ContentResolver.call() 同步取回 binder。
# 只加这一个组件，原版 16 个组件不动。
# 由本包托管的注册表 provider 已撤回给桌面（见 RETRACTED_PROVIDERS 附近说明）。
# 这里保留常量只用于「确认它已被删除」。
REGISTRY_PROVIDER = ".compat.VrSystemRegistryProvider"
REGISTRY_AUTHORITY = "com.huawei.vrservice.registry"
REGISTRY_PERMISSION = "com.huawei.vrservice.CLIENT_SERVICE"

# 布尔属性必须写成整数：aapt 把 android:exported="true" 编译成
# TYPE_INT_BOOLEAN(0x12)，data=1。手写 AXML 时若写成字符串，
# 平台解析出来的 exported 会判成假 —— 实测症状是消费方取 binder 时报
#   SecurityException: ... opening provider ... that is not exported from UID ...
# 即使调用方已经持有 provider 声明的 signature 权限也一样被拒。
# aapt 把布尔真写成 data=0xFFFFFFFF、假写成 0。**不能写 1**：实测平台会把
# data=1 的 TYPE_INT_BOOLEAN 当成假，于是 provider 虽然 manifest 里写着
# exported="true"，PackageManager 里的 info.exported 仍是 false，消费方取 binder 时
#   SecurityException: ... that is not exported from UID ...
# （这句话在 AOSP 里只有 !cpi.exported 时才会输出，见 ContentProviderHelper）
TYPE_INT_BOOLEAN = 0x12
BOOL_TRUE = 0xFFFFFFFF
BOOL_FALSE = 0
NO_RAW_VALUE = 0xFFFFFFFF


def bool_attribute(ns_index, name_index, value):
    return (ns_index, name_index, NO_RAW_VALUE, 8, 0, TYPE_INT_BOOLEAN,
            BOOL_TRUE if value else BOOL_FALSE)


def normalize_bool_attribute(document, element, name, value):
    """把布尔属性规范成整数编码；已经是整数就返回 False。"""
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


def name_of(document, element):
    return document.pool.strings[element.name_index]


def elements_named(document, name):
    """按解析后的元素名匹配，绕开字符串池重复项。"""
    found = []
    for position, (ctype, payload) in enumerate(document.entries):
        if ctype != axml_edit.RES_XML_START_ELEMENT_TYPE:
            continue
        if name_of(document, payload) == name:
            found.append((position, payload))
    return found


def attribute_of(document, element, name):
    """按解析后的属性名匹配。"""
    for _ns, aname, _raw, _size, _res0, data_type, data in element.attributes:
        if document.pool.strings[aname] != name:
            continue
        if data_type == axml_edit.TYPE_STRING:
            return document.pool.strings[data]
        return data
    return None


def drop_element(document, position):
    """删掉一个元素及其全部子元素，返回删除的 chunk 数。"""
    end = document.find_matching_end(position)
    removed = end - position + 1
    del document.entries[position:end + 1]
    return removed


def add_string_attribute(document, element, name, value):
    android_ns = document.pool.index_of("http://schemas.android.com/apk/res/android")
    element.attributes = list(element.attributes) + [
        axml_edit.StartElement.string_attribute(
            android_ns, document.pool.add(name), document.pool.add(value))]


def patch(path):
    document = axml_edit.BinaryXml(path.read_bytes())

    manifests = elements_named(document, "manifest")
    if len(manifests) != 1:
        raise SystemExit("expected exactly one <manifest> element")
    position, manifest = manifests[0]

    shared_uid = attribute_of(document, manifest, "sharedUserId")
    if shared_uid is None:
        print("sharedUserId: already removed")
    elif shared_uid != "android.uid.system":
        raise SystemExit("unexpected android:sharedUserId=%r" % (shared_uid,))
    else:
        document.drop_attribute(manifest, "sharedUserId")
        print("sharedUserId removed: android.uid.system")

    removed_permissions = []
    # 从后往前删，避免前面的删除移动后面元素的下标。
    for extra_pos, element in reversed(elements_named(document, "uses-permission")):
        name = attribute_of(document, element, "name")
        if name in DROP_PERMISSIONS:
            drop_element(document, extra_pos)
            removed_permissions.append(name)
    print("uses-permission removed: %s"
          % (", ".join(sorted(removed_permissions)) or "(none)"))

    added_permissions = []
    existing = {attribute_of(document, element, "name")
                for _, element in elements_named(document, "uses-permission")}
    for permission in ADDED_PERMISSIONS:
        if permission in existing:
            continue
        android_ns = document.pool.index_of(
            "http://schemas.android.com/apk/res/android")
        document.insert_child_after(position, axml_edit.StartElement(
            document.pool.add("uses-permission"),
            [axml_edit.StartElement.string_attribute(
                android_ns, document.pool.add("name"),
                document.pool.add(permission))]))
        added_permissions.append(permission)
    print("uses-permission added: %s"
          % (", ".join(sorted(added_permissions)) or "(none)"))

    removed_components = []
    for kind in ("activity", "service", "receiver", "provider"):
        for extra_pos, element in reversed(elements_named(document, kind)):
            name = attribute_of(document, element, "name")
            if name in DROP_COMPONENTS:
                drop_element(document, extra_pos)
                removed_components.append(name)
    print("online components removed: %s"
          % (", ".join(sorted(removed_components)) or "(none)"))

    applications = elements_named(document, "application")
    if len(applications) != 1:
        raise SystemExit("expected exactly one <application> element")
    application_position = applications[0][0]

    if not elements_named(document, "queries"):
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
    else:
        print("queries: already present")

    # 撤回早前多加的权限声明：原包本来就不声明它，见文件头说明。
    for declared_position, element in reversed(elements_named(document, "permission")):
        name = attribute_of(document, element, "name")
        if name not in RETRACTED_DECLARATIONS:
            continue
        end = document.find_matching_end(declared_position)
        del document.entries[declared_position:end + 1]
        print("permission declaration retracted: %s" % name)

    # 撤回本包里的注册表 provider：它现在由桌面包托管（见文件头说明与
    # patch_platform_permissions.py）。这里做删除，同时保证重复执行幂等。
    for provider_position, element in reversed(elements_named(document, "provider")):
        if attribute_of(document, element, "name") != REGISTRY_PROVIDER:
            continue
        end = document.find_matching_end(provider_position)
        del document.entries[provider_position:end + 1]
        print("registry provider retracted: %s" % REGISTRY_PROVIDER)

    # 兼容层的上下文 provider：本包也要有一个，兼容层里那些"原版不传 Context"
    # 的静态封装（SystemPropertiesEx / AudioManagerEx…）需要真实 Context。
    if not any(attribute_of(document, element, "name") == CONTEXT_PROVIDER
               for _, element in elements_named(document, "provider")):
        android_ns = document.pool.index_of(
            "http://schemas.android.com/apk/res/android")
        document.append_children(application_position, [axml_edit.ElementTree(
            document.pool.add("provider"),
            [(android_ns, document.pool.add("name"),
              document.pool.add(CONTEXT_PROVIDER)),
             (android_ns, document.pool.add("authorities"),
              document.pool.add(CONTEXT_AUTHORITY)),
             bool_attribute(android_ns, document.pool.add("exported"), False)])])
        print("context provider added: %s" % CONTEXT_PROVIDER)

    path.write_bytes(document.build())


def verify(path):
    document = axml_edit.BinaryXml(path.read_bytes())
    manifest = elements_named(document, "manifest")[0][1]
    if attribute_of(document, manifest, "sharedUserId") is not None:
        raise SystemExit("sharedUserId still present after patch")
    if attribute_of(document, manifest, "package") != PACKAGE:
        raise SystemExit("package name changed: %r"
                         % (attribute_of(document, manifest, "package"),))
    permissions = sorted(attribute_of(document, element, "name")
                         for _, element in elements_named(document, "uses-permission"))
    for forbidden in DROP_PERMISSIONS:
        if forbidden in permissions:
            raise SystemExit("forbidden permission still present: %s" % forbidden)
    for required in ADDED_PERMISSIONS:
        if required not in permissions:
            raise SystemExit("required permission missing: %s" % required)
    components = []
    for kind in ("activity", "service", "receiver", "provider"):
        components += sorted(attribute_of(document, element, "name") or ""
                             for _, element in elements_named(document, kind))
    for dropped in DROP_COMPONENTS:
        if dropped in components:
            raise SystemExit("online component still present: %s" % dropped)
    declared = sorted(attribute_of(document, element, "name") or ""
                      for _, element in elements_named(document, "permission"))
    for name in RETRACTED_DECLARATIONS:
        if name in declared:
            raise SystemExit("权限声明应当已撤回，但仍存在：%s" % name)
    providers = sorted(attribute_of(document, element, "name") or ""
                       for _, element in elements_named(document, "provider"))
    if REGISTRY_PROVIDER in providers:
        raise SystemExit(
            "注册表 provider 应当已移交给桌面，但本包 manifest 里仍存在：%s"
            % REGISTRY_PROVIDER)
    print("verify: package=%s" % PACKAGE)
    print("verify: %d uses-permission" % len(permissions))
    print("verify: declares %s" % ", ".join(declared))
    print("verify: %d components" % len(components))
    for name in components:
        print("  %s" % name)


def main():
    repo = Path(__file__).resolve().parent.parent
    path = repo / "decode" / PACKAGE / "AndroidManifest.xml"
    if not path.exists():
        raise SystemExit("missing %s" % path)
    patch(path)
    verify(path)


if __name__ == "__main__":
    main()
