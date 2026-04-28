# 安装右键菜单: 添加发票价格前缀
# - PDF 文件右键
# - 文件夹右键
# - 文件夹空白处右键

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BatPath = Join-Path $PSScriptRoot 'rename_invoice.bat'
$IconPath = Join-Path $PSScriptRoot 'assets\icon.ico'
if (-not (Test-Path $BatPath)) {
    Write-Host "[ERROR] 找不到 rename_invoice.bat: $BatPath" -ForegroundColor Red
    pause
    exit 1
}
# 图标可选: 有就用, 没有就回退到 .bat 自身
if (-not (Test-Path $IconPath)) {
    $IconPath = $BatPath
}

$MenuText = '添加发票价格前缀'
$KeyName  = 'AddInvoicePrice'

# %1 = file path (file/folder right-click), %V = current dir (background right-click)
$CmdFile = '"' + $BatPath + '" "%1"'
$CmdBg   = '"' + $BatPath + '" "%V"'

$Targets = @(
    @{ Path = "HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\$KeyName"; Cmd = $CmdFile; Desc = 'PDF 文件右键' },
    @{ Path = "HKCU:\Software\Classes\Directory\shell\$KeyName";                   Cmd = $CmdFile; Desc = '文件夹右键' },
    @{ Path = "HKCU:\Software\Classes\Directory\Background\shell\$KeyName";        Cmd = $CmdBg;   Desc = '文件夹空白处右键' }
)

foreach ($t in $Targets) {
    $shellKey   = $t.Path
    $commandKey = "$($t.Path)\command"

    if (-not (Test-Path $shellKey))   { New-Item -Path $shellKey   -Force | Out-Null }
    if (-not (Test-Path $commandKey)) { New-Item -Path $commandKey -Force | Out-Null }

    Set-ItemProperty -Path $shellKey   -Name '(Default)' -Value $MenuText
    Set-ItemProperty -Path $shellKey   -Name 'Icon'      -Value $IconPath
    Set-ItemProperty -Path $commandKey -Name '(Default)' -Value $t.Cmd

    Write-Host "[OK] $($t.Desc): $shellKey" -ForegroundColor Green
}

Write-Host ""
Write-Host "完成! 现在你可以:" -ForegroundColor Cyan
Write-Host "  - 在任意 PDF 上右键 -> '$MenuText'"
Write-Host "  - 在任意文件夹上右键 -> '$MenuText'"
Write-Host "  - 在文件夹空白处右键 -> '$MenuText'"
Write-Host ""
Write-Host "(Win11 用户可能需要点'显示更多选项'才能看到自定义菜单)" -ForegroundColor Yellow
Write-Host ""
pause
