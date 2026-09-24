<#
.SYNOPSIS
    卸载 rename-invoice 资源管理器扩展。

.PARAMETER KeepConfig
    保留 HKCU\Software\rename-invoice\ExplorerExt 的 CLI 配置 (重装时免配置)。

.PARAMETER RemoveCert
    同时把 CN=rename-invoice 自签证书从 LocalMachine\TrustedPeople 删掉 (弹一次 UAC)。

.EXAMPLE
    .\uninstall.ps1
#>
[CmdletBinding()]
Param(
    [switch]$KeepConfig,
    [switch]$RemoveCert
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$pkg = Get-AppxPackage -Name 'rename-invoice-ext' -ErrorAction SilentlyContinue
if ($pkg) {
    Remove-AppxPackage -Package $pkg.PackageFullName
    Write-Host "[OK] 已移除稀疏包: $($pkg.PackageFullName)"
} else {
    Write-Host '[..] 未发现已注册的稀疏包'
}

if (-not $KeepConfig) {
    Remove-Item 'HKCU:\Software\rename-invoice\ExplorerExt' -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host '[OK] 已清除 CLI 配置 (注册表)'
}

if ($RemoveCert) {
    $certs = Get-ChildItem Cert:\LocalMachine\TrustedPeople -ErrorAction SilentlyContinue |
        Where-Object { $_.Subject -eq 'CN=rename-invoice' }
    if ($certs) {
        $list = ($certs.Thumbprint | ForEach-Object { "'$_'" }) -join ','
        $ps = "Get-ChildItem Cert:\LocalMachine\TrustedPeople | " +
              "Where-Object { @($list) -contains `$_.Thumbprint } | Remove-Item"
        $proc = Start-Process powershell -Verb RunAs -Wait -PassThru `
            -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $ps
        if ($proc.ExitCode -eq 0) { Write-Host '[OK] 证书已从 TrustedPeople 移除' }
    } else {
        Write-Host '[..] TrustedPeople 里没有相关证书'
    }
}

Write-Host '完成。(菜单立即消失; 若仍显示, 重启 explorer.exe)'
