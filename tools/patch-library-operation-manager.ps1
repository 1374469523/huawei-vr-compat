<#
编译并运行 tools/PatchLibraryOperationManager.cs，给原版 Unity 程序集打
「LibraryCanvasManager.InitData 序列化字段兜底取单例」的小补丁。
背景见那个 .cs 顶部的注释。
#>
param(
    [string]$Assembly = "$PSScriptRoot/../decode/com.huawei.vrlauncherx/assets/bin/Data/Managed/Assembly-CSharp.dll"
)
$ErrorActionPreference = 'Stop'

$cecil = Join-Path $PSScriptRoot 'cecil/Mono.Cecil.dll'
$netstandard = Join-Path $PSScriptRoot 'cecil/netstandard.dll'
$source = Join-Path $PSScriptRoot 'PatchLibraryOperationManager.cs'
foreach ($file in @($cecil, $netstandard, $source)) {
    if (!(Test-Path -LiteralPath $file)) { throw "missing $file" }
}

$csc = @(
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (!$csc) { throw 'csc.exe not found (.NET Framework 4.x required)' }

$build = Join-Path ([System.IO.Path]::GetTempPath()) 'hvr-library-patch'
New-Item -ItemType Directory -Force -Path $build | Out-Null
$exe = Join-Path $build 'PatchLibraryOperationManager.exe'

& $csc /nologo /target:exe "/out:$exe" "/r:$cecil" "/r:$netstandard" $source
if ($LASTEXITCODE -ne 0) { throw "compile failed (exit $LASTEXITCODE)" }

Copy-Item -LiteralPath $cecil -Destination $build -Force
Copy-Item -LiteralPath $netstandard -Destination $build -Force

$target = (Resolve-Path -LiteralPath $Assembly).Path
& $exe $target
if ($LASTEXITCODE -ne 0) { throw "patch failed (exit $LASTEXITCODE)" }
