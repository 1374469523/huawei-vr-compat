# 归档说明（2026-10-19）

这是「华为 VR 七包兼容移植」项目**暂停时的源码归档**。完整工作区留在本地
`D:\Code\华为VR\华为VR_兼容版本`，本仓库是可公开/可复现的那部分。

> **公开前已脱敏**：真机取证里的手机无线调试地址与 CF20 手柄 MAC 已替换为
> `<phone-ip>` / `<cf20-mac>`；`lsposed/verify-display-routing.ps1` 的设备地址改为
> `-Serial` 参数（默认 `127.0.0.1:5555`，按自己的环境传）。

## 这个归档包含什么

| 目录 | 内容 |
| --- | --- |
| `shared/` | 平台兼容层源码：`shared/java`（约 40 个华为平台类的同名实现）、`shared/stubs`（编译期存根）、`shared/runtime-actor`（系统侧替身：`VrSystemActor`、`HvrVrVirtualDisplay`、`HvrVrPanelPresenter` 等） |
| `patches/` | 逐项可回退的补丁脚本（带锚点断言，不匹配即报错），约 30 个 |
| `build/` | 构建入口：`build-module.ps1`（单包）、`build-all.ps1`（七包） |
| `tools/` | apktool 2.10 / 2.4、apktool framework、Cecil、`DexDump`（dexlib2 反汇编）、EROFS 解包、`apk-rezip.py`（修 zip data descriptor）、各类分析脚本、SDK 路径解析器 |
| `ksu/` | KernelSU 模块 `hwvr_compat`：造 `/dev/hwvr1`、给眼镜 HID 节点授权 |
| `lsposed/` | LSPosed 模块 `com.hvr.displayrouting`：放行「VR 活动启动到自建虚拟屏」这一个平台判断，含构建脚本与加载说明 |
| `signing/` | 七包统一调试签名（`hvr-compat-debug.jks`，口令写在 README） |
| `docs/` | 全部台账与取证：`PATCH_AUDIT.md`（66 节）、`HELMET_HID_PROTOCOL.md`、`HUAWEI_VR_SYSTEM_IFACES.md`、`OFFICIAL_SOURCE_AUDIT.md`、`BASELINE.md`、`OFFLINE_FEATURE_MATRIX.md`、`evidence/`、`reference/` |
| `原包/` | **原始 APK**：六个直接入库（`appmarket` 66.5 MB / `hvrsdkserverapp` 63.8 MB / `vrlauncherx` 56.3 MB / `vrvirtualscreen` 14.1 MB / `vrhandle` 8.5 MB / `vrservice` 2.9 MB）；**`com.huawei.himovie.vr.apk`（111.4 MB）超过 GitHub 单文件 100 MB 上限，放在 Release「original-apks-v1」的附件里** |
| `install-six.ps1` | 装七个包 + 补授权（adb 路径运行时解析，不写死） |

## 刻意**没有**归档的内容

| 内容 | 原因 |
| --- | --- |
| `decode/`（1.2 GB 反编译树） | **逆向产物，按要求不入库**；可由 `原包/` + `tools/apktool_2.10.0.jar` 重建（README 有命令） |
| `系统固件/`（45 GB）、`工具链/`（3.5 GB） | 本地大件，且固件为华为官方镜像，不随仓库分发 |
| `旧版/` | 旧一轮移植的代码/脚本已删除，不再保留 |
| `build/out/` 与 `build/evidence/` | 构建产物与真机取证截图 |

## 怎么从归档复现

1. 准备环境：JDK 17 + Android SDK（build-tools 35、platform-35）；脚本会自动找 SDK，
   顺序为 `HVR_ANDROID_SDK` → `<仓库>/工具链/android-sdk` → `<工作区根>/android-sdk`。
2. `原包/` 里已有六个原始 APK；第七个 `com.huawei.himovie.vr.apk` 从
   [Releases](https://github.com/1374469523/huawei-vr-compat/releases/tag/original-apks-v1) 下载后放进 `原包/` 即可。
3. 按 `README.md` 的「反编译」一节解码到 `decode/<包名>/`。
4. 依次运行 `patches/` 里的脚本（顺序见 `docs/PATCH_AUDIT.md` 各节）。
5. `build/build-all.ps1 -Revision r1` 出七个 APK，`install-six.ps1 -Revision r1` 装机。

## 项目状态（暂停时）

- 七个包：能装、能起、能串起来；主线「开应用 → 插眼镜 → 准备页 → VR 空间 → 手柄/头动」跑通。
- 已修：Android 14+ 动态广播缺 `RECEIVER_EXPORTED` 导致视频包 `Application.onCreate` 崩溃；
  重打包 zip 的 data descriptor 导致原版 `ZipInputStream` 抛异常；主应用包名、在线链、启动闸门等。
- 未完成：眼镜输出层（虚拟屏 + 面板 + 路由已实现，等待启用 LSPosed 模块验证）、
  VR 视频 2D 登录路径、投屏启动门槛、CF20 真正配对后的稳定性。
