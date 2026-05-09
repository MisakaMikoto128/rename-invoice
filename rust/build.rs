fn main() {
    // 编译 Slint UI
    slint_build::compile("ui/summary.slint").expect("slint compile failed");

    // Windows: 嵌入 .exe 图标 + 应用 manifest (启用 visual styles)
    #[cfg(target_os = "windows")]
    {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("assets/icon.ico");
        if let Err(e) = res.compile() {
            eprintln!("cargo:warning=failed to embed icon: {}", e);
        }
    }
}
