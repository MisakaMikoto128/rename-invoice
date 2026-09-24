# 卸载右键菜单
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$KeyName = 'AddInvoicePrice'
$Paths = @(
    "HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\$KeyName",
    "HKCU:\Software\Classes\Directory\shell\$KeyName",
    "HKCU:\Software\Classes\Directory\Background\shell\$KeyName"
)

foreach ($p in $Paths) {
    if (Test-Path $p) {
        Remove-Item -Path $p -Recurse -Force
        Write-Host "[已删除] $p" -ForegroundColor Green
    } else {
        Write-Host "[跳过] $p (不存在)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "右键菜单已卸载完成." -ForegroundColor Cyan
pause
