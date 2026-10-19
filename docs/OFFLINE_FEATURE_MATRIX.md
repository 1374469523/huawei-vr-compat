# 离线功能矩阵（证据台账）

用途：证明「去掉联网/登录」没有顺手删掉本地功能。每一行都要有可复现的证据。

## 一、静态对照：组件是否被误删

比较对象：`原包/<包名>.apk`（未改动）与 `build/out/<包名>-r1.apk`（本次构建）。
统计方式：`aapt2 dump xmltree --file AndroidManifest.xml` 中
`E: activity` / `E: service` / `E: receiver` / `E: provider` 的条数。

| 包名 | 原包 act/svc/rcv/prv | 新包 act/svc/rcv/prv | 结论 |
|---|---|---|---|
| `com.huawei.appmarket.vr` | 32/10/2/8 | 31/10/2/8 | 只少 1 个 `com.huawei.hwid.api.common.apkimpl.DummyActivity`（华为账号占位页） |
| `com.huawei.himovie.vr` | 67/4/2/8 | 54/4/2/8 | 只少 13 个 `com.huawei.phoneservice.feedback.*`（问题反馈界面） |
| `com.huawei.hvrsdkserverapp` | 3/1/0/0 | 3/1/0/0 | 完全一致 |
| `com.huawei.vrhandle` | 10/1/0/1 | 10/1/0/1 | 完全一致 |
| `com.huawei.vrlauncherx` | 13/7/0/1 | 13/7/0/1 | 完全一致 |
| `com.huawei.vrvirtualscreen` | 7/0/0/0 | 7/0/0/0 | 完全一致 |

「完全一致」包含 service / receiver / provider：本轮**没有**像旧补丁那样整体删除它们。

## 二、移除的权限（每包逐条）

| 包名 | 去 UID | 去在线权限 | 去必装库 | 说明 |
|---|---|---|---|---|
| `com.huawei.appmarket.vr` | - | 10 | - | INTERNET / UDID / 安装包 / hwid / SMART_PROVIDER 等 |
| `com.huawei.himovie.vr` | - | 3 | - | INTERNET / UDID / CHANGE_NETWORK_STATE |
| `com.huawei.hvrsdkserverapp` | - | 0 | - | 二进制 manifest，且本来没有 INTERNET |
| `com.huawei.vrhandle` | - | 1 | - | INTERNET（蓝牙权限保留） |
| `com.huawei.vrlauncherx` | 1 | 4 | 1 | 另去 `android:sharedUserId="android.uid.system"` 与必装库 `nearbysdk` |
| `com.huawei.vrvirtualscreen` | 1 | 1 | - | 另去 `android:sharedUserId="android.uid.system"` |

构建脚本会在打包后断言「包名等于原包名」且「不含 INTERNET」，不通过就中断。

### 保留 `ACCESS_NETWORK_STATE` / `ACCESS_WIFI_STATE`（有证据的更正）

最初把这两个权限也一起删了，结果主应用 **一启动就崩**：

```
java.lang.RuntimeException: Unable to create application
    com.huawei.hwmarket.vr.framework.app.StoreApplication
Caused by: java.lang.SecurityException: ConnectivityService: Neither user 10370 nor
    current process has android.permission.ACCESS_NETWORK_STATE.
    at android.net.ConnectivityManager.registerNetworkCallback(...)
    at com.huawei.hwmarket.vr.service.alarm.NetWorkConnectivityManager.register(...)
    at com.huawei.hwmarket.vr.framework.app.StoreApplication.onCreate(...)
```

（这就是之前「华为VR 打开是白屏」的根因：进程在 `Application.onCreate` 就被它的 CrashHandler 杀掉。）

这两个权限只允许**读取**网络状态，不给任何联网能力；去掉 INTERNET 之后应用仍然发不出请求。
所以按证据更正为：**保留状态观察权限，只移除真正的联网与华为在线权限**。

更正后实测：主应用正常进入原版首屏 `com.huawei.hwmarket.vr.framework.activity.WelcomeVRActivity`
（截图 build/main-app-r2b.png，画面内容为原版「欢迎使用华为 VR / 开启 VR 之旅」），
不再是白屏。

## 三、界面逐屏分类（待补）

计划：对每个可达界面用 `uiautomator` 抓取，标注数据来源（本地/在线/混合），只移除在线专用屏。
当前状态：**待真机逐模块跑**，结果按下面的表格式补进本节。

| 包名 | 界面 | 数据来源 | 处理 | 离线后是否可用 | 证据 |
|---|---|---|---|---|---|
| （待填） | | | | | |

## 四、构建产物

| 包名 | APK | sha256 |
|---|---|---|
当前已安装的版本为 **r2**（保留状态观察权限、去掉必装库的更正版）：

| 包名 | APK | sha256 |
|---|---|---|
| `com.huawei.hvrsdkserverapp` | `build/out/com.huawei.hvrsdkserverapp-r2.apk` | `4D541A2C2748AA09A3A68A0C13E84B301BFF980EEC73B3567595650D7E85372D` |
| `com.huawei.vrhandle` | `build/out/com.huawei.vrhandle-r2.apk` | `F6570F57D89462FD3E242C7FDE19540BBECA4BAB389EB1DC7AAA7DABBF36B60A` |
| `com.huawei.vrvirtualscreen` | `build/out/com.huawei.vrvirtualscreen-r2.apk` | `502B49E2D7DBFA536526400356E8C04BFBA666BB5C7704B74D000B5FE2FA50EB` |
| `com.huawei.himovie.vr` | `build/out/com.huawei.himovie.vr-r2.apk` | `879FBFC694441C4510D32136493915E3A991B433BB809896B6214D424CE6570E` |
| `com.huawei.vrlauncherx` | `build/out/com.huawei.vrlauncherx-r2.apk` | `A1E429787941A57503AF8A2CD45DF508EEBA9769A0545CBB9650ED8FFEF56EBB` |
| `com.huawei.appmarket.vr` | `build/out/com.huawei.appmarket.vr-r2.apk` | `BEDCB06D996B850F2E2093603E6716A8D9006C638AA4BFCFE4960248D7E0FE16` |
