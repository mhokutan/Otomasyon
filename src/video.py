# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _ffprobe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",path],
            check=True, capture_output=True, text=True
        ).stdout.strip()
        d = float(out)
        return d if d > 0 else 60.0
    except Exception:
        return 60.0

def _theme_colors(theme: str) -> Tuple[Tuple[int,int,int], Tuple[int,int,int], Tuple[int,int,int]]:
    t = (theme or "news").lower()
    if t == "crypto":
        return (6,18,14), (0,140,90), (0,200,130)     # koyu -> yeşil -> neon
    if t == "sports":
        return (8,14,30), (20,90,180), (0,140,255)    # koyu lacivert -> mavi -> canlı mavi
    return (18,18,28), (120,0,0), (220,40,40)         # news: koyu -> bordo -> kırmızı

def _make_bg(theme: str) -> Image.Image:
    c1, c2, c3 = _theme_colors(theme)
    img = Image.new("RGB", (W,H), c1)
    drw = ImageDraw.Draw(img)

    # Dikey yumuşak degrade (c1 -> c2)
    for y in range(H):
        r = y/(H-1)
        col = (
            int(c1[0]*(1-r)+c2[0]*r),
            int(c1[1]*(1-r)+c2[1]*r),
            int(c1[2]*(1-r)+c2[2]*r),
        )
        drw.line([(0,y),(W,y)], fill=col)

    # Üstten spot ışığı (c3 ile)
    spot = Image.new("RGB", (W,H), c3)
    mask = Image.new("L", (W,H), 0)
    mdr = ImageDraw.Draw(mask)
    mdr.ellipse([(-W*0.1,-H*0.2),(W*1.1,H*0.8)], fill=180)
    mask = mask.filter(ImageFilter.GaussianBlur(180))
    img = Image.composite(spot, img, mask)  # c3 parıltı verir

    # Hafif diyagonal çizgiler (kontrast için)
    overlay = Image.new("RGBA", (W,H), (0,0,0,0))
    od = ImageDraw.Draw(overlay)
    step = 42
    for x in range(-H, W, step):
        od.line([(x,0),(x+H,H)], fill=(255,255,255,18), width=2)
    overlay = overlay.filter(ImageFilter.GaussianBlur(1.2))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    return img

def _wrap_lines(drw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        t = w if not cur else f"{cur} {w}"
        bbox = drw.textbbox((0,0), t, font=font, stroke_width=2)
        if (bbox[2]-bbox[0]) <= max_w:
            cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def _slide_png_from_caption(text: str, theme: str, idx: int) -> str:
    img = _make_bg(theme).convert("RGBA")
    drw = ImageDraw.Draw(img)

    # Üst şerit
    bar_h = 160
    topbar = Image.new("RGBA", (W, bar_h), (0,0,0, int(0.35*255)))
    img.alpha_composite(topbar, (0,60))

    # Alt ticker şeridi
    ticker_h = int(_env("TICKER_H","120"))
    bottombar = Image.new("RGBA", (W, ticker_h), (0,0,0, int(0.55*255)))
    img.alpha_composite(bottombar, (0, H - ticker_h))

    # Başlık metni
    try:
        title_font = ImageFont.truetype(FONT_BOLD, 50)
    except Exception:
        title_font = ImageFont.load_default()

    inner_w = W - 120
    lines = _wrap_lines(drw, text, title_font, inner_w)
    y = 90
    for line in lines:
        bbox = drw.textbbox((0,0), line, font=title_font, stroke_width=2)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        x = (W - tw)//2
        drw.text((x, y), line, font=title_font, fill=(255,255,255,255),
                 stroke_width=3, stroke_fill=(0,0,0,190))
        y += th + 10

    out_dir = Path("out"); out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / f"slide_{idx:02d}.png"
    img.convert("RGB").save(out_png.as_posix(), "PNG", optimize=True)
    print(f"[slide] PNG written -> {out_png}")
    return out_png.as_posix()

def _png_to_video(png: str, duration: float, out_mp4: str, fps: int=60):
    # Basit & sağlam: sadece ölçek + yuv420p
    cmd = [
        "ffmpeg","-y",
        "-loop","1","-t",f"{max(0.5,duration):.2f}",
        "-i", png,
        "-vf", f"scale={W}:{H},format=yuv420p",
        "-r", str(fps),
        "-c:v","libx264","-preset","veryfast","-crf", _env("CRF","22"),
        "-pix_fmt","yuv420p","-an","-movflags","+faststart",
        out_mp4
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"[part] MP4 written -> {out_mp4} ({duration:.2f}s)")

def _concat(parts: list[str], out_mp4: str):
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
        lst = f.name
    cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i", lst,"-c","copy", out_mp4]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"[concat] -> {out_mp4}")

def _mux(video_mp4: str, audio_mp3: str, out_mp4: str, bitrate="128k"):
    cmd = [
        "ffmpeg","-y",
        "-i", video_mp4, "-i", audio_mp3,
        "-c:v","copy","-c:a","aac","-b:a", bitrate,
        "-shortest","-movflags","+faststart", out_mp4
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"[mux] A+V -> {out_mp4}")

def make_slideshow_video(images: List[str], captions: List[str], audio_mp3: str, out_mp4: str,
                         theme: str="news", ticker_text: str|None=None) -> None:
    """
    Her zaman kendi slayt PNG'lerini üretir; images parametresi kullanılmaz.
    """
    Path("out").mkdir(parents=True, exist_ok=True)

    if not captions:
        captions = ["60-second brief"]

    total = _ffprobe_duration(audio_mp3)
    # Basit süre paylaştırması (min 3s)
    lens = [max(1, len(c)) for c in captions]
    total_weight = float(sum(lens)) or 1.0
    min_per = 3.0
    raw = [max(min_per, total * (ln/total_weight)) for ln in lens]
    scale = total / max(1e-6, sum(raw))
    durations = [max(2.5, r*scale) for r in raw]
    durations[-1] = max(2.0, total - sum(durations[:-1]))

    fps = int(_env("FPS","60"))
    parts = []
    for i, (cap, dur) in enumerate(zip(captions, durations), start=1):
        png = _slide_png_from_caption(cap, theme, i)
        part = f"/tmp/slide_{i}.mp4"
        _png_to_video(png, dur, part, fps=fps)
        parts.append(part)

    body = "/tmp/body.mp4"
    _concat(parts, body)
    _mux(body, audio_mp3, out_mp4, bitrate=_env("TTS_BITRATE","128k"))
    print(f"[video] DONE -> {out_mp4}")