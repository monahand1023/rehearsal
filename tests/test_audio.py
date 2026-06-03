import os
import subprocess

from engine.audio import to_wav

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hello.wav")


def test_to_wav_produces_16k_mono(tmp_path):
    # Re-encode the fixture to a non-wav container, then convert back.
    src = tmp_path / "in.m4a"
    subprocess.run(["ffmpeg", "-y", "-i", FIXTURE, str(src)],
                   check=True, capture_output=True)
    out = to_wav(str(src), str(tmp_path / "out.wav"))
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=channels,sample_rate", "-of", "csv=p=0", out],
        check=True, capture_output=True, text=True,
    ).stdout
    fields = set(probe.strip().split(","))
    assert "16000" in fields   # 16kHz sample rate
    assert "1" in fields       # mono (exactly 1 channel)
