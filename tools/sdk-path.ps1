<#
解析 Android SDK 的位置 —— 脚本里不再写死任何绝对路径。

查找顺序（先命中先用）：
  1. 环境变量 HVR_ANDROID_SDK
  2. <仓库>/工具链/android-sdk          （工程自包含的那份）
  3. <仓库>/../android-sdk             （工作区根目录的那份，通常是 junction）
  4. <仓库>/android-sdk

用法：
    . (Join-Path $repo 'tools/sdk-path.ps1')
    $sdk = Resolve-HvrAndroidSdk -RepoRoot $repo
找不到会抛错并列出查过的位置，不会静默用一个不存在的路径。
#>
function Resolve-HvrAndroidSdk {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $repo = (Resolve-Path -LiteralPath $RepoRoot).Path
    $workspace = Split-Path $repo -Parent
    $candidates = @()
    if ($env:HVR_ANDROID_SDK) { $candidates += $env:HVR_ANDROID_SDK }
    $candidates += (Join-Path $repo '工具链/android-sdk')
    $candidates += (Join-Path $workspace 'android-sdk')
    $candidates += (Join-Path $repo 'android-sdk')

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate 'build-tools'))) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw ("找不到 Android SDK，查过这些位置：`n  " + ($candidates -join "`n  ") +
        "`n可以设环境变量 HVR_ANDROID_SDK 指到 SDK 根目录。")
}

function Resolve-HvrAdb {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)
    $sdk = Resolve-HvrAndroidSdk -RepoRoot $RepoRoot
    $adb = Join-Path $sdk 'platform-tools/adb.exe'
    if (!(Test-Path -LiteralPath $adb)) {
        throw "SDK 里没有 platform-tools/adb.exe：$sdk"
    }
    return $adb
}
