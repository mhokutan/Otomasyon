import os, io, re, tempfile, subprocess
from gtts import gTTS
from pydub import AudioSegment

def split_for_tts(text, max_chars=200):
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) <= max_chars:
            chunks.append(p)
        else:
            s = 0
            while s < len(p):
                chunks.append(p[s:s+max_chars])
                s += max_chars
    return chunks

def _ffmpeg_atempo(in_path: str, out_path: str, atempos: str, bitrate: str):
    """
    atempos: '1.25' ya da '1.25,1.15' gibi virgüllü liste (FFmpeg zincirlenir)
    """
    filters = ",".join([f"atempo={v.strip()}" for v in atempos.split(",") if v.strip()])
    cmd = [
        "ffmpeg", "-y",
        "-i", in_path,
        "-filter:a", filters,
        "-ar", "44100", "-ac", "2", "-b:a", bitrate,
        out_path
    ]
    subprocess.run(cmd, check=True)

def script_to_mp3(text, out_path, lang="tr"):
    gap_ms = int(os.getenv("TTS_GAP_MS", "40"))          # cümle arası daha kısa boşluk
    atempos = os.getenv("TTS_ATEMPO", "1.25")            # 1.25 ≈ %25 daha hızlı
    bitrate = os.getenv("TTS_BITRATE", "128k")

    chunks = split_for_tts(text)
    final = AudioSegment.silent(duration=150)
    for ch in chunks:
        tts = gTTS(ch, lang=lang)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        seg = AudioSegment.from_file(buf, format="mp3")
        final += seg + AudioSegment.silent(duration=gap_ms)

    # Standart parametreler
    final = final.set_frame_rate(44100).set_channels(2)

    # Geçici dosyaya yaz
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = tmp.name
    final.export(tmp_path, format="mp3", bitrate=bitrate)

    # FFmpeg atempo zinciri ile hızlandır (pitch korunur)
    _ffmpeg_atempo(tmp_path, out_path, atempos, bitrate)

    return out_path
