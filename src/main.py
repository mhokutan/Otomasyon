import os, datetime, json, pathlib
from scriptgen import fetch_trends_tr, make_script_tr, make_script_crypto
from tts import script_to_mp3
from video import make_slideshow_video
from youtube_upload import try_upload_youtube
from gen_images import build_images_for_items
from crypto import build_crypto_items_and_images

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = (ROOT / "out")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def now_stamp():
    return datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")

def _fmt(v: float) -> str:
    if v >= 1000:
        return f"${v:,.0f}"
    elif v >= 1:
        return f"${v:,.2f}"
    else:
        s = f"${v:.6f}"
        return s.rstrip("0").rstrip(".")

def sanitize_privacy(value: str) -> str:
    v = (value or "").strip().lower()
    return v if v in {"public", "unlisted", "private"} else "unlisted"

def main():
    stamp = now_stamp()
    theme = (os.getenv("THEME") or "news").strip().lower()

    if theme == "crypto":
        coins = [c.strip() for c in (os.getenv("CRYPTO_COINS") or "bitcoin,ethereum,solana").split(",") if c.strip()]
        print(">> Fetching crypto...")
        coin_items, images = build_crypto_items_and_images(coins, OUT_DIR, stamp)
        titles = [f"{ci['id'].upper()} {_fmt(ci['price'])} ({ci['change']:+.2f}% 24s)" for ci in coin_items]
        print(">> Generating script (crypto)...")
        script = make_script_crypto(coin_items)
        ticker_text = "  •  ".join([f"{ci['id'].upper()}: {_fmt(ci['price'])} ({ci['change']:+.2f}%)" for ci in coin_items])
    else:
        print(">> Fetching trends (news)...")
        items = fetch_trends_tr(limit=3)
        titles = [it["title"] for it in items]
        print(">> Generating script (news)...")
        script = make_script_tr(items)
        print(">> Building visuals (PIL, no network)...")
        images = build_images_for_items(titles, OUT_DIR, prefix=f"news-{stamp}")
        ticker_text = "  •  ".join(titles)

    print("SCRIPT:\n", script)
    meta = {"timestamp": stamp, "theme": theme, "titles": titles, "script": script}
    (OUT_DIR / f"meta-{stamp}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    mp3_path = OUT_DIR / f"voice-{stamp}.mp3"
    print(">> TTS...")
    script_to_mp3(script, str(mp3_path), lang="tr")

    mp4_path = OUT_DIR / f"video-{stamp}.mp4"
    print(">> Render video...")
    make_slideshow_video(images, titles, str(mp3_path), str(mp4_path), theme=theme, ticker_text=ticker_text)
    print(">> Done:", mp4_path)

    print(">> Trying YouTube upload (if creds exist)...")
    title_prefix = os.getenv("VIDEO_TITLE_PREFIX", "Günlük Özet:")
    first_title = titles[0] if titles else ("Günlük Kripto" if theme == "crypto" else "Günlük Haber")
    title = f"{title_prefix} {first_title}".strip()[:95]
    description = ("Kaynak: CoinGecko (fiyat/sparkline)\n#kripto #bitcoin #ethereum #solana #günlüközet"
                   if theme == "crypto"
                   else "Günlük kısa özet.\n#haber #gündem #özet")
    privacy = sanitize_privacy(os.getenv("YT_PRIVACY"))

    uploaded_url = None
    try:
        uploaded_url = try_upload_youtube(str(mp4_path), title=title, description=description, privacy_status=privacy)
    except Exception as e:
        print(f"[WARN] Upload exception: {e}")

    if uploaded_url:
        print("Uploaded:", uploaded_url)
        (OUT_DIR / f"youtube-{stamp}.txt").write_text(uploaded_url, encoding="utf-8")
    else:
        print("YouTube upload skipped or failed — video kept as artifact.")

if __name__ == "__main__":
    main()
