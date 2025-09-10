# src/video.py
import os, subprocess, tempfile, textwrap, datetime, shutil

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _write_tmp_textfile(txt: str) -> str:
    # drawtext=textfile= ile kullanmak için geçici dosya
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.write(fd, txt.encode("utf-8"))
    os.close(fd)
    return path

def _ticker_text_block(t: str, repeat: int = 20) -> str:
    t = t.strip().replace("\n", " ").replace("\r", " ")
    if not t:
        t = "Stay informed • Subscribe • "
    return ("  •  ".join([t] * repeat)) + "     "

def _make_slide(
    img_path: str,
    caption: str,
    seg_dur: float,
    out_mp4: str,
    theme: str = "news",
    ticker_text: str | None = None,
    fps: int = 60,
    zoom_per_sec: float = 0.0018,
    ticker_h: int = 120,
    xfade_sec: float = 1.0,
):
    """
    Tek kareden (image) dikey 1080x1920 MP4 segment üretir.
    - Arka plan blur + hafif zoom
    - Üst “etiket” (BREAKING NEWS / CRYPTO BRIEF / SPORTS BRIEF)
    - Başlık (caption) ortada
    - Alt kayan yazı (opsiyonel)
    """

    # Tema etiketi
    theme_label = {
        "news": "BREAKING NEWS",
        "crypto": "CRYPTO BRIEF",
        "sports": "SPORTS BRIEF",
    }.get(theme, "DAILY BRIEF")

    cap_file = _write_tmp_textfile(caption)
    ticker_file = None
    if ticker_text:
        ticker_file = _write_tmp_textfile(_ticker_text_block(ticker_text, repeat=24))

    # drawtext/drawbox'ta 'h' ve 'w' kullanılır; overlay'de main_w/main_h.
    # Kayan yazı x= ifadesindeki virgülü kaçırıyoruz: \,
    parts = []

    # 1) split/scale/blur/zoom/crop ve overlay
    parts.append(
        "[0:v]split=2[bgsrc][fgsrc];"
        "[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,"
        f"boxblur=20:1,zoompan=z='if(lte(on,1),1.0,zoom+{zoom_per_sec})':d=1:s=1080x1920[bg];"
        "[fgsrc]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[fg];"
        "[bg][fg]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[base]"
    )

    # 2) Üst etiket + başlık kutusu
    parts.append(
        "[base]"
        f"drawtext=fontfile='{FONT_BOLD}':text='{theme_label}':fontcolor=white:fontsize=40:"
        "box=1:boxcolor=red@0.85:boxborderw=20:x=40:y=30,"
        "drawbox=x=0:y=60:w=iw:h=160:color=black@0.35:t=fill,"
        f"drawtext=fontfile='{FONT_BOLD}':textfile='{cap_file}':fontcolor=white:fontsize=48:"
        "line_spacing=8:borderw=2:bordercolor=black@0.6:text_shaping=1:"
        "x=(w-text_w)/2:y=90[base2]"
    )

    # 3) Alt ticker (opsiyonel)
    if ticker_file:
        parts.append(
            "[base2]"
            f"drawbox=x=0:y=h-{ticker_h}:w=iw:h={ticker_h}:color=black@0.55:t=fill,"
            f"drawtext=fontfile='{FONT_BOLD}':textfile='{ticker_file}':fontcolor=white:fontsize=42:"
            "line_spacing=0:borderw=0:"
            # virgülü kaçır: \,
            f"x=w-mod(t*180.0\\,(text_w+w)):y=h-{ticker_h}+39[vout]"
        )
        last_label = "[vout]"
    else:
        # Ticker yoksa doğrudan vout'a bağla
        parts.append("[base2]null[vout]")
        last_label = "[vout]"

    filter_complex = ";".join(parts)

    # ffmpeg komutu
    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-t", f"{seg_dur:.2f}",
        "-i", img_path,
        "-filter_complex", filter_complex,
        "-map", last_label,
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        out_mp4,
    ]
    subprocess.run(cmd, check=True)

def make_slideshow_video(
    images: list[str],
    captions: list[str],
    audio_mp3: str,
    out_mp4: str,
    theme: str = "news",
    ticker_text: str | None = None,
):
    """
    Birden çok slaytı ardışık render edip tek videoda birleştirir,
    ardından sesle mux eder.
    """
    assert images, "No images"
    assert len(images) == len(captions), "images vs captions mismatch"

    fps = int(os.getenv("FPS", "60"))
    zoom_per_sec = float(os.getenv("BG_ZOOM_PER_SEC", "0.0018"))
    ticker_h = int(os.getenv("TICKER_H", "120"))
    xfade_sec = float(os.getenv("XFADE_SEC", "1.0"))

    # Ses süresini ölç (segment sürelerini orantılı bölmek istersen burada mantık kurarsın)
    # Basit yaklaşım: her slayta eşit süre
    # Eğer toplam = N slayt ise audio süresini N'e böl.
    # Aksi halde sabit 9s kullan.
    try:
        # ffprobe ile süre
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_mp3],
            check=True, capture_output=True, text=True
        )
        total_audio = float(probe.stdout.strip())
    except Exception:
        total_audio = 27.0

    n = len(images)
    seg = max(6.0, total_audio / n)  # min 6s
    tmp_slides = []

    try:
        for i, (img, cap) in enumerate(zip(images, captions), start=1):
            slide_mp4 = f"/tmp/slide_{i}.mp4"
            _make_slide(
                img_path=img,
                caption=cap,
                seg_dur=seg,
                out_mp4=slide_mp4,
                theme=theme,
                ticker_text=ticker_text,
                fps=fps,
                zoom_per_sec=zoom_per_sec,
                ticker_h=ticker_h,
                xfade_sec=xfade_sec,
            )
            tmp_slides.append(slide_mp4)

        # Slaytları concat
        list_file = tempfile.mkstemp(suffix=".txt")[1]
        with open(list_file, "w", encoding="utf-8") as f:
            for p in tmp_slides:
                f.write(f"file '{p}'\n")

        concat_mp4 = "/tmp/concat.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", concat_mp4],
            check=True
        )

        # Video + ses mux
        os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", concat_mp4,
                "-i", audio_mp3,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                out_mp4,
            ],
            check=True
        )

    finally:
        # geçici dosyaları serbest bırak
        for p in tmp_slides:
            try:
                os.remove(p)
            except Exception:
                pass
