# 并排图：把 S5 地图页截图与原型截图拼成一张（验收①要求「与原型并排」）。
# 用法：python make-side-by-side.py   （在本目录执行；PYTHONUTF8=1 避免中文路径/文字问题）
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PAIRS = [
    ("cmp-390x844.png", "shot-03-map-lv3-390x844.png", "proto-390x844.png",
     "S5 学生端地图（真数据）", "原型 index.html"),
    ("cmp-1440x900.png", "shot-04-map-pc-1440x900.png", "proto-1440x900.png",
     "S5 学生端地图（真数据）", "原型 index.html"),
]
GAP = 24
BAR = 44


def font(size):
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose(out, left, right, title_l, title_r):
    a = Image.open(os.path.join(HERE, left)).convert("RGB")
    b = Image.open(os.path.join(HERE, right)).convert("RGB")
    h = max(a.height, b.height) + BAR
    w = a.width + b.width + GAP * 3
    canvas = Image.new("RGB", (w, h), (18, 16, 38))
    canvas.paste(a, (GAP, BAR))
    canvas.paste(b, (GAP * 2 + a.width, BAR))
    draw = ImageDraw.Draw(canvas)
    f = font(18)
    draw.text((GAP + 4, 13), title_l, fill=(255, 255, 255), font=f)
    draw.text((GAP * 2 + a.width + 4, 13), title_r, fill=(255, 215, 110), font=f)
    canvas.save(os.path.join(HERE, out))
    print(f"{out}: {a.size} | {b.size} -> {canvas.size}")


for row in PAIRS:
    compose(*row)