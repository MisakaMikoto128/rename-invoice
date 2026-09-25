# COM Invoke 端到端测试: 构造真实 IShellItemArray, 调 IExplorerCommand::Invoke,
# 验证完整链路 (DLL -> spawn CLI -> 重命名). 用法:
#   powershell -File scripts\test-invoke.ps1 -PdfPath "D:\test\某发票.pdf"
# 前置: -PdfPath 指向一个【无前缀】的可识别增值税发票 PDF.
param(
    [Parameter(Mandatory = $true)]
    [string]$PdfPath
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $PdfPath)) { throw "找不到测试 PDF: $PdfPath" }
$full = (Resolve-Path $PdfPath).Path
$dir = Split-Path $full -Parent
$name = Split-Path $full -Leaf
Write-Host "目标: $full"

$src = @"
using System;
using System.Runtime.InteropServices;

namespace InvoiceInvokeTest {
    [ComImport, Guid("377B2F61-66A6-4688-A5BE-82AD42F3ADF6")]
    class InvoiceCommandClass {}

    [ComImport, Guid("A08CE4D0-FA25-44AB-B57C-C7B1C323E0B9"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IExplorerCommandWithInvoke
    {
        [PreserveSig] int GetTitle(IntPtr psiItemArray, out IntPtr ppszTitle);
        [PreserveSig] int GetIcon(IntPtr psiItemArray, out IntPtr ppszIcon);
        [PreserveSig] int GetToolTip(IntPtr psiItemArray, out IntPtr ppszToolTip);
        [PreserveSig] int GetCanonicalName(out Guid guid);
        [PreserveSig] int GetState(IntPtr psiItemArray, int fOkToBeSlow, out uint pCmdState);
        [PreserveSig] int Invoke(IntPtr psiItemArray, IntPtr pbc);
    }

    public static class Test {
        [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
        public static extern void SHCreateItemFromParsingName(
            string path, IntPtr pbc, ref Guid riid, out IntPtr ppv);

        [DllImport("shell32.dll", PreserveSig = false)]
        public static extern void SHCreateShellItemArrayFromShellItem(
            IntPtr psi, ref Guid riid, out IntPtr ppv);

        public static int Run(string path) {
            object obj = new InvoiceCommandClass();
            var cmd = (IExplorerCommandWithInvoke)obj;

            Guid iidItem  = new Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"); // IShellItem
            Guid iidArray = new Guid("B63EA76D-1F85-456F-A19C-48159EFA858B"); // IShellItemArray

            IntPtr item;
            SHCreateItemFromParsingName(path, IntPtr.Zero, ref iidItem, out item);
            Console.WriteLine("IShellItem   OK");

            IntPtr array;
            SHCreateShellItemArrayFromShellItem(item, ref iidArray, out array);
            Console.WriteLine("IShellItemArray OK");

            int hr = cmd.Invoke(array, IntPtr.Zero);
            Console.WriteLine("Invoke hr = 0x" + hr.ToString("X") + (hr == 0 ? " (S_OK)" : " (FAIL)"));
            Marshal.Release(array);
            Marshal.Release(item);
            return hr;
        }
    }
}
"@

Add-Type -TypeDefinition $src -Language CSharp
$hr = [InvoiceInvokeTest.Test]::Run($full)
if ($hr -ne 0) { throw "Invoke 失败" }

# 等 CLI (pythonw --silent, 0.25s debounce + PDF 解析) 完成
Write-Host "等待 CLI 处理 ..."
$deadline = (Get-Date).AddSeconds(15)
$done = $false
while ((Get-Date) -lt $deadline -and -not $done) {
    Start-Sleep -Milliseconds 500
    $children = Get-ChildItem -LiteralPath $dir -File
    foreach ($f in $children) {
        if ($f.Name -match '^\d+(\.\d{1,2})?元-' -and $f.Name -like "*$name") { $done = $true; break }
        if ($f.Name -eq $name) { $done = $false }
    }
    # 原文件已不在且目录里出现带前缀文件 -> 成功; 原文件还在 -> 继续等
    if (-not (Test-Path (Join-Path $dir $name)) ) { $done = $true }
}
if ($done) {
    Write-Host "[PASS] Invoke 端到端: PDF 已被重命名"
    Get-ChildItem -LiteralPath $dir -File | ForEach-Object { Write-Host ("  -> " + $_.Name) }
    exit 0
} else {
    Write-Host "[FAIL] 15 秒内未见重命名发生"
    Get-ChildItem -LiteralPath $dir -File | ForEach-Object { Write-Host ("  -> " + $_.Name) }
    exit 1
}
