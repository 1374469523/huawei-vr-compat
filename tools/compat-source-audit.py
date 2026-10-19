#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compat-source-audit.py —— 把「手写的兼容类」逐个拿去原包/原厂件里找同名原件。

    python tools/compat-source-audit.py            # 生成 docs/OFFICIAL_SOURCE_AUDIT.md

输入：
  shared/**/*.java            我手写/新增的代码（含 shared/stubs、shared/runtime-actor）
  build/official-index/*.txt  由 tools/official-index.ps1 生成的原包+原厂件类索引

判定：
  官方有同名类 -> 不该手写（改成复制官方字节码）
  官方无同名类 -> 属于兼容层必须自己提供的框架类，保留，但要按官方调用方签名对齐
"""
import os
import re
import sys
import glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "OFFICIAL_SOURCE_AUDIT.md")

# 明确属于本项目新增、原厂不存在的东西（不是「替换官方」，是「本项目自己的胶水」）
OURS = {
    "com/huawei/vrlauncherx/compat/": "本项目新增（跨进程注册表宿主）",
    "com/huawei/vrservice/compat/": "本项目新增（provider 侧上下文）",
    "com/huawei/vrframework/compat/": "本项目新增（VR 平台兼容入口）",
}

# 官方有原件、但实现依赖华为系统设施，原样搬到三星上跑不起来：
# 这一批按「反编译官方实现 -> 换掉系统依赖 -> 生成通用安卓版本」处理。
# 值 = (为什么不能原样搬, 要换掉的那一个点)
EXCEPTIONS = {
    "com.huawei.android.os.ServiceManagerEx":
        ("官方实现读写 Huawei 的 service manager（系统进程才有权限注册）",
         "服务表换成签名权限保护的 ContentProvider 注册表（宿主 = 桌面包）"),
    "com.huawei.android.os.SystemPropertiesEx":
        ("官方就是 android.os.SystemProperties 的直连封装，但 VR 状态键"
         "（sys.glass.state / hw.vr.environment.status / hw.vr.virtualmode …）"
         "在 EMUI 上是可写的系统属性，普通应用写不了",
         "五个方法照官方直连 SystemProperties；只把 VR 状态键的后端换成"
         '桌面托管的跨进程注册表（持久化）；ro.vr.surport 按「平台是否真的装着」回答'),
    "com.huawei.android.util.HwNotchSizeUtil":
        ("官方完全由 ro.config.hw_notch_size 驱动，通用安卓上该属性为空",
         "保留官方属性通路，属性为空时改用真实 DisplayCutout（取不到就 0,0）"),
    "com.huawei.android.iawareperf.UniPerfEx":
        ("官方调用华为 iAware 性能服务",
         "服务不可用时保持中性值，不伪造性能策略生效"),
    "com.huawei.fileprotect.HwSfpPolicyManager":
        ("官方查询 EMUI 文件保护服务",
         "无等价物：isSupportIudf() 返回 false，其余走「不支持」分支"),
    "com.huawei.android.immersion.ImmersionStyle":
        ("官方读 EMUI 主题配置",
         "配置缺失时返回默认值"),
    "com.huawei.android.vrsystem.IVRSystemServiceManagerEx":
        ("官方持有 getSystemService(\"vr_system\") 的 manager；三个静态多显示方法"
         "落到华为框架 HwDisplayManager；isVirtualScreenMode 在 boot classpath 版"
         "接口里才有",
         "manager 改走兼容入口 VRSystemServiceManagerImpl.get；多显示三个方法"
         "按已批准口径只保接口返回不可用；isVirtualScreenMode 在公开接口里不存在，"
         "如实返回 false 并记日志（不反射）"),
    "com.huawei.android.os.PowerManagerEx":
        ("官方 isInteractive/亮度接口走 IPowerManager 系统服务（要 DEVICE_POWER），"
         "userActivity/wakeUp 是 hidden 方法",
         "isInteractive 用公开 PowerManager；亮度用 Settings.System（appops 授权）；"
         "不反射 hidden 方法：wakeUp 只走公开的 ACQUIRE_CAUSES_WAKEUP 短暂持锁，"
         "userActivity 只走公开的 PARTIAL_WAKE_LOCK（并注明它不进系统 user-activity 统计）"),
    "com.huawei.android.vrsystem.VrTouchInterfaceEx":
        ("官方输入通道由 android.vrsystem.VrTouchInterface 提供，"
         "而它要求 Process.myUid()==1000（system UID），否则抛 SecurityException",
         "普通应用没有等价接口（MONITOR_INPUT 是签名级）：只保接口，"
         "事件不投递；后续按原计划走可选无障碍 / Shizuku 路径"),
    "com.huawei.android.os.UserHandleEx":
        ("官方直接调 hidden 的 UserHandle.myUserId/getUserId/getIdentifier",
         "前两个用同一套 uid 区间算术；getIdentifier 只用公开的 UserHandle.hashCode()"
         "（AOSP 源码里就是 return mHandle），null 返回 -1 与官方一致"),
    "com.huawei.android.media.AudioSystemEx":
        ("官方直连 hidden 的 android.media.AudioSystem",
         "同样直连（编译期存根），因此 setParameters 返回 HAL 的真实返回码"),
    "com.huawei.android.media.AudioServiceEx":
        ("官方取 audio 服务后调 IAudioService.setBluetoothA2dpOn",
         "改用公开 AudioManager.setBluetoothA2dpOn（AOSP 内部同一条调用），"
         "公开 API 没有 A2DP 开关：如实记一次日志，由用户从系统 UI 切音频输出（不反射）"),
    "com.huawei.android.hardware.input.InputManagerEx":
        ("官方 injectInputEvent 直连 hidden 方法；按显示注入只允许投屏包，"
         "最终落 HwInputManager",
         "公开 API 没有注入能力（INJECT_EVENTS 是 signature|privileged）："
         "如实记日志返回 false，不反射；按显示注入保留官方包名校验"),
    "com.huawei.android.telephony.PhoneStateListenerEx":
        ("官方的关键接线是 onPreciseCallStateChanged(PreciseCallState) -> "
         "包装成 PreciseCallStateEx -> 回调 onPreciseCallStateChangedCallBack",
         "按官方补齐这条链；Looper 构造与 @Override 受公开 SDK 限制，已写明原因"),
    "com.huawei.android.telephony.PreciseCallStateEx":
        ("官方是公开构造函数 + PreciseCallState 的转发；null 一律 -1",
         "照官方重写（含 8 个常量）；之前 private 构造导致应用造不出对象、判断链断掉"),
    "com.huawei.android.app.ActivityManagerEx":
        ("官方直接调 hidden 的 ActivityManager.getCurrentUser()",
         "公开 SDK 没有这个方法，用等价的 uid 区间推导并注明差异"),
    "android.telephony.MSimTelephonyManager":
        ("官方 from() 是单例；getCallState(slot) 走 hidden 的 "
         "TelephonyManager.getDefault().getCallStateForSlot()",
         "from() 改为单例；getCallState 用公开 TelephonyManager.getCallState()，"
         "slotId 接受但忽略（VR 只需判断有无通话）"),
    "com.huawei.android.util.NoExtAPIException":
        ("官方是四个构造函数的普通异常类",
         "逐字补齐（含 serialVersionUID 与四个构造函数）"),
    "com.huawei.android.media.IAudioModeCallback":
        ("官方是 abstract class + 无参构造 + 抽象方法 onAudioModeChanged(int)，"
         "内部经 HwAudioServiceManager 注册",
         "形状照官方（抽象类、无参构造、同一抽象方法）；投递改由 AudioManagerEx 用公开的 "
         "AudioManager.addOnModeChangedListener（API 31+）完成"),
    "com.huawei.system.BuildEx":
        ("官方 getOsBrand 读的是框架字符串资源 0x104020b；getRadioVersion 读 "
         "gsm.version.baseband",
         "getRadioVersion 逐字照搬；getOsBrand 用公开的 Build.BRAND"
         "（资源 ID 跨设备不稳定，照抄会拿到错文本），官方公开字段一并补齐"),
    "com.huawei.android.immersion.ImmersionStyle":
        ("官方读 EMUI 主题资源取颜色",
         "改用公开主题属性（colorPrimary / colorControlNormal）取运行中主题的真实颜色，"
         "取不到退黑并记日志；getControlColor 与公开构造按官方补齐"),
    "com.huawei.cust.HwCfgFilePolicy":
        ("官方转给 huawei.cust.HwCfgFilePolicy（本机固件里没有该类），"
         "返回 EMUI 的 /cust 等目录",
         "通用安卓没有这些分区：返回空目录列表（调用方找不到配置即不升级），"
         "官方公开常量全部补齐"),
    "com.huawei.android.content.pm.ApplicationInfoEx":
        ("官方直接读 ApplicationInfo.hwFlags（hidden 字段）",
         "公开 API 没有这组标志：返回 0 并记日志（不反射）"),
    "com.huawei.android.app.PackageManagerEx":
        ("官方转给 com.huawei.android.content.pm.HwPackageManager（华为隐藏特性表）",
         "用公开 PackageManager 的特性表；七个包里这两个方法只被 updatesdk"
         "（在线更新链，已按离线范围切掉）调用"),
    "com.huawei.android.fsm.HwFoldScreenManagerEx":
        ("官方转给 com.huawei.android.fsm.HwFoldScreenManager（华为折叠屏管理器）",
         "通用安卓公开 API 没有这个概念：返回中性值（不可折叠 / 模式未知）并记日志，"
         "注册的监听器保留，不伪造折叠状态（不反射）"),
    "com.huawei.android.view.WindowManagerEx":
        ("官方把 EMUI 私有 layout flags 写进平台 LayoutParams",
         "记录在本包装对象上，并尝试写 AOSP 同义的 extraFlags 字段；"
         "字段不存在时只保留在包装对象里"),
    "com.huawei.android.provider.SettingsEx":
        ("官方 Systemex 就是 Settings.System 的同名封装",
         "直接转发公开的 Settings.System（同一张表），已逐条对齐"),
    "com.huawei.android.content.ContextEx":
        ("官方 registerReceiverAsUser 是 hidden API",
         "改用公开 registerReceiver（只能登记本用户，与原进程所在用户一致）"),
    "com.huawei.android.telephony.ServiceStateEx":
        ("官方直接调 ServiceState.getConfigRadioTechnology()（hidden）",
         "EMUI 专有概念，公开 API 没有对应接口：返回 0（AOSP NETWORK_TYPE_UNKNOWN）并记日志（不反射）"),
    "com.huawei.android.app.HiEventEx":
        ("官方是华为分析 SDK 的事件载体（putAppInfo 填包名/版本）",
         "事件仍按官方构造（同一构造与 putAppInfo 语义）；按已批准的离线范围，"
         "不上报任何后端"),
    "com.huawei.android.app.HiViewEx":
        ("官方 byJson/report 把事件交给华为分析后端",
         "byJson 照官方构造事件；report 不发送（无 INTERNET、不初始化 hianalytics）"),
    "com.huawei.android.app.WindowManagerEx":
        ("官方经 IWindowManager.get/setAnimationScale 读写动画缩放",
         "改读写 Settings.Global 里同名的三个键（平台自己就存在那里），"
         "写需要 WRITE_SECURE_SETTINGS（已声明并 pm grant）"),
    "com.huawei.android.media.AudioManagerEx":
        ("官方经 HwAudioServiceManager 注册音频模式回调，"
         "并把回调对象包装成华为内部类型",
         "改用公开的 AudioManager.addOnModeChangedListener（API 31+）投递，"
         "Handler 转成 Executor；低于 API 31 时记日志不注册"),
    "com.huawei.android.os.BuildEx":
        ("官方只有 EMUI_VERSION / IS_DEBUGGABLE / getUDID / getSecondaryUDID",
         "本包只用到 VERSION.EMUI_SDK_INT（读 ro.build.hw_emui_api_level，非 EMUI 构建为 0）"),
    "com.huawei.android.os.UEventObserverEx":
        ("官方包装 android.os.UEventObserver；平台实现要开 /dev/socket/uevent，"
         "普通应用被 SELinux 拒（且 startObserving/stopObserving 是 final，不能覆写）",
         "按桌面真正关心的 DP link 事件改用 DisplayManager 的显示连接回调，"
         "对外保留 UEventObserverEx + UEvent.get(String) 的同一套接口"),
    "com.huawei.android.view.LayoutParamsEx":
        ("官方 addHwFlags 写 EMUI 私有 layout flags",
         "记录在包装对象上并尝试写 AOSP 同义的 extraFlags；字段不存在就只记在包装对象里"),
    "com.huawei.systemmanager.notificationmanager.HwNotificationListenerEx":
        ("官方调 NotificationListenerService 的 hidden registerAsSystemService/"
         "unregisterAsSystemService",
         "只调公开的 NotificationListenerService.requestRebind(ComponentName)；"
         "unregisterAsSystemService 没有公开等价物，如实记日志不动作（不反射）"),
    "com.huawei.systemmanager.notificationmanager.restrictedlock.HwLockPatternUtilsEx":
        ("官方用 hidden LockPatternUtils 读写 Settings.Secure 的 lockscreen.disabled",
         "用公开 Settings.Secure（只能当前用户）读写同一个键，"
         "写需要 WRITE_SECURE_SETTINGS（已声明并 pm grant）"),
}

# 与 patches/patch_official_platform_classes.py 的 COPY_PREFIXES 保持一致：
# 这些类族的官方实现只依赖公开 AOSP API 或自身，可以整族复制字节码。
COPY_PREFIXES = (
    "Landroid/vrsystem/",
    "Lcom/huawei/gson/",
    "Lcom/huawei/libcore/io/ExternalStorage",
)


def hand_written_classes():
    """返回 {类描述符: 相对路径}，来自 shared 下的 java 源码。"""
    found = {}
    for path in glob.glob(os.path.join(REPO, "shared", "**", "*.java"), recursive=True):
        rel = os.path.relpath(path, REPO).replace("\\", "/")
        with open(path, encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
        pkg = re.search(r"^package\s+([\w.]+);", text, re.M)
        if not pkg:
            continue
        types = re.findall(
            r"^\s*(?:public\s+)?(?:final\s+|abstract\s+|static\s+)*"
            r"(?:class|interface|enum)\s+(\w+)", text, re.M)
        for name in types:
            desc = "L%s/%s;" % (pkg.group(1).replace(".", "/"), name)
            found[desc] = rel
    return found


def official_index():
    sources = {}
    for path in glob.glob(os.path.join(REPO, "build", "official-index", "*.txt")):
        name = os.path.basename(path)[:-4]
        if name.startswith("_"):
            continue
        with open(path, encoding="utf-8", errors="ignore") as handle:
            sources[name] = set(line.strip() for line in handle if line.strip())
    return sources


def main():
    mine = hand_written_classes()
    official = official_index()
    if not official:
        print("缺少 build/official-index/*.txt：先跑 tools/official-index.ps1", file=sys.stderr)
        return 1

    rows = []
    for desc in sorted(mine):
        rel = mine[desc]
        hits = [name for name, classes in sorted(official.items()) if desc in classes]
        apk_hits = [h for h in hits if not h.endswith(".jar")]
        jar_hits = [h for h in hits if h.endswith(".jar")]
        ours = next((why for prefix, why in OURS.items() if prefix in rel), None)
        if "/stubs/" in rel:
            # 编译期存根：只给 javac 看，不进包，因此不参与「该不该手写」的判定。
            verdict = "编译期存根（不进包）"
            note = "运行时用设备/平台上的真类，见文件头注释"
        elif hits and desc.startswith(COPY_PREFIXES):
            verdict = "改：复制官方字节码"
            note = "原厂件：" + "、".join(jar_hits) if jar_hits else "原包：" + "、".join(apk_hits)
        elif hits:
            # 官方有原件，但实现依赖华为系统设施：不能整族复制，要按官方
            # 实现反编译后替换系统依赖。
            verdict = "改：按官方移植"
            note = "原厂件：" + "、".join(jar_hits) if jar_hits else "原包：" + "、".join(apk_hits)
        elif ours:
            verdict = "保留（本项目新增）"
            note = ours
        else:
            verdict = "保留（官方无同名类）"
            note = "原包与已入库原厂件里都没有；属兼容层必须提供的框架类"
        rows.append((desc, rel, verdict, note))

    replace = [r for r in rows if r[2] == "改：复制官方字节码"]
    port = [r for r in rows if r[2] == "改：按官方移植"]
    keep = [r for r in rows if r[2].startswith("保留")]
    stubs = [r for r in rows if r[2] == "编译期存根（不进包）"]

    lines = []
    lines.append("# 手写兼容类 vs 原厂件：来源审计")
    lines.append("")
    lines.append("由 `tools/compat-source-audit.py` 生成（先跑 `tools/official-index.ps1`）。")
    lines.append("口径：**原厂自己有的类就不该手写**，应当复制官方字节码，只换指向不改实现。")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append("- 手写/新增类合计 **%d** 个。" % len(rows))
    lines.append("- 三族**已整族改成官方字节码**（`android.vrsystem.*`、`com.huawei.gson.*`、"
                 "`com.huawei.libcore.io.ExternalStorage*`）：实现已由 `patches/patch_official_platform_classes.py` "
                 "从原厂件复制进各模块，手写实现已删除，只剩 javac 用的存根。")
    lines.append("- **%d** 个官方有原件、但实现依赖华为系统设施：按「反编译官方实现、只换掉系统依赖、"
                 "其余逐行照搬」处理（见下节）。" % len(port))
    lines.append("- 其余 **%d** 个原厂确实没有（兼容层必须补的框架类，或本项目自己的胶水）。" % len(keep))
    lines.append("- 另有 **%d** 个编译期存根（只给 javac 用，不进包）。" % len(stubs))
    lines.append("")
    lines.append("## 要按官方实现移植的那一批")
    lines.append("")
    lines.append("| 类 | 官方来源 | 官方实现依赖什么 | 需要换掉的那一个点 |")
    lines.append("| --- | --- | --- | --- |")
    for desc, rel, verdict, note in port:
        name = desc[1:-1].replace("/", ".")
        why, swap = EXCEPTIONS.get(name, ("（待逐类判定）", "（待逐类判定）"))
        lines.append("| `%s` | %s | %s | %s |" % (name, note, why, swap))
    lines.append("")
    lines.append("处理方式统一为：反汇编官方类 -> 读懂它每一步在做什么 -> 只把"
                 "「华为系统设施」那一步换成通用安卓等价物 -> 其余逐行照搬。")
    lines.append("**不允许**因为「官方版跑不通」就另写一套自己的逻辑。")
    lines.append("")
    lines.append("## 对照表")
    lines.append("")
    lines.append("| 类 | 手写文件 | 判定 | 依据 |")
    lines.append("| --- | --- | --- | --- |")
    for desc, rel, verdict, note in rows:
        name = desc[1:-1].replace("/", ".")
        lines.append("| `%s` | `%s` | %s | %s |" % (name, rel, verdict, note))
    lines.append("")
    lines.append("## 原厂件来源")
    lines.append("")
    for name, classes in sorted(official.items()):
        lines.append("- `%s`：%d 个类定义" % (name, len(classes)))
    lines.append("")
    lines.append("详见 `原厂件/README.md`（来源镜像、镜像内路径、sha256）。")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    print("已写出 %s" % os.path.relpath(OUT, REPO))
    print("手写 %d，复制官方 %d，按官方移植 %d，保留 %d"
          % (len(rows), len(replace), len(port), len(keep)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
