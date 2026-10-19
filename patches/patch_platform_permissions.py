"""Declare the platform permissions the original code uses but no longer holds.

⚠️ 顺序要求：本脚本按自己的列表重写 `<provider>` 段，会把
`patch_context_provider_processes.py` 加进去的子进程 provider 清掉。
**本脚本跑完必须再跑一次 `patches/patch_context_provider_processes.py`**，
否则桌面的 VRService 子进程又拿不到 Context，真机症状是每秒刷
`W HvrServiceManagerEx: no application context; vr_system stays process-local`，
主线握手会直接起不来（2026-09-16 实测过）。

On EMUI the desktop, video and cast packages ran with
android:sharedUserId="android.uid.system" (the system user), so they could write
Settings.System without declaring anything. The port runs them as ordinary
applications - the system UID cannot be granted to a normal app - so the very
same code now hits

    java.lang.SecurityException: <pkg> was not granted this permission:
        android.permission.WRITE_SETTINGS
        at android.provider.Settings$System.putInt(...)
        at q2.e.b(PrivacytHelper.java)              <- the app's own code
        at ...PrivacyStatementActivity.onClick(...)

and the process is killed (reproduced on the desktop right after the privacy
page's 同意 button).

The 1:1 fix is to give the app the capability, not to change the app: declare
WRITE_SETTINGS in the manifest (it is a special permission, granted through
Settings/appops, exactly as any Android app needs it), and grant it with

    adb shell appops set <pkg> WRITE_SETTINGS allow

which install-six.ps1 does for the packages listed here.
"""
import re
import sys
from pathlib import Path

# package -> permissions its original code needs on a common Android device
NEEDED = {
    # WRITE_SETTINGS: the app writes Settings.System (desktop: PRIVACY_ACCEPTED
    # through q2/e PrivacytHelper, and its brightness helpers).
    #
    # WRITE_SECURE_SETTINGS was tried and deliberately reverted: the platform
    # refuses PRIVACY_ACCEPTED in the System namespace for ordinary callers with
    # "You cannot keep your settings in the secure settings.", and granting the
    # permission (or running with elevated rights) does not change that verdict.
    # The consent flags are therefore seeded through the shell, which the
    # platform does accept - see install-six.ps1.
    # FOREGROUND_SERVICE: VRService.onCreate calls startForeground() for the
    # environment notification. With the system UID that came for free; as a
    # normal app the declaration is required, otherwise the service cannot even
    # be created:
    #   SecurityException: Permission Denial: startForeground from pid=...,
    #   uid=... requires android.permission.FOREGROUND_SERVICE
    #   at com.huawei.client.vrservice.VRService.a(VRService.java:6)
    #   at com.huawei.client.vrservice.VRService.onCreate(VRService.java:3)
    # WRITE_SECURE_SETTINGS: Hw6dofMonitor writes a Settings.Global key while
    # VRService starts up (n1.f.t <- q1.a.f <- x0.a.<init> <- t0.c.<init>).
    # The system UID had it; stock Android refuses with
    #   SecurityException: Permission denial, must have one of:
    #   [android.permission.WRITE_SECURE_SETTINGS]
    # The permission carries the "development" flag, so it is grantable with
    # pm grant (install-six.ps1).
    # SYSTEM_ALERT_WINDOW: the environment host has to bring up
    # VRPrepareActivity and the VR space by itself, which Android 10+ blocks for
    # background callers:
    #   Background activity launch blocked! [callingPackage: com.huawei.vrlauncherx;
    #   callingUidProcState: FOREGROUND_SERVICE; ... BAL_BLOCK;
    #   intent: Intent { cmp=...activity.VRPrepareActivity }]
    # The platform-provided exemption for this is the "display over other apps"
    # appop, granted with `appops set <pkg> SYSTEM_ALERT_WINDOW allow`
    # (install-six.ps1). EMUI ran the same code as the system UID and never
    # needed it.
    #
    # READ_PHONE_STATE: the environment refuses to start while a call is in
    # progress (w0.b.r -> MSimTelephonyManager.getCallState). Reading call state
    # is a local capability, so the declaration is kept even though the earlier
    # offline pass dropped it as an "online companion".
    "com.huawei.vrlauncherx": ["android.permission.WRITE_SETTINGS",
                               "android.permission.FOREGROUND_SERVICE",
                               "android.permission.WRITE_SECURE_SETTINGS",
                               "android.permission.SYSTEM_ALERT_WINDOW",
                               "android.permission.READ_PHONE_STATE",
                               # bridge 到 vr_system 的 registry provider 需要；
                               # 原版它是系统 UID 隐式持有，见 docs/PATCH_AUDIT.md 第 25 节
                               "com.huawei.vrservice.CLIENT_SERVICE",
                               # 真机 2026-09-16：桌面绑 vrservice 的
                               #   com.huawei.vrinstaller.service.VrParamsInitializeService
                               # 被拒：
                               #   Permission Denial: ... requires com.huawei.vrservice.VRSystemApp
                               # 这个权限由 com.huawei.vrservice 自己声明（signature 级），
                               # 七个模块同一签名，消费者申请即可获得；EMUI 上它是系统授予的。
                               "com.huawei.vrservice.VRSystemApp",
                               # 真机 2026-09-16：空间里的 WiFi 名称控件崩
                               #   ArgumentOutOfRangeException at
                               #   WifiControllerQ.UpdateWifiName -> String.Substring(1, len-2)
                               # 原因是 i2/g1.r(Context) 读不到 SSID，返回了空串
                               # （原版把它当带引号的 SSID 去截引号）。
                               # 原版能读到是因为它跑在 system UID（原 manifest 有
                               # sharedUserId=android.uid.system），系统 UID 天然持有定位权限；
                               # Android 10+ 起 getSSID()/getConfiguredNetworks() 必须有定位权限。
                               # 这里把系统 UID 的隐式授权显式化，功能即恢复（并需在运行期 pm grant）。
                               "android.permission.ACCESS_FINE_LOCATION",
                               "android.permission.ACCESS_COARSE_LOCATION",
                               # 真机 2026-09-16：i2/t0.getUsageStatsList 拿不到用量统计，
                               #   W/HwVrLauncherX_AppManager: getUsageStatsList abnormal,
                               #   queryUsageStats size is 0
                               # UsageStatsManager.queryUsageStats 要求声明这条权限并由用户/
                               # appops 授予（GET_USAGE_STATS）；原版靠 system UID 隐式持有，
                               # 运行期用 `appops set com.huawei.vrlauncherx GET_USAGE_STATS allow`。
                               "android.permission.PACKAGE_USAGE_STATS"],
    # 主应用也要查 vr_system（2 处调用点），同样需要这个签名级权限
    "com.huawei.appmarket.vr": ["com.huawei.vrservice.CLIENT_SERVICE",
                                "com.huawei.vrservice.VRSystemApp",
                                # 打开主应用时由它显式启动 Runtime 的监督服务
                                # （通用安卓里跨应用启动组件的标准做法）。
                                # 原厂清单里这条权限本来就存在，另外五个包都在申请。
                                "com.huawei.hvrsdkserverapp.permission.RUNTIME_ALLOW",
                                # 真机 2026-09-16：
                                #   W/TelephonyPermissions: reportAccessDeniedToReadIdentifiers:
                                #     com.huawei.appmarket.vr:getSerial:-1
                                # 原版跑在 system UID，读设备序列号不需要额外授权；普通应用走
                                # TelephonyManager.getSerial 需要 READ_PHONE_STATE（运行期 pm grant）。
                                "android.permission.READ_PHONE_STATE"],
    # 视频/投屏/手柄：它们自己也要读写 VR 状态（SystemPropertiesEx）和
    # 查 ro.vr.surport，走的是桌面托管的注册表，所以要申请同一个签名级权限。
    "com.huawei.himovie.vr": ["android.permission.WRITE_SETTINGS",
                              "com.huawei.vrservice.CLIENT_SERVICE"],
    "com.huawei.vrvirtualscreen": ["android.permission.WRITE_SETTINGS",
                                   "com.huawei.vrservice.CLIENT_SERVICE"],
    # SYSTEM_ALERT_WINDOW: the handle service is started from the background by
    # the desktop's VRService and immediately calls startForeground(). Android 12+
    # refuses that unless the app has an exemption, and the crash loop shows up as
    # the system's "屡次停止运行" dialog:
    #
    #   Process: com.huawei.vrhandle:VRHandleService
    #   Unable to start service VRHandleService with Intent
    #       { act=com.huawei.vrservice.ACTION_RECONNECT_MSG }
    #   Caused by: android.app.ForegroundServiceStartNotAllowedException:
    #       Service.startForeground() not allowed due to mAllowStartForeground false
    #     at com.huawei.vrhandle.service.VRHandleService.b3(VRHandleService.java:44)
    #     at com.huawei.vrhandle.service.VRHandleService.onStartCommand(...)
    #
    # Reproduced deterministically by pushing both packages into the restricted
    # standby bucket (`am set-standby-bucket <pkg> restricted`): 6 exceptions and a
    # restart loop. SYSTEM_ALERT_WINDOW is the platform's own exemption for
    # background foreground-service starts, and the declaration is required before
    # `appops set <pkg> SYSTEM_ALERT_WINDOW allow` can take effect.
    "com.huawei.vrhandle": ["android.permission.SYSTEM_ALERT_WINDOW",
                            "com.huawei.vrservice.CLIENT_SERVICE"],
    # 注意：com.huawei.hvrsdkserverapp 的 manifest 是二进制（apktool -r 解码），
    # 不能走本脚本的文本改写；它的权限在 patch_sdk_manifest.py 里加，其中包含
    # 系统侧 actor 锁横屏所需的 WRITE_SETTINGS（见该脚本注释）。
}

# package -> sibling packages its original code resolves at runtime.
#
# Android 11+ hides other installed packages unless the app declares them, and
# the original code predates that rule. The handle app reads its JNI libraries
# out of the Runtime package:
#
#   r0.y0.j0()  -> createPackageContext("com.huawei.hvrsdkserverapp", 3)
#                  .getApplicationInfo().nativeLibraryDir
#
# A hidden package makes createPackageContext throw NameNotFoundException, the
# path degrades to "" and the static initialiser ends up calling
# System.load("/libMobileSensor.so"):
#
#   D nativeloader: Load /libMobileSensor.so ...: dlopen failed:
#       library "/libMobileSensor.so" not found
#   E vrhandle_VrPoseJni: load library error
#   java.lang.UnsatisfiedLinkError: No implementation found for void
#       com.huawei.vrhandle.VrPoseJni.helmetPoseStart()
#     at com.huawei.vrhandle.service.VRHandleService.e3(VRHandleService.java:23)
#
# The declaration is the platform's own answer to this, no app logic changes.
QUERIES = {
    "com.huawei.appmarket.vr": [
        "com.huawei.hvrsdkserverapp", "com.huawei.vrhandle",
        "com.huawei.vrlauncherx", "com.huawei.vrvirtualscreen",
        # Android 11+ 包可见性：要 call 它的 registry provider 才能拿到 vr_system
        "com.huawei.vrservice"],
    "com.huawei.vrlauncherx": [
        "com.huawei.appmarket.vr", "com.huawei.himovie.vr",
        "com.huawei.hvrsdkserverapp", "com.huawei.vrhandle",
        "com.huawei.vrvirtualscreen",
        "com.huawei.vrservice"],
    "com.huawei.himovie.vr": ["com.huawei.vrhandle"],
    "com.huawei.vrvirtualscreen": [
        "com.huawei.hvrsdkserverapp", "com.huawei.vrhandle",
        "com.huawei.vrlauncherx"],
    "com.huawei.vrhandle": [
        "com.huawei.appmarket.vr", "com.huawei.hvrsdkserverapp",
        "com.huawei.vrlauncherx"],
}


# 兼容层的跨进程注册表（vr_system 的 binder）由桌面托管。
# 原因：provider 只有在平台真正采纳 android:exported="true" 时才可跨进程访问，
# 而这份 manifest 是 apktool 解码后由 aapt2 重新编译的（文本 manifest），
# 布尔属性会被正确编译。同一个属性我们手写进 vrservice 的二进制 manifest 时，
# aapt2 与自写解析器都显示正确，但运行中的 PackageManager 仍当成未导出，
# 跨进程访问被拒：SecurityException ... that is not exported from UID ...
# 详见 docs/PATCH_AUDIT.md 第 29 节。
REGISTRY_PROVIDERS = {
    "com.huawei.vrlauncherx": {
        "name": ".compat.VrSystemRegistryProvider",
        "authority": "com.huawei.vrlauncherx.registry",
        "permission": "com.huawei.vrservice.CLIENT_SERVICE",
    },
}


def ensure_provider(working, spec, exported, permission):
    """把注册表 provider 插进 <application> 内部。

    必须插在 <application ...> 开标签**之后**：组件元素写在 <application> 外面
    （即 <manifest> 的子节点）会被 PackageParser 直接忽略，平台报
       IllegalArgumentException: Unknown authority ...
    踩过：早前版本把 provider 插到了 <application> 之前，结果 provider 根本没注册。
    """
    line = re.compile(
        r'\n[ \t]*<provider[^>]*android:name\s*=\s*"%s"[^>]*/?>'
        % re.escape(spec["name"]))
    working = line.sub("", working)          # 先删掉可能插错位置的旧条目
    anchor = re.search(r"\n(\s*)<application[^>]*>", working)
    if anchor is None:
        raise SystemExit("<application> not found for registry provider")
    indent = anchor.group(1)
    block = ('\n%s    <provider android:name="%s" android:authorities="%s"'
             ' android:exported="%s"%s/>'
             % (indent, spec["name"], spec["authority"],
                "true" if exported else "false",
                '' if not permission
                else ' android:permission="%s"' % permission))
    at = anchor.end()
    return working[:at] + block + working[at:], True


# 兼容层的上下文 provider：每个包都要有（见 HvrContextProvider 的注释）。
# 不导出 —— 它只在自己进程里被平台实例化，把 application context 交给兼容层。
CONTEXT_PROVIDER_NAME = "com.huawei.vrframework.compat.HvrContextProvider"

def ensure_queries(working, packages):
    """Add the missing <package> entries to <queries>, creating it if needed."""
    added = []
    block = re.search(r"<queries[^>]*>(.*?)</queries>", working, re.S)
    if block is not None:
        body = block.group(1)
        inserts = ""
        for package in packages:
            if 'android:name="%s"' % package in body:
                continue
            inserts += '        <package android:name="%s"/>\n' % package
            added.append(package)
        if inserts:
            end = block.end(1)
            working = working[:end] + "\n" + inserts + "    " + working[end:]
        return working, added

    anchor = re.search(r"\n(\s*)<application", working)
    if anchor is None:
        raise SystemExit("<application> not found for <queries> insertion")
    indent = anchor.group(1)
    inserts = "".join('        <package android:name="%s"/>\n' % package
                      for package in packages)
    text = "\n%s<queries>\n%s%s</queries>" % (indent, inserts, indent)
    working = working[:anchor.start()] + text + working[anchor.start():]
    return working, list(packages)


def main(root):
    decode = Path(root) / "decode"
    for package, permissions in NEEDED.items():
        manifest = decode / package / "AndroidManifest.xml"
        if not manifest.is_file():
            raise SystemExit("missing %s" % manifest)
        with open(manifest, "r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        eol = "\r\n" if "\r\n" in text else "\n"
        working = text.replace("\r\n", "\n")
        added = []
        for permission in permissions:
            # 必须严格匹配 <uses-permission ...>；同名的 <permission> 声明不算。
            # 踩过：桌面自己就 <permission android:name="com.huawei.vrservice.CLIENT_SERVICE"
            # protectionLevel="signatureOrSystem"/> —— 只声明、没申请。松散的
            # 'android:name="X" in text' 判断把这条声明当成了"已经申请过"，
            # 于是桌面拿不到权限，进不去我们托管的 registry provider。
            uses = re.compile(
                r'<uses-permission[^>]*android:name\s*=\s*"%s"' % re.escape(permission))
            if uses.search(working):
                continue
            anchor = re.search(r"<manifest[^>]*>\n", working)
            if anchor is None:
                raise SystemExit("manifest header not found in %s" % package)
            insertion = '    <uses-permission android:name="%s"/>\n' % permission
            working = working[:anchor.end()] + insertion + working[anchor.end():]
            added.append(permission)
        if added:
            if eol != "\n":
                working = working.replace("\n", eol)
            with open(manifest, "w", encoding="utf-8", newline="") as handle:
                handle.write(working)
        print("%-32s 新增权限 %s" % (package, ", ".join(added) if added else "（已存在）"))

    for package, packages in QUERIES.items():
        manifest = decode / package / "AndroidManifest.xml"
        with open(manifest, "r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        eol = "\r\n" if "\r\n" in text else "\n"
        working = text.replace("\r\n", "\n")
        working, added = ensure_queries(working, packages)
        if added:
            if eol != "\n":
                working = working.replace("\n", eol)
            with open(manifest, "w", encoding="utf-8", newline="") as handle:
                handle.write(working)
        print("%-32s 新增包可见性 %s"
              % (package, ", ".join(added) if added else "（已存在）"))

    for package, spec in REGISTRY_PROVIDERS.items():
        manifest = decode / package / "AndroidManifest.xml"
        with open(manifest, "r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        eol = "\r\n" if "\r\n" in text else "\n"
        working = text.replace("\r\n", "\n")
        working, added = ensure_provider(working, spec, True, spec["permission"])
        if added:
            if eol != "\n":
                working = working.replace("\n", eol)
            with open(manifest, "w", encoding="utf-8", newline="") as handle:
                handle.write(working)
        print("%-32s 注册表 provider %s" % (package, "已加入" if added else "（已存在）"))

    # 兼容层的上下文 provider：五个文本 manifest 的包都加。
    for package in NEEDED:
        manifest = decode / package / "AndroidManifest.xml"
        with open(manifest, "r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        eol = "\r\n" if "\r\n" in text else "\n"
        working = text.replace("\r\n", "\n")
        spec = {"name": CONTEXT_PROVIDER_NAME,
                "authority": "%s.hvrcompat.ctx" % package}
        working, added = ensure_provider(working, spec, False, None)
        if added:
            if eol != "\n":
                working = working.replace("\n", eol)
            with open(manifest, "w", encoding="utf-8", newline="") as handle:
                handle.write(working)
        print("%-32s 上下文 provider %s" % (package, "已加入" if added else "（已存在）"))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1]))
