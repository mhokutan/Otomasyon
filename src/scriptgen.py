import os
from datetime import datetime

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

def build_crypto_script(coin_rows):
    # coin_rows: list of dicts: {symbol, price_usd, change_24h}
    lines = []
    hook = "Bitcoin, Ethereum and top altcoins — here is your 60-second market brief!"
    lines.append("[ON SCREEN TEXT] 60-second crypto brief")
    lines.append(f"[HOOK] {hook}")
    lines.append("[B-ROLL] Dynamic background.")

    for row in coin_rows[:3]:
        sym = row.get("symbol","").upper()
        price = _fmt_price(row.get("price_usd","?"))
        chg = _trend_word(row.get("change_24h",0))
        lines.append(f"[CUT] {sym}: ${price}, 24h {chg}.")

    lines.append("[TIP] Not financial advice. Mind the volatility.")
    lines.append("[CTA] Subscribe for a short daily brief!")
    return "\n".join(lines)

def build_news_script(headlines):
    # headlines: list of strings (already in EN via RSS)
    lines = []
    lines.append("[ON SCREEN TEXT] 60-second brief")
    first = headlines[0] if headlines else "Top stories right now."
    lines.append(f"[HOOK] {first} — let’s go!")
    lines.append("[B-ROLL] Dynamic background.")

    for i, h in enumerate(headlines[:3], start=1):
        lines.append(f"[CUT] {i}. {h}")

    lines.append("[CUT] 10 seconds left; quick recap:")
    lines.append(" • We track the day’s developments and pick the clearest headlines.")
    lines.append(" • Subscribe to never miss the brief.")
    lines.append("[CTA] New 1-minute summaries every day!")
    return "\n".join(lines)

def build_titles(theme, coin_rows=None, headlines=None):
    now = datetime.utcnow().strftime("%b %d")
    if theme == "crypto" and coin_rows:
        return [
            f"Bitcoin: ${_fmt_price(coin_rows[0]['price_usd'])}",
            f"Ethereum: ${_fmt_price(coin_rows[1]['price_usd'])}" if len(coin_rows)>1 else "Market update",
            f"Altcoins moving today" if len(coin_rows)>2 else "24h change"
        ]
    if headlines:
        return headlines[:3]
    return [f"Daily Brief — {now}"]

def generate_script(theme: str, coin_rows=None, headlines=None):
    theme = (theme or "news").lower()
    if theme == "crypto":
        return build_crypto_script(coin_rows or [])
    else:
        return build_news_script(headlines or [])
