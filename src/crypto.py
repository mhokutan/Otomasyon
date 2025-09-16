import requests, datetime, random
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920


def _fetch_simple_prices(ids: List[str], vs="usd") -> Dict[str, Dict]:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(ids),
        "vs_currencies": vs,
        "include_24hr_change": "true",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _fetch_market_chart(id_: str, vs="usd", days=1) -> List[float]:
    url = f"https://api.coingecko.com/api/v3/coins/{id_}/market_chart"
    r = requests.get(url, params={"vs_currency": vs, "days": days}, timeout=30)
    r.raise_for_status()
    data = r.json().get("prices", [])
    return [p[1] for p in data] if data else []


def _fmt_price(v: float) -> str:
    if v >= 1000:
        return f"${v:,.0f}"
    elif v >= 1:
        return f"${v:,.2f}"
    else:
        s = f"${v:.6f}"
        return s.rstrip("0").rstrip(".")


def _draw_bg() -> Image.Image:
    img = Image.new("RGB", (W, H), (10, 12, 18))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        c = int(16 + 24 * (y / H))
        draw.line([(0, y), (W, y)], fill=(c, c, c + 4))
    px = img.load()
    for _ in range(20000):
        x = random.randint(0, W - 1)
        y = random.randint(0, H - 1)
        r, g, b = px[x, y]
        d = random.randint(-8, 8)
        px[x, y] = (
            max(0, min(255, r + d)),
            max(0, min(255, g + d)),
            max(0, min(255, b + d)),
        )
    img = img.filter(ImageFilter.GaussianBlur(2))
    return img


def _load_font(size=64):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=size
        )
    except:
        return ImageFont.load_default()


def _sparkline(
    prices: List[float],
    w: int,
    h: int,
    color_up=(60, 220, 140),
    color_down=(240, 85, 85),
) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if not prices or len(prices) < 2:
        d.line([(0, h // 2), (w, h // 2)], fill=(200, 200, 200, 200), width=4)
        return img
    mn, mx = min(prices), max(prices)
    rng = mx - mn if mx > mn else 1.0
    pts = []
    for i, v in enumerate(prices):
        x = int(i * (w - 1) / (len(prices) - 1))
        y = int(h - 1 - (v - mn) * (h - 1) / rng)
        pts.append((x, y))
    up = prices[-1] >= prices[0]
    col = color_up if up else color_down
    d.line(pts, fill=col + (230,), width=6)
    d.ellipse(
        [pts[-1][0] - 8, pts[-1][1] - 8, pts[-1][0] + 8, pts[-1][1] + 8],
        fill=col + (255,),
    )
    return img


def build_crypto_items_and_images(ids: List[str], out_dir, stamp: str):
    data = _fetch_simple_prices(ids)
    items = []
    for cid in ids:
        entry = data.get(cid)
        if not entry:
            continue
        price = float(entry.get("usd", 0.0))
        chg = float(entry.get("usd_24h_change", 0.0))
        hist = _fetch_market_chart(cid, days=1)
        items.append({"id": cid, "price": price, "change": chg, "history": hist})

    paths = []
    for i, it in enumerate(items, 1):
        img = _draw_bg()
        draw = ImageDraw.Draw(img)

        bar_h = 140
        draw.rectangle([0, 0, W, bar_h], fill=(0, 0, 0, 110))
        f_small = _load_font(40)
        draw.text((40, 40), "CRYPTO • DAILY UPDATE", fill=(230, 230, 240), font=f_small)

        f_big = _load_font(120)
        code = it["id"].upper()[:6]
        price_txt = _fmt_price(it["price"])
        code_w = draw.textlength(code, font=f_big)
        price_w = draw.textlength(price_txt, font=f_big)
        draw.text(((W - code_w) // 2, 300), code, fill=(250, 250, 250), font=f_big)
        draw.text(
            ((W - price_w) // 2, 450), price_txt, fill=(255, 255, 255), font=f_big
        )

        chg = it["change"]
        up = chg >= 0
        chg_txt = f"{chg:+.2f}% / 24s"
        f_med = _load_font(56)
        ccol = (60, 220, 140) if up else (240, 85, 85)
        cw = draw.textlength(chg_txt, font=f_med)
        draw.text(((W - cw) // 2, 600), chg_txt, fill=ccol, font=f_med)

        pad = 80
        sw, sh = W - pad * 2, 600
        sp = _sparkline(it["history"], sw, sh)
        panel = Image.new("RGBA", (sw, sh), (0, 0, 0, 80))
        img.paste(panel, (pad, 760), panel)
        img.paste(sp, (pad, 760), sp)

        f_info = _load_font(36)
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        info = f"Source: CoinGecko • {now}"
        draw.text((40, H - 80), info, fill=(210, 210, 215), font=f_info)

        p = out_dir / f"crypto-{stamp}-{i}.png"
        img.save(p, format="PNG", optimize=True)
        paths.append(str(p))

    return items, paths
