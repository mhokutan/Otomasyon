import os, json, time, pathlib, tempfile
from datetime import datetime
from typing import List
import requests

from scriptgen import generate_script, build_titles, fetch_trends_tr, make_script_tr, make_script_crypto
from tts import synth_tts_to_mp3
from video import make_slideshow_video
from youtube_upload import try_upload_youtube

OUT_DIR = pathlib.Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def fetch_crypto_rows(coins_csv: str) -> List[dict]:
    coins = [c.strip().lower() for c in (coins_csv or "bitcoin,ethereum,solana").split(",") if c.strip()]
    ids = ",".join(coins)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    rows = []
    for c in coins:
        d = data.get(c, {})
        rows.append({
            "symbol": c.upper(),
            "price_usd": d.get("usd", "?"),
            "change_24h": d.get("usd_24h_change", 0.0),
        })
    return rows

def build_images(headlines_or_titles: List[str], theme: str) -> List[str]:
    # Try HF text2img vertical; fallback to simple PIL render.
    from PIL import Image, ImageDraw, ImageFont
    HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
    model = "stabilityai/sdxl-turbo"  # fast, decent
    imgs = []
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    def _fallback(text, idx):
        W, H = 1080, 1920
        im = Image.new("RGB", (W, H), (18, 18, 24))
        dr = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype(font_path, 56)
        except:
            font = ImageFont.load_default()
        wrapped = []
        words = text.split()
        line = []
        for w in words:
            test = " ".join(line + [w])
            if dr.textlength(test, font=font) < W*0.86:
                line.append(w)
            else:
                wrapped.append(" ".join(line)); line = [w]
        if line: wrapped.append(" ".join(line))
        y = 140
        for ln in wrapped[:5]:
            wlen = dr.textlength(ln, font=font)
            dr.text(((W-wlen)//2, y), ln, font=font, fill=(240,240,240), stroke_width=2, stroke_fill=(0,0,0))
            y += 70
        p = OUT_DIR / f"{theme}-{datetime.utcnow():%Y%m%d-%H%M%S}-{idx+1}.png"
        im.save(p)
        return str(p)

    for i, title in enumerate(headlines_or_titles):
        prompt = f"{theme} news abstract background, dynamic light, high contrast, vertical 1080x1920"
        if HF_TOKEN:
            try:
                resp = requests.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    headers={"Authorization": f"Bearer {HF_TOKEN}"},
                    json={
                        "inputs": prompt,
                        "options": {"wait_for_model": True},
                        "parameters": {"num_inference_steps": 15, "guidance_scale": 1.5}
                    },
                    timeout=60
                )
                resp.raise_for_status()
                img_bytes = resp.content
                p = OUT_DIR / f"ai-{datetime.utcnow():%Y%m%d-%H%M%S}-{i+1}.png"
                with open(p, "wb") as f:
                    f.write(img_bytes)
                imgs.append(str(p))
                continue
            except Exception as e:
                # fallback
                imgs.append(_fallback(title, i))
        else:
            imgs.append(_fallback(title, i))
    return imgs

def main():
    theme = (os.getenv("THEME") or "news").lower()
    title_prefix = os.getenv("VIDEO_TITLE_PREFIX", "").strip()
    language = os.getenv("LANGUAGE", "en")
    region   = os.getenv("REGION", "US")

    print(">> Fetching content...")
    headlines = []
    coin_rows = []
    if theme == "crypto":
        coin_rows = fetch_crypto_rows(os.getenv("CRYPTO_COINS", "bitcoin,ethereum,solana"))
        script = generate_script("crypto", coin_rows=coin_rows)
        captions = build_titles("crypto", coin_rows=coin_rows)
        ticker_text = "Subscribe for daily crypto briefs • This is not financial advice •"
    else:
        # sports/news via RSS
        rss_url = os.getenv("RSS_URL", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
        headlines = fetch_trends_tr() if not rss_url else __import__("scriptgen")._fetch_headlines_from_rss(rss_url, limit=12)  # uses compat helper
        script = generate_script("news", headlines=headlines)
        captions = build_titles("news", headlines=headlines)
        ticker_text = "Breaking updates • Sports highlights • Subscribe for daily briefs •"

    print("SCRIPT:\n", script)

    print(">> TTS...")
    voice = os.getenv("TTS_VOICE", "alloy")
    atempo = float(os.getenv("TTS_ATEMPO", "1.60"))
    gap_ms = int(os.getenv("TTS_GAP_MS", "10"))
    bitrate = os.getenv("TTS_BITRATE", "128k")
    mp3_path = OUT_DIR / f"voice-{datetime.utcnow():%Y%m%d-%H%M%S}.mp3"
    synth_tts_to_mp3(text=script, out_mp3=str(mp3_path), voice=voice, atempo=atempo, gap_ms=gap_ms, bitrate=bitrate)

    print(">> Building visuals...")
    images = build_images(captions, theme)
    mp4_path = OUT_DIR / f"video-{datetime.utcnow():%Y%m%d-%H%M%S}.mp4"

    print(">> Render video...")
    make_slideshow_video(images, captions, str(mp3_path), str(mp4_path), theme=theme, ticker_text=ticker_text)

    print(">> Try YouTube upload...")
    title = f"{title_prefix} {datetime.now().strftime('%b %d')}".strip() or "Daily Brief"
    description = "Automated short. Generated with TTS + ffmpeg. #news #shorts"
    privacy = (os.getenv("YT_PRIVACY") or "public").lower()
    uploaded_url = try_upload_youtube(str(mp4_path), title=title, description=description, privacy_status=privacy)

    print(">> Done.")
    if uploaded_url:
        print("YouTube:", uploaded_url)

if __name__ == "__main__":
    main()
