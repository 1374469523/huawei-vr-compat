# 华为 VR 六包 · 1:1 系统层替换（新仓）

本仓库只做一件事：**把六个华为 VR 原包依赖的华为/EMUI 系统层，换成通用安卓实现**。
原版 Java 与 Unity 逻辑保持原样，不改界面、不写替代首页、不伪造登录；联网与账号链按批准范围去掉。

> **动手前先读 [`docs/PORTING_METHOD.md`](docs/PORTING_METHOD.md)。**
> 那是本项目的执行口径：只动和系统不兼容的那一层，接口不动，先查原厂怎么做的再动手，
> 每轮改动都要落地到文件。偏离该文档的改动视为跑偏。

> **想先看全貌？读 [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)。**
> 那份文档讲清了：整体思路（怎么判断该补哪一层）、架构（七个包怎么串起来）、
> 平台层替换清单、踩过的坑与解法、以及分阶段/逐包的当前进度与下一步。

## 目录

| 路径 | 内容 |
|---|---|
| `原包/` | 六个未改动的原始 APK，按包名命名（基线，永不修改） |
| `decode/<包名>/` | apktool 全量反编译树（含资源） |
| `shared/java/` | 平台兼容层源码（40 个平台类 + `vr_system` 实现） |
| `patches/` | 每模块一个补丁脚本（在解码树上做最小改动） |
| `ksu/hwvr_compat/` | 系统侧配套的 KernelSU 模块（重建 `/dev/hwvr1`，按协议探测选接口） |
| `tools/` | apktool 2.10.0、framework(1.apk/2.apk)、解码与签名辅助工具 |
| `signing/` | 六包统一签名密钥 |
| `build/` | 构建输出与中间产物（不入 git） |
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
