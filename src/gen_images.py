import os, io, requests, random
from typing import List
from PIL import Image, ImageDraw, ImageFilter

HF_MODEL = "black-forest-labs/FLUX.1-schnell"  # hızlı, ücretsiz inference noktası genelde açık olur
HF_ENDPOINT = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

def _ai_image_for_title(title: str, token: str) -> bytes | None:
    try:
        headers = {"Authorization": f"Bearer {token}"}
        prompt = (
            f"High-quality vertical 9:16 illustration for a Turkish news headline:\n"
            f"'{title}'. Cinematic lighting, photo-realistic, dramatic, trending on artstation."
        )
        resp = requests.post(HF_ENDPOINT, headers=headers, json={"inputs": prompt}, timeout=60)
        if resp.ok and resp.content and resp.headers.get("content-type","").startswith("image/"):
            return resp.content
        return None
    except Exception:
        return None

def _placeholder_image(title: str, w=1080, h=1920) -> bytes:
    # Basit degrade + blur + overlay; metni videoda drawtext ile basacağız
    img = Image.new("RGB", (w, h), (10, 10, 20))
    draw = ImageDraw.Draw(img)
    # Degrade
    for y in range(h):
        c = int(20 + 80 * (y / h))
        draw.line([(0, y), (w, y)], fill=(c, c, c))
    img = img.filter(ImageFilter.GaussianBlur(radius=6))
    # Hafif vinyet
    vign = Image.new("L", (w, h), 0)
    dv = ImageDraw.Draw(vign)
    dv.ellipse([int(-0.2*w), int(-0.2*h), int(1.2*w), int(1.2*h)], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(200))
    img.putalpha(vign)
    bg = Image.new("RGB", (w, h), (12, 12, 16))
    bg.paste(img, (0,0), img)
    buf = io.BytesIO()
    bg.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

def build_images_for_items(titles: List[str], out_dir, prefix="ai") -> List[str]:
    out_paths = []
    token = os.getenv("HF_TOKEN")

    for i, t in enumerate(titles, 1):
        data = None
        if token:
            data = _ai_image_for_title(t, token)
        if not data:
            data = _placeholder_image(t)

        path = out_dir / f"{prefix}-{i}.png"
        with open(path, "wb") as f:
            f.write(data)
        out_paths.append(str(path))
    return out_paths
