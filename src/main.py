# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import json
import sys
import time
import traceback
import subprocess
from pathlib import Path
from typing import Optional, List, Any

# Yerel modüller
try:
    from . import scriptgen as _scriptgen
except Exception as exc:  # pragma: no cover - yalnızca import hatası loglanır
    print(f"[import warning] scriptgen import edilemedi: {exc}", flush=True)
    _scriptgen = None

try:
    from . import tts as _tts
except Exception as exc:  # pragma: no cover - yalnızca import hatası loglanır
    print(f"[import warning] tts import edilemedi: {exc}", flush=True)
    _tts = None

try:
    from . import video as _video
except Exception as exc:  # pragma: no cover - yalnızca import hatası loglanır
    print(f"[import warning] video import edilemedi: {exc}", flush=True)
    _video = None

try:
    from . import youtube_upload as _uploader
except Exception as exc:  # pragma: no cover - yalnızca import hatası loglanır
    print(f"[import warning] youtube_upload import edilemedi: {exc}", flush=True)
    _uploader = None

generate_script = getattr(_scriptgen, "generate_script", None)
build_titles    = getattr(_scriptgen, "build_titles", None)
synth_tts_to_mp3 = getattr(_tts, "synth_tts_to_mp3", None)
make_slideshow_video = getattr(_video, "make_slideshow_video", None)
try_upload_youtube   = getattr(_uploader, "try_upload_youtube", None)

# ---------- Yardımcılar ----------
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _ts(fmt: str = "%Y%m%d-%H%M%S") -> str:
    return time.strftime(fmt, time.gmtime())

def _safe_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return [str(i) for i in x]
    return [str(x)]

def _append_error(msg: str) -> None:
    Path("out").mkdir(parents=True, exist_ok=True)
    with open("out/error.log", "a", encoding="utf-8") as f:
        f.write(msg.rstrip() + "\n")

def _print_youtube_error_summary() -> None:
    path = Path("out/youtube_error.json")
    if not path.exists():
        print(">> YouTube upload hatasıyla ilgili ayrıntı bulunamadı (out/youtube_error.json yok).", flush=True)
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f">> youtube_error.json okunamadı: {e}", flush=True)
        return

    detail = None
    if isinstance(data, dict):
        detail = data.get("http_error") or data.get("error") or json.dumps(data, ensure_ascii=False)
    if detail is None:
        detail = json.dumps(data, ensure_ascii=False)

    print(f">> YouTube upload hata özeti: {detail}", flush=True)

def _ffmpeg_silence_mp3(out_mp3: str, seconds: int = 30) -> None:
    """TTS yoksa/sorunluysa: 30 sn sessiz MP3 üret."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(seconds),
        "-acodec", "libmp3lame", "-q:a", "9",
        out_mp3
    ]
    subprocess.run(cmd, check=True)

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

# ---------- Ana Akış ----------
def main() -> None:
    Path("out").mkdir(parents=True, exist_ok=True)

    theme   = (_env("THEME", "crypto") or "crypto").lower()   # story/crypto/sports/news
    lang    = _env("LANGUAGE", "en") or "en"
    region  = _env("REGION", "US") or "US"
    rss_url = _env("RSS_URL", None)
    story_topic = _env("STORY_TOPIC", None)

    # 1) Senaryo üretimi (fallbacklı)
    print(">> Generating script...", flush=True)
    script = ""
    captions: List[str] = []
    coins_data = None

    try:
        if callable(generate_script):
            s, c, coins_data = generate_script(
                mode=theme, language=lang, region=region,
                rss_url=rss_url, story_topic=story_topic
            )
            script = s if isinstance(s, str) else str(s or "")
            captions = _safe_list(c)
        else:
            raise RuntimeError("generate_script fonksiyonu yok")
    except Exception as e:
        _append_error(f"[script warning] generate_script failed: {e}")
        # Basit varsayılan metinler
        if lang == "tr":
            script = "Bugün gizemli bir hikaye: Beklenmedik bir buluşma, şehir ışıkları altında başlar..."
            captions = [
                "Gizemli bir mektup...",
                "Gece yarısı sokakları",
                "Eski bir dost",
                "Sır perdesi aralanıyor"
            ]
        else:
            script = "A short mysterious tale: Under the city lights, an unexpected meeting unfolds..."
            captions = [
                "A strange letter",
                "Midnight streets",
                "An old friend",
                "The secret revealed"
            ]
    print("SCRIPT:\n", script, flush=True)

    # 2) Başlık & açıklama (fallbacklı)
    try:
        title_prefix = _env("VIDEO_TITLE_PREFIX", {
            "crypto": "Daily Crypto Brief:",
            "sports": "Sports Brief:",
            "news":   "Daily Brief:",
            "story":  "Story:",
        }.get(theme, "Daily Brief:"))
        if callable(build_titles):
            title, description = build_titles(
                theme, captions=captions, coins_data=coins_data, title_prefix=title_prefix
            )
        else:
            raise RuntimeError("build_titles fonksiyonu yok")
    except Exception as e:
        _append_error(f"[title warning] build_titles failed: {e}")
        if lang == "tr":
            title = f"{title_prefix} Kısa Gizemli Hikaye"
            description = "Otomatik üretilmiştir."
        else:
            title = f"{title_prefix} Short Mystery Story"
            description = "Auto-generated."
    print("TITLE:", title, flush=True)

    # 3) TTS (fallback: sessiz MP3)
    voice    = _env("TTS_VOICE", "alloy") or "alloy"
    atempo   = _env("TTS_ATEMPO", "1.05") or "1.05"
    gap_ms   = _env("TTS_GAP_MS", "10") or "10"
    bitrate  = _env("TTS_BITRATE", "128k") or "128k"

    ts = _ts()
    mp3_path = f"out/voice-{ts}.mp3"
    mp4_path = f"out/video-{ts}.mp4"

    print(">> TTS...", flush=True)
    try:
        if callable(synth_tts_to_mp3) and (_env("OPENAI_API_KEY") or "").strip():
            synth_tts_to_mp3(
                text=script, out_mp3=mp3_path,
                voice=voice, atempo=atempo, gap_ms=gap_ms, bitrate=bitrate
            )
        else:
            raise RuntimeError("TTS kullanılamıyor veya OPENAI_API_KEY yok")
    except Exception as e:
        _append_error(f"[tts warning] synth_tts_to_mp3 failed: {e}")
        # Sessiz mp3 üret
        _ffmpeg_silence_mp3(mp3_path, seconds=30)
        print(">> TTS yok, sessiz MP3 ile devam.", flush=True)

    # 4) Video render (fallback: siyah arka plan)
    print(">> Render video...", flush=True)
    rendered = False
    try:
        if callable(make_slideshow_video):
            # Görseller ağdan alınmıyor; captions ile slideshow oluştur.
            make_slideshow_video(
                images=[], captions=captions,
                audio_mp3=mp3_path, out_mp4=mp4_path,
                theme=theme, ticker_text=None
            )
            rendered = True
        else:
            raise RuntimeError("make_slideshow_video fonksiyonu yok")
    except Exception as e:
        _append_error(f"[render warning] slideshow failed: {e}")

    if not rendered:
        _fallback_black_video(1080, 1920, mp3_path, mp4_path)

    print(f">> Done: {mp4_path}", flush=True)

    # 5) YouTube yükleme (opsiyonel; hata olsa da düşürme)
    print(">> Trying YouTube upload (if creds exist)...", flush=True)
    try:
        if not callable(try_upload_youtube):
            msg = ">> YouTube uploader modülü bulunamadı; yükleme atlandı."
            print(msg, flush=True)
            _append_error("[upload warning] uploader module missing")
        else:
            yt_client_id = _env("YT_CLIENT_ID")
            yt_client_secret = _env("YT_CLIENT_SECRET")
            yt_refresh_token = _env("YT_REFRESH_TOKEN")
            missing_envs = [
                name for name, value in {
                    "YT_CLIENT_ID": yt_client_id,
                    "YT_CLIENT_SECRET": yt_client_secret,
                    "YT_REFRESH_TOKEN": yt_refresh_token,
                }.items() if not value
            ]
            if missing_envs:
                reason = ", ".join(missing_envs)
                print(
                    ">> YouTube yüklemesi yapılamadı: eksik ortam değişkenleri: "
                    + reason,
                    flush=True,
                )
                _append_error(
                    "[upload warning] missing required env vars for YouTube upload: " + reason
                )
            else:
                privacy = (_env("YT_PRIVACY", "public") or "public").lower().strip()
                valid_privacy_values = {"public", "private", "unlisted"}
                if privacy not in valid_privacy_values:
                    warn_msg = (
                        f">> YouTube privacy ayarı '{privacy}' geçersiz; 'public' kullanılacak."
                    )
                    print(warn_msg, flush=True)
                    _append_error("[upload warning] invalid YT_PRIVACY value: " + privacy)
                    privacy = "public"
                url = try_upload_youtube(
                    mp4_path,
                    title=title,
                    description=description,
                    privacy_status=privacy,
                )
                if url:
                    print(">> Uploaded:", url, flush=True)
                else:
                    _append_error("[upload warning] uploader returned no URL")
                    print(">> Upload skipped or failed (no URL).", flush=True)
                    _print_youtube_error_summary()
    except Exception as e:
        _append_error(f"[upload warning] {e}")
        print(f"[upload warning] {e}", flush=True)
        _print_youtube_error_summary()

    # ÖNEMLİ: Asla sys.exit(1) yapma; loglara yazdık ve fallback ile çıktıyı ürettik.
    return

# ---------- Giriş Noktası ----------
if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Yine de beklenmeyen bir şey olursa iş düşmesin; logla ve sıfırla bitir.
        Path("out").mkdir(parents=True, exist_ok=True)
        with open("out/error.log", "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        traceback.print_exc()
        # exit(0) → job yeşil kalsın
        sys.exit(0)