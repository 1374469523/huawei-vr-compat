# LSPosed 签名伪造模块（**未完成，后续解决**）

## 为什么要它

2026-09-16 定位到：`com.huawei.himovie.vr`（华为VR视频）在**自签名的构建**上会
自己 SIGKILL 自己（日志 `IDS_TAG: ... has not finished training` →
`Process: Sending signal. PID: … SIG: 9`，无 Java 异常、无 tombstone）。

三步对照证明成因是**签名**，不是我们的改动：

| 装的包 | 签名 | 结果 |
| --- | --- | --- |
| 原包 | 华为 | 正常 |
| 原包，一个字节没改，只重签 | 自签 | 自杀 |
| 移植构建 | 自签 | 自杀 |

守卫代码在运行时解密的那部分（原 dex 里搜不到 `IDS_TAG` 这些字符串，
同目录的 `libaegissec.so` 就是这套保护链），静态改不了，只能在系统层让应用
**读到官方签名**。见 `docs/PATCH_AUDIT.md` 第 30 节。

## 当前状态

- 已完成：`extract-certs.py` —— 按 `apksigner` 的权威指纹，从七个原包里
  各自取出官方签名证书（DN 相同、密钥不同，**必须按包各返回各的**），
  生成 `src/com/hvr/spoof/Certs.java`。
- 未完成：模块本体（Xposed 入口、PackageManager/SigningInfo 挂钩）、构建脚本、
  真机验证。
- 用户口径（2026-09-16）：**先记录，不阻塞主线**，等核心功能做完再回来处理。

## 恢复工作时要做的事

1. 写模块入口：`IXposedHookLoadPackage`，只对七个包生效；把
   `PackageManager.getPackageInfo*` / `getInstalledPackages` /
   `getPackageArchiveInfo` / `PackageManager.hasSigningCertificate` 的返回值里
   `signatures` 与 `signingInfo` 换成该包的原证书。
2. 构建：本仓库没有 Gradle，用 `build-tools` 的 aapt2 + d8 + apksigner 直接出包
   （参考 `build/build-module.ps1` 的做法）；Xposed API 用最小存根编译，
   运行期由 LSPosed 提供。
3. 真机：设备上目前只有 KernelSU（`me.weishu.kernelsu`）和 Shizuku，**没有
   LSPosed**；需要用户手动装 ZygiskNext + LSPosed 并在管理器里勾选作用域。
4. 验证：同一份自签原包，挂钩前自杀、挂钩后能起来，才算通过。
