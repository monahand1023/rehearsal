import os
import subprocess


def probe_duration(path: str) -> float:
    """Seconds of audio in a file, via ffprobe. Returns 0.0 if it can't be read
    (e.g. a non-audio upload), so callers can reject/short-circuit safely."""
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", path],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def to_wav(src_path: str, dst_path: str | None = None, sample_rate: int = 16000) -> str:
    if dst_path is None:
        dst_path = os.path.splitext(src_path)[0] + ".converted.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, "-ac", "1", "-ar", str(sample_rate), dst_path],
        check=True, capture_output=True,
    )
    return dst_path
