# -*- coding: utf-8 -*-
"""
Helpers for the YouTube auto workflow (compat layer).

Exposed functions:
- generate_script(mode, language=None, region=None, rss_url=None, coins=None,
                  coin_rows=None, rss_limit=None, story_topic=None, **ignored)
    -> (script_text, captions_list, coins_data_or_none)

- build_titles(mode, captions=None, coins_data=None, title_prefix=None,
               coin_rows=None, headlines=None, **ignored)
    -> If coin_rows or headlines is provided: returns a captions LIST (compat).
       Else (classic usage with captions): returns (title, description) TUPLE.

- fetch_trends_tr(n=3)
- make_script_tr(headlines)
- make_script_crypto(coins_data, language="en")
- _fetch_headlines_from_rss(url, limit=3)
"""

from __future__ import annotations
import os
import time
import textwrap
from typing import List, Tuple, Dict, Optional, Any

import logging

import requests

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

def _fmt_usd(x: float) -> str:
    return f"${x:,.2f}"

def _fmt_pct(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f}%"

def _clean_text(s: str) -> str:
    return " ".join((s or "").replace("\r", " ").replace("\n", " ").split())

def _safe_first(items: List, n: int) -> List:
    return items[:n] if items else []

def _now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())


# ------------------ CRYPTO ------------------

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

def make_script_crypto(coins_data: Dict[str, Dict[str, float]], language: str = "en") -> Tuple[str, List[str]]:
    if not coins_data:
        if language.lower().startswith("tr"):
            return ("[ON SCREEN TEXT] Kripto özeti (veri alınamadı)\n[CTA] Takipte kal!",
                    ["Kripto özeti (veri alınamadı)"])
        return ("[ON SCREEN TEXT] 60-second crypto brief (no data)\n[CTA] Subscribe for daily briefs!",
                ["60-second crypto brief (no data)"])

    order_env = _env("CRYPTO_COINS", "bitcoin,ethereum,solana")
    order = [c.strip() for c in (order_env or "").split(",") if c.strip()]
    ordered = [c for c in order if c in coins_data] or list(coins_data.keys())

    lines: List[str] = []
    caps: List[str] = []

    if language.lower().startswith("tr"):
        lines.append("[ON SCREEN TEXT] Kripto Günlük Özeti")
        lines.append("[HOOK] Bitcoin, Ethereum ve seçili altcoinlerde son 24 saatin özeti!")
    else:
        lines.append("[ON SCREEN TEXT] 60-second crypto brief")
        lines.append("[HOOK] Bitcoin, Ethereum and top altcoins — here is your 60-second market brief!")

    for cid in ordered:
        d = coins_data[cid]
        name = cid.upper()
        price = _fmt_usd(d["usd"])
        pct = _fmt_pct(d["usd_24h_change"])
        if language.lower().startswith("tr"):
            dir_tr = "yukarı" if d["usd_24h_change"] >= 0 else "aşağı"
            line = f"[CUT] {name}: {price}, 24 saatte {pct} {dir_tr}."
        else:
            dir_en = "up" if d["usd_24h_change"] >= 0 else "down"
            line = f"[CUT] {name}: {price}, 24h {pct} {dir_en}."
        cap = f"{name}: {price} | 24h {pct}"
        lines.append(line)
        caps.append(cap)

    if language.lower().startswith("tr"):
        lines.append("[TIP] Yatırım tavsiyesi değildir. Volatiliteye dikkat.")
        lines.append("[CTA] Günlük kısa özet için abone ol!")
    else:
        lines.append("[TIP] Not financial advice. Mind the volatility.")
        lines.append("[CTA] Subscribe for a short daily brief!")

    return "\n".join(lines), caps


# ------------------ NEWS / SPORTS ------------------

def _rss_top_titles(url: str, n: int = 3) -> List[Tuple[str, str]]:
    titles: List[Tuple[str, str]] = []
    if _HAS_FEEDPARSER:
        try:
            feed = feedparser.parse(url)
        except Exception as exc:  # pragma: no cover - feedparser robustness
            logger.warning("RSS feedparser failed for %s: %s", url, exc)
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
        logger.warning("RSS request failed for %s: %s", url, exc)
        return titles

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        logger.warning("RSS XML parse failed for %s: %s", url, exc)
        return titles

    for item in root.findall(".//item"):
        t = _clean_text(item.findtext("title") or "")
        l = item.findtext("link") or ""
        if t:
            titles.append((t, l))
        if len(titles) >= n:
            return titles

    for ent in root.findall(".//{*}entry"):
        tnode = ent.find("{*}title")
        lnode = ent.find("{*}link")
        t = _clean_text(tnode.text if (tnode is not None and tnode.text) else "")
        l = ""
        if lnode is not None:
            l = lnode.get("href") or lnode.text or ""
        if t:
            titles.append((t, l))
        if len(titles) >= n:
            return titles

    return titles[:n]

def _fetch_headlines_from_rss(url: str, limit: int = 12) -> List[Tuple[str, str]]:
    return _rss_top_titles(url, n=limit)

def make_script_news(headlines: List[Tuple[str, str]], language: str = "en") -> Tuple[str, List[str]]:
    if not headlines:
        if language.lower().startswith("tr"):
            return ("[ON SCREEN TEXT] 60 saniyelik özet (haber bulunamadı)\n[CTA] Takipte kal!",
                    ["60 saniyelik özet (haber bulunamadı)"])
        return ("[ON SCREEN TEXT] 60-second brief (no headlines)\n[CTA] Subscribe for daily briefs!",
                ["60-second brief (no headlines)"])

    lines: List[str] = []
    caps: List[str] = []

    if language.lower().startswith("tr"):
        lines.append("[ON SCREEN TEXT] 60 saniyelik özet")
        lines.append(f"[HOOK] {headlines[0][0]} — haydi başlayalım!")
    else:
        lines.append("[ON SCREEN TEXT] 60-second brief")
        lines.append(f"[HOOK] {headlines[0][0]} — let’s go!")

    for i, (t, _) in enumerate(_safe_first(headlines, 3), start=1):
        lines.append(f"[CUT] {i}. {t}")
        caps.append(t)

    if language.lower().startswith("tr"):
        lines.append("[CUT] 10 saniye kaldı; kısaca: Günün gelişmelerini tarayıp en net başlıkları seçiyoruz.")
        lines.append("[CTA] Her gün yeni 1 dakikalık özet için abone ol!")
    else:
        lines.append("[CUT] 10 seconds left; quick recap: we track the day’s developments and pick the clearest headlines.")
        lines.append("[CTA] New 1-minute summaries every day—subscribe!")

    return "\n".join(lines), caps


# ------------------ (optional) STORY ------------------

def make_script_story(topic: Optional[str], language: str="en") -> Tuple[str, List[str]]:
    t = (topic or "mystery").strip()
    if language.lower().startswith("tr"):
        lines = [
            f"[ON SCREEN TEXT: \"{t.title()}\"]",
            f"[HOOK] {t.title()} temalı kısa bir hikâye: gizemli bir başlangıç...",
            "[CUT] Eski bir kitap, kapakta silik bir sembol.",
            "[CUT] Beklenmedik bir ziyaretçi ve açığa çıkan sır.",
            "[ON SCREEN TEXT: “Seçim Anı”]",
            "[CUT] Bir karar, iki kader.",
            "[CTA] Devamı için abone ol; her gün yeni kısa hikâyeler!"
        ]
    else:
        lines = [
            f"[ON SCREEN TEXT: \"{t.title()}\"]",
            f"[HOOK] A short {t} story: a mysterious beginning...",
            "[CUT] An old book, a faded sigil on the cover.",
            "[CUT] An unexpected visitor and a revealed secret.",
            "[ON SCREEN TEXT: “The Turning Point”]",
            "[CUT] One decision, two destinies.",
            "[CTA] Subscribe for daily short stories!"
        ]
    # captions
    caps = [
        f"{t.title()} — short story",
        "A mysterious beginning",
        "An unexpected visitor",
        "The turning point"
    ]
    return "\n".join(lines), caps


# ------------------ Titles / Descriptions ------------------

def _coins_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for r in rows or []:
        cid = str(r.get("id") or r.get("coin") or "").strip().lower()
        if not cid:
            continue
        try:
            usd = float(r.get("usd"))
            chg = float(r.get("usd_24h_change", 0.0))
        except Exception:
            continue
        out[cid] = {"usd": usd, "usd_24h_change": chg}
    return out

def build_titles(mode: str,
                 captions: Optional[List[str]] = None,
                 coins_data: Optional[Dict[str, Dict[str, float]]] = None,
                 title_prefix: Optional[str] = None,
                 coin_rows: Optional[List[Dict[str, Any]]] = None,
                 headlines: Optional[List[Tuple[str, str]]] = None,
                 **ignored: Any):
    mode_l = (mode or "").lower()

    if coin_rows is not None:
        data = _coins_from_rows(coin_rows)
        if not data:
            return []
        order_env = _env("CRYPTO_COINS", "bitcoin,ethereum,solana")
        order = [c.strip() for c in (order_env or "").split(",") if c.strip()]
        ordered = [c for c in order if c in data] or list(data.keys())
        caps = [f"{cid.upper()}: {_fmt_usd(data[cid]['usd'])} | 24h {_fmt_pct(data[cid]['usd_24h_change'])}"
                for cid in ordered]
        return caps

    if headlines is not None:
        return [t for (t, _link) in (headlines[:5] if headlines else [])]

    ts = _now_ts()
    if not title_prefix:
        title_prefix = {
            "crypto": "Daily Crypto Brief:",
            "sports": "Sports Brief:",
            "news": "Daily Brief:",
            "story": "Story:"
        }.get(mode_l, "Daily Brief:")

    main_part = (captions[0] if captions else
                 ("Crypto market update" if mode_l == "crypto" else
                  ("A short story" if mode_l == "story" else "Top headlines")))
    title = f"{title_prefix} {main_part}"
    if len(title) > 95:
        title = title[:92] + "..."

    if mode_l == "crypto" and coins_data:
        rows = []
        for cid, d in coins_data.items():
            rows.append(f"{cid.upper()}: {_fmt_usd(d['usd'])} ({_fmt_pct(d['usd_24h_change'])})")
        block = "\n".join(rows)
        desc = textwrap.dedent(f"""\
            Auto-generated {mode_l} video — {ts}

            Prices:
            {block}

            Chapters:
            0:00 Intro
            0:05 BTC / ETH / SOL
            0:45 Outro

            #crypto #bitcoin #ethereum #solana #ai #shorts
        """).strip()
    else:
        bullets = "\n".join([f"- {c}" for c in _safe_first(captions or [], 5)])
        desc = textwrap.dedent(f"""\
            Auto-generated {mode_l or 'news'} video — {ts}

            Highlights:
            {bullets}

            Chapters:
            0:00 Intro
            0:05 Key points
            0:45 Outro

            #news #sports #story #ai #shorts
        """).strip()

    return title, desc


# ------------------ Orchestrator ------------------

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
    language = (language or _env("LANGUAGE", "en")).lower()
    _ = region or _env("REGION", "US")
    mode = (mode or _env("THEME", "crypto")).lower()

    if mode == "story":
        s, caps = make_script_story(story_topic, language=language)
        return s, caps, None

    if mode == "crypto":
        if coin_rows:
            data = _coins_from_rows(coin_rows)
        else:
            coin_list = coins
            if not coin_list:
                coin_list = [c.strip() for c in (_env("CRYPTO_COINS", "bitcoin,ethereum,solana") or "").split(",") if c.strip()]
            data = fetch_crypto_simple(coin_list)
        script, caps = make_script_crypto(data, language=language)
        return script, caps, data

    # news/sports
    url = rss_url or _env("RSS_URL", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
    n = rss_limit or 3
    heads = _rss_top_titles(url, n=n)
    if language.startswith("tr"):
        script, caps = make_script_tr(heads)
    else:
        script, caps = make_script_news(heads, language="en")
    return script, caps, None


# Turkish helpers
def fetch_trends_tr(n: int = 3) -> List[Tuple[str, str]]:
    url = "https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr"
    return _rss_top_titles(url, n=n)

def make_script_tr(headlines: List[Tuple[str, str]]) -> Tuple[str, List[str]]:
    return make_script_news(headlines, language="tr")


if __name__ == "__main__":
    md = os.getenv("THEME", "crypto")
    script, caps, coins_data = generate_script(
        mode=md,
        language=os.getenv("LANGUAGE", "en"),
        region=os.getenv("REGION", "US"),
        rss_url=os.getenv("RSS_URL"),
        story_topic=os.getenv("STORY_TOPIC"),
    )
    title, desc = build_titles(md, captions=caps, coins_data=coins_data, title_prefix=os.getenv("VIDEO_TITLE_PREFIX"))
    print("SCRIPT:\n", script)
    print("\nCAPTIONS:", caps)
    print("\nTITLE:", title)
    print("\nDESC:\n", desc)