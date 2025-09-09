# ...
from video import make_slideshow_video
# ...

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
        print(">> Building visuals (AI if HF_TOKEN present)...")
        images = build_images_for_items(titles, OUT_DIR, prefix=f"ai-{stamp}")
        ticker_text = "  •  ".join(titles)  # haberlerde alt ticker

    print("SCRIPT:\n", script)
    # ... (meta ve TTS aynı)
    mp3_path = OUT_DIR / f"voice-{stamp}.mp3"
    print(">> TTS...")
    script_to_mp3(script, str(mp3_path), lang="tr")

    mp4_path = OUT_DIR / f"video-{stamp}.mp4"
    print(">> Render video...")
    make_slideshow_video(images, titles, str(mp3_path), str(mp4_path), theme=theme, ticker_text=ticker_text)
    print(">> Done:", mp4_path)
    # ... (YouTube kısmı aynı)
