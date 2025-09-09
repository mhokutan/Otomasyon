import subprocess
from pydub import AudioSegment

def get_duration_sec(mp3_path):
    audio = AudioSegment.from_file(mp3_path)
    return round(len(audio) / 1000, 2)

def mp3_to_vertical_mp4(mp3_path, mp4_out):
    dur = get_duration_sec(mp3_path)
    # Basit siyah arka plan + ses; dikey video
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={dur}",
        "-i", mp3_path,
        "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        mp4_out
    ]
    subprocess.run(cmd, check=True)
    return mp4_out
