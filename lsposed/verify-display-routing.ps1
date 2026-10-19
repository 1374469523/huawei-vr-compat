<#
一键验证「VR 活动落到虚拟屏、画面走眼镜面板」这条链。

前提：LSPosed 里已经启用 com.hvr.displayrouting 并勾好作用域（系统框架 + 七个包）、
按提示重启过。脚本自己会先确认模块真的生效，没生效就停下来告诉你，不会把主线改坏。

做四件事：
  1. 确认 LSPosed 模块已生效（logcat 里能看到 hook 日志）；
  2. 打上虚拟屏路由补丁并构建/安装桌面；
  3. 冷启动一次「华为 VR」，跑主线；
  4. 打印验收判据：路由日志、Permission Denial 计数、虚拟屏归属、面板窗口所在 display。
#>
param(
    # 留空则自动解析 SDK（tools/sdk-path.ps1）
    [string]$Adb = '',
    # 设备地址（adb devices 里看到的那个），按你的环境改
    [string]$Serial = '127.0.0.1:5555',
    [string]$Revision = 'route1'
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
if (!$Adb) {
    . (Join-Path $repo 'tools/sdk-path.ps1')
    $Adb = Resolve-HvrAdb -RepoRoot $repo
}
$serial = $Serial

function Invoke-Adb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $Adb -s $serial @Arguments
}

Write-Output '== 1. 确认 LSPosed 模块已生效 =='
$hookCount = (Invoke-Adb shell "logcat -d | grep -c 'HvrDisplayRouting'") -join ''
if ($hookCount.Trim() -eq '0') {
    Write-Warning @'
LSPosed 模块还没生效（logcat 里没有 HvrDisplayRouting 的 hook 日志）。
请先：安装 lsposed/out/com.hvr.displayrouting-*.apk → 在 LSPosed 里启用 →
作用域勾选「系统框架(android)」和七个包 → 按提示重启。然后再跑这个脚本。
（现在退出，不动主线。）
'@
    exit 1
}
Write-Output "  hook 日志条数：$hookCount"

Write-Output '== 2. 打路由补丁并重装桌面 =='
& python (Join-Path $repo 'patches/patch_vr_display_launch.py') $repo
if ($LASTEXITCODE -ne 0) { throw '路由补丁失败' }
& (Join-Path $repo 'build/build-module.ps1') -Package com.huawei.vrlauncherx -Revision $Revision |
    Select-Object -Last 3
if ($LASTEXITCODE -ne 0) { throw '桌面构建失败' }
Invoke-Adb install -r -d (Join-Path $repo "build/out/com.huawei.vrlauncherx-$Revision.apk") |
    Select-Object -Last 1

Write-Output '== 3. 冷启动主线 =='
Invoke-Adb shell "su -c 'am force-stop com.huawei.hvrsdkserverapp; am force-stop com.huawei.vrlauncherx'" | Out-Null
Invoke-Adb shell 'am force-stop com.huawei.appmarket.vr' | Out-Null
Invoke-Adb shell 'logcat -c' | Out-Null
Invoke-Adb shell 'am start -n com.huawei.appmarket.vr/com.huawei.hwmarket.vr.MainActivity' |
    Select-Object -Last 1
Start-Sleep -Seconds 30

Write-Output '== 4. 验收判据 =='
$denial = (Invoke-Adb shell "logcat -d | grep -cE 'Permission Denial.*launchDisplayId'") -join ''
$routed = (Invoke-Adb shell "logcat -d | grep -E 'HvrDisplayRouter|HvrVrDisplay created' | tail -4") -join "`n"
$owner = (Invoke-Adb shell "dumpsys display | grep -E 'mPrimaryDisplayDevice=HUAWEI VR Display' | head -2") -join "`n"
$panel = (Invoke-Adb shell "dumpsys window windows | grep -B3 'ty=PRESENTATION' | grep -E 'Window #|mDisplayId' | head -6") -join "`n"

Write-Output "  Permission Denial(launchDisplayId) = $($denial.Trim())   （期望 0）"
Write-Output "  路由/建屏日志：`n$routed"
Write-Output "  虚拟屏归属：`n$owner"
Write-Output "  面板窗口：`n$panel"
Write-Output '  人工判据：眼镜里应显示 VR 内容（不是手机镜像），投屏不再报 app start on default display error'
