import os
from datetime import datetime
from typing import List
import feedparser

# ---------- Helpers ----------
def _fmt_price(p):
    try:
        return f"{float(p):,.2f}"
    except Exception:
        return str(p)

def _trend_word(pct):
    try:
        v = float(pct)
    except Exception:
        return "flat"
    if v > 0: return f"+{v:.2f}% up"
    if v < 0: return f"{v:.2f}% down"
    return "flat"

# ---------- EN script builders ----------
def build_crypto_script(coin_rows: List[dict]):
    lines = []
    hook = "Bitcoin, Ethereum and top altcoins — here is your 60-second market brief!"
    lines.append("[ON SCREEN TEXT] 60-second crypto brief")
    lines.append(f"[HOOK] {hook}")
    lines.append("[B-ROLL] Dynamic background.")
    for row in (coin_rows or [])[:3]:
        sym = (row.get("symbol") or "").upper()
        price = _fmt_price(row.get("price_usd", "?"))
        chg = _trend_word(row.get("change_24h", 0))
        lines.append(f"[CUT] {sym}: ${price}, 24h {chg}.")
    lines.append("[TIP] Not financial advice. Mind the volatility.")
    lines.append("[CTA] Subscribe for a short daily brief!")
    return "\n".join(lines)

def build_news_script(headlines: List[str]):
    lines = []
    lines.append("[ON SCREEN TEXT] 60-second brief")
    first = (headlines[0] if headlines else "Top stories right now.")[:120]
    lines.append(f"[HOOK] {first} — let’s go!")
    lines.append("[B-ROLL] Dynamic background.")
    for i, h in enumerate((headlines or [])[:3], start=1):
        lines.append(f"[CUT] {i}. {h}")
    lines.append("[CUT] 10 seconds left; quick recap:")
    lines.append(" • We track the day’s developments and pick the clearest headlines.")
    lines.append(" • Subscribe to never miss the brief.")
    lines.append("[CTA] New 1-minute summaries every day!")
    return "\n".join(lines)

def build_titles(theme, coin_rows=None, headlines=None):
    now = datetime.utcnow().strftime("%b %d")
    if (theme or "").lower() == "crypto" and coin_rows:
        t1 = f"Bitcoin: ${_fmt_price(coin_rows[0]['price_usd'])}"
        t2 = f"Ethereum: ${_fmt_price(coin_rows[1]['price_usd'])}" if len(coin_rows) > 1 else "Market update"
        t3 = "Altcoins on the move" if len(coin_rows) > 2 else "24h change"
        return [t1, t2, t3]
    if headlines:
        return [h[:80] for h in headlines[:3]]
    return [f"Daily Brief — {now}"]

def generate_script(theme: str, coin_rows=None, headlines=None):
    theme = (theme or "news").lower()
    if theme == "crypto":
        return build_crypto_script(coin_rows or [])
    else:
        return build_news_script(headlines or [])

# ---------- RSS helper ----------
def _fetch_headlines_from_rss(rss_url: str, limit: int = 8) -> List[str]:
    if not rss_url:
        rss_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)
    heads = []
    for e in feed.entries[:limit]:
        title = getattr(e, "title", None) or ""
        if title:
            heads.append(title)
    return heads

# ---------- Backward compatibility (old main.py imports) ----------
def fetch_trends_tr():
    """Old name kept for compatibility. Returns EN headlines list."""
    rss = os.getenv("RSS_URL", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
    return _fetch_headlines_from_rss(rss, limit=12)

def make_script_tr(headlines):
    """Old name -> now EN news script."""
    return build_news_script(headlines or [])

def make_script_crypto(coin_rows):
    """Old name -> EN crypto script."""
    return build_crypto_script(coin_rows or [])
