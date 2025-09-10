import subprocess, tempfile, os
from typing import List
from pydub import AudioSegment

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG_ZOOM_PER_SEC = float(os.getenv("BG_ZOOM_PER_SEC", "0.0006"))
XFADE_SEC       = float(os.getenv("XFADE_SEC", "0.6"))
TICKER_SPEED    = float(os.getenv("TICKER_SPEED", "120"))
TICKER_H        = int(os.getenv("TICKER_H", "120"))

def _dur_sec(mp3_path):
    audio = AudioSegment.from_file(mp3_path)
    return max(8, round(len(audio) / 1000))

def _wrap_lines(text: str, max_len: int = 48) -> str:
    words = text.split()
    lines, line = [], []
    for w in words:
        if sum(len(x) for x in line) + len(line) + len(w) <= max_len:
            line.append(w)
        else:
            lines.append(" ".join(line)); line = [w]
    if line: lines.append(" ".join(line))
    return "\n".join(lines[:3])

def _make_slide(image_path: str, caption: str, duration: float, out_path: str,
                theme: str = "news", ticker_text: str | None = None):
    wrapped = _wrap_lines(caption or "", max_len=48)
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tf:
        tf.write(wrapped)
        textfile_path = tf.name

    ticker_file = None
    has_ticker = (theme == "news") and (ticker_text or "").strip() != ""
    if has_ticker:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tt:
            tt.write(ticker_text.strip())
            ticker_file = tt.name

    # ---- FFMPEG FILTERGRAPH ----
    # Etiketli dallar (split -> [bgsrc] ve [fgsrc]) yeni zincir başlatır -> ';' gerekir
    base_chains = [
        "split=2[bgsrc][fgsrc]",
        f"[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,boxblur=20:1,"
        f"zoompan=z='if(lte(on,1),1.0,zoom+{BG_ZOOM_PER_SEC})':d=1:s=1080x1920[bg]",
        "[fgsrc]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[fg]",
        "[bg][fg]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2"
    ]
    tail_ops = [
        "drawbox=x=0:y=60:w=iw:h=160:color=black@0.35:t=fill",
        f"drawtext=fontfile='{FONT}':textfile='{textfile_path}':"
        "fontcolor=white:fontsize=48:line_spacing=8:borderw=2:bordercolor=black@0.6:"
        "text_shaping=1:x=(w-text_w)/2:y=90"
    ]
    if theme == "news":
        tail_ops.append(
            "drawtext=fontfile='{font}':text='BREAKING NEWS':"
            "fontcolor=white:fontsize=40:box=1:boxcolor=red@0.85:boxborderw=20:x=40:y=30".format(font=FONT)
        )
    if has_ticker and ticker_file:
        tail_ops.append(
            f"drawbox=x=0:y=main_h-{TICKER_H}:w=iw:h={TICKER_H}:color=black@0.55:t=fill"
        )
        tail_ops.append(
            f"drawtext=fontfile='{FONT}':textfile='{ticker_file}':"
            f"fontcolor=white:fontsize=42:line_spacing=0:borderw=0:"
            f"x=w-mod(t*{TICKER_SPEED}, (text_w+w)):y=main_h-{TICKER_H}+{(TICKER_H-42)//2}"
        )

    # Zincirleri ';' ile birleştir, overlay sonrası efektleri aynı zincirde ',' ile ekle
    vf = ";".join(base_chains) + "," + ",".join(tail_ops)

    try:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", f"{duration:.2f}", "-i", image_path,
            "-vf", vf,
            "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart",
            out_path
        ]
        subprocess.run(cmd, check=True)
    finally:
        try: os.unlink(textfile_path)
        except Exception: pass
        if ticker_file:
            try: os.unlink(ticker_file)
            except Exception: pass

def _xfade_video(slide_paths: List[str], out_path: str, seg: float):
    n = len(slide_paths)
    if n == 1:
        cmd = [
            "ffmpeg", "-y", "-i", slide_paths[0],
            "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart",
            out_path
        ]
        subprocess.run(cmd, check=True)
        return

    cmd = ["ffmpeg", "-y"]
    for p in slide_paths:
        cmd += ["-i", p]

    # Zincir: [0:v][1:v] -> [v1] ; [v1][2:v] -> [v2] ; ... -> [vout]
    filters = []
    prev = "[0:v]"
    for i in range(1, n):
        cur = f"[{i}:v]"
        out = f"[v{i}]"
        offset = i * (seg - XFADE_SEC)
        filters.append(f"{prev}{cur}xfade=transition=fade:duration={XFADE_SEC}:offset={offset}{out}")
        prev = out
    filters.append(f"{prev}format=yuv420p[vout]")

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]",
        "-r", "30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-movflags", "+faststart",
        out_path
    ]
    subprocess.run(cmd, check=True)

def _mux_audio(video_in: str, audio_mp3: str, out_path: str):
    cmd = [
        "ffmpeg", "-y",
        "-i", video_in,
        "-i", audio_mp3,
        "-shortest",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        out_path
    ]
    subprocess.run(cmd, check=True)

def _overlay_waveform(in_mp4: str, out_mp4: str, has_ticker: bool):
    bottom_margin = 40 + (TICKER_H if has_ticker else 0)
    overlay_y = f"main_h-200-{bottom_margin}"
    cmd = [
        "ffmpeg", "-y",
        "-i", in_mp4,
        "-filter_complex",
        f"[0:a]showwaves=s=1080x200:mode=cline:rate=30[wf];"
        f"[0:v][wf]overlay=0:{overlay_y},format=yuv420p",
        "-map", "0:v", "-map", "0:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "copy",
        "-movflags", "+faststart",
        out_mp4
    ]
    subprocess.run(cmd, check=True)

def make_slideshow_video(images: List[str], captions: List[str], audio_mp3: str, out_mp4: str,
                         theme: str = "news", ticker_text: str | None = None):
    total = _dur_sec(audio_mp3)
    n = max(1, len(images))
    seg = max(6, total / n)

    slide_paths = []
    for idx, img in enumerate(images):
        slide_mp4 = f"/tmp/slide_{idx+1}.mp4"
        cap = captions[idx] if idx < len(captions) else ""
        _make_slide(img, cap, seg, slide_mp4, theme=theme, ticker_text=ticker_text)
        slide_paths.append(slide_mp4)

    temp_xfade = "/tmp/xfaded.mp4"
    _xfade_video(slide_paths, temp_xfade, seg)

    temp_with_audio = "/tmp/with_audio.mp4"
    _mux_audio(temp_xfade, audio_mp3, temp_with_audio)

    has_ticker = (theme == "news") and (ticker_text or "").strip() != ""
    _overlay_waveform(temp_with_audio, out_mp4, has_ticker)
