# -*- coding: utf-8 -*-
"""
Script/text generation helpers for the YouTube auto workflow.

Provides:
- generate_script(mode, language, region, rss_url=None, coins=None)
- build_titles(mode, captions, coins_data=None, title_prefix="...")
- fetch_trends_tr(n=3)
- make_script_tr(headlines)
- make_script_crypto(coins_data, language="en")

No external API keys required (CoinGecko + RSS).
"""

from __future__ import annotations
import os
import time
import json
import math
import html
import textwrap
from typing import List, Tuple, Dict, Optional

import requests

# Optional feedparser (nicer RSS); falls back to xml if not installed.
try:
    import feedparser  # type: ignore
    _HAS_FEEDPARSER = True
except Exception:
    _HAS_FEEDPARSER = False
import xml.etree.ElementTree as ET


# -----------------------------
# Utilities
# -----------------------------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if (val is not None and str(val).strip() != "") else default

def _fmt_usd(x: float) -> str:
    return f"${x:,.2f}"

def _fmt_pct(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f}%"

def _clean_text(s: str) -> str:
    """Keep for captions; avoid weird newlines or control chars."""
    s = s.replace("\r", " ").replace("\n", " ").strip()
    return " ".join(s.split())

def _safe_first(items: List, n: int) -> List:
    return items[:n] if items else []

def _now_ts() -> str:
    # yyyy-mm-dd HH:MM (UTC)
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())


# -----------------------------
# Crypto (CoinGecko)
# -----------------------------

def fetch_crypto_simple(coin_ids: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Returns: {coin_id: {"usd": float, "usd_24h_change": float}}
    """
    ids = ",".join(coin_ids)
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    out: Dict[str, Dict[str, float]] = {}
    for cid in coin_ids:
        if cid in data and "usd" in data[cid]:
            price = float(data[cid]["usd"])
            chg = float(data[cid].get("usd_24h_change", 0.0))
            out[cid] = {"usd": price, "usd_24h_change": chg}
    return out


def make_script_crypto(coins_data: Dict[str, Dict[str, float]], language: str = "en") -> Tuple[str, List[str]]:
    """
    Returns:
      script_text (str),
      captions (List[str])  -> slide captions for video
    """
    if not coins_data:
        # fallback line
        if language.lower().startswith("tr"):
            return ("[ON SCREEN TEXT] Kripto özeti (veri alınamadı)\n[CTA] Takipte kal!",
                    ["Kripto özeti (veri alınamadı)"])
        return ("[ON SCREEN TEXT] 60-second crypto brief (no data)\n[CTA] Subscribe for daily briefs!",
                ["60-second crypto brief (no data)"])

    # order coins by our preference, not alphabetic
    order = _env("CRYPTO_COINS", "bitcoin,ethereum,solana").split(",")
    ordered = [c.strip() for c in order if c.strip() in coins_data] or list(coins_data.keys())

    lines = []
    captions = []

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
            line = f"[CUT] {name}: {price}, 24 saatte %{d['usd_24h_change']:.2f} {'yukarı' if d['usd_24h_change']>=0 else 'aşağı'}."
            cap = f"{name}: {price} | 24h {pct}"
        else:
            dir_word = "up" if d["usd_24h_change"] >= 0 else "down"
            line = f"[CUT] {name}: {price}, 24h {pct} {dir_word}."
            cap = f"{name}: {price} | 24h {pct}"
        lines.append(line)
        captions.append(cap)

    if language.lower().startswith("tr"):
        lines.append("[TIP] Yatırım tavsiyesi değildir. Volatiliteye dikkat.")
        lines.append("[CTA] Günlük kısa özet için abone ol!")
    else:
        lines.append("[TIP] Not financial advice. Mind the volatility.")
        lines.append("[CTA] Subscribe for a short daily brief!")

    return ("\n".join(lines), captions)


# -----------------------------
# News / Sports via RSS
# -----------------------------

def _rss_top_titles(url: str, n: int = 3) -> List[Tuple[str, str]]:
    """
    Returns list of (title, link)
    """
    titles: List[Tuple[str, str]] = []
    if _HAS_FEEDPARSER:
        feed = feedparser.parse(url)
        for e in _safe_first(feed.entries, n):
            t = _clean_text(getattr(e, "title", "") or "")
            lnk = getattr(e, "link", "") or ""
            if t:
                titles.append((t, lnk))
        return titles

    # Fallback minimal XML parsing
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    # Google News uses atom/rss; try both:
    # Find all item/title + link or entry/title + link
    for item in root.findall(".//item"):
        t = item.findtext("title") or ""
        l = item.findtext("link") or ""
        t = _clean_text(t)
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


def make_script_news(headlines: List[Tuple[str, str]], language: str = "en") -> Tuple[str, List[str]]:
    if not headlines:
        if language.lower().startswith("tr"):
            return ("[ON SCREEN TEXT] 60 saniyelik özet (haber bulunamadı)\n[CTA] Takipte kal!",
                    ["60 saniyelik özet (haber bulunamadı)"])
        return ("[ON SCREEN TEXT] 60-second brief (no headlines)\n[CTA] Subscribe for daily briefs!",
                ["60-second brief (no headlines)"])

    lines = []
    caps = []
    if language.lower().startswith("tr"):
        lines.append("[ON SCREEN TEXT] 60 saniyelik özet")
        hook = f"[HOOK] {headlines[0][0]} — haydi başlayalım!"
    else:
        lines.append("[ON SCREEN TEXT] 60-second brief")
        hook = f"[HOOK] {headlines[0][0]} — let’s go!"
    lines.append(hook)

    for i, (t, _) in enumerate(_safe_first(headlines, 3), start=1):
        lines.append(f"[CUT] {i}. {t}")
        caps.append(t)

    if language.lower().startswith("tr"):
        lines.append("[CUT] 10 saniye kaldı; kısaca: Günün gelişmelerini tarayıp en net başlıkları seçiyoruz.")
        lines.append("[CTA] Her gün yeni 1 dakikalık özet için abone ol!")
    else:
        lines.append("[CUT] 10 seconds left; quick recap: we track the day’s developments and pick the clearest headlines.")
        lines.append("[CTA] New 1-minute summaries every day—subscribe!")

    return ("\n".join(lines), caps)


# -----------------------------
# Turkish helpers kept for backward compatibility
# -----------------------------

def fetch_trends_tr(n: int = 3) -> List[Tuple[str, str]]:
    """Top 3 TR headlines via Google News TR general feed."""
    url = "https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr"
    return _rss_top_titles(url, n=n)

def make_script_tr(headlines: List[Tuple[str, str]]) -> Tuple[str, List[str]]:
    """Old TR script maker used in earlier versions."""
    return make_script_news(headlines, language="tr")


# -----------------------------
# Title / Description builders
# -----------------------------

def build_titles(mode: str,
                 captions: List[str],
                 coins_data: Optional[Dict[str, Dict[str, float]]] = None,
                 title_prefix: Optional[str] = None) -> Tuple[str, str]:
    """
    Returns (title, description)
    """
    ts = _now_ts()
    mode_lower = (mode or "").lower()
    if not title_prefix:
        if mode_lower == "crypto":
            title_prefix = "Daily Crypto Brief:"
        elif mode_lower == "sports":
            title_prefix = "Sports Brief:"
        else:
            title_prefix = "Daily Brief:"

    # Title
    main_part = captions[0] if captions else ("Crypto market update" if mode_lower == "crypto" else "Top headlines")
    title = f"{title_prefix} {main_part}"

    # Description
    if mode_lower == "crypto" and coins_data:
        parts = []
        for cid, d in coins_data.items():
            parts.append(f"{cid.upper()}: {_fmt_usd(d['usd'])} ({_fmt_pct(d['usd_24h_change'])})")
        block = "\n".join(parts)
        desc = textwrap.dedent(f"""\
            Auto-generated {mode_lower} video — {ts}

            Prices:
            {block}

            Chapters:
            0:00 Intro
            0:05 BTC / ETH / SOL
            0:45 Outro

            #crypto #bitcoin #ethereum #solana #ai #shorts
        """).strip()
    else:
        bullets = "\n".join([f"- {c}" for c in _safe_first(captions, 5)])
        desc = textwrap.dedent(f"""\
            Auto-generated {mode_lower or 'news'} video — {ts}

            Headlines:
            {bullets}

            Chapters:
            0:00 Intro
            0:05 Top 3 headlines
            0:45 Outro

            #news #sports #ai #shorts
        """).strip()

    # YouTube max title length ~100; keep it tidy
    if len(title) > 95:
        title = title[:92] + "..."
    return title, desc


# -----------------------------
# Orchestrator
# -----------------------------

def generate_script(mode: str,
                    language: Optional[str] = None,
                    region: Optional[str] = None,
                    rss_url: Optional[str] = None,
                    coins: Optional[List[str]] = None
                    ) -> Tuple[str, List[str], Optional[Dict[str, Dict[str, float]]]]:
    """
    High-level entry:
      - mode: "crypto" | "news" | "sports"
      - returns (script_text, captions, coins_data_or_None)
    """
    language = (language or _env("LANGUAGE", "en")).lower()
    region = region or _env("REGION", "US")
    mode = (mode or _env("THEME", "crypto")).lower()

    if mode == "crypto":
        coin_list = coins or [c.strip() for c in _env("CRYPTO_COINS", "bitcoin,ethereum,solana").split(",") if c.strip()]
        data = fetch_crypto_simple(coin_list)
        script, caps = make_script_crypto(data, language=language)
        return script, caps, data

    # news or sports -> RSS
    url = rss_url or _env("RSS_URL", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
    heads = _rss_top_titles(url, n=3)

    # language switch
    if language.startswith("tr"):
        script, caps = make_script_tr(heads)
    else:
        script, caps = make_script_news(heads, language="en")

    return script, caps, None


# -----------------------------
# CLI (for quick local tests)
# -----------------------------

if __name__ == "__main__":
    md = os.getenv("THEME", "crypto")
    script, caps, coins_data = generate_script(
        mode=md,
        language=os.getenv("LANGUAGE", "en"),
        region=os.getenv("REGION", "US"),
        rss_url=os.getenv("RSS_URL"),
    )
    title, desc = build_titles(md, caps, coins_data, title_prefix=os.getenv("VIDEO_TITLE_PREFIX"))
    print("SCRIPT:\n", script)
    print("\nCAPTIONS:", caps)
    print("\nTITLE:", title)
    print("\nDESC:\n", desc)
