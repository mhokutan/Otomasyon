# -*- coding: utf-8 -*-
from __future__ import annotations
import os, time
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

def _env(n: str, d: str|None=None) -> str|None:
    v = os.getenv(n); return v if (v is not None and str(v).strip()!="") else d
def _ts(fmt="%Y%m%d-%H%M%S"): return time.strftime(fmt, time.gmtime())

def main():
    Path("out").mkdir(parents=True, exist_ok=True)
    theme   = (_env("THEME","story") or "story").lower()
    lang    = _env("LANGUAGE","tr")
    region  = _env("REGION","TR")
    rss_url = _env("RSS_URL", None)

    print(">> Generating script...")
    script, captions, meta = generate_script(mode=theme, language=lang, region=region, rss_url=rss_url)
    print("SCRIPT:\n", script)
    title, description = build_titles(theme, captions=captions)

    voice   = _env("TTS_VOICE","alloy")
    atempo  = _env("TTS_ATEMPO","1.03")
    gap_ms  = _env("TTS_GAP_MS","120")
    bitrate = _env("TTS_BITRATE","128k")

    mp3_path = f"out/voice-{_ts()}.mp3"
    mp4_path = f"out/video-{_ts()}.mp4"

    print(">> TTS...")
    synth_tts_to_mp3(text=script, out_mp3=mp3_path, voice=voice, atempo=atempo, gap_ms=gap_ms, bitrate=bitrate)

    print(">> Render video...")
    if make_slideshow_video is not None:
        kw = (meta or {}).get("keywords")
        gen = (meta or {}).get("genre")
        make_slideshow_video([], captions, mp3_path, mp4_path, theme=theme, ticker_text=None,
                             keywords=kw, genre=gen)
    else:
        import subprocess
        subprocess.run([
            "ffmpeg","-y",
            "-f","lavfi","-i","color=c=black:s=1080x1920:d=9999",
            "-i", mp3_path,
            "-c:v","libx264","-pix_fmt","yuv420p","-shortest","-movflags","+faststart",
            mp4_path
        ], check=True)

    print(">> Uploading to YouTube...")
    if try_upload_youtube is not None:
        url = try_upload_youtube(mp4_path, title=title, description=description,
                                 privacy_status=_env("YT_PRIVACY","public") or "public")
        print("Uploaded URL:", url or "(failed)")
    else:
        print("Uploader not available; skipping.")
    print("DONE:", mp4_path)

if __name__ == "__main__":
    main()
