fn main() {
    // 编译 Slint UI
    slint_build::compile("ui/summary.slint").expect("slint compile failed");

    // Windows: 嵌入 .exe 图标 + 把 -w.exe 切换成 windows 子系统
    #[cfg(target_os = "windows")]
    {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("assets/icon.ico");
        if let Err(e) = res.compile() {
            eprintln!("cargo:warning=failed to embed icon: {}", e);
        }

        // 默认子系统是 console; 只把 -w.exe 改成 windows 子系统 (无 cmd 闪窗)
        // /ENTRY:mainCRTStartup 让 MSVC 用 fn main 而不是 WinMain (Rust 提供的是前者)
        println!("cargo:rustc-link-arg-bin=rename-invoice-w=/SUBSYSTEM:WINDOWS");
        println!("cargo:rustc-link-arg-bin=rename-invoice-w=/ENTRY:mainCRTStartup");
    }
}
