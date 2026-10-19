<#
安装七个模块，并把「通用安卓不再自动给、但原版依赖系统 UID 天然拥有」的授权补齐。

文件名保留 install-six.ps1 是因为前面几轮的文档与习惯都指向它；现在装的是七个包
（第六个之外的第七个是 com.huawei.vrservice —— 从 HMA-AL00 EMUI 11 整包固件里
提取到的 VR 系统服务本体，它才是 vr_system 的注册方和准备流程的发起方）。

权限声明都在各包 manifest 里（patches/patch_platform_permissions.py 负责加）；
本脚本只做运行时/特殊授权，也就是必须由 shell、Shizuku 或 root 才能给的那部分：

  appops WRITE_SETTINGS        桌面/视频/投屏写 Settings.System（原版靠系统 UID）
                               vrservice 也要这条：原版它是 uid 0，改 Settings 不需要批准
  appops SYSTEM_ALERT_WINDOW   桌面进空间、手柄后台启动前台服务的豁免
  pm grant WRITE_SECURE_SETTINGS  桌面 Hw6dofMonitor 写 Settings.Global
  pm grant READ_PHONE_STATE       进入 VR 前的通话判断
  deviceidle whitelist         三个长驻组件在待机时不被压制

缺了 SYSTEM_ALERT_WINDOW 的手柄包会在桌面后台拉起时崩溃，系统显示
「华为 VR 手柄屡次停止运行」；证据与 A/B 复现在 docs/PATCH_AUDIT.md 第八节。

用法：
    .\install-six.ps1                 # 安装 build/out 里每个包的最新 APK 并补授权
    .\install-six.ps1 -Revision r5    # 只安装指定版本
    .\install-six.ps1 -SkipInstall    # 只补授权，不重新安装
#>
param(
    # 留空则用 tools/sdk-path.ps1 自动解析（工程内 工具链/android-sdk 或工作区根 android-sdk）
    [string]$Adb = '',
    [string]$Revision = '',
    [switch]$SkipInstall
)
$ErrorActionPreference = 'Stop'

$repo = $PSScriptRoot
if (!$Adb) {
    . (Join-Path $repo 'tools/sdk-path.ps1')
    $Adb = Resolve-HvrAdb -RepoRoot $repo
}
$outDir = Join-Path $repo 'build\out'
$packages = @(
    'com.huawei.appmarket.vr',
    'com.huawei.vrlauncherx',
    'com.huawei.himovie.vr',
    'com.huawei.vrvirtualscreen',
    'com.huawei.vrhandle',
    'com.huawei.hvrsdkserverapp',
    'com.huawei.vrservice'
)

function Invoke-Adb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $output = & $Adb @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "adb $($Arguments -join ' ') 失败：$output"
    }
    return $output
}

function Newest-Apk {
    param([string]$Package)
    if ($Revision) {
        $path = Join-Path $outDir "$Package-$Revision.apk"
        if (!(Test-Path -LiteralPath $path)) { throw "缺少 $path" }
        return $path
    }
    $candidate = Get-ChildItem -LiteralPath $outDir -Filter "$Package-*.apk" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($null -eq $candidate) { throw "build/out 里没有 $Package 的 APK，请先构建" }
    return $candidate.FullName
}

Write-Output "== 设备 =="
Invoke-Adb -Arguments @('devices', '-l') | Write-Output

if (!$SkipInstall) {
    foreach ($package in $packages) {
        $apk = Newest-Apk $package
        Write-Output "== 安装 $package ($(Split-Path $apk -Leaf)) =="
        $output = & $Adb install -r -d $apk 2>&1
        if ($LASTEXITCODE -eq 0) {
            $output | Select-Object -Last 1 | Write-Output
            continue
        }
        # 这台设备上出现过：同一个已安装的 APK 覆盖装都报
        #   INSTALL_FAILED_UPDATE_INCOMPATIBLE: upgrade keys do not match
        # （设备装有 HMA 等会 hook system_server PackageManager 的模块，
        #   签名记录与实际 APK 对不上）。全新安装始终成功，所以兜底为
        # 完整卸载后重装；代价是该包的本地数据被清空。
        if (($output -join "`n") -match 'INSTALL_FAILED_UPDATE_INCOMPATIBLE') {
            Write-Warning "  $package 覆盖装被设备拒绝，改为完整卸载后重装（该包本地数据会丢失）"
            Invoke-Adb -Arguments @('shell', 'cmd', 'package', 'uninstall', $package) | Out-Null
            Invoke-Adb -Arguments @('install', '-r', '-d', $apk) |
                Select-Object -Last 1 | Write-Output
        } else {
            throw "adb install $apk 失败：$($output -join ' ')"
        }
    }
}

# 环境由谁拉起（2026-09-16 用户口径：不做开机自启，打开应用时自动启动）：
#
#   打开「华为 VR」主应用 -> 兼容层的进程入口（HvrContextProvider）显式启动
#   Runtime 的眼镜监督服务（com.huawei.hvrsdkserverapp/.compat.VrGlassWatchService）
#   与 vrservice 的 VrParamsInitializeService。
#
# 这是通用安卓里跨应用启动组件的标准做法：显式组件 + 目标应用自己声明的
# 签名级权限 com.huawei.hvrsdkserverapp.permission.RUNTIME_ALLOW（原厂清单里
# 本来就有）。装完这里用**公开命令**把主应用启动一次，既解除新装包的
# stopped 状态（否则收不到 USB 插入这类隐式广播），也让环境起来；
# 不投递任何受保护广播，也不模拟开机。
if (!$SkipInstall) {
    Write-Output "== 启动一次「华为 VR」，解除 stopped 状态并拉起环境 =="
    Invoke-Adb -Arguments @('shell', 'am', 'start', '-n',
            'com.huawei.appmarket.vr/com.huawei.hwmarket.vr.MainActivity') |
        Select-Object -Last 1 | Write-Output
}

# 方向冻结复位：EMUI 的 VR 模式会打开 ignore-orientation-request（冻结显示方向），
# 会话没释放干净时整机会卡在横屏——用户 2026-09-16 报的「手机画面被强制横屏」
# 就是它。这一条是幂等的安全操作，装包时统一清一遍。
Write-Output "== 复位显示方向冻结 =="
Invoke-Adb -Arguments @('shell', 'wm', 'set-ignore-orientation-request', 'false') | Write-Output

Write-Output "== 补授权 =="
$appOps = @(
    @('com.huawei.vrlauncherx', 'WRITE_SETTINGS'),
    @('com.huawei.himovie.vr', 'WRITE_SETTINGS'),
    @('com.huawei.vrvirtualscreen', 'WRITE_SETTINGS'),
    # Runtime 的系统侧 actor 用它在眼镜在位时锁横屏（EMUI 的 VR 模式行为）
    @('com.huawei.hvrsdkserverapp', 'WRITE_SETTINGS'),
    # vrservice 原版是 uid 0，改 Settings 不需要批准；普通应用要靠这条 appop
    @('com.huawei.vrservice', 'WRITE_SETTINGS'),
    # SYSTEM_ALERT_WINDOW 是公开的后台启动 Activity 豁免：桌面从
    # com.huawei.vrservice 进程里起 VRPrepareActivity / MainActivity，没有它
    # Android 10+ 直接拦掉（ActivityTaskManager: Abort background activity
    # starts from 10421），VR 空间永远进不去。手柄/投屏的服务同样要这条。
    @('com.huawei.vrlauncherx', 'SYSTEM_ALERT_WINDOW'),
    @('com.huawei.vrhandle', 'SYSTEM_ALERT_WINDOW'),
    @('com.huawei.vrvirtualscreen', 'SYSTEM_ALERT_WINDOW'),
    @('com.huawei.vrservice', 'SYSTEM_ALERT_WINDOW'),
    @('com.huawei.hvrsdkserverapp', 'SYSTEM_ALERT_WINDOW')
)
foreach ($entry in $appOps) {
    Invoke-Adb -Arguments @('shell', 'appops', 'set', $entry[0], $entry[1], 'allow') | Out-Null
    $state = (Invoke-Adb -Arguments @('shell', 'appops', 'get', $entry[0], $entry[1])) -join ' '
    Write-Output ("  {0,-28} {1,-22} {2}" -f $entry[0], $entry[1], $state)
}

$grants = @(
    @('com.huawei.vrlauncherx', 'android.permission.WRITE_SECURE_SETTINGS'),
    @('com.huawei.vrlauncherx', 'android.permission.READ_PHONE_STATE'),
    # 原版靠 system UID 读设备序列号；普通应用要显式授权（真机日志
    #   reportAccessDeniedToReadIdentifiers: com.huawei.appmarket.vr:getSerial）。
    @('com.huawei.appmarket.vr', 'android.permission.READ_PHONE_STATE'),
    # 原版跑在 system UID 下，定位权限是隐式持有的；通用安卓要显式授予，
    # 否则 i2/g1.r(Context) 读不到 WiFi SSID（Android 10+ 需要定位权限），
    # 空间里的 WifiControllerQ.UpdateWifiName 会拿到空串并崩在 Substring 上。
    @('com.huawei.vrlauncherx', 'android.permission.ACCESS_FINE_LOCATION'),
    @('com.huawei.vrlauncherx', 'android.permission.ACCESS_COARSE_LOCATION'),
    # vrservice 用 WindowManagerEx 在进 VR 时关动画、退出时恢复（写 Settings.Global）
    @('com.huawei.vrservice', 'android.permission.WRITE_SECURE_SETTINGS')
)
foreach ($entry in $grants) {
    Invoke-Adb -Arguments @('shell', 'pm', 'grant', $entry[0], $entry[1]) | Out-Null
    Write-Output ("  {0,-28} {1}" -f $entry[0], $entry[1])
}

# 用量统计（UsageStatsManager.queryUsageStats）不是普通 runtime 权限，声明之后
# 还要 appops 放行 GET_USAGE_STATS。原版跑在 system UID 下是隐式持有的；
# 缺了它桌面 i2/t0.getUsageStatsList 会拿到空列表并打
#   W/HwVrLauncherX_AppManager: getUsageStatsList abnormal, queryUsageStats size is 0
Invoke-Adb -Arguments @('shell', 'appops', 'set', 'com.huawei.vrlauncherx',
        'GET_USAGE_STATS', 'allow') | Out-Null
$usageStats = (Invoke-Adb -Arguments @('shell', 'appops', 'get', 'com.huawei.vrlauncherx',
        'GET_USAGE_STATS')) -join ' '
Write-Output ("  {0,-28} {1,-22} {2}" -f 'com.huawei.vrlauncherx', 'GET_USAGE_STATS', $usageStats)

# 待机时不能把「眼镜监督 / VR 系统服务 / 空间宿主 / 手柄服务」压掉，
# 否则插入眼镜没人响应：vrservice 是 vr_system 的注册方与准备流程的发起方。
foreach ($package in @('com.huawei.hvrsdkserverapp', 'com.huawei.vrservice', 'com.huawei.vrlauncherx', 'com.huawei.vrhandle')) {
    Invoke-Adb -Arguments @('shell', 'cmd', 'deviceidle', 'whitelist', "+$package") | Out-Null
}
Write-Output "  deviceidle whitelist : hvrsdkserverapp / vrservice / vrlauncherx / vrhandle"

# 按 tag 提日志级别：这两条不是缺陷，是 SDK 对被正确回答的问题每帧打 ERROR。
#   E/HvrFramework  : native 问 VrFramework.isHW6DoFHeaderAvailable()，本机是
#                     CV10 眼镜 + CF20 手柄（3DoF），如实返回 false，native 按
#                     ERROR 打出来（实测 45 秒 2700+ 条）。
#   E/VrHelmetExt   : 同一件事在 helmet 扩展侧的记录（mVRDeviceExt is null）。
# liblog 支持 log.tag.<TAG> 设置最低级别，提到 ASSERT 即不再打印；
# 这只是关闭日志输出，SDK 的返回值与全部行为不变，可以随时删掉这两行或
# `setprop log.tag.HvrFramework VERBOSE` 恢复查看。
foreach ($tag in @('HvrFramework', 'VrHelmetExt')) {
    Invoke-Adb -Arguments @('shell', 'su', '-c', "setprop log.tag.$tag ASSERT") | Out-Null
    $level = (Invoke-Adb -Arguments @('shell', 'getprop', "log.tag.$tag")) -join ' '
    Write-Output ("  log.tag.{0,-16} {1}" -f $tag, $level.Trim())
}

Write-Output "== 校验 =="
$alertWindow = (Invoke-Adb -Arguments @('shell', 'appops', 'get', 'com.huawei.vrhandle',
        'SYSTEM_ALERT_WINDOW')) -join ' '
if ($alertWindow -notmatch 'allow') {
    Write-Warning "com.huawei.vrhandle 的 SYSTEM_ALERT_WINDOW 未生效，手柄会在后台启动前台服务时崩溃"
}
$watcher = (Invoke-Adb -Arguments @('shell', 'ps', '-A')) -join "`n"
foreach ($process in @('com.huawei.hvrsdkserverapp', 'com.huawei.vrhandle:VRHandleService')) {
    $state = if ($watcher -match [regex]::Escape($process)) { 'running' } else { 'not running' }
    Write-Output ("  {0,-40} {1}" -f $process, $state)
}
