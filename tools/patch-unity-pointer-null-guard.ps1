<#
用 Mono.Cecil 给原版 Unity 程序集打「空指针判断」补丁。

背景、原始 C# 意图与影响写在 tools/PatchUnityPointerNullGuard.cs 顶部。
这个脚本只负责：编译那个 C# 工具 -> 对指定 Assembly-CSharp.dll 执行 -> 报结果。
原始 IL 形态不匹配时工具会报错退出（不会写文件）；重复运行时第二次会明确
提示 already patched。
#>
param(
    [string]$Assembly = "$PSScriptRoot/../decode/com.huawei.vrlauncherx/assets/bin/Data/Managed/Assembly-CSharp.dll"
)
$ErrorActionPreference = 'Stop'

$cecil = Join-Path $PSScriptRoot 'cecil/Mono.Cecil.dll'
if (!(Test-Path -LiteralPath $cecil)) { throw "missing $cecil" }
$netstandard = Join-Path $PSScriptRoot 'cecil/netstandard.dll'
if (!(Test-Path -LiteralPath $netstandard)) { throw "missing $netstandard" }
$source = Join-Path $PSScriptRoot 'PatchUnityPointerNullGuard.cs'
if (!(Test-Path -LiteralPath $source)) { throw "missing $source" }

$csc = @(
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (!$csc) { throw 'csc.exe not found (.NET Framework 4.x required)' }

$build = Join-Path ([System.IO.Path]::GetTempPath()) 'hvr-pointer-patch'
New-Item -ItemType Directory -Force -Path $build | Out-Null
$exe = Join-Path $build 'PatchUnityPointerNullGuard.exe'

& $csc /nologo /target:exe "/out:$exe" "/r:$cecil" "/r:$netstandard" $source
if ($LASTEXITCODE -ne 0) { throw "compile failed (exit $LASTEXITCODE)" }

# 运行时 exe 需要和 Cecil 同目录。
Copy-Item -LiteralPath $cecil -Destination $build -Force
Copy-Item -LiteralPath $netstandard -Destination $build -Force

$target = (Resolve-Path -LiteralPath $Assembly).Path
& $exe $target
if ($LASTEXITCODE -ne 0) { throw "patch failed (exit $LASTEXITCODE)" }
