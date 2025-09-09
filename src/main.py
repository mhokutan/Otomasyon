import os
import datetime
import pathlib
import json
from scriptgen import fetch_trends_tr, make_script_tr
from tts import script_to_mp3
from video import mp3_to_vertical_mp4
from youtube_upload import try_upload_youtube

OUT_DIR = pathlib.Path("out")
OUT_DIR.mkdir(exist_ok=True)

def now_stamp():
    # UTC zaman damgası
    return datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")

def sanitize_privacy(value: str) -> str:
    # Boş veya hatalıysa 'unlisted'
    v = (value or "").strip().lower()
    return v if v in {"public", "unlisted", "private"} else "unlisted"

def main():
    stamp = now_stamp()

    print(">> Fetching trends...")
    items = fetch_trends_tr(limit=3)
    if not items:
        print("No RSS items found; aborting.")
        return

    print(">> Generating script...")
    script = make_script_tr(items)
    print("SCRIPT:\n", script)

    meta = {
        "timestamp": stamp,
        "items": items,
        "script": script,
    }
    (OUT_DIR / f"meta-{stamp}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    mp3_path = OUT_DIR / f"voice-{stamp}.mp3"
    print(">> TTS...")
    script_to_mp3(script, str(mp3_path), lang="tr")

    mp4_path = OUT_DIR / f"video-{stamp}.mp4"
    print(">> FFmpeg render (vertical 1080x1920)...")
    mp3_to_vertical_mp4(str(mp3_path), str(mp4_path))
    print(">> Done:", mp4_path)

    # Opsiyonel: YouTube upload
    print(">> Trying YouTube upload (if creds exist)...")
    title_prefix = os.getenv("VIDEO_TITLE_PREFIX", "Günün Özeti:")
    first_title = items[0]["title"] if items else "Günün Özeti"
    # Başlık max 95 karakter
    title = f"{title_prefix} {first_title}".strip()[:95]
    description = "Kaynak: Google News RSS\n#haber #gündem #kısaözet"

    privacy_env = os.getenv("YT_PRIVACY")
    privacy = sanitize_privacy(privacy_env)

    uploaded_url = None
    try:
        uploaded_url = try_upload_youtube(
            str(mp4_path),
            title=title,
            description=description,
            privacy_status=privacy,
        )
    except Exception as e:
        print(f"[WARN] Upload exception: {e}")

    if uploaded_url:
        print("Uploaded:", uploaded_url)
        (OUT_DIR / f"youtube-{stamp}.txt").write_text(uploaded_url, encoding="utf-8")
    else:
        print("YouTube upload skipped or failed — video kept as artifact.")

if __name__ == "__main__":
    main()
