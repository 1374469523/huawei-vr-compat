<#
把「原包 + 原厂固件件」里定义的类做成索引，供审计脚本比对。

    & .\tools\official-index.ps1
    -> build/official-index/<来源名>.txt        每个来源一份（类描述符，已排序去重）
    -> build/official-index/_summary.txt        汇总

来源分两类：
  原包/*.apk        七个原始 APK（应用自己带的类）
  原厂件/*.jar      从华为官方固件镜像里取出的框架 jar（见 原厂件/README.md）

索引只记录「类定义」，不记录引用：用的是 dexlib2 的 classSection，不是字符串扫描。
#>
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$workspace = Split-Path $repo -Parent
. (Join-Path $PSScriptRoot 'sdk-path.ps1')
$sdk = Resolve-HvrAndroidSdk -RepoRoot $repo
$jdk = (Get-ChildItem (Join-Path $sdk 'jdk17tmp') -Directory | Select-Object -First 1).FullName
$env:JAVA_HOME = $jdk
$java = Join-Path $jdk 'bin/java.exe'
$javac = Join-Path $jdk 'bin/javac.exe'
$apktool = Join-Path $repo 'tools/apktool_2.10.0.jar'
$toolSrc = Join-Path $repo 'tools/dexdump/DexDump.java'
$toolOut = Join-Path $repo 'build/dexdump'
$index = Join-Path $repo 'build/official-index'
New-Item -ItemType Directory -Force -Path $toolOut, $index | Out-Null

& $javac -nowarn -encoding UTF-8 -cp $apktool -d $toolOut $toolSrc
if ($LASTEXITCODE -ne 0) { throw 'DexDump 编译失败' }
$cp = "$apktool;$toolOut"

function New-Index([string]$name, [string]$file) {
    $out = Join-Path $index "$name.txt"
    $lines = & $java -cp $cp DexDump --list $file 29 2>$null
    if ($LASTEXITCODE -ne 0) { throw "索引失败：$file" }
    $lines | Sort-Object -Unique | Set-Content -Encoding UTF8 $out
    $count = (Get-Content -LiteralPath $out).Count
    Write-Host ("{0,-34} {1,6} 类" -f $name, $count)
    return $count
}

$rows = @()
foreach ($apk in Get-ChildItem (Join-Path $repo '原包') -Filter *.apk) {
    $c = New-Index $apk.BaseName $apk.FullName
    $rows += "{0}`t{1}`t原包" -f $apk.BaseName, $c
}
foreach ($jar in Get-ChildItem (Join-Path $repo '原厂件') -Filter *.jar -ErrorAction SilentlyContinue) {
    $c = New-Index $jar.BaseName $jar.FullName
    $rows += "{0}`t{1}`t原厂件" -f $jar.BaseName, $c
}
$rows | Set-Content -Encoding UTF8 (Join-Path $index '_summary.txt')
Write-Host "索引已写入 $index"
