import subprocess, shlex, tempfile, os
from typing import List
from pydub import AudioSegment

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _dur_sec(mp3_path):
    audio = AudioSegment.from_file(mp3_path)
    return max(8, round(len(audio) / 1000))  # en az 8 sn

def _escape_drawtext(text: str) -> str:
    # ffmpeg drawtext için temel kaçışlar
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

def _make_slide(image_path: str, caption: str, duration: float, out_path: str):
    caption = _escape_drawtext(caption[:110])
    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=cover,"
        f"crop=1080:1920,"
        f"drawbox=x=0:y=60:w=iw:h=120:color=black@0.35:t=fill,"
        f"drawtext=fontfile='{FONT}':text='{caption}':fontcolor=white:fontsize=48:"
        f"borderw=2:bordercolor=black@0.6:x=(w-text_w)/2:y=90"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", f"{duration:.2f}", "-i", image_path,
        "-vf", vf,
        "-r", "30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        out_path
    ]
    subprocess.run(cmd, check=True)

def _concat_slides(slide_paths: List[str], audio_path: str, out_path: str):
    # Concat demuxer ile video birleştir, sonra tek adımda ses ekle
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        for p in slide_paths:
            f.write(f"file '{p}'\n")
        list_path = f.name
    try:
        # concat + ses ekle
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-i", audio_path,
            "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            out_path
        ]
        subprocess.run(cmd, check=True)
    finally:
        os.unlink(list_path)

def _overlay_waveform(in_mp4: str, out_mp4: str):
    # Varolan videonun sesinden waveform üretip altta overlay ediyoruz (200px yükseklik)
    cmd = [
        "ffmpeg", "-y",
        "-i", in_mp4,
        "-filter_complex",
        "[0:a]showwaves=s=1080x200:mode=cline:rate=30[wf];"
        "[0:v][wf]overlay=0:main_h-200-40,format=yuv420p",
        "-map", "0:v", "-map", "0:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "copy",
        "-movflags", "+faststart",
        out_mp4
    ]
    subprocess.run(cmd, check=True)

def make_slideshow_video(images: List[str], captions: List[str], audio_mp3: str, out_mp4: str):
    total = _dur_sec(audio_mp3)
    n = max(1, len(images))
    seg = max(6, total / n)  # her slayt en az 6 sn
    # Önce tek tek slaytlar
    slide_paths = []
    for idx, img in enumerate(images):
        slide_mp4 = f"/tmp/slide_{idx+1}.mp4"
        cap = captions[idx] if idx < len(captions) else ""
        _make_slide(img, cap, seg, slide_mp4)
        slide_paths.append(slide_mp4)
    # Slaytları birleştir + ses
    temp_concat = "/tmp/concat_with_audio.mp4"
    _concat_slides(slide_paths, audio_mp3, temp_concat)
    # Waveform overlay
    _overlay_waveform(temp_concat, out_mp4)
