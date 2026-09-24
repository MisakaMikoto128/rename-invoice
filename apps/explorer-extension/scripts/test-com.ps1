# COM 冒烟测试: CoCreate 扩展的 IExplorerCommand 并调 GetTitle / GetIcon / GetState
# 用法: powershell -File scripts\test-com.ps1   (先跑 install.ps1)
$src = @"
using System;
using System.Runtime.InteropServices;

namespace InvoiceExtTest {
    // 我们 DLL 里的 COM 类 (CLSID 与 src/lib.rs 的 CLSID_INVOICE_EXT 一致)
    [ComImport, Guid("377B2F61-66A6-4688-A5BE-82AD42F3ADF6")]
    class InvoiceCommandClass {}

    // 真实 IID 来自 shobjidl_core: IExplorerCommand
    [ComImport, Guid("A08CE4D0-FA25-44AB-B57C-C7B1C323E0B9"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IExplorerCommandPartial
    {
        [PreserveSig] int GetTitle(IntPtr psiItemArray, out IntPtr ppszTitle);
        [PreserveSig] int GetIcon(IntPtr psiItemArray, out IntPtr ppszIcon);
        [PreserveSig] int GetToolTip(IntPtr psiItemArray, out IntPtr ppszToolTip);
        [PreserveSig] int GetCanonicalName(out Guid guid);
        [PreserveSig] int GetState(IntPtr psiArray, int fOkToBeSlow, out uint pCmdState);
    }

    public static class Test {
        public static int Run() {
            object obj = new InvoiceCommandClass();          // CoCreateInstance
            var cmd = (IExplorerCommandPartial)obj;          // QueryInterface

            IntPtr title;
            int hr = cmd.GetTitle(IntPtr.Zero, out title);
            if (hr != 0) { Console.WriteLine("FAIL GetTitle hr=0x" + hr.ToString("X")); return 1; }
            string titleStr = Marshal.PtrToStringUni(title);
            Marshal.FreeCoTaskMem(title);
            Console.WriteLine("GetTitle  = " + titleStr);

            IntPtr icon;
            hr = cmd.GetIcon(IntPtr.Zero, out icon);
            string iconStr = hr == 0 ? Marshal.PtrToStringUni(icon) : "(error 0x" + hr.ToString("X") + ")";
            if (hr == 0) Marshal.FreeCoTaskMem(icon);
            Console.WriteLine("GetIcon   = " + iconStr);

            Guid canonical;
            cmd.GetCanonicalName(out canonical);
            Console.WriteLine("Canonical = " + canonical);

            uint state;
            cmd.GetState(IntPtr.Zero, 0, out state);
            Console.WriteLine("GetState(null) = " + state + " (0=enabled, 4=hidden)");

            Console.WriteLine(titleStr == "添加发票价格前缀" ? "PASS" : "TITLE-MISMATCH");
            return 0;
        }
    }
}
"@

Add-Type -TypeDefinition $src -Language CSharp
exit [InvoiceExtTest.Test]::Run()
