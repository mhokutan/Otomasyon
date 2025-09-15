# -*- coding: utf-8 -*-
from __future__ import annotations
import os, random, time, textwrap, re
from typing import List, Tuple, Dict, Optional
import requests

try:
    import feedparser  # type: ignore
    _HAS_FEEDPARSER = True
except Exception:
    _HAS_FEEDPARSER = False
import xml.etree.ElementTree as ET

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def _now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

def _clean_text(s: str) -> str:
    return " ".join((s or "").replace("\r"," ").replace("\n"," ").split())

def _safe_first(items: List, n: int) -> List:
    return items[:n] if items else []

# ---------- OpenAI chat ----------
def _openai_base_url() -> str:
    return (_env("OPENAI_BASE_URL","https://api.openai.com/v1") or "https://api.openai.com/v1").rstrip("/")
def _openai_model_chat() -> str:
    return _env("OPENAI_MODEL_CHAT","gpt-4o-mini") or "gpt-4o-mini"
def _openai_temperature() -> float:
    try: return float(_env("OPENAI_TEMPERATURE","0.9") or "0.9")
    except: return 0.9
def _openai_max_tokens() -> int:
    try: return int(_env("OPENAI_MAX_TOKENS","600") or "600")
    except: return 600

def _openai_chat(messages: List[Dict[str,str]]) -> str:
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")
    url = f"{_openai_base_url()}/chat/completions"
    payload = {"model": _openai_model_chat(), "messages": messages,
               "temperature": _openai_temperature(), "max_tokens": _openai_max_tokens()}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=120); r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ---------- keyword extraction ----------
_TR_STOP = set("ve veya ile çünkü ama fakat hatta yani şu bu o bir birisi birşey hiç çok gibi kadar sonra önce yine ise diye daha pek ben sen o biz siz onlar mı mi mu mü da de ki ya".split())
_EN_STOP = set("the a an and or but so because as of to in on at for from with without about into over under after before by this that these those is are was were be been being have has had do does did can could should would will may might must if then than just not no yes it its it's they them he she we you i my your our their his her who whom which what when where why how".split())

def _extract_keywords(text: str, lang: str, topk: int = 12) -> List[str]:
    words = re.findall(r"[a-zA-ZğüşöçıİĞÜŞÖÇ0-9\-]+", (text or "").lower())
    stop = _TR_STOP if lang.startswith("tr") else _EN_STOP
    counts: Dict[str,int] = {}
    for w in words:
        if len(w) < 3: continue
        if w in stop: continue
        if w.startswith('['): continue
        counts[w] = counts.get(w, 0) + 1
    # genre kelimesi çok tekrar ederse onu da alalım
    out = sorted(counts, key=lambda k: (-counts[k], k))[:topk]
    # biraz “ambiyans” ekleyelim:
    ambiance = ["night","moody","dark","fog","mist","shadow","retro","ancient","ruins","castle","forest"]
    if lang.startswith("tr"):
        ambiance = ["gece","sis","gizemli","karanlık","eski","kalıntı","kale","orman","gölge"]
    for a in ambiance:
        if a not in out:
            out.append(a)
    return out[:topk]

# ---------- story mode ----------
def _pick_genre() -> str:
    raw = _env("STORY_GENRES","tarihsel gizem,esrarengiz olay,çözülmemiş korku,paranormal,şehir efsanesi") or ""
    items = [i.strip() for i in raw.split(",") if i.strip()]
    if not items:
        items = ["tarihsel gizem","esrarengiz olay","çözülmemiş korku"]
    seed = _env("STORY_SEED","")
    if seed: random.seed(seed)
    return random.choice(items)

def _make_story_script(language: str):
    lang = (language or "tr").lower()
    genre = _pick_genre()

    sys = ("You are a concise story writer for 60–75 second narrated shorts. "
           "Output MUST use labels: [ON SCREEN TEXT], [HOOK], [CUT] (x5), [CTA].")
    if lang.startswith("tr"):
        user = textwrap.dedent(f"""
        {genre} türünde 60–75 saniyelik kısa hikâye yaz.
        Dil: Türkçe, doğal ve akıcı anlatım.
        Etiketleri aynen kullan: [ON SCREEN TEXT], [HOOK], [CUT] x5, [CTA].
        5 CUT bloğu olsun; her biri 1-2 cümle.
        Aşırı rahatsız edici içerik verme; gerilim/gizem odaklı olsun.
        Sonda ufak bir twist ya da açık uç olabilir.
        """).strip()
    else:
        user = textwrap.dedent(f"""
        Write a {genre} short for 60–75 seconds.
        Language: English, natural spoken tone.
        Use EXACT labels: [ON SCREEN TEXT], [HOOK], [CUT] x5, [CTA].
        Keep it PG-13 suspense. Subtle twist welcome.
        """).strip()

    text = _openai_chat([{"role":"system","content":sys},{"role":"user","content":user}])

    # captions: HOOK + ilk 2-3 CUT
    caps: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s: continue
        if s.startswith("[HOOK]"):
            caps.append(s.replace("[HOOK]","").strip())
        elif s.startswith("[CUT]"):
            caps.append(s.replace("[CUT]","").strip())
        if len(caps) >= 4: break
    if not caps:
        caps = ["60 saniyelik hikâye"] if lang.startswith("tr") else ["60-second story"]

    # görsel arama için anahtar kelimeler
    keywords = _extract_keywords(text, lang, topk=12)
    meta = {"genre": genre, "language": lang, "keywords": keywords}
    return text, caps, meta

# ---------- legacy RSS (kalsın) ----------
def _rss_top_titles(url: str, n: int = 3) -> List[Tuple[str, str]]:
    titles: List[Tuple[str,str]] = []
    if _HAS_FEEDPARSER:
        feed = feedparser.parse(url)
        for e in _safe_first(getattr(feed,"entries",[]), n):
            t = _clean_text(getattr(e,"title","") or ""); l = getattr(e,"link","") or ""
            if t: titles.append((t,l))
        return titles
    r = requests.get(url, timeout=20); r.raise_for_status()
    root = ET.fromstring(r.content)
    for item in root.findall(".//item"):
        t=_clean_text(item.findtext("title") or ""); l=item.findtext("link") or ""
        if t: titles.append((t,l))
        if len(titles)>=n: return titles
    for ent in root.findall(".//{*}entry"):
        tnode=ent.find("{*}title"); lnode=ent.find("{*}link")
        t=_clean_text(tnode.text if (tnode is not None and tnode.text) else "")
        l=lnode.get("href") if lnode is not None else ""
        if t: titles.append((t,l))
        if len(titles)>=n: return titles
    return titles[:n]

# ---------- public API ----------
def generate_script(mode: str, language: Optional[str]=None, region: Optional[str]=None,
                    rss_url: Optional[str]=None, **ignored):
    m = (mode or _env("THEME","story")).lower()
    lang = (language or _env("LANGUAGE","tr")).lower()
    if m == "story":
        return _make_story_script(lang)  # (script, caps, meta)
    # fallback news
    url = rss_url or _env("RSS_URL","https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
    heads = _rss_top_titles(url, n=3)
    script = "[ON SCREEN TEXT] 60-second brief\n" + "\n".join([f"[CUT] {t}" for t,_ in heads])
    caps = [t for t,_ in heads][:3] or (["Günün kısa özeti"] if lang.startswith("tr") else ["Daily short brief"])
    return script, caps, {"genre":"news","language":lang,"keywords":["news","headline","today"]}

def build_titles(mode: str, captions: Optional[List[str]]=None, **ignored):
    m = (mode or "story").lower()
    lang = (_env("LANGUAGE","tr") or "tr").lower()
    ts = _now_ts()
    main = (captions[0] if captions else ("Kısa hikâye" if lang.startswith("tr") else "Short Story"))
    if lang.startswith("tr"):
        title_prefix = "Kısa Hikâye:" if m=="story" else "Günlük Özet:"
        desc = textwrap.dedent(f"""
            Otomatik üretilmiş kısa hikâye — {ts}

            Bölümler:
            0:00 Giriş / Hook
            0:05 Hikâye Akışı
            0:55 Kapanış

            #hikaye #korku #gizem #shorts #ai
        """).strip()
    else:
        title_prefix = "Short Story:" if m=="story" else "Daily Brief:"
        desc = textwrap.dedent(f"""
            Auto-generated short story — {ts}

            Chapters:
            0:00 Hook
            0:05 Story Beats
            0:55 Outro

            #story #horror #mystery #shorts #ai
        """).strip()

    title = f"{title_prefix} {main}"
    if len(title) > 95: title = title[:92] + "..."
    return title, desc
