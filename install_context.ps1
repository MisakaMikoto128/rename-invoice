# 安装右键菜单: 添加发票价格前缀
# - PDF 文件右键
# - 文件夹右键
# - 文件夹空白处右键
#
# 默认使用 pythonw.exe 静默执行 (无 cmd 窗口闪烁).
# 多选文件并发右键时, 通过文件锁合并为一次处理 (见 rename_invoice.py).
#
# 用法:
#   install_context.ps1                  # 交互式: [1] 静默 / [2] 静默+汇总窗口 / [3] 静默+Excel
#   install_context.ps1 -Summary         # 非交互: 直接装"静默+汇总窗口"
#   install_context.ps1 -Xlsx            # 非交互: 直接装"静默+Excel 汇总"
#   install_context.ps1 -NoSummary       # 非交互: 直接装"静默"
[CmdletBinding(DefaultParameterSetName = 'Interactive')]
Param(
    [Parameter(ParameterSetName = 'Summary')]
    [switch]$Summary,
    [Parameter(ParameterSetName = 'Xlsx')]
    [switch]$Xlsx,
    [Parameter(ParameterSetName = 'NoSummary')]
    [switch]$NoSummary
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = $PSScriptRoot
$BatPath   = Join-Path $ScriptDir 'rename_invoice.bat'
$PyScript  = Join-Path $ScriptDir 'rename_invoice.py'
$IconPath  = Join-Path $ScriptDir 'assets\icon.ico'

if (-not (Test-Path $PyScript)) {
    Write-Host "[ERROR] 找不到 rename_invoice.py: $PyScript" -ForegroundColor Red
    pause
    exit 1
}
if (-not (Test-Path $IconPath)) {
    # 图标可选: 没有就回退到 .bat / .py 自身
    $IconPath = if (Test-Path $BatPath) { $BatPath } else { $PyScript }
}

# --- 找 pythonw.exe (优先 python 命令所在目录的 pythonw.exe) ---
function Resolve-PythonW {
    $pyCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $candidate = Join-Path (Split-Path $pyCmd.Source) 'pythonw.exe'
        if (Test-Path $candidate) { return $candidate }
    }
    $pywCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($pywCmd) { return $pywCmd.Source }
    return $null
}

$PythonW = Resolve-PythonW
if (-not $PythonW) {
    Write-Host "[WARN] 找不到 pythonw.exe, 回退到 python.exe (右键时会闪 cmd 窗口)" -ForegroundColor Yellow
    $pyCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $pyCmd) {
        Write-Host "[ERROR] 也找不到 python.exe, 请先把 Python 加进 PATH" -ForegroundColor Red
        pause
        exit 1
    }
    $PythonW = $pyCmd.Source
}

Write-Host "[INFO] pythonw 路径: $PythonW" -ForegroundColor Gray
Write-Host "[INFO] 脚本路径:    $PyScript" -ForegroundColor Gray
Write-Host ""

# --- 选择安装模式 ---
# Mode: 'silent' | 'summary' | 'xlsx'
$Mode = 'silent'
if ($Summary)        { $Mode = 'summary' }
elseif ($Xlsx)       { $Mode = 'xlsx' }
elseif ($NoSummary)  { $Mode = 'silent' }
else {
    Write-Host "请选择安装模式:" -ForegroundColor Cyan
    Write-Host "  [1] 静默 (默认) - 右键完全无窗口, 仅写日志"
    Write-Host "  [2] 静默 + 处理后弹出汇总窗口"
    Write-Host "  [3] 静默 + 自动导出 Excel 汇总到当前文件夹"
    $choice = Read-Host "选择 (回车=1)"
    switch ($choice.Trim()) {
        '2' { $Mode = 'summary' }
        '3' { $Mode = 'xlsx' }
        default { $Mode = 'silent' }
    }
}

switch ($Mode) {
    'summary' {
        Write-Host "[INFO] 安装模式: 静默 + 汇总窗口" -ForegroundColor Cyan
        $ExtraArgs = '--silent --summary'
    }
    'xlsx' {
        Write-Host "[INFO] 安装模式: 静默 + Excel 汇总" -ForegroundColor Cyan
        $ExtraArgs = '--silent --xlsx'
    }
    default {
        Write-Host "[INFO] 安装模式: 静默 (无窗口)" -ForegroundColor Cyan
        $ExtraArgs = '--silent'
    }
}

# %1 = file path (file/folder right-click), %V = current dir (background right-click)
$CmdFile = '"' + $PythonW + '" "' + $PyScript + '" ' + $ExtraArgs + ' "%1"'
$CmdBg   = '"' + $PythonW + '" "' + $PyScript + '" ' + $ExtraArgs + ' "%V"'

$MenuText = '添加发票价格前缀'
$KeyName  = 'AddInvoicePrice'

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
switch ($Mode) {
    'summary' { Write-Host "(已启用汇总窗口: 处理完后会弹一个 Tk 窗口列出全部结果)" -ForegroundColor Yellow }
    'xlsx'    { Write-Host "(已启用 Excel 导出: 处理完后会在当前文件夹生成 发票汇总_<时间戳>.xlsx)" -ForegroundColor Yellow }
    default   { Write-Host "(静默模式: 完全无窗口, 结果写入 rename_invoice.log)" -ForegroundColor Yellow }
}
Write-Host "(Win11 用户可能需要点'显示更多选项'才能看到自定义菜单)" -ForegroundColor Yellow
Write-Host ""
pause
