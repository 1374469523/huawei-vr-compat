# HVR 显示路由（LSPosed 辅助模块）

只做一件事：**放行华为 VR 七包把 VR 活动启动到自建的 `HUAWEI VR Display` 虚拟屏上**。

## 为什么需要它

原版由 EMUI 的 VR 模式把 VR 应用放到 `HUAWEI VR Display` 那块虚拟屏上。通用安卓上
我们已用公开 API 把同一块屏建出来（名字、尺寸 3200×1600 都对齐，见
`shared/java/com/huawei/vrframework/compat/HvrVrVirtualDisplay.java`），但往它上面
启动活动会被平台拒绝：

```
SecurityException: Permission Denial: starting Intent {... VRPrepareActivity}
  from ProcessRecord{...com.huawei.vrservice/u0a421} (pid=..., uid=10421)
  with launchDisplayId=27
```

根因在 `ActivityTaskSupervisor.isCallerAllowedToLaunchOnDisplay`：它先判「这块屏是否
trusted」，而非系统进程建的虚拟屏都不 trusted，**连屏的拥有者自己也不放行**；要过这关
需要 `INTERNAL_SYSTEM_WINDOW`（signature 级），普通应用拿不到。本机签名（从设备
`/system/framework/services.jar` 查出）：

```
Lcom/android/server/wm/ActivityTaskSupervisor;->isCallerAllowedToLaunchOnDisplay(IIILandroid/content/pm/ActivityInfo;)Z
```

## 它做了什么

hook 上面那个方法：**当调用方是我们这七个包之一、且目标屏不是默认屏（launchDisplayId > 0）
时，直接返回 true**。其它任何情况一律不干预。

七个包：`com.huawei.vrlauncherx` / `com.huawei.himovie.vr` / `com.huawei.vrvirtualscreen` /
`com.huawei.appmarket.vr` / `com.huawei.vrhandle` / `com.huawei.hvrsdkserverapp` / `com.huawei.vrservice`。

## 构建与加载

```powershell
.\lsposed\build-module.ps1 -Revision r1
# 产物：lsposed\out\com.hvr.displayrouting-r1.apk
```

1. 安装这个 APK（已经随构建装过一次也行）；
2. 在 LSPosed 里启用「HVR 显示路由」，作用域勾选：`系统框架 (android)` + 上面七个包；
3. 重启手机（或至少重启 `system_server`：勾选作用域后 LSPosed 会提示重启）。

启用之后 `parse` 日志里会看到：

```
HvrDisplayRouting: hooked com.android.server.wm.ActivityTaskSupervisor#isCallerAllowedToLaunchOnDisplay
HvrDisplayRouting: allow uid 10421 to launch on display 28
```

## 关掉它

在 LSPosed 里停用即可：停了之后行为与不开这个模块完全一样（VR 活动回到手机默认屏，
投屏仍会因为「app start on default display error」而退出）。
