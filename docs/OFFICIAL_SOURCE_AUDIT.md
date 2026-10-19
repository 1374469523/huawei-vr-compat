# 手写兼容类 vs 原厂件：来源审计

由 `tools/compat-source-audit.py` 生成（先跑 `tools/official-index.ps1`）。
口径：**原厂自己有的类就不该手写**，应当复制官方字节码，只换指向不改实现。

## 结论

- 手写/新增类合计 **68** 个。
- 三族**已整族改成官方字节码**（`android.vrsystem.*`、`com.huawei.gson.*`、`com.huawei.libcore.io.ExternalStorage*`）：实现已由 `patches/patch_official_platform_classes.py` 从原厂件复制进各模块，手写实现已删除，只剩 javac 用的存根。
- **36** 个官方有原件、但实现依赖华为系统设施：按「反编译官方实现、只换掉系统依赖、其余逐行照搬」处理（见下节）。
- 其余 **23** 个原厂确实没有（兼容层必须补的框架类，或本项目自己的胶水）。
- 另有 **9** 个编译期存根（只给 javac 用，不进包）。

## 要按官方实现移植的那一批

| 类 | 官方来源 | 官方实现依赖什么 | 需要换掉的那一个点 |
| --- | --- | --- | --- |
| `android.telephony.MSimTelephonyManager` | 原厂件：hwframework.jar | 官方 from() 是单例；getCallState(slot) 走 hidden 的 TelephonyManager.getDefault().getCallStateForSlot() | from() 改为单例；getCallState 用公开 TelephonyManager.getCallState()，slotId 接受但忽略（VR 只需判断有无通话） |
| `com.huawei.android.app.ActivityManagerEx` | 原厂件：hwframework.jar | 官方直接调 hidden 的 ActivityManager.getCurrentUser() | 公开 SDK 没有这个方法，用等价的 uid 区间推导并注明差异 |
| `com.huawei.android.app.HiEventEx` | 原厂件：hwframework.jar | 官方是华为分析 SDK 的事件载体（putAppInfo 填包名/版本） | 事件仍按官方构造（同一构造与 putAppInfo 语义）；按已批准的离线范围，不上报任何后端 |
| `com.huawei.android.app.HiViewEx` | 原厂件：hwframework.jar | 官方 byJson/report 把事件交给华为分析后端 | byJson 照官方构造事件；report 不发送（无 INTERNET、不初始化 hianalytics） |
| `com.huawei.android.app.PackageManagerEx` | 原厂件：hwframework.jar | 官方转给 com.huawei.android.content.pm.HwPackageManager（华为隐藏特性表） | 用公开 PackageManager 的特性表；七个包里这两个方法只被 updatesdk（在线更新链，已按离线范围切掉）调用 |
| `com.huawei.android.app.WindowManagerEx` | 原厂件：hwframework.jar | 官方经 IWindowManager.get/setAnimationScale 读写动画缩放 | 改读写 Settings.Global 里同名的三个键（平台自己就存在那里），写需要 WRITE_SECURE_SETTINGS（已声明并 pm grant） |
| `com.huawei.android.content.ContextEx` | 原厂件：hwframework.jar | 官方 registerReceiverAsUser 是 hidden API | 改用公开 registerReceiver（只能登记本用户，与原进程所在用户一致） |
| `com.huawei.android.content.pm.ApplicationInfoEx` | 原厂件：hwframework.jar | 官方直接读 ApplicationInfo.hwFlags（hidden 字段） | 公开 API 没有这组标志：返回 0 并记日志（不反射） |
| `com.huawei.android.fsm.HwFoldScreenManagerEx` | 原厂件：hwframework.jar | 官方转给 com.huawei.android.fsm.HwFoldScreenManager（华为折叠屏管理器） | 通用安卓公开 API 没有这个概念：返回中性值（不可折叠 / 模式未知）并记日志，注册的监听器保留，不伪造折叠状态（不反射） |
| `com.huawei.android.hardware.input.InputManagerEx` | 原厂件：hwframework.jar | 官方 injectInputEvent 直连 hidden 方法；按显示注入只允许投屏包，最终落 HwInputManager | 公开 API 没有注入能力（INJECT_EVENTS 是 signature|privileged）：如实记日志返回 false，不反射；按显示注入保留官方包名校验 |
| `com.huawei.android.iawareperf.UniPerfEx` | 原厂件：hwframework.jar | 官方调用华为 iAware 性能服务 | 服务不可用时保持中性值，不伪造性能策略生效 |
| `com.huawei.android.immersion.ImmersionStyle` | 原厂件：hwframework.jar | 官方读 EMUI 主题资源取颜色 | 改用公开主题属性（colorPrimary / colorControlNormal）取运行中主题的真实颜色，取不到退黑并记日志；getControlColor 与公开构造按官方补齐 |
| `com.huawei.android.media.AudioManagerEx` | 原厂件：hwframework.jar | 官方经 HwAudioServiceManager 注册音频模式回调，并把回调对象包装成华为内部类型 | 改用公开的 AudioManager.addOnModeChangedListener（API 31+）投递，Handler 转成 Executor；低于 API 31 时记日志不注册 |
| `com.huawei.android.media.AudioServiceEx` | 原厂件：hwframework.jar | 官方取 audio 服务后调 IAudioService.setBluetoothA2dpOn | 改用公开 AudioManager.setBluetoothA2dpOn（AOSP 内部同一条调用），公开 API 没有 A2DP 开关：如实记一次日志，由用户从系统 UI 切音频输出（不反射） |
| `com.huawei.android.media.AudioSystemEx` | 原厂件：hwframework.jar | 官方直连 hidden 的 android.media.AudioSystem | 同样直连（编译期存根），因此 setParameters 返回 HAL 的真实返回码 |
| `com.huawei.android.media.IAudioModeCallback` | 原厂件：hwframework.jar | 官方是 abstract class + 无参构造 + 抽象方法 onAudioModeChanged(int)，内部经 HwAudioServiceManager 注册 | 形状照官方（抽象类、无参构造、同一抽象方法）；投递改由 AudioManagerEx 用公开的 AudioManager.addOnModeChangedListener（API 31+）完成 |
| `com.huawei.android.os.BuildEx` | 原厂件：hwframework.jar | 官方只有 EMUI_VERSION / IS_DEBUGGABLE / getUDID / getSecondaryUDID | 本包只用到 VERSION.EMUI_SDK_INT（读 ro.build.hw_emui_api_level，非 EMUI 构建为 0） |
| `com.huawei.android.os.PowerManagerEx` | 原厂件：hwframework.jar | 官方 isInteractive/亮度接口走 IPowerManager 系统服务（要 DEVICE_POWER），userActivity/wakeUp 是 hidden 方法 | isInteractive 用公开 PowerManager；亮度用 Settings.System（appops 授权）；不反射 hidden 方法：wakeUp 只走公开的 ACQUIRE_CAUSES_WAKEUP 短暂持锁，userActivity 只走公开的 PARTIAL_WAKE_LOCK（并注明它不进系统 user-activity 统计） |
| `com.huawei.android.os.ServiceManagerEx` | 原厂件：hwframework.jar | 官方实现读写 Huawei 的 service manager（系统进程才有权限注册） | 服务表换成签名权限保护的 ContentProvider 注册表（宿主 = 桌面包） |
| `com.huawei.android.os.SystemPropertiesEx` | 原厂件：hwframework.jar | 官方就是 android.os.SystemProperties 的直连封装，但 VR 状态键（sys.glass.state / hw.vr.environment.status / hw.vr.virtualmode …）在 EMUI 上是可写的系统属性，普通应用写不了 | 五个方法照官方直连 SystemProperties；只把 VR 状态键的后端换成桌面托管的跨进程注册表（持久化）；ro.vr.surport 按「平台是否真的装着」回答 |
| `com.huawei.android.os.UEventObserverEx` | 原厂件：hwframework.jar | 官方包装 android.os.UEventObserver；平台实现要开 /dev/socket/uevent，普通应用被 SELinux 拒（且 startObserving/stopObserving 是 final，不能覆写） | 按桌面真正关心的 DP link 事件改用 DisplayManager 的显示连接回调，对外保留 UEventObserverEx + UEvent.get(String) 的同一套接口 |
| `com.huawei.android.os.UserHandleEx` | 原厂件：hwframework.jar | 官方直接调 hidden 的 UserHandle.myUserId/getUserId/getIdentifier | 前两个用同一套 uid 区间算术；getIdentifier 只用公开的 UserHandle.hashCode()（AOSP 源码里就是 return mHandle），null 返回 -1 与官方一致 |
| `com.huawei.android.provider.SettingsEx` | 原厂件：hwframework.jar | 官方 Systemex 就是 Settings.System 的同名封装 | 直接转发公开的 Settings.System（同一张表），已逐条对齐 |
| `com.huawei.android.telephony.PhoneStateListenerEx` | 原厂件：hwframework.jar | 官方的关键接线是 onPreciseCallStateChanged(PreciseCallState) -> 包装成 PreciseCallStateEx -> 回调 onPreciseCallStateChangedCallBack | 按官方补齐这条链；Looper 构造与 @Override 受公开 SDK 限制，已写明原因 |
| `com.huawei.android.telephony.PreciseCallStateEx` | 原厂件：hwframework.jar | 官方是公开构造函数 + PreciseCallState 的转发；null 一律 -1 | 照官方重写（含 8 个常量）；之前 private 构造导致应用造不出对象、判断链断掉 |
| `com.huawei.android.telephony.ServiceStateEx` | 原厂件：hwframework.jar | 官方直接调 ServiceState.getConfigRadioTechnology()（hidden） | EMUI 专有概念，公开 API 没有对应接口：返回 0（AOSP NETWORK_TYPE_UNKNOWN）并记日志（不反射） |
| `com.huawei.android.util.HwNotchSizeUtil` | 原厂件：hwframework.jar | 官方完全由 ro.config.hw_notch_size 驱动，通用安卓上该属性为空 | 保留官方属性通路，属性为空时改用真实 DisplayCutout（取不到就 0,0） |
| `com.huawei.android.util.NoExtAPIException` | 原厂件：hwframework.jar | 官方是四个构造函数的普通异常类 | 逐字补齐（含 serialVersionUID 与四个构造函数） |
| `com.huawei.android.view.LayoutParamsEx` | 原厂件：hwframework.jar | 官方 addHwFlags 写 EMUI 私有 layout flags | 记录在包装对象上并尝试写 AOSP 同义的 extraFlags；字段不存在就只记在包装对象里 |
| `com.huawei.android.view.WindowManagerEx` | 原厂件：hwframework.jar | 官方把 EMUI 私有 layout flags 写进平台 LayoutParams | 记录在本包装对象上，并尝试写 AOSP 同义的 extraFlags 字段；字段不存在时只保留在包装对象里 |
| `com.huawei.android.vrsystem.IVRSystemServiceManagerEx` | 原厂件：hwframework.jar | 官方持有 getSystemService("vr_system") 的 manager；三个静态多显示方法落到华为框架 HwDisplayManager；isVirtualScreenMode 在 boot classpath 版接口里才有 | manager 改走兼容入口 VRSystemServiceManagerImpl.get；多显示三个方法按已批准口径只保接口返回不可用；isVirtualScreenMode 在公开接口里不存在，如实返回 false 并记日志（不反射） |
| `com.huawei.android.vrsystem.VrTouchInterfaceEx` | 原厂件：hwPartVr.jar | 官方输入通道由 android.vrsystem.VrTouchInterface 提供，而它要求 Process.myUid()==1000（system UID），否则抛 SecurityException | 普通应用没有等价接口（MONITOR_INPUT 是签名级）：只保接口，事件不投递；后续按原计划走可选无障碍 / Shizuku 路径 |
| `com.huawei.cust.HwCfgFilePolicy` | 原厂件：hwframework.jar | 官方转给 huawei.cust.HwCfgFilePolicy（本机固件里没有该类），返回 EMUI 的 /cust 等目录 | 通用安卓没有这些分区：返回空目录列表（调用方找不到配置即不升级），官方公开常量全部补齐 |
| `com.huawei.system.BuildEx` | 原厂件：hwframework.jar | 官方 getOsBrand 读的是框架字符串资源 0x104020b；getRadioVersion 读 gsm.version.baseband | getRadioVersion 逐字照搬；getOsBrand 用公开的 Build.BRAND（资源 ID 跨设备不稳定，照抄会拿到错文本），官方公开字段一并补齐 |
| `com.huawei.systemmanager.notificationmanager.HwNotificationListenerEx` | 原厂件：hwframework.jar | 官方调 NotificationListenerService 的 hidden registerAsSystemService/unregisterAsSystemService | 只调公开的 NotificationListenerService.requestRebind(ComponentName)；unregisterAsSystemService 没有公开等价物，如实记日志不动作（不反射） |
| `com.huawei.systemmanager.notificationmanager.restrictedlock.HwLockPatternUtilsEx` | 原厂件：hwframework.jar | 官方用 hidden LockPatternUtils 读写 Settings.Secure 的 lockscreen.disabled | 用公开 Settings.Secure（只能当前用户）读写同一个键，写需要 WRITE_SECURE_SETTINGS（已声明并 pm grant） |

处理方式统一为：反汇编官方类 -> 读懂它每一步在做什么 -> 只把「华为系统设施」那一步换成通用安卓等价物 -> 其余逐行照搬。
**不允许**因为「官方版跑不通」就另写一套自己的逻辑。

## 对照表

| 类 | 手写文件 | 判定 | 依据 |
| --- | --- | --- | --- |
| `android.media.AudioSystem` | `shared/stubs/android/media/AudioSystem.java` | 编译期存根（不进包） | 运行时用设备/平台上的真类，见文件头注释 |
| `android.os.SystemProperties` | `shared/stubs/android/os/SystemProperties.java` | 编译期存根（不进包） | 运行时用设备/平台上的真类，见文件头注释 |
| `android.os.UEvent` | `shared/stubs/android/os/UEventObserver.java` | 编译期存根（不进包） | 运行时用设备/平台上的真类，见文件头注释 |
| `android.os.UEventObserver` | `shared/stubs/android/os/UEventObserver.java` | 编译期存根（不进包） | 运行时用设备/平台上的真类，见文件头注释 |
| `android.telephony.MSimTelephonyManager` | `shared/java/android/telephony/MSimTelephonyManager.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `android.telephony.PreciseCallState` | `shared/stubs/android/telephony/PreciseCallState.java` | 编译期存根（不进包） | 运行时用设备/平台上的真类，见文件头注释 |
| `android.vrsystem.IVRListener` | `shared/stubs/android/vrsystem/IVRListener.java` | 编译期存根（不进包） | 运行时用设备/平台上的真类，见文件头注释 |
| `android.vrsystem.IVRSystemService` | `shared/stubs/android/vrsystem/IVRSystemService.java` | 编译期存根（不进包） | 运行时用设备/平台上的真类，见文件头注释 |
| `android.vrsystem.IVRSystemServiceManager` | `shared/stubs/android/vrsystem/IVRSystemServiceManager.java` | 编译期存根（不进包） | 运行时用设备/平台上的真类，见文件头注释 |
| `android.vrsystem.Stub` | `shared/stubs/android/vrsystem/IVRSystemService.java` | 编译期存根（不进包） | 运行时用设备/平台上的真类，见文件头注释 |
| `android.vrsystem.VRSystemServiceManagerImpl` | `shared/java/android/vrsystem/VRSystemServiceManagerImpl.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.android.app.ActionBarEx` | `shared/java/com/huawei/android/app/ActionBarEx.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.android.app.ActivityManagerEx` | `shared/java/com/huawei/android/app/ActivityManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.app.HiEventEx` | `shared/java/com/huawei/android/app/HiEventEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.app.HiViewEx` | `shared/java/com/huawei/android/app/HiViewEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.app.PackageManagerEx` | `shared/java/com/huawei/android/app/PackageManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.app.WindowManagerEx` | `shared/java/com/huawei/android/app/WindowManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.content.ContextEx` | `shared/java/com/huawei/android/content/ContextEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.content.pm.ApplicationInfoEx` | `shared/java/com/huawei/android/content/pm/ApplicationInfoEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.fsm.FoldDisplayModeListener` | `shared/java/com/huawei/android/fsm/HwFoldScreenManagerEx.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.android.fsm.HwFoldScreenManagerEx` | `shared/java/com/huawei/android/fsm/HwFoldScreenManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.hardware.input.InputManagerEx` | `shared/java/com/huawei/android/hardware/input/InputManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.iawareperf.UniPerfEx` | `shared/java/com/huawei/android/iawareperf/UniPerfEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.immersion.ImmersionStyle` | `shared/java/com/huawei/android/immersion/ImmersionStyle.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.media.AudioManagerEx` | `shared/java/com/huawei/android/media/AudioManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.media.AudioServiceEx` | `shared/java/com/huawei/android/media/AudioServiceEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.media.AudioSystemEx` | `shared/java/com/huawei/android/media/AudioSystemEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.media.IAudioModeCallback` | `shared/java/com/huawei/android/media/IAudioModeCallback.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.os.BuildEx` | `shared/java/com/huawei/android/os/BuildEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.os.PowerManagerEx` | `shared/java/com/huawei/android/os/PowerManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.os.ServiceManagerEx` | `shared/java/com/huawei/android/os/ServiceManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.os.SystemPropertiesEx` | `shared/java/com/huawei/android/os/SystemPropertiesEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.os.UEvent` | `shared/java/com/huawei/android/os/UEventObserverEx.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.android.os.UEventObserverEx` | `shared/java/com/huawei/android/os/UEventObserverEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.os.UserHandleEx` | `shared/java/com/huawei/android/os/UserHandleEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.os.VERSION` | `shared/java/com/huawei/android/os/BuildEx.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.android.provider.SettingsEx` | `shared/java/com/huawei/android/provider/SettingsEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.provider.Systemex` | `shared/java/com/huawei/android/provider/SettingsEx.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.android.telephony.PhoneStateListenerEx` | `shared/java/com/huawei/android/telephony/PhoneStateListenerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.telephony.PreciseCallStateEx` | `shared/java/com/huawei/android/telephony/PreciseCallStateEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.telephony.ServiceStateEx` | `shared/java/com/huawei/android/telephony/ServiceStateEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.util.HwNotchSizeUtil` | `shared/java/com/huawei/android/util/HwNotchSizeUtil.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.util.NoExtAPIException` | `shared/java/com/huawei/android/util/NoExtAPIException.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.view.LayoutParamsEx` | `shared/java/com/huawei/android/view/WindowManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.view.WindowManagerEx` | `shared/java/com/huawei/android/view/WindowManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.vrsystem.IVRSystemServiceManagerEx` | `shared/java/com/huawei/android/vrsystem/IVRSystemServiceManagerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.android.vrsystem.VrInputEventCallback` | `shared/java/com/huawei/android/vrsystem/VrTouchInterfaceEx.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.android.vrsystem.VrTouchInterfaceEx` | `shared/java/com/huawei/android/vrsystem/VrTouchInterfaceEx.java` | 改：按官方移植 | 原厂件：hwPartVr.jar |
| `com.huawei.cust.HwCfgFilePolicy` | `shared/java/com/huawei/cust/HwCfgFilePolicy.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.fileprotect.HwSfpPolicyManager` | `shared/java/com/huawei/fileprotect/HwSfpPolicyManager.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.hvrsdkserverapp.compat.SystemServiceBinder` | `shared/runtime-actor/java/com/huawei/hvrsdkserverapp/compat/SystemServiceBinder.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| ~~`com.huawei.hvrsdkserverapp.compat.VrGlassBootReceiver`~~ | 已删除（2026-09-16） | — | 原包没有这个组件；它当初是「开机自启 + 装完模拟开机」的入口，用户明确不要自启，改成「打开华为 VR 时拉起」后它成了死代码，连类带清单声明一起去掉（见 PATCH_AUDIT 第 61 节） |
| `com.huawei.hvrsdkserverapp.compat.VrGlassWatchService` | `shared/runtime-actor/java/com/huawei/hvrsdkserverapp/compat/VrGlassWatchService.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类。2026-09-16 起改成导出 + `com.huawei.hvrsdkserverapp.permission.RUNTIME_ALLOW`（原厂清单里已有的签名级权限），由主应用在启动时显式拉起 |
| `com.huawei.hvrsdkserverapp.compat.VrSystemActor` | `shared/runtime-actor/java/com/huawei/hvrsdkserverapp/compat/VrSystemActor.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.nearbysdk.NearbyAdapter` | `shared/java/com/huawei/nearbysdk/NearbyAdapter.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.nearbysdk.NearbyAdapterCallback` | `shared/java/com/huawei/nearbysdk/NearbyAdapterCallback.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.nearbysdk.closeRange.CloseRangeBusinessType` | `shared/java/com/huawei/nearbysdk/closeRange/CloseRangeBusinessType.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.nearbysdk.closeRange.CloseRangeDeviceFilter` | `shared/java/com/huawei/nearbysdk/closeRange/CloseRangeDeviceFilter.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.nearbysdk.closeRange.CloseRangeDeviceListener` | `shared/java/com/huawei/nearbysdk/closeRange/CloseRangeDeviceListener.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.nearbysdk.closeRange.CloseRangeResult` | `shared/java/com/huawei/nearbysdk/closeRange/CloseRangeResult.java` | 保留（官方无同名类） | 原包与已入库原厂件里都没有；属兼容层必须提供的框架类 |
| `com.huawei.system.BuildEx` | `shared/java/com/huawei/system/BuildEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.systemmanager.notificationmanager.HwNotificationListenerEx` | `shared/java/com/huawei/systemmanager/notificationmanager/HwNotificationListenerEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.systemmanager.notificationmanager.restrictedlock.HwLockPatternUtilsEx` | `shared/java/com/huawei/systemmanager/notificationmanager/restrictedlock/HwLockPatternUtilsEx.java` | 改：按官方移植 | 原厂件：hwframework.jar |
| `com.huawei.vrframework.compat.HvrContextProvider` | `shared/java/com/huawei/vrframework/compat/HvrContextProvider.java` | 保留（本项目新增） | 本项目新增（VR 平台兼容入口） |
| `com.huawei.vrframework.compat.VrPlatformCompat` | `shared/java/com/huawei/vrframework/compat/VrPlatformCompat.java` | 保留（本项目新增） | 本项目新增（VR 平台兼容入口） |
| `com.huawei.vrframework.compat.VrPropertyStore` | `shared/java/com/huawei/vrframework/compat/VrPropertyStore.java` | 保留（本项目新增） | 本项目新增（VR 平台兼容入口） |
| `com.huawei.vrlauncherx.compat.VrSystemRegistryProvider` | `shared/java/com/huawei/vrlauncherx/compat/VrSystemRegistryProvider.java` | 保留（本项目新增） | 本项目新增（跨进程注册表宿主） |
| `com.huawei.vrservice.compat.CompatAppContext` | `shared/java/com/huawei/vrservice/compat/CompatAppContext.java` | 保留（本项目新增） | 本项目新增（provider 侧上下文） |

## 原厂件来源

- `com.huawei.appmarket.vr`：9726 个类定义
- `com.huawei.himovie.vr`：25341 个类定义
- `com.huawei.hvrsdkserverapp`：615 个类定义
- `com.huawei.vrhandle`：5389 个类定义
- `com.huawei.vrlauncherx`：2776 个类定义
- `com.huawei.vrservice`：1482 个类定义
- `com.huawei.vrvirtualscreen`：4560 个类定义
- `hvrframework-dex`：485 个类定义
- `hwPartVr`：9 个类定义
- `hwPartVr.jar`：9 个类定义
- `hwframework`：2025 个类定义
- `hwframework.jar`：2025 个类定义

详见 `原厂件/README.md`（来源镜像、镜像内路径、sha256）。
