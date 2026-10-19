<#
Builds one compatibility module from its decoded tree.

    decode/<包名>/                      原始反编译树（已由补丁脚本改成目标状态）
      -> javac 共享兼容层（shared/java，编译期用 shared/stubs 提供隐藏 API 存根）
      -> d8 生成一个额外 classesN.dex
      -> apktool b 重建 APK
      -> 把 classesN.dex 写进 APK
      -> zipalign + apksigner（六包同一签名）

存根（shared/stubs）只参与编译，不会进包：平台在运行时提供真正的
android.os.UEventObserver 与 android.vrsystem.* 接口。
#>
param(
    [Parameter(Mandatory = $true)][string]$Package,
    [string]$Revision = 'r1',
    # 原版调试开关：不插眼镜也能在手机上看 VR 画面
    # （<meta-data name="com.huawei.android.vr.sensor.mode" value="mobile"/>）。
    # 华为官方指南写明「正式发布的应用程序中必须去掉该标签」，
    # 所以它只能由这个开关在**构建副本**上打开，decode 树永远不带；
    # 下面的第 7 步还会反过来断言正式构建里绝对没有它。
    [switch]$DebugMobileMode
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$workspace = Split-Path $repo -Parent
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'tools/sdk-path.ps1')
$sdk = Resolve-HvrAndroidSdk -RepoRoot $repo
$jdk = (Get-ChildItem (Join-Path $sdk 'jdk17tmp') -Directory | Select-Object -First 1).FullName
# d8.bat / apksigner.bat 都通过 JAVA_HOME 找 java，必须在第一次调用前设好。
$env:JAVA_HOME = $jdk
$java = Join-Path $jdk 'bin/java.exe'
$javac = Join-Path $jdk 'bin/javac.exe'
$bt = Join-Path $sdk 'build-tools/35.0.0'
$androidJar = Join-Path $sdk 'platforms/android-35/android.jar'
$apktool = Join-Path $repo 'tools/apktool_2.10.0.jar'
$framework = Join-Path $repo 'tools/framework'
$aapt = Join-Path $bt 'aapt2.exe'
$zipalign = Join-Path $bt 'zipalign.exe'
$apksigner = Join-Path $bt 'apksigner.bat'
$keystore = Join-Path $repo 'signing/hvr-compat-debug.jks'
$decode = Join-Path $repo "decode/$Package"
if (!(Test-Path -LiteralPath $decode)) { throw "缺少解码树：$decode" }

$stamp = [guid]::NewGuid().ToString('N').Substring(0, 8)
# aapt2 是原生程序，打不开中文路径，所以工作区必须放在 ASCII 路径下；仓库本身
# 仍然在中文路径，只有「复制过去的构建树」参与 aapt2/apktool。
#
# 2026-09-16：原来放在 %LOCALAPPDATA%，每构建一次就留一份整棵解码树的副本
# （主应用一棵几百 MB），攒到 319 份把系统盘占满、构建直接报「磁盘空间不足」。
# 改成放工作区所在盘的根目录（D:\ 这种纯 ASCII 路径），并且每次构建前只保留
# 最近 3 份，避免再堆垃圾。
$stageRoot = Join-Path ([System.IO.Path]::GetPathRoot($workspace)) '.hvrbuild'
if (Test-Path -LiteralPath $stageRoot) {
    Get-ChildItem -LiteralPath $stageRoot -Directory |
        Sort-Object LastWriteTime -Descending | Select-Object -Skip 3 |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
}
$buildRoot = Join-Path $repo 'build'
$stage = Join-Path $stageRoot "$Package-$Revision-$stamp"
$stubClasses = Join-Path $stage 'stub-classes'
$compatClasses = Join-Path $stage 'compat-classes'
$dexDir = Join-Path $stage 'dex'
$unsigned = Join-Path $stage 'unsigned.apk'
$aligned = Join-Path $stage 'aligned.apk'
$outDir = Join-Path $buildRoot 'out'
New-Item -ItemType Directory -Force -Path $stage, $stubClasses, $compatClasses, $dexDir, $outDir | Out-Null

function Invoke-Step([string]$name, [scriptblock]$body) {
    & $body
    if ($LASTEXITCODE -ne 0) { throw "$name 失败（exit $LASTEXITCODE）" }
}

# 1) 编译期存根（只用于让 javac 看到隐藏 API）
$stubSources = @(Get-ChildItem (Join-Path $repo 'shared/stubs') -Recurse -Filter *.java |
    ForEach-Object { $_.FullName })
Invoke-Step '编译存根' {
    & $javac -nowarn -encoding UTF-8 -source 8 -target 8 -classpath $androidJar -d $stubClasses $stubSources
}

# 2) 共享兼容层
$compatSources = @(Get-ChildItem (Join-Path $repo 'shared/java') -Recurse -Filter *.java |
    ForEach-Object { $_.FullName })
# Runtime 额外带一套“系统侧”实现：EMUI 原来由框架承担的眼镜监督与 VR 环境拉起，
# 只属于 com.huawei.hvrsdkserverapp，别的模块不打包。
$actorDir = Join-Path $repo 'shared/runtime-actor/java'
if ($Package -eq 'com.huawei.hvrsdkserverapp' -and (Test-Path -LiteralPath $actorDir)) {
    $compatSources += @(Get-ChildItem $actorDir -Recurse -Filter *.java |
        ForEach-Object { $_.FullName })
}
Invoke-Step '编译兼容层' {
    & $javac -nowarn -encoding UTF-8 -source 8 -target 8 -classpath "$androidJar;$stubClasses" -d $compatClasses $compatSources
}

# 3) d8 生成额外 dex
# 类文件列表走 d8 的 @argfile：Runtime 带系统侧实现后逐个传参会超过 Windows
# 命令行长度上限，而 d8 本身不接受裸目录。
$classFiles = @(Get-ChildItem $compatClasses -Recurse -Filter *.class |
    ForEach-Object { $_.FullName })
$d8Args = Join-Path $stage 'd8-args.txt'
@("--lib", $androidJar, "--min-api", "24", "--output", $dexDir) + $classFiles |
    # UTF-8 无 BOM：仓库路径含中文，ASCII 会破坏路径（d8 按 UTF-8 读 argfile）。
    Set-Content -LiteralPath $d8Args -Encoding utf8
Invoke-Step 'd8 生成 dex' {
    & (Join-Path $bt 'd8.bat') "@$d8Args"
}
$compatDex = Join-Path $dexDir 'classes.dex'
if (!(Test-Path -LiteralPath $compatDex)) { throw 'd8 没有产出 classes.dex' }

# 4) apktool 重建 APK
$tree = Join-Path $stage 'tree'
Copy-Item -LiteralPath $decode -Destination $tree -Recurse
if ($DebugMobileMode) {
    Write-Warning '调试构建：加上 com.huawei.android.vr.sensor.mode=mobile（不插眼镜也能看手机画面）。正式发布必须去掉。'
    & python (Join-Path $repo 'patches/patch_debug_mobile_mode.py') enable `
        (Join-Path $tree 'AndroidManifest.xml')
    if ($LASTEXITCODE -ne 0) { throw '注入调试开关失败' }
}
Invoke-Step 'apktool 构建' {
    & $java -jar $apktool b -f -p $framework --aapt $aapt -o $unsigned $tree
}

# 5) 把兼容层 dex 写进 APK，占用下一个 classesN.dex 序号
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::Open($unsigned, 'Update')
try {
    $used = @{}
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName -match '^classes(\d*)\.dex$') { $used[$entry.FullName] = $true }
    }
    $index = 2
    while ($used.ContainsKey("classes$index.dex")) { $index++ }
    $target = "classes$index.dex"
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, $compatDex, $target, [IO.Compression.CompressionLevel]::Optimal) | Out-Null
    Write-Output "兼容层写入 $target"
} finally { $zip.Dispose() }

# 6) 对齐 + 签名
# 5.5) zip 结构按原包对齐重写。
# apktool 重建出来的条目同时带 data descriptor 与非零本地头尺寸，原版用
# ZipInputStream 读自己 APK 的那几处（WhiteListUtil / LibUpdateClient /
# UncompressTask）会抛 invalid entry size。这一步同时把同名条目的压缩方式
# 按原包对齐，并断言「无 data descriptor / testzip 通过 / resources.arsc 未压缩」。
$rezip = Join-Path $stage 'rezip.apk'
$originalApk = Join-Path $repo "原包/$Package.apk"
Invoke-Step 'zip 结构对齐' {
    & python (Join-Path $repo 'tools/apk-rezip.py') $unsigned $originalApk $rezip
}

Invoke-Step '对齐' { & $zipalign -f -p 4 $rezip $aligned }
$env:JAVA_HOME = $jdk
$out = Join-Path $outDir "$Package-$Revision.apk"
Invoke-Step '签名' {
    & $apksigner sign --ks $keystore --ks-key-alias hvrcompat `
        --ks-pass pass:android --key-pass pass:android --out $out $aligned
}
Invoke-Step '验签' { & $apksigner verify $out }

# 7) 静态核对：包名与权限
$packageName = (& $aapt dump packagename $out | Select-Object -First 1).Trim()
if ($packageName -ne $Package) { throw "包名不符：期望 $Package，实际 $packageName" }
$permissions = (& $aapt dump permissions $out) -join "`n"
# 2026-09-16 用户口径纠正：不做「完全离线」，只拦发往华为服务器的请求。
# 通用安卓联网权限（INTERNET / ACCESS_NETWORK_STATE / ACCESS_WIFI_STATE /
# CHANGE_WIFI_STATE）按原包保留，这里不再断言它们不存在；
# 华为专有权限（hwid / ACCESS_UDID / MDM 等）的清理仍在各自的 manifest 补丁里。

# 调试开关只能出现在 -DebugMobileMode 的构建里
$manifestXml = (& $aapt dump xmltree --file AndroidManifest.xml $out) -join "`n"
$hasDebugSwitch = $manifestXml -match 'com\.huawei\.android\.vr\.sensor\.mode'
if ($hasDebugSwitch -and !$DebugMobileMode) {
    throw '正式构建里出现了调试开关 com.huawei.android.vr.sensor.mode（不插眼镜也能跑的那个）'
}
if ($DebugMobileMode) {
    if (!$hasDebugSwitch) { throw '指定了 -DebugMobileMode 但包内没有这条 meta-data' }
    Write-Output 'DEBUG_MOBILE_MODE=on'
} else {
    Write-Output 'DEBUG_MOBILE_MODE=off'
}

$sha256 = (Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash
Write-Output "SHA256=$sha256"
Write-Output "PACKAGE=$packageName"
Write-Output "OUT=$out"
