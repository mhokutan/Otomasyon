# src/scriptgen.py
import os, json, requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_MODEL_CHAT", "gpt-4o-mini")
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "400"))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

def _require_key():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")

def chat_complete(messages):
    """
    Ucuz chat modeli ile tamamlanma alır.
    messages: [{"role":"system"|"user"|"assistant", "content":"..."}]
    """
    _require_key()
    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_CHAT_MODEL,
        "messages": messages,
        "temperature": OPENAI_TEMPERATURE,
        "max_tokens": OPENAI_MAX_TOKENS,
    }
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
    if resp.status_code >= 400:
        raise RuntimeError(f"Chat HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()

# ÖRNEK yardımcılar (mevcut main.py’niz nasıl çağırıyorsa benzer imzalar bırakın)
def make_script_en(headlines):
    """
    headlines: ["Title 1", "Title 2", ...]
    """
    bullet = "\n".join([f"- {h}" for h in headlines[:3]]) or "- Headline"
    messages = [
        {"role":"system","content":"You write tight 60-second scripts for vertical videos. Concise, energetic, in English."},
        {"role":"user","content": f"Turn these headlines into a 60-second punchy script:\n{bullet}\nKeep it brisk."}
    ]
    return chat_complete(messages)

def make_script_crypto(snapshot):
    """
    snapshot: dict, örn: {"BTC": {"price": 111000.0, "pct24h": -0.4}, ...}
    """
    lines = []
    for sym, d in list(snapshot.items())[:3]:
        lines.append(f"{sym}: ${d['price']:.2f}, 24h {d['pct24h']:+.2f}%")
    body = "\n".join(lines) or "BTC: $100.00, 24h +0.00%"
    messages = [
        {"role":"system","content":"You write brisk 60-second crypto briefs in English. No advice."},
        {"role":"user","content": f"Make a 60s voiceover script from:\n{body}\nInclude a short disclaimer at end (not financial advice)."}
    ]
    return chat_complete(messages)
