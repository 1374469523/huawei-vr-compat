# 补丁审计台账

> 本文件记录每次改动的「原调用点 → 替代实现 → 消费者 → 验证结果」。
> **执行口径见 [`PORTING_METHOD.md`](PORTING_METHOD.md)**：只动和系统不兼容的那一层，
> 接口不动；动手前先去原厂固件里确认这个边界原来是谁提供的；每轮改动都要落到本文件。

规则：每一条对原包的改动都要写清楚「原调用点 / 为什么改 / 由谁接管 / 当前状态」。
凡是不能用平台接口解释的改动，一律视为待回退项。

## 一、允许改动的系统调用点（已完成）

### vr_system 查找重定向

- 原调用点：`Context.getSystemService("vr_system")`（含经 `Activity` / `Service` 调用的形式）。
- 事实：EMUI 在框架里注册了名为 `vr_system` 的系统服务，返回
  `android.vrsystem.IVRSystemServiceManager`；通用安卓没有这个名字，且应用无法往平台注册表里加名字。
- 改动：全部 19 处查找改为 `android.vrsystem.VRSystemServiceManagerImpl.get(Context)`，
  返回值实现的仍是同一个 `android.vrsystem.IVRSystemServiceManager` 接口。
- 统计（脚本 `patches/patch_vr_system.py` 断言，数量不符即报错）：

  | 包 | 查找重定向 | 注册保留 |
  |---|---|---|
  | `com.huawei.appmarket.vr` | 2 | 0 |
  | `com.huawei.hvrsdkserverapp` | 7 | 0 |
  | `com.huawei.vrlauncherx` | 10 | 1 |

- 保留不动的一处：桌面 `VRService` 用
  `com.huawei.android.os.ServiceManagerEx.addService("vr_system", binder)` 注册自己的 binder。
  这是服务**注册**不是查找，逻辑保持原样（兼容层的 ServiceManagerEx 只做本地登记）。
- 由谁接管：`shared/java/android/vrsystem/VRSystemServiceManagerImpl.java`。
  状态来自真实硬件：`HUAWEIAV03` 外接显示的插拔驱动
  `isVRMode` / `onHelmetChanged` / `onModeChanged` / `onHeartBeatChanged`；
  无真实来源的（眼镜电量/亮度、联系人）返回不可用；联网类回调一律不触发。

## 二、只保接口、实现待补（用户已确认本轮不做）

## 二之二、只动和系统不兼容的部分（用户确立的原则）

**原则：接口一律不动。** 系统层缺什么，就用同名的方式把它实现出来；不改原版的
再拿它们逐个去原包和原厂固件里找同名原件。凡是原厂自己有的，就不该手写    搬运「官方实现能在通用安卓上直接跑」的类族  ，其余反编译并借鉴生成能在通用安卓上直接跑的
权限名、类名、方法签名和调用点。

### 案例：手柄一直提示「请开启蓝牙」（已修复）

- 现象：蓝牙已开启、权限也已授予，手柄界面仍弹「华为 VR 手柄想要开启蓝牙」。
- 原调用点：`decode/com.huawei.vrhandle/smali/r0/y0.smali`
  `.method public static W(I)I` 里

  ```
  const-string v3, "com.huawei.android.permission.VR"
  invoke-virtual {v0, v3, p0}, Landroid/content/pm/PackageManager;->checkPermission(...)
  ```

  这是华为的平台权限，通用安卓上不存在，于是**连应用自己**都没通过检查，
  蓝牙状态查询被拒 → 界面判定「蓝牙没开」。
- 修复方式（1:1，不改代码）：在 manifest 里**同名实现**该权限

  ```
  <permission android:name="com.huawei.android.permission.VR" android:protectionLevel="signature"/>
  ```

  六包同一签名，因此持有该权限，原版检查原样通过。
- 证据：`patches/patch_controller.py`；实测装配后手柄直接进入原版配对页
  （「手柄配对 / 配对前，请将电池放入手柄 / 配对」），不再出现开启蓝牙弹窗。

### 案例：手柄配对时的分析上报崩溃（已修复）

- `k0/d.smali` 的分析基类构造里读 `BuildEx.VERSION`，在通用安卓上抛异常打断配对。
- 修复：把该基类的构造与两个上报方法清空，**配对界面与协议一律不动**。

### 待办：其余各包按同一原则继续

### 桌面已经越过的卡点（2026-09-15 实测）

| 卡点 | 原调用点 | 同名实现方式 |
|---|---|---|
| 隐私页点「同意」后崩溃 `SecurityException: WRITE_SETTINGS` | `q2/e`(PrivacytHelper) → `Settings.System.putInt` | manifest 声明 `WRITE_SETTINGS`，`appops set <pkg> WRITE_SETTINGS allow` 授予（EMUI 上它是系统 UID 所以天然持有） |
| 同上，`IllegalArgumentException: You cannot keep your settings in the secure settings.` | 同一个 helper 写 `PRIVACY_ACCEPTED` 键 | 平台禁止应用写该键（给 root / `WRITE_SECURE_SETTINGS` 同样被拒），因此用 shell/root 预置该键；已按用户要求撤回 `WRITE_SECURE_SETTINGS` 那处编辑 |
| 启动弹「当前系统版本或机型不支持打开该应用」 | `Vr2dStartUpActivity.<clinit>`：`SystemPropertiesEx.getBoolean("ro.vr.surport", false)` | 兼容层同名实现该平台属性（`SystemPropertiesEx` 对 `ro.vr.surport` / `ro.vr.support` 返回 true），应用代码不动 |

当前桌面停在「若要使用该应用，请连接华为 VR 眼镜」——这句是布局
`activity_2d_start_up.xml` 里的静态文本，眼镜（`HUAWEIAV03`）其实已经插着。
真机确认：**桌面的 VR 环境服务一个都没在跑**
（`dumpsys activity services com.huawei.vrlauncherx` 为空），而它的 manifest 里有

```
com.huawei.client.vrservice.VRService            (process com.huawei.vrservice)
com.huawei.vrtouch.VrTouchService                (permission com.huawei.android.permission.VR)
com.huawei.client.vrservice.VrStateService
com.huawei.client.vrservice.VrInnerService
com.huawei.client.vrservice.VrStateQueryService
com.huawei.vrhandle.VrHandleReconnectService
```

在 EMUI 上这些由框架拉起、并被其它 VR 应用绑定；通用安卓上没人拉它们，
所以 `VRListenerManager` 收不到「眼镜已连接」，页面就一直等着。
下一步就是按同一原则补这个「系统侧启动者」：把这些原版服务按其原始 action/绑定关系拉起来，
不改它们的代码。

各包当前卡点（真机实测）：

| 包 | 现象 | 需要按同名方式补的系统件 |
|---|---|---|
| `com.huawei.himovie.vr` | 启动进 `TermsLoginActivity`（条款/登录）后退出 | 条款/登录链（属已批准的离线移除范围） |
| `com.huawei.vrlauncherx` | 停在 `PrivacyStatementActivity` | 平台 VR 权限/服务 |
| `com.huawei.vrvirtualscreen` | 停在 `Vr2dStartUpActivity` | 平台 VR 权限/服务 |
| `com.huawei.appmarket.vr` | 停在「连接 VR 眼镜」 | `vr_system` 状态（已接，待复核） |

处理方式与手柄一致：先定位原调用点，再用同名实现补齐，不改原接口。

### 异步投屏

- 接口：`com.huawei.android.vrsystem.IVRSystemServiceManagerEx`
  `createVrDisplay(String, int[], Context)` / `destroyVrDisplay(String, Context)` /
  `destroyAllVrDisplay(Context)`；`android.vr.IVrServiceManager`
  `startFrontBufferDisplay()` / `stopFrontBufferDisplay()` / `getVsync()` /
  `getAvailableFreqLevels()` / `setSchedFifo(int,int)` / `setVrPlatPerf(int,int)` /
  `releaseVrPlatPerf()`（服务名常量 `VR_MANAGER`，SDK 包自带该接口）。
- 当前实现：签名照抄，返回「不可用」（`false` / `-1` / 空数组），让调用方走它原有的失败分支。
- 待补：接入真实虚拟屏/FrontBuffer 路径。

### 头部跟踪

- 接口：`HVRCORE.IHelmetHandle`（`GetHeadInfo` / `GetPosture` / `GetHelmetInfoInner`）、
  `HVRPluginCore.GetHelmetHandle()`、原生 `HVR_Android_GetHeadPose` /
  `HVR_Android_IsHelmetAvailable` / `HVR_Android_GetHelmet` /
  `HVR_Android_RegisterHelmetCallback` / `HVR_Android_SetPoseLock`，
  配套类型 `TrackStatus` / `VrHeadPose` / `VrPosture` / `VrQuaternion` / `HelmetHandleImp`。
- 当前状态：Unity 程序集与调用点未改动（按用户要求不做自研改造）；
  可行性判定待做——枚举 `HUAWEIAV03` 的 USB 接口与 HID 描述符，确认是否存在姿态通道。
- 待补：判定可行则接真实姿态；不可行则以设备描述符 dump 作为阻塞证据记录。

## 三、旧仓补丁中发现的问题（新仓一律不再采用）

| 旧做法 | 为什么有问题 | 新仓做法 |
|---|---|---|
| `patch_main.py` 把主应用包名改成 `com.huawei.vr` | 六个原包 dex 里没有任何一处引用 `com.huawei.vr`，而 `com.huawei.appmarket.vr` 被桌面(2)/手柄(1)/投屏(1)/SDK(2) 与主应用自身(11) 引用；改名直接破坏跨包身份 | 保留原包名，禁止改名 |
| 整体删除 manifest 里所有 service / receiver / provider | 一次性抹掉原版职责，是「少功能」的直接来源 | 只摘纯在线组件，其余保留 |
| 改写 `HVRActivity.onCreate`、跳过准备页、把欢迎页按钮改接到桌面 | 属于自研改造，改变了原操作流程 | 不改原逻辑，走平台接口 |
| Runtime 包不是移植原 APK，而是重写了一个 Gradle 工程 | 与原版职责脱节 | Runtime 直接用原 APK 移植 |
| 编译期只部署 `com.huawei.vrcompat.*` 自有实现，不补齐华为平台类 | 原版调用的 `com.huawei.android.*` 平台类缺失，代码走不到原分支 | 补齐 35 个平台类（见 `PLATFORM_API_SURFACE.txt`） |

## 四、平台类实现台账

- 清单与每个成员的真实调用方式（`invoke-static` / `invoke-virtual` / `invoke-interface`）
  见 `PLATFORM_INVOKE_MODES.txt`，静态/实例归属以它为准。
- 实现进度（已实现 / 接口占位 / 不可用）随每个类落盘时回填。
- 修正一处早期统计错误：`com.huawei.android.feature.*` **不是**平台依赖，
  使用它的包都自带了这套动态特性库（`PLATFORM_DEPENDENCIES.txt` 的逐包清单为准），
  因此兼容层不实现它。

## 五、补齐「系统侧」缺失职责（2026-09-15，真机 SM-F731U1 + HUAWEIAV03）

这一轮的对象不是某一个原应用，而是**EMUI 框架原来承担、通用安卓上不存在的那一层**。
证据全部来自六个原包的 smali 与真机 logcat，没有自研接口。

### 5.1 原版协议的还原（调用点 → 语义）

| 证据（原包） | 原语义 | 通用安卓缺什么 |
|---|---|---|
| `com.huawei.client.vrservice.VRService`（桌面，进程 `com.huawei.vrservice`），`onCreate` 里 `ServiceManagerEx.addService("vr_system", …)` | 桌面就是 `vr_system` 的提供方，EMUI 框架在眼镜插入时把它拉起来 | 普通应用不能向 servicemanager 注册，也没有框架去 bind 它 |
| `t0/a.smali`（ServiceConnector）：收到 `Message.what = 0x3e9`，取 bundle key `system_service_binder`，`a3/a$a.K(IBinder)` | 框架 bind 桌面服务 → 通过 Messenger 把「系统服务 binder」交给桌面 | 没有框架来 bind、也没有 binder 可给 |
| `a3/a$a$a.smali`：descriptor `com.huawei.vrservice.ISysServiceInterface`，事务码 1=`h(int,List)`、2=`v(int,List)`、3=`A(int,List)`、4=`r(int,List)`、5=`H(int,List)` | 桌面回查系统的 5 个方法 | 需要服务端实现 |
| `t0/c.smali`（VRWorkThread）状态机：`what=1 → C()/L()`（step 1）→ `what=0xf → O()/f()`（step 2）→ `what=0xf → O()/M()`（step 3，回调 `H(0x89a)`）→ `what=0x3eb → t()`（handle Helmet Up，state==4 时 `P(1)`）| 框架按硬件事件推进入口流程 | 没人发这些消息 |
| `t0/c.D()` 读 `Message.obj` (Integer) 的 `0x3ea` 分支 | 只可能同进程投递；**跨进程不能带非 Parcelable**，所以真正跨进程的是无负载的 `0x3eb` | —— |
| `class VRPromptActivity`（Runtime，`flag=animation/usbIsDetached/...`）| 定位丢失提示，不是「进入 VR」确认 | —— |

### 5.2 实现（只加系统侧，不改原应用流程）

新增 `shared/runtime-actor/java`（只编进 `com.huawei.hvrsdkserverapp`，构建脚本按包名选择）：

- `VrSystemActor`：`DisplayManager` 监听真实外接显示（`HUAWEIAV03`）→ 插入时 bind 桌面
  `com.huawei.client.vrservice.VRService` → 发 `0x3e9` 握手（bundle 带
  `system_service_binder`）→ 依次发 `0x1`、`0xf`、`0xf`、`0x3eb`。
- `SystemServiceBinder`：按原 descriptor 与事务码实现，`0x899`/`0x89a` 返回 true，
  其余按「不可用」返回中性值；不放行任何伪造的成功。
- `VrGlassWatchService` + `VrGlassBootReceiver`：EMUI 上由框架常驻监督，这里用
  前景服务 + 开机接收器承担（唯一新增组件，`patch_sdk_manifest.py` 记录在案）。

### 5.3 二进制 manifest（`com.huawei.hvrsdkserverapp`）

该包 apktool 全量解码会撞重复资源（`Multiple resources: spec=0x7f070009 string/Hvr_wifi`），
所以树里保留二进制 manifest（`apktool d -r`）。新增 `patches/axml_edit.py` 做同名最小改动
（可逐字节还原，已验证 round-trip 与原文一致），由 `patch_sdk_manifest.py` 使用：

1. 去掉 `android:sharedUserId="android.uid.system"`（普通应用拿不到平台签名）；
2. 补 `uses-permission`：`com.huawei.vrservice.CLIENT_SERVICE`、
   `com.huawei.android.permission.VR`、`...VR.DEVICE_MESSAGE`（EMUI 上靠系统 UID 天然持有）、
   `RECEIVE_BOOT_COMPLETED`；
3. 在 `<application>` 下补 `VrGlassBootReceiver` 与 `VrGlassWatchService`
   （第一次误挂到 `<manifest>` 下，PackageParser 会静默忽略，已修正）。

### 5.4 逐个真机卡点与同名实现

按真机 logcat 顺序，每个都是「平台原来给、通用安卓不给」，都用同名方式补：

| 现象（真机日志） | 原调用点 | 处理 |
|---|---|---|
| `SecurityException: startForeground … requires android.permission.FOREGROUND_SERVICE` | `VRService.onCreate` → `a()` → `startForeground` | 桌面 manifest 补同名权限声明 |
| `LinkageError: …UEventObserverEx.startObserving overrides final method` | `x0/j.smali` 继承 `UEventObserverEx` | 改成**组合**平台 observer，不再继承；存根同步改成 `final` 以便编译期拦住同类错误 |
| `RuntimeException: Unable to open socket for UEventObserver`（平台线程直接崩、进程被杀） | 同上 | 平台 uevent socket 对普通应用不可用（SELinux）。桌面只读 `DP_LINK_STATE` 一个字段，改为用真实外接显示连接状态生成同名 `UEvent`（`DEVPATH=/devices/virtual/dp/vr`），真机日志 `VROsMonitor: dp link good.` |
| `SecurityException: Permission denial, must have one of: [WRITE_SECURE_SETTINGS]` | `x0/a(Hw6dofMonitor)` → `q1/a.f` → `n1/f.t` 写 `Settings.Global` | 同名声明 `WRITE_SECURE_SETTINGS`（带 `development` 标志，可 `pm grant`） |
| `NoClassDefFoundError: com.huawei.systemmanager.notificationmanager.HwNotificationListenerEx` | `x0/i(VRNotificationMonitor)` 构造 | 兼容层补同名类，转发公开 API；不可用时记录并保持监视器存活（通知转发本身是可选能力） |
| `ClassNotFoundException: android.telephony.MSimTelephonyManager` | `w0/b.r(VRManager)` 查是否通话中 | 兼容层补同名类，映射公开 `TelephonyManager.getCallState()`；无 `READ_PHONE_STATE` 时记一次日志并返回 idle |
| `SecurityException: listen`（`enforceCarrierPrivilege`） | `l2/q.c` / `l2/l` 注册 `PhoneStateListener`，事件掩码 `0x920` | `0x800`（载波特权位）无法用任何权限获得，`patches/patch_phone_listener.py` 把掩码改为 `0x120`，保留 `0x100`/`0x20`（信号强度与通话状态）——来电/摘机逻辑不变，去掉的只有载波专属细节 |
| `Background activity launch blocked! … VRPrepareActivity … BAL_BLOCK` | 桌面 `VRService` 自动拉起准备页 | 补同名 `SYSTEM_ALERT_WINDOW` 声明 + `appops set … SYSTEM_ALERT_WINDOW allow`（平台为此提供的豁免），准备页随即正常显示 |
| `READ_PHONE_STATE` 被离线补丁当作「在线伴生权限」摘掉 | `w0/b.r` 读通话状态 | **恢复声明**：它是本地能力，不是联网能力；摘掉等于丢原功能。见 5.5 |

### 5.5 与既有离线补丁的偏差（需用户确认）

`patch_offline.py` 的 `ONLINE_PERMISSIONS` 里含 `android.permission.READ_PHONE_STATE`，
但原版用它在进入 VR 前判断是否正在通话（`w0.b.r(VRManager)` →
`MSimTelephonyManager.getCallState`）。这是本地能力，`patch_platform_permissions.py`
已把它加回桌面的声明并授予。除此之外的离线策略不变。

### 5.6 真机进展（本轮实测）

`插入眼镜 → 桌面 VRService 启动 → 握手成功 → step 1/2/3 → VRPrepareActivity 显示 →
MainActivity（Unity VR 空间）启动` 已全部跑通，证据：

```
I VrSystemActor: refresh(start) displays=[0:内置屏幕 8:HUAWEIAV03] helmet=true
I VRService_Client_ServiceConnector: system service to client service connect success.
I VRService_Client_VRWorkThread: vrEnvPrepare step 1, startLocalPrepareLocked
I VRService_Client_VROsMonitor: dp link good.
I VRService_Client_VRManager: startPrepareActivity
I ActivityTaskManager: START u0 {cmp=…activity.VRPrepareActivity}
I UnityPlugin: HVR_SetInitVariables() / HVR_UpdateTexture / SinglePassTimeWarpEvent 1
topResumedActivity=ActivityRecord{u0 com.huawei.vrlauncherx/.MainActivity}
```

### 5.7 仍未完成（不得写成通过）

- **眼镜端还没有画面**：Unity 空间已跑起来，眼镜 display 上目前是黑屏。缺的是 EMUI 让
  「另一侧」把渲染结果送到 DP 面板的那条路——`VrSystemClient.init` 里的
  `getSystemService("vr_display")` → `android.vr.IVrServiceManager`
  （`startFrontBufferDisplay`/`stopFrontBufferDisplay`/`getVsync` 等）。按既定决策它只留接口、
  返回「不可用」，调用方走它自己的失败分支，因此没有输出。补它属于用户明确推迟的
  「异步投屏/输出」范围。
- **MainActivity ANR**：`Input dispatching timed out … FocusEvent(hasFocus=false)`，
  与上面没有输出路径同时出现，需要在上面的输出路径补齐后一起复核。
- **头部跟踪**：`HVR_Android_GetHelmetInfo failed`（已知，接口保留）。
- **手柄**：`Unity_HVRController: Right controller is not available`，CF20 尚未在这个
  新框架下接通（旧仓有协议样本，可在本轮框架里按同一原则补）。

## 六、手柄原生库与华为内核节点（2026-09-15 第二轮真机）

主线跑到空间之后，手柄与控制器链路是两个独立缺口，本轮都定位到根因并修掉其一。

### 6.1 手柄原生库：不是 ABI 问题，是 Android 11+ 包可见性

现象：`com.huawei.vrhandle:VRHandleService` 反复崩溃

```
E vrhandle_VrPoseJni: load library error
java.lang.UnsatisfiedLinkError: No implementation found for void
    com.huawei.vrhandle.VrPoseJni.helmetPoseStart()
  at com.huawei.vrhandle.service.VRHandleService.e3(VRHandleService.java:23)
```

排查证据（`tools/native-audit.py`、`tools/so-deps.py`）：

- 关卡不支持 32 位是错的：`ro.product.cpu.abilist = arm64-v8a,armeabi-v7a,armeabi`。
- `VrPoseJni` 的 `<clinit>` 用 `System.load` 绝对路径加载
  `libMobileSensor.so / libWalleAlg.so / libWalleDev.so / libvrpose.so`，路径来自
  `r0.y0.j0()` = `createPackageContext("com.huawei.hvrsdkserverapp", 3)`
  `.getApplicationInfo().nativeLibraryDir` —— 即**从 Runtime 包里取库**。
- 这四个库手柄 APK 里没有，但 Runtime APK 里有（`armeabi-v7a` 29 个），
  依赖闭包只有系统库 + 这三个同族库，可满足。
- 真机日志给出真正原因：路径退化成空串
  `D nativeloader: Load /libMobileSensor.so ... dlopen failed: not found`
  → `VrHandleApplication.c()` 正常，但 `createPackageContext` 抛了
  NameNotFoundException（`j0()` 的 catch 分支把路径置空）。

根因：**Android 11+ 包可见性**。手柄 manifest 既没有 `<queries>` 也没有
`QUERY_ALL_PACKAGES`，看不到 Runtime 包。

处理（同名补平台声明，不动任何应用逻辑）：`patch_platform_permissions.py` 为六个包
补上各自引用到的兄弟包 `<queries>`（Runtime 是二进制 manifest，由
`patch_sdk_manifest.py` 的 `insert_before` 补）。

修复后真机证据：

```
D nativeloader: Load .../com.huawei.hvrsdkserverapp-.../lib/arm/libvrpose.so ... ok
I vrhandle_VrPoseJni: load libMobileSensor/libWalleAlg/libWalleDev/libvrpose success
I HelmetPose: HelmetPose.cpp:Java_com_huawei_vrhandle_VrPoseJni_helmetPoseStart(134): helmetPoseStart
I vrhandle_VrSdkApi: getUsedDeviceList, mDeviceInfoList size = 1
```

手柄服务不再崩溃，原生姿态模块按原实现启动。

### 6.2 华为内核节点 `/dev/hwvr1`：眼镜在位判定

控制器链路仍然失败：

```
W PhoneController: vr glass not exist, no need to bind service
W VrControllerManager: bind VrTouchService failed
```

`VrSystemClient.isVRGlassExist()`、`VrMonitor.isVRGlassDevExist()`、
`VrTouchService.isVRGlassExist()` 三个方法都用
`new File("/dev/hwvr1").exists()` 判断眼镜在位——那是华为内核驱动建的节点。

处理（`patches/patch_vr_glass_probe.py`）：三个方法的方法名/签名/调用方全部不动，
只把「探华为私有节点」这一步换成
`com.huawei.vrframework.compat.VrPlatformCompat.isVrGlassPresent()`，
用本项目已经在用的两个真实信号回答同一问题：外接显示 `HUAWEIAV03`
（EDID 名）与 USB `12d1:1092`。眼镜拔掉时两个信号同时消失，返回值与节点消失一致，
不伪造状态。

修复后真机证据：

```
I VrPlatformCompat: glass probe: display=true usb=true
I PhoneController: bind VrTouchService enter
I VrControllerManager: Try to connect controller PhoneController
I DefaultController: onServiceConnected : ComponentInfo{com.huawei.vrhandle/com.huawei.vrhandle.service.VRHandleService}
```

控制器子系统不再提前放弃，开始真正连接。

### 6.3 仍未接通：CF20 的 GATT 通道

控制器管理器现在停在「等第三方控制器」：

```
I VrControllerManager: ThirdPartyCtrl is connecting
I VrControllerManager: Current device status is 0
```

蓝牙侧证据（`dumpsys bluetooth_manager`）：CF20 已配对（`HUAWEI CF20_902F`，LE），
但 GATT 通道已关闭，且应用侧记录为反复 `REASON_UNREGISTER_CLIENT`：

```
stack::gatt  ... 01:14:15.948 xx:..:90:2f, BT_TRANSPORT_LE, state: GATT_CH_CLOSE,
             ACL holders gatt_if: com.huawei.vrhandle (56)
AppRecord<... com.huawei.vrhandle, transport: LE, reason: REASON_UNREGISTER_CLIENT>
```

即控制器链路的下一环是**让手柄应用与 CF20 重新建立并保持 GATT 连接**，
然后 `ThirdPartyController` 才会进入 connected。旧仓有 CF20 协议样本与跨模块客户端代码，
按同一原则在当前框架里补（不改手柄应用逻辑）。

### 6.4 本轮新增工具（可复现）

| 工具 | 用途 |
|---|---|
| `tools/native-audit.py` | 逐包列出 `native` 方法与 `System.load/LoadLibrary` 的库，对照 APK 自带库 |
| `tools/so-deps.py` | 解析 ELF `DT_NEEDED`，给出某个 .so 的依赖闭包（判断缺哪个库） |
| `patches/axml_edit.py` | 二进制 AXML 读写：删属性、加权限、加组件、加 `<queries>`，round-trip 逐字节一致 |
| `tools/smali-dump.py` | 打印某个 smali 方法体（去 `.line`），便于按调用点核对 |

## 七、控制器链路（2026-09-15 第三轮真机）

### 7.1 ANR 的真正原因：手柄服务崩溃的连带结果

`/data/anr/anr_2026-09-15-02-04-07-762`（**修复前**）里 VR 空间主线程：

```
native: __ioctl -> IPCThreadState::transact -> BinderProxy.transact
  at com.huawei.vrhandle.IVRHandleServiceAidl$Stub$Proxy.setVRSDKValue(IVRHandleServiceAidl.java:497)
  at com.huawei.vrframework.DefaultController.setValue(DefaultController.java:287)
  at com.huawei.vrframework.VrControllerManager.helmetPoseStart(VrControllerManager.java:137)
  at com.huawei.vrframework.DefaultController.onServiceConnected(DefaultController.java:371)
```

主线程在 `onServiceConnected` 里同步调用手柄服务的 `setVRSDKValue`，而此时手柄服务正
因为 `VrPoseJni` 缺库反复崩溃 → binder 调用挂住 >10s → ANR → VR 空间被系统回收
（`Process com.huawei.vrlauncherx has died: cch+5 CEM`）。第 6.1 节修好原生库之后，
`/data/anr/` 不再产生新文件，`ANR in` 事件为 0（70 秒完整跑机验证）。

### 7.2 控制器管理器死锁：未初始化的第三方控制器报「connecting」

完整 60 秒日志（`run1.log`，832k 行）里一分钟内出现 **11625 次**
`ThirdPartyController: getStatus() = 0`，并且：

```
I DefaultController: onServiceConnected : ComponentInfo{com.huawei.vrhandle/
    com.huawei.vrhandle.service.VRHandleService}     <- CF20 的控制器已连上
I VrControllerManager: ThirdPartyCtrl is connecting   <- 却一直等第三方控制器
E Unity_HVRController: Right controller is not available in Update
```

`VrControllerManager.init()` 只在环境报告有华为 6DoF 套装或 Nolo 时才初始化第三方控制器：

```java
if (VrFramework.isHW6DoFCtrlAvailable() || VrFramework.isNoloAvailable()) {
    mThirdPartyCtrl.init(activity);
}
```

本机两者都没有 → `ThirdPartyController.initVrController()` 从未执行 → 它的 `mStatus`
保持 Java 默认值 0，而 `checkConnecting()` 把 0 当作「正在连接」，且**第一个**就问它，
于是直接 return，永远轮不到已经连上的 `DefaultController`。

处理（`patches/patch_thirdparty_controller.py`）：按该类自己的约定（`initVrController()`
失败时就是 `mStatus = -1`），让未初始化的控制器也返回 -1 = 不可用，管理器继续往下走。
不改任何连接判断，也不伪造连接状态。

修复后真机（`run2.log`，75 秒完整抓取）：

```
I VrControllerManager: Default controller init succeed
I DefaultController: onServiceConnected : ComponentInfo{com.huawei.vrhandle/...VRHandleService}
I DefaultController: onServiceConnected registerDeviceStateCallBack
I VrControllerManager: onStatusChanged sender DefaultController, status -6, index 0
I VrControllerManager: Try to connect controller PhoneController
E VrControllerManager: No valid controller          <- 真实状态，不再是假「connecting」
```

`ThirdPartyCtrl is connecting` 与 `getStatus() = 0` 完全消失。

### 7.3 仍未接通：CF20 的扫描被华为 nearbysdk 挡住

手柄自己的重连/扫描链：

```
I vrhandle_VrHandleReconnectController: bindVrReconnectService / service success
I vrhandle_VrHandleReconnectController: sendRemoteMessage, msgId = 1
I vrhandle_VrHandleReconnectService: init                     <- 桌面托管端
W vrhandle_VrHandleReconnectController: service not init finish, cannot notify scan
```

桌面托管的 `com.huawei.vrhandle.VrHandleReconnectService` 把工作交给 `Ls1/b`
（NearbyScanManager），而它的 init 是：

```java
mClientMessenger = messenger;
NearbyAdapter.createInstance(context, mAdapterCallback);   // com.huawei.nearbysdk
```

即扫描/重连依赖**华为专有 nearbysdk**。当前兼容层按既定决策只保接口
（`createInstance` 记录回调但不产生任何回调），所以「init finish」永远不会到来，
手柄也就永远不触发扫描。

需要的 nearbysdk 面很小（`docs/PLATFORM_API_SURFACE.txt`）：

| 成员 | 用途 |
|---|---|
| `NearbyAdapter.createInstance(Context, NearbyAdapterCallback)` / `releaseInstance()` | 建立/释放适配器 |
| `NearbyAdapter.subscribeDevice(CloseRangeDeviceFilter, CloseRangeDeviceListener)Z` / `unSubscribeDevice(filter)Z` | 订阅/退订近场设备 |
| `CloseRangeBusinessType.iConnect` | 业务类型（本工程只用 iConnect） |
| `CloseRangeDeviceFilter.buildFilter(businessType, String)` | 过滤条件 |

下一步实现方向：用通用 Android BLE（`BluetoothLeScanner` + `BluetoothGatt`）实现同一套
签名，把 CF20 的广播/连接交给标准 BLE 栈，回调交给原调用方——即把这一层华为专有实现
替换为通用实现，应用逻辑不动。

## 八、「华为 VR 手柄屡次停止运行」的根因与修复（2026-09-15 第四轮真机）

### 8.1 现象与堆栈

系统弹出「华为 VR 手柄屡次停止运行」，手柄服务反复重启。开机至今的完整 logcat 里
只有两条 FATAL，都是它：

```
Process: com.huawei.vrhandle:VRHandleService, PID: 27821
Unable to start service com.huawei.vrhandle.service.VRHandleService
    with Intent { act=com.huawei.vrservice.ACTION_RECONNECT_MSG ... }
Caused by: android.app.ForegroundServiceStartNotAllowedException:
    Service.startForeground() not allowed due to mAllowStartForeground false
  at android.app.Service.startForeground(Service.java:775)
  at com.huawei.vrhandle.service.VRHandleService.b3(VRHandleService.java:44)
  at com.huawei.vrhandle.service.VRHandleService.c3(VRHandleService.java:22)
  at com.huawei.vrhandle.service.VRHandleService.p1(VRHandleService.java:57)
  at com.huawei.vrhandle.service.VRHandleService.n1(VRHandleService.java:94)
  at com.huawei.vrhandle.service.VRHandleService.onStartCommand(VRHandleService.java:5)
```

这一条**与原生库无关**：同一次开机日志里
`vrhandle_VrPoseJni: load libMobileSensor/libWalleAlg/libWalleDev/libvrpose success`
且 `UnsatisfiedLinkError` 为 0。第 6.1 节的包可见性修复仍然有效。

### 8.2 语义

桌面 VRService 在**后台**用 `ACTION_RECONNECT_MSG` 拉起手柄服务；手柄
`onStartCommand` 立刻 `startForeground()`。Android 12+ 默认禁止后台启动前台服务，
只有拿到豁免才允许：

- EMUI 9（Android 9）时代没有这条限制 —— 属于纯粹的新系统版本不兼容；
- 失败时 AMS 把 `mAllowStartForeground` 记为 false，`startForeground()` 抛异常，
  AMS 随后重启该服务，于是形成崩溃循环，系统显示「屡次停止运行」。

### 8.3 可复现条件与 A/B 证据

用平台自身的手段制造受限状态（把两个包压到 restricted 待机桶），可 100% 复现：

```powershell
am force-stop com.huawei.vrhandle / com.huawei.vrlauncherx / com.huawei.hvrsdkserverapp
am set-standby-bucket com.huawei.vrhandle restricted
am set-standby-bucket com.huawei.vrlauncherx restricted
am broadcast -n com.huawei.hvrsdkserverapp/.compat.VrGlassBootReceiver -a android.intent.action.BOOT_COMPLETED
```

| 条件 | `ForegroundServiceStartNotAllowedException` |
|---|---|
| 豁免关闭（`appops set … ignore`）+ 两包 restricted | **6 次**，服务反复重启 |
| 豁免开启（`appops set … allow`）+ 同样 restricted | **0 次**，服务存活 |

### 8.4 处理

平台对后台前台服务的豁免之一就是 `SYSTEM_ALERT_WINDOW`；但该 appop 只有在 manifest
声明了对应权限之后才可设置（手柄包原本没有声明，所以 `appops set` 一直是 `default`）。

- `patches/patch_platform_permissions.py` 给 `com.huawei.vrhandle` 补
  `android.permission.SYSTEM_ALERT_WINDOW`；
- `install-six.ps1`（本轮新增）负责安装六个包并补齐所有必须由 shell/Shizuku/root 给的
  授权：`WRITE_SETTINGS`、`SYSTEM_ALERT_WINDOW`、`WRITE_SECURE_SETTINGS`、
  `READ_PHONE_STATE`，以及三个长驻组件的 deviceidle 白名单。

修复后真机：

```
appops get com.huawei.vrhandle SYSTEM_ALERT_WINDOW
  -> SYSTEM_ALERT_WINDOW: allow
ps -A | grep vrhandle:VRHandleService
  -> 存活；logcat 中 ForegroundServiceStartNotAllowedException 计数 0
```

### 8.5 顺带发现（待处理）

`install-six.ps1` 校验时发现 `com.huawei.himovie.vr` 的 `WRITE_SETTINGS` 仍是
`default`：设备上装的是 00:30 构建的视频包，早于该权限补丁。需要用当前补丁重建视频包
后才能生效（不影响本轮手柄结论）。

## 九、手柄在原空间里被识别为控制器（2026-09-15 第五轮真机）

### 9.1 原版的连接触发点（逐条从 smali 读出）

手柄真正的连接动作是 `r1/x.e0()`（→ `t0/l8.y0(地址)` + `u2(true)` → `t0/s5$c` 里的
`BluetoothDevice.connectGatt(ctx, false, callback, 2)`，标准 Android BLE）。
它的调用者只有三处：

| 触发 | 原调用点 | 说明 |
|---|---|---|
| `what=4` | `r1/x$c.handleMessage` | 桌面托管的 `VrHandleReconnectService` 说「设备在附近」 |
| 绑定失败回退 | `VRHandleService.p1()` 里的 `if (!h)` | `h` = 绑定桌面重连服务是否成功 |
| iConnect 重连 | `VRHandleService.m1()`，由 `com.huawei.iconnect.ACTION_RECONNECT_MSG` 触发 | EMUI 上由 `com.huawei.iconnect` 系统应用发出 |

桌面侧协议（`VrHandleReconnectService$a` + `s1/b`）：手柄发 `what=1`（带 replyTo）→
桌面 `NearbyAdapter.createInstance` → 适配器就绪后回 `what=2`；手柄发 `what=3`
（+`deviceAddress`）→ 桌面订阅近场 → 命中后回 `what=4`。

关键点：**`p1()` 在绑定成功（`h=true`）时不会直接连**，只请求桌面去扫描；这条链完全
依赖华为专有的近场服务（nearbysdk）。该服务在这台机器上不存在，所以手柄有时要靠其它
路径、等好几分钟才连上。早前尝试用通用 BLE 扫描顶替这一层，已按用户意见全部撤回，
代码里没有残留。

### 9.2 补上「iConnect」这一职责（用原版自己的入口）

`VRHandleService` 的服务声明里本来就写了这个 action：

```
<service android:name="com.huawei.vrhandle.service.VRHandleService" android:exported="true">
    <intent-filter>
        <action android:name="com.huawei.vrhandle.service.vrdeviceservice"/>
        <action android:name="com.huawei.iconnect.ACTION_RECONNECT_MSG"/>
        <action android:name="com.huawei.vrservice.ACTION_RECONNECT_MSG"/>
```

因此 `shared/runtime-actor` 的 `VrSystemActor` 在眼镜插入后，按 3/8/15/25 秒四次向
`com.huawei.vrhandle/.service.VRHandleService` 发送原版的
`com.huawei.iconnect.ACTION_RECONNECT_MSG`。这不是新协议，而是把 EMUI 上
`com.huawei.iconnect` 那个系统应用的职责搬到我们的系统侧 actor；手柄若已连上，
`m1()` 会自己返回「device is already connected」，重复请求无副作用。

实测时间关系：09:41:15 发 intent → 09:41:16.44 手柄 `connected to gatt server`，1.4 秒。

### 9.3 主线结果（无需人工干预的一轮）

```
09:44:48.138 vrhandle: processDeviceStateChange, deviceState = 1
09:44:49.894 vrhandle_VrDeviceService: connected to gatt server
09:44:51.173 vrhandle_VrDeviceService: mIsNotificationSet = true
09:44:51.185 vrhandle: processDeviceStateChange, deviceState = 2
09:44:52.784 VrControllerManager: onStatusChanged sender DefaultController, status 5
09:44:56.108 Unity_HVRController: Start HVRRightController
09:44:56.109 Unity_HVRController: RRIGHT controller is available in GetControllerHandle
09:44:56.111 Unity_HVRController: mControllerType: Controller3DOF
topResumedActivity = com.huawei.vrlauncherx/.MainActivity
```

同一缓冲区内 `Right controller is not available` 由修复前的 1402 次降到 0，
`Fail to GetPosture` 0 次。

### 9.4 仍未完成

- **按键/触控板的实际操作**需要人手按一次才算验收；本轮只证到「控制器被识别为
  3DoF 可用」。
- 桌面侧那套华为近场扫描（nearbysdk）仍只有接口：本轮没有用它，手柄靠原版
  `ACTION_RECONNECT_MSG` 加上我们补的 iConnect 请求连接。是否还需要近场这一层，
  等按键实测稳定后再定。
- 眼镜端画面仍为黑屏（`vr_display` 前缓冲输出未实现，见 5.7）。

### 9.5 手柄链路会掉线，需要「常驻式」重连（10:05 实测）

单次开局请求不够。真机一次完整会话里 CF20 链路每隔约 11 秒掉一次：

```
10:05:42 / 10:05:53 / 10:06:04 / 10:06:15 vrhandle_VrDeviceService: disconnected from gatt server
10:06:15 vrhandle: processDeviceStateChange, deviceState = 4
         （手柄自身只重试一次，随后 "not retry connect" 放弃）
```

EMUI 上 iConnect 是常驻服务，掉了会继续拉；手柄自己的近场路径又不可用，所以没有外部
请求时控制器会一直缺失。`VrSystemActor` 因此改为**眼镜在位期间每 20 秒**发一次原版
`com.huawei.iconnect.ACTION_RECONNECT_MSG`（眼镜拔掉即停止）。手柄已连上时 `m1()`
会自己返回「device is already connected」，代价可忽略。

修复后的恢复循环（同一次会话）：

```
10:06:27.706 vrhandle: processDeviceStateChange, deviceState = 1     ← 周期请求拉起
10:06:29.002 vrhandle_VrDeviceService: connected to gatt server
10:06:30.125 vrhandle: processDeviceStateChange, deviceState = 2
10:06:30.129 VrControllerManager: onStatusChanged sender DefaultController, status 5
10:06:30.183 Unity_HVRController: RightController is available in Update.
```

注意：CF20 本身掉线的频率（本次约 11 秒一次）是硬件/射频/固件层面的现象，两个应用抢
同一条 BLE 连接时会更糟（`dumpsys bluetooth_manager` 里该设备同时挂着
`com.vrremote.controller` 与 `com.huawei.vrhandle`）。移植层能做到的是不让它「一掉就
永久失去控制器」；经验稳定度需要实测，必要时先只保留一个占用连接的客户端。

## 十、工程性问题（2026-09-15 第六轮）

### 10.1 构建脚本在重定向时崩溃

`build-all.ps1` 把子脚本输出重定向到文件时会报
`GroupStartData ... is not valid or not in the correct sequence`：`build-module.ps1`
用了 `Get-FileHash | Format-List`，输出的是格式化对象而不是文本。已改成输出
`SHA256=<hex>` 纯文本，`build-all.ps1` 用 `Out-String` 收尾。修好后六个包一次构建成功：

```
com.huawei.hvrsdkserverapp / vrhandle / vrvirtualscreen / himovie.vr / vrlauncherx / appmarket.vr  -> r14
```

### 10.2 设备上主应用无法覆盖安装

这台设备上 `com.huawei.appmarket.vr` 覆盖安装必失败：

```
INSTALL_FAILED_UPDATE_INCOMPATIBLE: Package com.huawei.appmarket.vr upgrade keys do not match
```

排查结论（都有实测）：

- 把设备上**正在安装的那份 APK 原样拉出来再覆盖安装**，同样失败；
- 新包与已装包的签名证书、scheme（v2+v3）、versionCode、manifest（无 sharedUserId）
  逐项一致；
- `pm list packages -u` 显示该包处于 `installed=false`（已卸载但被记住）；
- 完整卸载（`cmd package uninstall`，不带 `-k`）后**全新安装成功**；用 `-k` 保留数据的
  卸载则会留下半残记录，仍然装不进去；
- 该机装有 HMA（`cn.smart.tool`，LSPosed 日志显示它在 system_server 内 hook
  PackageManager）等模块，PMS 的签名判定不可全信。

因此 `install-six.ps1` 增加了兜底：覆盖装失败且错误为
`INSTALL_FAILED_UPDATE_INCOMPATIBLE` 时，改为「完整卸载 → 重新安装」，并明确提示该包
本地数据会丢失。其它五个包在该设备上覆盖装正常。

## 十一、眼镜显示这条路：先纠正三个错误假设（2026-09-15 第七轮）

### 11.1 `vr_display` 的真实语义：前缓冲路由，不是「把纹理交给服务」

`android.vr.IVrServiceManager`（服务名常量 `VR_MANAGER = "vr_display"`）的全部成员是：

```
startFrontBufferDisplay()Z      stopFrontBufferDisplay()Z      getVsync()D
setSchedFifo(II)I               setVrPlatPerf(II)I             releaseVrPlatPerf()I
getAvailableFreqLevels()[I
```

**没有任何传纹理/传 Surface 的方法**。也就是说 EMUI 上不是「应用把画面交给一个服务」，
而是框架打开前缓冲显示模式后，由显示硬件把该应用的前缓冲扫出到眼镜面板。调用点只有
`VrSystemClient.startFrontBufferDisplay/stopFrontBufferDisplay` 与
`VrFramework$VrDisplay$ChoreographerVsync.getVsync`。这解释了为什么手机屏在 VR 模式
下是暗的：应用只有一个前缓冲，被路由到眼镜。

### 11.2 眼镜 display 不能承载 task（推翻了「把空间移到眼镜上」的想法）

```
DisplayInfo{"HUAWEIAV03", displayId 6, ... type EXTERNAL, FLAG_PRESENTATION, ..., canHostTasks false}
```

- `canHostTasks=false`：**不能把 task 移过去**。实测：
  - `am start --display 6` → `SecurityException ... with launchDisplayId=6`（**用 root 也一样被拒**）；
  - `cmd activity display move-stack <taskId> <id>` → `Unknown displayId`（旧 id 还会变）。
- `FLAG_PRESENTATION` 存在 → 官方支持的路径是 **Presentation**（在那块屏上显示一个窗口），
  这也是 `android:flags` 里 `FLAG_PRESENTATION` 的含义。
- **display id 是动态的**：同一台机器先后出现过 5 / 6 / 8；actor 与 `VrPlatformCompat`
  都按 EDID 名 `HUAWEIAV03` 查找，不能写死 id。

### 11.3 截图在这台机器上不可信（重要）

- `screencap -d <SurfaceFlinger 的 64 位 token>` 与 `-d <逻辑 id>` **都不被接受**；
  两次调用返回的是同一张纯黑 3200x1600（23842 字节），即实际抓的是「第一个 display」。
- 用 root 抓也是同一张黑图。
- 该层带 `handleSkipScreenshotFlag:true`，属于被标记为不参与截图的图层。

结论：**不能再用截图判断眼镜/手机是否有画面**，必须依赖现场肉眼或外接录像设备。
（此前把黑截图当作「没有画面」的判断已作废。）

### 11.4 真正观察到的事实：内容已经在往眼镜送，缺的是几何

`dumpsys SurfaceFlinger` 显示 VR 空间的层**有缓冲、在持续出帧，并且被镜像到眼镜那路**：

```
Layer [1459 mirrored from 736,] SurfaceView[com.huawei.vrlauncherx/...MainActivity]@0(BLAST)#1459
  visible reason= buffer=88381837017090 frame=12229 contentDirty
  bounds={139,0,1600,3200} toDisplayTransform={ tx=139.0000 ty=0.0000 }
  outputFilter{layerstack:6, toInternalDisplay:false, skipScreenshot:false}   ← layerstack 6 = HUAWEIAV03
```

即：Samsung 的外部显示镜像本来就把该层送到了眼镜（layerstack 6），同一条镜像也在
scrcpy 的虚拟屏（layerstack 7）上。**缺的不是「输出通道」，而是几何**：
层的 bounds 是 1600x3200（竖屏），眼镜面板是 3200x1600（横屏），并且带 139px 偏移。
另外 `dumpsys window` 记录到 09:25 有一条 `wm user-rotation lock 0`（锁竖屏）。

下一步方向（按原版语义）：让 VR 空间**全屏横屏、按面板 3200x1600 渲染**，也就是
EMUI 上「VR 模式强制横屏 + 前缓冲直出」的等价物；在此之前先用肉眼确认当前眼镜上到底
显示的是什么，再决定是修几何还是修输出链路。

### 11.5 已实现：眼镜在位时强制横屏（EMUI 的「VR 模式」等价物）

`VrSystemActor` 在眼镜插入时写 `Settings.System`：

```
ACCELEROMETER_ROTATION = 0
USER_ROTATION          = Surface.ROTATION_90
```

眼镜拔掉时把自动旋转恢复。Runtime 的二进制 manifest 因此补了
`android.permission.WRITE_SETTINGS`（走 `patch_sdk_manifest.py`，文本脚本处理不了这棵
树），`install-six.ps1` 同步补 appop。

真机证据：

```
10:39:09 VrSystemActor: display locked to landscape for the VR session
之后 settings: accelerometer_rotation=0  user_rotation=1
      dumpsys window displays: cur=2640x1080 app=2640x1080        ← 由竖屏变横屏
      SurfaceFlinger 眼镜那路镜像: scale 1.2121 tx=113.9 ty=145   ← 2640*1.2121 = 3200
```

同一轮里手柄也自动连上、控制器可用：

```
10:39:15 vrhandle_VrDeviceService: connected to gatt server
10:39:16 vrhandle: processDeviceStateChange, deviceState = 2
10:39:17 VrControllerManager: onStatusChanged sender DefaultController, status 5
10:39:20 Unity_HVRController: mControllerType: Controller3DOF
```

### 11.6 仍需现场确认

SurfaceFlinger 的 bounds 数字不足以判断「眼镜里看起来对不对」（它给的是合成用矩形，
而且这台机器抓不到屏）。需要人眼确认三件事：眼镜里是否有画面、方向/比例是否正确、
双眼是否重叠正确。若仍有问题，下一步按原版 `vr_display` 的语义处理「前缓冲直出」，
而不是继续调镜像参数。

---

## 12. 头盔设备通道：/dev/hwvr1 与 libWalleDev 私有 ioctl

### 12.1 原调用点

`com.huawei.hvrsdkserverapp` 的 `lib/armeabi-v7a/libWalleDev.so`（`WalleCommon` 类）
在 `openDev()` 里打开 EMUI 内核驱动创建的节点 `/dev/hwvr1`，然后用一串
driver-private ioctl 取设备信息：

| 函数 | vaddr | ioctl | 作用 |
| --- | --- | --- | --- |
| `ioGetVendorInfo` | `0xece0` | `0xC0044807` | 读 VID/PID 写入 `mVendor` |
| `ioGetVersionInfo` | `0xff64` | `0xC03E4807` | 读 62 字节版本结构到 `this+0xa1a8` |
| `ioGetOffsetInfo` | `0x106ac` | `0xC0104807` | 读 16 字节显示偏移到 `this+0xe8` |
| `ioActiveDev` | `0xeecc` | `0xC0054806` | 激活数据通道 |

通用内核没有这个驱动，所以 `openDev()` 每次都失败；`DeviceServer` 线程以约 10ms
周期重试（真机实测该线程 CPU 58%），接近传感器 / IMU / 按键的数据通道全断，
桌面状态机停在「眼镜未就绪」。

### 12.2 替代实现

`patches/patch_walledev.py` 在 `.text` 内按 vaddr 改写入参，读路径（`read()` 拿 HID
原始帧）不动：

- 厂商号：直接写入真实硬件身份 `VID 0x12d1 | PID 0x1092`（线缆上的 CV10），走原成功分支
- 版本：直线代码填 62 字节结构（hw `1.0.0` / sw `3.0.300`），返回 0
- 偏移：写 16 字节零偏移，返回 0
- 激活：直接返回 0

脚本对每个站点断言原始字节，反编译树变化即报错停止。

### 12.3 设备节点：KSU 模块 `ksu/hwvr_compat/`

`/dev/hwvr1` 本身由模块 `service.sh` 重建：按 `HID_NAME` 匹配 `HUAWEI GLASS CV10`
（节点号插拔会变，不能写死），用相同 major:minor `mknod`，`chmod 666`，
并打标签 `u:object_r:null_device:s0`。

选 `null_device` 是有依据的，不是绕过：通用策略本来就允许应用打开该标签的字符
设备（`/dev/null` 就是），标签只作用在我们自己新建的这个 inode 上，不改动任何
系统 SELinux 策略，也**不需要宽容模式**。实测被否掉的方案：

| 标签 / 手段 | 结果 |
| --- | --- |
| `hidraw_device` | `avc denied { read }`（Enforcing） |
| `vendor_hidraw_device` | `avc denied { read }` |
| `app_data_file` | `avc denied { read }`（策略不允许应用打开数据目录里的字符设备） |
| `ksud sepolicy apply/patch` | 静默无效（对垃圾语句同样返回 0），不能作为运行时方案 |
| `null_device` | 通过 |

真机证据（SELinux `Enforcing`）：

```
14:26:36 I DevHid: openDevice success, fd=110, vendorId=4817, productId=4242
14:26:41 I DevHid: dev_open: use helmet 1.0
14:26:41 I DevHid: parseGlassSwVersion: SwVersion Major(3), Minor(0), Patch(300)
14:26:53 I VRRenderWalleImpl: DBG INFO: fps0: 29.3, fps1: 29.3, fps2: 53.5
14:26:41 I Unity_HVRController: RRIGHT controller is available
14:26:41 I Unity_HVRController: mControllerType: Controller3DOF
```

### 12.4 未完成

- 模块的**开机自启**尚未验证（运行时装机 + 手工触发已验证）。需要一次重启确认
  `service.sh` 被 KernelSU 在 `late_start` 阶段拉起、节点自动出现。
- 眼镜拔插时节点会随之增删，脚本每 2 秒轮询；热插拔的长时稳定性待观察。
---

## 13. 更正：libWalleDev 不需要改，之前那版补丁是改错了层

第 12 节记录的做法（在 `libWalleDev.so` 里把厂商号/版本/偏移换成常量、
把激活调用改成直接返回成功）**已全部撤销**。它是错的，原因不是数值猜得
准不准，而是**改错了层**。

### 13.1 原厂对照：这些"私有 ioctl"其实是标准 HID 调用

从 EMUI9 工程固件
（`Huawei_Mate_20_X_EVR-AL00B_..._EMUI9.0.0_05022LPM_HMT`）解出内核后确认，
`/dev/hwvr1` 由内核 HID 驱动 `hid_vr` 创建（源码路径
`drivers/hid/hid_vr.c`，是 hidraw 的一个分支，注册 `hwvr%d` 字符设备），
另有 `hwvrdfu` misc 设备负责从 `hwvr.img` 升级固件。

`/dev/hwvr1` 对使用者就是**普通 hidraw 节点**。应用发的四个命令与
`hidraw.h` 完全对应，没有一个是华为私有的：

| 应用发出的命令 | 标准定义 | 用途 |
| --- | --- | --- |
| `0xC0044807` | `HIDIOCGFEATURE(4)` | 厂商号 |
| `0xC03E4807` | `HIDIOCGFEATURE(62)` | 版本 |
| `0xC0104807` | `HIDIOCGFEATURE(16)` | 显示偏移 |
| `0xC0054806` | `HIDIOCSFEATURE(5)` | 激活数据流 |

（`_IOC(dir, 'H', nr, size)`：nr=0x07 取特性报告、nr=0x06 写特性报告，
size 就是载荷长度。`hidraw.h` 里 `HIDIOCGFEATURE(len)` 就是这个形状。）

原固件里的另外两处印证：

- `system/bin/ueventd.rc`（或等价文件）：
  `# huawei vr deivces` → `/dev/hwvr0 0664 root system`、`/dev/hwvr1 0664 root system`
- `vendor/lib*/hw/sensors.default.so` 直接 `open("/dev/hwvr1")`，用
  `HW_IOCTL_GLASS_GET_VER` 读版本，并把节点上的流式记录解析成接近/心跳等
  传感器事件——同样把它当普通 hidraw 用。

VR 显示那侧对应关系也一并记下（供后续阶段参考，与本节无关）：
AOSP `android.hardware.vr@1.0-service` → `android.hardware.vr@1.0-impl.so`
→ `vr.kirin980.so`（`vr_init`/`vr_set_vr_mode`）→ HIDL
`vendor.huawei.hardware.hivrar@1.0/1.1`；另有 Kirin 面板库
`hivr.kirin980.so`（`hivr_device_open`/`hivr_set_vr_mode`/
`hivr_set_low_persistence`/`hivr_set_auto_refresh`/`hivr_get_vsync_timestamp`），
这些才是真正与麒麟显示控制器绑定的部分。

### 13.2 真正要修的只有"节点指向哪个接口"

眼镜枚举出三个 HID 接口：

| 节点 | HID_ID | HID_NAME | 对特性报告的反应 |
| --- | --- | --- | --- |
| hidraw0 | `12d1:1092` | HUAWEI HUAWEI GLASS CV10 | STALL（EPIPE） |
| hidraw1/2 | `12d1:107e` | HUAWEI HUAWEI GLASS HID | 正常应答 |

原厂 `/dev/hwvr1` 对应的是**控制接口**（107e）。之前把它指到 CV10 接口，
所以才一直 `ioGetVendorInfo failed`。指向正确接口后**原版库一行不改**即可：

```
15:08:12 I DevHid: openDevice success, fd=110, vendorId=4817, productId=4222
15:08:12 I DevHid: IoGetHallidayVersionInfo: halliday version: hwVer = CV10AC, swVer = 10.0.1.357
15:08:12 I DevHid: ioActiveDev: active device(2) OK
15:08:17 I DevHid: dev_open: use helmet 2.0
15:08:22 I wallex : receive imu data count(10055), invalid data count(0) in one(10.000818) second
           Unity_HwVrLauncherX_RecenterBase: Proximity is away to near, recenter ready canvas.
           Unity_HVRController: mControllerType: Controller3DOF
```

对照我编造的常量（`hw 1.0.0` / `sw 3.0.300` / VID 0x1092 / PID 0x1092）：
真机是 `hwVer CV10AC`、`swVer 10.0.1.357`、`productId 4222(0x107E)`，头盔
协议版本也因此从 `use helmet 1.0` 变成 **2.0**——假数据会让 SDK 走错分支。

### 13.3 一次错误的"验证"记录在案

第 12 节之后我曾用 `git checkout -- <so>` 做"还原后重测"，但当时 HEAD
里存的就是打过补丁的 `.so`（提交 8ab9bc52），所以那次"原版验证"其实跑
的仍是补丁版，结论无效。以 `原包/com.huawei.hvrsdkserverapp.apk` 里的
原始 `.so` 逐字节还原后重测，才是 13.2 的结果。教训：验证"原版"必须
以原包为基准做哈希比对，不能以工作区或 HEAD 为基准。

### 13.4 模块改为按协议探测选接口

`ksu/hwvr_compat/` 不再按设备名/厂商号匹配，改由 `hwvr-probe` 对每个
hidraw 节点发一次真实的厂商号查询（`HIDIOCGFEATURE(4)`，首字节 1），
谁以 4 字节应答谁就是控制接口；探测不可用时才退回按 `HID_NAME` 含
`GLASS HID` 匹配。因此换任何 VR 设备都适用，不含任何写死的厂商号。

节点标签沿用 `null_device`（见第 12 节），SELinux 保持 Enforcing，系统策略无改动。

### 13.5 生效验证（软重启）

本机只能用软重启（临时 root），实测 **KernelSU 的模块脚本在软重启后同样会
被拉起**，不需要真重启。验证方式：先删掉 `/dev/hwvr1` 并确认不存在，再软重启，
节点自动重现且脚本进程在跑。

软重启后的完整链路（全程 SELinux `Enforcing`，原版库未做任何修改）：

```
15:16:59 DevHid : DeviceMgrImpl start glass
15:16:59 DevHid : openDevice success, fd=110, vendorId=4817, productId=4222
15:16:59 DevHid : IoGetHallidayVersionInfo: hwVer = CV10AC, swVer = 10.0.1.357
15:16:59 DevHid : ioActiveDev: active device(2) OK
15:17:04 DevHid : dev_open: use helmet 2.0
15:17:05 Unity_HVRController: mControllerType: Controller3DOF
15:17:05 Unity_HwVrLauncherX_RecenterBase: Proximity is away to near, recenter ready canvas.
15:17:24 wallex : receive imu data count(9999), invalid data count(0) in one(10.000438) second
15:17:59 VRRenderWalleImpl: DBG INFO: fps0: 29.2, fps1: 29.2, fps2: 60.4
          dumpsys display: HUAWEIAV03 在位
```

遗留：`hidraw3`（`2109:8888`）与本链路无关，是别的外设。

---

## 14. 姿态链路为什么一直没起来：MyService 没声明

症状：日志每帧刷
```
E VrHelmetExt: mVRDeviceExt is null
I Unity_HVRController: Fail to GetPosture. Throw Controller out.
```
画面跟着头动、手柄无姿态。`VrHelmetExt.mVRDeviceExt` 始终为 `null`。

### 14.1 查到的链路

1. `VrHelmetExt.init(Activity)` 会 `mVRDeviceExt = VrInteractiveDeviceManager.getInstance()`，
   并在 `mActivity` 上调用 `init`。该方法进入时打 "init" 日志；日志里**完全没
   出现过**——`init()` 从未被调用。
2. `VrHelmetExt` 唯一被 Java 侧引用的是 `LibUpdate.loadLibInFullApp()`，它会
   `loadClass("com.huawei.vrframework.VrHelmetExt")` 然后通过 JNI 调 `callParentSetClass`
   把 4 个 vrframework 类（VrFramework / VrSystemClient / VrControllerManager / VrHelmetExt）
   交给原生层。
3. `MyService.onCreate()` 起一个 Thread 调 `startNative()`，原生层再做 `VrHelmetExt.init`。
4. `MyService.startNative()` 是 `libHVRSDKServerApp.so` 的 JNI 方法。
5. `aapt2 dump xmltree` 检 `com.huawei.hvrsdkserverapp` 的 `AndroidManifest.xml`，**没有
   `<service android:name=".MyService"/>`**——`MyService` 类在 dex 里存在，但 manifest
   没声明，OS 永远不会启动它。
6. `ArvrRuntimeService` 倒是声明了（在 `com.huawei.hvrsdkserverapp.service.ArvrRuntimeService` 进程里
   跑），但它只 `loadLibrary("c++", "arvr_slam", "ctrl3dof", "hivrar_fd", "VR6Dof",
   "runtime_service_module")`，**没加载** `libHVRSDKServerApp.so`，也没碰 `LibUpdate`、
   `VrHelmetExt`。

所以 `LibUpdate.loadLibInFullApp()` 永远不会被调用，`VrHelmetExt.init()` 永远不会被触发，
`mVRDeviceExt` 一直是 `null`。

### 14.2 结论

这一版 APK 的源码层面，**头盔初始化路径不通**——不管我方在系统侧做什么（节点指向、
SELinux、KSU 模块），只要应用自己不在合适的时点调用 `init()`，姿态链就起不来。
这是应用的"系统层不兼容"的一部分，但必须由应用自己补。

### 14.3 候选修复

按 `docs/PORTING_METHOD.md` 的原则，**优先"只动指向、不改代码"**——不切。

按四步法**查原厂**："EMUI 的内核驱动为 VR Glass 建 /dev/hwvr1"，对应到这一层就是
"EMUI 系统替它启动 MyService"。原厂固件的内核模块 `hid_vr` 与应用 init 路径没有直接
对应。

所以必须由应用自己补。要做的是让 `MyService` 真正跑起来：最干净的做法是在 manifest
里加 `<service android:name=".MyService"/>`，并保证 `libHVRSDKServerApp.so` 的依赖能
load（其中 `HVRSDKServerApp` 自己的 ABI 与依赖在 APK 里都有）。

也可绕过 `MyService` 直接调 `LibUpdate.loadLibInFullApp(context)` 一次，但 lib 加载
仍然要解决。

### 14.4 待做

- 把 `MyService` 加进 manifest，并在合适时机启动（推荐 `BOOT_COMPLETED`，
  或由 `VrSystemActor` 通知）。
- 校验 `libHVRSDKServerApp.so` 的依赖：ABI、链接的 `libc++_shared.so`、
  `libipcclient.so` 等。
- 重启验证：日志里出现 `VrHelmetExt: init` / `VrHelmetExt: deinit` 等字样；IMU 姿态
  从常量 0 变成随头部转动而变化；`Fail to GetPosture` 不再每帧刷。

按 PORTING_METHOD.md，这本来属于"补 EMUI 那一层"的范畴，但 EMUI 这一层是
`MyService` 自动被系统拉起——通用安卓没有这个机制，只能由应用自己声明。

### 14.5 关于发热

把手机逻辑尺寸设到 1600x3200（与面板 1:1）后，Unity 在手机上每帧渲染 3200x1600 像素，
再镜像到面板——手机 GPU 做了约 2.2 倍（1080x2640→3200x1600）的额外负载，机器温度明显
上升。这是为了"比例正确"的权宜代价。

根治还是回到"应用直接画到面板"的异步路径（按 PORTING_METHOD.md 的 8.节列在"未做"
清单里），可以彻底避免手机侧多刷一份。短期可以靠降低刷新率 / 限制 fps 缓解，
但本质是镜像路径的副作用。


---

## 15. 姿态初始化的完整门控链（第 14 节的续，结论修正）

第 14 节说"这一版 APK 源码层面头盔初始化路径不通"，**不准确**。补齐 `MyService`
声明后按四步法重查，发现真正的关系是一条门控链，链路本身是通的，只是被门控挡住。

### 15.1 完整链

```
眼镜在位
  -> android.vrsystem.IVRSystemServiceManager.isVRMode() == true
  -> com.huawei.vrlab.HVRActivity.onCreate 不 finish，继续
  -> new LibUpdateClient(this).runUpdate()
       在**客户端进程内**加载 Runtime 的 classes.dex，
       反射调 com.huawei.hvr.LibUpdate.updateAndLoad()
  -> LibUpdate.loadLibInFullApp()
       loadClass VrFramework / VrSystemClient / VrControllerManager / VrHelmetExt，
       JNI callParentSetClass 把 4 个类交给原生层，
       再 loadLibrary ipcclient / vrsdk / vrunityplugin / WalleDev / MobileSensor /
       WalleAlg / ipcserver / HVRSDKServerApp
  -> VrHelmetExt.init(mActivity) 把 mVRDeviceExt 填上
  -> 姿态链路可用
```

`HVRActivity.onCreate` 原文：

```java
invoke-super UnityPlayerActivity->onCreate()
if (!isVrMode()) {
    Log.i("HVRActivity", "Not in VrMode. Then return!");
    finish();
    return;                     // <- 后面的 runUpdate 不执行
}
new LibUpdateClient(this).runUpdate();
```

`runUpdate()` 一定会打 "Run update 2.0 succeed" 或 "Run update fall back 1.0"
（`LibUpdateClient.smali` 1427–1442 行），日志里没有出现过这两句——说明之前
`runUpdate()` 根本没被调到，也就是当时 `isVRMode()` 返回了 false 或者插件
路径走了别的分支。

### 15.2 我方补的两处

| 缺口 | 原厂怎么给 | 通用安卓怎么做 | 落地位置 |
| --- | --- | --- | --- |
| `vr_system` 服务的 `isVRMode()` | EMUI 系统服务 | 已有桩实现，返回"眼镜在位"（真实外接显示 + USB） | `shared/java/android/vrsystem/VRSystemServiceManagerImpl.java` |
| Runtime 的 `MyService` 由谁拉起 | EMUI 系统自动拉起 | manifest 里声明 + 开机 receiver 顺带拉起 | `patches/patch_sdk_manifest.py`、`VrGlassBootReceiver.java` |

`MyService.onCreate()` 会起线程调 JNI `startNative()`，原生层再做 `VrHelmetExt.init`。
所以补它有意义：即使客户端的 `runUpdate()` 那条路哪天再断，服务端这条也能兜。

### 15.3 真机验证（部分）

眼镜未插时：

```
I UnityPlayerActivity: Not in VrMode. Then return!
I HVRActivity: Not in VrMode. Then return!
I UnityPlayerActivity: onDestroy: Not in VrMode. Then return!
```

门控生效、行为与原文一致（这是"眼镜不在位就结束"的原语义，不是缺陷）。

眼镜未插时 `runUpdate()` 不执行、`MyService` 仍能由 boot receiver 拉起，
`libHVRSDKServerApp.so` 与 `libipcserver.so` 已在该进程 maps 里。

### 15.4 待验证

插回眼镜后确认：

1. 日志出现 `LibUpdateCall: Run update ...`；
2. 进程 maps 里出现 `libWalleDev.so` / `libWalleAlg.so` / `libMobileSensor.so` 等；
3. 日志出现 `VrHelmetExt: init`，且 `mVRDeviceExt is null` 消失；
4. `Fail to GetPosture` 不再每帧刷，Unity 相机姿态随头部变化。

### 15.5 附带

`ksu/hwvr_compat/service.sh` 增加"眼镜在位时把手机逻辑尺寸对齐面板 2:1
（`wm size 1600x3200`），拔除时 `wm size reset`"，省掉每次手敲。
依据见 `docs/evidence/README.md`（三组尺寸对照）。


---

## 16. 姿态链打通（真机验证，第 14/15 节收口）

上一轮补了 `MyService` 声明与 boot receiver 之后，插回眼镜实测，整条链走通。

### 16.1 实测日志（眼镜在位）

```
I HwVrLauncherX_MainActivity: onCreate
I HvrVrSystem: glass present=true                 <- 我方 vr_system 桩，按真实外接显示判定
I UnityPlayerActivity: HVRActivity find Context Constructor
W LibUpdateCall: App is 32 bit
I LibUpdateCall: loadRemoteClass in
I LibUpdateServer: Lib dir : .../lib/arm
I VrMonitor: init and set activity
I LibUpdateServer: Load libc++.so succeed
   ... libhivrar_fd / libipcclient / libvrsdk / libvrunityplugin / libvrunitypluginExt /
       libWalleDev / libMobileSensor / libWalleAlg / libipcserver / libHVRSDKServerApp /
       libarvr_slam / libctrl3dof / libc++_shared / libhiai* / libhcl / libminddata-lite /
       libmindspore-lite / libhiai_hcl_model_runtime / libhiai / libVR6Dof / libyuv /
       libruntime_service_module 逐个 succeed
I HvrFramework: SetClass HVR_FRAMEWORK_CLASS_INDEX
I HvrFramework: SetClass HVR_SYSTEM_CLIENT_CLASS_INDEX
I HvrFramework: SetClass HVR_CONTROLLER_CLASS_INDEX
I HvrFramework: SetClass HVR_HELMET_EXT_CLASS_INDEX
I VrHelmetExt: getInstanceObject
I HvrHelmetExt: [HvrHelmetExt.cpp:Setup] OUT
I LibUpdateCall: Run update 2.0 succeed
I HVRActivity ... -> MainActivity 继续，Unity 空间起
```

结论：**姿态初始化链是通的**，原版逻辑没有被破坏。

### 16.2 关键观测：姿态本来就在工作

之前一直盯错了接口。真机现在的两类日志：

```
UnityPlugin: [UnityPlugin.cpp:HVR_GetSensorState](1013):
    Unity posture time: 16738686450, wxyz: 0.028356, 0.001138, -0.043512, 0.998650
UnityPlugin: [UnityPlugin.cpp:HVR_GetCameraPositionOrientation](1107):
    Unity position xyz: 0.000000, 0.000000, -0.000000
```

- `HVR_GetSensorState` 是**头部姿态四元数**，时间戳持续推进、四元数有效 → 3DoF 头姿在工作。
- `HVR_GetCameraPositionOrientation` 是**位置**，恒为 0 是 3DoF 的正确行为（无位置跟踪），
  不是缺陷。

`Fail to GetPosture` 每帧刷的现象也消失了：`logcat | grep -c 'Fail to GetPosture'` = **0**。

### 16.3 `mVRDeviceExt is null` 的定性：应用自身逻辑，不是移植缺陷

`VrHelmetExt.isEnable()` 的分支：

```
if (mVRDeviceExt == null) {
    if (VrFramework.isHW6DoFHeaderAvailable()) { helmetMod = HW6DOF_MOD; }
    else if (VrFramework.isNoloAvailable())     { helmetMod = NOLO_MOD; }
    else { return false; }        // 两个都 false 就在这里返回，不赋值
    mVRDeviceExt = VrInteractiveDeviceManager.getInstance();
    mVRDeviceExt.init(mActivity);
}
```

`isHW6DoFHeaderAvailable()` → `VrParamsRequester.isHW6DoFAvailable(0)`，它要求
`ArvrRuntimeInternalInterface.getCurrentDevices()` 返回**恰好 3 个设备**。

- 6DoF 头显/手柄在 `VrInteractiveDeviceManager` 里是按**设备名**识别的：
  `HUAWEI USB HELMET` / `HUAWEI VISUAL CONTROLLER LEFT` / `RIGHT`。
- 本机眼镜是 `HUAWEI GLASS CV10`（3DoF），不属于这组；`isNoloAvailable()` 也是 false。
- 厂商固件里搜不到 `hvrsdk/externaldevice`、`HUAWEI USB HELMET`、`HUAWEI VISUAL
  CONTROLLER`（system.img / vendor.img 均 0 命中），说明 6DoF 那套要第三方 App 提供，
  EMUI 本身不带。

所以对 3DoF 眼镜，`mVRDeviceExt` 为 null 是**应用的既有分支行为**：它本来就不为 3DoF
建这个对象，3DoF 头姿也不经过它（`VrHelmetExt.mHmdDataExt` 这个 `float[7]` 在 Java 侧
只被读、不被写，由原生层填）。

结论：这条 `E VrHelmetExt: mVRDeviceExt is null` 属于**噪声日志**，不阻塞 3DoF 主线。
台账不再把它当阻塞项。

### 16.4 眼镜画面（原版桌面主界面）

`docs/evidence/2026-09-15-glass-launcher-home-pose-ok.png`（3200x1600，直接抓眼镜那一路）：

- 环境（天空、山、树、蓝色结构）完整渲染；
- 原版帮助卡片"手机指向前方并长按主页键 / 可将视角及投射屏幕中置"显示；
- 双眼各自占面板一半，圆角与畸变正常。

仍待确认：卡片上的文字看起来是竖排的，而环境是正的。需要肉眼确认这是原版设计
（卡片在 3D 里带角度）还是贴图朝向问题；眼镜内观感只能真人判断。

### 16.5 待验证

- 头转动时四元数是否跟随变化（把眼镜戴上转一下头，看 `HVR_GetSensorState` 的
  wxyz 是否连续变化）；
- 手柄按键在空间内是否生效（`Fail to GetPosture` 已归零，判据是按键有响应）；
- 断连/重连后这条链能否自动重走。


---

## 17. 为什么单独点图标进不去 VR 空间（这不是缺陷）

用户反馈：单独打开 `华为VR` 或 `华为VR桌面` 都进不去，只有插眼镜自动跳转才进得去。

### 17.1 结论：两个 App 其实都打开了，只是打开的是 2D 引导页

用 `aapt2 dump xmltree` 查两个原包的 `LAUNCHER` intent-filter 指向：

| 包 | 桌面图标指向的 Activity | 内容 |
| --- | --- | --- |
| `com.huawei.vrlauncherx` | `com.huawei.vrlauncherx.activity.Vr2dStartUpActivity` | "若要使用该应用，请连接华为 VR 眼镜"（含开放源代码许可、用户协议入口） |
| `com.huawei.appmarket.vr` | `com.huawei.hwmarket.vr.MainActivity` | "连接 VR 眼镜 / 请连接 VR 眼镜，享受身临其境的虚拟现实体验" |

真机实测（眼镜已在位）：

```
monkey -p com.huawei.vrlauncherx -c android.intent.category.LAUNCHER 1
-> topResumedActivity = com.huawei.vrlauncherx/.activity.Vr2dStartUpActivity
```

停在 `Vr2dStartUpActivity` 不动。

### 17.2 该页没有进入 VR 的代码路径

`Vr2dStartUpActivity.onCreate`：

```
if (q2.e.a(context)) { startActivity(PrivacyStatementActivity); return; }   // 未接受隐私声明
d();                                                                        // 否则只是铺页面
```

`d()` 只调 `i()` / `h()` / `j()`，三者都是 `findViewById` + `setText`（版本号、版权、
协议链接），没有任何 `startActivity` 指向 VR 空间。

也就是说：**这个 2D 页就是用来提示"请连接眼镜"的静态页**，它本身不负责进 VR。

`com.huawei.appmarket.vr` 的 `MainActivity` 继承
`com.huawei.hwmarket.vr.support.emui.permission.BasePermissionActivity`，同样有
`onFinish()` 直接 `finish()` 的路径——它是主应用的引导页，不是 VR 空间。

### 17.3 VR 空间是另一个 Activity

VR 空间是 `com.huawei.vrlauncherx.MainActivity`（Unity 活动，继承
`com.huawei.vrlab.HVRActivity`）。它由原版自动流程拉起：眼镜插入 → 引导/确认流程
→ `MainActivity`。这条链在移植版上是通的，实测：

```
am start -n com.huawei.vrlauncherx/.MainActivity
-> topResumedActivity = com.huawei.vrlauncherx/.MainActivity
   VRRenderWalleImpl: DBG INFO: fps0 29.3, fps1 29.0, fps2 51.4
   UnityPlugin: HVR_GetSensorState: posture time 17389525680,
                wxyz 0.043044, 0.001772, -0.042532, 0.998166
```

（同一轮里四元数较更早的 0.028356 有变化，说明姿态在实时更新。）

### 17.4 处置

按 `docs/PORTING_METHOD.md` 第 1 节"保留原交互流程"，**不做改动**：

- 不给 2D 引导页加"直接进 VR"的跳转（那是另造流程）；
- 不把桌面图标指向 `MainActivity`（那是改原版入口）；
- 保持原语义：图标进引导页、插眼镜走自动流程进 VR。

如果希望手动也能进 VR，正确做法是走原版的准备/确认流程（`VRPrepareActivity` 那条链），
而不是绕过引导页。这条链的补齐属于第 8 节"主应用 / 桌面"那一项。


---

## 18. 流程偏差：准备/确认链没跑，插入后是别的路径进的 VR

用户反馈："一插入直接进 VR，原版流程应该有准备/确认"，要求按原版。

### 18.1 原版流程（从代码读出）

```
com.huawei.vrlauncherx/com.huawei.client.vrservice.VRService.onCreate
  -> new t0.c   (source: VRWorkThread.java, tag "VRWorkThread")
  -> t0.c.L()   日志 "vrEnvPrepare step 1, startLocalPrepareLocked"
  -> w0.b.t(ctx)  日志 "start VR Adapte!"
       -> w0.b.C(ctx)  日志 "startPrepareActivity"
            -> startActivity(com.huawei.client.vrservice.activity.VRPrepareActivity)
  -> VRPrepareActivity 里再调 w0.b.A(ctx)（日志 "start 3D Launcher"）
       -> startActivity(com.huawei.vrlauncherx.MainActivity)   ← VR 空间
```

`w0.b.A()` 读两个系统属性决定 VR 入口，默认值就是 VR 空间：

```
persist.sys.hw_vr_pkg      默认 com.huawei.vrlauncherx     (实测未设置)
persist.sys.hw_vr_activity 默认 com.huawei.vrlauncherx.MainActivity (实测未设置)
```

### 18.2 真机事实：这条链没跑

- `logcat | grep VRWorkThread` = **0 条**（该 tag 是 `t0.c` 的日志 tag，不是消息内容；
  一开始按消息内容 grep 是错的，已更正口径）。
- 当前在跑的服务只有 `VrStateQueryService` 与 `ArvrRuntimeService`；
  **`com.huawei.client.vrservice.VRService` 没在运行**。

### 18.3 VRService 由谁启动：没找到

- `VRService` 在 manifest 里声明为 `exported=true`、
  `android:permission="com.huawei.vrservice.CLIENT_SERVICE"`、**没有 intent-filter**，
  只能按组件显式启动。
- 六个包的 smali 里搜 `Lcom/huawei/client/vrservice/VRService;` 与字符串
  `com.huawei.client.vrservice.VRService`：**除 `t0.c` 自己持有它的引用外，没有任何
  启动点**。持有 `CLIENT_SERVICE` 权限的是 Runtime，但 Runtime 侧也搜不到启动代码。
- 结论：启动它的应该是 EMUI 系统侧或另一个包，六个包内部找不到。

### 18.4 另一个缺口：第七个包 `com.huawei.vrservice`

真机日志：

```
W ActivityManager: Unable to start service Intent {
    cmp=com.huawei.vrservice/com.huawei.vrinstaller.service.VrParamsInitializeService
  } U=0: not found
W HwVrLauncherX_VrParamsInitializer: bind service fail.
    Is VRService support provide vr params = false
```

桌面要绑一个**独立包** `com.huawei.vrservice` 里的 `VrParamsInitializeService`。

- 厂商工程固件 `system.img` 的字符串表里有 `com.huawei.vrservice` 与 `com.huawei.vrinstaller`
  （各 7 / 4 处），但 `system.img` 的 56 个 APK、以及 `version.img`（factory cust）里
  **都没有对应的 APK**。
- 本地工作区也没有这两个包。

所以：**华为 VR 套件不止六个包**。至少还缺 `com.huawei.vrservice`
（提供 `VrParamsInitializeService`）与 `com.huawei.vrinstaller`。这两个包在零售 ROM 里，
不在手头的工程固件里。

### 18.5 当前可用的人工进入方式（记录，非方案）

VR 空间是 `com.huawei.vrlauncherx.MainActivity`，`exported=true`：

```
adb shell am start -n com.huawei.vrlauncherx/.MainActivity
```

或做一个指定组件的桌面快捷方式。**这不是移植方案**，只是眼下可用的人工入口；
按第 1 节口径，正式路径必须是原版准备/确认链。

### 18.6 待办（按优先级）

1. 找 `com.huawei.vrservice` / `com.huawei.vrinstaller` 两个包（零售 ROM 提取），
   它们很可能就是把 `VRService` 拉起来的那个"系统侧"。
2. 若拿不到那两个包，退一步：确认 `VRService` 在 EMUI 上是否由系统广播拉起，
   以及它的 `android:permission` 在实际调用链里是否真的被校验。
3. 在此之前不改任何原版入口，也不给引导页加跳转。


---

## 19. 手柄：控制器型号取值为空的那条链

用户反馈过"手柄按键不生效"。日志里有一条稳定的异常：

```
I VrControllerManager: Current Ctrl is getValue for prod_model And result is
```

`result is` 后面是空的。这条链查清了：

### 19.1 链路

```
launcher/VrControllerManager.getValue("prod_model")           (smali 2106-2143)
  -> mUsingCtrl.getValue(key)                                  IVrController
  -> DefaultController.getValue(key)                           (smali 1161)
       mService.getVRSDKValue(key)                             AIDL
  -> com.huawei.vrhandle/com.huawei.vrhandle.IVRHandleServiceAidl
       Stub.onTransact 事务 1 -> g.s(String)
  -> VRHandleService$e.s(String) -> VRHandleService.A0(...)
  -> VRHandleService.i1(String)                                (smali 5324)
       key 以 "helmetPose"/"phonePose" 开头 -> 走 VrPoseJni
       否则 -> Map VRHandleService.w.get(key)   ← 空
```

`w` 在 `<clinit>` 里被初始化为空 `HashMap`（容量 5），唯一的写入点是
`VRHandleService.Z2(int,String,String)`（AIDL 的 `setVRSDKValue`，事务 0xe）。
map 里没有 `prod_model`，所以返回 `""`，日志就是空。

### 19.2 谁负责填这个 map

`DefaultController.setValue(key,value)`（smali 1766）会用索引 0 调
`setVRSDKValue` 把值推进 vrhandle。但六个包里搜 `"prod_model"` 字面量，
**只有一处**：`com.huawei.hvrsdkserverapp/module/ArvrRuntimeModuleManager.getValue(int,String)`
（smali 6754），它对 `prod_model` 返回固定串 `"huawei 6dof"`；同一方法里
`turn_around` / `use_default_resetCenter` 返回 `"true"`。

而 `ArvrRuntimeModuleManager.getValue` 的调用方只有一个：
`com.huawei.hvrsdkserverapp/service/f.smali:1837`——那是 Runtime 提供给
`VrParamsRequester` 的 AIDL 实现。

也就是说：
- **Runtime 侧**能给出 `prod_model = "huawei 6dof"`（`service/f` → `ArvrRuntimeModuleManager`）；
- **launcher 侧**问的是 vrhandle（`DefaultController` → `IVRHandleServiceAidl`），
  而 vrhandle 的表里没有这个键。

两边接口不是同一条。原版在 EMUI 上这两条应该被某个环节接起来（把 Runtime 的值
`setVRSDKValue` 推进 vrhandle），六个包内部找不到这个调用点。

### 19.3 结论与下一步

- 已证实：`prod_model` 为空是因为 vrhandle 的 `VRHandleService.w` 没被写入。
- 未证实：这是否就是"按键不生效"的原因。`VrControllerManager` 另有
  `getProductModel()` 之类的路径，且按键事件是否依赖该值还没验证。
- 下一步（按优先级）：
  1. 先在真机上确认当前按键到底有没有响应（姿态链已通、`Fail to GetPosture` 已归零，
     基线比之前好，需重新测一次再判定）；
  2. 若确实不响应，再确认 `DefaultController` 绑定的到底是 vrhandle 还是别的组件，
     以及 `setVRSDKValue` 在 EMUI 上由谁发起；
  3. 不自行补一个"把值塞进去"的兼容实现——那属于伪造状态，先找到原厂调用点。

### 19.4 顺带确认的两件事

- CF20 的 GATT 连接在 45 秒观测窗口内**0 次掉线**（`disconnected from gatt server` 计数 0），
  早前那批 `status=147` 是瞬时的，不是持续故障。
- 已装但未运行的 `com.vrremote.controller` 不持有 GATT 连接，未与 vrhandle 抢设备。


---

## 20. 流程偏差的根因：缺的第七个包就是 VR 系统服务本体

第 18 节遗留的问题是"谁该启动 `VRService`"。这一轮查到底了。

### 20.1 关键发现：vr_system 的提供者就在桌面包里

`com.huawei.client.vrservice.VRService.onCreate`（smali 540-600）：

```
invoke-static {}, Lt0/b;->K()Lt0/b;                    // t0.b 单例
invoke-virtual {v1, p0}, Lt0/b;->L(Landroid/content/Context;)V
const-string v2, "vr_system"
invoke-static {v2, v1}, Lcom/huawei/android/os/ServiceManagerEx;->addService(...)V
```

而 `t0/b` 的类头是：

```
.class public Lt0/b;
.super Landroid/vrsystem/IVRSystemService$Stub;
.source "VRInterfaceService.java"
```

也就是说：**原版的 `vr_system` 服务实现（`IVRSystemService`）就在 `com.huawei.vrlauncherx`
包里**，由 `VRService.onCreate` 注册，不是别的东西。

我们之前用 `patches/patch_vr_system.py` 把每个 `getSystemService("vr_system")` 调用点
重定向到自写的 `android.vrsystem.VRSystemServiceManagerImpl`，等于**绕开了这条注册/连接链**。

### 20.2 准备流程的触发点

```
VRService.onCreate -> new t0.c (VRWorkThread)
  -> t0.a (ServiceConnector) 拿到 work handler
  -> 收到 Messenger 消息 what=0x3e9（"system service to client service connect success"）
  -> t0.a.g() 发 what=1
  -> t0.c.G(Message) :cond_7 -> t0.c.C()
  -> state=1 -> O() -> L()  "vrEnvPrepare step 1, startLocalPrepareLocked"
  -> w0.b.t() -> C() -> startActivity(VRPrepareActivity)
  -> VRPrepareActivity -> w0.b.A() -> MainActivity
```

`0x3e9` 在六个包的全部 smali 里**只有 `t0.a` 这一处比较用**，没有发送方。
发送方不在六个包里。

### 20.3 真机实验

手动拉起 `VRService`：

```
am start-service -n com.huawei.vrlauncherx/com.huawei.client.vrservice.VRService
```

结果：服务确实起来并做实事——

```
VRService_Client_Main: service onCreate
VRService_Client_Main: recordVrStartTime start.
VRService_Client_ServiceConnector: ServiceConnector construction
VRService_Client_VRUtils: start VrHandle service
VRService_Client_VRUtils: start with action = com.huawei.vrservice.ACTION_RECONNECT_MSG
VRService_Client_Main: savePhoneBrightness brightness : 16
```

但它**没有**走到 `vrEnvPrepare`——因为拿不到那条 `0x3e9` 消息。
实验后已停掉该服务并把手机亮度从 16 恢复为 128。

### 20.4 结论

**六个包不构成完整的华为 VR 环境。** 缺的那个包（`com.huawei.vrservice`，第 18 节已确认
它不在 `system.img` / `product.img` / `odm.img` / `version.img` 里，设备上也没有）
是 **VR 系统服务的服务端**：

- 它向客户端发 `0x3e9`，客户端这才开始走准备流程；
- 桌面还从它取 `com.huawei.vrinstaller.service.VrParamsInitializeService`。

没有它，"插入 → 准备/确认 → 进入空间"这条原版链无法成立。
这也解释了为什么现在的进入路径是别的样子：我们的 `getSystemService("vr_system")`
重定向让 `isVRMode()` 能返回真，从而**跳过了**原版的服务连接与准备环节。

### 20.5 待办

1. 拿到 `com.huawei.vrservice`（零售 ROM 提取）。这是恢复原流程的前提。
2. 拿到后要做的是：**撤回 `patch_vr_system.py` 的调用点重定向**，改由原版的
   `VRService`/`t0.b` 注册 `vr_system`，让 `ServiceManagerEx` 的注册/查找真正贯通
   （多进程可见，而不是现在的进程内 Map）。
3. 在此之前：保持现状（能进 VR 空间），不伪造准备页，也不把重定向改成"假的服务端"。


---

## 21. 缺失包提供的组件清单（第 20 节的补充）

把六个包里所有指向 `com.huawei.vrservice` 的绑定点找齐，一共两处在**桌面**、
一处在本节新增的 **Runtime** 侧：

| 绑定方 | 目标包 | 目标组件 | 真机结果 |
| --- | --- | --- | --- |
| `com.huawei.vrlauncherx` / `t2.a`（VrParamsInitializer） | `com.huawei.vrservice` | `com.huawei.vrinstaller.service.VrParamsInitializeService` | `not found` |
| `com.huawei.hvrsdkserverapp` / `VrParamsRequester` | `com.huawei.vrservice` | `com.huawei.vrinstaller.service.VrParamsProviderService` | 绑定失败 |
| `com.huawei.hvrsdkserverapp` / `VrParamsRequester` | `com.huawei.vrlauncherx` | `com.huawei.client.vrservice.VrStateQueryService` | 正常（这个包在） |

对照说明：Runtime 对桌面包的那条绑定是通的（`VrStateQueryService` 真机在跑），
只有指向 `com.huawei.vrservice` 的两条是失败的。所以问题精确定位在缺的那一个包，
不是我们的其它适配。

### 21.1 它与准备流程的关系

- `t2.a`（VrParamsInitializer）用 **Messenger** 跟
  `VrParamsInitializeService` 通信（`t2/a.smali` 里有 `messenger is null` 分支）。
- 桌面侧等待 `0x3e9` 的那一端是 `t0.a`（ServiceConnector），它同样基于 Messenger。
- `IVRSystemService` 接口里**没有**任何 Messenger 注册方法（只有
  `addVRListener` / `getHelmetBattery` 等），而 `a3.a`（`ISysServiceInterface`）
  在六个包里**只有 Stub 与 Proxy，没有实现类**。

三点合起来：**Messenger 协议的服务端在 `com.huawei.vrservice` 里**，
它发 `0x3e9` 之后，桌面的 `VRWorkThread` 才会走准备流程。

### 21.2 因此这是一个"缺件"型阻塞，不是适配缺陷

六个包内部：
- 客户端齐（`t0.a`、`t2.a`、`a3.a$Proxy`）；
- 服务端缺（`a3.a` 无实现、`0x3e9` 无发送方、两个组件名无宿主包）。

这不是我们改错了什么，是**六个包不构成完整环境**。

### 21.3 两条可选路径（需要用户决定）

**路径 A：拿到 `com.huawei.vrservice` 原包**（零售 ROM 提取）。
拿到后按原样安装即可，`VRService`/准备流程有极大概率直接跑通；
我方需要做的只是把 `patch_vr_system.py` 的调用点重定向撤回，改由原版注册。

**路径 B：由我们补一个同名包**。
注意这**不是**新增 compat 包名——`com.huawei.vrservice` 是华为原名，
符合"保留原包名"的口径。但实现要照抄协议（Messenger、
`0x3e9` + `system_service_binder`、`a3.a` 的 `H(int,List)` 等方法），
属于逆向重写一个系统服务，工作量和风险都明显大于路径 A。

按 `docs/PORTING_METHOD.md` 第 2 节第 4 步，优先"只改指向"，
所以**建议先走路径 A**；A 不可得再考虑 B。
在决定之前不动任何原版代码，也不伪造 `0x3e9`。


---

## 22. 缺件链的最后一环：谁绑定 VRService

第 20/21 节确认准备流程要等 `0x3e9`。这一轮把"谁发 `0x3e9`"钉死了。

### 22.1 VRService 是被"绑定"才活起来的

`com.huawei.client.vrservice.VRService`：

```
.method public onBind(Intent)IBinder
    读 Intent 的 Extras（SERVICE_IN_ERROR 等）
    ...
    iget-object p1, p0, VRService;->b:Lt0/a;
    invoke-virtual {p1}, Lt0/a;->c()Landroid/os/IBinder;    // 返回 t0.a 的 Messenger binder
```

`t0.a.c()` 是 `t0.a` 的 Messenger（`t0/a.smali:96-104` 返回 `b.getBinder()`），
而 `t0.a.g(Message)` 只在 `t0/a.smali:78`（它自己的 Handler `t0/a$b`）被调用。

也就是说：**`0x3e9` 只能从"绑定 VRService 并拿到 Messenger 的客户端"发过来。**

### 22.2 六个包里没有这个客户端

- `VRService` 声明为 `android:permission="com.huawei.vrservice.CLIENT_SERVICE"`，
  这个权限名只在**桌面的 manifest**里出现（它定义了这个权限），
  Runtime 的 manifest 里**没有**申请它（我先前记错了，已更正）。
- 六个包里搜 `client/vrservice/VRService` 与 `client.vrservice.VRService`：
  **除桌面自己引用之外，没有任何绑定方**。
- `a3.a`（`ISysServiceInterface`）在六个包里只有 `a3/a$a`（Stub）与 `a3/a$a$a`（Proxy），
  **没有实现类**。

### 22.3 结论（完整链）

```
缺件 com.huawei.vrservice
   ├─ 实现 ISysServiceInterface(a3.a)          <- 系统服务端
   ├─ 提供 VrParamsInitializeService / VrParamsProviderService
   └─ 绑定 com.huawei.vrlauncherx/.VRService（持 CLIENT_SERVICE 权限）
        -> VRService.onBind 返回 t0.a 的 Messenger
        -> 客户端回发 0x3e9 + system_service_binder
        -> t0.a.g() 发 what=1
        -> t0.c.G() :cond_7 -> C() -> state=1 -> L()
        -> "vrEnvPrepare step 1" -> VRPrepareActivity -> VR 空间
```

六个包里：客户端齐、服务端缺、触发方缺。这是**缺件**，不是适配错误。

### 22.4 给用户的精确定位（便于去原机提取）

需要的是 **`com.huawei.vrservice`** 这个包，它应当包含：

- 组件：`com.huawei.vrinstaller.service.VrParamsInitializeService`、
  `com.huawei.vrinstaller.service.VrParamsProviderService`
- 接口实现：`ISysServiceInterface`（混淆后为 `a3.a` 的实现类）
- 权限定义/持有：`com.huawei.vrservice.CLIENT_SERVICE`

在 EMUI 真机上通常位于 `/system/app` 或 `/system/priv-app` 下的某个目录里。
拿到这个 APK，路径 A 就能走通；届时我方要做的仍然是撤回
`patch_vr_system.py` 的调用点重定向，改由原版注册。

工作区侧已排查完的位置（均无此包）：工程固件的 `system.img`(56 APK) /
`vendor.img` / `product.img` / `odm.img` / `version.img` / `preload_avb.img`、
设备 `/data`、`/system`、`/product`、`/odm`、`/sdcard`、`/data/local/tmp`。

---

## 23. 官方文档取证：VR Engine 指南，以及两处被误判的「原版设计」（2026-09-15 第八轮）

本轮**没有改动任何原版代码**，只做取证与定性。目的是把「看到的异常」和
「原版就是这么设计的」分开，避免继续在错的方向上改。

### 23.1 取证来源

华为开发者联盟的 VR Engine 开发指南（属于 Graphics 文档集）：

<https://developer.huawei.com/consumer/cn/doc/graphics-Guides/introduction-0000001097358942>

已抓成本地快照：`docs/reference/vr-engine/`（35 页正文 + `INDEX.md`），
逐条与本次移植的对应关系写在 `docs/reference/vr-engine/00-索引与对移植的意义.md`。

这一套是华为给 VR 内容开发者的官方规范，我们的六个包就是照它开发的，
因此它对「原版行为」的证明力高于从 smali 反推。

### 23.2 第 17 节的措辞要修正：`Vr2dStartUpActivity` 不是缺陷

`12-Unity-2D界面提示设置.md` 原文写明：2D 提示界面由 `hvrprompt.aar` 提供，
触发方式是在自己的 2D Activity 里发一个

```java
new Intent().setPackage(getPackageName()).setAction("com.huawei.android.vr.PROMPT")
```

「就会弹出提示界面，**插入头盔后就能跳过 VrLauncher，直接启动应用自己的 VR Activity**」。

对照六个包的 manifest：

| 包 | 注册 `com.huawei.android.vr.PROMPT` | 注册 `com.huawei.android.vr.action.MAIN` |
| --- | --- | --- |
| `com.huawei.vrlauncherx` | ✔ `Vr2dStartUpActivity` | ✘ |
| `com.huawei.vrvirtualscreen` | ✔ `Vr2dStartUpActivity` | ✔ |
| `com.huawei.himovie.vr` | ✘ | ✔ |
| 其余三个 | ✘ | ✘ |

`Vr2dStartUpActivity` 同时挂 `LAUNCHER` 和 `PROMPT` 两个 intent-filter ——
点图标和收到 PROMPT 落到同一页，这正是官方语义。第 17 节把它描述成
「静态提示页、没有进 VR 的跳转」在**现象**上没错，但定性要收紧：

逐行确认该页自身确实不含跳转（`decode/com.huawei.vrlauncherx/smali/...
/Vr2dStartUpActivity.smali`，826 行）：`onCreate` 只做隐私页判断、读
`content://smart_provider/smartabilityset` 的 `knowledgePage`、填文案（`h()`/`i()`/`j()`）；
`onResume` 只调 `k()` 弹一个 AlertDialog；`onStop` 关掉它。全类没有
`startActivity` 到 `MainActivity` 的路径。它还读一个属性 `ro.vr.surport`
（华为自己的拼写）。

所以「插入后进 VR」这一跳由**系统侧**提供。这与第 20/22 节查到的缺件
`com.huawei.vrservice` 是同一条链 —— **不是桌面该自己做的事，也不是我们漏写的跳转**。

### 23.3 `<queries>` 与 targetSdk：实测结论（可以排除）

`09-Unity-AndroidManifest配置.md` 要求 Android 11（API 30+）在 manifest 下声明：

```xml
<queries>
  <package android:name="com.huawei.vrhandle" />
  <package android:name="com.huawei.hvrsdkserverapp" />
  <intent><action android:name="com.huawei.vrhandle.service.vrdeviceservice"/></intent>
</queries>
```

用 `aapt2 dump badging` 读**原包**得到：

| 包 | minSdk | targetSdk |
| --- | --- | --- |
| `com.huawei.appmarket.vr` | 26 | 29 |
| `com.huawei.vrlauncherx` | 26 | 29 |
| `com.huawei.himovie.vr` | 26 | 29 |
| `com.huawei.vrvirtualscreen` | 26 | 29 |
| `com.huawei.hvrsdkserverapp` | 26 | 26 |
| `com.huawei.vrhandle` | 26 | **31** |

包可见性过滤按**调用方自己的 targetSdk** 生效：只有 `com.huawei.vrhandle`（31）
受限，而它的 `<queries>` 已列了 `appmarket.vr / hvrsdkserverapp / vrlauncherx`。
另外 `com.huawei.vrhandle` 已带 Android 12 的 `BLUETOOTH_SCAN`
（`neverForLocation`）/ `BLUETOOTH_CONNECT` / `BLUETOOTH_ADVERTISE`，
旧的 `BLUETOOTH` / `BLUETOOTH_ADMIN` / `ACCESS_FINE_LOCATION` 都标了
`maxSdkVersion=30`。

**因此第 6.1 节那条「Android 11+ 包可见性」在原包里本来是被正确处理过的**，
不再作为待办。（六个原包没有一个把 `com.huawei.vrhandle.service.vrdeviceservice`
这个 `<intent>` 写进 `<queries>`；由于 `<package>` 已声明，按需再补即可，
不是当前阻塞。）

旁证两条：`com.huawei.vrhandle` 还声明了 `android.permission.INJECT_EVENTS`
（系统签名权限）和自定义权限 `com.huawei.vrservice.permission.VR` ——
后者的**定义方**正是缺件 `com.huawei.vrservice`，与第 20/22 节的结论一致。

### 23.4 手柄按键的**原始语义**（按键映射的权威依据）

`32-手柄使用指南.md` + `07-Unity-添加HUAWEI-VR手柄.md`：

| 区域 | 动作 | 原语义 |
| --- | --- | --- |
| 触控板上半区 | 点击 | 确定（规范明确「应用中不能出现注视点击」） |
| 触控板上半区 | 滑动 | 界面滑动 / 行走，走 SDK API 判断 |
| 正前方扳机 | 点击 | 确定 |
| 触控板左下 返回键 | 单击 | 由应用弹「是否退出」提示 |
| 触控板左下 返回键 | 长按 ≥3s | 进主界面（VRLauncher） |
| 触控板右下 圆圈键 | 单击 | 直接回主界面 |
| 触控板右下 圆圈键 | 长按 | **方向校准**：画面焦点方向当正前方，手柄指向当手柄正前方 |
| 下半区 音量键 | — | 系统保留调音量，应用不能自定义 |
| 主页键 Home | 单击 <1s | 进 VRLauncher 界面 |
| 主页键 Home | 长按 ≥1s | **视点重置** |
| Home + 扳机 | 同时按 <1s | 截图 |

要收紧的表述：第 7 节记的「不能把 Home 一律改成视角复位」方向对，
但精确语义是 **单击 Home = 回 VRLauncher，长按 Home = 视点重置**，
两个是不同按键事件，不能合并成一个动作。

另一条实现细节（原文）：手柄状态在 `HVRLayoutCore.cs` 的 `Update()` 里更新，
要让应用内所有取手柄状态的脚本每帧一致，需要开发者自己调脚本执行顺序。
这说明「同一帧不同模块看到的状态不一致」是原版的执行顺序问题，不是链路断。

### 23.5 渲染侧的硬约束（后续对画面时按这几条判）

- `HVRCamera` 默认渲染分辨率 **1080×1080**（每眼），`RenderResolutionScale` 默认 1。
- `SinglePass` 只在 Multiview 模式下勾；普通模式勾了「会出现显示问题」。
- `HVRExtCamera` 下挂 **LeftCamera / RightCamera** 两个相机，分别对应头盔左/右眼
  —— 左右眼方向、裁剪、深度的语义以这一对相机为准。
- Multiview 与单目渲染 `EnableMonocularDisplay(bool)` **互斥**；视频类建议单目。
- 分区渲染四档 `Off / LowQuality / MiddleQuality / HighQuality`；
  开启分区渲染时**不要**用 `HVRExtCamera`。
- SDK 暂不支持 Vulkan，用 GLES3，勾 Multithreaded Rendering。
- 导入 SDK 会自动加 `HVRUILayer` 与 `HVRVolumeUILayer` 两个 UI Layer，
  规范禁止应用在这两层上画东西、也禁止其他相机显示这两层。
  → 眼镜里顶部那条与内容不同步的横条，**先按这两个系统 UI 层排查**，
  不要先假设是我们的合成错误。
- 调试开关（原版自带，正式发布要去掉）：
  `<meta-data android:name="com.huawei.android.vr.sensor.mode" android:value="mobile"/>`
  可在不插头盔时看手机上的画面。

### 23.6 头盔控制通道：原厂系统侧对照已完成

新文件 `docs/HELMET_HID_PROTOCOL.md` 汇总了本轮的反汇编结果，要点：

- `libWalleDev.so`（`WalleCommon`）对 `/dev/hwvr1` 的全部命令都是
  `HIDIOCGFEATURE` / `HIDIOCSFEATURE`：
  厂商号 `GFEATURE(4)`@report1、Glass 版本 `GFEATURE(62)`@report2、
  Halliday 版本 `GFEATURE(80)`@report2、光学信息 `GFEATURE(48)`@report9、
  显示偏移 `GFEATURE(16)`@report9、激活 `SFEATURE(5)`@report5、去激活 @report6。
- `libvrinfo.so` 走的是同一套，只有 `GFEATURE(62)` 与 `GFEATURE(80)` 两处。
- **原厂系统侧**：EMUI 内核里的驱动模块名 `hwvr`、驱动名 `hid_vr`，
  残留 `ovr_*` / `ovr - hidraw` 前缀（自 Oculus hidraw 改来），
  自己创建 `/dev/hwvrN`，**不含任何协议逻辑**。sensors HAL
  （`sensors.default.so`）里有字面量 `/dev/hwvr1` + `VR device added/deleted/modified`。
- 系统侧 `android.hardware.vr@1.0-impl.so` / `vr.kirin980.so` / `hivr.kirin980.so`
  扫不到任何 HIDIOC 常量，它们是显示/调度那条链（`DSSDevice::setLcdMode` 之类）。

**判定**：所谓「华为私有驱动接口」= 标准 HID feature report 透传，没有私有内核 ABI。
我们补 `/dev/hwvr1` 就是在替换原厂系统侧**同一层**，原版库一行不用改。
通用性由「按协议应答挑接口」保证（`ksu/hwvr_compat/hwvr-probe.c`，不写死 VID/PID），
这一点要守住 —— 62/80/48/16 字节里的字段语义属于**设备**，不属于传输层，换设备换这一层。

### 23.7 本轮结论与待办

- 不改原版代码；第 23.2 / 23.4 / 23.5 节是判据，不是改动。
- 待办（按优先级）：
  1. 缺件 `com.huawei.vrservice` 仍是主线唯一硬阻塞（第 20/22 节，本轮无进展）。
  2. 眼镜顶部那条横条按 `HVRUILayer` / `HVRVolumeUILayer` 复查一次。
  3. 左右眼方向问题按 `HVRExtCamera` 的 LeftCamera/RightCamera 语义复查。
  4. 手柄按键事件按第 23.4 节的表逐条对（尤其 Home 单击 vs 长按）。

---

## 24. 缺件 `com.huawei.vrservice` 已从固件中提取入库（2026-09-15 第九轮）

本轮**没有改动任何原版代码、没有改任何补丁**，只做固件取证与工具补齐。

详细过程见新文件 `docs/FIRMWARE_HMA11_EMUI11.md`，要点：

- 用户提供两包固件。EMUI 11 全量包（HMA-AL00 11.0.0.155）按
  `UPDATE.APP → 稀疏 super.img(7.81GB) → LP 逻辑分区 → EROFS` 逐层解开；
  system / hw_product 都是 **EROFS + LZ4**，Windows 上的 7-Zip 不认。
- 为此写了 `tools/erofs/erofs-extract.py`：纯 Python，支持
  FLAT_PLAIN/INLINE 与 COMPRESSED_FULL/COMPACT + LZ4（含 EROFS 的 0padding
  语义与紧凑索引 4B/2B 打包），自带 LZ4 块解码，不依赖 python-lz4。
- 在 `hw_product` 的 `/region_comm/china/app/VRServiceX/VRServiceX.apk`
  提取到**第 20/22 节一直在找的第七个包**：

  ```
  包名 com.huawei.vrservice   版本 11.0.0.322   大小 3,042,010 字节
  label "Huawei VR Service"，附 lib/arm64-v8a/libvrservice.so
  ```

  它与第 20/22 节逐条推断完全对上：
  `com.huawei.vrinstaller.service.VrParamsInitializeService`、
  `VrParamsProviderService`、以及权限定义
  `com.huawei.vrservice.CLIENT_SERVICE` / `.permission.VR` / `.VRSystemApp`。
  另含 `VRPromptActivity` / `VRUserPromptActivity`（插入眼镜后的手机侧提示）
  与 `VRGlassUpgrade/Warning`、`VRUpgradePrompt` 等页面。

- 已入库：`原包/com.huawei.vrservice.apk`（含 sha256 由 BASELINE 口径核对）、
  `tools/erofs/erofs-extract.py`、`docs/reference/hma11-apk-inventory.txt`
  （system 248 + hw_product 137 个 APK 清单）。

**新增约束（不要忽略）**：该 APK 是**系统签名级**应用
（`huawei.android.permission.HW_SIGNATURE_OR_SYSTEM` + 自定义 signature 权限），
直接装到三星机器上不会以系统身份运行。因此它既是“缺件”，也是下一轮
“系统层替换”的对象——与另外六个包同一口径：**接口、包名、组件、流程不动，
只替换系统签名与平台依赖**。

**待办**

1. 决定走 A（把它作为第七个模块纳入移植，并撤回 `patch_vr_system.py` 的
   `vr_system` 重定向）还是 B（只作参照实现）。
2. LYA-AL00C（EMUI 9）那包尚未展开；它早于 VR Glass 上市，预期不含该组件。
3. 六个用户包与固件版本（EMUI 10/11 混版）的版本对齐核对。

---

## 25. 第七个模块 `com.huawei.vrservice` 纳入移植（A 方案，2026-09-15 第十轮）

用户选定 A：把 `com.huawei.vrservice` 当作第七个模块，按与另外六个包相同的口径移植
（保留原包名/组件/流程，替换系统签名与平台依赖），并收回 `vr_system` 上那层
「本地自答」。

### 25.1 本轮做完的事（已构建 + 静态核对）

| 项 | 状态 |
| --- | --- |
| 解码 `com.huawei.vrservice` | `apktool d -r`（资源表有重复项，无法全量解，与 Runtime 同因） |
| 二进制 manifest 补丁 | 新增 `patches/patch_vrservice_manifest.py`，可重复执行、会自检 |
| 构建 | `build-module.ps1 -Package com.huawei.vrservice` 通过，兼容层写入 `classes2.dex` |
| 静态核对 | 包名 `com.huawei.vrservice`；16 个原组件全在；11 条 uses-permission；**无 INTERNET** |
| 接入构建 | `build/build-all.ps1` 增加该模块（排在 Runtime 之后、被它驱动的模块之前） |
| 接入安装 | `install-six.ps1` 增加该包、补 `WRITE_SETTINGS` appop、加入 deviceidle 白名单 |

manifest 改动只有四处，且都属「换系统层」范畴：

1. 去掉 `android:sharedUserId="android.uid.system"`（平台签名，通用安卓给不了）；
2. 去掉纯在线权限 `INTERNET` / `ACCESS_NETWORK_STATE` / `ACCESS_WIFI_STATE` /
   `REQUEST_INSTALL_PACKAGES`；
3. 摘掉纯在线组件 `com.huawei.updatesdk.*` 的两个 Activity；
4. 补 `<queries>`（Android 11+ 要 bind 桌面的服务）与声明
   `com.huawei.vrservice.CLIENT_SERVICE`（见 25.4）。

保留不动：`VRPromptActivity` / `VRUserPromptActivity` / `VRGlassUpgradeActivity` /
`VRGlassWarningActivity` / `VRUpgradePromptActivity` / `VrSoLoadFailActivity` /
`VRService` / `VRSysAppRequestService` / `VrParamsInitializeService` /
`VrParamsProviderService` / `UsrReceiver` / `SharedPreferenceProvider` 等 16 个组件。

### 25.2 从原包读出的链路（这轮的关键证据）

**`com.huawei.vrservice` 才是 `vr_system` 的服务端。**

`com/huawei/vrservice/VRService.smali` 的 `onCreate`：

```
invoke-static {}, Lcom/huawei/vrservice/VRInterfaceService;->getInstance()...
const-string v2, "vr_system"
invoke-static {v2, v1}, Lcom/huawei/android/os/ServiceManagerEx;->addService(Ljava/lang/String;Landroid/os/IBinder;)V
```

而 `VRInterfaceService` 的类声明是：

```
.class Lcom/huawei/vrservice/VRInterfaceService;
.super Landroid/vrsystem/IVRSystemService$Stub;
```

**桌面包也在注册同名服务**：`com/huawei/client/vrservice/VRService.smali` 里同样有
`ServiceManagerEx.addService("vr_system", t0/b)`，而 `t0/b` 也
`.super Landroid/vrsystem/IVRSystemService$Stub`。EMUI 的平台注册表对同名
`addService` 只认先到的那个，所以实际生效的提供方是本模块。

**准备流程由一条 Messenger 消息触发。**
`ServiceConnector$VRClientConnection.onServiceConnected` 绑定客户端服务后发出：

```
Message{what=0x3e9, data={ "system_service_binder" -> ServiceConnector$SysServiceInterface }}
日志: "start vr prepare."
```

**接口分层**（这决定了兼容层该扮演谁）：

| 类型 | 形态 | 角色 |
| --- | --- | --- |
| `android.vrsystem.IVRSystemService` | AIDL（有 `$Stub` / `$Stub$Proxy`） | 服务端 binder，`vr_system` 注册的就是它 |
| `android.vrsystem.IVRListener` | AIDL | 回调 |
| `android.vrsystem.IVRSystemServiceManager` | **纯 Java 接口**（无 Stub） | `getSystemService("vr_system")` 返回的**客户端管理器**，内部包着远端代理 |

也就是说：EMUI 的 `getSystemService("vr_system")` 由框架构造一个「客户端管理器」，
它把带 `Context` 的方法转成对远端 `IVRSystemService` 的调用。
我们现在 `shared/java` 里的 `VRSystemServiceManagerImpl` 扮演的正是这个客户端管理器，
但它**自己回答了**状态（`isVRMode()` 直接返回 `helmetPresent`），于是绕过了原版状态机 ——
这就是第 18/20 节记的「一插入直接进 VR、准备/确认链没跑」的根因。

### 25.3 所以「收回重定向」的正确含义

不是把 `patch_vr_system.py` 删掉（通用安卓没有 `vr_system` 这个服务名，
那一处查找必须桥接），而是把桥接的**实现**换掉：

```
VRSystemServiceManagerImpl.get(context)
  ├─ 注册表里查到 vr_system 的 IVRSystemService  -> 返回「转发版」客户端管理器（原版状态机说话）
  └─ 查不到                                      -> 退回现在的本地实现（兜底）
```

**顺序约束（重要）**：必须先有「转发版」，再降级本地实现。现在六个包全靠本地实现
拿 `vr_system`，先删掉它们会彻底拿不到服务，比现在更糟。所以本轮**没有**动
`patch_vr_system.py`，而是把替换方案与依赖关系先钉死在这里。

### 25.4 本轮发现的第二个平台缺口：那个权限没人定义

桌面的 `com.huawei.client.vrservice.VRService` 是这样声明的：

```xml
<service android:exported="true"
         android:name="com.huawei.client.vrservice.VRService"
         android:permission="com.huawei.vrservice.CLIENT_SERVICE"
         android:process="com.huawei.vrservice"/>
```

`com.huawei.vrservice.CLIENT_SERVICE` 在 EMUI 上是**框架**定义的权限；通用安卓上
没有任何包定义它，而未定义的权限一律判定为拒绝 → 本模块去 bind 桌面那个服务会被
`SecurityException` 挡掉，准备流程根本起不来。

处理：让本模块（这个名字空间的拥有者）把它声明出来，`protectionLevel="signature"`。
七个模块同一签名，互相授予，名字与契约不变。已实测进 manifest：

```
permission: com.huawei.vrservice.CLIENT_SERVICE
permission: com.huawei.vrservice.permission.VR
permission: com.huawei.vrservice.VRSystemApp
```

### 25.5 还没做的（下一轮的清单）

1. **跨进程 `vr_system` 注册表**。现在的 `ServiceManagerEx` 是进程内 `HashMap`，
   本模块注册的 binder 别的进程看不到。通用安卓的等价机制还没实现
   （EMUI 是平台服务注册表）。这是「转发版」的前置条件。
2. **`VRSystemServiceManagerImpl` 改成转发**，本地实现降为兜底（见 25.3）。
3. **真机安装第七个包并走一遍主线**：插入眼镜 → 手机提示确认 → 准备流程 →
   原 VR 空间。第 18/22 节记的所有偏差都要在这条链跑通后重新核对。
4. 第 18/22 节里「缺件」相关结论标记为**已解除**，但主线状态仍为**未完成** ——
   缺件补上不等于流程跑通。

### 25.6 复现

```
python patches/patch_vrservice_manifest.py
.\build\build-module.ps1 -Package com.huawei.vrservice -Revision r3
```

产物：`build/out/com.huawei.vrservice-r3.apk`
sha256 `901DDE102DE56AB59EA2435CA1C6B6E17E13D32DEF68E4AC527EF798D58B25DB`

---

## 26. `vr_system` 收回：删掉本地自答，改成真转发（2026-09-15 第十一轮）

用户裁定：**禁止兜底**。所以本地的 `vr_system` 实现不是「降级为兜底」，而是
**整块删除**：查不到真服务就返回 `null`，让原版走它自己的分支。

### 26.1 改了什么

| 位置 | 之前 | 现在 |
| --- | --- | --- |
| `shared/java/android/vrsystem/VRSystemServiceManagerImpl.java` | 自己维护 `helmetPresent` / `vrMode`，监听外接显示，`isVRMode()` 直接回答 | 只做转发：拿远端 `IVRSystemService` 代理，逐个方法转过去 |
| 同上，注册表 | 进程内 `HashMap`（`ServiceManagerEx`） | 由**拥有 `vr_system` 这个名字的进程**托管 registry provider，跨进程取 binder |
| `shared/java/com/huawei/android/vrsystem/IVRSystemServiceManagerEx.java` | 全部返回 false / -1 / 空 | 转发到同一个远端服务 |
| `shared/stubs/android/vrsystem/IVRSystemService.java` | 只有方法签名 | 补上 `Stub.asInterface(IBinder)` 与 AIDL 的 `throws RemoteException` |

**查询失败 = 返回 `null`**，`VRSystemServiceManagerImpl.get(context)` 的语义就等价于
EMUI 上「服务还没注册」时 `getSystemService("vr_system")` 的结果。原版每个调用点
本来就有对空结果的分支，我们不再替它编一个答案。

### 26.2 跨进程注册表的落点

EMUI 里 `ServiceManagerEx` 只是平台 `ServiceManager` 的壳，所以任何进程都能查到
同名 binder。应用在通用安卓上**不能**往平台注册表加名字，因此改用普通 Android 机制：

```
com.huawei.vrservice 进程
  VRService.onCreate
    └─ ServiceManagerEx.addService("vr_system", VRInterfaceService.getInstance())
         └─ 进程内注册表（原样保留，不动原版调用）

  新增组件 com.huawei.vrservice.compat.VrSystemRegistryProvider
    authority com.huawei.vrservice.registry
    exported=true, permission=com.huawei.vrservice.CLIENT_SERVICE(signature)
    call("getService","vr_system") -> Bundle{ binder = 上面注册的那个 binder }

其它进程
  VRSystemServiceManagerImpl.get(context)
    └─ ContentResolver.call(...) -> IVRSystemService.Stub.asInterface(binder)
         └─ 转发所有 IVRSystemServiceManager 方法
```

`ContentResolver.call()` 是同步的，和原版的同步查找语义一致；binder 通过 Bundle
传递是 Android 自己支持的机制，没有自造协议。

组件账：本模块从原版 **16 个组件**变成 **17 个**（只加这一个兼容 provider），
其余 16 个逐一保留。

### 26.3 本轮又补掉的一个平台缺口

`VRService.increaseProcessPriority()` 在 `onCreate` 里调用
`startForeground(1, notification)`。该包 `targetSdkVersion=28`，从 API 28 起
`startForeground` 需要 `android.permission.FOREGROUND_SERVICE`；原版是 uid 0 的
系统应用，这条对它无意义。缺了会在 `onCreate` 直接抛 `SecurityException` ——
服务起不来 → `vr_system` 注册不上 → 整条链断在最前面。已补进 manifest
（桌面包当年是同一个原因补的这条）。

### 26.4 入口与安装

原版入口是**插入眼镜**：`UsbReceiver`（`USB_DEVICE_ATTACHED`）→
`startService(VRService)` → 注册 `vr_system`。这条路径本身是自启动的，但新装的包
处于「已停止」状态，系统不会把隐式广播送给它，所以 `install-six.ps1` 在安装后显式
拉一次 `com.huawei.vrservice/.VRService`：既清掉已停止状态，也让 `vr_system` 立刻可用。

### 26.5 验证（静态）

- 七个模块全部重建通过（`build-all.ps1 -Revision r4`；本模块最后一次为 `r5`）。
- 兼容 dex 里旧实现的状态痕迹已归零：
  `helmetPresent` / `vrListeners` / `dispatchHelmet` / `dispatchMode` /
  `dispatchHeartbeat` / `findGlass` 在 `classes2.dex` 中均为 0 次；
  `VRSystemServiceManagerImpl` 只剩 `TAG` / `REGISTRY_AUTHORITY` /
  `METHOD_GET_SERVICE` / `KEY_BINDER` / `remote(IVRSystemService)` 五个字段。
- 本模块 manifest：provider 已声明（authority、exported、permission 齐全），
  权限 12 条，组件 17 个，`FOREGROUND_SERVICE` 已在。
- 三个消费方（桌面 / 主应用 / Runtime）都已持有 `com.huawei.vrservice.CLIENT_SERVICE`
  且 `<queries>` 里能看到 `com.huawei.vrservice`。

产物：

```
build/out/com.huawei.vrservice-r5.apk   sha256 D37FA3C43E396E1C6BCAC5A878128122935F57565C228AA93DE9C63DB0370C95
build/out/com.huawei.hvrsdkserverapp-r4.apk  50F901D362187BC4984EE89472C7061FFAC78CA27579963961FB47A4BFB33CCB
build/out/com.huawei.vrlauncherx-r4.apk      4031F9C0D4B8F0E359018C7C3F4C6FE8908C2B009F12D60D3EA623A99F51944C
build/out/com.huawei.appmarket.vr-r4.apk     A80A7265459C4981E5911A87E2B1646299D9A63A73674D9544636547E33CA341
build/out/com.huawei.vrhandle-r4.apk         FCC9F1AA5E6A37DFFFC69AE42913356BEE7DC08928852B262C8DDAEBC7143855
build/out/com.huawei.vrvirtualscreen-r4.apk  8AD4CE937BB3F097508FC84A012023EF57174DDC68463FDEE7235A319234DB84
build/out/com.huawei.himovie.vr-r4.apk       6F8DBE8E7E16E3535AF863BA94266F0505BAAFD7CD59F8B496CC78E7A3036476
```

### 26.6 两处没有远端对应的方法（明确记录，不当作兜底）

- `isVRApplication(Context, String)`：EMUI 的客户端管理器用它查「这个包是不是 VR 应用」，
  `IVRSystemService` 里没有对应方法。本移植没有 VR 应用清单，返回 `false`，
  即「没有任何包被认定为 VR 应用」。这是没有来源，不是替服务回答。
- `acceptInCall` / `endInCall`：原版标 `@Deprecated`，远端对应方法照转。

### 26.7 未完成

真机验证。静态层面 `vr_system` 已经只会来自真正的提供方，但下面这条链必须实测：
插入眼镜 → `UsbReceiver` → `VRService` 注册 → 手机侧提示/确认 → 准备流程 → 原 VR 空间。
在它跑通之前，主线仍是**未完成**，第 18/22 节记的偏差也还不能划掉。

### 26.8 为什么「查不到就返回 null」是安全的：原版自己就为它准备了分支

逐个核对过全部调用点（桌面 6 处、主应用 2 处、Runtime 7 处），**每一处拿到结果后
都立刻做了 null 判断**，例如：

```
invoke-static {p0}, Landroid/vrsystem/VRSystemServiceManagerImpl;->get(Landroid/content/Context;)...
move-result-object v0
check-cast v0, Landroid/vrsystem/IVRSystemServiceManager;
if-eqz v0, :cond_2                     # 桌面 MainActivity / z0/c / i2/g1 / l2/u
...
:cond_1
iget-object v0, ...->mVrServiceMgr:...
if-nez v0, :cond_2                     # Runtime VrSystemClient / VrMonitor / VrTouchService ...
```

也就是说原版本来就预期「这个服务可能还没注册」，并为此保留了自己的分支。
返回 `null` 不是我们在制造异常路径，而是在走它原有的那条路径 ——
这也是为什么本轮可以直接删掉本地实现，而不需要留任何替补。

（反过来说：之前那版本地实现**永远**返回非空对象，反而让这些 null 分支永远不被走到。）

---

## 27. 真机测试（无眼镜）：第七个模块跑通启动链（2026-09-15 第十二轮）

设备：SM-F731U1，Android 16，无线 adb；root 通道可用（KSU，`su -c id` → uid=0）。
眼镜不在身边，所以本轮只验证**不依赖眼镜的那半条链**。

### 27.1 怎么把服务拉起来

原版入口是「插入眼镜」：`UsbReceiver`（`USB_DEVICE_ATTACHED`）→
`startService(VRService)`。没有眼镜时用 root 显式拉起等价路径：

```
adb shell su -c 'am start-foreground-service -n com.huawei.vrservice/.VRService'
```

`am startservice` 会被 Android 8+ 的后台服务限制挡掉
（`Background start not allowed`），`start-foreground-service` 才可以 ——
`VRService.onCreate` 本来就会 `startForeground`，语义一致。

### 27.2 逐个撞出来的缺口（都已修）

真机第一次拉起只活了几百毫秒，之后每修一处就往下走一层。四处缺口按出现顺序：

| # | 现象 | 根因 | 处理 |
| --- | --- | --- | --- |
| 1 | 安装即失败：`INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION ... For input string: "signature"` | 手写 AXML 时把 `android:protectionLevel` 写成了字符串；它是平台的 flags 属性，aapt 会编译成整数 0x2 | 改成 `TYPE_INT_DEC` 整数编码，并让脚本能把旧的错误写法修回来 |
| 2 | 启动崩：`NoClassDefFoundError: com/huawei/android/media/IAudioModeCallback` | 缺华为平台类，且不只一个 | 见 27.3：一次性扫全、批量补齐 |
| 3 | 崩：`NoSuchFieldError: No field OWNER ... UserHandleEx` | 兼容层已有类缺成员 | 同上 |
| 4 | `load library error! dlopen failed: library "libc++.so" not found` | 原生库 `libvrservice.so` 依赖一批**私有平台库**（`libc++.so`/`libutils.so`/`libcutils.so`/`libc_secshared.so`/`libstdc++.so`…）。Android 7+ 起应用命名空间看不到这些非公开库 | 见 27.4：把依赖闭包打进 APK 自己的 `lib/arm64-v8a/` |

### 27.3 不再一个个撞：把「缺的成员」一次扫全

写了个只读扫描（`系统固件/firmware-extract/members.py` 的思路）：把 vrservice 反编译树里对所有
**兼容层已提供的类**的成员引用抽出来，逐个对照兼容层源码，列出缺的成员。结果：

```
UserHandleEx        缺 OWNER / getIdentifier / getUserId / myUserId
PowerManagerEx      缺 getUserActivityEventOther / userActivity / wakeUp
AudioSystemEx       缺 getParameters
```

另外扫描「引用了但既不在包内、也不在兼容层」的类，得到 23 个，分两类：

- **6 个是平台类**，各只出现在一处调用点，已全部补齐：
  `com.huawei.android.app.ActivityManagerEx`、`com.huawei.android.app.WindowManagerEx`、
  `com.huawei.android.iawareperf.UniPerfEx`、`com.huawei.android.media.AudioManagerEx`、
  `com.huawei.android.media.IAudioModeCallback`、`com.huawei.cust.HwCfgFilePolicy`、
  `com.huawei.systemmanager...HwLockPatternUtilsEx`。
- **其余 17 个是 okhttp3 / GRS 联网库**，全部落在 `com.huawei.vrinstaller.*`
  （`OkHttpManager` / `DownloadTask` / `HttpUtil` / `RequestPkgInfoHelper` / `GrsManager`），
  也就是 VR 应用商店的下载链。离线版本来就不该有它们；它们的入口组件
  （`com.huawei.updatesdk.*`）已在 25 节摘除。**当前状态：未触发、未验证**，
  如果走到安装器 UI 会 `NoClassDefFoundError`，记在待办里。

补齐时的取舍（按「能映射公开 API 就用真语义，华为专有的按不可用」）：

| 类 | 实现 |
| --- | --- |
| `ActivityManagerEx.getCurrentUser()` | `UserHandle.myUserId()` / `getUserId(int)` / `Context.getUserId()` 三者都不在公开 SDK 里，按 AOSP 的 per-user range 从 `Process.myUid()` 推：`uid / 100000` |
| `WindowManagerEx` 动画开关 | 真是 Settings.Global 的 `window_animation_scale` / `transition_animation_scale` / `animator_duration_scale`；读不用权限，写要 `WRITE_SECURE_SETTINGS`（已声明 + 安装脚本 `pm grant`） |
| `AudioManagerEx` + `IAudioModeCallback` | 用公开的 `AudioManager.addOnModeChangedListener`（API 31+），把真实的音频模式变化转给原回调；低于 31 无法订阅，如实记日志，不造事件 |
| `AudioSystemEx.getParameters/setParameters` | 用公开的 `AudioManager.getParameters/setParameters`，是同一套音频 HAL 参数，真实现 |
| `PowerManagerEx.wakeUp/userActivity` | 隐藏 API，反射调用；需要 `DEVICE_POWER`（signature 级），失败就记日志，不假装成功 |
| `UserHandleEx.getIdentifier` | 只解析自己发出去的句柄（ALL / OWNER / 当前用户），未知句柄返回 AOSP 的 NULL 值并记日志，不猜 |
| `UniPerfEx` | iAware 性能提示，无通用等价物 → 返回 -1，纯提示、不影响流程 |
| `HwCfgFilePolicy.getCfgPolicyDir` | 通用安卓没有 /cust 分区 → 返回空数组（调用方因此不升级，正是离线语义） |
| `HwLockPatternUtilsEx` | 普通应用无法关锁屏 → 查询返回 false、设置只记日志 |

### 27.4 原生库：把依赖闭包打进 APK

`libvrservice.so` 的 `DT_NEEDED`：`libc.so` `libm.so` `libc++.so` `libutils.so`
`libcutils.so` `libc_secshared.so` `liblog.so` `libstdc++.so` `libdl.so`。
其中只有 `libc/libm/liblog/libdl` 是应用可用的公开库，其余都会被命名空间挡住。

做法（标准手法，不是自造协议）：把闭包补齐后放进 APK 自己的 `lib/arm64-v8a/`，
链接器就会从应用自己的库目录解析它们。写了个循环脚本
（`系统固件/firmware-extract/closure.py`）逐轮算 `DT_NEEDED` 直到闭合，最终 10 个：

```
libvrservice.so（原版）     112,560
libc_secshared.so            65,080   ← 从 EMUI 11 system.img 里提取
libc++.so                 1,109,112   ← 设备 /system/lib64
libutils.so                 135,704
libcutils.so                 93,808
libbase.so                  185,960
libvndksupport.so            14,640
libdl_android.so             10,272
ld-android.so                 9,680
libstdc++.so                 23,088
```

`libc++.so` / `libutils.so` / `libcutils.so` / `libbase.so` / `libstdc++.so` 取**设备自带**
的版本（与设备的 libc 同源，避免混版本）；只有华为专有的 `libc_secshared.so`
（SecureC：`memcpy_s`/`sprintf_s` 等）从**同代固件** EMUI 11 `system.img` 提取，
它只依赖 `libc/libm/libdl/libc++`。

> **许可与长期方案**：这几个是平台私有库，打包进 APK 属于把平台依赖变成随包分发。
> 本地验证可用，正式分发需要复核授权；长期应改为在 AOSP 侧提供等价实现或
> 消除该原生依赖。已记入待办。

### 27.5 结果（真机日志）

启动后进程稳定存活，`VRService.onCreate` 的链路一路走通：

```
D/nativeloader: Load .../lib/arm64/libvrservice.so using class loader ns clns-9: ok
E/VRService_System_Main: savePhoneBrightness start!
E/VRService_System_Main: savePhoneBrightness brightness: 40
W/VRService_System_Main: usbDevice or action invalid
```

（最后一行是 USB 监视器的初始状态：没有眼镜，正常。）

**跨进程注册表实测**（root 身份绕过 signature 权限，模拟消费方）：

```
$ adb shell su -c 'content call --uri content://com.huawei.vrservice.registry \
      --method getService --arg vr_system'
Result: Bundle[{binder=android.os.BinderProxy@aa9e502}]

$ adb shell su -c 'content call --uri content://com.huawei.vrservice.registry \
      --method getService --arg no_such_service'
Result: null
```

第一条证明**真正注册的 `vr_system` binder 可以被别的进程取到**（第 26 节的转发链路
在设备上成立）；第二条证明**没有兜底**：没注册的名字就是 null。

### 27.6 仍未完成

1. **消费方在应用内取 `vr_system`**：桌面 / 主应用 / Runtime 装的还是旧构建，
   需要装 r4 之后再验证它们真的走「转发版」而不是空。
2. **okhttp3/GRS 的 17 个联网类**：确认安装器路径不会被主线触发，必要时按
   「在线专用」处理。
3. **带眼镜的主线**：插入 → 提示/确认 → 准备流程 → 原 VR 空间。
4. 主线状态仍为**未完成**。

---

## 28. 原版调试开关：不插眼镜也能看手机画面（2026-09-15 第十三轮）

用户指出华为文档里那条调试开关。核对后确认它是**原版自带**的能力，
本移植只是把它做成可控的开关，没有新造入口。

### 28.1 官方依据

`09-Unity-AndroidManifest配置` 原文：

> 另外，如果开发者需要不连接头盔看到手机上的显示，需要在AndroidManifest的
> application下包含以下meta-data，**但是，正式发布的应用程序中必须去掉该标签，
> 此功能仅用于调试**。
> `<meta-data android:name="com.huawei.android.vr.sensor.mode" android:value="mobile"/>`

### 28.2 谁在读它（反编译核实）

| 读取方 | 读什么 | 结果 |
| --- | --- | --- |
| `libvrsdk.so`、`libvrunityplugin.so` | 宿主 App 的 `<meta-data>` | 原生侧跳过头盔要求 |
| `com.huawei.vrframework.VrMonitor#isConfigMobileMode()` | 同一个 meta-data | 打 `in mobile mode, exit monitor`，VR 监视器不启动 |
| `libHVRSDKServerApp.so`、`libvrunityplugin.so` | 系统属性 `hvr.imm.mobile` | 同上，等价路径 |

也就是说原版留了**两条**等价路径：manifest 里的 meta-data，
或者系统属性 `hvr.imm.mobile=enable`（这条不用改包，见 28.4）。

### 28.3 落地方式：构建期开关，默认永远关

新增 `patches/patch_debug_mobile_mode.py`（只操作传给它的那一个 manifest，
文本与二进制 manifest 都支持）与 `build-module.ps1 -DebugMobileMode`：

```
build-module.ps1 -Package <包名> -Revision rN              -> DEBUG_MOBILE_MODE=off
build-module.ps1 -Package <包名> -Revision rN -DebugMobileMode -> DEBUG_MOBILE_MODE=on
```

三个刻意的设计：

1. **注入发生在 stage 出来的构建副本上，decode 树永远不带这条 meta-data** ——
   「正式发布必须去掉」由构建流程保证，不靠人记得改回来；
   （实测：二进制 manifest 一旦被重建就不是逐字节可逆的，所以更不能直接改 decode 树）
2. **第 7 步静态核对会反过来断言**：没给 `-DebugMobileMode` 却出现这条 meta-data
   就直接构建失败；给了却没出现也失败。
3. `patch_debug_mobile_mode.py verify <manifest...>` 可以随时检查现状。

实测：

```
普通构建  -> DEBUG_MOBILE_MODE=off
调试构建  -> WARNING: 调试构建：加上 com.huawei.android.vr.sensor.mode=mobile ...
             DEBUG_MOBILE_MODE=on
```

### 28.4 真机试了属性那条（不用重装）

```
adb shell su -c 'setprop hvr.imm.mobile enable'   -> getprop 回读 'enable' 成功
（验证完已清空，避免影响后续测试）
```

### 28.5 试出来的结论：这条开关管不到桌面那道门

设好属性后直接拉起桌面（`com.huawei.vrlauncherx/.MainActivity`），
splash 出现后活动立刻 `finish()`：

```
W/ActivityTaskManager: Duplicate finish request for r=... com.huawei.vrlauncherx/.MainActivity
```

原因是桌面自己的 Java 判断（`MainActivity` 里读取的那个方法）：

```
IVRSystemServiceManagerEx.create(ctx).isVRMode()   ← 或 →
VRSystemServiceManagerImpl.get(ctx).isVRMode()
```

两条路都指向真正的提供方 `com.huawei.vrservice`，而它在没有眼镜时
`isVRmode()` 就是 false（第 25 节查过：`VRService.init()` 才会
`VRModeManager.setVRMode(true)`，而 `init()` 是处理头盔时才走的）。
**这正是「不伪造连接状态」应有的表现。**

这条调试开关影响的是**原生插件**与 **VrMonitor**（原生侧跳过头盔要求、
监视器不启动），它并不改变 `vr_system` 报出来的状态。

所以要在没有眼镜的情况下把**桌面那条链**走完，只有两条路：

- 等眼镜到位（正路）；
- 或者刻意让提供方在无眼镜时报「VR 模式」——那就是伪造，本项目不做。

能靠这条开关验证的是：原生插件在 mobile 模式下的加载与初始化路径，
以及 VrMonitor 的跳过分支。等眼镜到位后这条开关也可以用来单独排查
「原生侧」和「Java 侧」谁在拦。

### 28.6 待办

1. 眼镜到位后，用 `-DebugMobileMode` 构建一次桌面，用来分离
   「原生侧要求头盔」与「Java 侧要求 vr_system」两个因素。
2. 其余五个 Unity 包（主应用 / 视频 / 投屏 …）同样支持该开关，
   需要时按同样方式构建。

---

## 29. 手写 vs 原厂件：先把「官方到底有没有」查清（2026-09-16 第十四轮）

起因是一句质疑：**「手写？不应该先检查官方吗？」** 这一轮不写功能，先把账查清。

### 29.1 可跑的两步审计（已入库，可复跑）

```
& .\tools\official-index.ps1        # 原包 + 原厂件 -> build/official-index/*.txt
python tools\compat-source-audit.py # 交叉比对 -> docs/OFFICIAL_SOURCE_AUDIT.md
```

- `tools/dexdump/DexDump.java`：apktool 自带 dexlib2 的 CLI 被裁掉了（`Main` 是
  abstract），这里把 `--list` 与「反汇编到 smali」两个入口重新接出来。它还能读
  EMUI 9 那种 `vr.jar`（200 字节壳）+ `vr.vdex`（compact dex）的形态 ——
  官方 baksmali 2.2.7 与 jadx 0.9 都读不了。
- `原厂件/`：从华为官方固件里原样取出的 `hwframework.jar`（2025 个类，EMUI 11
  的框架扩展分片）、`hwPartVr.jar`（9 个类，`android.vrsystem` 的官方实现）。
  来源镜像、镜像内路径、sha256 记在 `原厂件/README.md`。

### 29.2 查出来的事实

`docs/OFFICIAL_SOURCE_AUDIT.md`（自动生成）给出三档：

| 档 | 数量 | 说明 |
| --- | --- | --- |
| 可以整族复制官方字节码 | 3 族 | `android.vrsystem.*`、`com.huawei.gson.*`、`com.huawei.libcore.io.ExternalStorage*` |
| 官方有原件、但依赖华为系统设施 | 36 | 要按官方实现反编译后替换系统依赖，见 29.5 |
| 原厂确实没有 | 24 | 兼容层必须补的框架类，或本项目自己的胶水 |

其中最关键的一条：**`android.vrsystem.IVRSystemService$Stub` 在 EMUI 上是
boot classpath 提供的，应用包里只有消费方那半**（`IVRListener`、`IVRSystemServiceManager`），
所以谁都没想到要把它带进包 —— 这正是上一轮 `NoClassDefFoundError` 的根因。
官方原件在提供方应用里（`com.huawei.vrlauncherx` 自带 `IVRSystemService` +
`$Stub` + `$Stub$Proxy` + `$Default`），直接从原包取，不用手写。

另外两处纠正（都是「先查官方」查出来的）：

1. `android.vrsystem.VRSystemServiceManagerImpl` 这个类名在**七个原包和已入库
   原厂件里都不存在**。原版代码是 `getSystemService("vr_system")` 后转
   `IVRSystemServiceManager`；EMUI 11 的框架实现叫
   `android.vrsystem.HwVrServiceManagerImpl`（`原厂件/hwPartVr.jar`），
   内部是 `ServiceManagerEx.getService("vr_system")` →
   `IVRSystemService$Stub.asInterface(...)`。这条链路现在是我们唯一依据。
2. 上一轮 `dc8b8901` 把 19 处 `getSystemService("vr_system")` 改写成
   自写的 `VRSystemServiceManagerImpl.get()`，**这是全工程唯一允许改的系统调用点**，
   仍然保留（通用安卓的应用进程无法注册 `vr_system`），但实现已按 29.3 换成官方 AIDL。

### 29.3 这轮真正落地的改动

1. `patches/patch_official_platform_classes.py`（新）：
   按「模块引用 + 兼容层引用」的闭包，把官方类从字节码池搬进
   `decode/<包名>/smali/`，apktool 重建时随原代码一起汇编。
   - 只搬 `COPY_PREFIXES` 三族（其余见 29.5），在线链路
     （okhttp3 / networkit / vrinstaller / hianalytics / hms…）一律不搬；
   - 复制时剥掉 `whitelist/blacklist/greylist` 这些 hiddenapi 标记：它们只在
     系统镜像里有意义，apktool 在 api<29 时还会拒绝汇编
     （实测报错 `Hidden API restrictions are only supported on api 29 and above`）；
   - 模块自己已经有的类不覆盖（含 Runtime 的 `assets/hvrframework.dex`，原包
     索引里一并算了）。
2. 删除手写重复件：`shared/java/com/huawei/gson/Gson.java`（之前是 org.json
   拼的，语义撑不住 Gson）、`shared/java/com/huawei/libcore/io/ExternalStorage*`
   （4 个）。这两族现在用的是官方字节码。
3. `shared/java/android/vrsystem/VRSystemServiceManagerImpl.java` 重写：
   不再自己拼 Parcel、不再自己写事务号，改成官方
   `IVRSystemService$Stub.asInterface(binder)` 的代理；`isVRApplication` 也按
   官方常量 `com.huawei.android.vr.application.mode == "vr_only"` 判定。
   查表那一步仍然走兼容注册表（通用安卓的唯一换点），查不到就返回 null。

   踩到的两个坑，都已写进 `docs/PORTING_METHOD.md` 第 9 节：
   - 官方类不能塞进第一个 `smali/`：主应用塞进去后 apktool 报
     `Unsigned short value out of range: 65874`（64K 方法数上限），
     改成占用 `smali_classes<N+1>/` 独立成一个 dex 后构建通过；
   - 官方 smali 带 `whitelist/blacklist/greylist` 标记，apktool 在 api<29 时
     拒绝汇编（`Hidden API restrictions are only supported on api 29 and above`），
     复制时统一剥掉（不影响字节码语义）。
   - 七个模块 r23/r24 全部构建通过（r23：appmarket 2 分 06 秒、himovie 4 分 29 秒，
     产物见 `build/out/*-r2*.apk`）。

### 29.4 实测（SM-F731U1，无线 adb）

```
runtime(r23) 构建通过；产物里 classes.dex 含官方
  android/vrsystem/IVRSystemService{,$Stub}、IVRListener、com/huawei/gson/**
安装 r23 后拉起：
  进程在：com.huawei.vrservice / com.huawei.vrlauncherx / com.huawei.hvrsdkserverapp
  logcat 里不再出现 NoClassDefFoundError / ClassNotFoundException / FATAL
  注册表仍在发布：I HvrVrRegistry: published vr_system（每秒一次）
  端到端取回 binder 成功：
  $ adb shell su -c 'content call --uri content://com.huawei.vrlauncherx.registry --method getService --arg vr_system'
  Result: Bundle[{binder=android.os.BinderProxy@13a31e3}]
```

注意：这只证明「官方 AIDL 链路接上了、崩溃点没了」，**不等于主线跑通**；
眼镜不在手边，插入→确认→空间那一段仍未验证。

### 29.5 下一步：官方有原件但跑不通的那 36 个类

统一处理方式（用户口径）：**反编译官方实现 → 只把「依赖华为系统设施」的那一步
换成通用安卓等价物 → 其余逐行照搬**，不许因为跑不通就另写一套。

清单与替换点见 `docs/OFFICIAL_SOURCE_AUDIT.md` 的「要按官方实现移植的那一批」
一节（已填 6 个：`ServiceManagerEx`、`SystemPropertiesEx`、`HwNotchSizeUtil`、
`UniPerfEx`、`HwSfpPolicyManager`、`ImmersionStyle`，其余标「待逐类判定」）。

### 29.6 纪律补充

- 官方件只读；要改行为只能改兼容层。
- 新的兼容类写之前，先跑 `tools/compat-source-audit.py` 看官方有没有原件。
- 「整族复制官方字节码」与「按官方移植」的区别写进台账，避免下次又把
  能直接用的类重写一遍。

---

## 30. 华为VR视频「打开就闪退」：是应用自己的签名守卫（2026-09-16 第十五轮）

用户报：`com.huawei.himovie.vr` 打开就闪退。完整取证见
`docs/evidence/himovie-crash-2026-09-16.md`，结论如下。

### 30.1 现象不是崩溃，是自杀

```
09-16 01:05:44.672 I IDS_TAG : App com.huawei.vrlab.VrPlayerApplication@… has not finished training
09-16 01:05:44.672 I Process : Sending signal. PID: 28806 SIG: 9
09-16 01:05:44.686 I ActivityManager: Process com.huawei.himovie.vr (pid 28806) has died: fg TOP
```

没有 `FATAL EXCEPTION`，`/data/tombstones/` 里也没有新增记录；
应用自己的 `files/log/crash_log/*` 全是 0 字节。也就是说：**进程是自己 kill 自己的**。

### 30.2 三步对照证明成因是签名，不是我们的改动

同一个 Activity，同一台设备：

| 装的包 | 签名 | 结果 |
| --- | --- | --- |
| `原包/com.huawei.himovie.vr.apk` | 华为（`CN=China, OU=Huawei, O=Huawei`，sha256 `186cffec…`） | 正常：`has not finished training` → `Closing IDS observe window` → `IDS count updated to 1`，进程活着 |
| **同一个原包，一个字节没改，只重新签名** | 自签（`CN=HVR Offline`，sha256 `30094ded…`） | 自杀（同上 SIG:9） |
| 移植构建 `com.huawei.himovie.vr-r24.apk` | 自签 | 自杀（同上 SIG:9） |

第二行是关键证据：**只换签名就复现**，与 manifest / 组件 / 权限 / 平台类改动无关。

### 30.3 归类与处置

- 按 `docs/PORTING_METHOD.md` 第 2 节：这不是设备节点 / 系统服务 / 权限 / 显示 /
  总线 / 在线依赖，而是**应用自带的签名完整性校验**。
- 守卫字符串（`IDS_TAG` 等）在原包的 dex 和 .so 里都搜不到，属于运行时解密/
  保护的那部分；同目录的 `libaegissec.so` 就是这套保护链。
- 处理位置在**系统层**：用 KSU + LSPosed 做签名伪造，让应用读到华为原签名
  （只改指向，不改应用代码）。在不具备签名伪造之前，重装自签包复现该现象
  没有诊断价值 —— 已用「只重签的原包」证伪。
- 七个包可能不止这一个带守卫（桌面「splash 后立刻 finish」是另一种表现）。
  **以后凡是「某模块打不开/闪退」，先做「原包 vs 只重签的原包」对照，再判是不是移植问题。**

### 30.4 真机当前状态

设备上 `com.huawei.himovie.vr` 已装回**华为签名原版**（能正常打开）；
我们的构建产物仍在 `build/out/`，等签名伪造方案确定后再统一装。

---

## 31. 按官方实现移植第一批：SystemPropertiesEx / HwNotchSizeUtil / 状态通道（2026-09-16 第十六轮）

### 31.1 先看清这层到底被用来干什么

新增 `tools/vr-state-keys.py`：把七个包里所有 `SystemPropertiesEx` 调用点连同
键名列出来。结果（这是后面所有改动的依据）：

| 键 | 谁写 | 谁读 |
| --- | --- | --- |
| `sys.glass.state` | vrservice（AndroidAdapterManager，进/退 VR 各写一次） | —— |
| `hw.vr.environment.status` | vrservice | —— |
| `hw.vr.virtualmode` | vrvirtualscreen | —— |
| `vr.mode.enter` | —— | vrservice |
| `persist.sys.vr_left_hand_mode` | 桌面 | —— |
| `persist.sys.vr_def_brightness` | —— | 桌面 |
| `persist.sys.vr_not_check_ver` | —— | vrservice |
| `ro.vr.surport` / `ro.vr.mode` | ——（平台谓词） | vrservice、桌面、投屏 |

**这组键就是模块之间的状态总线**。「六个软件串不起来」里至少有一部分是它：
EMUI 上它们是普通系统属性，七个模块读写同一份；通用安卓上普通应用**写不了**
系统属性（property_service 直接拒绝），于是 vrservice 写的「眼镜状态 / 环境状态」
谁都看不到。

### 31.2 官方实现长什么样

`原厂件/hwframework.jar` 里 `com/huawei/android/os/SystemPropertiesEx.smali`
五个方法全部是 `android.os.SystemProperties` 的直连封装（get / get(String,String)
 / getInt / getBoolean / set），**没有任何 VR 专用逻辑**。所以「照官方实现移植」
= 直连 + 只换掉那条走不通的后端。

### 31.3 改了什么

1. `shared/java/com/huawei/android/os/SystemPropertiesEx.java` 重写：
   - 五个方法照官方直连 `android.os.SystemProperties`（`shared/stubs` 里新增
     编译期存根；直接调用不受 targetSdk≥28 的 hidden API 反射限制）；
   - 只把上表里那 7 个 VR 状态键的后端换成**桌面托管的跨进程注册表**
     （`VrPropertyStore` → `VrSystemRegistryProvider` 的 `getProp`/`setProp`，
     值落盘到 SharedPreferences，进程重启后仍在）—— 语义与全局属性一致：
     谁写谁读、跨进程、持久；
   - 读的时候**先读真实属性、没有再读注册表**：在真 EMUI 上行为与原版一致；
   - `set` 自己接住平台的拒绝（原版不接，通用安卓上会抛回原版逻辑）；
   - `ro.vr.surport` = **兼容平台是否真的装着**（`PackageManager` 注册表里有没有
     那个 provider），不再写死 `"true"`；
   - `ro.vr.mode`（EMUI 的副屏 VR 模式）**不特判**：本移植没有实现副屏模式，
     就让它取默认值 false，不假装支持。
2. `shared/java/com/huawei/android/util/HwNotchSizeUtil.java` 按官方重写：
   保留官方的 `ro.config.hw_notch_size` 通路与解析规则（长度 <4 判为配置错误），
   只在属性为空（= 通用安卓没有这个华为配置）时改用**真实 DisplayCutout**；
   取不到就返回 0,0，不编尺寸。
3. 兼容层上下文接入（`ContextEx.setApplication` + 新增 `HvrContextProvider`）：
   上面两个类原版都不传 Context，换实现后需要真实 Context。provider 由平台在
   进程启动时实例化，比反射 `ActivityThread.currentApplication()`（hidden API，
   targetSdk≥28 会被拦）可靠。为此在七个包里都插了一个不导出的 provider：
   - 文本 manifest（主应用/视频/手柄/桌面/投屏）：`patch_platform_permissions.py`
   - 二进制 manifest（Runtime / vrservice）：`patch_sdk_manifest.py` /
     `patch_vrservice_manifest.py`
   - authority 逐包不同（`<包名>.hvrcompat.ctx`），不会互相冲突。
4. 权限：视频、投屏、手柄、vrservice 追加申请
   `com.huawei.vrservice.CLIENT_SERVICE`（注册表那条签名级权限），否则读写状态
   会被 provider 挡掉。

### 31.4 验证状态

- 源码已改：是（本节全部文件）。
- 构建通过：七个模块 r25 全量构建（`build/build-all.ps1 -Revision r25`）。
- 单项实测 / 跨模块实测：**未做**。下一步是装 r25 后看
  `sys.glass.state` / `hw.vr.environment.status` 能否被其他模块读到
  （`adb shell su -c 'content call --uri content://com.huawei.vrlauncherx.registry
  --method getProp --arg sys.glass.state'`），以及桌面进 VR 的分支是否因此变化。

---

## 32. 按官方实现移植第二批 + 两个硬事实（2026-09-16 第十七轮）

### 32.1 状态通道的真机验证（第 31 节的收尾）

```
$ adb shell su -c "content call --uri content://com.huawei.vrlauncherx.registry \
      --method setProp --arg sys.glass.state --extra value:s:1"
Result: Bundle[{ok=true}]
$ ... --method getProp --arg sys.glass.state
Result: Bundle[{value=1}]
$ ... --method getProp --arg hw.vr.environment.status
Result: Bundle[{value=null}]      <- 没设置过就是 null，不编值
```

### 32.2 `IVRSystemServiceManagerEx` 按官方重写

官方原件：`原厂件/hwframework.jar` 的 `com/huawei/android/vrsystem/IVRSystemServiceManagerEx.smali`。
逐条照搬其语义与返回值：

| 方法 | 官方行为 | 本移植 |
| --- | --- | --- |
| `create(Context)` | null 上下文 → 记日志并持有 null；否则 `getSystemService("vr_system")` 包起来 | 改走兼容入口 `VRSystemServiceManagerImpl.get(context)`（就是 `vr_system` 的兼容实现，拿不到仍为 null） |
| `isVRMode()` | 无 manager → 记日志 false | 同 |
| `getHelmetBattery(ctx)` | 无 manager/ctx → 记日志**返回 0**（官方 `DEFAULT_BATTERY`） | 同（之前我方返回 -1，是错的） |
| `setHelmetBrightness(ctx,i)` | i 不在 0..9 → 记日志不转发 | 同（官方 `MIN/MAX_BRIGHTNESS`） |
| `checkPermissionForMultiDisplay(ctx)` | 包名必须是 `com.huawei.vrvirtualscreen` | 同 |
| `createVrDisplay/destroyVrDisplay/destroyAllVrDisplay` | 校验后交 `HwDisplayManager` | 校验与日志照官方，结果按已批准口径报「不可用」（异步投屏只保接口） |
| `isVirtualScreenMode()` | 转发接口方法（只在 EMUI boot classpath 版接口里有） | 反射转发，取不到 → 记日志 false |

同时删掉了我方多出来的 `acceptInCall/endInCall` —— 官方这个类没有这两个方法
（七个包也没有任何调用点）。

### 32.3 `PowerManagerEx` 按官方重写，并修掉一个语义错误

官方 6 个被用到的静态方法逐条对照后：

- `isInteractive()`：官方走 `ServiceManagerEx.getService("power")` →
  `IPowerManager`；本移植用公开 `PowerManager.isInteractive()`（问的是同一件事）。
- `setTemporaryScreenAutoBrightnessSetting(int)`：官方把它交给
  `IPowerManager.setTemporaryScreenAutoBrightnessSettingOverride(brightness)`。
  **之前我方把这当成 brightness mode 写进 `SCREEN_BRIGHTNESS_MODE`，是错的**
  （调用方传的是 `currentBrightness`，会把模式写成非法值）。现在改成
  「重新套用当前亮度设置」，即调用方真正想要的 nudge 动作。
- `userActivity/wakeUp`：先照官方直接调 hidden 方法；被平台拒绝
  （hidden API 策略或 `DEVICE_POWER`）时退到公开 wake lock
  （`ACQUIRE_CAUSES_WAKEUP` 点屏 / 短暂持锁重置 idle 计时器），并记日志。

### 32.4 两个硬事实（都来自原厂文件，不是推测）

1. **原版有四个包跑在 system UID 下**（`aapt2 dump xmltree` 读原包 manifest）：

   | 包 | sharedUserId |
   | --- | --- |
   | `com.huawei.hvrsdkserverapp` | `android.uid.system` |
   | `com.huawei.vrlauncherx` | `android.uid.system` |
   | `com.huawei.vrservice` | `android.uid.system` |
   | `com.huawei.vrvirtualscreen` | `android.uid.system` |
   | 其余三个（主应用/视频/手柄） | 普通应用 |

   通用安卓给不了 system UID，所以这些包原来「白拿」的能力必须逐条换成
   权限 + appops（第 25 节已按这个口径补了 WRITE_SETTINGS 等），或者承认
   没有等价能力。

2. **VR 输入通道要求 system UID，普通应用没有等价接口**。
   `原厂件/hwPartVr.jar` 的 `android.vrsystem.VrTouchInterface.smali` 开头就是：

   ```
   invoke-static {}, Landroid/os/Process;->myUid()I
   const/16 v2, 0x3e8            # 1000 = system
   if-ne v1, v2, :cond_2e
   ...
   :cond_2e  new-instance v1, Ljava/lang/SecurityException;
             const-string v2, "System Uid Only"
             throw v1
   ```

   之后才用 `InputConsumerEx.createInputConsumer(...)` 拿输入通道。
   普通应用侧能被授权的输入接口（`MONITOR_INPUT`）是签名级权限，拿不到。
   → `VrTouchInterfaceEx` 保持接口不变、事件不投递；
   **手机触控进 VR 这条链路按原计划走「可选无障碍服务 / Shizuku」**，
   不在这轮伪造成功（记录为待补项）。

### 32.5 签名守卫：按用户口径先记录

华为VR视频的自杀式签名守卫（第 30 节）本轮不继续投入。已经做完的部分是
「按 apksigner 权威指纹从七个原包各自取出官方证书」，放在
`tools/lsposed-signature-spoof/`（见该目录 README：模块本体未写、设备上也没有
LSPosed）。**后续解决**。

---

## 33. 按官方实现移植第三批：UserHandleEx / AudioSystemEx / InputManagerEx（2026-09-16 第十八轮）

这一批按「先读官方 smali，再逐条对照我方实现」做，**查出两个会真正跑错的行为差异**：

### 33.1 修掉的 bug 一：`UserHandleEx.getIdentifier(null)` 返回值不同

官方（`hwframework.jar` 的 `UserHandleEx.smali`）：

```
if-nez p0, :cond_4
const/4 v0, -0x1        # null -> -1
return v0
:cond_4  userHandle.getIdentifier()
```

我方旧版对 null 返回 `-10000`（USER_NULL），并且只认自己造过的 handle，
对其它 handle 直接返回 -10000。调用点（`com.huawei.vrservice.utils.VRUtils`）用它
和 `ActivityManagerEx.getCurrentUser()` 比较「当前用户是不是机主」，返回值不同
就会走错分支。现在按官方：null → -1；否则反射取真 `getIdentifier()`，
拿不到时退到 AOSP 里与它同值的 `UserHandle.hashCode()`（framework 源码
`UserHandle.java` 的实现就是 `return mHandle;`），再不行才 -1。

### 33.2 修掉的 bug 二：`InputManagerEx.injectInputEventByDisplayId` 的两个 int 反了

官方签名与顺序是：

```
injectInputEventByDisplayId(Landroid/view/InputEvent; I mode; I displayId; Landroid/content/Context;)Z
```

前两个参数都是 int，**写反了编译期不报错、行为一定错**。我方旧版写成了
`(event, displayId, mode, context)`，已按官方改正；同时补上官方的前置校验
（context 为空或包名不是 `com.huawei.vrvirtualscreen` → false）。

### 33.3 其他对照结论

| 类 | 官方做法 | 本移植 |
| --- | --- | --- |
| `UserHandleEx.myUserId()/getUserId(int)` | 调 hidden `UserHandle` 静态方法 | 用同一套 uid 区间算术（`uid / 100000`），值一致且不依赖 hidden API |
| `AudioSystemEx.get/setParameters` | 直连 hidden `android.media.AudioSystem` | 同样直连（新增编译期存根）——`setParameters` 现在返回**HAL 的真实返回码**，不再是我方旧版写死的 0；`setForceUse` 一并补齐 |
| `AudioServiceEx.getInstance()` | 加锁单例 | 一致 |
| `AudioServiceEx.setBluetoothA2dpOn(Z)` | `ServiceManager.getService("audio")` → `IAudioService.setBluetoothA2dpOn` | 用公开 `AudioManager.setBluetoothA2dpOn`（AOSP 内部就是同一条调用），hidden 方法走反射，失败记日志不假装切换 |
| `InputManagerEx.getInjectInputEventMode*()` | return 0 / return 2 | 一致 |
| `InputManagerEx.injectInputEvent(im,e,mode)` | `im.injectInputEvent(e,mode)` | 反射调用同一方法；被拒（`INJECT_EVENTS` 是签名级）就如实返回 false |

### 33.4 验证状态

- 源码已改：是。
- 构建通过：七个模块 r27。
- 单项实测 / 跨模块实测：未做（眼镜此刻不在位，设备上只有手机内屏与折叠副屏）。

---

## 34. 按官方实现移植第四批：电话状态链 + ActivityManagerEx（2026-09-16 第十九轮）

这一批里有一条**断掉的链**，补上它桌面「通话中不进 VR」的判断才可能生效。

### 34.1 断链：`PhoneStateListenerEx` 少了官方那条接线

官方（`hwframework.jar` 的 `PhoneStateListenerEx.smali`）只有一条关键接线：

```
onPreciseCallStateChanged(PreciseCallState callState) {
    onPreciseCallStateChangedCallBack(new PreciseCallStateEx(callState));
}
onPreciseCallStateChangedCallBack(PreciseCallStateEx callState) { }   // 子类覆写
```

桌面（`l2/s`）覆写的正是 `onPreciseCallStateChangedCallBack`，再由 `l2/u` 调
`PreciseCallStateEx.getRingingCallState/getForegroundCallState/getDisconnectCause`。
我方旧版本只保留了 `onSignalStrengthsChanged`，**这条链是断的**：监听器永远收不到
精确通话状态，桌面的判断只会走默认分支。

现在按官方补齐：三个构造函数、`onPreciseCallStateChanged` 包装并回调、
基类 `onPreciseCallStateChangedCallBack` 空实现。

两个平台的硬限制（都写在代码注释里）：

- `PhoneStateListener(Looper)` 是 hidden 构造，公开 SDK 只有无参与 API 30 起的
  `(Executor)`，所以带 Looper 的构造退回无参构造；
- `onPreciseCallStateChanged(PreciseCallState)` 本身是 hidden 方法，公开 SDK 里
  没有，因此**不能写 `@Override`**，但同名同签名在运行期仍会覆盖平台方法
  （编译期用 `shared/stubs/android/telephony/PreciseCallState` 存根）。

### 34.2 `PreciseCallStateEx`：构造函数被写成了 private，应用根本造不出来

官方是**公开构造函数** `PreciseCallStateEx(PreciseCallState)` + 私有字段
`mCallState` + 五个静态 getter；null 一律返回 -1（官方
`PRECISE_CALL_STATE_NOT_VALID`）。

我方旧版本把它写成 private 构造 + 一个 `Object state`，应用侧构造不出来，
`PhoneStateListenerEx` 也没法 new。现在按官方重写，并把官方那 8 个常量逐字补上。

### 34.3 `MSimTelephonyManager`：`from()` 应是单例

官方 `from(Context)` 是单例（`sContext`/`sInstance`），`getCallState(int)` 走
`TelephonyManager.getDefault().getCallStateForSlot(subscription)`（两者都是 hidden）。
我方改为单例 + 公开 `TelephonyManager.getCallState()`（VR 只需要「有没有通话」），
`slotId` 接受但忽略，已在注释里写明。

### 34.4 `ActivityManagerEx.getCurrentUser()`

官方那行 `ActivityManager.getCurrentUser()` 在公开 SDK 里不存在（hidden），
所以保留等价的 uid 区间推导 `Process.myUid() / 100000`，并把「官方原文是什么、
为什么不能直接抄」写进注释。

### 34.5 验证状态

- 源码已改：是。
- 构建通过：七个模块 r28。
- 单项实测 / 跨模块实测：未做（眼镜不在位）。

---

## 35. 按官方实现移植第五批：锁屏/通知/性能/分析（2026-09-16 第二十轮）

### 35.1 `HwLockPatternUtilsEx`：之前整个是空壳，现在按官方真正读写那个键

官方（`hwframework.jar` 的 `HwLockPatternUtilsEx.smali`）：

```
new LockPatternUtils(context)                 // com.android.internal.widget，hidden
setLockScreenDisabled(disable, userId)
isLockScreenDisabled(userId)
```

AOSP 的 `LockPatternUtils.setLockScreenDisabled` 落到 `Settings.Secure` 的
`lockscreen.disabled` 键、按 userId 读写 —— 这部分能用公开接口复现。

我方旧版本是「查询恒 false、写入只打日志」，等于把「戴眼镜时关锁屏」整件事丢掉。
现在：

- `isLockScreenDisabled(userId)` → 读真实值（非 0 即 true）；
- `setLockScreenDisabled(disabled, userId)` → 写真实值；
- 写这个键要 `WRITE_SECURE_SETTINGS`（本包已声明 + install-six.ps1 里 `pm grant`，
  与原版 system UID 白拿等价）；被拒就如实记日志。
- 平台的硬限制：公开 SDK 只有「当前用户」的 `Settings.Secure.getInt/putInt`，
  `*ForUser` 是 hidden，所以只能对当前用户读写；`userId` 不是本进程所属用户时
  记日志跳过，不假装写成功。

### 35.2 `HwNotificationListenerEx`：官方那步拿不到时退到公开的 requestRebind

官方是 `NotificationListenerService.registerAsSystemService(context, name, userId)` /
`unregisterAsSystemService()`（hidden）。普通应用拿不到这两步，平台提供的正规
替代是 `NotificationListenerService.requestRebind(ComponentName)`。现在先按官方调，
失败再退到 `requestRebind`，两条都失败才记日志。

### 35.3 `UniPerfEx`：按官方加锁单例，调用结果保持「不可用」

官方 `uniPerfEvent` → `android.iawareperf.UniPerf.getInstance().uniPerfEvent(...)`
（hidden 的华为性能提示服务）。通用安卓没有等价服务，按项目口径返回 -1
（不伪造提示已生效），单例形式与官方一致。

### 35.4 `HiViewEx` / `HiEventEx`：离线口径下的分析事件载体

官方是华为分析 SDK 的事件构造与上报入口。按已批准的离线范围（去掉联网/账号/
分析链），事件仍然被构造（`HiEventEx(int)`、`putAppInfo(Context)`、
`HiViewEx.byJson(int, JSONObject)` 语义不变），但 `report` 不向任何后端发送 ——
这与「不启动 hianalytics、无 INTERNET」一致，属既定范围例外，不是漏实现。

### 35.5 验证状态

- 源码已改：是。
- 构建通过：七个模块 r29。
- 单项实测 / 跨模块实测：未做（眼镜不在位）。

---

## 36. 按官方实现移植第六/七批：小组件类收尾（2026-09-16 第二十一轮）

### 36.1 真改了的

| 类 | 官方是什么 | 改成什么 |
| --- | --- | --- |
| `NoExtAPIException` | 四个构造函数的普通异常 | 逐字补齐（含 `serialVersionUID`） |
| `IAudioModeCallback` | **abstract class** + 无参构造 + 抽象 `onAudioModeChanged(int)` | 形状照官方（之前是 concrete + 继承 Binder，与官方不一致） |
| `com.huawei.system.BuildEx` | `getOsBrand()` 读框架字符串资源 `0x104020b`；`getRadioVersion()` 读 `gsm.version.baseband` | `getRadioVersion` 逐字照搬；`getOsBrand` 用 `Build.BRAND`（资源 ID 跨设备不稳定，照抄会拿到错文本），官方公开字段一并补齐 |
| `ImmersionStyle` | 读 EMUI 主题资源取色 | 改用公开主题属性（`colorPrimary`/`colorControlNormal`），取运行时真实主题色；`getControlColor` 与公开构造按官方补齐 |
| `HwCfgFilePolicy` | 转给 `huawei.cust.HwCfgFilePolicy`（本机固件没有该类） | 保持「无 cust 分区 → 空目录」，官方 17 个公开常量全部补齐 |

### 36.2 核对后确认已对齐、只补文档的

`ApplicationInfoEx`（反射读同名 `hwInfo.hwFlags`，官方就是直接读该字段）、
`SettingsEx$Systemex`（就是 `Settings.System` 同一张表）、
`ContextEx.registerReceiverAsUser`（公开 `registerReceiver` 只能登记本用户）、
`ServiceStateEx`（反射调同一个 hidden 方法）、
`HwFoldScreenManagerEx`（反射调同一个华为类；不存在时返回中性值，不伪造折叠态）、
`WindowManagerEx$LayoutParamsEx`（记录在包装对象并尝试写同义的 `extraFlags`）、
`UEventObserverEx`（平台 `UEventObserver` 要 `/dev/socket/uevent`，普通应用被 SELinux 拒；
按桌面真正关心的 DP link 事件改由 `DisplayManager` 提供，接口与 `UEvent.get()` 保持）、
`ServiceManagerEx`（平台服务表普通应用写不了，改由桌面托管的注册表承担）、
`VrTouchInterfaceEx`（官方要求 system UID，普通应用无等价接口 → 只保接口）、
`PackageManagerEx`（只被 updatesdk 那条在线更新链调用，已按离线范围切掉）。

逐类判定同时写进 `tools/compat-source-audit.py` 的 `EXCEPTIONS`，
`docs/OFFICIAL_SOURCE_AUDIT.md` 里的「要按官方实现移植的那一批」现在每一行都有
「官方依赖什么 / 换了哪一步」，不再有「待逐类判定」。

### 36.3 验证状态

- 源码已改：是。
- 构建通过：七个模块 r30。
- 单项实测 / 跨模块实测：未做（手机断联、眼镜不在位）。

---

## 37. 按 review-agent 口径做的只读评审 + 修复（2026-09-16 第二十二轮）

评审对象：本轮全部兼容层改动（`ac645cb8..HEAD`）。评审按
`review-agent` 的口径做：先读改动、找「会被作者修的缺陷」，只报能指出调用路径的；
评审本身不改文件，修复单独做。

### 37.1 查出的问题（已修）

| 级别 | 问题 | 证据 | 修复 |
| --- | --- | --- | --- |
| P2 | `UEventObserverEx` 自己反射 `ActivityThread.currentApplication()` 取 Context | 桌面 `targetSdk=29`，greylist 反射被拦 → 日志 `no application context, DP link monitoring stays inactive`，DP 链路监听完全不生效 | 改走兼容层统一的 `ContextEx.currentApplication()`（provider 在进程启动时注入的真实 context，见 `HvrContextProvider`） |
| P2 | `VrPlatformCompat` 同一问题 | 它是 `/dev/hwvr1` 判定的替代实现，被 Runtime 三处调用（VrSystemClient/VrMonitor/VrTouchService）；拿不到 context 就返回「眼镜不在位」，等于把整条手柄链路又关掉 | 同上，改用 `ContextEx.currentApplication()` |
| P3 | `com.huawei.android.app.WindowManagerEx.setAnimationScale` 只捕获 `SecurityException` | `Settings.Global.putFloat` 在别的失败形态下会把异常抛回原版逻辑 | 改成捕获 `Throwable` 并按同一语义记日志 |

### 37.2 新增的验证工具（可复跑）

`tools/compat-signature-check.py`：把**构建产物里所有 dex 定义的方法表**与
**decode 树里对兼容层类的调用点**逐条比对，报「缺实现 / 描述符不一致」。
检查器用 `tools/dexdump/DexDump` 的 `--methods` 直接从 APK 读方法描述符
（不是解析源码，避免误报）。

```
python tools/compat-signature-check.py
com.huawei.appmarket.vr-r31.apk    调用点  15  通过
com.huawei.himovie.vr-r31.apk      调用点  15  通过
com.huawei.hvrsdkserverapp-r31.apk 调用点  11  通过
com.huawei.vrhandle-r31.apk        调用点  15  通过
com.huawei.vrlauncherx-r31.apk     调用点  52  通过
com.huawei.vrservice-r31.apk       调用点  36  通过
```

（`java.lang.Object`/`Throwable`/`Binder` 上本来就有的方法在检查器里单独白名单，
否则子类调用 `getMessage()` 这类会被误判成缺失。）

### 37.3 评审确认的、属于平台限制而不是代码缺陷的项

hidden API 反射对 **targetSdk ≥ 28** 的应用会被拦；七个包的 targetSdk 是：

| 包 | targetSdk |
| --- | --- |
| `com.huawei.hvrsdkserverapp` | 26（反射可用） |
| `com.huawei.vrservice` | 28 |
| `com.huawei.appmarket.vr` / `himovie.vr` / `vrlauncherx` / `vrvirtualscreen` | 29 |
| `com.huawei.vrhandle` | 31 |

因此下面这些「官方用 hidden 方法、我们只能反射」的路径在后四个包里必然
拿不到真实结果，已经全部有「退到公开等价物或如实返回不可用」的处理：

- `PowerManagerEx.userActivity/wakeUp` → 退到公开 wake lock（`ACQUIRE_CAUSES_WAKEUP`）；
- `HwNotificationListenerEx.registerAsSystemService` → 退到公开 `requestRebind`；
- `UserHandleEx.getIdentifier` → 退到 AOSP 里同值的 `UserHandle.hashCode()`；
- `InputManagerEx.injectInputEvent` → 本来就要 `INJECT_EVENTS`（签名级），如实返回 false；
- `AudioServiceEx.setBluetoothA2dpOn`、`ServiceStateEx.getConfigRadioTechnology`：
  **没有公开等价物**（A2DP 开关、config radio technology 都只有 hidden 接口），
  这两个在通用安卓上保持「调用不生效 + 记日志」，不伪造成功。
  这是平台限制，记录在案，不做手写 AIDL 事务绕过（违反本项目「不手写事务号」的口径）。

### 37.4 已知偏差（有意保留，写明原因）

`HwNotchSizeUtil` 保留了官方的 `ro.config.hw_notch_size` 通路，但**没有实现官方那套
`calculateSize()` 缩放**（它依赖 `WindowManagerGlobal.getWindowManagerService()`、
`persist.sys.rog.width/height`、`getResolutionSize()` 等 hidden 部件）。这条分支只在
「设备上真的存在该 EMUI 属性」时才可能走到，而本移植的目标是**通用安卓 + 华为眼镜**，
不是 EMUI 手机；与其半吊子实现一个可能算错的缩放，不如按现状记录：
属性存在时返回配置里的原始值，属性不存在（目标机型）时走真实 `DisplayCutout`。

### 37.5 验证状态

- 源码已改：是（3 处修复）。
- 构建通过：七个模块 r31。
- 签名/描述符检查：六个已扫模块全通过。
- 单项实测 / 跨模块实测：未做（手机断联、眼镜不在位）。

---

## 38. 兼容层改为「只用公开 API」：hidden 反射全部清掉（2026-09-16 第二十三轮）

口径来自用户：**「将代码改为公开 API，拒绝搞回退」**。也就是说兼容层里不再保留
「先反射 hidden、失败再退到别处」这种两层写法：

- hidden 方法一律**不再反射**（反射在 targetSdk≥28 上本来就会被拦，留着等于埋雷）；
- 能用公开 API 达成同一件事的，就**只写那一条**（不是"回退"，是这条路径本身）；
- 没有任何公开等价物的，就**如实做不了**：记一次日志 + 返回该公开约定里的
  「未知/不可用」值，绝不再造一个假成功。

### 38.1 逐条改动

| 类 / 方法 | 官方（hidden） | 现在的公开写法 |
| --- | --- | --- |
| `ContextEx.currentApplication()` | 反射 `ActivityThread.currentApplication()` 兜底 | 删掉反射兜底。只留两条公开来源：兼容层 provider 注入的 context、Unity 自己的 `UnityPlayer.currentActivity`；都没有就返回 null |
| `PowerManagerEx.wakeUp` | `pm.wakeUp(time, reason, details)` | 只走公开的 `FULL_WAKE_LOCK \| ACQUIRE_CAUSES_WAKEUP` 短暂持锁（点亮屏幕） |
| `PowerManagerEx.userActivity` | `pm.userActivity(t, e, f)` | 只走公开的短暂 `PARTIAL_WAKE_LOCK`；注释写明它不进系统那份 user-activity 统计 |
| `UserHandleEx.getIdentifier` | `handle.getIdentifier()` | 只用公开的 `handle.hashCode()`（AOSP `UserHandle.java` 的实现就是 `return mHandle;`） |
| `HwNotificationListenerEx.registerAsSystemService` | `service.registerAsSystemService(...)` | 只调公开的 `NotificationListenerService.requestRebind(component)` |
| `HwNotificationListenerEx.unregisterAsSystemService` | `service.unregisterAsSystemService()` | 公开 API 没有这一步：如实记日志不动作 |
| `InputManagerEx.injectInputEvent` | `im.injectInputEvent(e, mode)` | 公开 API 没有注入能力（`INJECT_EVENTS` 是 signature\|privileged）：记一次日志返回 false |
| `InputManagerEx.injectInputEventByDisplayId` | `HwInputManager` / hidden `DisplayManager.injectInputEvent` | 同上，返回 false |
| `AudioServiceEx.setBluetoothA2dpOn` | AIDL `IAudioService.setBluetoothA2dpOn` | 无公开等价物：记一次日志，用户从系统 UI 切音频输出 |
| `ServiceStateEx.getConfigRadioTechnology` | `state.getConfigRadioTechnology()` | EMUI 专有概念：返回 0（AOSP `NETWORK_TYPE_UNKNOWN`） |
| `HwFoldScreenManagerEx.isFoldable/getDisplayMode` | `HwFoldScreenManager`（华为框架类） | 无公开等价物：返回中性值（不可折叠 / 模式未知）+ 日志 |
| `ApplicationInfoEx.readHwFlags` | `ApplicationInfo.hwFlags`（hidden 字段） | 返回 0 + 日志 |
| `WindowManagerEx.LayoutParamsEx.addHwFlags` | `LayoutParams.extraFlags`（hidden 字段） | 只记在包装对象上 + 日志 |
| `IVRSystemServiceManagerEx.isVirtualScreenMode` | boot classpath 版接口方法 | 返回 false + 日志（该接口方法在通用安卓上不存在） |

清完之后，兼容层里**只剩两处反射**，且都是应用侧自己的类，不是平台 hidden API：
`com.unity3d.player.UnityPlayer`（Unity 运行时随 APK 分发）在 `ContextEx` 与
`HwNotchSizeUtil` 里各一处。可以用一条命令复核：

```
rg -n "java\.lang\.reflect|Class\.forName|getField\(" shared/java
```

### 38.2 验证状态

- 源码已改：是。
- 构建通过：七个模块 r32。
- 签名/描述符检查：待 r32 全量构建完成后复跑。
- 单项实测 / 跨模块实测：未做（手机断联、眼镜不在位）。

---

## 39. 真机主线打通：从「卡在连接 VR 眼镜」到原空间跑起来（2026-09-16）

本轮从用户现场现象出发（「华为VR 打开还卡」「眼镜已经连上」），逐条定位到五处
平台层缺口，全部是「原来靠 EMUI 系统 UID / 框架角色才成立」的东西。原版
Java 与 Unity 逻辑一行未改。

### 39.1 安装期就失败：二进制 manifest 缺 `authorities` 资源映射

`com.huawei.hvrsdkserverapp` 的 manifest 是二进制的（apktool `-r` 保留），
它原本**没有任何 provider**，所以 AXML 的 resource map 里没有
`android:authorities`(0x01010018)。`axml_edit` 只是把属性写进 start-element，
resource map 没同步，平台解析时看不到这个属性：

    INSTALL_PARSE_FAILED_MANIFEST_MALFORMED: <provider> does not include authorities attribute

修法：`axml_edit.BinaryXml.ensure_resource_id(resource_id, attribute_name)` ——
resource map 是「字符串池索引 → 资源 ID」的数组，需要按名字在池里的下标扩容并
填值（不是简单 append）。修好之后同一个 APK 直接安装成功。

### 39.2 子进程拿不到 application context（`vr_system` 因此跨不了进程）

兼容层的 `ContextEx` 靠注入的 `HvrContextProvider` 拿 application context，而
provider 只在**它被声明的那个进程**里实例化。各模块的组件大量跑在独立进程：

| 包 | 独立进程 |
| --- | --- |
| com.huawei.vrlauncherx | `com.huawei.vrservice` |
| com.huawei.himovie.vr | `:player` / `:pushservice` |
| com.huawei.vrvirtualscreen | `:appDisplay` / `:userGuide` |
| com.huawei.vrhandle | `:VRHandleService` |
| com.huawei.hvrsdkserverapp | `...service.ArvrRuntimeService` / `...WlStrmActivity` |
| com.huawei.vrservice | `com.huawei.vrinstaller` |

现场日志（每个进程都在刷）：

    W HvrServiceManagerEx: no application context; vr_system stays process-local

发布方拿不到 Context → `vr_system` 只留在进程内存里 → 谁也别想查到。

修法：`patches/patch_context_provider_processes.py` 给每个独立进程再声明一个
同类的 provider 实例（authority `<包名>.hvrcompat.ctx1/2…`，不导出，带
`android:process`）。文本 manifest 与二进制 manifest 两条路都实现了。

### 39.3 消费者只查本地表：`ServiceManagerEx.getService` 少了注册表那一步

`addService` 会往桌面托管的注册表发布，但 `getService` **只查本地 map**。
桌面的 Unity 空间跑在主进程，发布方跑在 `com.huawei.vrservice`，于是：

    W HvrVrSystem: vr_system is not registered; returning null
    I UnityPlayerActivity: IVRSystemServiceManager is null
    I UnityPlayerActivity: onDestroy: Not in VrMode. Then return!

修法：`getService` 本地未命中时问一次注册表（`content://com.huawei.vrlauncherx.registry`
的 `getService`），拿到的 binder 用 `isBinderAlive()` 做缓存校验；查不到仍然返回
null，让调用方走它自己的分支。

### 39.4 后台启动 Activity 被拦（Android 10+ BAL）

准备好之后桌面要去起 `VRPrepareActivity` / `MainActivity`，而它当时的进程状态是
`FOREGROUND_SERVICE`：

    E ActivityTaskManager: Background activity launch blocked! ... callingPackage: com.huawei.vrlauncherx
    E ActivityTaskManager: Abort background activity starts from 10421
    I ActivityTaskManager: START u0 {...VRPrepareActivity} ... (BAL_BLOCK) result code=102

EMUI 上这一步是框架发起的，本来不受 BAL 约束。通用安卓上桌面**自己就声明了**
`SYSTEM_ALERT_WINDOW`（原版声明，用于悬浮窗），而持有该权限正是官方文档列出的
后台启动豁免之一，所以按原声明补授权即可，不改代码：

    adb shell appops set <包> SYSTEM_ALERT_WINDOW allow

### 39.5 `WRITE_SECURE_SETTINGS` / `WRITE_SETTINGS`（原版靠系统 UID）

- `com.huawei.vrlauncherx` 的 `Hw6dofMonitor` 构造里写
  `Settings.Global.allow_observe_hw6dof_events`，普通应用需要
  `WRITE_SECURE_SETTINGS`；缺了它 `VRService.onCreate` 直接崩，整个环境起不来：

      java.lang.RuntimeException: Unable to create service com.huawei.client.vrservice.VRService
      Caused by: java.lang.SecurityException: Permission denial, must have one of: [android.permission.WRITE_SECURE_SETTINGS]
          at n1.f.t(CommonUtil.java:4) -> q1.a.f -> x0.a.<init>(Hw6dofMonitor.java:4)

  该权限的 protectionLevel 含 `development`，所以 `pm grant` 可用。
- Runtime 的横屏锁定走 `Settings.System`，需要 `WRITE_SETTINGS`；这条由 role
  管理，`pm grant` 会被拒，只能用 `appops set ... WRITE_SETTINGS allow`。

已并入 `install-six.ps1`（appops + pm grant 清单一起维护）。

### 39.6 `what=0x835`（getVRModeState）：状态由真实硬件推进，不是常量

桌面 `t0/b.isVRmode()` → `z0/c.n()` 向系统服务查 `0x835`，结果按位取第 0 位。
我们此前一律回 0，于是用户空间一起来就自杀：

    I UnityPlayerActivity: Not in VrMode. Then return!
    I HVRActivity: Not in VrMode. Then return!

`VrSystemActor` 现在维护 `vrMode`：把环境推进到「戴上」那一步（发 `0x3eb`，原版
框架在用户戴上眼镜时发的就是它）之后置真，眼镜拔掉立刻清零；`SystemServiceBinder`
用它回答 `0x835`。其余查询（`0x836` 电量 / `0x837` 亮度 / `0x838` 接近 /
`0x83a` / `0x83c` 头盔型号 / `0x83d` 固件版本）**没有数据源，保持原样不改**，
不编造数值。

### 39.7 真机结果

SM-F731U1 + HUAWEIAV03，2026-09-16：

- 眼镜在位 → Runtime 监督服务 → 绑定桌面 `VRService` → 握手 → `0x1`/`0xf`/`0xf`/`0x3eb`
  → `VRService_Client_VRManager: start 3D Launcher`；
- 桌面主进程起来，Unity 空间渲染原场景与原提示（「手柄指向前方并长按扳机键
  可将视角及射线重置」），`HvrVrRegistry: published vr_system` 持续生效；
- 眼镜显示 3200x1600、display 8 有独立 `DefaultTaskDisplayArea_d8`。

截图：`build/vr-phone2.png`（3200x1600 双目画面）。

### 39.8 还没做完的

- **异步投屏**：现在手机屏仍在镜像双目画面（Huawei 官方是异步、手机不镜像）。
  本轮没做，按既定口径只保留官方接口。
- **手柄**：Unity 侧仍是 `HVRController: Right controller is not available`，
  CF20 还没把按键事件送到空间。
- 手机触控进 VR、视频/投屏进出空间、拔插恢复未验。
- 状态：**未完成**。

## 40. 手柄链路定位：CF20 当前没有和手机配对上（2026-09-16）

本轮跟着主线查「Unity 报 `Right controller is not available`」这一环。结论是
**桌面侧代码链路没有断，物理设备不在**：`VrControllerManager.mUsingCtrl == null`
是因为手柄模块自己的设备列表为空，而列表为空是因为这台手机上 CF20 已经没有配对了。

真机证据（SM-F731U1，无线 adb `<phone-ip>:5555`，HUAWEIAV03 在位、原 VR 空间在跑）：

- `dumpsys bluetooth_manager`：`Bonded devices: 1`，只有 `ATUMTEK`（Hogp），没有
  CF20；`HidHostService` 里该设备 `HID connection state=0`。
- 手柄模块数据目录里只有 `shared_prefs/android.app.ActivityThread.IDS.xml`，没有
  `sp_device_storage.xml`；即 `VrSdkApi.k2()`（从 `sp_device_storage` 恢复设备）
  没有可恢复内容。
- 手柄服务进程日志：`VrSdkApi: enter getUsedDeviceList, mDeviceInfoList size = 0`
  → `VrHandleReconnectController: not connected to any device, skip`。
- 桌面 Runtime 每 20 秒发的原始 action（`com.huawei.iconnect.ACTION_RECONNECT_MSG`）
  确实进了原服务：`VRHandleService.n1()` → `m1()` → `VrHandleReconnectController.e0()`，
  但 `e0()` 依赖已存设备地址，没有就只打日志跳过——这条路径本身是原版逻辑，不需要改。
- 原版配对入口是手柄模块自己的 UI（`SplashActivity` → `MainActivity`）。真机拉起后
  目前卡在三处**平台层**问题（都不是原版 Java 逻辑的问题）：
  1. Android 16/Samsung 弹「此应用与最新版 Android 不兼容」。该包
     `minSdk=26 / targetSdk=31`，不是低 targetSdk 拦截，来源待查，先记录。
  2. `WelcomeFragment` 的隐私声明判断 `AgreementUtils.a()` 读
     `r0/e5.o(context, "10000", "vr_handle_user_agree")`，在任何时候都读到空值，
     所以每次进入都要求重新点同意。
  3. UI 走到「连接 VR 眼镜」页时，`Hw6dofUtil.a()` 里 `UsbManager.getDeviceList()`
     返回空（日志 `getSpecificDevice, usbDeviceList is empty`），而 `dumpsys usb`
     里明明有 `HUAWEI GLASS CV10` / `HUAWEI GLASS HID`。

下一步（顺序不能颠倒）：

1. 手柄开机并进入配对：按原 UI 提示在扫描页按手柄任意键完成配对；
2. 配对成功后，桌面 Runtime 已有的原始 `com.huawei.iconnect.ACTION_RECONNECT_MSG`
   常驻重连会走 `e0()` → `connectGatt`，填上 `mDeviceInfoList`，Unity 才能拿到控制器；
3. 上面三处平台层缺口逐个按「同名接口 + 通用 Android 实现」补齐，不改原版流程。

状态：**未完成**。

## 54. 口径纠正：保留通用联网，只拦华为服务器；并补齐之前漏搬的通用库

用户明确纠正（2026-09-16）：**不要把应用做成完全离线环境，只要拦住发往华为
服务器的请求**。之前「去掉 INTERNET」的做法方向错了，它会逼着原版在线代码走
异常分支（真实后果：主应用 `HuaweiCloudModule` 因 DNS 被拒抛 FATAL 打死进程、
WiFi 名称取空导致 `WifiControllerQ` 里 `Substring` 负长度等）。

### 54.1 按原包恢复联网权限

对照 `aapt2 dump permissions 原包/*.apk`，逐包补回**原包本来就有**的通用权限
（脚本 `patches/patch_restore_network_permissions.py`；vrservice 是二进制清单，
走 `patch_vrservice_manifest.py` 的 ADDED_PERMISSIONS）：

| 包 | 恢复的权限 |
| --- | --- |
| com.huawei.appmarket.vr | INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE / CHANGE_WIFI_STATE |
| com.huawei.himovie.vr | INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE |
| com.huawei.vrhandle | INTERNET / ACCESS_NETWORK_STATE |
| com.huawei.vrlauncherx | INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE |
| com.huawei.vrservice | INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE |

同一口径下同步调整：

- `build/build-module.ps1` 去掉「发现 INTERNET 就构建失败」的断言；
- `patches/patch_offline.py` 不再把 INTERNET / CHANGE_WIFI_STATE 当「纯在线权限」摘除；
- 华为专有权限（hwid / ACCESS_UDID / MDM 等）与纯华为服务组件仍按原策略清理，
  因为它们的存在意义就是访问华为服务器。

真机校验（r51 装机后）：五个包 `dumpsys package` 里 `android.permission.INTERNET`
全部存在。

### 54.2 之前漏搬的通用库

`patches/patch_official_platform_classes.py` 的 EXCLUDE 里把 `com/huawei/okhttp3/`、
`com/huawei/networkit/` 也当成「在线链路」排除了 —— 它们其实是通用 HTTP / DNS
库（原包本来就用），不搬会让原代码缺类。现在判定改为「是不是通用库」：

- 通用库（okhttp3 / networkit）→ 按官方字节码搬；
- 华为服务 SDK（hianalytics / hms / agconnect / updatesdk / hwid / phoneservice /
  deviceshare / vrinstaller）→ 仍不搬，其调用方继续按「摘在线入口」处理。

状态：**未完成**。

## 53. 准备页回退：VR 模式状态再提前到「识别到眼镜」那一刻

§47.1 把 `vrMode` 提前到 actor 发 `0x1` 的步骤，但真机再进一次（14:22:34.905）
仍见到一次：

    I/VrSystemActor: system service call what=0x835 ...
    W/VRService_Client_VRUtils: should exit when glass out.
    E/VRService_Client_VRPrepareActivity: VRPrepareActivity should not show when glass out.

说明桌面在 actor 发出 `0x1` **之前**就已经起了准备页。把置位点再往前提到
`onHelmetUp()`（真实眼镜外接屏被识别到的那一刻）：仍然只在 `helmetPresent`
为真时置位，拔掉眼镜 `onHelmetDown` 立刻清零，没有伪造任何状态。

构建：Runtime r47。

真机复核（14:24 重新进入，r47 已装）：

- `should not show when glass out` / `should exit when glass out` 在**本轮进入里 0 次**
  （日志里唯一一条是 14:22:34.905 的旧记录，属 r47 安装之前那一次进入）；
- 流程照常：`VRPrepareActivity` 正常销毁 → `start 3D Launcher` →
  `VrControllerManager: UsingCtrl : DefaultController, status : 5` 手柄就位；
- `proximity value` / `battery info` / `ttyUSB1` 0，`FATAL EXCEPTION` 0。

### 同轮验证到的其它结果

- 接近/电量的 Android 化已生效：`proximity value` / `battery info` /
  `getProximityNative` / `getBatteryNative` / `ttyUSB1` 全部 **0**；
- `UpgradeGlass` 只剩 7 条，都是插拔瞬间 `/dev/hwvr1` 还没被 KSU 模块重建时的
  `isVRHelmetConnect -> OpenDevice failed: No such file`，属瞬时状态；
- `FATAL EXCEPTION` 0。

状态：**未完成**。

## 52. 接近/电量接到真正在跑的消费方（vrservice 的 VRHelmetUtils）

§49.3 把 Android 数据源接到了 Runtime 的 `SystemServiceBinder`（桌面 `0x836`/`0x838`）。
真机复核发现：进入 VR 的一整轮里桌面**只问了 `0x835`**（118 次），`0x836`/`0x838`
一次都没有 —— 这条路径在当前流程里根本没被调用。

真正在跑的消费方是 `com.huawei.vrservice` 自己的 `VRHelmetUtils`：

    getProximityNativeJNI()I -> getProximityNative()  (native, 走 /dev/ttyUSB1)
    getBatteryNativeJNI()I   -> getBatteryNative()    (native)

真机日志 `E/UpgradeGlass: proximity value -1` / `battery info 0, 0, 0` /
`get glass proximity fail!` 就来自这两个 native（证据见
docs/evidence/proximity-battery-2026-09-16.md：CV10 的 HID 报告里没有接近/电量）。

按「通用安卓直接用 Android 的」口径，`patches/patch_helmet_proximity_battery_android.py`
只替换这两个 **Java 包装方法**：

    getProximityNativeJNI() -> VrAndroidSensors.proximity()       (Sensor.TYPE_PROXIMITY)
    getBatteryNativeJNI()   -> VrAndroidSensors.batteryPercent()  (BatteryManager)

私有 native 原样保留（不再被调用），返回语义不变：取不到仍是 -1。

构建：vrservice r46。装机后清 log 观察 40 秒：`getProximityNative`/`getBatteryNative`
相关日志 **0**、`get glass proximity fail` **0**、`ttyUSB1` **0**、无 FATAL。
（该窗口里 DeviceNodeMonitor 本身没打印，属于状态相关；补丁生效与否以「这两个
包装方法不再落 native」为准，下一次摘戴/进入流程会自然覆盖到。）

状态：**未完成**。

## 51. 按 tag 关闭「如实回答」造成的 ERROR 刷屏（2026-09-16）

`E/HvrFramework: CallStaticBooleanMethodV == false`（45 秒 2700+ 条）与
`E/VrHelmetExt: mVRDeviceExt is null`（同窗口 1300+ 条）经取证不是缺陷：
native SDK 每帧问 `VrFramework.isHW6DoFHeaderAvailable()`，本机是
CV10 眼镜 + CF20 手柄（3DoF），`VrParamsRequester` 如实返回 false
（`I/VrParamsRequester: Huawei 6Dof Header is false` 同窗口 1.4 万条），
native 把这个正常结果按 ERROR 级别打出来。**改成 true 就是伪造 6DoF，不做。**

用户要求先关掉这段打印。做法用平台自带的按 tag 日志级别，不动任何代码：

    setprop log.tag.HvrFramework ASSERT
    setprop log.tag.VrHelmetExt ASSERT

真机验证（清 log 后 20 秒）：`E/HvrFramework` **0**、`E/VrHelmetExt` **0**，
SDK 返回值与行为完全不变。已写进 `install-six.ps1`（可随时删掉那两行，或用
`setprop log.tag.HvrFramework VERBOSE` 恢复查看）。

`I/VrParamsRequester` 保持 INFO：它同时承载 `queryVrStartTime` 等有用信息；
需要时同样一条 `setprop` 就能静音。

状态：**未完成**。

## 50. 主应用里残留的 hidden API 反射（不需要眼镜就能修）

单独拉起 `com.huawei.appmarket.vr` 后日志里固定出现：

    E/ei.appmarket.vr: hiddenapi: Accessing hidden method Landroid/view/DisplayInfo;-><init>()V ...
        from Lcom/google/vr/cardboard/AndroidPCompat; ... using reflection: denied
    E/AndroidPCompat: Failed to fetch DisplayCutout from Display:
        java.lang.NoSuchMethodException: android.view.DisplayInfo.<init> []
    E/CutoutSpecification: According to SVG definition, it shouldn't happen

Cardboard 的 `com.google.vr.cardboard.AndroidPCompat.getDisplayCutout(Display)` 为了拿
刘海信息反射构造 `android.view.DisplayInfo`，而该构造器在 Android 9+ 是 hidden API，
被平台直接拒绝 → 拿不到 cutout。

修法（`patches/patch_cardboard_cutout_api.py`）：只把该方法换成公开 API
`Display.getCutout()`（API 28 起），再用同包已有的
`DisplayCutoutCompat.create(Object)` 包装；方法的入参/返回值/失败返回 null 全部不变。
同文件其它方法（`doesWindowExtendIntoCutoutArea` / `getDisplayRect`）不动。

真机（13:52，主应用 r45；因签名不一致需卸载重装）：

| 指标 | 修前 | 修后 |
| --- | --- | --- |
| `E/AndroidPCompat` | 8 | **0** |
| `hiddenapi ... DisplayInfo` | 4 | **0** |

`E/CutoutSpecification` 仍在，但它是 **system_server（PID 27495）**在折叠副屏
DOZE 时打的系统日志，与本移植无关。

状态：**未完成**。

## 49. SDK init 从未被调用（7 万 + 8 千条错误的共同根因）与 Android 侧数据源

### 49.1 根因

日志量最大的两条其实同源：

    E/HvrFramework: [HvrFramework.cpp:CallStaticBooleanMethod](463): CallStaticBooleanMethodV == false   (70199)
    E/VrHelmetExt: mVRDeviceExt is null                                                                   (8267)

原版 Java 侧：

    VrFramework.isHW6DoFHeaderAvailable()
      -> if (VrFramework.mAppActivity == null) { Log.e("VrFramework","App activity is null"); return false; }
    VrHelmetExt.isEnable()
      -> if (mVRDeviceExt == null) { ... VrInteractiveDeviceManager.getInstance().init(mActivity) }
      （mActivity / mVRDeviceExt 只在 VrHelmetExt.init(Activity) 里建立）

而 `VrFramework.init(Activity)` / `VrHelmetExt.init(Activity)` 在七个包里
**没有任何调用点** —— EMUI 上这一步由系统/框架在 VR 应用起来时触发，通用安卓没人替它调。
于是 `mAppActivity` 恒为 null：native 每帧问一次静态 boolean 得到 false（7 万条），
`VrHelmetExt` 也永远建不出 `VrInteractiveDeviceManager`（8 千条）。

### 49.2 修法

- 新增 `shared/java/com/huawei/vrframework/compat/VrFrameworkBootstrap.java`：
  用反射调用 SDK 的 `VrFramework.init(Activity)` 与
  `VrHelmetExt.getInstanceObject().init(Activity)`（反射是为了避开 LibUpdateClient
  动态装载 SDK 代码带来的类加载器差异；调用失败如实记录，不伪造成功）。
- `patches/patch_vrframework_bootstrap.py`：在
  `com/huawei/vrlab/HVRActivity;->onCreate` 末尾（`LibUpdateClient.runUpdate()` 之后、
  SDK 代码已装载）插入一次该调用；只插一处，其余不动，脚本断言原始片段唯一。

构建：桌面 r43。

### 49.3 接近/电量改用 Android 自己的数据源（用户口径）

CV10 眼镜的 HID 报告里没有接近(report 4)/电量(report 8)（证据见
`docs/evidence/proximity-battery-2026-09-16.md`）。按「目标是通用安卓，可以直接用
Android 的」这一口径：

- 新增 `shared/java/com/huawei/vrframework/compat/VrAndroidSensors.java`：
  接近取 `Sensor.TYPE_PROXIMITY`（本机真实传感器，0=远离 / 1=贴近 / -1=无数据源），
  电量取 `BatteryManager.BATTERY_PROPERTY_CAPACITY`（CV10 由手机供电、没有独立电池）。
- `SystemServiceBinder` 现在回答桌面：`0x836` = 电量百分比、`0x838` = 接近状态；
  取不到仍然返回 -1（不可用），不编数值。其余查询（0x837/0x83a/0x83c/0x83d）不变。
- 语义差异如实记录：Android 的接近传感器测的是「手机靠近物体」，不是「眼镜戴在头上」，
  它只是同一物理量的通用等价信号。

构建：Runtime r44。

### 49.4 验证状态

装机时眼镜处于**物理断开**状态（`dumpsys display` 只剩两块内置屏，actor 日志
`refresh(start) ... helmet=false`），所以 r43/r44 的真机效果要在重新插入眼镜后复核：
预期 `CallStaticBooleanMethodV == false` 与 `mVRDeviceExt is null` 显著下降，
并且桌面能问到真实的电量/接近值。

状态：**未完成**。

## 48. 全量日志复扫（2026-09-16 13:30 会话，~33 万行）

按 tag 统计错误条数后的分诊结果：

| 条数 | tag / 消息 | 判定 | 处理 |
| --- | --- | --- | --- |
| 70199 | `E/HvrFramework: [HvrFramework.cpp:CallStaticBooleanMethod](463): CallStaticBooleanMethodV == false` | 待查：native 经 JNI 调了一个 Java static boolean 方法并得到 false，频率与渲染/状态查询同频 | 专项排查中 |
| 8267 | `E/VrHelmetExt: mVRDeviceExt is null` | 待查：外接设备管理器没被初始化（EMUI 上由系统触发 init） | 专项排查中 |
| 7969 | `E/VRRenderImplCommon: [VRRenderImplCommon.cpp:chooseFrame](184): choose frame ...` | 待查：需要完整消息判断是丢帧还是异常 | 专项排查中 |
| 396 | `E/DrmLibFs ...` | Samsung 系统 DRM 文件日志 | 与本移植无关 |
| 135 | `E/NotificationService: Suppressing notification from package com.huawei.vrhandle by user request.` | 用户关闭了该应用通知 | 设置行为，非缺陷 |
| 111 | `E/bta_gattc_main: Ignore unknown conn ID` | 手柄断线/重连瞬间的 BT 栈噪音 | 瞬时，重连后消失 |
| 7+7 | `E/HvrControllerClass: GetData arrayLen(0) invalid` + `E/DefaultController: data length invalid 0` | 手柄当前是掉线态（`UsingCtrl status -6`），`getControllerData` 返回空数组 | 手柄唤醒/重连后消失，非代码缺陷 |
| 3 | `E/ScreenControl: Not found eglDirectModeHISI` / `eglGetProcAddress ShareBufferMode fail` / `stopFrontBufferDisplay return failure` | 华为 EGL 直显/共享缓冲扩展在 Adreno 上不存在 | 属「异步投屏只保接口」的既定范围，见 §39.8 |
| 2 | `E/ActivityThread: Failed to find provider info for com.huawei.vrlauncherx.provider` | 原版 `MainActivity.queryUuid()` 查 `content://com.huawei.vrlauncherx.provider/uuid`；该 provider 不在六个包里（EMUI 侧系统组件），原代码自带 try/catch 失败分支 | 无真实来源，保持失败分支；不伪造 UUID |
| 13 | `E/Watchdog: !@Sync: heap(MB): 148/150 ...` | 桌面进程堆接近上限 | 记录为性能风险项，后续观察 |
| 其余 | `BatteryDump`/`thermal`/`SemContext`/`ClipboardService`/`PhoneInterfaceManager`/`ActivityManager(non-protected broadcast)` | 三星系统自身日志 | 与本移植无关 |

状态：**未完成**。

## 47. 准备页被误退 + 前台 activity 取不到（2026-09-16）

### 47.1 `VRPrepareActivity should not show when glass out.`

调用链（launcher，未改动）：

    VRPrepareActivity.onCreate
      -> Lz0/c;->A(Context)Z            # shouldExitWhenGlassOut
           -> VRSystemServiceManagerImpl.get(ctx).isVRMode()
           服务为空 或 isVRMode()==false  ->  return true
      -> 打日志 + moveTaskToBack(true) + finish()

根因：`isVRMode()`（我们兼容层用 what=0x835 回答）原本只在 actor 走到最后一步
（发 0x3eb「戴上」）才置真，而桌面的准备页是在那**之前**创建的，于是必被打回。
原版语义里「进入 VR 模式」是从开始准备那一刻算起的。

修法：`VrSystemActor.startStep`（发 0x1「开始」那一步）就置 `vrMode=true`，
仍然只在 `helmetPresent`（真实眼镜外接屏在位）时置位，`onHelmetDown` 立刻清零。

### 47.2 `error, RunningTaskInfo wrong.`

调用链：`w0/b.v(Context)`（VRManager 记「当前前台 activity」）→
`Lz0/c;->g(Context)` → `ActivityManager.getRunningTasks(1)` 读 `topActivity`。

Android 5 起 `getRunningTasks` 只返回**调用者自己的**任务，看别人的任务要
`android.permission.REAL_GET_TASKS`（签名级，通用安卓拿不到），真机上经常返回
空列表或 topActivity=null —— 于是
`top activity is null` / `error, RunningTaskInfo wrong.`。

修法：新增 `VrTopActivity.current(Context)`，用公开 API
`ActivityManager.getAppTasks()`（无需权限）取本应用自己的栈顶；
`patches/patch_top_activity_source.py` 把 `z0/c.g()` 整体换成一次该查询，
取不到仍然返回 null（与原版失败分支一致，不自造前台 activity）。

构建：桌面 r42 + Runtime r42。

### 47.3 验状态

真机（13:28–13:29，r42 装机后）：

- 全量日志里 `should not show when glass out` 与 `RunningTaskInfo wrong` 均**零命中**；
- VR 空间正常运行（`HVRInputMoudule processPointers` 持续）；
- 准备页完整路径要重走一次「进 VR」流程才能覆盖，留给下一次拔插复核；
- 手柄此时状态是 `UsingCtrl : DefaultController, status : -6`（掉线态），
  需要按一下手柄把它唤醒——这是 CF20 自己的省电行为，不是代码缺陷。

状态：**未完成**。

## 45. 手柄掉线后重连走不通：Nearby 壳服务把原版兜底堵死（2026-09-16）

### 现象

手柄中途掉线后（真机 13:10：`deviceState = 4`、`not retry connect`、
`device connect fail in vr environment`），桌面一直 `mUsingCtrl == null`，
发原来的重连 action 也不恢复。

### 根因

手柄自身的重连链是原版逻辑：

    VRHandleService.p1()
      -> bindService(com.huawei.vrlauncherx/com.huawei.vrhandle.VrHandleReconnectService)
      绑定失败 -> "bind fail, directly trigger reconnect" -> 直接 connectGatt
      绑定成功 -> 等远端 Messenger 握手（永远等不到）

桌面那个服务只是华为 Nearby SDK 的壳（`VrHandleReconnectService.e()`
→ `Ls1/b.d()` → `com.huawei.nearbysdk.NearbyAdapter`）。通用安卓没有华为 Nearby
平台服务，绑定「成功」但握手永远完不成，手柄端停在
`VrHandleReconnectController: service not init finish, cannot notify scan`，
原版自己的兜底路径被堵死。

另外，Runtime 之前发的是 `com.huawei.iconnect.ACTION_RECONNECT_MSG`
（iConnect 断线重连那条，手柄走 `m1()`，只查已连接列表），不触发重连。

### 修复（三处，全部是可回退的最小改动）

1. `patches/patch_vrhandle_reconnect_component.py`：摘掉桌面包里那个 Nearby 壳
   `<service android:name="com.huawei.vrhandle.VrHandleReconnectService" .../>`，
   让原版的 `bindService` 如实失败，走它自己的
   "bind fail, directly trigger reconnect"。（这是移除「依赖缺席平台」的组件，
   不是整体删 service；脚本断言原始行只出现一次。）
2. `VrSystemActor` 的重连 action 换成原版 VR-start 契约
   `com.huawei.vrservice.ACTION_RECONNECT_MSG`（手柄 intent-filter 里声明的就是它，
   `p1()` 也按它分支），保留原来 3/8/15/25 秒 + 每 20 秒的节奏。
3. 手柄进程若已在旧状态里（`h` 是旧值），重启一次手柄服务进程即可重新评估；
   之后掉线会自动走直接重连。

### 真机验证（13:14–13:15）

    I/vrhandle_VrHandleService: enter handleIntent, act=com.huawei.vrservice.ACTION_RECONNECT_MSG
    D/BluetoothGatt: connect() - device: <cf20-mac>
    I/vrhandle_VrSdkApi: processDeviceConnectionStateChange, deviceState = 2
    I/VrControllerManager: onStatusChanged sender DefaultController, status 5, index 0
    I/VrControllerManager: Change to controller DefaultController and lock

构建：桌面 r39 + Runtime r39。

状态：**未完成**。

## 46. VR 桌面崩溃：在线云入口在无 INTERNET 权限下抛未捕获异常（2026-09-16）

### 现象

用户报告「VR 桌面崩溃报错」。真机日志（13:16）里进程是这么死的：

    W/HwVrLauncherX_HuaweiCloudModule: post featured app onFailure
    E/AndroidRuntime: FATAL EXCEPTION: o3.w Dispatcher
        java.lang.SecurityException: Permission denied (missing INTERNET permission?)
        Caused by: android.system.GaiException ... EAI_NODATA
        Caused by: android.system.ErrnoException: android_getaddrinfo failed: EPERM
    E/Unity: ArgumentOutOfRangeException: Cannot be negative.
    E/VRRenderWalleImpl: vsync error        (连续多帧)
    I/HvrFramework: ForceProcessExit IN
    I/wei.vrlauncherx: System.exit called, status: -970643582

所以「崩溃」的起点不是渲染，是**在线云模块**：离线包按已批准范围去掉了
`android.permission.INTERNET`，但华为云的「精选应用 / VR 货架」代码仍在
`MainActivity` 启动时初始化，DNS 被拒后以 FATAL EXCEPTION 打死进程；渲染线程
随后 vsync 失败，原生框架走 `ForceProcessExit`。

### 入口与修复

调用链（launcher smali）：

    com.huawei.vrlauncherx.MainActivity:2089
      -> Lu2/d0;->q(Landroid/content/Context;)V        # HuaweiCloudModule
         -> 构造 client.vrShelves 请求（在线货架）-> o3.w Dispatcher 发网络

`u2/d0.q(Context)` 整体就是这条在线请求的组装与派发，没有任何本地行为，属于
已批准的「摘在线入口」范围。`patches/patch_offline_cloud_entry.py` 把该方法改成
空实现（断言原方法体里存在 `"client.vrShelves"`，改完再断言它已消失）。

### 真机验证（13:21，桌面 r41 + vrservice/vrhandle/vrvirtualscreen r40）

    （无 FATAL EXCEPTION / 无 HuaweiCloudModule / 无 ForceProcessExit / 无 vsync error）
    I/UnityPlayerActivity: HVRActivity find Context Constructor
    I/VrControllerManager: onStatusChanged sender DefaultController, status 5, index 0
    I/VrControllerManager: Change to controller DefaultController and lock
    I/VrControllerManager: UsingCtrl : DefaultController, status : 5

状态：**未完成**。

## 44. 射线偶尔点不中：原版 Unity 输入模块的空指针缺陷（2026-09-16）

### 现象

用户反馈：手柄按键正常，但射线偶尔打不中画面里的按钮（不是完全打不中）。

### 根因

桌面 Unity 程序集里 `HVRInputModule.UpdateAnchorPos(HVRLinePointer, Vector3)`
每个「无命中目标」帧都会抛一次 NullReferenceException，被外层 try/catch 吞掉并打日志：

    I/ (Unity): System.NullReferenceException
      at HVRInputModule.UpdateAnchorPos (.HVRLinePointer pointer, Vector3 intersectionPosition)

反编译原始 IL 后确认原版写法是：

    if (nowGaze == lastGaze) {                    // 同一目标，或都为 null
        if (nowGaze != null) pointer.OnLineHover(pos, true);
        if (lastGaze.ToString().Equals("null"))   // 对 Unity 伪 null 解引用 → NRE
            pointer.OnLineExit(pos, false);
    }

EMUI 上有注视指针兜底，这条路不常走到；通用安卓没有注视指针，于是
**OnLineExit 被异常跳过**：射线离开按钮后 hover 状态留在旧目标上，下次再瞄
同一个按钮只走 `OnLineHover`、不再走 `OnLineEnter` —— 表现就是「偶尔点不中」。

### 修复

只把那一处判断改成 Unity 伪 null 安全的形式，其余 IL 一个字不动：

    lastGaze.ToString().Equals("null")   ->   lastGaze == null
                                             （UnityEngine.Object::op_Equality）

IL 变换前后（工具输出）：

    before: IL_003c callvirt ToString | IL_0041 ldstr "null" | IL_0046 callvirt String::Equals
    after:  IL_003c ldnull            | IL_0041 call UnityEngine.Object::op_Equality | IL_0046 nop

工具与脚本：

- `tools/PatchUnityPointerNullGuard.cs`：C# + Mono.Cecil，对原始 IL 形态做断言
  （唯一一处 `ToString` + `ldstr "null"`），不匹配即报错退出、不写文件；
- `tools/patch-unity-pointer-null-guard.ps1`：编译并执行它（`tools/cecil/` 内附
  Mono.Cecil 与 netstandard）；
- 同一处理在旧仓 `porting/original-patches/desktop/PatchDesktop.cs` 的
  NULL POINTER GUARD 里已真机验证过。

### 口径说明（与「不改 assets 里的 Unity 程序集」的冲突）

本项确实修改了 `decode/com.huawei.vrlauncherx/assets/bin/Data/Managed/Assembly-CSharp.dll`。
判定理由：这不是自研改造，而是**原版代码自身的空指针缺陷**在「没有 EMUI 注视指针」
这个平台差异下必现；修法是把原意图（「lastGaze 没了就 OnLineExit」）用 Unity 官方
比较函数写出来，等价、最小、可审计、可回退（重跑一次 apktool 解码即还原）。
如果后续口径改为完全不碰 Unity 程序集，回退这一步即可，其余改动不受影响。

### 真机 A/B（SM-F731U1 + HUAWEIAV03，2026-09-16 13:08）

同一台机器、同一段触控手势（12 次上下滑动，把射线在场景里来回推过目标），
只换桌面包，日志各取同一长度：

| 桌面包 | `NullReferenceException` | `UpdateAnchorPos` 帧 | `processPointers` |
| --- | --- | --- | --- |
| r37（原版 IL） | 476 | 482 | （未单独计数） |
| r38（本补丁） | 0 | 0 | 470 |

补丁前是「每帧一次」——射线只要不在目标上就抛；补丁后同一路径一次都不抛，
同时输入模块照常处理指针（`processPointers` 持续输出），Unity 空间照常渲染
原场景与原提示卡（眼镜侧 3200x1600 双目取证：
`build/evidence/ray-guard-r38-glass-20260916.png`）。

复现方式（A/B 都走同一步）：装包 → `am start-foreground-service` 拉起 Runtime 的
`VrGlassWatchService` 重新走一遍主线 → `input swipe` 驱动射线 → 数日志。

状态：源码已改、构建通过、单项实测（本缺陷本身）完成。
**「射线点中按钮」的手感验收仍需用户实际操作**，不计入本轮通过项。

## 43. 黑屏复插恢复的原因 + 日志报错分诊（2026-09-16）

### 43.1 为什么重插眼镜就恢复了

上次误杀 zygote 之后，系统保留了眼镜那块外接屏（`HUAWEIAV03`，display 6）的
**设备条目**（`DisplayDeviceInfo` 里 `state ON`、亮度 0.49），但没有为它建立
逻辑输出：`dumpsys display` 的 `mViewports` 只剩手机自己的 display 0。
后果就是「屏在、亮着、没人往上面送图层」——应用侧 `VRRenderWalleImpl` 仍在
30fps 出帧，手机截屏也有画面，但眼镜全黑。

DisplayPort 这条输出通道（viewport / mirror 关系）只在链路重新协商时重建，
所以拔插一次就恢复。结论：**这套环境里不要杀 VR 相关进程去“重启”**；
需要重启就走「停止 → 重新握手」的既有流程，显示链路的状态跟着系统走。

（更正：事后复核，恢复画面之后 `mViewports` 里同样只有 display 0，
所以「viewport 消失」只是当时的观察之一，不能当作唯一判据。可复现的事实是
「杀进程 → 黑屏，拔插 → 恢复」，机制层面归因留给后续复核。）

### 43.2 日志分诊（`logcat` 全量过了一遍）

| 报错 | 判定 | 处理 |
| --- | --- | --- |
| `E/ActivityTaskManager: Background activity launch blocked! ... cmp=com.huawei.vrservice/.activity.VRPromptActivity`（callerProcState=FOREGROUND_SERVICE → BAL_BLOCK） | 真缺口：原版「插入眼镜 → 手机进入提示」被 Android 10+ 的后台启动限制拦住 | **已修**：`com.huawei.vrservice` 的二进制 manifest 补声明 `android.permission.SYSTEM_ALERT_WINDOW`（公开豁免途径，和桌面/手柄同一条），再 `appops set ... allow`。补丁在 `patches/patch_vrservice_manifest.py`，构建 r37。验证：`appops get` 从 `default` 变为 `allow` |
| `E/VRPrepareActivity: VRPrepareActivity should not show when glass out.` + `E/VRService_Client_VRUtils: error, RunningTaskInfo wrong.` | 待查：准备页在「眼镜不在位」判断下被拉起。和 §42 的屏名/在位判断同源，需继续核 | 未修，记入待办 |
| `E/UpgradeGlass: proximity value -1` / `get glass proximity fail!` / `battery info 0, 0, 0` / `open node /dev/ttyUSB1 error` | 无数据源：原版走的是 EMUI 专有节点 `/dev/ttyUSB1`（固件/接近/电量） | 不伪造，保持不可用；后续若要补，须从眼镜的真实 HID 特性报告解析 |
| `E/uawei.vrlauncherx: Failed to find parent 0x020600cd of bag 0x7f100123` | 重打包后资源 bag 的 parent 丢失 | 未修，记入待办（目前只影响个别样式/图） |
| `I/ (Unity): System.NullReferenceException at HVRInputModule.UpdateAnchorPos` | 原版 Unity 代码用 `lastGaze.ToString()` 对 Unity 伪 null 解引用；被 try/catch 吃掉 | 位于 `Assembly-CSharp.dll`，按现行口径不动 Unity 程序集；用户反馈的「射线偶尔打不中」另行定位 |
| `E/NotificationService: Suppressing notification from package com.huawei.vrhandle by user request.` | 用户把该应用通知关了，前台服务通知被折叠 | 行为提示，非代码缺陷 |

状态：**未完成**。

## 41. `vr_system` 缓存 binder 失效导致「不在 VR 模式」死循环（2026-09-16）

### 现象

用户反馈「插着眼镜仍卡在连接 VR 眼镜页，拔了重连也不行」。抓现场：

- 前台是 `com.huawei.appmarket.vr/ConnectVRHelpActivity`（主应用的连接帮助页）；
- 眼镜侧 display 正常（`HUAWEIAV03` 3200x1600 state ON）；
- 桌面侧反复刷：

      W/HvrVrSystem: isVRmode failed
      W/HvrVrSystem: android.os.DeadObjectException
          at android.vrsystem.IVRSystemService$Stub$Proxy.isVRmode
          at android.vrsystem.VRSystemServiceManagerImpl.isVRMode
          at com.huawei.vrlab.UnityPlayerActivity.isVrMode
      I/UnityPlayerActivity: Not in VrMode. Then return!
      I/VRService_Client_VRManager: start 3D Launcher

即：Unity 每轮 `onCreate` 判「不在 VR 模式」→ 立即销毁 → 桌面 PrepareActivity
再拉起 → 死循环。

### 根因

`VRSystemServiceManagerImpl` 把首次解析到的官方 AIDL 代理存成 `final` 字段。
EMUI 上 `vr_system` 是常驻系统服务，binder 不会随某个应用进程消失；通用安卓上
这条注册表由桌面包托管，Runtime 监督进程一旦重启，调用方缓存的代理就永久指向
死 binder，每次都抛 `DeadObjectException`，不会自愈。

### 修复

只改兼容层（原版逻辑不动）：

- 同时缓存 binder 与代理，调用前用公开 API `IBinder.isBinderAlive()` 判活；
- 判活失败时重新向注册表 `com.huawei.vrlauncherx.registry` 解析一次；
- 解析不到就维持原语义——返回中性值，让原版走它自己的失败分支，不代答状态；
- 调用抛 `RemoteException` 时清空缓存，下次调用重新解析。

实现见 `shared/java/android/vrsystem/VRSystemServiceManagerImpl.java`
（`liveService()` / `invalidate()`）。

### 真机验证（12:37–12:38，SM-F731U1 + HUAWEIAV03）

构造同样的失效场景：只重启 Runtime 监督进程，**不重启桌面进程**：

    I/VrSystemActor: refresh(start) displays=[0:内置屏幕 15:HUAWEIAV03] helmet=true
    I/VrSystemActor: sent message 0x1 / 0xf / 0xf / 0x3eb
    I/VRService_Client_VRManager: start 3D Launcher
    I/UnityPlayerActivity: HVRActivity find Context Constructor     # 不再 Not in VrMode

桌面不再进入死循环，并且这次真正选中了手柄：

    I/VrControllerManager: onStatusChanged sender DefaultController, status 5, index 0
    I/VrControllerManager: Change to controller DefaultController and lock
    I/VrControllerManager: UsingCtrl : DefaultController, status : 5
    I/HVRInputModule: HVRInputMoudule processPointers
    I/UnityPlugin: HVR_GetSensorState Unity posture time ... wxyz: ...

手柄模块侧同时可见真实设备记录（`shared_prefs/sp_device_storage.xml`）：

    HUAWEI CF20_902F / <cf20-mac> / mDeviceConnectState=2
    VrSdkApi: enter getUsedDeviceList, mDeviceInfoList size = 1
    VrHandleReconnectController: device is already connected

构建：`com.huawei.vrlauncherx` / `com.huawei.hvrsdkserverapp` /
`com.huawei.appmarket.vr` 三包 r36（主应用因签名不一致改为卸载重装）。

### 仍未验收

- 手柄按键（扳机/确认/Home/返回/音量）与触控板手势在 VR 空间内的实际生效；
- 双目画面左右眼内容不一致（既有问题，不在本轮范围）。

状态：**未完成**。

## 42. 重启 VR 进程后眼镜黑屏：原版用 EMUI 虚拟屏名判断 VR 屏（2026-09-16）

### 现象

重启 Runtime/桌面进程后，眼镜整块黑；同时可以确认渲染没死：

- 桌面进程里 `VRRenderWalleImpl` 仍在 ~30fps 出帧；
- `/dev/hwvr1` 存在且被桌面进程与手柄进程正常打开；
- 眼镜屏 `HUAWEIAV03` 3200x1600 `state ON`；
- 手机侧截屏有完整双目画面。

### 根因

桌面 `z0/c.w(Context)`（`isVrDisplayConnected`，官方代码未改动）用

    display.getName().equals("HUAWEI VR Display")     // smali/z0/c.smali:2076

判断 VR 屏在不在。`"HUAWEI VR Display"` 是 **EMUI 框架给眼镜建的那块虚拟屏**
的名字；通用安卓上眼镜是一块普通外接屏，EDID 名是 `HUAWEIAV03`，于是这个判断
恒为 false，桌面直接走：

    W/VRService_Client_VRManager: should not wake up when vr display is off.

`z0/c.v()/q()` 那两条前置判断（同样是屏名/模式）也会跟着偏，最终结果就是
「跳过唤醒面板」——画面在跑，面板不亮。

### 修复

只改「屏名从哪来」，判断本身不动：

- 新增 `shared/java/com/huawei/vrframework/compat/VrDisplayCompat.java`：
  `vrDisplayName()` 查询真实的眼镜外接屏（EDID 含 `HUAWEIAV03`）并返回它的名字；
  查不到则返回原常量 `"HUAWEI VR Display"`，让原版保持原本的失败分支；
- 新增 `patches/patch_vr_display_name.py`：把桌面包里 4 处
  `const-string vX, "HUAWEI VR Display"` 换成一次该查询（同寄存器），
  后面的 `equals` 原样保留；脚本断言原始文本与站点数量，不匹配即报错停止。

### 真机验证（12:49，SM-F731U1 + HUAWEIAV03）

    I/HvrVrDisplay: real VR display name: HUAWEIAV03
    I/VRService_Client_VRManager: Vr2 Glass wake up
    I/VRService_Client_VRManager: start 3D Launcher
    I/UnityPlayerActivity: HVRActivity find Context Constructor

`should not wake up when vr display is off.` 不再出现。构建：桌面 r37。

### 待办

同一常量在 `com.huawei.vrservice` 包里还有 4 处（`VRService`×2、`VRUtils`×1、
`VRConstant.HW_VR_DISPLAY_NAME`）。该包目前没有注入共享兼容层，补丁前要先确认
它被 `build-module.ps1` 正常带上 `classesN.dex`，再按同一脚本处理。

### 操作纪律（本轮教训）

排查时用 `ps` 取列取错，误杀了 zygote 导致全机应用重启。后续禁止批量 kill：
必须先按包名精确匹配进程，再逐条确认 PID 才允许发信号。

状态：**未完成**。

## 44. `Failed to find parent 0x0206…`：不是重打包丢的，是 EMUI 的 androidhwext 资源包（2026-09-16）

### 4.1 推翻旧归因

第 43 节把它记成「重打包后资源 bag 的 parent 丢失」。**不对**：用 `原包/*.apk`
（哈希基准）和重打包产物各 dump 一次资源表，父级引用一字不差
（`0x7f100123 style/Theme_NoTitle` 在原包里就是 `parent=0x020600cd`）。
重打包没丢过东西，原包就是这么写的。

### 4.2 真正的边界

`0x02` 是 EMUI 的**扩展框架资源包**：真机固件里就是
`/system/framework/framework-res-hwext.apk`，包名 `androidhwext`。
三条被本项目引用的样式（原文与 sha256 见 `docs/reference/emui-androidhwext-styles.txt`）：

| id | androidhwext 的名字 | 父级 |
| --- | --- | --- |
| `0x02060008` | `Theme.Emui` | `@android:style/Theme.Holo`（AOSP） |
| `0x020600cd` | `Theme.Emui.Dark` | `androidhwext:Theme.Emui` |
| `0x02060189` | `Theme.Emui.Dark.Emphasize` | `androidhwext:Theme.Emui.Dark` |

通用安卓没有这个包，父级解析不到，样式退化成「只剩自己那几条 item」
（`Theme_NoTitle` 只剩 `windowNoTitle=true`）。日志里那几个 `…vrservice` 进程
报的其实是**桌面包**的 bag——那些提示页 Activity 声明在桌面包里，
只是写了 `android:process="com.huawei.vrservice"`。

### 4.3 影响面（逐包 dump）

vrlauncherx：`Theme_NoTitle`（Unity `MainActivity` + 六个提示/准备页）、
`ThemeBlack`、`Theme_Dark_NoTitle`、`AppBaseTheme`；
vrhandle：`SplashTheme` / `SubBgTheme` / `ThemeBlack`；
vrvirtualscreen：`AppHwTheme` / `ThemeBlack`；
vrservice：`Theme_NoTitle`（它自己的 `VRPromptActivity`，主线第 2 步那个提示）。
`appmarket.vr` / `himovie.vr` 没有这类父级，无需处理。

### 4.4 修复（只改「指向」）

样式名、条目、用它的 Activity 一律不动，只把父级换成原厂主题底下那层 AOSP 主题：

| androidhwext 的样式 | 换成 |
| --- | --- |
| `Theme.Emui` | `@android:style/Theme.Holo.Light.NoActionBar` |
| `Theme.Emui.Dark` | `@android:style/Theme.Holo.NoActionBar` |
| `Theme.Emui.Dark.Emphasize` | `@android:style/Theme.Holo.NoActionBar` |

- `patches/patch_emui_theme_parents.py`：改文本解码树
  （launcher / vrhandle / vrvirtualscreen 的 `res/values*/styles.xml`，
  apktool 把父级写成占位名 `@com.huawei.fakeframework:style/huawei_*`）；
- `patches/patch_arsc_bag_parent.py`：vrservice 是 `apktool d -r` 解的，父级只在二进制
  `resources.arsc` 里，按 chunk 走到 `ResTable_map_entry.parent` 只改 4 字节；
  改前改后各扫一遍，确认表里不再有指向 `0x02xxxxxx` 的 bag。

深色/浅色与原厂一致；统一取 `NoActionBar` 变体，因为这些样式在原包里都不带
AOSP 动作栏，取带动作栏的变体会凭空多出一条系统动作栏。

### 4.5 本轮做到哪一步

构建 r38t 四包，`aapt2 dump resources` 复核：`parent=0x0206` **零命中**，
目标样式落到 `0x0103006c`（`Theme.Holo.NoActionBar`）/ `0x010300f0`
（`Theme.Holo.Light.NoActionBar`）；构建脚本自带静态核对全过。

**真机未验**：设备被同一仓库的并行改动占用（对方刚装桌面包 r38 在验），
本轮只做到「构建 + 静态核对」。要补：装 r38t 四包，确认
`Failed to find parent` 不再出现、且 VR 空间与准备/提示页观感无变化。
完整证据链见 `docs/evidence/emui-theme-parent-2026-09-16.md`。

### 4.6 顺带修掉的工具 bug

`tools/erofs/erofs-extract.py` 把 `FLAT_INLINE`（dl=2）误当成「整个文件内联在
inode 后面」，实际是「前 `size // BLK` 个整块在 `i_u`，只有尾部内联」。
后果是 `/system/framework` 这类大目录只读到尾巴，开头几十个文件（含
`framework-res-hwext.apk`、`framework-res.apk`）凭空消失。已按正确语义修正。

状态：**未完成**（真机验证待补）。

## 47. 接近（佩戴）与电量：原版要什么、这台眼镜给什么（2026-09-16）

### 47.1 先回到「谁在用」

接手第 43 节留下的 `E/UpgradeGlass: proximity value -1` /
`get glass proximity fail!` / `battery info 0, 0, 0`。先把三个消费方查清：

| 消费方 | 原调用点 | 用途 |
| --- | --- | --- |
| 桌面 | `t0/c` → 系统服务 `a3.a.v(0x838, …)`（getProximityState） | 进空间前的「有没有戴上」判断、`helmet away now, wait for proximity msg to start.` |
| Runtime | `VrSystemClient$VRStateListener` → `onProximityChanged` → `PhoneController.setProximityStatus`；`VrTouchService$VRStateListener` 里做休眠 | 佩戴/摘下时休眠与状态同步 |
| VRServiceX | `VRDeviceNodeMonitor.initGlassProximity/initGlassBattery` + `UpgradeGlass.cpp`；`VRService.sendProximityStatus` 广播 `com.huawei.vrservice.vr.vrproximitystatus` | 安装/欢迎页按接近决定何时拉起 |

原厂系统侧旁证：EMUI 的 `vendor/lib64/hw/sensors.default.so` 直接
`open("/dev/hwvr1")`，把节点上的流解析成 `android.sensor.proximity`
（串：`android.sensor.proximity`、`proximitg data: %s`、`heartbeat data: %0x`）。
所以接近传感器是眼镜上的真实器件，EMUI 由系统把它接进 sensor 框架。

### 47.2 原版发的是哪两条请求

从 `com.huawei.vrservice` 的 `lib/arm64-v8a/libvrservice.so`
（源文件串 `…/VRServiceX/app/src/main/jni/UpgradeGlass.cpp`）反汇编：

| 功能 | 函数 | ioctl | 解码 | 缓冲区 |
| --- | --- | --- | --- | --- |
| 读接近 | `IoGetProximityStatus` | `0xC0014807` | `HIDIOCGFEATURE(1)` | `buf[0]=4`，取 1 字节 |
| 读电量 | `IoGetBatteryStatus` | `0xC0084807` | `HIDIOCGFEATURE(8)` | `buf[0]=8`，取 8 字节 |

两条都先 `open("/dev/hwvr1")`（打开助手把全局 `std::string`（静态初始化为
`hwvr1`）拼成 `"/dev/%s"`）。

### 47.3 真机逐条问（本轮取证）

新增 `tools/hwvr-report-probe.c`（只发 GET_REPORT）与 `tools/hwvr-read-dump.c`
（只 read 输入流），配 `tools/hidraw-probe.sh`（临时把节点标签改成
`null_device`、跑完恢复，SELinux 保持 Enforcing）。

```text
report  1 len   4 ret   4 errno  0   d1 12 7e 10
report  2 len  62 ret  -1 errno 32 (Broken pipe)
report  2 len  80 ret  80 errno  0   "CV10AC" / "10.0.1.357" / SN
report  4 len   1 ret  -1 errno 22 (Invalid argument)   ← 接近
report  8 len   8 ret  -1 errno 32 (Broken pipe)         ← 电量
report  9 len  16 ret  16 errno  0   00 00 40 40 …（四个浮点 3.0/-2.0/-2.0/3.0）
report  9 len  48 ret  -1 errno 32 (Broken pipe)
```

report id 1–9 × 长度 1…128 全交叉问过，**只有 `1:4`、`2:80`、`9:16` 成功**。
眼镜的 HID 报告描述符里根本没有 report id 8，也没有 1 字节的 report id 4；
长度 1 的请求在通用内核的 hidraw 上直接 `EINVAL`。
`/dev/hwvr1` 连续读 25 秒共 4000 个报文，全是 report id 1 的 IMU 帧，
描述符里的 id 2/3/4/6 状态帧一帧都没有。

### 47.4 判定

**取不到的原因不在兼容层，也不在权限或标签，而在眼镜本身**：它不提供
接近/电量这两条特性报告。按本项目口径**不伪造、不填常量**，继续按
「无数据源」处理；原来那两条错误日志会照旧出现，那是眼镜的真实答复。
完整证据链见 `docs/evidence/proximity-battery-2026-09-16.md`。

兼容层这一侧不改：桌面 `0x838` 仍回 0，Runtime 的 `onProximityChanged`
不触发；空间进入由 `0x3eb`（头盔-戴上）驱动，与接近查询是两条独立路径，
真机上主线不受影响。

### 47.5 未排除的两条（不要当已知）

1. **佩戴事件才上报**：25 秒采集期间没人戴上/摘下，需一次「戴上→摘下」的长采集。
2. **厂商专有接口上的 vcom 串口**：`12d1:107e` 除两个 `usbhid` 口外还有三个
   `class=0xff`（子类 `0x13`）接口，本机无驱动绑定；原版 `AT^…` 那套
   （`ttyUSB0/1` + `tcgetattr`）在 EMUI 上走的就是它们。本轮**没有**证据说
   接近/电量从这条通道来（两条 ioctl 走的是 HID 特性报告），补它属于后续项。

另记一条硬事实：这台眼镜回答的是 Halliday 格式的版本请求（report 2 × 80），
CV10 格式（2 × 62）与光学信息（9 × 48）都拒。带电池的是 Halliday 那代眼镜，
CV10 由手机供电、本身没有电池；换型号要重跑同一套探测，不能照搬结论。

状态：**源码/工具已改、构建通过（工具）、单项实测完成**；接近与电量的
真实来源**未打通**，作为明确未完成项留档。

## 55. 三条 SDK/Unity 报错的修复与「和原版对比」

1. `LibraryCanvasManager.InitData` 空指针（198→0，见 §53/§47 系列）：
   与原版逐条 IL 对比（真机从 `原包/com.huawei.vrlauncherx.apk` 取原始 DLL）：
   - `LibrarySortPanel..ctor` 原版 = `ldarg.0 / call MonoBehaviour::.ctor() / ret`；
     补丁后 = 在前面插入 `newobj List<CardData>::.ctor()` + `stfld mCurrentCardDatas`，
     其余原样；
   - `LibraryCanvasManager.InitData` 原版 = 直接 `stsfld sInstance`；
     补丁后 = 前置 6 条「字段为空才取 `LibraryOperationManager.get_Instance()`」，
     之后原版指令序列一条不改。
2. `VRUtils.getPseudo3dNonCompatDensity` 的 hidden 字段
   `DisplayMetrics.noncompatDensity` → 公开字段 `DisplayMetrics.density`
   （该 metrics 取自 Display，本就是非兼容密度）；真机 `noncompatDensity` 归零。
3. `HisiVsyncThread`（麒麟 VRAR HAL）：
   - vsync 取值改为 `VrVsyncCompat.timestamp(int)`（真实显示刷新率 + System.nanoTime()
     推算 vsync 边界，与 Choreographer 同基准）；
   - `getHivrarService()` 不再反射 `ServiceManager.getService/waitForService`，
     直接返回已缓存引用；真机 `waitForService` hiddenapi 归零。

状态：**未完成**。

## 56. 复连后的新两项（2026-09-16）

1. `Permission Denial: Accessing service com.huawei.vrservice/com.huawei.vrinstaller.service.VrParamsInitializeService from ... requires com.huawei.vrservice.VRSystemApp`
   —— 桌面绑 vrservice 的 VrParamsInitializeService 时被拒。该权限由 com.huawei.vrservice
   自己声明（signature 级），七个模块同一签名，消费者申请即可；EMUI 上它是系统授予的。
   已在 `patches/patch_platform_permissions.py` 给 vrlauncherx / appmarket.vr 补上，
   真机 `dumpsys package` 显示 `com.huawei.vrservice.VRSystemApp: granted=true`（r52 装机）。

2. `FATAL EXCEPTION` in `com.huawei.vrservice/com.huawei.vrinstaller.activity.ServiceTermActivity`：
   `InflateException: layout/activity_service_term line #19 -> Error inflating class android.widget.TextView`。
   属「EMUI 主题父级改指 AOSP 主题」之后的样式跟进问题（该 TextView 依赖的某个属性在
   AOSP 父主题里不存在），待查具体 style 条目。

3. `WifiControllerQ.UpdateWifiName` 的 `Substring` 负长度仍在（56 条）：恢复联网/ WiFi
   权限后依旧，说明读不到 SSID（Android 10+ 读 SSID 还需要定位权限）→ 需要代码侧兜住
   空串/负长度。

4. `hiddenapi`：主应用访问 `InputMethodManager.mCurRootView/mServedView/mNextServedView`
   （键盘相关的常见 hidden 字段，失败后可回退）；另有 dex2oat 自己的一条，与本移植无关。

5. `E/VrControllerManager: mUsingCtrl == null`（1008 条）：本轮手柄没连上（status -6），
   按一下手柄即可唤醒重连，不是代码缺陷。

## 57. 权限显式化推广到全部包（2026-09-16）

用户口径：原版跑在 system UID / EMUI 框架下，很多权限是**隐式持有**的；换成通用
安卓普通应用后必须显式声明 + 运行期授予，否则原代码会因权限被拒而功能缺失或崩溃。
**所有包都按这个原则处理**。

新增 `patches/patch_restore_original_permissions.py`：用 `aapt2 dump permissions`
读「原包」的权限集合，逐包补齐当前清单缺失的项，只补不删：

| 包 | 本轮补回 |
| --- | --- |
| com.huawei.appmarket.vr | WRITE_APN_SETTINGS / REQUEST_INSTALL_PACKAGES / INSTALL_PACKAGES / DELETE_PACKAGES / hwid.ACCESS / hwid.CONTENT_PROVIDER / hwid.ACTION_MAIN_SETTING_ACCESS / ACCESS_UDID |
| com.huawei.vrlauncherx | SMART_PROVIDER / RECEIVE_SMS |
| com.huawei.himovie.vr | ACCESS_UDID / CHANGE_NETWORK_STATE |
| com.huawei.vrvirtualscreen | SMART_PROVIDER |
| com.huawei.vrhandle | （无缺失） |
| com.huawei.hvrsdkserverapp / com.huawei.vrservice | 二进制清单，由 `patch_vrservice_manifest.py` 负责 |

另外把「系统 UID 隐式权限显式化」的典型例子也落地了：空间里的 WiFi 名称控件
`WifiControllerQ.UpdateWifiName` 崩在 `Substring(1, len-2)`，根因是
`i2/g1.r(Context)` 读不到 SSID 返回空串 —— 原版能读是因为 system UID 天然持有定位
权限，而 Android 10+ 的 `getSSID()/getConfiguredNetworks()` 必须有定位权限。
已给桌面声明 `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION`，并在
`install-six.ps1` 里加运行期 `pm grant`（真机校验 `granted=true`）。

构建装机：appmarket.vr / vrlauncherx / himovie.vr / vrvirtualscreen = r54，
桌面 = r53。

状态：**未完成**。

## 58. 口径再纠正：什么都不拦；把漏掉的官方库补进来

用户口径（2026-09-16）：**服务器请求也不拦了，都不拦了**。相应回退：

- 桌面在线货架入口回退为原版：`decode/com.huawei.vrlauncherx/smali/u2/d0.smali`
  从基线提交 `22297941` 恢复（`q(Context)` 重新是原版实现）；
- 温控下载任务回退为原版：`ThermalConfigUpdateTask.run()` 从该文件入库提交
  `58c013c6` 恢复（重新调用 `updateThermalConfig`）。

同时修掉因此暴露的真崩溃：

    FATAL EXCEPTION: pool-5-thread-1 (com.huawei.vrservice)
    java.lang.NoClassDefFoundError: Lcom/huawei/networkit/grs/GrsApi;

根因是 `vrinstaller` 的温控下载链依赖 `com.huawei.networkit.grs.GrsApi`，而这个类
在 vrservice 包里不存在（EMUI 上由系统侧提供）。官方件里本来就有实现，按
「官方有原件就搬原字节码」的口径补齐：

- 从 `build/official-pool/hwframework/classes` 复制
  `com/huawei/networkit`（69 个类）与 `com/huawei/okhttp3`（224 个类）到
  `decode/com.huawei.vrservice/smali/`；
- 这些 smali 是较新 baksmali 导出的，带 `blacklist`/`greylist` 这类隐藏 API 访问
  标记，apktool 2.10 的 smali 不认；批量规范掉 272 个文件的这些标记后构建通过。

真机：vrservice r56 装机，产物 `classes.dex` 中已包含 `Lcom/huawei/networkit/grs/GrsApi;`。

状态：**未完成**。

## 59. hvrsdkserverapp 的 SYSTEM_ALERT_WINDOW 与 BOOT_COMPLETED 投递方式（2026-09-16）

### 59.1 补 hvrsdkserverapp 的显式权限（已修）

`appops set com.huawei.hvrsdkserverapp SYSTEM_ALERT_WINDOW allow` 一直是 `default`，
因为该权限没写进它的清单；这个包的清单是 apktool `-r` 解出的**二进制 AXML**。
按 vrservice 那套（axml_edit）处理：新增
`patches/patch_hvrsdk_manifest_permissions.py`，补

    android.permission.SYSTEM_ALERT_WINDOW   （后台启动 Activity 的公开豁免途径）
    android.permission.FOREGROUND_SERVICE    （常驻服务 startForeground；原本已有）

真机（r58 装机后）：`SYSTEM_ALERT_WINDOW: allow` ✓

### 59.2 BOOT_COMPLETED 的投递（找到可用方式）

`install-six.ps1` 之前以 shell(uid 2000) 身份投递 `BOOT_COMPLETED`，被系统拒：

    SecurityException: not allowed to send broadcast android.intent.action.BOOT_COMPLETED from uid=2000

改用 **root 投递**即可，实测：

    su -c am broadcast -a android.intent.action.BOOT_COMPLETED -n com.huawei.hvrsdkserverapp/.compat.VrGlassBootReceiver
    Broadcast completed: result=0

脚本已改成「先 su，失败再退回 shell，最后退回直接起监督服务」的三级路径。

状态：**未完成**。

## 60. `?0x0201xxxx`：EMUI 共享库属性导致安装/条款页崩溃（2026-09-16）

### 60.1 崩溃与根因

原流程里 `com.huawei.vrservice` 的安装/条款页一进就崩（进程 `com.huawei.vrinstaller`）：

    Unable to start activity ... com.huawei.vrinstaller.activity.ServiceTermActivity
    Caused by: InflateException: Binary XML file line #19 in
        com.huawei.vrservice:layout/activity_service_term: Error inflating class android.widget.TextView
    Caused by: UnsupportedOperationException: Can't convert value at index 2 to dimension: type=0x8
      at android.widget.TextView.readTextAppearance(TextView.java:4712)

根因与第 44 节（样式父级 `0x0206xxxx`）是同一个包的**另一种用法**：`0x02` 是 EMUI
扩展资源包 `androidhwext`（`/system/framework/framework-res-hwext.apk`，共享库）。
布局里的 `?0x020100e9` 这类**属性**引用编译成 `Res_value::TYPE_DYNAMIC_ATTRIBUTE
= 0x8`，EMUI 上由共享库主题给值；通用安卓查不到这个包，**0x8 原样透传**，
`TextView` 拿到转换不了的 0x8 就抛异常。父级那种只是样式退化，这种会**崩**。

### 60.2 取值来源（不猜）

从 HMA-AL00 EMUI 11.0.0.155 的 `system.img` 里用
`tools/erofs/erofs-extract.py` 取出 `framework-res-hwext.apk`（21639272 字节），
`aapt2 dump resources` 后按 `androidhwext:Theme.Emui` 逐条查：15 个属性各有正式
名字，指向的 dimen/string 也各有默认值（表见
`docs/evidence/emui-hwext-attrs-2026-09-16.md` 第三节）。例如
`textSizeBody2 -> @dimen/emui_text_size_body2 = 14sp`、
`maxPaddingStart -> @dimen/emui_dimens_max_start = 24dp`。

### 60.3 改法：只换「指向平台包的那一个值」

新增 `patches/patch_hwext_attr_refs.py`，改 `com.huawei.vrservice` 的 7 个
**二进制布局**（该包是 `apktool d -r` 解的，`res/` 里是原始 AXML），共 **63 处**：
把 `type=0x8 + 0x020100xx` 换成 `type=0x5`（dimension）或 `type=0x3`（string）。
元素、层级、顺序、文案、其它属性一律不动；脚本按文件断言处数、改后复扫，
残留的非 `buttonStyleEmphasize` 引用直接报错。

字体族按语义对齐：`textFontFamilyRegular` 原厂值本来就是 `sans-serif`；
`textFontFamilyMedium` 原厂是华为自带族名 `HwChinese-medium`，通用安卓没有这个族
（会被丢弃退回常规字重），改用语义相同的 `sans-serif-medium`。

### 60.4 没内联的一条：`style="?0x02010013"`（待补，不是回退）

`buttonStyleEmphasize` 指向整套样式，含 `androidhwext` 自己的九宫格背景
`@drawable/btn_emphasize_emui_translucent` 与状态色选择器，没法内联成一个值；
要还原必须往本包 `resources.arsc` **新增资源条目**（本包资源表是原样打进包的，
apktool 不重建），属于单独的工程。现状：引用解析不到 → 按钮走应用主题自己的
按钮样式，也就是框架本来的失败分支，**不伪造背景**。留 3 处，已登记。

### 60.5 同类扫描（全仓七个包，只读工具）

新增 `tools/axml-ref-scan.py`（扫二进制 AXML 的 `0x02` 引用）与
`tools/arsc-ref-scan.py`（扫 `resources.arsc` 的 bag parent、bag 条目键、
entry 的 `Res_value`）。结果：文本资源 0 命中、两个二进制资源表 0 命中、
vrservice 二进制布局 66 命中（63 已内联 + 3 条上面的按钮样式）、
投屏包清单 2 命中（见 60.6）。

### 60.6 顺带查出的丢项：投屏两个对话框主题被写成 `@null`

新增 `tools/manifest-themes.py` 逐组件对照原包与产物的 `android:theme`。
七个包里只有投屏包有非预期差异：`NoloDialogActivity` 与 `Hw6dofDialogActivity`
原为 `@androidhwext:style/Theme.Emui.Dialog.Alert`（`0x0206002b`），
apktool 解不出外来包引用，写成了 `@null`，重建后进包的也是 `@null` —— 主题丢掉，
两个对话框会落到应用默认主题、不再悬浮（功能性丢失）。

原厂继承链 `Theme.Emui.Dialog.Alert -> Theme.Emui.Dialog -> Theme.Emui ->
@android:style/Theme.Holo`（三条都 dump 过），故换成 AOSP 的
`@android:style/Theme.Holo.Dialog.Alert`。新增
`patches/patch_hwext_dialog_themes.py`，只改这两处 `android:theme`。

（同一份对照里其它包的差异都是**已在台账里的在线组件摘除**：himovie 的
`com.huawei.hwid.api.common.apkimpl.DummyActivity` /
`com.huawei.phoneservice.feedback.*`，appmarket 的 `DummyActivity`，
vrservice 的 `com.huawei.updatesdk.*`，以及兼容层新增的
`com.huawei.vrframework.compat.HvrContextProvider`。）

### 60.7 真机验证（SM-F731U1，vrservice/vrvirtualscreen `r58`）

| 项 | 结果 |
| --- | --- |
| 原崩溃页 `ServiceTermActivity` | 进程存活，无 `InflateException`；`uiautomator` 层级含「欢迎使用 / 华为 VR 安装向导 / 下载、安装 VR 应用 / 取消 / 同意」 |
| 内联尺寸是否生效 | 按钮栏左右各 72px = 24dp、两按钮间距 48px = 16dp，与 `maxPaddingStart/End`、`elementsMarginHorizontalL` 的取值一致 |
| `WelcomeActivity`/`InstallActivity`/`VRUserPromptActivity`/`VRGlassUpgradeActivity` | 逐个拉起，均无 `InflateException` |
| 投屏 `NoloDialogActivity` | `Non-opaque activity is created, styleTranslucent=false, floating=true` —— 对话框主题已生效 |

状态：**未完成**（60.4 的按钮背景待补；Android 10–15 未验）。

## 61. 环境由谁拉起：去掉开机自启与模拟开机，改成「打开华为 VR 时启动」（2026-09-16）

### 61.1 用户口径

安装脚本原来是这样「唤醒」环境的：装完投一次 `BOOT_COMPLETED` 给 Runtime 的
`compat.VrGlassBootReceiver`（先 root、再 shell、再退回直接起服务）。用户指出
两件事：

1. 不需要开机自启；
2. 装完模拟一次开机属于花里胡哨，通用安卓该怎么做就怎么做 —— 打开华为 VR
   应用时把环境拉起来即可。

### 61.2 为什么装完确实要有人「踢」一次

`adb install` 装上的包处于 **stopped 状态**：收不到隐式广播（USB 插入就是隐式
广播），原版入口「插入眼镜 → `UsbReceiver` → `startService(VRService)`」因此
起不来。EMUI 上这套是系统常驻进程，开机就在跑；普通应用模型里必须有人显式启动
一次。所以「装完踢一次」本身不是错，错在**用一条模拟开机的受保护广播去踢**，
并且**给 Runtime 加了 BOOT_COMPLETED 自启接收器**。

### 61.3 改法（全部是通用安卓的标准做法）

| 位置 | 改动 |
| --- | --- |
| Runtime 清单 | 删掉 `<receiver .compat.VrGlassBootReceiver>` 与 `RECEIVE_BOOT_COMPLETED` 权限（原厂清单里本来就没有这两项，是我们自己加的框架替身） |
| Runtime 清单 | `VrGlassWatchService` 改成 `exported="true"` + `android:permission="com.huawei.hvrsdkserverapp.permission.RUNTIME_ALLOW"`。这条权限是**原厂清单里已有的**（`protectionLevel=signatureOrSystem`），六个原包本来就在申请 |
| 兼容层 `HvrContextProvider` | 进程启动时（平台实例化 provider）判断宿主是不是主应用 `com.huawei.appmarket.vr`，是就 `startForegroundService()` 显式启动 Runtime 的监督服务。没有模拟广播，也没有分级兜底 |
| 主应用清单 | 补声明 `com.huawei.hvrsdkserverapp.permission.RUNTIME_ALLOW`（普通应用要显式声明才能调用被它保护的服务） |
| `install-six.ps1` | 三级路径整段删除，只留一句说明：装完打开一次「华为 VR」，环境由它拉起 |
| `VrGlassBootReceiver.java` | 删除（改完即成死代码） |

### 61.4 真机验证（SM-F731U1，`r59`）

    adb shell am force-stop com.huawei.hvrsdkserverapp       # 先把环境停掉
    adb shell am start -n com.huawei.appmarket.vr/com.huawei.hwmarket.vr.MainActivity
    # logcat:
    #   I/HvrContextProvider(10455): VR environment start requested
    #   I/ActivityManager: Start proc ... for service
    #       {com.huawei.hvrsdkserverapp/com.huawei.hvrsdkserverapp.compat.VrGlassWatchService}
    #   I/VrSystemActor(10470): refresh(start) displays=[0:内置屏幕 1:内置屏幕] helmet=false
    # dumpsys activity services:
    #   ServiceRecord{... com.huawei.hvrsdkserverapp/.compat.VrGlassWatchService
    #                 c:com.huawei.appmarket.vr}

`c:com.huawei.appmarket.vr` 就是「由主应用启动」；`helmet=false` 是因为当时眼镜
没插。构建产物清单里已无 `BOOT_COMPLETED` / `RECEIVE_BOOT_COMPLETED` /
`VrGlassBootReceiver`，监督服务为 `exported=true` + `RUNTIME_ALLOW`。

顺带修掉一个真 bug：这一轮之前 `VrGlassWatchService` 是 `exported="false"`，
shell（uid 2000）根本起不动它（`Error: Requires permission not exported from
uid 10423`），所谓「第三级兜底」实际上只有 root 能走通。

### 61.5 代价（明确记下，不掩盖）

去掉自启后，**重启手机、或 force-stop 过 Runtime 之后，第一次插眼镜不会有
反应**，要先打开一次华为 VR。这是用户选择的语义。将来若要拿回开机自启，把接收器
与 `RECEIVE_BOOT_COMPLETED` 加回 Runtime 清单即可（`patch_sdk_manifest.py` 里
`LEGACY_BOOT_RECEIVER` / `LEGACY_BOOT_PERMISSION` 两段就是给它准备的摘除点）。

状态：**未完成**（写这轮时眼镜不在位，插拔 → 提示 → 进空间这条主线没重跑）。

## 62. 环境启动闸门放进「进入 VR」页（不新建页面）（2026-09-16）

### 62.1 用户口径

- 不新建页面；
- 那些「要被被动拉起」的服务，放到主应用里显示「正在启动 X…」，全部好了才让
  「进入 VR」按钮可点；
- 原版那条 `USB 插入 → UsbReceiver → VRService` 可能根本用不上，要评估；
- 通用安卓怎么做就怎么做，不要花里胡哨。

### 62.2 页面事实（真机 dump 出来的顺序）

| 页面 | 内容 | 有没有可点的动作 |
| --- | --- | --- |
| `MainActivity` | 启动后分叉：能进商城就去商城，否则走欢迎流程 | 无 |
| `ProtocolActivity` | 阅读提示说明（"每次都要重新点一下"的那页） | 有确认按钮 |
| `WelcomeVRActivity` | 品牌页：`进入应用`（已被第 5 节隐藏）+ **`进入 VR`** | 有「进入 VR」按钮 |
| `ConnectVRHelpActivity` | 连接 VR 帮助（图片 + 标题 + 正文） | **没有按钮** |

结论：**要「好了才能点」，闸门必须长在有按钮的那一页**，也就是欢迎页；帮助页只有
文字，放状态可以、门禁放不了。

### 62.3 实现

- `shared/java/com/huawei/vrframework/compat/VrStartupGate.java`：在原页面的按钮行
  上方插一个纵向状态区，逐项显示；`welcome_vr` 先 `setEnabled(false)`，全部就绪后
  放开。布局、文案、按钮原有监听一律不动，状态行是运行时 new 出来的。
- `patches/patch_main_startup_gate.py`：在 `WelcomeVRActivity.initView()` 末尾加**一条**
  静态调用（锚点断言，不匹配即报错）。
- 两项内容：
  1. `VR 运行环境` → `com.huawei.hvrsdkserverapp/.compat.VrGlassWatchService`：
     `startForegroundService` + `bindService`，**绑定成功才算就绪**；
  2. `VR 系统服务` → `com.huawei.vrservice/com.huawei.vrinstaller.service.VrParamsInitializeService`：
     `startService` 把包唤醒。该组件**只有 `onBind`、没有 `onCreate`/`onStartCommand`**，
     所以页面写「已唤醒」，不写「已就绪」。
- 失败不再死锁：4 秒重试一次，30 秒仍未就绪就把原因写在该行上。
- 同一轮把上一版「进程一起来就拉环境」（`HvrContextProvider` 里的那次启动）**去掉**：
  一个启动点，语义是「用户打开这个应用才启动」，也避开后台启动前台服务会被系统拒的路径。

### 62.4 真机验证（SM-F731U1，r62）

    I/VrStartupGate: started com.huawei.hvrsdkserverapp/.compat.VrGlassWatchService
    I/VrStartupGate: started com.huawei.vrservice/com.huawei.vrinstaller.service.VrParamsInitializeService
    I/VrStartupGate: ready  com.huawei.hvrsdkserverapp/.compat.VrGlassWatchService
    I/VrStartupGate: environment ready

即：运行时监督服务被真的拉起并**回连成功**，按钮门禁在就绪后放开。

一个系统侧现象记下来：主应用 `targetSdk` 是旧的，**每次重装后首次启动**，Android 16
会弹一次「此应用与最新版 Android 不兼容。请检查是否有更新，或与应用开发者联系。」，
点掉才看到页面。它不是我们引入的，与闸门无关，但会挡在首次流程前面。

### 62.5 顺带修掉的构建问题

构建暂存目录原本放在 `%LOCALAPPDATA%\HvrCompatBuild`，每构建一次留一份整棵解码树
的副本，攒到 319 份把系统盘占满（C 盘 0 可用），主应用构建直接报「磁盘空间不足」。
改成放工作区所在盘的根目录（`D:\.hvrbuild`，纯 ASCII，aapt2 才认），并且每次构建前
只保留最近 3 份。

### 62.6 还没定的（等用户拍板）

- 「USB 插入 → UsbReceiver → VRService」这条原版链在本移植里是否真的用得上：现在的
  运行时 actor 是按外接显示判断眼镜在位、并自己绑定桌面空间宿主、自己给手柄发重连的，
  所以闸门里第 2 项目前只是保险。要实测确认后再决定去留。
- 触发点位置：放在「阅读提示页」提前启动（用户读提示时环境已经在起，走到欢迎页按钮
  直接可点）比只在欢迎页等更省时间；若采纳，需要再加一处 hook，欢迎页仍保留状态显示。

状态：**未完成**（第 2 项去留与触发点位置待定；眼镜不在位，主线未跑）。

## 63. 手机卡在横屏 / 画面变形：VR 会话没把方向还回去（2026-09-16）

### 63.1 现象与定位

用户报「手机画面是变形的」「又是强制横屏」。真机读数：

    wm get-ignore-orientation-request    -> ignoreOrientationRequest true for displayId=0
    settings get system user_rotation    -> 1     （横屏）
    settings get system accelerometer_rotation -> 1
    wm size / wm density                 -> 只有 Physical 行，没有 Override

**分辨率与密度从来没被改过**，坏的是方向：`ignore-orientation-request` 是 EMUI
VR 模式用来「忽略应用方向请求」的机制，它留着，应用自己就转不回来；再叠加
`user_rotation=1`，整机一直横着 —— 竖着拿手机看到的就是横屏 + 应用被塞进居中
窄窗口，这就是用户说的「变形」。

### 63.2 两个漏点（都在我们这边，不是三星的锅）

| 位置 | 漏在哪 |
| --- | --- |
| `shared/runtime-actor/.../VrSystemActor.java` | `lockLandscape()` 写 `ACCELEROMETER_ROTATION=0` + `USER_ROTATION=90`；`unlockRotation()` **只还自动旋转，不还方向** |
| `ksu/hwvr_compat/service.sh` | `set_size()` 写 `accelerometer_rotation=0` + `user_rotation=1`；`reset_size()` 同样只还自动旋转，而且完全没清 `ignore-orientation-request` |

`ignore-orientation-request` 不是这两个文件设的（仓里搜不到），是早期在真机上手工
试 VR 横屏时留下的（`wm set-ignore-orientation-request true`），一直没人清。

### 63.3 修法

1. `VrSystemActor`：进 VR 前先把手机自己的 `accelerometer_rotation` /
   `user_rotation` **存下来**，退出时按原值还回去；没存过就回到「自动旋转 + 竖屏」。
2. `service.sh`：`set_size()` 先把原值写进 `/data/local/tmp/hwvr_rotation_saved`，
   `reset_size()` 按原值还原，并且 `wm set-ignore-orientation-request false` 一并清掉。
3. `install-six.ps1`：每次装包补一条幂等的 `wm set-ignore-orientation-request false`，
   这样即使上一次会话崩在中间，重装也能把整机方向救回来。

### 63.4 现场复位与验证（真机，r63）

    adb shell wm set-ignore-orientation-request false
    adb shell settings put system user_rotation 0
    adb shell settings put system accelerometer_rotation 1
    # 复读：
    ignoreOrientationRequest false for displayId=0
    user_rotation=0  accelerometer_rotation=1
    wm size -> 只有 Physical size: 1080x2640   wm density -> 只有 Physical density: 480

Runtime `r63` 已装机（含「按原值还原方向」的修复）。

状态：**未完成**（眼镜不在位，插拔时的锁/还原只做了代码修正，未在真机重复验；
下次插拔时要确认退出后 `user_rotation`/`accelerometer_rotation` 回到原值）。

### 63.5 第二轮：设备上跑的仍是旧模块（2026-09-16 当日复查）

复位后用户又报「再恢复一下」。复读发现 `ignoreOrientationRequest` 变回 true、
`user_rotation` 又回到 1。查现场：

    /data/adb/modules/hwvr_compat/service.sh   2026-09-15 16:30   3502 字节（旧版）
    ps: 两个 busybox 实例在跑同一个脚本

即：**改的是仓库里的脚本，设备上跑的仍是旧版**。旧版 `reset_size()` 在没有 size
覆盖时直接 `return 0`，方向永远不还；`ignore-orientation-request` 从来没被清过
（它是原版应用进 VR 模式时打开的，不是我们这两个文件设的）。

处理：

1. 新增 `ksu/hwvr_compat/deploy.sh`：推脚本 → **先杀掉还在跑旧逻辑的循环** → 用新脚本
   重启 → 现场复位方向 → 打印状态。必须杀旧循环，否则新旧两套逻辑互相打架。
2. 新 `reset_size()` 加了「只有真的要还原才动」的判断（存过原值 / 还留着 size 覆盖 /
   冻结仍是 true），否则每 2 秒重写一次方向设置会把用户自己的手动转屏按住。
3. 真机复读（部署后 8 秒）：`ignoreOrientationRequest false`、`user_rotation=0`、
   `accelerometer_rotation=1`、无 size/density 覆盖，稳定不变；模块单实例运行
   （pid 9291）。

状态：**未完成**（插拔眼镜时的锁/还原仍未在真机重复验）。

## 64. 全流程对齐官方：眼镜识别、环境启动点、在线 1:1（2026-09-16）

用户口径（本轮定稿）：**插眼镜走官方自动链、不做开机自启、打开华为 VR 即启动环境、
页面上不挂启动闸门、眼镜识别用 USB VID/PID、在线链完全 1:1。**

### 64.1 眼镜识别：显示名 → USB VID/PID

- `VrPlatformCompat` 重写：`isVrGlassPresent(Context)` = **USB 身份**（vendor `0x12d1`
  + product `0x1092` "HUAWEI GLASS CV10" 或 `0x107e` "HUAWEI GLASS HID"）**且**
  **有外接屏在位**（`Display.getState() != STATE_OFF`，不按名字匹配）。
  两个都是真实信号：USB 证明线上是哪台设备，外接屏证明它的 DP 侧起来了。
- `VrDisplayCompat.vrDisplayName()` 不再拿 EDID 名 `HUAWEIAV03` 去猜，改问同一组信号，
  查到就返回那块外接屏的真实名字，查不到返回原常量走原失败分支。
- `VrSystemActor` 删掉 `HELMET_DISPLAY_NAME` / `HELMET_USB_*` 三个常量与
  `isHelmet(Display)`（原本按屏名 contains 判断），`refresh()` 直接问兼容层。
- 静态核对：全仓已无 `HUAWEIAV03` 判定（只剩 `patch_vr_display_name.py` 注释里的一句
  历史说明）。`VRConstant` 里那两个同名常量在原版就是**死字段**（无 sget-object 读取），
  按原样留着。

### 64.2 环境启动点：页面闸门 → 打开应用时启动

- 新增 `HvrContextProvider.onCreate()` 里的启动：仅主应用 `com.huawei.appmarket.vr`
  执行，`startForegroundService(VrGlassWatchService)` +
  `startService(com.huawei.vrinstaller.service.VrParamsInitializeService)`。
  失败如实记日志，不代答状态。
- `VrStartupGate.java` 删除；`patches/patch_main_startup_gate.py` 改成**撤回**脚本并已运行
  （`decode/.../WelcomeVRActivity.smali` 回到原样：无状态行、按钮不禁用）。
- `install-six.ps1`：装完用公开命令 `am start -n .../MainActivity` 启动一次，解除新装包的
  stopped 状态；不投受保护广播、不模拟开机。
- **补回 `MyService` 的拉起**：它原来挂在已删掉的模拟开机 receiver 上，删掉之后没人拉起，
  `VrHelmetExt.init()` 永不执行。现在 `VrGlassWatchService.onCreate/onStartCommand` 里
  按类名启动 `com.huawei.hvrsdkserverapp.MyService`。真机日志：
  `I MyService: onStartCommand() executed`。

### 64.3 在线链严格 1:1

- `patch_offline.py` 改写：只保留「去 `android.uid.system`」与「去 `nearbysdk` uses-library」，
  权限与组件一律不再摘。
- 新增 `patches/patch_online_restore.py`：把上一轮按离线口径摘掉的在线入口按原包逐字还原，
  **来源是 git 里的原始解码 `22297941`**（不是凭记忆手改）：
  - 主应用 `MainActivity`（`startMarketFrame()` 的市场入口、`is_entryhome_button_clicked` 写入）；
  - 主应用 `WelcomeVRActivity`（「进入应用」按钮恢复可见）；
  - 清单组件：主应用 `DummyActivity` 1 个、视频 `DummyActivity` + 12 个
    `com.huawei.phoneservice.feedback.*` 共 13 个。
  - 另一处同类改动（vrservice `ThermalConfigUpdateTask.run()` 空实现）在 `c1c8a1d6` 已还原，
    脚本改为存在性核对（断言 `updateThermalConfig` 仍在）。
- 删除 `patch_main_entry.py` / `patch_offline_cloud_entry.py` /
  `patch_offline_thermal_config_task.py`（它们会再次把在线入口摘掉）。
- `patch_restore_network_permissions.py` 补上 `com.huawei.vrservice`
  （INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE），实测该包已带这三条。
- 静态核对（构建产物）：主应用在线组件 1 个、视频 13 个、vrservice 三条联网权限齐全。

### 64.4 顺带修掉的真缺口：子进程 compat context 没打上

`patches/patch_context_provider_processes.py` 之前**没被应用**到解码树，导致桌面的
`VRService` 进程（`android:process="com.huawei.vrservice"`）里 `ContextEx.application` 为 null，
每秒刷：

    W HvrServiceManagerEx: no application context; vr_system stays process-local

后果是 `vr_system` 发布不到注册表、主线握手起不来。本轮在各包补齐子进程 provider
（vrlauncherx / himovie / vrvirtualscreen / vrhandle / vrservice）。

### 64.5 真机主线（SM-F731U1 + HUAWEIAV03，u3）

    22:28:36 I HvrContextProvider: VR environment start requested
    22:28:36 I VrPlatformCompat: glass probe: usb=true externalDisplay=true
    22:28:36 I VrSystemActor: refresh(start) displays=[0:内置屏幕 19:HUAWEIAV03] helmet=true
    22:28:36 I MyService: onStartCommand() executed
    22:35:10 I VRService_Client_VRManager: startPrepareActivity
    22:35:10 ActivityTaskManager: START ... VRPrepareActivity (BAL_ALLOW_VISIBLE_WINDOW)
    22:35:10 I VRService_Client_VRWorkThread: vrEnvPrepare step 2 / step 3
    22:35:10 I VRService_Client_VROsMonitor: dp link good.
    22:35:14 I VRService_Client_VRManager: start 3D Launcher
    22:35:15 I UnityPlayerActivity: HVRActivity find Context Constructor
    topResumedActivity = com.huawei.vrlauncherx/.MainActivity

即：打开华为 VR → 环境自动起 → 按 USB 身份识别在位 → 桌面 VRService 握手 →
准备页 → 原 VR 空间。

### 64.6 仍未完成（下一轮）

- **头部跟踪**：真机仍刷
  `HvrVrFramework: VrHelmetExt.init failed: ClassNotFoundException: com.huawei.vrframework.VrHelmetExt`
  与 `Unity_HVRController: Fail to GetPosture`。`LibUpdate` 是用 **DexClassLoader** 动态加载
  SDK 类（日志 `LibUpdateCall: loadRemoteClass succeed / Run update 2.0 succeed`），
  而兼容层的反射用的是应用类加载器，所以拿不到。下一步要让 bootstrap 用 `LibUpdate`
  的那个加载器去解析 `VrFramework` / `VrHelmetExt`，不是新写一套姿态实现。
- 手柄三处平台缺口（`AgreementUtils` 的 `vr_handle_user_agree` 持久化、`Hw6dofUtil`
  的 `UsbManager.getDeviceList()` 返回空、Android 16 首次启动弹窗）。
- 主应用数据被清空后，「阅读提示说明」页要再点一次（原版首次流程，不是缺陷）。

状态：**未完成**。

## 65. VR 视频崩溃已修；投屏/视频的真正门槛是「必须跑在非默认屏」（2026-09-17）

### 65.1 视频包崩溃：Android 14+ 动态注册广播必须给导出标志

真机（SM-F731U1 / Android 16）：

    java.lang.RuntimeException: Unable to create application com.huawei.vrlab.VrPlayerApplication
    Caused by: java.lang.SecurityException: com.huawei.himovie.vr:
      One of RECEIVER_EXPORTED or RECEIVER_NOT_EXPORTED should be specified
      when a receiver isn't being registered exclusively for system broadcasts
        at android.app.ContextImpl.registerReceiver
        at com.huawei.vrlab.VrPlayerApplication.onCreate

原版 targetSdk 30，`registerReceiver(receiver, filter)` 不给标志位；Android 14 起平台强制要求，
于是视频包连 Application.onCreate 都过不去 —— 桌面点「VR 视频」自然没反应。

修法（只换指向，不改参数与后续逻辑）：

- 新增 `shared/java/com/huawei/vrframework/compat/HvrReceiverCompat.java`：
  语义按 Android 14 之前取 `RECEIVER_EXPORTED`（pre-34 的动态接收器本来就能收其它应用的广播，
  取 NOT_EXPORTED 会把七个包之间的广播链挡掉）。34 以下仍按原调用。
- 新增 `patches/patch_receiver_exports.py`：把 `Context.registerReceiver` 的两参数/五参数
  调用点改成走兼容层。实测改写 **88 处**（两参数 74、五参数 14），分布在七个包。
- 重装后复测：`CrashExceptionHandler` 计数 0，`com.huawei.himovie.vr` 进程起来，
  `VrLauncherActivity` 起来，播放器子进程加载 `libffmpeg_neon.so` / `libwiseffvplayer.so`。

### 65.2 投屏起不来是「屏幕」问题，不是权限问题

`com.huawei.vrvirtualscreen` 的启动闸门（`b/a/c/k/b/d.e`）逐条是：

    ① d(context) 必需应用存在
    ② IVRSystemServiceManagerEx 非空
    ③ ex.isVRMode() == true
    ④ b(context) == false            ← 必须不是在默认屏启动
    否则 「app start on default display error, finish!」

而 `b(context)` 就是：

    int displayId = a0.a(context);       // 当前 activity 所在 display
    return displayId == 0;               // 在默认屏就返回 true

真机读到的 display：`displayId=19 HUAWEIAV03 3200x1600 canHostTasks=false`，
而所有窗口（含 VR 空间 `com.huawei.vrlauncherx/.MainActivity`）都在 `mDisplayId=0`。
也就是：**我们的移植把一切都跑在手机默认屏上**，投屏因此每次都判「在默认屏启动」并自杀。

### 65.3 澄清官方架构：EMUI 用的是**虚拟屏**，不是外接屏

原版代码到处判断 `display.getName().equals("HUAWEI VR Display")` ——
`HUAWEI VR Display` 不是眼镜那块 DP 面板，而是 EMUI 的 VR 模式**自己建的一块虚拟屏**：
VR 应用被启动到那块虚拟屏上（所以投屏的 ④ 才成立），虚拟屏的图像再送到眼镜面板。
眼镜那块外接屏在三星上是 `canHostTasks=false`（只能做 Presentation），本来也承载不了应用。

这解释了第 42 节为什么把屏名换成 `HUAWEIAV03` 只是权宜：真实形状是「虚拟屏承载应用 +
眼镜面板只做输出」。第 2/3 阶段（黑边/错位/延迟/头晕）要做的正是这块：
`DisplayManager.createVirtualDisplay(PUBLIC, 3200x1600, 90Hz)` → 启动 VR 应用到它上面
（`ActivityOptions.setLaunchDisplayId`）→ 把虚拟屏合成的 Surface 画到眼镜 display 上的
Presentation。这条链就是原版「异步前缓冲 + 面板合成」的等价物。

状态：**未完成**（65.1 已修并验证；65.2/65.3 已定位，实现待做）。

## 66. 复核两条「以为是缺陷」的项（2026-09-17）

### 66.1 手柄「每次都要重新点同意」：不是缺陷，是反复重装清的数据

`r0/e5.n(Context,String)` 就是 `context.getSharedPreferences(name, 0)`，读的是手柄包**自己的**
SharedPreferences；同意状态存在 `10000.xml` 的 `vr_handle_user_agree`。真机读数：

    $ su -c cat /data/data/com.huawei.vrhandle/shared_prefs/10000.xml
    <map><string name="vr_handle_user_agree">agree</string></map>

也就是说它一直有持久化，之前反复弹是因为我们这一路反复重装（签名冲突时还会卸载重装）把
数据清了。第 40 节那条待办据此关闭。

### 66.2 「可信虚拟屏」这条路对普通应用是死的

试过在建屏时带上 `VIRTUAL_DISPLAY_FLAG_TRUSTED`（@hide，1<<10），平台直接拒绝：

    SecurityException: Requires ADD_TRUSTED_DISPLAY permission to create a trusted virtual display.

所以「只用公开 API 就能让 VR 活动落到自建虚拟屏」不成立：非可信屏会被
`ActivityTaskSupervisor.isCallerAllowedToLaunchOnDisplay` 挡掉（连屏的拥有者自己也不行）。
放行只有两个办法：LSPosed hook 那处判断（`lsposed/hvr-display-routing`，已就绪待启用），
或者由 root/shell 代发启动。脚本 `lsposed/verify-display-routing.ps1` 会在模块生效后
一键跑完补丁、构建、主线与验收判据。

状态：**未完成**（等待 LSPosed 模块启用后验证）。
