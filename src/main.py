# -*- coding: utf-8 -*-
from __future__ import annotations
import importlib, os, json, sys, time, subprocess
from pathlib import Path
from typing import Optional, List, Any

def _load_local_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:
        print(f"[import warning] {name} import edilemedi: {exc}", flush=True)
        return None

_scriptgen = _load_local_module("src.scriptgen") or _load_local_module("scriptgen")
_tts       = _load_local_module("src.tts")       or _load_local_module("tts")
_video     = _load_local_module("src.video")     or _load_local_module("video")
_uploader  = _load_local_module("src.youtube_upload") or _load_local_module("youtube_upload")

generate_script       = getattr(_scriptgen, "generate_script", None)
build_titles          = getattr(_scriptgen, "build_titles", None)
synth_tts_to_mp3      = getattr(_tts, "synth_tts_to_mp3", None)
make_slideshow_video  = getattr(_video, "make_slideshow_video", None)
try_upload_youtube    = getattr(_uploader, "upload_video", None) or getattr(_uploader, "try_upload_youtube", None)

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _env_bool(name: str, default: bool=False) -> bool:
    v = _env(name)
    return default if v is None else str(v).strip().lower() in {"1","true","yes","on"}

def _ts(fmt: str = "%Y%m%d-%H%M%S") -> str:
    return time.strftime(fmt, time.gmtime())

def _append_error(msg: str) -> None:
    Path("out").mkdir(parents=True, exist_ok=True)
    with open("out/error.log", "a", encoding="utf-8") as f:
        f.write(msg.rstrip() + "\n")

def _ffmpeg_silence_mp3(out_mp3: str, seconds: int = 45) -> None:
    cmd = [
        "ffmpeg","-y","-f","lavfi","-i","anullsrc=r=44100:cl=mono",
        "-t", str(seconds), "-acodec","libmp3lame","-q:a","9", out_mp3
    ]
    subprocess.run(cmd, check=True)

def main() -> None:
    Path("out").mkdir(parents=True, exist_ok=True)

    theme   = (_env("THEME","story") or "story").lower()
    lang    = _env("LANGUAGE","en") or "en"
    region  = _env("REGION","US") or "US"
    rss_url = _env("RSS_URL", None)
    story_topic = _env("STORY_TOPIC", None)

    print(">> Generating script...", flush=True)
    try:
        script, captions, coins_data = generate_script(theme, language=lang, region=region, rss_url=rss_url, story_topic=story_topic)
    except Exception as e:
        _append_error(f"[script warning] {e}")
        script = "A daily episode."
        captions = ["Daily episode"]
        coins_data = None
    print("SCRIPT:\n", script, flush=True)

    print(">> Building SEO metadata...", flush=True)
    try:
        meta = build_titles(theme, captions=captions, coins_data=coins_data, title_prefix=_env("VIDEO_TITLE_PREFIX"))
        title, description = meta.title or "Auto Episode", meta.description or ""
        tags = meta.tags or []
    except Exception as e:
        _append_error(f"[title warning] {e}")
        title, description, tags = "Auto Episode", "", []
    print("TITLE:", title, flush=True)

    # TTS settings — slower + gap for longer runtime
    voice   = _env("TTS_VOICE","alloy") or "alloy"
    atempo  = _env("TTS_ATEMPO","0.95") or "0.95"
    gap_ms  = _env("TTS_GAP_MS","300") or "300"
    bitrate = _env("TTS_BITRATE","128k") or "128k"

    ts = _ts()
    mp3_path = f"out/voice-{ts}.mp3"
    mp4_path = f"out/video-{ts}.mp4"

    print(">> TTS...", flush=True)
    try:
        if callable(synth_tts_to_mp3) and (_env("OPENAI_API_KEY") or "").strip():
            synth_tts_to_mp3(script, mp3_path, voice=voice, atempo=atempo, gap_ms=gap_ms, bitrate=bitrate)
        else:
            raise RuntimeError("TTS unavailable")
    except Exception as e:
        _append_error(f"[tts warning] {e}")
        _ffmpeg_silence_mp3(mp3_path, seconds=60)
        print(">> Silent MP3 fallback.", flush=True)

    print(">> Render video...", flush=True)
    try:
        make_slideshow_video(images=[], captions=captions, audio_mp3=mp3_path, out_mp4=mp4_path, theme=theme, ticker_text=None)
    except Exception as e:
        _append_error(f"[render warning] {e}")
        # last-chance: solid color + audio
        subprocess.run([
            "ffmpeg","-y","-f","lavfi","-i","color=c=black:s=1080x1920:d=9999",
            "-i", mp3_path, "-c:v","libx264","-pix_fmt","yuv420p",
            "-shortest","-movflags","+faststart", mp4_path
        ], check=True)

    print(f">> Done: {mp4_path}", flush=True)

    print(">> Upload (if creds)...", flush=True)
    try:
        if callable(try_upload_youtube) and _env("YT_CLIENT_ID") and _env("YT_CLIENT_SECRET") and _env("YT_REFRESH_TOKEN"):
            # Prefer YT_TAGS env override; else use SEO tags
            env_tags = [t.strip() for t in (_env("YT_TAGS","") or "").split(",") if t.strip()]
            tag_list = env_tags or tags
            url = try_upload_youtube(
                video_path=mp4_path,
                title=title,
                description=description,
                privacy_status=(_env("YT_PRIVACY","public") or "public"),
                category_id="22",
                tags=tag_list
            )
            if url: print(">> Uploaded:", url, flush=True)
        else:
            print(">> Upload skipped (missing creds).", flush=True)
    except Exception as e:
        _append_error(f"[upload warning] {e}")
        print(f"[upload warning] {e}", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _append_error(f"[fatal] {e}")
        sys.exit(0)
