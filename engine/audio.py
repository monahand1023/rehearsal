import os
import subprocess


def to_wav(src_path: str, dst_path: str | None = None, sample_rate: int = 16000) -> str:
    if dst_path is None:
        dst_path = os.path.splitext(src_path)[0] + ".converted.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, "-ac", "1", "-ar", str(sample_rate), dst_path],
        check=True, capture_output=True,
    )
    return dst_path
