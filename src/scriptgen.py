import os, feedparser
from html import unescape

# Haber modu için RSS (değiştirmek istersen SECRET ile RSS_URL geçebilirsin)
RSS_URL_TR = os.getenv("RSS_URL", "https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr")

def fetch_trends_tr(limit=3):
    d = feedparser.parse(RSS_URL_TR)
    items = []
    for e in d.entries[:limit]:
        items.append({
            "title": unescape(getattr(e, "title", "")),
            "link": getattr(e, "link", ""),
            "published": getattr(e, "published", ""),
        })
    return items

def make_script_tr(items):
    # Kısa, akıcı 60 sn metni
    lines = []
    lines.append("[ON SCREEN TEXT] 60 saniyede gündem!")
    if items:
        lines.append(f"[HOOK] {items[0]['title']}… Peki detaylar ne?")
    lines.append("[B-ROLL] Dinamik arka plan.")
    for i, it in enumerate(items[:3], 1):
        lines.append(f"[CUT] {i}. {it['title']}")
    lines.append("[CUT] 10 saniyemiz kaldı; kısaca:")
    lines.append(" • Gün boyu süren gelişmeleri izleyip en net başlıkları seçiyoruz.")
    lines.append(" • Abone ol, 60 saniyede geri kalma!")
    lines.append("[CTA] Her gün 1 dakikada özet için takipte kal!")
    return "\n".join(lines)

# --- CRYPTO modu ---
def make_script_crypto(coin_items):
    """
    coin_items: [{id, price, change, history}, ...]
    """
    if not coin_items:
        return "Bugün veri çekilemedi; yarın tekrar görüşürüz."

    def line(ci):
        name = ci["id"].upper()
        price = ci["price"]
        chg = ci["change"]
        sign = "yukarı" if chg >= 0 else "aşağı"
        return f"{name}: {price:.2f} dolar, 24 saatte %{chg:+.2f} ile {sign}."

    lines = []
    lines.append("[ON SCREEN TEXT] Kripto Günlük Özeti")
    lines.append("[HOOK] Bitcoin, Ethereum ve seçili altcoinlerde son 24 saatin özeti!")
    for ci in coin_items[:3]:
        lines.append("[CUT] " + line(ci))
    lines.append("[TIP] Yatırım tavsiyesi değildir. Volatiliteye dikkat.")
    lines.append("[CTA] Günlük kısa özet için takip etmeyi unutma!")
    return "\n".join(lines)
