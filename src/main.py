# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import sys
import time
import traceback
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List, Any

# Projendeki modüller
from scriptgen import generate_script, build_titles
from tts import synth_tts_to_mp3

# Opsiyonel modüller (yoksa graceful degradation)
try:
    from video import make_slideshow_video  # type: ignore
except Exception:
    make_slideshow_video = None

try:
    from youtube_upload import try_upload_youtube  # type: ignore
except Exception:
    try_upload_youtube = None


# ---------- Yardımcılar ----------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Boş stringleri de 'yok' sayarak environment değişkeni oku."""
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _ts(fmt: str = "%Y%m%d-%H%M%S") -> str:
    """UTC zaman damgası."""
    return time.strftime(fmt, time.gmtime())

def _fallback_black_video(image_w: int, image_h: int, audio_mp3: str, out_mp4: str) -> None:
    """Görsel pipeline çökerse: siyah arka plan + ses ile MP4 üret (dikey 1080x1920)."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={image_w}x{image_h}:d=9999",
        "-i", audio_mp3,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        out_mp4
    ]
    subprocess.run(cmd, check=True)

def _safe_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return [str(i) for i in x]
    return [str(x)]


# ---------- Ana Akış ----------

def main() -> None:
    # Çıktı klasörü
    Path("out").mkdir(parents=True, exist_ok=True)

    # Parametreler
    theme   = (_env("THEME", "crypto") or "crypto").lower()        # story / crypto / sports / news
    lang    = _env("LANGUAGE", "en") or "en"
    region  = _env("REGION", "US") or "US"
    rss_url = _env("RSS_URL", None)
    story_topic = _env("STORY_TOPIC", None)  # story modu için opsiyonel konu

    # Script üretimi
    print(">> Generating script...", flush=True)
    script, captions, coins_data = generate_script(
        mode=theme,
        language=lang,
        region=region,
        rss_url=rss_url,
        story_topic=story_topic,
    )

    # Tip/boşluk korumaları
    if not isinstance(script, str):
        script = str(script) if script is not None else " "
    captions = _safe_list(captions)

    print("SCRIPT:\n", script, flush=True)

    # Başlık & açıklama
    title_prefix = _env("VIDEO_TITLE_PREFIX", {
        "crypto": "Daily Crypto Brief:",
        "sports": "Sports Brief:",
        "news":   "Daily Brief:",
        "story":  "Story:",
    }.get(theme, "Daily Brief:"))
    title, description = build_titles(
        theme,
        captions=captions,
        coins_data=coins_data,
        title_prefix=title_prefix
    )

    # TTS parametreleri
    voice    = _env("TTS_VOICE", "alloy") or "alloy"
    atempo   = _env("TTS_ATEMPO", "1.05") or "1.05"
    gap_ms   = _env("TTS_GAP_MS", "10") or "10"          # tts.py bu parametreyi destekliyorsa
    bitrate  = _env("TTS_BITRATE", "128k") or "128k"

    mp3_path = f"out/voice-{_ts()}.mp3"
    mp4_path = f"out/video-{_ts()}.mp4"

    # TTS
    print(">> TTS...", flush=True)
    synth_tts_to_mp3(
        text=script,
        out_mp3=mp3_path,
        voice=voice,
        atempo=atempo,
        gap_ms=gap_ms,
        bitrate=bitrate,
    )

    # Video render
    print(">> Render video...", flush=True)
    rendered = False
    try:
        if make_slideshow_video is not None:
            # Not: Görsel listeyi boş geçiriyoruz; video.py boş listeyi handle etmeli.
            make_slideshow_video(
                images=[],                 # dış görsel çekmiyorsan boş kalsın
                captions=captions,         # altyazı/sahne metinleri
                audio_mp3=mp3_path,
                out_mp4=mp4_path,
                theme=theme,
                ticker_text=None
            )
            rendered = True
    except Exception as e:
        print(f"[render warning] slideshow failed, fallback to black bg. Reason: {e}", flush=True)

    if not rendered:
        # Dikey shorts boyutu
        _fallback_black_video(1080, 1920, mp3_path, mp4_path)

    print(f">> Done: {mp4_path}", flush=True)

    # YouTube yükleme (isteğe bağlı; kimlik yoksa atlar)
    print(">> Trying YouTube upload (if creds exist)...", flush=True)
    try:
        if try_upload_youtube is not None:
            privacy = _env("YT_PRIVACY", "public") or "public"
            url = try_upload_youtube(
                mp4_path,
                title=title,
                description=description,
                privacy_status=privacy
            )
            if url:
                print(">> Uploaded:", url, flush=True)
            else:
                print(">> Upload skipped or failed (no URL).", flush=True)
        else:
            print(">> Uploader not found; skipping.", flush=True)
    except Exception as e:
        print(f"[upload warning] {e}", flush=True)


# ---------- Giriş Noktası ----------

if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Hata olursa hem ekrana hem dosyaya ayrıntılı traceback yaz
        with open("out/error.log", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        traceback.print_exc()
        sys.exit(1)