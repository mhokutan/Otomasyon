import os, subprocess, tempfile, json, requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

def _openai_tts(text: str, voice: str, out_mp3: str):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")
    url = "https://api.openai.com/v1/audio/speech"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "tts-1",
        "voice": voice or "alloy",
        "input": text,
        "format": "mp3"
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"TTS error {r.status_code}: {r.text[:200]}")
    with open(out_mp3, "wb") as f:
        f.write(r.content)

def synth_tts_to_mp3(text: str, out_mp3: str, voice="alloy", atempo=1.4, gap_ms=10, bitrate="128k"):
    # Basic gap: replace "\n\n" with short pause textually – OpenAI handles punctuation well.
    txt = " ".join([t.strip() for t in text.splitlines() if t.strip()])
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_name = tmp.name
    _openai_tts(txt, voice, tmp_name)

    # Speed/pacing by ffmpeg atempo and re-encode target bitrate
    # (if atempo too high, quality may degrade)
    atempo = max(0.5, min(2.0, float(atempo)))
    subprocess.run([
        "ffmpeg","-y",
        "-i", tmp_name,
        "-af", f"atempo={atempo},loudnorm=I=-18:TP=-1.5:LRA=11",
        "-b:a", bitrate, "-ar", "44100", "-ac", "2",
        out_mp3
    ], check=True)
    try:
        os.unlink(tmp_name)
    except Exception:
        pass
