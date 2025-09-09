import subprocess, tempfile, os
from typing import List
from pydub import AudioSegment

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Env ayarları
BG_ZOOM_PER_SEC = float(os.getenv("BG_ZOOM_PER_SEC", "0.0006"))
XFADE_SEC       = float(os.getenv("XFADE_SEC", "0.6"))
TICKER_SPEED    = float(os.getenv("TICKER_SPEED", "120"))
TICKER_H        = int(os.getenv("TICKER_H", "120"))

def _dur_sec(mp3_path):
    audio = AudioSegment.from_file(mp3_path)
    return max(8, round(len(audio) / 1000))  # en az 8 sn

def _wrap_lines(text: str, max_len: int = 48) -> str:
    words = text.split()
    lines, line = [], []
    for w in words:
        if sum(len(x) for x in line) + len(line) + len(w) <= max_len:
            line.append(w)
        else:
            lines.append(" ".join(line))
            line = [w]
    if line:
        lines.append(" ".join(line))
    return "\n".join(lines[:3])  # en fazla 3 satır

def _make_slide(image_path: str, caption: str, duration: float, out_path: str,
                theme: str = "news", ticker_text: str | None = None):
    """
    Dinamik arka plan: blur + yavaş zoom (zoompan).
    Ön plan: 9:16 kırpılmış net görsel.
    Üstte yarı saydam başlık bar + (news ise) BREAKING NEWS etiketi.
    Altta (news ise) kayan ticker.
    """
    wrapped = _wrap_lines(caption or "", max_len=48)
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tf:
        tf.write(wrapped)
        textfile_path = tf.name

    ticker_file = None
    has_ticker = theme == "news" and (ticker_text or "").strip() != ""
    if has_ticker:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tt:
            tt.write(ticker_text.strip())
            ticker_file = tt.name

    # Filtre zinciri
    vf_parts = [
        "split=2[bgsrc][fgsrc]",
        f"[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,boxblur=20:1,"
        f"zoompan=z='if(lte(on,1),1.0,zoom+{BG_ZOOM_PER_SEC})':d=1:s=1080x1920[bg]",
        "[fgsrc]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[fg]",
        "[bg][fg]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,",
        # üst başlık bar + caption
        "drawbox=x=0:y=60:w=iw:h=160:color=black@0.35:t=fill",
        f",drawtext=fontfile='{FONT}':textfile='{textfile_path}':"
        "fontcolor=white:fontsize=48:line_spacing=8:borderw=2:bordercolor=black@0.6:"
        "text_shaping=1:x=(w-text_w)/2:y=90"
    ]

    if theme == "news":
        # sol üst kırmızı BREAKING NEWS etiketi
        vf_parts.append(
            f",drawtext=fontfile='{FONT}':text='BREAKING NEWS':"
            "fontcolor=white:fontsize=40:box=1:boxcolor=red@0.85:boxborderw=20:x=40:y=30"
        )

    if has_ticker and ticker_file:
        # altta ticker bandı + kayan yazı
        vf_parts.append(
            f",drawbox=x=0:y=main_h-{TICKER_H}:w=iw:h={TICKER_H}:color=black@0.55:t=fill"
            f",drawtext=fontfile='{FONT}':textfile='{ticker_file}':"
            f"fontcolor=white:fontsize=42:line_spacing=0:borderw=0:"
            f"x=w-mod(t*{TICKER_SPEED}, (text_w+w)):y=main_h-{TICKER_H}+{(TICKER_H-42)//2}"
        )

    vf = "".join(vf_parts)

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

def _xfade_and_add_audio(slide_paths: List[str], audio_path: str, out_path: str, seg: float):
    """
    Tüm slayt videolarını (sessiz) al, aralarına xfade ile yumuşak geçiş ekle,
    sonra MP3 sesi bindir.
    """
    if len(slide_paths) == 1:
        # tek slayt: sadece sesi ekle
        cmd = [
            "ffmpeg", "-y",
            "-i", slide_paths[0],
            "-i", audio_path,
            "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            out_path
        ]
        subprocess.run(cmd, check=True)
        return

    # Çoklu giriş
    cmd = ["ffmpeg", "-y"]
    for p in slide_paths:
        cmd += ["-i", p]
    cmd += ["-i", audio
