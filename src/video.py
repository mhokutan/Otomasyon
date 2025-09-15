# -*- coding: utf-8 -*-
from __future__ import annotations
import os, random, time, urllib.request, urllib.parse, tempfile, subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def _env(name: str, default: str) -> str:
    v = os.getenv(name); return v if (v is not None and str(v).strip()!="") else default

def _ffprobe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",path],
            check=True, capture_output=True, text=True
        ).stdout.strip()
        d = float(out); return d if d>0 else 60.0
    except Exception:
        return 60.0

# ---------- theme colors ----------
def _theme_colors(theme: str) -> Tuple[Tuple[int,int,int], Tuple[int,int,int], Tuple[int,int,int]]:
    t = (theme or "story").lower()
    if t == "crypto":  return (6,18,14), (0,140,90), (0,200,130)
    if t in ("sports","news"): return (8,14,30), (20,90,180), (0,140,255)
    if t == "story":  return (14,10,20), (60,0,90), (160,30,200)
    return (18,18,28), (120,0,0), (220,40,40)

def _fallback_bg(theme: str) -> Image.Image:
    c1,c2,c3 = _theme_colors(theme)
    img = Image.new("RGB",(W,H), c1); drw=ImageDraw.Draw(img)
    for y in range(H):
        r=y/(H-1)
        col=(int(c1[0]*(1-r)+c2[0]*r), int(c1[1]*(1-r)+c2[1]*r), int(c1[2]*(1-r)+c2[2]*r))
        drw.line([(0,y),(W,y)], fill=col)
    spot=Image.new("RGB",(W,H),c3); mask=Image.new("L",(W,H),0); mdr=ImageDraw.Draw(mask)
    mdr.ellipse([(-W*0.1,-H*0.2),(W*1.1,H*0.8)], fill=160)
    mask=mask.filter(ImageFilter.GaussianBlur(180))
    img=Image.composite(spot,img,mask)
    return img

# ---------- image sources ----------
def _picsum_urls(count: int) -> List[str]:
    ts=int(time.time()); return [f"https://picsum.photos/{W}/{H}?random={ts+i+random.randint(0,99999)}" for i in range(count)]

def _unsplash_urls(queries: List[str], count: int) -> List[str]:
    # source.unsplash.com is keyless and supports queries
    # Build URLs like: https://source.unsplash.com/1080x1920/?fog,forest,night
    urls=[]
    if not queries:
        return urls
    base=f"https://source.unsplash.com/{W}x{H}/?{{q}}"
    # randomly sample combinations
    pool=queries[:]
    random.shuffle(pool)
    while len(urls)<count:
        k = min(3, max(1, random.randint(1,3)))
        terms = random.sample(pool, k=min(k, len(pool)))
        q = urllib.parse.quote(",".join(terms))
        urls.append(base.replace("{q}", q))
    return urls[:count]

def _download_url(url: str) -> Optional[str]:
    try:
        fd, tmp = tempfile.mkstemp(suffix=".jpg"); os.close(fd)
        urllib.request.urlretrieve(url, tmp); return tmp
    except Exception:
        return None

def _fit_cover(img: Image.Image, w=W, h=H) -> Image.Image:
    iw,ih = img.size
    if iw==0 or ih==0: return img.resize((w,h))
    scale=max(w/iw, h/ih); nw,nh=int(iw*scale), int(ih*scale)
    img2=img.resize((nw,nh), Image.LANCZOS)
    x=(nw-w)//2; y=(nh-h)//2
    return img2.crop((x,y,x+w,y+h))

# ---------- text helpers ----------
def _wrap_lines(drw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words=(text or "").split()
    if not words: return [""]
    lines,cur=[], ""
    for w in words:
        t=w if not cur else f"{cur} {w}"
        bbox=drw.textbbox((0,0), t, font=font, stroke_width=2)
        if (bbox[2]-bbox[0])<=max_w: cur=t
        else:
            if cur: lines.append(cur)
            cur=w
    if cur: lines.append(cur)
    return lines

# ---------- presenter ----------
def _load_presenter_avatar(size: int) -> Optional[Image.Image]:
    url=_env("PRESENTER_URL","")
    try:
        if url.startswith("http"): p=_download_url(url)
        elif url and os.path.exists(url): p=url
        else: p=None
        if not p:
            avatar=Image.new("RGBA",(size,size),(30,30,30,255))
            m=Image.new("L",(size,size),0); ImageDraw.Draw(m).ellipse((0,0,size-1,size-1), fill=255)
            avatar.putalpha(m); dr=ImageDraw.Draw(avatar)
            try: fnt=ImageFont.truetype(FONT_BOLD, size//2)
            except: fnt=ImageFont.load_default()
            txt=_env("PRESENTER_INITIALS","AI"); bb=dr.textbbox((0,0), txt, font=fnt)
            dr.text(((size-(bb[2]-bb[0]))//2,(size-(bb[3]-bb[1]))//2), txt, font=fnt, fill=(255,255,255,255))
            return avatar
        img=Image.open(p).convert("RGBA").resize((size,size), Image.LANCZOS)
        mask=Image.new("L",(size,size),0); ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1), fill=255)
        shadow=Image.new("RGBA",(size+20,size+20),(0,0,0,0)); sd=ImageDraw.Draw(shadow)
        sd.ellipse((10,10,size+10,size+10), fill=(0,0,0,140)); shadow=shadow.filter(ImageFilter.GaussianBlur(8))
        base=Image.new("RGBA",(size+20,size+20),(0,0,0,0)); base.alpha_composite(shadow,(0,0))
        circle=Image.new("RGBA",(size,size),(0,0,0,0)); circle.paste(img,(0,0), mask)
        base.alpha_composite(circle,(10,10)); return base
    except Exception:
        return None

def _place_presenter(canvas: Image.Image, avatar: Image.Image, pos: str):
    if avatar is None: return
    aw,ah=avatar.size; m=40; ticker_h=int(_env("TICKER_H","120"))
    if pos=="bottom-left":  xy=(m, H-ticker_h-ah-m)
    elif pos=="bottom-right": xy=(W-aw-m, H-ticker_h-ah-m)
    elif pos=="top-right":    xy=(W-aw-m, 220)
    else:                     xy=(m, 220)
    canvas.alpha_composite(avatar, xy)

# ---------- compose ----------
def _compose_caption(bg: Image.Image, caption: str, theme: str, blink_variant: int=0) -> Image.Image:
    img=bg.convert("RGBA")
    topbar_h=160; topbar=Image.new("RGBA",(W,topbar_h),(0,0,0,int(0.35*255))); img.alpha_composite(topbar,(0,60))
    ticker_h=int(_env("TICKER_H","120")); bottombar=Image.new("RGBA",(W,ticker_h),(0,0,0,int(0.55*255)))
    img.alpha_composite(bottombar,(0,H-ticker_h))
    if _env("BREAKING_ON","0") in ("1","true","True","yes"):
        text=_env("BREAKING_TEXT","BREAKING")
        try: bf=ImageFont.truetype(FONT_BOLD,42)
        except: bf=ImageFont.load_default()
        draw=ImageDraw.Draw(img); bb=draw.textbbox((0,0), text, font=bf); tw,th=bb[2]-bb[0], bb[3]-bb[1]
        padx,pady=28,16; alpha=220 if (blink_variant%2==0) else 180
        box=Image.new("RGBA",(tw+padx*2, th+pady*2),(255,49,49,alpha)); box=box.filter(ImageFilter.GaussianBlur(0.5))
        img.alpha_composite(box,(40,30)); draw.text((40+padx,30+pady), text, font=bf, fill=(255,255,255,255))
    try: title_font=ImageFont.truetype(FONT_BOLD,50)
    except: title_font=ImageFont.load_default()
    draw=ImageDraw.Draw(img); lines=_wrap_lines(draw, caption, title_font, W-120); y=90
    for line in lines:
        bb=draw.textbbox((0,0), line, font=title_font, stroke_width=3); tw,th=bb[2]-bb[0], bb[3]-bb[1]
        x=(W-tw)//2
        draw.text((x,y), line, font=title_font, fill=(255,255,255,255),
                  stroke_width=3, stroke_fill=(50,0,70,190))
        y+=th+10
    size=int(_env("PRESENTER_SIZE","240")); pos=_env("PRESENTER_POS","top-right")
    avatar=_load_presenter_avatar(size)
    if avatar: _place_presenter(img, avatar, pos)
    return img.convert("RGB")

# ---------- encode helpers ----------
def _png_to_video(png: str, duration: float, out_mp4: str, fps: int=60):
    cmd=["ffmpeg","-y","-loop","1","-t",f"{max(0.5,duration):.2f}","-i",png,
         "-vf", f"scale={W}:{H},format=yuv420p","-r", str(fps),
         "-c:v","libx264","-preset","veryfast","-crf", _env("CRF","22"),
         "-pix_fmt","yuv420p","-an","-movflags","+faststart", out_mp4]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def _concat(parts: list[str], out_mp4: str):
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        for p in parts: f.write(f"file '{p}'\n")
        lst=f.name
    cmd=["ffmpeg","-y","-f","concat","-safe","0","-i", lst,"-c","copy", out_mp4]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def _mux(video_mp4: str, audio_mp3: str, out_mp4: str, bitrate="128k"):
    cmd=["ffmpeg","-y","-i",video_mp4,"-i",audio_mp3,"-map","0:v:0","-map","1:a:0",
         "-c:v","libx264","-preset","veryfast","-crf", _env("CRF","22"),
         "-pix_fmt","yuv420p","-c:a","aac","-b:a", bitrate,"-shortest","-movflags","+faststart", out_mp4]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# ---------- main ----------
def make_slideshow_video(images: List[str], captions: List[str], audio_mp3: str, out_mp4: str,
                         theme: str="story", ticker_text: str|None=None,
                         keywords: Optional[List[str]]=None, genre: Optional[str]=None) -> None:
    """
    Arka planı hikâyeye göre seçer:
      - BG_QUERY_MODE=unsplash => query tabanlı (anahtar kelime + ambiyans)
      - BG_QUERY_MODE=picsum   => rastgele (fallback)
    """
    Path("out").mkdir(parents=True, exist_ok=True)
    if not captions: captions=["Short story"]

    total=_ffprobe_duration(audio_mp3)
    lens=[max(1,len(c)) for c in captions]; total_weight=float(sum(lens)) or 1.0
    min_per=3.0; raw=[max(min_per, total*(ln/total_weight)) for ln in lens]
    scale=total/max(1e-6,sum(raw)); slide_durations=[max(2.5, r*scale) for r in raw]
    slide_durations[-1]=max(2.0, total - sum(slide_durations[:-1]))

    fps=int(_env("FPS","60"))
    bgs_per_slide=max(1, min(10, int(_env("BG_IMAGES_PER_SLIDE","6"))))
    mode=_env("BG_QUERY_MODE","unsplash").lower()

    # keywords -> query list
    queries = (keywords or [])
    # tür bazlı birkaç varsayılan query ekle
    g = (genre or "").lower()
    default_map = {
        "tarihsel gizem":"ancient ruins,old library,parchment,castle,candlelight",
        "esrarengiz":"foggy forest,abandoned building,night alley,shadows",
        "çözülmemiş korku":"abandoned hospital,dark corridor,moonlight,creepy forest",
        "paranormal":"haunted house,ghost,cemetery,old church,gothic",
        "şehir efsanesi":"city night,alley,neon,subway,tunnel",
        "historical mystery":"ancient ruins,old manuscript,archive,castle",
        "unsolved horror":"abandoned hospital,dark woods,moody night",
        "urban legend":"city alley,neon,underground tunnel",
        "paranormal tale":"haunted house,ghost,cemetery"
    }
    defaults = []
    for k,v in default_map.items():
        if k in g:
            defaults = [x.strip() for x in v.split(",") if x.strip()]
            break
    # queries + defaults + atmosferik ekler
    base_queries = list(dict.fromkeys((queries or []) + defaults + ["night","fog","moody","shadow","mystery"]))
    if not base_queries: base_queries = ["mystery","night","fog","shadow","forest"]

    slide_mp4s=[]
    for i,(cap, sdur) in enumerate(zip(captions, slide_durations), start=1):
        if mode=="unsplash":
            urls = _unsplash_urls(base_queries, bgs_per_slide)
        else:
            urls = _picsum_urls(bgs_per_slide)

        parts_for_slide=[]
        per_dur=max(1.3, sdur/bgs_per_slide)
        for j, url in enumerate(urls, start=1):
            f=_download_url(url)
            if f:
                try: img=Image.open(f).convert("RGB")
                except: img=_fallback_bg(theme)
            else:
                img=_fallback_bg(theme)
            img=_fit_cover(img,W,H).filter(ImageFilter.GaussianBlur(0.6))
            frame=_compose_caption(img, cap, theme, blink_variant=j)
            out_png=Path("out")/f"slide_{i:02d}_{j:02d}.png"; frame.save(out_png.as_posix(),"PNG", optimize=True)
            part_mp4=f"/tmp/slide_{i}_{j}.mp4"; _png_to_video(out_png.as_posix(), per_dur, part_mp4, fps=fps)
            parts_for_slide.append(part_mp4)

        slide_body=f"/tmp/slide_body_{i}.mp4"; _concat(parts_for_slide, slide_body)
        slide_mp4s.append(slide_body)

    body="/tmp/body.mp4"; _concat(slide_mp4s, body)
    _mux(body, audio_mp3, out_mp4, bitrate=_env("TTS_BITRATE","128k"))
    print(f"[video] DONE -> {out_mp4}")
