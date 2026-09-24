# 构建 invoice_shext.dll + invoice-ext-host.exe, 并把产物放进 package/
# (install.ps1 在产物缺失时会自动调用本脚本)
$ErrorActionPreference = 'Stop'

$AppDir = Split-Path -Parent $PSScriptRoot   # apps/explorer-extension
$Target = Join-Path $AppDir 'target\release'

cargo build --release --manifest-path (Join-Path $AppDir 'Cargo.toml')
if ($LASTEXITCODE -ne 0) { throw "cargo build 失败 (exit $LASTEXITCODE)" }

foreach ($name in @('invoice_shext.dll', 'invoice-ext-host.exe')) {
    Copy-Item (Join-Path $Target $name) (Join-Path $AppDir 'package') -Force
    Write-Host "[OK] package/$name"
}
