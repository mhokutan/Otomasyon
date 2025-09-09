import feedparser
from html import unescape

# Türkiye haber RSS (Google News TR)
RSS_URL_TR = "https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr"

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
    """
    Basit kural tabanlı 60 sn script (OpenAI yok, ücretsiz).
    ~120-140 kelime hedefli.
    """
    titles = [it.get("title", "").strip() for it in items if it.get("title")]
    topline = titles[0] if titles else "Bugünün en çok konuşulan başlıkları"

    hook = (
        "[ON SCREEN TEXT] 60 saniyede gündem!\n"
        f"[HOOK] {topline}… Peki detaylar ne?"
    )

    bullets = []
    for i, t in enumerate(titles, 1):
        bullets.append(f"[CUT] {i}. {t}")

    cta = "[CTA] Her gün 1 dakikada özet için takipte kal!"

    script = (
        f"{hook}\n"
        "[B-ROLL] Dinamik arka plan.\n"
        + "\n".join(bullets[:3]) + "\n"
        "[CUT] 10 saniyemiz kaldı; kısaca:\n"
        " • Gün boyu süren gelişmeleri izleyip en net başlıkları seçiyoruz.\n"
        " • Abone ol, 60 saniyede geri kalma!\n"
        + cta
    )
    return script
