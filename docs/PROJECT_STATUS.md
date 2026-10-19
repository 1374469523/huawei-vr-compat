# 华为 VR 七包兼容移植：整体思路、实现方式与当前进度

> 更新：2026-10-19（项目暂停时的状态快照）
>
> 本文回答三个问题：**我们在做什么**、**是怎么做的**、**现在做到哪一步**。
> 逐条改动的证据在 [PATCH_AUDIT.md](PATCH_AUDIT.md)（66 节，按轮次记录），
> 方法口径在 [PORTING_METHOD.md](PORTING_METHOD.md)。

---

## 0. 一句话

把华为 VR Glass 的**七个原包**（六个原厂 APK + 从 EMUI 固件里提取的 VR 系统服务）
原样搬到通用安卓上运行：**应用层一个字不改，只把「跟 EMUI/麒麟/华为在线服务绑定的那一层」
换成通用安卓的等价实现**。

---

## 1. 范围与边界

### 1.1 七个包

| 包 | 版本 | 角色 | 来源 |
| --- | --- | --- | --- |
| `com.huawei.appmarket.vr` | 12.2.1.301 | 主应用：启动页、条款页、进入 VR 入口 | `华为VR.apk` |
| `com.huawei.vrlauncherx` | 11.1.0.337 | VR 桌面 / Unity VR 空间、准备页、模块导航 | `华为VR桌面.apk` |
| `com.huawei.himovie.vr` | 8.2.0.300 | VR 视频（本地媒体、2D/SBS/TB/360） | `华为VR视频.apk` |
| `com.huawei.vrvirtualscreen` | 11.1.0.325 | VR 投屏（MediaProjection） | `VR手机投屏.apk` |
| `com.huawei.vrhandle` | 10.0.1.345 | CF20 手柄的私有 BLE 协议与 UI | `VR手机手柄.apk` |
| `com.huawei.hvrsdkserverapp` | 3.5.0.82 | Runtime / SDK：原生渲染、头盔通道、手柄重连 | `华为vrsdk3.5.0.82.apk` |
| `com.huawei.vrservice` | 11.0.0.322 | **第七个包**：EMUI 的 VR 系统服务本体（vr_system 注册、准备流程） | HMA-AL00 EMUI 11 固件 `/hw_product/.../VRServiceX.apk` |

> 主应用原包名是 `com.huawei.appmarket.vr`。六个原包的 dex 里**没有任何一处**引用
> `com.huawei.vr`，所以禁止给主应用改名（改名会直接让六个包串不起来）。

### 1.2 不做什么

- 不改包名、不改 Activity/Service/Receiver/Provider、不改 Intent、广播、AIDL 签名；
- 不改原版 Java 逻辑与 Unity 资产（`assets/bin/Data`、`Assembly-CSharp.dll`）；
- 不写替代首页、不跳过准备页/条款页、不伪造连接状态或电量；
- 不把「跑不通」的地方换成自研的"兼容实现"来假装成功。

---

## 2. 整体思路

### 2.1 先分清「哪一层不兼容」

移植失败的现象千奇百怪，但根因只落在几类边界上：

| 边界 | 原厂在哪 | 通用安卓 |
| --- | --- | --- |
| 系统服务 | 框架注册的 `vr_system`（`IVRSystemServiceManager`） | 不存在 |
| 设备节点 | 内核 `hid_vr` 驱动建 `/dev/hwvr1`（标准 HID feature report 透传） | 不存在 |
| 系统身份 | uid=1000 + 平台签名 → 一批权限隐式持有 | 普通应用，权限要显式申请/授权 |
| 资源 | 固件里的 `androidhwext` 主题包 | 不存在 |
| 平台类 | `hwframework.jar` 里的 `com.huawei.android.*`（约 40 个被应用直接引用） | 不存在 |
| 显示与合成 | EMUI VR 模式建一块虚拟屏承载应用，面板由框架送 DP | 只有"手机屏镜像" |
| 在线链 | 华为账号/商城/更新/配置下发 | 服务器已停服 |

**做法**：每遇到一个失败，先跑**未改动的原版**拿到第一个真实报错（errno / avc / 找不到服务或路径），
判断它跨的是上面哪一类边界，然后只补这一类。

### 2.2 补平台层的三条优先序

1. **原厂有同名原件 → 直接搬官方字节码**，只改"指向"（例如 `hwframework.jar` 里的
   `WifiManagerCommonEx`、`HuaweiTelephonyManager`，以及 `android.vrsystem.*` 整族）；
0 个类被判定为「原厂有、但我们手写」——`docs/OFFICIAL_SOURCE_AUDIT.md` 就是这张对账表。
2. **原厂没有、但公开 API 能等价表达 → 按真实语义实现**（`SystemPropertiesEx`→系统属性、
   `SettingsEx`→`Settings`、`PowerManagerEx`→`PowerManager`、`HwNotchSizeUtil`→`DisplayCutout`…）。
3. **公开 API 也没有 → 按"不可用"语义处理**：抛 `NoExtAPIException`、返回中性值、或让原版
   走它自己的失败分支；**不编数据**。

### 2.3 补丁必须可回退、可审计

- 优先「新增 smali/Java 文件 + 最小清单改动」；必须改原方法时，脚本对原始文本做**锚点断言**，
  不匹配就报错停止（`patches/*.py` 共 33 个，全部是这个形状）；
- 每一处改动写进 `docs/PATCH_AUDIT.md`：原调用点 → 处理 → 由谁接管 → 真机证据；
- 每次提交一个计划项，提交信息写"模块 + 动作"。

### 2.4 分层验收，不拿"能装"当"能用"

四个阶段，各有硬指标：

| 阶段 | 目标 | 硬指标 |
| --- | --- | --- |
| 1 | 主线可进可退 | 开应用 → 插眼镜 → 准备页 → VR 空间 → 手柄导航 → 返回 → 拔插恢复；无 FATAL/ANR |
| 2 | 眼镜里显示的是 VR 内容 | 眼镜 display 上不再镜像手机层；面板 3200×1600；无 Letterbox 黑边；双眼重合 |
| 3 | 时序达标 | 90Hz 输出、pose→光子延迟有实测、画面不抖 |
| 4 | 各模块可用 | 视频/投屏/商城射线/手柄全键位；飞行模式下可用 |

---

## 3. 架构：七个包怎么串起来

原版在 EMUI 上的链路是「系统 VR 服务 + 六个应用」。通用安卓上没有那个系统服务，
所以我们在**第七个包（vrservice）+ Runtime（hvrsdkserverapp）**里把它重建出来：

```
用户打开「华为VR」(appmarket)
  └─ HvrContextProvider（进程入口）拉起环境
       ├─ VrGlassWatchService（前台服务，Runtime 包）
       │    ├─ 启动原厂 MyService → startNative() → VrHelmetExt.init()（姿态/头盔链路）
       │    └─ VrSystemActor（系统侧替身）
       └─ VrParamsInitializeService（vrservice 包，原厂组件）

插入眼镜
  └─ VrSystemActor 用 USB 身份（VID 0x12d1 + PID 0x107e/0x1092）+ 外接屏 判定在位
       ├─ bind 桌面 VRService（com.huawei.client.vrservice.VRService）
       ├─ Messenger 握手 0x3e9，随后 0x1 / 0xf / 0xf / 0x3eb
       ├─ 每 3/8/15/25 秒 + 每 20 秒向手柄发 ACTION_RECONNECT_MSG
       └─ 回答 what=0x835/0x836/0x838（VR 模式 / 电量 / 接近）

桌面 VRService
  └─ vrEnvPrepare step 1/2/3 → VRPrepareActivity → start 3D Launcher → Unity MainActivity

跨进程的 vr_system
  └─ 桌面托管 content://com.huawei.vrlauncherx.registry（签名级权限）
       └─ 六个包的 android.vrsystem.VRSystemServiceManagerImpl 按活 binder 解析/重连
```

另外两个"系统级"组件：

- **KSU 模块 `hwvr_compat`**：造 `/dev/hwvr1`（内核 HID 驱动在 EMUI 上提供），
  并给眼镜 HID 节点授权；
- **LSPosed 模块 `com.hvr.displayrouting`**：只放行一个判断——
  允许我们七个包把 Activity 启动到自建的 `HUAWEI VR Display` 虚拟屏上。

---

## 4. 平台层替换清单

| 原厂机制 | 通用安卓上的实现 | 位置 |
| --- | --- | --- |
| `getSystemService("vr_system")` | 同名接口 + 跨进程注册表（桌面托管 ContentProvider） | `shared/java/android/vrsystem/*`、`VrSystemRegistryProvider` |
| `IVRSystemServiceManager.isVRMode()` | 由真实硬件（USB 身份 + 外接屏 + 握手进度）驱动 | `VrSystemActor` |
| `/dev/hwvr1` 的 HID feature report | KSU 模块建同名节点；协议是标准 `HIDIOCGFEATURE/SFEATURE`，无华为私有内核 ABI | `ksu/hwvr_compat`、`docs/HELMET_HID_PROTOCOL.md` |
| uid system 隐式权限 | 逐包显式声明 + 安装脚本 `pm grant` / `appops set`（`WRITE_SECURE_SETTINGS`、`SYSTEM_ALERT_WINDOW`、`PACKAGE_USAGE_STATS`、`READ_PHONE_STATE`…） | `patches/patch_platform_permissions.py`、`install-six.ps1` |
| `androidhwext` 主题 | 把主题父级与属性引用改成公共 `Theme/attr`（保留原布局与文案） | `patches/patch_hwext_*`、`patch_emui_theme_parents.py` |
| 约 40 个 `com.huawei.android.*` 平台类 | 同名同签名实现：官方件优先，其次公开 API 映射，最后中性值 | `shared/java/**`（70 个 Java 文件） |
| EMUI 的 `HUAWEI VR Display` 虚拟屏 | `DisplayManager.createVirtualDisplay(PUBLIC)` + 眼镜面板上的 `Presentation`/`SurfaceView` 作输出目标 | `HvrVrVirtualDisplay`、`HvrVrPanelPresenter`、`HvrDisplayRouter` |
| 开机常驻的 vrservice | 改为"打开华为VR 时由进程入口拉起"（不做开机自启） | `HvrContextProvider` |
| 在线账号/商城/更新 | 按口径保留代码、恢复权限，服务器失败走原版分支 | `patches/patch_online_restore.py` |

---

## 5. 关键技术点与踩过的坑

每一条都是"现象 → 根因 → 处理"，细节与日志在 `PATCH_AUDIT.md` 对应小节。

1. **主应用包名被改错**（导致六包互不识别）→ 原包 dex 里只认 `com.huawei.appmarket.vr`；
   删掉改名逻辑，恢复原包名。
2. **`vr_system` 查不到** → 通用安卓没有这个系统服务名。做法：同名接口 + 注册表 provider +
   客户端按 `IBinder.isBinderAlive()` 判活重连；查不到就返回 null，让原版走它自己的分支。
3. **`/dev/hwvr1` 不存在** → EMUI 内核 `hid_vr` 驱动创建。反汇编确认所谓"华为私有接口"
   全是标准 `HIDIOCGFEATURE/SFEATURE`；KSU 模块建节点并授权（不写死 VID/PID）。
4. **uid system 的隐式权限** → 普通应用逐条显式化并用 appops/pm grant 补；
   典型报错：`BAL_BLOCK`、`WRITE_SECURE_SETTINGS`、`PACKAGE_USAGE_STATS` 为空、`getSerial` 被拒。
5. **`androidhwext` 主题父级找不到** → 重打包后 `Theme_NoTitle` 的父级在固件的
   `framework-res-hwext.apk` 里；把父级与属性换成公共主题，页面布局与文案不动。
6. **重打包 zip 结构不合规** → apktool 产出的条目同时带 data descriptor 与非零本地头尺寸，
   原版用 `ZipInputStream` 读自己 APK 会抛 `invalid entry size`（SDK 包 107 处、桌面 979 处）。
   新增 `tools/apk-rezip.py`：构建末段按原包对齐压缩方式重写 zip（`flag&0x8` 归零、
   `resources.arsc` 保持 STORED），并做断言。
7. **Android 14+ 动态广播** → 原版 `registerReceiver(receiver, filter)` 不带导出标志，
   视频包在 `VrPlayerApplication.onCreate` 直接抛 `SecurityException`。加兼容类
   `HvrReceiverCompat`，脚本改写 **88 处**调用点（按 Android 14 之前的语义取 `RECEIVER_EXPORTED`）。
8. **显示：手机镜像 → 虚拟屏** → 原来眼镜显示的是手机整屏镜像（连 `Letterbox` 层都镜像，
   就是黑边来源）。改为：自建 `HUAWEI VR Display` 虚拟屏（3200×1600），在眼镜面板上起
   `Presentation` + `SurfaceView`，把它的 Surface 作为虚拟屏输出目标。
9. **平台只允许"可信屏"承载别处启动的 Activity** → 非系统进程建的虚拟屏 `isTrusted()` 为假，
   连拥有者自己也被 `isCallerAllowedToLaunchOnDisplay` 拒；
   带 `VIRTUAL_DISPLAY_FLAG_TRUSTED` 会被 `ADD_TRUSTED_DISPLAY` 权限挡回。
   结论：用 LSPosed 模块只 hook 这一个判断（`lsposed/hvr-display-routing`）。
10. **手柄链路** → 手柄是私有 BLE 协议，系统没有 profile；`vrhandle` 自己连 GATT。
    真机已到 `mDeviceInfoList=1`、`UsingCtrl: DefaultController, status 5`；
    但 CF20 在蓝牙层**没有真正配对**（`bond_type:UNKNOWN`，无 link key），
    链路会周期性被远端断开，Unity 随之 `Controller Disconnected` / `Fail to GetPosture`。
11. **启动时序** → 准备页会在 `getVRModeState` 返回 false 时 `moveTaskToBack + finish`
    （`VRPrepareActivity should not show when glass out.`）。处理：把 `vrMode` 的置位点提前到
    "开始准备/识别到眼镜"那一刻，且仍以真实硬件为准，拔掉立即清零。
12. **手机被卡横屏/画面变形** → EMUI 的 `ignore-orientation-request` + `user_rotation` 被留下；
    退出 VR 时按原值还原，KSU 脚本不再每 2 秒重写。

---

## 6. 当前进度（2026-10-19 暂停时）

### 6.1 分阶段

| 阶段 | 状态 | 证据 |
| --- | --- | --- |
| 1 主线可进可退 | **基本通过** | `refresh(start) helmet=true` → `startPrepareActivity` → `vrEnvPrepare step 2/3` → `dp link good` → `start 3D Launcher` → `topResumedActivity=com.huawei.vrlauncherx/.MainActivity`；`UsingCtrl: DefaultController, status 5`；`mDeviceInfoList=1` |
| 2 眼镜显示 VR 内容 | **实现完成，待启用系统模块验证** | 虚拟屏 `HUAWEI VR Display 3200x1600` 已能创建；眼镜面板上 `Window{...} mDisplayId=19 ty=PRESENTATION`；跨应用路由被平台权限拦，LSPosed 模块已构建安装、**待启用** |
| 3 时序/重投影 | **未开始** | 官方 `IVrServiceManager`（`startFrontBufferDisplay`/`getVsync`/`setSchedFifo`…）目前只保接口 |
| 4 各模块可用 | **部分** | 视频：崩溃已修、能起；投屏：门槛判定已定位（必须非默认屏）；商城射线依赖手柄；离线未验 |

### 6.2 逐包状态

| 包 | 能启动 | 说明 |
| --- | --- | --- |
| 主应用 | ✅ | 页面原样；数据清空后需过一次原版阅读提示 |
| 桌面/空间 | ✅ | 主线跑通；控制器与头动有真实数据 |
| 视频 | ✅（入口待接） | `Application.onCreate` 崩溃已修；会走 2D 条款/登录页，VR 播放路径未接完 |
| 投屏 | ⚠️ | `MainActivity` 起后立即 `finish`，因为"在默认屏启动"（需要虚拟屏路由生效） |
| 手柄 | ⚠️ | 应用侧正常，CF20 未真正配对导致周期性掉线 |
| Runtime | ✅ | `MyService` 拉起、IMU 进流、`ArvrRuntimeService` 运行 |
| vrservice | ✅ | 注册/握手/准备流程正常 |

### 6.3 已交付的统计

- 工作仓 114 个提交（2026-09-14 → 2026-09-20）；
- 兼容层 70 个 Java 文件（含 stubs 与 runtime-actor）；
- 33 个补丁脚本、49 篇文档（含 66 节台账与真机取证）；
- 七个包均产出可安装 APK，统一签名（`signing/hvr-compat-debug.jks`）。

---

## 7. 未完成与下一步

| 优先级 | 事项 | 下一步具体动作 |
| --- | --- | --- |
| P0 | 眼镜输出层 | 在 LSPosed 里启用 `com.hvr.displayrouting`（作用域：android + 七包）→ 打上 `patch_vr_display_launch.py` → 跑 `lsposed/verify-display-routing.ps1` 验证四点：无 Permission Denial、VR 活动落在虚拟屏、面板有画面、投屏不再报默认屏错误 |
| P0 | CF20 配对 | 在系统蓝牙里真正配对（或按需在兼容层补 `createBond`），让 `bond_type=BONDED`，消除周期性 `Controller Disconnected` |
| P1 | 视频 VR 路径 | 查 `VrLauncherActivity → HVRActivity` 为什么走 2D（`openAbilityStart2D` 的置位来源），把本地列表接进 VR 播放器 |
| P1 | 时序/重投影 | 实现 `IVrServiceManager` 等价物（前缓冲 + 90Hz + late-latching），这是"戴着不晕"的唯一路径 |
| P2 | 手柄全键位验收 | 射线、触控板、扳机、Home/返回、音量逐项实测 |
| P2 | 离线验收 | 飞行模式下六模块启动与本地播放 |

---

## 8. 复现（构建 / 安装 / 验证）

### 8.1 环境

- JDK 17 + Android SDK（build-tools 35、platforms/android-35、platform-tools、NDK 26）
- 脚本不写死 SDK 路径，查找顺序：`HVR_ANDROID_SDK` → `<仓库>/工具链/android-sdk`
  → `<工作区根>/android-sdk` → `<仓库>/android-sdk`
- PowerShell 7；真机开启无线调试或 USB 调试

### 8.2 构建

```powershell
# 单包
.\build\build-module.ps1 -Package com.huawei.vrlauncherx -Revision r1
# 七包
.\build\build-all.ps1 -Revision r1
```

构建链：`javac`（shared + stubs）→ `d8` 生成兼容 dex → `apktool b` 重建 →
注入 `classesN.dex` → `tools/apk-rezip.py` 按原包对齐重写 zip →
`zipalign` → `apksigner`（七包同签名）。

### 8.3 安装与授权

```powershell
.\install-six.ps1 -Revision r1
```

它会：装七个包 → 启动一次主应用解除 stopped → 复位方向冻结 →
`appops`/`pm grant` 补系统 UID 原本隐式持有的权限 → 日志级别收敛 → 自检。

### 8.4 验证

```powershell
# 主线：开华为VR → 拔插眼镜 → 看准备页/空间
adb logcat | Select-String 'VrSystemActor|VRService_Client|start 3D Launcher|UsingCtrl'

# 显示路由（需要 LSPosed 模块先启用）
.\lsposed\verify-display-routing.ps1 -Serial <你的设备地址>
```

判据：`VrSystemActor: refresh(...) helmet=true`、`start 3D Launcher`、
`UsingCtrl: DefaultController, status 5`、`mDeviceInfoList≥1`；
显示侧：`dumpsys display` 有 `HUAWEI VR Display 3200x1600`、
`dumpsys window` 里眼镜 display 上有 `ty=PRESENTATION` 窗口。

---

## 9. 台账索引（想深入看哪一块）

| 文档 | 内容 |
| --- | --- |
| [PORTING_METHOD.md](PORTING_METHOD.md) | 方法论：只换平台层、四步法、硬性口径 |
| [PATCH_AUDIT.md](PATCH_AUDIT.md) | 66 节逐轮记录：现象/根因/处理/真机证据 |
| [HUAWEI_VR_SYSTEM_IFACES.md](HUAWEI_VR_SYSTEM_IFACES.md) | `vr_system` 的 AIDL 契约与各包引用面 |
| [HELMET_HID_PROTOCOL.md](HELMET_HID_PROTOCOL.md) | `/dev/hwvr1` 的真实协议（标准 HID feature report） |
| [OFFICIAL_SOURCE_AUDIT.md](OFFICIAL_SOURCE_AUDIT.md) | 手写类 vs 原厂件的逐类对账 |
| [PLATFORM_API_SURFACE.txt](PLATFORM_API_SURFACE.txt) | 40 个平台类的精确签名清单 |
| [BASELINE.md](BASELINE.md) | 原包 sha256 基线 |
| [OFFLINE_FEATURE_MATRIX.md](OFFLINE_FEATURE_MATRIX.md) | 逐屏的在线/本地分类 |
| [FIRMWARE_HMA11_EMUI11.md](FIRMWARE_HMA11_EMUI11.md) | 第七个包是怎么从固件里找到并提取的 |
| [evidence/](evidence/) | 真机取证（崩溃栈、HID 探测、主题父级等） |

---

## 10. 一句总结

这套移植的核心不是"改代码让它跑起来"，而是**把 EMUI 提供的那一层一层地基补回来**：
系统服务、设备节点、权限身份、资源、平台类、显示与合成。
应用层始终是原版，我们只在地基缺失处补等价物——每补一处都留下断言、台账和真机证据。
主线已经跑通；剩下的是显示输出（虚拟屏路由 + 重投影）和几处模块入口，
它们都已有明确的定位与下一步动作，而不是"不知道为什么不行"。
