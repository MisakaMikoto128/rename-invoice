<#
.SYNOPSIS
    列出 / 禁用 / 恢复 Windows 右键菜单的 shell 扩展 (COM ContextMenuHandlers)。

.DESCRIPTION
    右键菜单慢, 绝大多数情况是因为 Explorer 构建"显示更多选项"那个经典菜单时,
    要逐个 COM 实例化已注册的 shell 扩展 DLL —— 装的软件越多越慢, 而且是串行的,
    其中任何一个 DLL 卡一下, 整个菜单就卡一下。

    本脚本【不删除】任何软件的注册信息, 而是往 Windows 自带的屏蔽名单里加 CLSID:

        HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Extensions\Blocked

    Explorer 看到名单里有这个 CLSID 就不再加载它。NirSoft 的 ShellExView 用的也是
    这个机制。特点:
      - 完全可逆 (-Enable 就恢复)
      - 不影响软件本身运行, 只是不出现在右键菜单里
      - 按 CLSID 记录, 软件升级/重装也绕不过去

    默认隐藏微软自家的系统扩展 (system32 / SysWOW64 下的), 免得手滑把"共享"、
    "打开方式"、"发送到"这类核心功能关掉。想看全部加 -IncludeMicrosoft。

.PARAMETER Disable
    进入禁用模式。不带 -Id 就列出来让你输编号。

.PARAMETER Enable
    进入恢复模式, 列出当前被屏蔽的, 选编号恢复。

.PARAMETER Id
    非交互指定编号, 逗号分隔。编号取自本次运行打印的那张表。

.PARAMETER IncludeMicrosoft
    连微软自家的系统扩展一起列出 (默认隐藏)。

.PARAMETER RestartExplorer
    改完直接重启 explorer.exe, 不再询问。

.EXAMPLE
    .\shell-ext-manager.ps1
    只列出, 什么都不改。不需要管理员权限。

.EXAMPLE
    .\shell-ext-manager.ps1 -Disable
    列出后让你输编号, 比如: 3,5,7

.EXAMPLE
    .\shell-ext-manager.ps1 -Disable -Id 3,5,7

.EXAMPLE
    .\shell-ext-manager.ps1 -Enable
    看当前屏蔽了哪些, 选编号恢复。

.NOTES
    -Disable / -Enable 需要管理员权限 (屏蔽名单在 HKLM)。
    每次修改前会把屏蔽名单导出成 .reg 备份, 放在脚本同目录。
    改完必须重启 explorer.exe 才生效。
#>
[CmdletBinding()]
Param(
    [switch]$Disable,
    [switch]$Enable,
    [int[]]$Id,
    [switch]$IncludeMicrosoft,
    [switch]$RestartExplorer
)

$ErrorActionPreference = 'Stop'

$BlockedKeys = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Extensions\Blocked',
    'HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Explorer\Shell Extensions\Blocked'
)

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-BlockedClsids {
    $set = @{}
    foreach ($k in $BlockedKeys) {
        if (-not (Test-Path -LiteralPath $k)) { continue }
        $props = Get-ItemProperty -LiteralPath $k
        foreach ($p in $props.PSObject.Properties) {
            if ($p.Name -like '{*}') { $set[$p.Name.ToUpper()] = $true }
        }
    }
    return $set
}

function Get-DefaultValue($keyPath) {
    if (-not (Test-Path -LiteralPath $keyPath)) { return $null }
    try {
        return (Get-ItemProperty -LiteralPath $keyPath -ErrorAction Stop).'(default)'
    } catch {
        return $null
    }
}

function Get-ClsidInfo($clsid) {
    $name = ''
    $dll = ''
    $bases = @(
        'HKLM:\SOFTWARE\Classes\CLSID',
        'HKLM:\SOFTWARE\Classes\Wow6432Node\CLSID',
        'HKCU:\SOFTWARE\Classes\CLSID'
    )
    foreach ($base in $bases) {
        $k = Join-Path $base $clsid
        if (-not (Test-Path -LiteralPath $k)) { continue }
        if (-not $name) { $name = Get-DefaultValue $k }
        foreach ($server in @('InprocServer32', 'LocalServer32')) {
            if ($dll) { break }
            $dll = Get-DefaultValue (Join-Path $k $server)
        }
        if ($name -and $dll) { break }
    }
    return [pscustomobject]@{ Name = $name; Dll = $dll }
}

function Format-Location($rootPath) {
    $s = $rootPath
    $s = $s -replace '^HKLM:\\SOFTWARE\\Classes\\', 'HKLM\'
    $s = $s -replace '^HKCU:\\SOFTWARE\\Classes\\', 'HKCU\'
    $s = $s -replace '\\shellex\\ContextMenuHandlers$', ''
    return $s
}

function Get-ContextMenuHandlers {
    # 经典右键菜单会遍历的几个挂载点
    $classPaths = @(
        '*',
        'AllFilesystemObjects',
        'Directory',
        'Directory\Background',
        'Folder',
        'Drive'
    )
    $roots = @()
    foreach ($hive in @('HKLM:\SOFTWARE\Classes', 'HKCU:\SOFTWARE\Classes')) {
        foreach ($cp in $classPaths) {
            $roots += (Join-Path $hive ($cp + '\shellex\ContextMenuHandlers'))
        }
        # .pdf 关联的 ProgID 链 (Adobe / Foxit 常挂这儿)
        foreach ($ext in @('.pdf')) {
            $progId = Get-DefaultValue (Join-Path $hive $ext)
            if ($progId) {
                $roots += (Join-Path $hive ($progId + '\shellex\ContextMenuHandlers'))
            }
            $roots += (Join-Path $hive ('SystemFileAssociations\' + $ext + '\shellex\ContextMenuHandlers'))
        }
    }

    $byClsid = @{}
    foreach ($root in ($roots | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        foreach ($k in (Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue)) {
            $keyName = $k.PSChildName
            $clsid = Get-DefaultValue $k.PSPath
            if (-not $clsid -or $clsid -notlike '{*}') {
                # 有些扩展直接拿 CLSID 当子键名, 默认值是空的
                if ($keyName -like '{*}') { $clsid = $keyName } else { continue }
            }
            $clsid = $clsid.Trim().ToUpper()
            if (-not $byClsid.ContainsKey($clsid)) {
                $info = Get-ClsidInfo $clsid
                $display = if ($info.Name) { $info.Name } else { $keyName }
                $byClsid[$clsid] = [pscustomobject]@{
                    Clsid     = $clsid
                    KeyName   = $keyName
                    Name      = $display
                    Dll       = $info.Dll
                    Locations = New-Object System.Collections.ArrayList
                }
            }
            [void]$byClsid[$clsid].Locations.Add((Format-Location $root))
        }
    }
    return $byClsid.Values
}

function Test-IsMicrosoftSystem($dll) {
    if (-not $dll) { return $false }
    $d = $dll.Trim('"').ToLower()
    $win = $env:SystemRoot.ToLower()
    return ($d.StartsWith($win + '\system32\')) -or ($d.StartsWith($win + '\syswow64\'))
}

function Backup-BlockedList {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $dir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
    $out = Join-Path $dir ('shell-ext-blocked-backup-' + $stamp + '.reg')
    $key = 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Extensions\Blocked'
    & reg.exe export $key $out /y 2>$null | Out-Null
    if (Test-Path -LiteralPath $out) {
        Write-Host "[备份] 屏蔽名单已导出: $out" -ForegroundColor DarkGray
    } else {
        Write-Host '[备份] 屏蔽名单当前为空, 无需备份' -ForegroundColor DarkGray
    }
}

# ---------------------------------------------------------------------------

$blocked = Get-BlockedClsids
$all = @(Get-ContextMenuHandlers)

if ($Enable) {
    $list = @($all | Where-Object { $blocked.ContainsKey($_.Clsid) } | Sort-Object Name)
    $title = '当前被屏蔽的 shell 扩展'
} else {
    $visible = $all | Where-Object { $IncludeMicrosoft -or -not (Test-IsMicrosoftSystem $_.Dll) }
    $list = @($visible | Sort-Object @{ Expression = { [bool]$blocked.ContainsKey($_.Clsid) } }, Name)
    $title = '右键菜单 shell 扩展'
    if (-not $IncludeMicrosoft) {
        $title += ' (已隐藏微软系统自带的; 加 -IncludeMicrosoft 看全部)'
    }
}

if ($list.Count -eq 0) {
    Write-Host '没有可列出的项。' -ForegroundColor Yellow
    return
}

Write-Host ''
Write-Host "=== $title ===" -ForegroundColor Cyan
Write-Host ''
for ($i = 0; $i -lt $list.Count; $i++) {
    $e = $list[$i]
    $isBlocked = $blocked.ContainsKey($e.Clsid)
    $mark = if ($isBlocked) { '[已屏蔽]' } else { '[  正常]' }
    $color = if ($isBlocked) { 'DarkGray' } else { 'White' }
    Write-Host ("{0,3}. {1} {2}" -f ($i + 1), $mark, $e.Name) -ForegroundColor $color
    $dllText = if ($e.Dll) { $e.Dll } else { '(未注册 / 卸载残留)' }
    Write-Host ("      DLL   : {0}" -f $dllText) -ForegroundColor DarkGray
    Write-Host ("      CLSID : {0}" -f $e.Clsid) -ForegroundColor DarkGray
    Write-Host ("      挂载点: {0}" -f (($e.Locations | Select-Object -Unique) -join ', ')) -ForegroundColor DarkGray
}
Write-Host ''

if (-not ($Disable -or $Enable)) {
    Write-Host '只读模式, 什么都没改。' -ForegroundColor Yellow
    Write-Host '  禁用:  .\shell-ext-manager.ps1 -Disable' -ForegroundColor Gray
    Write-Host '  恢复:  .\shell-ext-manager.ps1 -Enable' -ForegroundColor Gray
    return
}

if (-not (Test-Admin)) {
    Write-Host '[ERROR] 修改屏蔽名单需要管理员权限。' -ForegroundColor Red
    Write-Host '        请在"以管理员身份运行"的 PowerShell 里重跑本脚本。' -ForegroundColor Red
    return
}

if (-not $Id -or $Id.Count -eq 0) {
    $verb = if ($Enable) { '恢复' } else { '禁用' }
    $ans = Read-Host "输入要$verb 的编号 (逗号分隔, 如 3,5,7; 直接回车=放弃)"
    if (-not $ans.Trim()) {
        Write-Host '已放弃, 什么都没改。' -ForegroundColor Yellow
        return
    }
    $Id = @()
    foreach ($t in $ans.Split(',')) {
        $t = $t.Trim()
        if ($t -match '^\d+$') { $Id += [int]$t }
    }
}

$targets = @()
foreach ($n in ($Id | Select-Object -Unique)) {
    if ($n -lt 1 -or $n -gt $list.Count) {
        Write-Host "[跳过] 编号 $n 超出范围 1..$($list.Count)" -ForegroundColor Yellow
        continue
    }
    $targets += $list[$n - 1]
}
if ($targets.Count -eq 0) {
    Write-Host '没有有效编号, 什么都没改。' -ForegroundColor Yellow
    return
}

$actionWord = if ($Enable) { '恢复' } else { '禁用' }
Write-Host ''
Write-Host "即将$actionWord :" -ForegroundColor Cyan
foreach ($t in $targets) { Write-Host "  - $($t.Name)   $($t.Clsid)" }
$confirm = Read-Host '确认? (y/N)'
if ($confirm.Trim().ToLower() -ne 'y') {
    Write-Host '已放弃。' -ForegroundColor Yellow
    return
}

Backup-BlockedList

foreach ($t in $targets) {
    foreach ($bk in $BlockedKeys) {
        if ($Enable) {
            if (Test-Path -LiteralPath $bk) {
                try { Remove-ItemProperty -LiteralPath $bk -Name $t.Clsid -ErrorAction Stop } catch {}
            }
        } else {
            if (-not (Test-Path -LiteralPath $bk)) { New-Item -Path $bk -Force | Out-Null }
            New-ItemProperty -LiteralPath $bk -Name $t.Clsid -Value $t.Name -PropertyType String -Force | Out-Null
        }
    }
    $word = if ($Enable) { '已恢复' } else { '已屏蔽' }
    Write-Host "[$word] $($t.Name)" -ForegroundColor Green
}

Write-Host ''
Write-Host '要重启 explorer.exe 才生效 (桌面会闪一下, 不影响其它程序)。' -ForegroundColor Yellow
$doRestart = $RestartExplorer
if (-not $doRestart) {
    $r = Read-Host '现在重启 explorer.exe? (y/N)'
    $doRestart = ($r.Trim().ToLower() -eq 'y')
}
if ($doRestart) {
    Stop-Process -Name explorer -Force
    Write-Host 'explorer.exe 已重启。' -ForegroundColor Green
} else {
    Write-Host '记得稍后手动重启 explorer.exe 或注销重登。' -ForegroundColor Gray
}
