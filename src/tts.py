# src/tts.py
import os, json, requests, tempfile, subprocess, shutil

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_TTS_MODEL = os.getenv("OPENAI_MODEL_TTS", "gpt-4o-mini-tts")

def _require_key():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")

def _post_json(url: str, payload: dict) -> requests.Response:
    _require_key()
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
    if resp.status_code >= 400:
        raise RuntimeError(f"TTS HTTP {resp.status_code}: {resp.text}")
    return resp

def synth_tts_to_mp3(
    text: str,
    out_mp3: str,
    voice: str = "verse",     # "alloy", "ash", "sage", "verse" vb. — maliyeti etkilemez
    bitrate: str = "128k",
):
    """
    Verilen metni ucuz TTS modeliyle MP3'e çevirir.
    """
    _require_key()
    # 1) OpenAI Audio/Speech ile ikili (binary) ses al
    url = f"{OPENAI_BASE_URL}/audio/speech"
    payload = {
        "model": OPENAI_TTS_MODEL,
        "voice": voice,
        "input": text,
        "format": "mp3",
    }
    resp = _post_json(url, payload)

    # 2) MP3'i dosyaya yaz
    tmp_fd, tmp_mp3 = tempfile.mkstemp(suffix=".mp3")
    try:
        os.write(tmp_fd, resp.content)
        os.close(tmp_fd)

        # 3) Sabit bitrate’e normalize et (GitHub Actions ortamında uyum için)
        # (Zaten mp3 gelse de, tek tip dosya üretmek için ffmpeg ile geçelim)
        cmd = [
            "ffmpeg", "-y",
            "-i", tmp_mp3,
            "-acodec", "libmp3lame",
            "-b:a", bitrate,
            out_mp3,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        try:
            os.remove(tmp_mp3)
        except Exception:
            pass
