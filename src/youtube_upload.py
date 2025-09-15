# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, time, traceback, subprocess
from pathlib import Path
from typing import Optional, List, Any

# Emniyetli import
def _safe_import(name: str):
    try:
        return __import__(name)
    except Exception as e:
        print(f"[import warning] {name} import edilemedi: {e}", flush=True)
        return None

_scriptgen = _safe_import("scriptgen")
_tts       = _safe_import("tts")
_video     = _safe_import("video")
_uploader  = _safe_import("youtube_upload")

generate_script       = getattr(_scriptgen, "generate_script", None)
build_titles          = getattr(_scriptgen, "build_titles", None)
synth_tts_to_mp3      = getattr(_tts, "synth_tts_to_mp3", None)
make_slideshow_video  = getattr(_video, "make_slideshow_video", None)
try_upload_youtube    = getattr(_uploader, "try_upload_youtube", None)

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _ts(fmt: str = "%Y%m%d-%H%M%S") -> str:
    return time.strftime(fmt, time.gmtime())

def _safe_list(x: Any) -> List[str]:
    if x is None: return []
    if isinstance(x, (list, tuple)): return [str(i) for i in x]
    return [str(x)]

def _append_error(msg: str) -> None:
    Path("out").mkdir(parents=True, exist_ok=True)
    with open("out/error.log", "a", encoding="utf-8") as f:
        f.write(msg.rstrip() + "\n")

def _ffmpeg_silence_mp3(out_mp3: str, seconds: int = 30) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(seconds),
        "-acodec", "libmp3lame", "-q:a", "9",
        out_mp3
    ]
    subprocess.run(cmd, check=True)

def _fallback_black_video(image_w: int, image_h: int, audio_mp3: str, out_mp4: str) -> None:
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

def main() -> None:
    Path("out").mkdir(parents=True, exist_ok=True)

    theme   = (_env("THEME", "crypto") or "crypto").lower()
    lang    = _env("LANGUAGE", "en") or "en"
    region  = _env("REGION", "US") or "US"
    rss_url = _env("RSS_URL")
    story_topic = _env("STORY_TOPIC")

    # 1) Script
    print(">> Generating script...", flush=True)
    script = ""
    captions: List[str] = []
    coins_data = None
    try:
        if callable(generate_script):
            s, c, coins_data = generate_script(mode=theme, language=lang, region=region,
                                               rss_url=rss_url, story_topic=story_topic)
            script = s if isinstance(s, str) else str(s or "")
            captions = _safe_list(c)
        else:
            raise RuntimeError("generate_script yok")
    except Exception as e:
        _append_error(f"[script warning] {e}")
        if lang == "tr":
            script = "Bugün gizemli bir hikaye: Beklenmedik bir buluşma, şehir ışıkları altında başlar..."
            captions = ["Gizemli bir mektup...", "Gece yarısı sokakları", "Eski bir dost", "Sır perdesi aralanıyor"]
        else:
            script = "A short mysterious tale: Under the city lights, an unexpected meeting unfolds..."
            captions = ["A strange letter", "Midnight streets", "An old friend", "The secret revealed"]
    print("SCRIPT:\n", script, flush=True)

    # 2) Başlık & açıklama
    try:
        title_prefix = _env("VIDEO_TITLE_PREFIX", {
            "crypto": "Daily Crypto Brief:",
            "sports": "Sports Brief:",
            "news":   "Daily Brief:",
            "story":  "Story:",
        }.get(theme, "Daily Brief:"))
        if callable(build_titles):
            title, description = build_titles(theme, captions=captions, coins_data=coins_data, title_prefix=title_prefix)
        else:
            raise RuntimeError("build_titles yok")
    except Exception as e:
        _append_error(f"[title warning] {e}")
        if lang == "tr":
            title, description = f"{title_prefix} Kısa Gizemli Hikaye", "Otomatik üretilmiştir."
        else:
            title, description = f"{title_prefix} Short Mystery Story", "Auto-generated."
    print("TITLE:", title, flush=True)

    # 3) TTS (fallback sessiz)
    voice   = _env("TTS_VOICE", "alloy") or "alloy"
    atempo  = _env("TTS_ATEMPO", "1.05") or "1.05"
    gap_ms  = _env("TTS_GAP_MS", "10") or "10"
    bitrate = _env("TTS_BITRATE", "128k") or "128k"

    mp3_path = f"out/voice-{_ts()}.mp3"
    mp4_path = f"out/video-{_ts()}.mp4"

    print(">> TTS...", flush=True)
    try:
        if callable(synth_tts_to_mp3) and (_env("OPENAI_API_KEY") or "").strip():
            synth_tts_to_mp3(text=script, out_mp3=mp3_path,
                             voice=voice, atempo=atempo, gap_ms=gap_ms, bitrate=bitrate)
        else:
            raise RuntimeError("TTS kullanılamıyor (anahtar yok ya da modül yok)")
    except Exception as e:
        _append_error(f"[tts warning] {e}")
        _ffmpeg_silence_mp3(mp3_path, seconds=30)
        print(">> Sessiz MP3 ile devam.", flush=True)

    # 4) Render (fallback siyah)
    print(">> Render video...", flush=True)
    rendered = False
    try:
        if callable(make_slideshow_video):
            make_slideshow_video(images=[], captions=captions, audio_mp3=mp3_path,
                                 out_mp4=mp4_path, theme=theme, ticker_text=None)
            rendered = True
        else:
            raise RuntimeError("make_slideshow_video yok")
    except Exception as e:
        _append_error(f"[render warning] {e}")

    if not rendered:
        _fallback_black_video(1080, 1920, mp3_path, mp4_path)

    print(f">> Done: {mp4_path}", flush=True)

    # 5) YouTube (opsiyonel)
    print(">> Trying YouTube upload (if creds exist)...", flush=True)
    try:
        if callable(try_upload_youtube) and _env("YT_CLIENT_ID") and _env("YT_CLIENT_SECRET") and _env("YT_REFRESH_TOKEN"):
            privacy = _env("YT_PRIVACY", "unlisted") or "unlisted"
            url = try_upload_youtube(mp4_path, title=title, description=description, privacy_status=privacy)
            if url:
                print(">> Uploaded:", url, flush=True)
            else:
                _append_error("[upload warning] uploader returned no URL")
                print(">> Upload skipped or failed (no URL).", flush=True)
        else:
            print(">> Uploader not configured; skipping.", flush=True)
    except Exception as e:
        _append_error(f"[upload warning] {e}")
        print(f"[upload warning] {e}", flush=True)

    return

if __name__ == "__main__":
    try:
        main()
    except Exception:
        Path("out").mkdir(parents=True, exist_ok=True)
        with open("out/error.log", "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        traceback.print_exc()
        sys.exit(0)  # düşürme
