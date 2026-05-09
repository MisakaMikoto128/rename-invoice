# 开发者用: 下载 pdfium.dll (Windows x64) 到当前 rust/ 目录.
# 末端用户不需要跑这个脚本 —— release zip 已经把 pdfium.dll 打进去.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$tmp  = Join-Path $env:TEMP 'pdfium_fetch.tgz'
$url  = 'https://github.com/bblanchon/pdfium-binaries/releases/latest/download/pdfium-win-x64.tgz'

Write-Host "Downloading $url ..."
Invoke-WebRequest -Uri $url -OutFile $tmp

$work = Join-Path $env:TEMP ('pdfium_fetch_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
tar -xzf $tmp -C $work

$dll = Join-Path $work 'bin\pdfium.dll'
if (-not (Test-Path $dll)) {
    throw "解压后没有找到 pdfium.dll"
}
Copy-Item $dll (Join-Path $root 'pdfium.dll') -Force
$lic = Join-Path $work 'LICENSE'
if (Test-Path $lic) {
    Copy-Item $lic (Join-Path $root 'PDFIUM_LICENSE') -Force
}

Remove-Item $tmp -ErrorAction SilentlyContinue
Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue

Write-Host '[OK] pdfium.dll 已就绪: ' (Join-Path $root 'pdfium.dll')
