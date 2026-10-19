# 华为VR视频「打开就闪退」：成因定位（2026-09-16）

## 结论（先说结果）

**不是我们的移植改坏的，也不是 Java 层异常。**
`com.huawei.himovie.vr` 里有一个**自己的完整性守卫**（日志 tag `IDS_TAG`），
它在检测到 APK 不是华为签名之后，**自己给自己发 SIGKILL**：

```
I IDS_TAG : App com.huawei.vrlab.VrPlayerApplication@... has not finished training
I Process : Sending signal. PID: 28806 SIG: 9
I ActivityManager: Process com.huawei.himovie.vr (pid 28806) has died: fg TOP
```

没有 `FATAL EXCEPTION`，没有 tombstone —— 不是崩溃，是**自杀**。

## 三步对照（决定性证据）

同一台设备（SM-F731U1 / Android 16），同一个 Activity
`com.huawei.himovie.vr/com.huawei.vrlab.twodimensional.login.TermsLoginActivity`：

| 装的包 | 签名 | 结果 |
| --- | --- | --- |
| `原包/com.huawei.himovie.vr.apk` | 华为（`CN=China, OU=Huawei, O=Huawei`，sha256 `186cffec…`） | **正常**：`has not finished training` → `Closing IDS observe window` → `IDS count updated to 1`，进程存活 |
| 同一个原包，**只重新签名**（我们的 key `CN=HVR Offline`，sha256 `30094ded…`），其它一个字节没改 | 自签 | **自杀**：`Clearing training data` → `has not finished training` → `Sending signal. PID: … SIG: 9` |
| 我们移植构建的 `build/out/com.huawei.himovie.vr-r24.apk` | 自签 | 同上，自杀 |

第二行是关键：**原包一行没改、只换签名就崩**，所以成因是签名本身，
与我们改过的 manifest / 组件 / 权限 / 平台类无关。

## 复现命令

```powershell
$adb = 'D:\Code\华为VR\华为VR_兼容版本\工具链\android-sdk\platform-tools\adb.exe'
$s   = '<phone-ip>:15038'
# 1) 清日志并按 Activity 启动
& $adb -s $s logcat -c
& $adb -s $s shell am start -W -n com.huawei.himovie.vr/com.huawei.vrlab.twodimensional.login.TermsLoginActivity
# 2) 8 秒后看这三行
& $adb -s $s logcat -d | Select-String 'IDS_TAG|Sending signal|has died'
```

重签（只换签名，不改内容）：

```powershell
$env:JAVA_HOME='D:\Code\华为VR\华为VR_兼容版本\工具链\android-sdk\jdk17tmp\jdk-17.0.20.1+1'
cd D:\Code\华为VR\华为VR_兼容版本
& 'D:\Code\华为VR\华为VR_兼容版本\工具链\android-sdk\build-tools\35.0.0\zipalign.exe' -f -p 4 `
    '原包\com.huawei.himovie.vr.apk' 'build\resign-test-himovie-a.apk'
& 'D:\Code\华为VR\华为VR_兼容版本\工具链\android-sdk\build-tools\35.0.0\apksigner.bat' sign `
    --ks signing\hvr-compat-debug.jks --ks-pass pass:android `
    --ks-key-alias hvrcompat --key-pass pass:android `
    --out 'build\resign-test-himovie-signed.apk' 'build\resign-test-himovie-a.apk'
```

## 这条失败点属于哪一类边界

按 `docs/PORTING_METHOD.md` 第 2 节的分类：**不是设备节点 / 系统服务 / 权限 /
显示 / 总线 / 在线依赖**，而是**应用自带的签名完整性校验**。
它校验的对象是「APK 的签名者」，绕过它的位置在**系统层**，不在应用代码里。

`IDS_TAG` 这些字符串在 `原包/com.huawei.himovie.vr.apk` 的 dex 与 .so 里都搜不到，
说明守卫代码位于运行时解密/保护的那部分（应用同目录里的 `libaegissec.so`
就是这套保护链）。这也解释了为什么无法靠读 smali 直接定位。

## 下一步（系统层解法，按优先级）

1. **签名伪造**：用用户已有的 KSU + LSPosed，让目标应用读到的签名是华为原签名
   （hook `PackageManager.getPackageInfo(...GET_SIGNING_CERTIFICATES)` 一类调用）。
   这是「只改指向、不改代码」的解，符合项目口径。
2. 若伪造不可行，再考虑对守卫本身做最小 patch —— 但那属于改原版逻辑，必须
   先记台账、并说明为什么没有系统层等价物。
3. **在没有签名伪造之前，不要再反复重装自签包来复现这个现象**：
   它与我们的移植改动无关，已经用「只重签的原包」证伪。

## 影响面（待验证的推断，不要当结论）

七个包里可能不止视频一个带这种守卫（桌面之前「splash 后立刻 finish」是另一种
表现，需要单独按同一方法验证：原包 vs 只重签的原包）。
**验证顺序永远先做「原包 vs 只重签的原包」对照**，再决定是不是移植问题。
