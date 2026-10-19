<#
Builds every module in the fixed order: Runtime first (the other modules talk to
it), then the desktop, video, cast, handle and finally the main app.
#>
param([string]$Revision = 'r1')
$ErrorActionPreference = 'Stop'
$modules = @(
    'com.huawei.hvrsdkserverapp',
    # 第七个模块：EMUI 的 VR 系统服务本体（从 HMA-AL00 EMUI 11 整包固件提取）。
    # 它注册 vr_system、拉起准备流程，是主线缺的那一环，排在被它驱动的模块之前。
    'com.huawei.vrservice',
    'com.huawei.vrhandle',
    'com.huawei.vrvirtualscreen',
    'com.huawei.himovie.vr',
    'com.huawei.vrlauncherx',
    'com.huawei.appmarket.vr'
)
$summary = @()
foreach ($module in $modules) {
    Write-Output "===== $module ====="
    # Out-String keeps the child script's output as plain text: a redirected run
    # used to fail with "GroupStartData ... not valid" because build-module.ps1
    # emitted Format-List objects.
    $output = (& (Join-Path $PSScriptRoot 'build-module.ps1') -Package $module `
            -Revision $Revision 2>&1 | Out-String) -split "`r?`n"
    $tail = $output | Where-Object { $_ -ne '' } | Select-Object -Last 6
    $tail | ForEach-Object { Write-Output $_ }
    if ($LASTEXITCODE -ne 0) { throw "$module 构建失败" }
    $line = $tail | Where-Object { $_ -like 'OUT=*' }
    if ($line) { $summary += $line.Substring(4) }
}
Write-Output '===== 构建产物 ====='
foreach ($apk in $summary) {
    $hash = (Get-FileHash -LiteralPath $apk -Algorithm SHA256).Hash
    Write-Output ("{0}`n  sha256 {1}" -f $apk, $hash)
}
