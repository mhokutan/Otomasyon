from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
import logging

logger = logging.getLogger(__name__)

W, H = 1080, 1920
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _bg():
    # Morumsu degrade + noise
    img = Image.new("RGB", (W, H), (24, 18, 36))
    d = ImageDraw.Draw(img)
    for y in range(H):
        c = int(24 + 40 * (y / H))
        d.line([(0, y), (W, y)], fill=(c, 18 + (y % 20), 50 + (y % 30)))
    px = img.load()
    for _ in range(15000):
        x = random.randint(0, W-1); y = random.randint(0, H-1)
        r,g,b = px[x,y]; dd = random.randint(-10, 10)
        px[x,y] = (max(0, min(255, r+dd)), max(0, min(255, g+dd)), max(0, min(255, b+dd)))
    return img.filter(ImageFilter.GaussianBlur(1.5))

def _wrap(text, font, max_width):
    words = text.split()
    lines, cur = [], []
    d = ImageDraw.Draw(Image.new("RGB", (1,1)))
    for w in words:
        test = " ".join(cur+[w])
        if d.textlength(test, font=font) <= max_width:
            cur.append(w)
        else:
            lines.append(" ".join(cur)); cur = [w]
    if cur: lines.append(" ".join(cur))
    return lines[:3]

def build_images_for_items(titles, out_dir, prefix="news"):
    paths = []
    for i, t in enumerate(titles, 1):
        img = _bg()
        d = ImageDraw.Draw(img)
        try:
            f_big = ImageFont.truetype(FONT, size=58)
            f_tag = ImageFont.truetype(FONT, size=40)
            f_water = ImageFont.truetype(FONT, size=160)
        except OSError as exc:
            logger.warning("Failed to load font '%s': %s", FONT, exc)
            f_big = f_tag = f_water = ImageFont.load_default()

        # büyük "NEWS" watermark
        d.text((40, 220), "NEWS", font=f_water, fill=(255,255,255,20))

        # üst bar
        d.rectangle([0,0,W,140], fill=(0,0,0,120))
        d.text((40, 45), "DAILY NEWS", font=f_tag, fill=(235,235,240))

        # başlık metin
        lines = _wrap(t, f_big, max_width=W-160)
        y = 340
        for ln in lines:
            w = d.textlength(ln, font=f_big)
            d.text(((W-w)//2, y), ln, font=f_big, fill=(255,255,255))
            y += 80

        p = out_dir / f"{prefix}-{i}.png"
        img.save(p, "PNG", optimize=True)
        paths.append(str(p))
    return paths
