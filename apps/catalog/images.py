"""Placeholder product pictures drawn with Pillow (no copyrighted photos in the demo)."""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

COLORS = {
    "brake_pad": ("#fde68a", "#92400e"),
    "brake_disc": ("#e5e7eb", "#374151"),
    "brake_drum": ("#d1d5db", "#1f2937"),
    "oil_filter": ("#bfdbfe", "#1e3a8a"),
    "air_filter": ("#bbf7d0", "#14532d"),
    "air_spring": ("#e9d5ff", "#4c1d95"),
    "shock_absorber": ("#fecaca", "#7f1d1d"),
    "clutch_disc": ("#fed7aa", "#7c2d12"),
}


def _font(size):
    for name in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _shape(draw: ImageDraw.ImageDraw, code: str, fg: str):
    c = 300
    if code in ("brake_disc", "clutch_disc"):
        draw.ellipse((c - 170, c - 190, c + 170, c + 150), outline=fg, width=18)
        draw.ellipse((c - 70, c - 90, c + 70, c + 50), outline=fg, width=12)
        for i in range(10 if code == "brake_disc" else 6):
            a = i * 2 * math.pi / (10 if code == "brake_disc" else 6)
            x, y = c + 105 * math.cos(a), c - 20 + 105 * math.sin(a)
            draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=fg)
    elif code == "brake_drum":
        draw.ellipse((c - 180, c - 200, c + 180, c + 160), fill=fg)
        draw.ellipse((c - 120, c - 140, c + 120, c + 100), fill="#9ca3af")
        draw.ellipse((c - 45, c - 65, c + 45, c + 25), fill=fg)
    elif code == "brake_pad":
        for dx in (-95, 95):
            draw.rounded_rectangle((c + dx - 80, c - 170, c + dx + 80, c + 110), radius=40, fill=fg)
            draw.rounded_rectangle((c + dx - 62, c - 150, c + dx + 62, c + 90), radius=30, fill="#78716c")
    elif code in ("oil_filter", "air_filter"):
        w = 110 if code == "oil_filter" else 150
        draw.rectangle((c - w, c - 170, c + w, c + 120), fill=fg)
        draw.ellipse((c - w, c - 200, c + w, c - 140), fill="#475569")
        for y in range(c - 130, c + 110, 22):
            draw.line((c - w + 15, y, c + w - 15, y), fill="#cbd5e1", width=4)
    elif code == "air_spring":
        for i, y in enumerate((c - 150, c - 60, c + 30)):
            draw.ellipse((c - 150, y - 55, c + 150, y + 55), fill=fg if i % 2 == 0 else "#6d28d9")
        draw.rectangle((c - 120, c - 215, c + 120, c - 190), fill="#1f2937")
        draw.rectangle((c - 90, c + 85, c + 90, c + 130), fill="#1f2937")
    elif code == "shock_absorber":
        draw.rectangle((c - 35, c - 200, c + 35, c - 40), fill="#9ca3af")
        draw.rectangle((c - 65, c - 60, c + 65, c + 110), fill=fg)
        draw.ellipse((c - 40, c - 245, c + 40, c - 175), outline=fg, width=14)
        draw.ellipse((c - 40, c + 100, c + 40, c + 170), outline=fg, width=14)


def draw_part_image(path: Path, code: str, title: str, subtitle: str = "", demo_label: dict | None = None, photo: bool = False):
    bg, fg = COLORS.get(code, ("#f3f4f6", "#111827"))
    img = Image.new("RGB", (600, 600), "#6b7280" if photo else bg)
    draw = ImageDraw.Draw(img)
    if photo:  # "customer photo": darker background, label sticker with numbers
        draw.rectangle((30, 30, 570, 570), fill="#a8a29e")
    _shape(draw, code, fg)
    draw.text((300, 500), title, font=_font(30), fill="#111827", anchor="mm")
    if subtitle:
        draw.text((300, 545), subtitle, font=_font(22), fill="#374151", anchor="mm")
    if not photo:
        draw.text((575, 25), "DEMO", font=_font(18), fill="#6b7280", anchor="ra")
    path.parent.mkdir(parents=True, exist_ok=True)
    info = PngInfo()
    if demo_label:
        info.add_text("demo_label", json.dumps(demo_label, ensure_ascii=False))
    img.save(path, pnginfo=info)
    return path
