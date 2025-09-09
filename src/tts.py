import os, io, re
from gtts import gTTS
from pydub import AudioSegment
from pydub.effects import speedup

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

def script_to_mp3(text, out_path, lang="tr"):
    gap_ms = int(os.getenv("TTS_GAP_MS", "80"))          # cümleler arası boşluk
    speed  = float(os.getenv("TTS_SPEED", "1.12"))        # 1.12 ≈ %12 hızlı
    bitrate = os.getenv("TTS_BITRATE", "128k")            # çıktı bitrate

    chunks = split_for_tts(text)
    final = AudioSegment.silent(duration=200)
    for ch in chunks:
        tts = gTTS(ch, lang=lang)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        seg = AudioSegment.from_file(buf, format="mp3")
        final += seg + AudioSegment.silent(duration=gap_ms)

    # Standart ses parametreleri (uyumluluk):
    final = final.set_frame_rate(44100).set_channels(2)

    # Hızlandır (pitch’i koruyacak şekilde)
    if abs(speed - 1.0) > 0.01:
        final = speedup(final, playback_speed=speed, chunk_size=50, crossfade=20)

    final.export(out_path, format="mp3", bitrate=bitrate)
    return out_path
