# 华为 VR 六包 · 1:1 系统层替换（新仓）

本仓库只做一件事：**把六个华为 VR 原包依赖的华为/EMUI 系统层，换成通用安卓实现**。
原版 Java 与 Unity 逻辑保持原样，不改界面、不写替代首页、不伪造登录；联网与账号链按批准范围去掉。

---

## 先说清楚：这个仓库是什么、东西都在哪

这是项目**暂停时的源码归档**（2026-10-19）。完整开发工作区、114 条提交历史、
45 GB 系统固件和 1.2 GB 解码树都留在本地，这里只放可公开/可复现的部分。

### 顶层目录

| 路径 | 内容 |
| --- | --- |
| `原包/` | **原始 APK**（见下方清单） |
| `shared/` | 平台兼容层源码：`shared/java`（约 40 个华为平台类）、`shared/stubs`、`shared/runtime-actor` |
| `patches/` | 30+ 个逐项可回退的补丁脚本（带锚点断言，不匹配即报错） |
| `build/` | `build-module.ps1`（单包）、`build-all.ps1`（七包） |
| `tools/` | apktool 2.10/2.4 + framework、Cecil、`DexDump`、EROFS 解包、`apk-rezip.py`、SDK 路径解析器、分析脚本 |
| `ksu/` | KernelSU 模块 `hwvr_compat`（`/dev/hwvr1` 与 HID 授权） |
| `lsposed/` | LSPosed 模块 `com.hvr.displayrouting`（放行 VR 活动启动到自建虚拟屏） |
| `signing/` | 七包统一调试签名（口令写在下面「签名」一节） |
| `docs/` | 全部台账与取证，入口见文末「台账索引」 |
| `install-six.ps1` | 装七个包 + 补授权（adb 路径运行时解析，不写死） |
| `ARCHIVE.md` | 归档范围、排除项与复现步骤的完整说明 |

### 原始 APK 在哪

**没有使用 Git LFS**，直接 `git clone` 就能拿到下面六个普通文件：

| 文件（`原包/`） | 大小 |
| --- | --- |
| `com.huawei.appmarket.vr.apk`（主应用） | 66.5 MB |
| `com.huawei.hvrsdkserverapp.apk`（Runtime / SDK） | 63.8 MB |
| `com.huawei.vrlauncherx.apk`（桌面 / VR 空间） | 56.3 MB |
| `com.huawei.vrvirtualscreen.apk`（投屏） | 14.1 MB |
| `com.huawei.vrhandle.apk`（手柄） | 8.5 MB |
| `com.huawei.vrservice.apk`（第七个包，从固件提取） | 2.9 MB |

第七个原始包 **`com.huawei.himovie.vr.apk`（VR 视频，111.4 MB）** 超过 GitHub
仓库单文件 100 MB 的硬限制，因此放在 **Release 附件** 里：

- 页面：https://github.com/1374469523/huawei-vr-compat/releases/tag/original-apks-v1
- 直链：https://github.com/1374469523/huawei-vr-compat/releases/download/original-apks-v1/com.huawei.himovie.vr.apk

下载后放进 `原包/`，就和仓库里的六个凑齐七个，可以按下面的「反编译」「构建」步骤复现。

### 刻意没有放进来的

| 内容 | 原因 |
| --- | --- |
| `decode/<包名>/`（1.2 GB 反编译树） | **逆向产物，按要求不入库**；把七个原包放回 `原包/` 后用 `tools/apktool_2.10.0.jar` 解码即可重建（见「反编译」） |
| `系统固件/`（45 GB）、`工具链/`（3.5 GB） | 本地大件，不入库 |
| `build/out/`、`build/evidence/` | 构建产物与真机取证截图 |
| `旧版/` | 旧一轮移植代码与旧仓存档，**已删除**；访问 `/tree/main/旧版` 会 404，这是预期行为 |

> 需要完整历史或固件时，请用本地工作区 `D:\Code\华为VR\华为VR_兼容版本`；
> 本仓库是快照，不包含 114 条逐轮提交。

---

> **动手前先读 [`docs/PORTING_METHOD.md`](docs/PORTING_METHOD.md)。**
> 那是本项目的执行口径：只动和系统不兼容的那一层，接口不动，先查原厂怎么做的再动手，
> 每轮改动都要落地到文件。偏离该文档的改动视为跑偏。

> **想先看全貌？读 [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)。**
> 那份文档讲清了：整体思路（怎么判断该补哪一层）、架构（七个包怎么串起来）、
> 平台层替换清单、踩过的坑与解法、以及分阶段/逐包的当前进度与下一步。

## 目录

| 路径 | 内容 |
|---|---|
| `原包/` | 六个未改动的原始 APK；第七个（视频，111 MB）在 Release `original-apks-v1`（见上文） |
| `decode/<包名>/` | apktool 全量反编译树（含资源）。**本仓库不包含**，按「反编译」一节重建 |
| `shared/java/` | 平台兼容层源码（40 个平台类 + `vr_system` 实现） |
| `patches/` | 每模块一个补丁脚本（在解码树上做最小改动） |
| `ksu/hwvr_compat/` | 系统侧配套的 KernelSU 模块（重建 `/dev/hwvr1`，按协议探测选接口） |
| `tools/` | apktool 2.10.0、framework(1.apk/2.apk)、解码与签名辅助工具 |
| `signing/` | 六包统一签名密钥 |
| `build/` | 构建脚本；`build/out`、`build/evidence` 不入 git |
| `docs/` | **[移植方法](docs/PORTING_METHOD.md)**、基线、接口台账、补丁审计、离线功能矩阵 |

## 六个包

| 模块 | 包名 | 源文件 |
|---|---|---|
| 主应用 | `com.huawei.appmarket.vr` | 根目录 `华为VR.apk` |
| 桌面 / VR 空间 | `com.huawei.vrlauncherx` | `华为VR桌面.apk` |
| 视频 | `com.huawei.himovie.vr` | `华为VR视频.apk` |
| 投屏 | `com.huawei.vrvirtualscreen` | `VR手机投屏.apk` |
| 手柄 | `com.huawei.vrhandle` | `VR手机手柄.apk` |
| Runtime / SDK | `com.huawei.hvrsdkserverapp` | `华为vrsdk3.5.0.82.apk` |

主应用原包名是 `com.huawei.appmarket.vr`：六个原包的 dex 里没有任何一处引用 `com.huawei.vr`，
所以**禁止把主应用改名**。

## 反编译

```powershell
$repo = $PSScriptRoot   # 在仓库根目录执行；换成该脚本所在目录即可
. (Join-Path $repo 'tools/sdk-path.ps1')
$sdk  = Resolve-HvrAndroidSdk -RepoRoot $repo          # 自动找 SDK，不写死路径
$jdk  = (Get-ChildItem (Join-Path $sdk 'jdk17tmp') -Directory | Select-Object -First 1).FullName
$java = Join-Path $jdk 'bin/java.exe'
foreach ($pkg in 'com.huawei.appmarket.vr','com.huawei.vrlauncherx','com.huawei.himovie.vr',
                 'com.huawei.vrvirtualscreen','com.huawei.vrhandle','com.huawei.hvrsdkserverapp') {
    & $java -jar tools/apktool_2.10.0.jar d -f -p tools/framework -o "decode/$pkg" "原包/$pkg.apk"
}
```

SDK 位置由 `tools/sdk-path.ps1`（PowerShell）/ `tools/sdk_path.py`（Python）运行时解析，
查找顺序：`HVR_ANDROID_SDK` 环境变量 → `<仓库>/工具链/android-sdk` → `<工作区根>/android-sdk`
→ `<仓库>/android-sdk`。`D:\Code\华为VR\android-sdk` 是一份**独立的完整拷贝**（3.5 GB），
给习惯从工作区根找 SDK 的工具用；工程自己的脚本默认优先 `工具链/android-sdk`。

## 签名

六包必须同签名，否则跨模块调用（同签名才允许的显式组件与权限校验）会失败。

- 密钥库：`signing/hvr-compat-debug.jks`
- alias：`hvrcompat`，storepass / keypass：`android`

这是本项目专用的调试密钥，入库只为让构建可复现。

## 构建与安装

```powershell
# 单个模块（在 build/out/ 出包）
build/build-module.ps1 -Package com.huawei.hvrsdkserverapp -Revision r23

# 六个一次
build/build-all.ps1 -Revision r23

# 装机（含必要的授权补丁）
install-six.ps1 -Revision r23
```

系统侧配套模块（重建 /dev/hwvr1）单独打包安装：

```powershell
# 打包 ksu/hwvr_compat -> build/hwvr_compat.zip，再在设备上
#   su -c "/data/adb/ksu/bin/ksud module install /data/local/tmp/hwvr_compat.zip"
# 本机只能用软重启；实测软重启即会拉起模块脚本，不需要真重启。
```

## 状态

**未完成。** 只有主线（插入眼镜 → 原提示 → 用户确认 → 准备流程 → 原 VR 空间 → CF20 手柄导航 →
视频/投屏 → 返回空间 → 拔插恢复）全部真机通过后，才会改状态。

异步投屏与头部跟踪本轮只保官方接口，实现留待后续补齐，详见 `docs/PATCH_AUDIT.md`。
