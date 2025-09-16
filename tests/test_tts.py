from pathlib import Path

import pytest

import tts


def test_synth_tts_to_mp3_with_mocked_openai(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    recorded_segments = []

    def fake_segment(text, voice, out_path):
        recorded_segments.append((text, voice))
        Path(out_path).write_bytes(f"SEG:{text}".encode("utf-8"))

    monkeypatch.setattr(tts, "_openai_tts_segment", fake_segment)

    def fake_silence(seconds):
        silence_path = tmp_path / f"silence_{seconds:.2f}.mp3"
        silence_path.write_bytes(b"SILENCE")
        return silence_path.as_posix()

    monkeypatch.setattr(tts, "_mk_silence_mp3", fake_silence)

    ffmpeg_calls = []

    def fake_run(cmd, check, stdout, stderr, **kwargs):
        ffmpeg_calls.append(cmd)
        out_file = Path(cmd[-1])
        out_file.write_bytes(b"FINAL")
        class Result:
            pass
        return Result()

    monkeypatch.setattr(tts.subprocess, "run", fake_run)

    out_mp3 = tmp_path / "narration.mp3"
    script_text = "\n".join([
        "[HOOK] Welcome to the show",
        "[CUT] Here is the update",
        "[CTA] See you soon",
    ])

    tts.synth_tts_to_mp3(
        script_text,
        out_mp3.as_posix(),
        voice="test-voice",
        atempo="1.25",
        gap_ms=250,
        bitrate="96k",
    )

    assert recorded_segments == [
        ("Welcome to the show", "test-voice"),
        ("Here is the update", "test-voice"),
        ("See you soon", "test-voice"),
    ]
    assert ffmpeg_calls, "Expected ffmpeg to be invoked"
    cmd = ffmpeg_calls[0]
    assert cmd[0] == "ffmpeg"
    assert "-af" in cmd
    atempo_arg = cmd[cmd.index("-af") + 1]
    assert "atempo" in atempo_arg
    assert out_mp3.exists()
    assert out_mp3.read_bytes() == b"FINAL"
