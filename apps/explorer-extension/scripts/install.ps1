<#
.SYNOPSIS
    安装 rename-invoice 资源管理器扩展 (Windows 11 顶层右键菜单)。

.DESCRIPTION
    流程: 构建 DLL -> 配置 CLI -> 自签证书 -> makeappx 打包 -> signtool 签名
          -> Add-AppxPackage 稀疏注册。完成后, 右键任意 PDF / 文件夹,
          Windows 11 现代菜单顶层会出现 "添加发票价格前缀" (带图标)。

    - 需要 Windows 11 (>= 21H2 / 22000)。老系统请用 invoice-cli 的经典右键菜单。
    - 第一次运行会弹一次 UAC (把自签证书导入 TrustedPeople)。
    - 移动过仓库位置后需要重新运行本脚本。

.PARAMETER CliExe
    直接指定一个可执行文件作为处理器 (高级用法), 例如未来 Rust 版 CLI。
    默认自动配置为 pythonw.exe + apps/cli/rename_invoice.py --silent。

.PARAMETER RestartExplorer
    安装后立即重启 explorer.exe (一般不需要)。

.EXAMPLE
    .\install.ps1
#>
[CmdletBinding()]
Param(
    [string]$CliExe,
    [switch]$RestartExplorer
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$AppDir  = Split-Path -Parent $PSScriptRoot                  # apps/explorer-extension
$PkgDir  = Join-Path $AppDir 'package'
$RepoDir = Split-Path -Parent (Split-Path -Parent $AppDir)   # 仓库根
$SignDir = Join-Path $AppDir '.sign'
$Dll     = Join-Path $PkgDir 'invoice_shext.dll'
$HostExe = Join-Path $PkgDir 'invoice-ext-host.exe'
$Msix    = Join-Path $PkgDir 'rename-invoice-ext.msix'
$Subject = 'CN=rename-invoice'

# --- 0. 环境检查 ---------------------------------------------------------
$osBuild = (Get-CimInstance Win32_OperatingSystem).BuildNumber
if ($osBuild -lt 22000) {
    Write-Warning "当前系统 build $osBuild 没有 Windows 11 现代右键菜单, 本扩展不适用。"
    Write-Warning "请改用 invoice-cli 的 install_context.bat (经典右键菜单)。"
    pause
    exit 1
}
if (-not (Test-Path (Join-Path $PkgDir 'AppxManifest.xml'))) {
    Write-Host "[ERROR] 缺少 package/AppxManifest.xml, 仓库不完整" -ForegroundColor Red
    pause
    exit 1
}

# --- 0.5 DLL 占用检查 ----------------------------------------------------
# 用过右键菜单后重装时, explorer.exe 可能还加载着旧 DLL, 覆盖会失败;
# 检测到占用就先重启资源管理器 (explorer.exe 会自动拉起)。
function Test-FileLocked([string]$path) {
    if (-not (Test-Path $path)) { return $false }
    try {
        $fs = [System.IO.File]::Open($path, 'Open', 'ReadWrite', 'None')
        $fs.Close()
        return $false
    } catch { return $true }
}
if (Test-FileLocked $Dll) {
    Write-Host "[..] DLL 正被 explorer.exe 占用, 重启资源管理器 ..."
    Stop-Process -Name explorer -Force
    Start-Sleep -Seconds 3
    if (Test-FileLocked $Dll) { throw "DLL 仍被占用: $Dll (请关闭所有资源管理器窗口后重试)" }
    Write-Host "[OK] explorer.exe 已重启"
}

# --- 1. 构建 DLL ---------------------------------------------------------
if (-not (Test-Path $Dll) -or -not (Test-Path $HostExe)) {
    & (Join-Path $PSScriptRoot 'build.ps1')
}
if (-not (Test-Path $Dll)) { throw "构建产物缺失: $Dll" }

# --- 2. CLI 配置 (注册表) ------------------------------------------------
$RegKey = 'HKCU:\Software\rename-invoice\ExplorerExt'
if ($CliExe) {
    if (-not (Test-Path $CliExe)) { throw "找不到 -CliExe: $CliExe" }
    New-Item -Path $RegKey -Force | Out-Null
    Set-ItemProperty -Path $RegKey -Name 'ExePath' -Value $CliExe
    Set-ItemProperty -Path $RegKey -Name 'Args'     -Value ''
    Write-Host "[OK] CLI (自定义): $CliExe"
} else {
    $CliPy = Join-Path $RepoDir 'apps\cli\rename_invoice.py'
    if (-not (Test-Path $CliPy)) {
        Write-Host "[ERROR] 找不到 invoice-cli: $CliPy" -ForegroundColor Red
        Write-Host "        资源管理器扩展依赖 invoice-cli 做重命名; 也可以用 -CliExe 指定别的处理器。"
        pause
        exit 1
    }
    $pyCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    $PythonW = $null
    if ($pyCmd) {
        $cand = Join-Path (Split-Path $pyCmd.Source) 'pythonw.exe'
        if (Test-Path $cand) { $PythonW = $cand }
    }
    if (-not $PythonW) {
        $pw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        if ($pw) { $PythonW = $pw.Source }
    }
    if (-not $PythonW) { throw "找不到 pythonw.exe, 请确认 Python 在 PATH 里 (或用 -CliExe 指定独立 exe)" }

    New-Item -Path $RegKey -Force | Out-Null
    Set-ItemProperty -Path $RegKey -Name 'ExePath' -Value $PythonW
    Set-ItemProperty -Path $RegKey -Name 'Args'     -Value ('"{0}" --silent' -f $CliPy)
    Write-Host "[OK] CLI: $PythonW"
    Write-Host "     参数: ""$CliPy"" --silent"
}

# --- 3. 注册 (按能力走两条路) --------------------------------------------
# 开发者模式开启: 直接 -Register 稀疏清单, 免签名免证书免 UAC (推荐)。
# 未开开发者模式: 自签证书 + makeappx 打包 + signtool 签名 + TrustedPeople
#                 导入 (弹一次 UAC)。
$devMode = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock' `
    -ErrorAction SilentlyContinue).AllowDevelopmentWithoutDevLicense -eq 1

if ($devMode) {
    Write-Host "[..] 检测到开发者模式, 用 -Register 直注册稀疏清单 (免证书/免 UAC)"
    # 清掉旧的注册 (版本变化时必须重注册)
    $existing = Get-AppxPackage -Name 'rename-invoice-ext' -ErrorAction SilentlyContinue
    if ($existing) { Remove-AppxPackage -Package $existing.PackageFullName }
    Add-AppxPackage -Register (Join-Path $PkgDir 'AppxManifest.xml') -ExternalLocation $PkgDir
} else {
    Write-Host "[..] 未开开发者模式, 走自签证书 + msix 部署流程 (弹一次 UAC)"

    $kitsBin = 'C:\Program Files (x86)\Windows Kits\10\bin'
    if (-not (Test-Path $kitsBin)) { throw "未找到 Windows SDK (需要 makeappx/signtool): $kitsBin" }
    $kit = Get-ChildItem $kitsBin -Directory |
        Where-Object { $_.Name -match '^10\.' -and (Test-Path (Join-Path $_.FullName 'x64\makeappx.exe')) } |
        Sort-Object Name -Descending | Select-Object -First 1
    $MakeAppx = Join-Path $kit.FullName 'x64\makeappx.exe'
    $Signtool = Join-Path $kit.FullName 'x64\signtool.exe'
    Write-Host "SDK: $($kit.Name)"

    if (-not (Test-Path $SignDir)) { New-Item -ItemType Directory -Path $SignDir | Out-Null }
    $PfxPath = Join-Path $SignDir 'package-sign.pfx'

    $cert = Get-ChildItem Cert:\CurrentUser\My |
        Where-Object { $_.Subject -eq $Subject -and $_.HasPrivateKey } |
        Sort-Object NotAfter -Descending | Select-Object -First 1

    if (-not $cert) {
        Write-Host "创建自签代码签名证书 $Subject ..."
        $cert = New-SelfSignedCertificate -Type Custom -Subject $Subject `
            -KeyUsage DigitalSignature -FriendlyName 'rename-invoice MSIX (self-signed)' `
            -CertStoreLocation 'Cert:\CurrentUser\My' `
            -NotAfter (Get-Date).AddYears(5) -HashAlgorithm SHA256
    }
    $Thumbprint = $cert.Thumbprint

    if (-not (Test-Path $PfxPath)) {
        $pwdPlain = [System.Guid]::NewGuid().ToString('N')
        $sec = ConvertTo-SecureString -String $pwdPlain -Force -AsPlainText
        Export-PfxCertificate -Cert $cert -FilePath $PfxPath -Password $sec | Out-Null
        Set-Content -Path (Join-Path $SignDir 'pfx-password.txt') -Value $pwdPlain -NoNewline
    } else {
        $pwdPlain = Get-Content (Join-Path $SignDir 'pfx-password.txt') -Raw
    }

    # 证书必须进 LocalMachine\TrustedPeople (签名包验证), 需要一次 UAC
    $trusted = Get-ChildItem Cert:\LocalMachine\TrustedPeople -ErrorAction SilentlyContinue |
        Where-Object { $_.Thumbprint -eq $Thumbprint }
    if (-not $trusted) {
        Write-Host "把证书导入 TrustedPeople (会弹一次 UAC) ..."
        $ps = "Import-PfxCertificate -FilePath '$PfxPath' " +
              "-CertStoreLocation Cert:\LocalMachine\TrustedPeople " +
              "-Password (ConvertTo-SecureString '$pwdPlain' -AsPlainText -Force) | Out-Null"
        $proc = Start-Process powershell -Verb RunAs -Wait -PassThru `
            -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $ps
        if ($proc.ExitCode -ne 0) { throw "证书导入失败 (UAC 被拒绝或出错)" }
        Write-Host "[OK] 证书已导入 TrustedPeople ($Thumbprint)"
    }

    if (Test-Path $Msix) { Remove-Item $Msix -Force }
    & $MakeAppx pack /nv /o /d $PkgDir /p $Msix | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "makeappx pack 失败" }

    & $Signtool sign /fd SHA256 /a /f $PfxPath /p $pwdPlain $Msix | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "signtool 签名失败" }
    Write-Host "[OK] 打包并签名完成"

    $existing = Get-AppxPackage -Name 'rename-invoice-ext' -ErrorAction SilentlyContinue
    if ($existing) { Remove-AppxPackage -Package $existing.PackageFullName }
    Add-AppxPackage -Path $Msix -ExternalLocation $PkgDir
}
if ($?) {
    Write-Host ''
    Write-Host '==========================================' -ForegroundColor Green
    Write-Host '[OK] 安装完成!  右键任意 PDF 或文件夹试试。' -ForegroundColor Green
    Write-Host '    (如果在旧菜单里看不到, 先在桌面新建文件夹试一次)' -ForegroundColor Green
    Write-Host '==========================================' -ForegroundColor Green
}
if ($RestartExplorer) {
    Stop-Process -Name explorer -Force
    Write-Host '[OK] explorer.exe 已重启'
}
