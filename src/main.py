# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import time
import subprocess
from pathlib import Path

from scriptgen import generate_script, build_titles
from tts import synth_tts_to_mp3

try:
    from video import make_slideshow_video
except Exception:
    make_slideshow_video = None

try:
    from youtube_upload import try_upload_youtube
except Exception:
    try_upload_youtube = None


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _ts(fmt: str = "%Y%m%d-%H%M%S") -> str:
    return time.strftime(fmt, time.gmtime())

def _fallback_black_video(image_w: int, image_h: int, audio_mp3: str, out_mp4: str) -> None:
    """Görsel pipeline çökerse: siyah arka plan + ses ile MP4 üret."""
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

def main():
    Path("out").mkdir(parents=True, exist_ok=True)

    theme   = (_env("THEME", "crypto") or "crypto").lower()
    lang    = _env("LANGUAGE", "en")
    region  = _env("REGION", "US")
    rss_url = _env("RSS_URL", None)
    story_topic = _env("STORY_TOPIC", None)  # story modu kullanırsan

    print(">> Generating script...", flush=True)
    script, captions, coins_data = generate_script(
        mode=theme,
        language=lang,
        region=region,
        rss_url=rss_url,
        story_topic=story_topic,   # scriptgen yok sayarsa sorun değil
    )
    print("SCRIPT:\n", script if isinstance(script, str) else str(script), flush=True)

    title_prefix = _env("VIDEO_TITLE_PREFIX", {
        "crypto": "Daily Crypto Brief:",
        "sports": "Sports Brief:",
        "news":   "Daily Brief:",
        "story":  "Story:"
    }.get(theme, "Daily Brief:"))
    title, description = build_titles(theme, captions=captions, coins_data=coins_data, title_prefix=title_prefix)

    voice    = _env("TTS_VOICE", "alloy")
    atempo   = _env("TTS_ATEMPO", "1.05")
    gap_ms   = _env("TTS_GAP_MS", "10")   # tts.py destekli
    bitrate  = _env("TTS_BITRATE", "128k")

    mp3_path = f"out/voice-{_ts()}.mp3"
    mp4_path = f"out/video-{_ts()}.mp4"

    print(">> TTS...", flush=True)
    synth_tts_to_mp3(
        text=script,
        out_mp3=mp3_path,
        voice=voice,
        atempo=atempo,
        gap_ms=gap_ms,
        bitrate=bitrate,
    )

    print(">> Render video...", flush=True)
    rendered = False
    try:
        if make_slideshow_video is not None:
            make_slideshow_video([], captions, mp3_path, mp4_path, theme=theme, ticker_text=None)
            rendered = True
    except Exception as e:
        print(f"[render warning] slideshow failed, fallback black bg. Reason: {e}", flush=True)

    if not rendered:
        _fallback_black_video(1080, 1920, mp3_path, mp4_path)

    print(f">> Done: {mp4_path}", flush=True)

    # YouTube upload
    print(">> Trying YouTube upload (if creds exist)...", flush=True)
    try:
        if try_upload_youtube is not None:
            privacy = _env("YT_PRIVACY", "public")
            url = try_upload_youtube(mp4_path, title=title, description=description, privacy_status=privacy)
            if url:
                print(">> Uploaded:", url, flush=True)
            else:
                print(">> Upload skipped or failed (no URL).", flush=True)
        else:
            print(">> Uploader not found; skipping.", flush=True)
    except Exception as e:
        print(f"[upload warning] {e}", flush=True)

if __name__ == "__main__":
    main()