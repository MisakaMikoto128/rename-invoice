# -*- coding: utf-8 -*-
"""
生成 rename-invoice 项目图标 (.ico + .png).

设计:
  - 圆角矩形背景, 深蓝色 #1e3a5f (财务/专业感)
  - 白色 "¥" 字符居中
  - 输出多尺寸 .ico (16/32/48/64/128/256) + 256 PNG

依赖: pip install pillow
重新生成: python generate_icon.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).parent
BG = (30, 58, 95, 255)        # #1e3a5f deep professional blue
FG = (255, 255, 255, 255)     # white
SIZE = 1024                   # render at high res, downsample for sharpness
RADIUS = int(SIZE * 0.18)     # rounded corner radius
FONT_PATH = r'C:\Windows\Fonts\segoeuib.ttf'  # Segoe UI Bold


def render_master(size: int = SIZE) -> Image.Image:
    """渲染高分辨率主图, 后续 downsample 出多尺寸."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆角背景
    radius = int(size * 0.18)
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=radius,
        fill=BG,
    )

    # ¥ 字符 - 占主体
    font_size = int(size * 0.72)
    font = ImageFont.truetype(FONT_PATH, font_size)
    text = '¥'
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    # 视觉居中: 字形 bbox 不一定从 0 开始, 减去左/上偏移
    x = (size - text_w) / 2 - bbox[0]
    y = (size - text_h) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=FG)

    return img


def main():
    master = render_master()

    # 256 PNG (用于 README、网络展示)
    png_path = OUT_DIR / 'icon-256.png'
    master.resize((256, 256), Image.LANCZOS).save(png_path, 'PNG')
    print(f'[OK] {png_path}')

    # 1024 PNG (高清原图, 备用)
    big_png = OUT_DIR / 'icon-1024.png'
    master.save(big_png, 'PNG')
    print(f'[OK] {big_png}')

    # 多尺寸 .ico (Windows 资源管理器/任务栏会自动选最合适的)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = [master.resize(s, Image.LANCZOS) for s in sizes]
    ico_path = OUT_DIR / 'icon.ico'
    images[0].save(ico_path, format='ICO', sizes=sizes, append_images=images[1:])
    print(f'[OK] {ico_path}  (sizes: {sizes})')


if __name__ == '__main__':
    main()
