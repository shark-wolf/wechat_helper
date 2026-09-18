import os
from PIL import Image, ImageDraw

def create_wechat_app_icon(output_path="app_icon.ico"):
    """
    生成高品质超采样抗锯齿微信风格图标 (.ico)
    :param output_path: 图标保存路径
    """
    # 1. 设置 4 倍超采样画布 (1024x1024) 提升边缘平滑度
    scale = 4
    canvas_size = (256 * scale, 256 * scale)

    # 创建超高分辨率 RGBA 画布
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # 2. 放大坐标以在 1024x1024 画布上绘制
    bg_color = (7, 193, 96, 255)  # 微信绿色
    draw.rounded_rectangle(
        [10 * scale, 10 * scale, 246 * scale, 246 * scale],
        radius=50 * scale,
        fill=bg_color
    )

    # 3. 绘制主聊天气泡 (白色)
    draw.ellipse([50 * scale, 60 * scale, 170 * scale, 160 * scale], fill=(255, 255, 255, 255))
    draw.polygon(
        [(60 * scale, 140 * scale), (40 * scale, 175 * scale), (90 * scale, 155 * scale)],
        fill=(255, 255, 255, 255)
    )

    # 4. 绘制副聊天气泡 (略小带半透明)
    draw.ellipse([100 * scale, 100 * scale, 206 * scale, 190 * scale], fill=(255, 255, 255, 240))
    draw.polygon(
        [(190 * scale, 170 * scale), (210 * scale, 195 * scale), (170 * scale, 185 * scale)],
        fill=(255, 255, 255, 240)
    )

    # 5. 使用高质量 LANCZOS 滤波缩放至标准 256x256 尺寸
    img_hd = canvas.resize((256, 256), resample=Image.Resampling.LANCZOS)

    # 6. 保存为兼容 Windows 各级缩放的完整 ICO 图标文件
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img_hd.save(output_path, format="ICO", sizes=sizes)
    print(f"高清图标已生成并保存至: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    create_wechat_app_icon()
