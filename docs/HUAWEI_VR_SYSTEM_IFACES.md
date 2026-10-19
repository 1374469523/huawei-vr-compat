# 华为 VR 系统层接口契约（1:1 迁移基准）

本文记录原版六个软件真正依赖的华为系统层接口，以及它们的获取方式。
**这是“只换系统层、其余 1:1 照原样跑”的唯一依据**，不要用自己发明的接口替代。

证据来源（都可复现）：

1. 六个原包 dex 里的类型引用（`android/vrsystem/*`、`android/vr/*`）。
2. 桌面包 `华为VR桌面.apk` 自带了一份 AIDL 副本，签名完整可读。
3. 固件 `Huawei_Mate_20_X_EVR-AL00B_..._HMT/Firmware/fastbootimage/system.img`
   里 `system/framework/boot-hwframework.vdex`、`boot-hwEmui.vdex`、`boot-framework.vdex`
   含 `android.vrsystem` 的真实实现。

## 一、服务获取方式（最关键）

原版通过标准系统服务查找拿 VR 服务，不是私有 IPC：

```java
const-string v1, "vr_system"
invoke-virtual {p0, v1}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
check-cast p0, Landroid/vrsystem/IVRSystemServiceManager;
invoke-interface {p0}, Landroid/vrsystem/IVRSystemServiceManager;->isVRMode()Z
```

（`z0/c.smali` `shouldExitWhenGlassOut`，桌面包内）

即 EMUI 在框架里注册了名为 **`vr_system`** 的 system service，返回
`android.vrsystem.IVRSystemServiceManager`。通用安卓上该查找返回 null，
所有依赖它的原版分支都会走“VR 不可用”，这是六个软件串不起来、
主应用白屏的首要嫌疑点。

`IVRSystemServiceManager.VR_MANAGER = "vr_system"` 就是服务名常量。

## 二、客户端接口 `android.vrsystem.IVRSystemServiceManager`

（客户端用的门面，方法带 `Context`）

| 方法 | 说明 |
|---|---|
| `isVRMode()` | 当前是否处于 VR 模式（眼镜连接 + 已进入） |
| `isVRApplication(Context, String)` | 某包名是否 VR 应用 |
| `getHelmetBattery(Context)` | 眼镜电量 |
| `getHelmetBrightness(Context)` / `setHelmetBrightness(Context, int)` | 眼镜亮度 |
| `getContactName(Context, String)` | 来电联系人名（VR 内接电话用） |
| `registerVRListener(Context, IVRListener)` / `unregisterVRListener` | 注册/注销 VR 状态回调 |
| `registerExpandListener(Context, IVRListener)` | 扩展回调 |
| `acceptInCall(Context)` / `endInCall(Context)` | `@Deprecated`，接听/挂断 |

## 三、Binder 接口 `android.vrsystem.IVRSystemService`

（真正的 binder，`implements android.os.IInterface`）

`isVRmode()`、`getHelmetBattery()`、`getHelmetBrightness()`、`setHelmetBrightness(int)`、
`getContactName(String)`、`addVRListener(IVRListener)`、`deleteVRListener(IVRListener)`、
`registerExpandListener(IVRListener)`、`acceptInCall()`、`endInCall()`

## 四、回调接口 `android.vrsystem.IVRListener`

（`implements android.os.IInterface`；事件驱动整个 VR 环境状态机）

| 回调 | 语义 |
|---|---|
| `onHelmetChanged(boolean)` | 眼镜插入/拔出 |
| `onModeChanged(boolean)` | 进入/退出 VR 模式 |
| `onHeartBeatChanged(boolean)` | 心跳（眼镜在位保活） |
| `onBatteryChanged(Intent)` | 眼镜/手柄电量 |
| `onNetworkStateChanged(Intent)` | 网络状态（离线版可只保留接口） |
| `onPhoneStateChanged(int, int, String)` | 来电状态（离线版可只保留接口） |
| `onNewSMS(Intent)` | 短信（离线版可只保留接口） |
| `onNewNotification(StatusBarNotification)` | 通知转发到 VR 空间 |
| `onCallback(String, List)` | 通用回调通道 |

## 五、各包实际引用的接口

| 包 | 引用的系统接口 |
|---|---|
| `com.huawei.vr`（主应用） | `IVRListener`、`IVRSystemServiceManager` |
| `com.huawei.vrlauncherx`（桌面） | `IVRListener`、`IVRSystemService`、`IVRSystemServiceManager` |
| `com.huawei.himovie.vr`（视频） | 无（走 SDK/Runtime） |
| `com.huawei.vrvirtualscreen`（投屏） | `IVRListener` |
| `com.huawei.vrhandle`（手柄） | 无（蓝牙私有协议 + 广播） |
| 华为 vrsdk 3.5.0.82 | `IVRListener`、`IVRSystemServiceManager`、`android.vr.IVrServiceManager` |

## 六、迁移做法（不魔改）

1. 在 APK 内提供 `android.vrsystem.*` 三个接口的**同名同签名**实现（原包已自带
   interface/stub 副本，不需要重写；只补服务端实现类）。
2. 提供 `vr_system` 服务的实现，语义按上表，行为来自我们自己的底层：
   - `isVRMode()` / `onHelmetChanged` / `onModeChanged` 由真实 `HUAWEIAV03` 外接显示状态驱动；
   - `getHelmetBattery` 有真实来源才返回，否则保持“不可用”，不伪造；
   - `onNetworkStateChanged` / `onNewSMS` / `onPhoneStateChanged` 只保留接口，不给实现
     （用户明确要求离线，且这些是华为专属在线功能）。
3. 因为通用安卓无法往框架的 system service 表里注册名字，`getSystemService("vr_system")`
   这一处查找需要落到我们的实现上——这是**唯一允许动的系统调用点**，
   语义与返回值必须与原版一致。
4. 其余 Java/smali/Unity 逻辑不要改；去掉的只有联网、账号、登录、在线推荐/更新/推送链。

## 七、当前进度与待办

## 七之二、完整平台层清单（已用工具从 dex 抽出）

工具：`porting/tools/dex-platform-deps.py`（区分“包里已自带”与“真正依赖平台”）、
`porting/tools/dex-platform-signatures.py`（从调用点抽出精确签名）。
产出：`porting/analysis/PLATFORM_DEPENDENCIES.txt`、`porting/analysis/PLATFORM_API_SURFACE.txt`。

结论：六个包共引用 195 个华为平台类型，其中 **155 个是应用自己打包进来的**
（`android.vrsystem.*` 的 interface/stub/proxy 副本、`com.huawei.android.feature.*`、
`com.huawei.android.download.*` 等），**只有 40 个需要兼容层提供**，且签名已全部抽出：

| 命名空间 | 类 |
|---|---|
| `android.vrsystem` | `IVRSystemServiceManager`（`isVRMode`） |
| `com.huawei.android.app` | `ActionBarEx`、`HiEventEx`、`HiViewEx`、`PackageManagerEx` |
| `com.huawei.android.content` | `ContextEx`、`content.pm.ApplicationInfoEx` |
| `com.huawei.android.feature.*` | `compat.InstallCompat`、`install.*`、`module.*`（动态特性库，缺省即不可用） |
| `com.huawei.android.fsm` | `HwFoldScreenManagerEx(+$FoldDisplayModeListener)` |
| `com.huawei.android.hardware.input` | `InputManagerEx`（`injectInputEvent` / `injectInputEventByDisplayId`） |
| `com.huawei.android.immersion` | `ImmersionStyle` |
| `com.huawei.android.media` | `AudioServiceEx`、`AudioSystemEx` |
| `com.huawei.android.os` | `BuildEx$VERSION`、`PowerManagerEx`、`ServiceManagerEx`、`SystemPropertiesEx`、`UEventObserverEx(+$UEvent)`、`UserHandleEx` |
| `com.huawei.android.provider` | `SettingsEx$Systemex` |
| `com.huawei.android.telephony` | `PhoneStateListenerEx`、`PreciseCallStateEx`、`ServiceStateEx` |
| `com.huawei.android.util` | `HwNotchSizeUtil`、`NoExtAPIException` |
| `com.huawei.android.view` | `WindowManagerEx$LayoutParamsEx` |
| `com.huawei.android.vrsystem` | `IVRSystemServiceManagerEx`、`VrTouchInterfaceEx(+$VrInputEventCallback)` |
| `com.huawei.nearbysdk` | `NearbyAdapter`、`NearbyAdapterCallback`、`closeRange.*`（手柄近场配对用的华为专有库） |

其中两个是这套环境的关键：

- `IVRSystemServiceManagerEx.createVrDisplay(String, int[], Context)` /
  `destroyVrDisplay` / `destroyAllVrDisplay` —— 原版创建 VR 虚拟屏走的就是这里；
- `VrTouchInterfaceEx.registerInputEventCallback(IBinder, Looper, VrInputEventCallback)` /
  `setDefaultDisplayPowerMode(int)` —— 手柄/触控事件进入 VR 空间的通道。

按用户要求，异步投屏这一类可以**只提供接口、不给实现**；`nearbysdk`（华为专有近场配对）
同理，接口在、实现按需补。

- 已确认接口契约与获取方式（本文）。
- 已确认固件里 `android.vrsystem` 的真实实现位于 boot 类路径 vdex，
  需要时为签名核对再取。
- 待做：写出 `vr_system` 的兼容实现类；把 `getSystemService("vr_system")` 落到该实现；
  用真实外接显示状态驱动 `onHelmetChanged` / `onModeChanged` / `isVRMode()`；
  再逐个模块验证原流程。
- 主应用 `com.huawei.vr` 启动的是 `com.huawei.hwmarket.vr.MainActivity`
  （应用市场 VR 入口），当前显示纯白（截图像素均值 243/243/243），
  需要单独确认它是卡在 vr_system 缺失、还是卡在已停服的在线接口。
