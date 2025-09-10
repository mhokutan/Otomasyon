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
    voice: str = "verse",     # "alloy", "ash", "sage", "verse" vb.
    bitrate: str = "128k",
    atempo: float | None = None,  # 1.00 normal; <1 yavaş; >1 hızlı
):
    """
    Verilen metni ucuz TTS modeliyle MP3'e çevirir, sabit bitrate'e normalize eder
    ve istenirse hızını (tempo) değiştirir.
    """
    _require_key()
    if atempo is None:
        # GitHub Actions env’den kontrol edilebilir
        atempo = float(os.getenv("OPENAI_TTS_ATEMPO", "1.00"))

    # --- 1) OpenAI Audio/Speech ile mp3 al ---
    url = f"{OPENAI_BASE_URL}/audio/speech"
    payload = {
        "model": OPENAI_TTS_MODEL,
        "voice": voice,
        "input": text,
        "format": "mp3",
    }
    resp = _post_json(url, payload)

    # Geçici dosya yolları
    fd_raw, tmp_mp3_raw = tempfile.mkstemp(suffix=".mp3")
    os.write(fd_raw, resp.content)
    os.close(fd_raw)

    tmp_norm = tempfile.mktemp(suffix=".mp3")
    tmp_out  = tempfile.mktemp(suffix=".mp3")

    try:
        # --- 2) Sabit bitrate’e normalize et ---
        norm_cmd = [
            "ffmpeg", "-y",
            "-i", tmp_mp3_raw,
            "-acodec", "libmp3lame",
            "-b:a", bitrate,
            tmp_norm,
        ]
        subprocess.run(norm_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # --- 3) Tempo ayarı (0.5–2.0 aralığı tek filtredir) ---
        if abs(atempo - 1.0) < 1e-3:
            # Hız değiştirmeden direkt çıktıya yaz
            shutil.move(tmp_norm, out_mp3)
        else:
            # atempo zinciri: 0.5–2.0 dışına çıkarsanız bölüp zincirleyin (gerek yok genelde)
            tempo_cmd = [
                "ffmpeg", "-y",
                "-i", tmp_norm,
                "-filter:a", f"atempo={atempo:.3f}",
                "-acodec", "libmp3lame",
                "-b:a", bitrate,
                tmp_out,
            ]
            subprocess.run(tempo_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            shutil.move(tmp_out, out_mp3)

    finally:
        for p in (tmp_mp3_raw, tmp_norm, tmp_out):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
