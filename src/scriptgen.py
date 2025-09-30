# -*- coding: utf-8 -*-
"""
Series-aware script & SEO metadata generator.

- generate_script(mode, language, region, rss_url, story_topic, ...)
  -> (script_text, captions_list, coins_data_or_none)

- build_titles(mode, captions, coins_data, title_prefix, ...)
  -> TitleMetadata(title, description, captions, tags)

Env knobs (optional):
- SERIES_NAME="Mystery Files"
- SERIES_SEASON="1"
- SERIES_LANG_KEY defaults to LANGUAGE (so en/tr run independent counters)
- MIN_SEC_PER_CAPTION (float, default 4.0)
"""

from __future__ import annotations
import os, time, textwrap, math
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Any, Iterator
import logging, requests
try:
    import feedparser  # type: ignore
    _HAS_FEEDPARSER = True
except Exception:
    _HAS_FEEDPARSER = False
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

def _clean_text(s: str) -> str:
    return " ".join((s or "").replace("\r"," ").replace("\n"," ").split())

def _fmt_usd(x: float) -> str:
    return f"${x:,.2f}"

def _fmt_pct(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f}%"

def _safe_first(items: List, n: int) -> List:
    return items[:n] if items else []

# ---------- Series helpers ----------
def _series_name() -> str:
    return _env("SERIES_NAME", "Mystery Files") or "Mystery Files"

def _series_season() -> int:
    try:
        return int(_env("SERIES_SEASON", "1") or "1")
    except Exception:
        return 1

def _series_episode(language: str) -> int:
    """
    Deterministic daily ep number per language key.
    E.g., en and tr sequences advance independently.
    """
    lang_key = (_env("SERIES_LANG_KEY") or language or "en").lower()
    # day count since 2025-01-01
    yday = int(time.strftime("%j", time.gmtime()))
    year = int(time.strftime("%Y", time.gmtime()))
    base = 1000 if lang_key.startswith("tr") else 0
    return (year * 400 + yday + base)  # monotonically increasing

# ---------- Crypto fetch ----------
def fetch_crypto_simple(coin_ids: List[str]) -> Dict[str, Dict[str, float]]:
    ids = ",".join(coin_ids)
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    )
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    raw = r.json()
    out: Dict[str, Dict[str, float]] = {}
    for cid in coin_ids:
        if cid in raw and "usd" in raw[cid]:
            price = float(raw[cid]["usd"])
            chg = float(raw[cid].get("usd_24h_change", 0.0))
            out[cid] = {"usd": price, "usd_24h_change": chg}
    return out

# ---------- News helpers ----------
def _rss_top_titles(url: str, n: int = 5) -> List[Tuple[str, str]]:
    titles: List[Tuple[str, str]] = []
    if _HAS_FEEDPARSER:
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            logger.warning("RSS feedparser failed: %s", exc)
            return titles
        for e in _safe_first(getattr(feed, "entries", []), n):
            t = _clean_text(getattr(e, "title", "") or "")
            l = getattr(e, "link", "") or ""
            if t:
                titles.append((t, l))
        return titles

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("RSS request failed: %s", exc)
        return titles

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        logger.warning("RSS XML parse failed: %s", exc)
        return titles

    for item in root.findall(".//item"):
        t = _clean_text(item.findtext("title") or "")
        l = item.findtext("link") or ""
        if t: titles.append((t, l))
        if len(titles) >= n:
            break
    return titles[:n]

# ---------- Story / News / Crypto scripts (longer) ----------
def make_script_story(topic: Optional[str], language: str="en") -> Tuple[str, List[str]]:
    """
    Story is forced to EN (we ignore 'language' to disable TR variant intentionally).
    """
    t = (topic or "mystery").strip().title()
    lines = [
        f"[ON SCREEN TEXT: \"{t}\"]",
        f"[HOOK] A short {t.lower()} tale: a mysterious beginning...",
        "[CUT] A foggy alley and a forgotten note.",
        "[CUT] The symbol matches an old book’s cover.",
        "[CUT] A knock: a visitor from the past.",
        "[CUT] A secret: the lost key and two doors.",
        "[CUT] First door—easy. Second—right.",
        "[CUT] Hesitation; time runs out.",
        "[CUT] Choice made; an unexpected outcome.",
        "[CUT] A trail to follow; paths diverge.",
        "[CUT] What remains: courage and silence.",
        "[TIP] Sometimes the right answer is the hardest to face.",
        "[CTA] Subscribe for the next episode!",
    ]
    caps = [
        f"{t} — short story","Foggy alley","Old symbol","Visitor",
        "Two doors","The choice","Outcome","Trail","Courage",
    ]
    return "\n".join(lines), caps

def make_script_news(headlines: List[Tuple[str, str]], language: str="en") -> Tuple[str, List[str]]:
    if not headlines:
        return ("[ON SCREEN TEXT] 60-second brief (no headlines)\n[CTA] Subscribe!", ["60-second brief"])
    titles = [h[0] for h in headlines]
    if language.startswith("tr"):
        lines = ["[ON SCREEN TEXT] 60 saniyelik özet", f"[HOOK] {titles[0]} — başlayalım!"]
        for i, t in enumerate(_safe_first(titles, 6), 1):
            lines.append(f"[CUT] {i}. {t}")
        lines += ["[CUT] Kısa tekrar ve kapanış.", "[CTA] Her gün 1 dakikalık özetler için abone ol!"]
    else:
        lines = ["[ON SCREEN TEXT] 60-second brief", f"[HOOK] {titles[0]} — let’s go!"]
        for i, t in enumerate(_safe_first(titles, 6), 1):
            lines.append(f"[CUT] {i}. {t}")
        lines += ["[CUT] Quick recap and closing.", "[CTA] New 1-minute briefs daily—subscribe!"]
    return "\n".join(lines), _safe_first(titles, 6)

def make_script_crypto(coins_data: Dict[str, Dict[str, float]], language: str="en") -> Tuple[str, List[str]]:
    if not coins_data:
        if language.startswith("tr"):
            return ("[ON SCREEN TEXT] Kripto özeti (veri alınamadı)\n[CTA] Takipte kal!", ["Kripto özeti (veri yok)"])
        return ("[ON SCREEN TEXT] Crypto brief (no data)\n[CTA] Subscribe!", ["Crypto brief"])
    order_env = _env("CRYPTO_COINS", "bitcoin,ethereum,solana")
    order = [c.strip() for c in (order_env or "").split(",") if c.strip()]
    ordered = [c for c in order if c in coins_data] or list(coins_data.keys())

    caps: List[str] = []
    lines: List[str] = []
    if language.startswith("tr"):
        lines += ["[ON SCREEN TEXT] Kripto Günlük Özeti", "[HOOK] BTC, ETH ve seçili altcoinlerde son 24 saat..."]
    else:
        lines += ["[ON SCREEN TEXT] Daily Crypto Brief", "[HOOK] BTC, ETH and top alts — last 24h..."]

    for cid in ordered:
        d = coins_data[cid]
        name = cid.upper()
        price = _fmt_usd(d["usd"]); pct = _fmt_pct(d["usd_24h_change"])
        if language.startswith("tr"):
            dir_tr = "yukarı" if d["usd_24h_change"] >= 0 else "aşağı"
            lines.append(f"[CUT] {name}: {price}, 24 saatte {pct} {dir_tr}.")
        else:
            dir_en = "up" if d["usd_24h_change"] >= 0 else "down"
            lines.append(f"[CUT] {name}: {price}, 24h {pct} {dir_en}.")
        caps.append(f"{name}: {price} | 24h {pct}")

    lines += (["[TIP] Yatırım tavsiyesi değildir.", "[CTA] Günlük özet için abone ol!"]
              if language.startswith("tr")
              else ["[TIP] Not financial advice.", "[CTA] Subscribe for the daily brief!"])
    return "\n".join(lines), caps

# ---------- SEO metadata ----------
@dataclass
class TitleMetadata:
    title: Optional[str] = None
    description: Optional[str] = None
    captions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.captions = [str(c) for c in (self.captions or [])]
        self.tags = [t.strip() for t in (self.tags or []) if t and t.strip()]

    def as_tuple(self):
        return self.title, self.description

def build_titles(mode: str,
                 captions: Optional[List[str]] = None,
                 coins_data: Optional[Dict[str, Dict[str, float]]] = None,
                 title_prefix: Optional[str] = None,
                 **ignored: Any) -> TitleMetadata:
    mode_l = (mode or "").lower()
    language = (_env("LANGUAGE","en") or "en").lower()
    ts = _now_ts()

    if not title_prefix:
        title_prefix = {
            "crypto": "Daily Crypto Brief:",
            "sports": "Sports Brief:",
            "news": "Daily Brief:",
            "story": "Story:"
        }.get(mode_l, "Daily Brief:")

    provided_caps = [str(c) for c in (captions or [])]
    main_part = provided_caps[0] if provided_caps else (
        "Crypto market update" if mode_l=="crypto" else
        ("A short story" if mode_l=="story" else "Top headlines")
    )

    series = _series_name()
    season = _series_season()
    episode = _series_episode(language)
    # Title
    title = f"{series} S{season:02d}E{episode}: {main_part}"
    if title_prefix and not title.lower().startswith(title_prefix.lower()):
        title = f"{title_prefix} {title}"
    if len(title) > 95: title = title[:92] + "..."

    # Description
    p_intro = (
        f"This video is part of the “{series}” daily series. "
        f"Episode {episode} (Season {season})."
        if not language.startswith("tr") else
        f"Bu video “{series}” günlük serisinin bir parçası. "
        f"{episode}. bölüm (Sezon {season})."
    )

    bullets = "\n".join([f"• {c}" for c in _safe_first(provided_caps, 5)]) if provided_caps else ""
    if language.startswith("tr"):
        p_body = "Kısa ve akılda kalıcı bir bölüm; her gün yeni bir bölüm paylaşıyoruz."
        cta = "👉 Beğenmeyi ve abone olmayı unutmayın!"
        hashtags = "#shorts #hikaye #gizem #gündem #ai"
    else:
        p_body = "A punchy, easy-to-follow episode; we publish a new one every day."
        cta = "👉 Like & subscribe for more!"
        hashtags = "#shorts #story #news #crypto #ai"

    chapters = [
        "0:00 Intro",
        "0:05 Main beats",
        "0:50 Wrap-up"
    ]
    desc = textwrap.dedent(f"""\
        {p_intro}
        {p_body}

        Highlights:
        {bullets}

        Chapters:
        {chr(10).join(chapters)}

        {cta}

        {hashtags}
    """).strip()

    # Tags
    base_tags = [
        "shorts","daily","series", series.lower().replace(" ",""),
        "ai","auto","story" if mode_l=="story" else mode_l
    ]
    if mode_l=="crypto":
        base_tags += ["bitcoin","ethereum","solana","market","price","update"]
    elif mode_l=="news":
        base_tags += ["news","headlines","today"]
    tags = list(dict.fromkeys([t for t in base_tags if t]))[:18]

    return TitleMetadata(title=title, description=desc, captions=provided_caps, tags=tags)

# ---------- Orchestrator ----------
def generate_script(mode: str,
                    language: Optional[str] = None,
                    region: Optional[str] = None,
                    rss_url: Optional[str] = None,
                    coins: Optional[List[str]] = None,
                    coin_rows: Optional[List[Dict[str, Any]]] = None,
                    rss_limit: Optional[int] = None,
                    story_topic: Optional[str] = None,
                    **ignored: Any
                    ) -> Tuple[str, List[str], Optional[Dict[str, Dict[str, float]]]]:
    # Keep env fallbacks but force EN for story mode to disable TR variant.
    language = (language or _env("LANGUAGE", "en")).lower()
    _ = region or _env("REGION", "US")
    mode = (mode or _env("THEME", "story")).lower()

    if mode == "story":
        # Force English output regardless of env
        s, caps = make_script_story(story_topic, language="en")
        return s, caps, None

    if mode == "crypto":
        coins_list = coins or [c.strip() for c in (_env("CRYPTO_COINS","bitcoin,ethereum,solana") or "").split(",") if c.strip()]
        data = fetch_crypto_simple(coins_list)
        s, caps = make_script_crypto(data, language=language)
        return s, caps, data

    # news / sports via RSS
    url = rss_url or _env("RSS_URL", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
    heads = _rss_top_titles(url, n=6)
    if language.startswith("tr"):
        s, caps = make_script_news(heads, language="tr")
    else:
        s, caps = make_script_news(heads, language="en")
    return s, caps, None
