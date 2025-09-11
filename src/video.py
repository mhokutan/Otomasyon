# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import math
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter


W, H = 1080, 1920
FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _safe_env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v and str(v).strip() != "" else default


def _ffprobe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1",
                path
            ],
            check=True, capture_output=True, text=True
        ).stdout.strip()
        d = float(out)
        if d > 0:
            return d
    except Exception:
        pass
    return 60.0  # güvenli varsayılan


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    words = text.split()
    if not words:
        return [""]
    lines, line = [], ""
    for w in words:
        test = w if not line else f"{line} {w}"
        bbox = draw.textbbox((0, 0), test, font=font, stroke_width=2)
        if bbox[2] - bbox[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _theme_colors(theme: str) -> Tuple[Tuple[int,int,int], Tuple[int,int,int]]:
    t = (theme or "news").lower()
    if t == "crypto":
        # koyu yeşil -> neon yeşil
        return (8, 20, 16), (0, 130, 80)
    if t == "sports":
        # koyu lacivert -> canlı mavi
        return (10, 18, 40), (0, 120, 200)
    # news / default
    return (20, 20, 35), (130, 0, 0)


def _make_gradient_bg(theme: str) -> Image.Image:
    c1, c2 = _theme_colors(theme)
    img = Image.new("RGB", (W, H), c1)
    # dikey gradient
    for y in range(H):
        r = y / (H - 1)
        col = (
            int(c1[0] * (1 - r) + c2[0] * r),
            int(c1[1] * (1 - r) + c2[1] * r),
            int(c1[2] * (1 - r) + c2[2] * r),
        )
        ImageDraw.Draw(img).line([(0, y), (W, y)], fill=col)
    # hafif blur + vignette
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    vignette = Image.new("L", (W, H), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse([(-W*0.2, -H*0.1), (W*1.2, H*1.3)], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=200))
    img = Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), vignette.point(lambda p: 255 - p))
    return img


def _draw_caption_slide(text: str, theme: str, idx: int) -> str:
    img = _make_gradient_bg(theme).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # başlık şeridi (üst)
    bar_h = 160
    bar = Image.new("RGBA", (W, bar_h), (0, 0, 0, int(0.35 * 255)))
    img.alpha_composite(bar, (0, 60))

    # alt ticker şeridi (isteğe bağlı; şu an boş)
    ticker_h = int(_safe_env("TICKER_H", "120"))
    ticker_bar = Image.new("RGBA", (W, ticker_h), (0, 0, 0, int(0.55 * 255)))
    img.alpha_composite(ticker_bar, (0, H - ticker_h))

    # metni yaz
    title_font = ImageFont.truetype(FONT_PATH_BOLD, 48)
    inner_w = W - 80
    lines = _wrap_lines(draw, text, title_font, inner_w)
    y = 90  # bar üstünden biraz aşağı
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font, stroke_width=2)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (W - tw) // 2
        draw.text((x, y), line, font=title_font, fill=(255, 255, 255, 255),
                  stroke_width=2, stroke_fill=(0, 0, 0, 180))
        y += th + 8

    out_png = f"out/slide_{idx:02d}.png"
    Path("out").mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_png, "PNG", optimize=True)
    return out_png


def _png_to_mp4(png_path: str, duration: float, out_mp4: str, fps: int = 60) -> None:
    # Basit, her yerde çalışan bir filter: ölçekle + yuv420p
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", f"{duration:.2f}",
        "-i", png_path,
        "-vf", f"scale={W}:{H},format=yuv420p",
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", _safe_env("CRF", "22"),
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        out_mp4
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _concat_mp4(parts: List[str], out_mp4: str) -> None:
    # concat demuxer kullan
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
        list_path = f.name
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_path,
        "-c", "copy",
        out_mp4
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _mux_audio(video_mp4: str, audio_mp3: str, out_mp4: str, bitrate: str = "128k") -> None:
    cmd = [
        "ffmpeg", "-y",
        "-i", video_mp4,
        "-i", audio_mp3,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", bitrate,
        "-shortest",
        "-movflags", "+faststart",
        out_mp4
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def make_slideshow_video(images: List[str], captions: List[str], audio_mp3: str, out_mp4: str,
                         theme: str = "news", ticker_text: str | None = None) -> None:
    """
    images parametresini **görmezden gelir**; captions listesinden kendi slaytlarını üretir.
    Her slayt için PNG -> MP4; sonra concat; sonra ses ile mux.
    """
    Path("out").mkdir(parents=True, exist_ok=True)

    # Captions boşsa tek satırlık güvenli varsayılan
    if not captions:
        captions = ["60-second brief"]

    total_audio = _ffprobe_duration(audio_mp3)
    n = max(1, len(captions))

    # Metin uzunluğuna göre kabaca süre bölüştür (min 3 sn)
    lens = [max(1, len(c)) for c in captions]
    L = float(sum(lens))
    min_per = 3.0
    raw = [max(min_per, total_audio * (ln / L)) for ln in lens]
    # toplam ses süresine çok yaklaşsın:
    scale = total_audio / max(1e-6, sum(raw))
    durations = [max(2.5, r * scale) for r in raw]
    # son slaytı tam eşitle
    durations[-1] = max(2.5, total_audio - sum(durations[:-1]))

    fps = int(_safe_env("FPS", "60"))

    parts = []
    for i, (cap, dur) in enumerate(zip(captions, durations), 1):
        png = _draw_caption_slide(cap, theme, i)
        part_mp4 = f"/tmp/slide_{i}.mp4"
        _png_to_mp4(png, dur, part_mp4, fps=fps)
        parts.append(part_mp4)

    body = "/tmp/body.mp4"
    _concat_mp4(parts, body)

    _mux_audio(body, audio_mp3, out_mp4, bitrate=_safe_env("TTS_BITRATE", "128k"))

    print(f"[video] done -> {out_mp4}")
