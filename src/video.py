# -*- coding: utf-8 -*-
from __future__ import annotations
import os, random, time, tempfile, subprocess, re, socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Tuple, Iterable, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import urllib.request

W, H = 1080, 1920
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

# ---- Ağ ve işlem zaman aşımları ----
NET_TIMEOUT = float(_env("NET_TIMEOUT", "8"))       # saniye (tek indirme)
FFMPEG_TIMEOUT = int(float(_env("FFMPEG_TIMEOUT", "240")))  # saniye (tek ffmpeg çağrısı)
MAX_BG_SIZE_MB = float(_env("MAX_BG_SIZE_MB", "6")) # tek görsel üst sınır
USE_UNSPLASH = _env("USE_UNSPLASH", "0").lower() in ("1","true","yes")

socket.setdefaulttimeout(NET_TIMEOUT)

def _ffprobe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",path],
            check=True, capture_output=True, text=True, timeout=30
        ).stdout.strip()
        d = float(out)
        return d if d > 0 else 60.0
    except Exception:
        return 60.0

# ---------------- Tema renkleri ----------------
def _theme_colors(theme: str) -> Tuple[Tuple[int,int,int], Tuple[int,int,int], Tuple[int,int,int]]:
    t = (theme or "news").lower()
    if t == "crypto":
        return (6,18,14), (0,140,90), (0,200,130)
    if t == "sports":
        return (8,14,30), (20,90,180), (0,140,255)
    return (18,18,28), (120,0,0), (220,40,40)

def _fallback_bg(theme: str, variant: int = 0) -> Image.Image:
    c1, c2, c3 = _theme_colors(theme)
    jitter = (variant % 5) * 8
    c1 = tuple(max(0, min(255, x + (-1)**variant * jitter)) for x in c1)
    c2 = tuple(max(0, min(255, x + jitter//2)) for x in c2)
    c3 = tuple(max(0, min(255, x + jitter)) for x in c3)

    img = Image.new("RGB", (W,H), c1)
    drw = ImageDraw.Draw(img)
    for y in range(H):
        r = y/(H-1)
        col = (
            int(c1[0]*(1-r)+c2[0]*r),
            int(c1[1]*(1-r)+c2[1]*r),
            int(c1[2]*(1-r)+c2[2]*r),
        )
        drw.line([(0,y),(W,y)], fill=col)
    spot = Image.new("RGB", (W,H), c3)
    mask = Image.new("L", (W,H), 0)
    mdr  = ImageDraw.Draw(mask)
    mdr.ellipse([(-W*0.1,-H*0.2),(W*1.1,H*0.8)], fill=180)
    mask = mask.filter(ImageFilter.GaussianBlur(180))
    img  = Image.composite(spot, img, mask)
    px = img.load()
    for _ in range(8000):
        x = random.randint(0, W-1); y = random.randint(0, H-1)
        r,g,b = px[x,y]; dd = random.randint(-10,10)
        px[x,y] = (max(0,min(255,r+dd)), max(0,min(255,g+dd)), max(0,min(255,b+dd)))
    return img.filter(ImageFilter.GaussianBlur(1.0))

# --------------- Görseller (picsum/unsplash) ---------------
def _sanitize_kw(tokens: Iterable[str]) -> List[str]:
    out = []
    for t in tokens:
        t = t.strip().lower()
        if not t: continue
        t = re.sub(r"[^a-z0-9çğıöşü\s\-]", "", t)
        if len(t) < 3: continue
        out.append(t)
    return out[:5]

_GENRE_MAP = {
    "history": ["history","library","manuscript","ruins","antique","parchment"],
    "mystery": ["mystery","fog","alley","shadow","noir","secret"],
    "horror":  ["horror","abandoned","dark","forest","eerie","gothic"],
    "crime":   ["crime","detective","evidence","police","casefile"],
    "war":     ["war","battlefield","trench","archive","vintage"],
    "fantasy": ["fantasy","castle","ancient","myth","dragon"],
    "space":   ["space","stars","nebula","cosmos","telescope"],
    "nature":  ["nature","forest","mountain","river","mist"],
    "city":    ["city","street","night","architecture","old town"],
    "tarih":   ["tarih","kütüphane","el yazması","arkeoloji","eser"],
    "gizem":   ["gizem","sis","sokak","gölge","sır"],
    "korku":   ["korku","terkedilmiş","karanlık","orman","gotik"],
    "suç":     ["suç","dedektif","delil","polis","dosya"],
    "savaş":   ["savaş","cephe","arşiv","tarihî belge"],
    "doğa":    ["doğa","orman","dağ","nehir","sis"],
    "şehir":   ["şehir","sokak","gece","mimari","eski şehir"],
}

def _picsum_urls(count: int) -> List[str]:
    ts = int(time.time())
    return [f"https://picsum.photos/{W}/{H}?random={ts+i+random.randint(0,99999)}" for i in range(count)]

def _unsplash_urls(count: int, keywords: List[str]) -> List[str]:
    if not USE_UNSPLASH:
        return []
    ts = int(time.time())
    urls = []
    for i in range(count):
        q = ",".join(random.sample(keywords, k=min(2, len(keywords)))) if keywords else "abstract"
        urls.append(f"https://source.unsplash.com/random/{W}x{H}/?{q}&sig={ts+i}")
    return urls

def _bg_urls_for_theme(theme: str, count: int, keywords=None, genre: str | None = None) -> List[str]:
    kw_list: List[str] = []
    if isinstance(keywords, str) and keywords.strip():
        kw_list = _sanitize_kw(re.split(r"[,\s]+", keywords))
    elif isinstance(keywords, (list, tuple)):
        kw_list = _sanitize_kw([str(x) for x in keywords])
    if not kw_list and genre:
        g = genre.strip().lower()
        for key, vals in _GENRE_MAP.items():
            if key in g:
                kw_list = vals[:]
                break
    if not kw_list:
        t = (theme or "").lower()
        if t == "crypto":
            kw_list = ["crypto","blockchain","finance","charts","market"]
        elif t == "sports":
            kw_list = ["sports","stadium","crowd","arena","action"]
        else:
            kw_list = ["history","library","manuscript","mystery","city"]

    # kaynak karışımı
    picsum = _picsum_urls(count)
    unspl  = _unsplash_urls(count, kw_list)
    urls = picsum + unspl
    random.shuffle(urls)
    return urls[:max(1, count)]

def _download_url(url: str) -> str | None:
    tmp_path: str | None = None
    try:
        # Manuel indirme + timeout + boyut sınırı
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=NET_TIMEOUT) as r:
            cap = int(MAX_BG_SIZE_MB*1024*1024)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                tmp_path = tmp_file.name
                total = 0
                while True:
                    chunk = r.read(64*1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > cap:
                        raise RuntimeError("image too large")
                    tmp_file.write(chunk)
        return tmp_path
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        print(f"[img] skip {url} ({e})")
        return None

def _download_many(urls: List[str]) -> List[Optional[str]]:
    if not urls:
        return []
    try:
        max_workers = int(_env("IMG_DL_WORKERS", "4") or "4")
    except Exception:
        max_workers = 4
    max_workers = max(1, min(len(urls), max_workers))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(_download_url, urls))

def _fit_cover(img: Image.Image, w=W, h=H) -> Image.Image:
    iw, ih = img.size
    if iw == 0 or ih == 0:
        return img.resize((w,h))
    scale = max(w/iw, h/ih)
    nw, nh = int(iw*scale), int(ih*scale)
    img2 = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - w)//2
    y = (nh - h)//2
    return img2.crop((x, y, x+w, y+h))

# --------------- Metin yardımcıları ---------------
def _wrap_lines(drw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = (text or "").split()
    if not words: return [""]
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

# --------------- Spiker avatar ---------------
def _load_presenter_avatar(size: int) -> Image.Image | None:
    url = _env("PRESENTER_URL", "")
    try:
        if url.startswith("http"):
            p = _download_url(url)
        elif url and os.path.exists(url):
            p = url
        else:
            p = None
        if not p:
            avatar = Image.new("RGBA", (size, size), (30,30,30,255))
            m = Image.new("L", (size, size), 0)
            ImageDraw.Draw(m).ellipse((0,0,size-1,size-1), fill=255)
            avatar.putalpha(m)
            dr = ImageDraw.Draw(avatar)
            try:
                fnt = ImageFont.truetype(FONT_BOLD, size//2)
            except Exception:
                fnt = ImageFont.load_default()
            txt = _env("PRESENTER_INITIALS","AI")
            bb = dr.textbbox((0,0), txt, font=fnt)
            dr.text(((size-(bb[2]-bb[0]))//2, (size-(bb[3]-bb[1]))//2),
                    txt, font=fnt, fill=(255,255,255,255))
            return avatar
        img = Image.open(p).convert("RGBA").resize((size,size), Image.LANCZOS)
        mask = Image.new("L", (size,size), 0)
        ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1), fill=255)
        shadow = Image.new("RGBA", (size+20,size+20), (0,0,0,0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse((10,10,size+10,size+10), fill=(0,0,0,140))
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))
        base = Image.new("RGBA", (size+20,size+20), (0,0,0,0))
        base.alpha_composite(shadow,(0,0))
        circle = Image.new("RGBA", (size,size), (0,0,0,0))
        circle.paste(img, (0,0), mask)
        base.alpha_composite(circle, (10,10))
        return base
    except Exception:
        return None

def _place_presenter(canvas: Image.Image, avatar: Image.Image, pos: str):
    if avatar is None:
        return
    aw, ah = avatar.size
    m = 40
    ticker_h = int(_env("TICKER_H","120"))
    if pos == "bottom-left":
        xy = (m, H - ticker_h - ah - m)
    elif pos == "bottom-right":
        xy = (W - aw - m, H - ticker_h - ah - m)
    elif pos == "top-right":
        xy = (W - aw - m, 220)
    else:
        xy = (m, 220)
    canvas.alpha_composite(avatar, xy)

# --------------- Kompozit: caption + banner + spiker ---------------
def _compose_caption(
    bg: Image.Image,
    caption: str,
    theme: str,
    blink_variant: int=0,
    avatar: Image.Image | None = None,
) -> Image.Image:
    img = bg.convert("RGBA")

    topbar_h = 160
    topbar = Image.new("RGBA", (W, topbar_h), (0,0,0, int(0.35*255)))
    img.alpha_composite(topbar, (0,60))

    ticker_h = int(_env("TICKER_H","120"))
    bottombar = Image.new("RGBA", (W, ticker_h), (0,0,0, int(0.55*255)))
    img.alpha_composite(bottombar, (0, H - ticker_h))

    if _env("BREAKING_ON","0").lower() in ("1","true","yes"):
        text = _env("BREAKING_TEXT","BREAKING NEWS")
        try:
            bf = ImageFont.truetype(FONT_BOLD, 42)
        except Exception:
            bf = ImageFont.load_default()
        draw = ImageDraw.Draw(img)
        bb = draw.textbbox((0,0), text, font=bf)
        tw, th = bb[2]-bb[0], bb[3]-bb[1]
        padx, pady = 28, 16
        alpha = 220 if (blink_variant % 2 == 0) else 180
        box = Image.new("RGBA", (tw+padx*2, th+pady*2), (255,49,49, alpha))
        box = box.filter(ImageFilter.GaussianBlur(0.5))
        img.alpha_composite(box, (40, 30))
        draw.text((40+padx, 30+pady), text, font=bf, fill=(255,255,255,255))

    try:
        title_font = ImageFont.truetype(FONT_BOLD, 50)
    except Exception:
        title_font = ImageFont.load_default()
    draw = ImageDraw.Draw(img)

    def _wrap(drw, text, font, max_w):
        words = (text or "").split()
        if not words: return [""]
        lines, cur = [], ""
        for w in words:
            t = w if not cur else f"{cur} {w}"
            bbox = drw.textbbox((0,0), t, font=font, stroke_width=3)
            if (bbox[2]-bbox[0]) <= max_w:
                cur = t
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines[:3]

    lines = _wrap(draw, caption or "", title_font, W-120)
    y = 90
    for line in lines:
        bb = draw.textbbox((0,0), line, font=title_font, stroke_width=3)
        tw, th = bb[2]-bb[0], bb[3]-bb[1]
        x = (W - tw)//2
        draw.text((x, y), line, font=title_font, fill=(255,255,255,255),
                  stroke_width=3, stroke_fill=(0,0,0,190))
        y += th + 10

    size = int(_env("PRESENTER_SIZE","260"))
    pos  = _env("PRESENTER_POS","top-right")
    presenter = avatar if avatar is not None else _load_presenter_avatar(size)
    if presenter:
        _place_presenter(img, presenter, pos)

    return img.convert("RGB")

# --------------- PNG -> MP4 / concat / mux ---------------
def _run_ffmpeg(cmd: list[str]):
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=FFMPEG_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg timeout")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed: {e}")

def _png_to_video(png: str, duration: float, out_mp4: str, fps: int=60, zoom_per_sec: float=0.0018):
    d_frames = max(1, int(fps * max(0.5, duration)))
    zpf = max(0.0, float(zoom_per_sec)) / float(fps)

    filter_complex = (
        f"scale={W}:{H},"
        f"zoompan=z='if(lte(on,1),1.0,zoom+{zpf:.6f})':d={d_frames}:s={W}x{H},"
        f"fps={fps}"
    )

    cmd = [
        "ffmpeg","-y",
        "-loop","1","-t",f"{max(0.5,duration):.2f}",
        "-i", png,
        "-filter_complex", filter_complex,
        "-c:v","libx264","-preset","veryfast","-crf", _env("CRF","22"),
        "-pix_fmt","yuv420p","-an","-movflags","+faststart",
        out_mp4
    ]
    try:
        _run_ffmpeg(cmd)
    except Exception as e:
        print(f"[ffmpeg warn] zoompan fallback ({e})")
        cmd2 = [
            "ffmpeg","-y",
            "-loop","1","-t",f"{max(0.5,duration):.2f}",
            "-i", png,
            "-vf", f"scale={W}:{H},format=yuv420p",
            "-r", str(fps),
            "-c:v","libx264","-preset","veryfast","-crf", _env("CRF","22"),
            "-pix_fmt","yuv420p","-an","-movflags","+faststart",
            out_mp4
        ]
        _run_ffmpeg(cmd2)

def _concat(parts: list[str], out_mp4: str):
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
        lst = f.name
    cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i", lst,"-c","copy", out_mp4]
    _run_ffmpeg(cmd)

def _mux(video_mp4: str, audio_mp3: str, out_mp4: str, bitrate="128k"):
    cmd = [
        "ffmpeg","-y",
        "-i", video_mp4, "-i", audio_mp3,
        "-map","0:v:0","-map","1:a:0",
        "-c:v","libx264","-preset","veryfast","-crf", _env("CRF","22"),
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a", bitrate,
        "-shortest","-movflags","+faststart",
        out_mp4
    ]
    _run_ffmpeg(cmd)

# --------------- Ana ---------------
def make_slideshow_video(
    images: List[str],
    captions: List[str],
    audio_mp3: str,
    out_mp4: str,
    theme: str = "news",
    ticker_text: str | None = None,
    keywords: List[str] | str | None = None,
    genre: str | None = None,
    **_ignored,
) -> None:
    """
    captions -> süre paylaştır; her slaytta birden fazla arka plan (keywords/genre/tema ile);
    Ken-Burns efekti; slaytları concat; sesle mux. Ağ/FFmpeg takılmalarına karşı timeout ve fallback’ler var.
    """
    Path("out").mkdir(parents=True, exist_ok=True)
    if not captions:
        captions = ["60-second brief"]

    total = _ffprobe_duration(audio_mp3)

    lens = [max(1, len(c)) for c in captions]
    total_weight = float(sum(lens)) or 1.0
    min_per = 3.0
    raw = [max(min_per, total * (ln/total_weight)) for ln in lens]
    scale = total / max(1e-6, sum(raw))
    slide_durations = [max(2.5, r*scale) for r in raw]
    slide_durations[-1] = max(2.0, total - sum(slide_durations[:-1]))

    fps = int(_env("FPS","60"))
    bgs_per_slide = int(_env("BG_IMAGES_PER_SLIDE","4"))
    bgs_per_slide = max(1, min(10, bgs_per_slide))
    zoom_per_sec = float(_env("BG_ZOOM_PER_SEC","0.0018"))

    presenter_size = int(_env("PRESENTER_SIZE","260"))
    presenter_avatar = _load_presenter_avatar(presenter_size)

    slide_mp4s = []

    for i, (cap, sdur) in enumerate(zip(captions, slide_durations), start=1):
        urls = _bg_urls_for_theme(theme, bgs_per_slide, keywords=keywords, genre=genre)
        parts_for_slide = []
        per_dur = max(1.5, sdur / bgs_per_slide)

        downloaded = _download_many(urls)

        for j, (url, f) in enumerate(zip(urls, downloaded), start=1):
            if f:
                try:
                    with Image.open(f) as raw:
                        img = raw.convert("RGB")
                except Exception:
                    img = _fallback_bg(theme, variant=j)
                finally:
                    try:
                        os.remove(f)
                    except OSError:
                        pass
            else:
                img = _fallback_bg(theme, variant=j)

            img = _fit_cover(img, W, H).filter(ImageFilter.GaussianBlur(radius=0.6))
            frame = _compose_caption(img, cap, theme, blink_variant=j, avatar=presenter_avatar)

            out_png = Path("out") / f"slide_{i:02d}_{j:02d}.png"
            frame.save(out_png.as_posix(), "PNG", optimize=True)
            print(f"[slide] PNG -> {out_png}")

            part_mp4 = f"/tmp/slide_{i}_{j}.mp4"
            _png_to_video(out_png.as_posix(), per_dur, part_mp4, fps=fps, zoom_per_sec=zoom_per_sec)
            parts_for_slide.append(part_mp4)

        slide_body = f"/tmp/slide_body_{i}.mp4"
        try:
            _concat(parts_for_slide, slide_body)
            slide_mp4s.append(slide_body)
        finally:
            for part_mp4 in parts_for_slide:
                try:
                    os.remove(part_mp4)
                except OSError:
                    pass

    body = "/tmp/body.mp4"
    try:
        _concat(slide_mp4s, body)
    finally:
        for slide_body in slide_mp4s:
            try:
                os.remove(slide_body)
            except OSError:
                pass

    final_out = out_mp4
    _mux(body, audio_mp3, final_out, bitrate=_env("TTS_BITRATE","128k"))
    print(f"[video] DONE -> {final_out}")
