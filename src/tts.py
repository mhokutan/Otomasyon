# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import re
import shutil
import tempfile
import subprocess
from pathlib import Path
import requests
from typing import List, Optional


def _get(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    return v if (v is not None and str(v).strip() != "") else default


def _openai_base_url() -> str:
    return (
        _get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        or "https://api.openai.com/v1"
    ).rstrip("/")


def _openai_model_tts() -> str:
    return _get("OPENAI_MODEL_TTS", "gpt-4o-mini-tts") or "gpt-4o-mini-tts"


def _openai_tts_segment(text: str, voice: str, out_mp3_path: str) -> None:
    api_key = _get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")
    url = f"{_openai_base_url()}/audio/speech"
    payload = {
        "model": _openai_model_tts(),
        "input": text,
        "voice": voice,
        "format": "mp3",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    with requests.post(
        url, json=payload, headers=headers, stream=True, timeout=120
    ) as r:
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
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=24000:cl=mono",
        "-t",
        f"{seconds:.3f}",
        "-q:a",
        "9",
        "-acodec",
        "libmp3lame",
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
    gap_ms: int | str = 0,
    bitrate: str = "128k",
) -> None:
    """Generate a narration MP3 using OpenAI TTS.

    The historical implementation in this repository stopped halfway through,
    which meant the workflow always fell back to the silent MP3 generation.
    This implementation restores the intended behaviour: split the script into
    logical narration chunks, request speech for each chunk, optionally insert
    configurable gaps, and finally stitch the pieces together while applying
    the requested tempo and bitrate.
    """

    os.makedirs(os.path.dirname(out_mp3) or ".", exist_ok=True)

    try:
        atempo_val = float(atempo) if isinstance(atempo, str) else float(atempo)
    except Exception:
        atempo_val = 1.0

    try:
        gap_ms_val = int(gap_ms) if isinstance(gap_ms, str) else int(gap_ms)
    except Exception:
        gap_ms_val = 0
    gap_sec = max(0.0, gap_ms_val / 1000.0)

    narration_lines = [ln.strip() for ln in _split_for_narration(text) if ln.strip()]
    if not narration_lines:
        narration_lines = [text.strip() or " "]

    # Prepare silence clip once if we need inter-line gaps.
    silence_mp3: str | None = None
    if gap_sec > 0:
        silence_mp3 = _mk_silence_mp3(gap_sec)

    with tempfile.TemporaryDirectory(prefix="tts_") as tmpdir:
        concat_entries: List[Path] = []
        for idx, line in enumerate(narration_lines):
            seg_path = Path(tmpdir) / f"seg_{idx:03d}.mp3"
            _openai_tts_segment(line, voice, seg_path.as_posix())
            concat_entries.append(seg_path)

            if silence_mp3 and idx < len(narration_lines) - 1:
                gap_path = Path(tmpdir) / f"gap_{idx:03d}.mp3"
                shutil.copy(silence_mp3, gap_path)
                concat_entries.append(gap_path)

        if not concat_entries:
            # Shouldn't happen because we guard above, but keep a hard fallback.
            fallback_silence = _mk_silence_mp3(max(1.0, gap_sec))
            concat_entries.append(Path(fallback_silence))

        concat_list = Path(tmpdir) / "list.txt"
        with concat_list.open("w", encoding="utf-8") as f:
            for item in concat_entries:
                f.write(f"file '{item.as_posix()}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list.as_posix(),
            "-vn",
        ]

        filters: List[str] = []
        if abs(atempo_val - 1.0) > 1e-3:
            filters.append(_chain_atempo(atempo_val))
        if filters:
            cmd.extend(["-af", ",".join(filters)])

        cmd.extend(
            [
                "-c:a",
                "libmp3lame",
                "-b:a",
                bitrate,
                out_mp3,
            ]
        )

        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if silence_mp3:
        try:
            os.unlink(silence_mp3)
        except OSError:
            pass
