<#
构建 LSPosed 辅助模块（放行「把 VR 活动启动到自建虚拟屏」这一个动作）。

产物：lsposed/out/com.hvr.displayrouting.apk —— 手动装进手机，在 LSPosed 里启用并
勾选作用域（android + 华为 VR 七包）后重启相关进程即可。

工具链与主工程一致（android-sdk 里的 build-tools 35 + jdk17 + 仓库自带 keystore）。
#>
param([string]$Revision = 'r1')
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $repo 'tools/sdk-path.ps1')
$sdk = Resolve-HvrAndroidSdk -RepoRoot $repo
$jdk = (Get-ChildItem (Join-Path $sdk 'jdk17tmp') -Directory | Select-Object -First 1).FullName
$javac = Join-Path $jdk 'bin/javac.exe'
$bt = Join-Path $sdk 'build-tools/35.0.0'
$aapt2 = Join-Path $bt 'aapt2.exe'
$androidJar = Join-Path $sdk 'platforms/android-35/android.jar'
$zipalign = Join-Path $bt 'zipalign.exe'
$apksigner = Join-Path $bt 'apksigner.bat'
$keystore = Join-Path $repo 'signing/hvr-compat-debug.jks'
$module = Join-Path $PSScriptRoot 'hvr-display-routing'
$stageRoot = Join-Path ([System.IO.Path]::GetPathRoot($repo)) '.hvrbuild'
$stage = Join-Path $stageRoot "lsposed-$Revision"
$outDir = Join-Path $PSScriptRoot 'out'

$env:JAVA_HOME = $jdk
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'classes'), $outDir | Out-Null

Write-Output '== 编译模块 + 存根 =='
$sources = @(
    Get-ChildItem (Join-Path $module 'java') -Recurse -Filter *.java | ForEach-Object FullName
    Get-ChildItem (Join-Path $module 'stub') -Recurse -Filter *.java | ForEach-Object FullName
)
& $javac -nowarn -encoding UTF-8 -source 8 -target 8 -classpath $androidJar `
    -d (Join-Path $stage 'classes') $sources
if ($LASTEXITCODE -ne 0) { throw 'javac 失败' }

Write-Output '== d8 生成 classes.dex =='
$classFiles = @(Get-ChildItem (Join-Path $stage 'classes') -Recurse -Filter *.class |
    ForEach-Object FullName)
$argsFile = Join-Path $stage 'd8-args.txt'
@('--lib', $androidJar, '--min-api', '29', '--output', $stage) + $classFiles |
    Set-Content -LiteralPath $argsFile -Encoding utf8
& (Join-Path $bt 'd8.bat') "@$argsFile"
if ($LASTEXITCODE -ne 0) { throw 'd8 失败' }

Write-Output '== aapt2 链接清单 =='
$resZip = Join-Path $stage 'res.zip'
$base = Join-Path $stage 'base.apk'
$resDir = Join-Path $module 'res'
$linkArgs = @('link', '-o', $base, '-I', $androidJar,
    '--manifest', (Join-Path $module 'AndroidManifest.xml'),
    '--min-sdk-version', '29', '--target-sdk-version', '34')
$resFiles = @(Get-ChildItem -LiteralPath $resDir -Recurse -File -ErrorAction SilentlyContinue)
if ($resFiles.Count -gt 0) {
    & $aapt2 compile --dir $resDir -o $resZip
    if ($LASTEXITCODE -ne 0) { throw 'aapt2 compile 失败' }
    $linkArgs += @('-R', $resZip)
}
& $aapt2 @linkArgs
if ($LASTEXITCODE -ne 0) { throw 'aapt2 link 失败' }

Write-Output '== 写入 classes.dex 与 xposed_init =='
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::Open($base, 'Update')
try {
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, (Join-Path $stage 'classes.dex'), 'classes.dex',
        [IO.Compression.CompressionLevel]::Optimal) | Out-Null
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, (Join-Path $module 'assets/xposed_init'), 'assets/xposed_init',
        [IO.Compression.CompressionLevel]::Optimal) | Out-Null
} finally {
    $zip.Dispose()
}

Write-Output '== 对齐 + 签名 =='
$aligned = Join-Path $stage 'aligned.apk'
& $zipalign -f -p 4 $base $aligned
if ($LASTEXITCODE -ne 0) { throw 'zipalign 失败' }
$out = Join-Path $outDir "com.hvr.displayrouting-$Revision.apk"
& $apksigner sign --ks $keystore --ks-key-alias hvrcompat `
    --ks-pass pass:android --key-pass pass:android --out $out $aligned
if ($LASTEXITCODE -ne 0) { throw '签名失败' }
& $apksigner verify $out
if ($LASTEXITCODE -ne 0) { throw '验签失败' }

Write-Output ("OUT={0}" -f $out)
Write-Output ("SHA256={0}" -f (Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash)
