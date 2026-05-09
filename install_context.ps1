# 安装右键菜单: 添加发票价格前缀
# - PDF 文件右键
# - 文件夹右键
# - 文件夹空白处右键
#
# 默认使用 pythonw.exe 静默执行 (无 cmd 窗口闪烁).
# 多选文件并发右键时, 通过文件锁合并为一次处理 (见 rename_invoice.py).
#
# 用法:
#   install_context.ps1                  # 交互式: 两个独立 y/n 问题 (汇总窗口? Excel 汇总?)
#   install_context.ps1 -Summary         # 非交互: 启用汇总窗口 (Excel 关)
#   install_context.ps1 -Xlsx            # 非交互: 启用 Excel 汇总 (窗口关)
#   install_context.ps1 -Summary -Xlsx   # 非交互: 两个都启用
#   install_context.ps1 -NoPrompt        # 非交互: 两个都关闭 (纯静默)
Param(
    [switch]$Summary,
    [switch]$Xlsx,
    [switch]$NoPrompt
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

# --- 选两个独立选项 ---
function Read-YesNo($prompt, $default = $false) {
    $hint = if ($default) { '[Y/n]' } else { '[y/N]' }
    $ans  = Read-Host "$prompt $hint"
    $t    = $ans.Trim().ToLower()
    if ($t -eq '') { return $default }
    return ($t -eq 'y' -or $t -eq 'yes')
}

$EnableSummary = $Summary.IsPresent
$EnableXlsx    = $Xlsx.IsPresent

if (-not $NoPrompt -and -not $Summary -and -not $Xlsx) {
    Write-Host "请回答两个独立问题 (回车=否, 都选否就是纯静默):" -ForegroundColor Cyan
    $EnableSummary = Read-YesNo "  1) 处理完后弹出 Tk 汇总窗口?" $false
    $EnableXlsx    = Read-YesNo "  2) 处理完后在文件夹生成 Excel 汇总?" $false
}

$ExtraArgsParts = @('--silent')
if ($EnableSummary) { $ExtraArgsParts += '--summary' }
if ($EnableXlsx)    { $ExtraArgsParts += '--xlsx' }
$ExtraArgs = ($ExtraArgsParts -join ' ')

$ModeDesc = if ($EnableSummary -and $EnableXlsx) { '静默 + 汇总窗口 + Excel 汇总' }
            elseif ($EnableSummary)              { '静默 + 汇总窗口' }
            elseif ($EnableXlsx)                 { '静默 + Excel 汇总' }
            else                                  { '静默 (纯无窗口)' }
Write-Host "[INFO] 安装模式: $ModeDesc" -ForegroundColor Cyan

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
if ($EnableSummary) { Write-Host "(汇总窗口: 处理完后会弹一个 Tk 窗口列出全部结果)" -ForegroundColor Yellow }
if ($EnableXlsx)    { Write-Host "(Excel 导出: 处理完后会在当前文件夹生成 发票汇总_<时间戳>.xlsx)" -ForegroundColor Yellow }
if (-not $EnableSummary -and -not $EnableXlsx) {
    Write-Host "(纯静默: 完全无窗口, 结果写入 rename_invoice.log)" -ForegroundColor Yellow
}
Write-Host "(Win11 用户可能需要点'显示更多选项'才能看到自定义菜单)" -ForegroundColor Yellow
Write-Host ""
if (-not $NoPrompt) { pause }
