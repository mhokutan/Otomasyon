from gtts import gTTS
from pydub import AudioSegment
import io, re

def split_for_tts(text, max_chars=200):
    # Noktalamaya göre parçalayıp çok uzunsa böl
    parts = re.split(r'(?<=[.!?])\\s+', text.strip())
    chunks = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) <= max_chars:
            chunks.append(p)
        else:
            # kaba bölme
            s = 0
            while s < len(p):
                chunks.append(p[s:s+max_chars])
                s += max_chars
    return chunks

def script_to_mp3(text, out_path, lang="tr"):
    chunks = split_for_tts(text)
    final = AudioSegment.silent(duration=300)
    for ch in chunks:
        tts = gTTS(ch, lang=lang)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        seg = AudioSegment.from_file(buf, format="mp3")
        final += seg + AudioSegment.silent(duration=150)
    final.export(out_path, format="mp3")
    return out_path
