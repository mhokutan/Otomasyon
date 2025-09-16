import shutil
from pathlib import Path

import pytest
from PIL import Image

import video


def test_make_slideshow_video_uses_downloads_and_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    base_image = tmp_path / "base.jpg"
    Image.new("RGB", (200, 200), color=(10, 120, 200)).save(base_image)

    audio_mp3 = tmp_path / "audio.mp3"
    audio_mp3.write_bytes(b"fake audio")

    out_mp4 = tmp_path / "result.mp4"

    monkeypatch.setenv("BG_IMAGES_PER_SLIDE", "1")
    monkeypatch.setenv("FPS", "24")
    monkeypatch.setenv("TTS_BITRATE", "96k")

    def fake_ffprobe(path):
        assert path == audio_mp3.as_posix()
        return 9.0

    monkeypatch.setattr(video, "_ffprobe_duration", fake_ffprobe)

    def fake_bg_urls(theme, count, keywords=None, genre=None):
        assert theme == "news"
        assert count == 1
        return ["https://example.com/bg.jpg"]

    monkeypatch.setattr(video, "_bg_urls_for_theme", fake_bg_urls)

    download_requests = []

    def fake_download_many(urls):
        download_requests.append(list(urls))
        paths = []
        for idx, _ in enumerate(urls):
            tmp_img = tmp_path / f"dl_{idx}.jpg"
            shutil.copy(base_image, tmp_img)
            paths.append(tmp_img.as_posix())
        return paths

    monkeypatch.setattr(video, "_download_many", fake_download_many)

    png_calls = []

    def fake_png_to_video(png, duration, out_mp4_path, fps, zoom_per_sec):
        png_calls.append((png, duration, out_mp4_path, fps, zoom_per_sec))
        Path(out_mp4_path).write_text("video")

    monkeypatch.setattr(video, "_png_to_video", fake_png_to_video)

    concat_calls = []

    def fake_concat(parts, out_mp4_path):
        concat_calls.append((list(parts), out_mp4_path))
        Path(out_mp4_path).write_text("concat")

    monkeypatch.setattr(video, "_concat", fake_concat)

    mux_calls = []

    def fake_mux(video_mp4, audio_mp3_arg, final_out, bitrate):
        mux_calls.append((video_mp4, audio_mp3_arg, final_out, bitrate))
        Path(final_out).write_text("muxed")

    monkeypatch.setattr(video, "_mux", fake_mux)

    captions = ["Breaking update"]

    video.make_slideshow_video(
        images=[],
        captions=captions,
        audio_mp3=audio_mp3.as_posix(),
        out_mp4=out_mp4.as_posix(),
        theme="news",
    )

    assert download_requests == [["https://example.com/bg.jpg"]]
    assert png_calls, "Slides should render backgrounds"
    first_png_call = png_calls[0]
    assert Path(first_png_call[0]).suffix == ".png"
    assert pytest.approx(first_png_call[1], rel=1e-3) == 9.0
    assert first_png_call[3] == 24

    assert len(concat_calls) == 2
    assert mux_calls == [
        (concat_calls[-1][1], audio_mp3.as_posix(), out_mp4.as_posix(), "96k")
    ]
    assert out_mp4.exists()
    assert out_mp4.read_text() == "muxed"

    generated_pngs = list((tmp_path / "out").glob("*.png"))
    assert generated_pngs, "Expected rendered slide images"
