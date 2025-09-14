# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import re
import tempfile
import subprocess
import requests
from typing import List, Optional

def _get(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    return v if (v is not None and str(v).strip() != "") else default

def _openai_base_url() -> str:
    return (_get("OPENAI_BASE_URL", "https://api.openai.com/v1") or "https://api.openai.com/v1").rstrip("/")

def _openai_model_tts() -> str:
    return _get("OPENAI_MODEL_TTS", "gpt-4o-mini-tts") or "gpt-4o-mini-tts"

def _openai_tts_segment(text: str, voice: str, out_mp3_path: str) -> None:
    api_key = _get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")

    url = f"{_openai_base_url()}/audio/speech"
    payload = {"model": _openai_model_tts(), "input": text, "voice": voice, "format": "mp3"}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "audio/mpeg"}
    with requests.post(url, json=payload, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out_mp3_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

def _split_for_narration(full_text: str) -> List[str]:
    lines = []
    for raw in (full_text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        m = re.match(r"^\[(HOOK|CUT|TIP|CTA)\]\s*(.*)$", s, re.IGNORECASE)
        if m:
            spoken = m.group(2).strip()
            if spoken:
                lines.append(spoken)
    if not lines:
        lines = [full_text.strip()]
    return lines

def _mk_silence_mp3(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds == 0.0:
        seconds = 0.001
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{seconds:.3f}",
        "-q:a", "9",
        "-acodec", "libmp3lame",
        tmp.name,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return tmp.name

def _chain_atempo(val: float) -> str:
    val = float(val)
    if 0.5 <= val <= 2.0:
        return f"atempo={val:.3f}"
    filters = []
    if val <= 0:
        val = 1.0
    current = val
    while current > 2.0:
        filters.append("atempo=2.0")
        current /= 2.0
    while current < 0.5:
        filters.append("atempo=0.5")
        current /= 0.5
    filters.append(f"atempo={current:.3f}")
    return ",".join(filters)

def synth_tts_to_mp3(
    text: str,
    out_mp3: str,
    voice: str = "alloy",
    atempo: str | float = "1.0",
    bitrate: str = "128k",
) -> None:
    os.makedirs(os.path.dirname(out_mp3) or ".", exist_ok=True)

    try:
        atempo_val = float(atempo) if isinstance(atempo, str) else float(atempo)
    except Exception:
        atempo_val = 1.0

    segments = _split_for_narration(text)
    tmp_parts: List[str] = []

    for seg in segments:
        seg_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        seg_file.close()
        _openai_tts_segment(seg, voice, seg_file.name)
        tmp_parts.append(seg_file.name)
        # cümle arası kısa nefes: 80ms
        tmp_parts.append(_mk_silence_mp3(0.08))

    if len(tmp_parts) >= 2:
        try:
            os.remove(tmp_parts[-1])
        except Exception:
            pass
        tmp_parts = tmp_parts[:-1]

    concat_list = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    for p in tmp_parts:
        concat_list.write(f"file '{p}'\n")
    concat_list.close()

    combined = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    combined.close()

    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list.name,
        "-c", "copy",
        combined.name
    ]
    subprocess.run(cmd_concat, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    atempo_filter = _chain_atempo(atempo_val)
    cmd_final = [
        "ffmpeg", "-y",
        "-i", combined.name,
        "-filter:a", atempo_filter,
        "-b:a", bitrate,
        out_mp3
    ]
    subprocess.run(cmd_final, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
