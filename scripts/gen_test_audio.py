import json
import os
import sys

from engine.tts.elevenlabs import ElevenLabsProvider

GEN_DIR = os.path.join("tests", "fixtures", "generated")

# Default to a stock ElevenLabs voice so only ELEVENLABS_API_KEY is required.
# Override with ELEVENLABS_VOICE_EN / ELEVENLABS_VOICE_JA if you prefer other voices.
os.environ.setdefault("ELEVENLABS_VOICE_EN", "21m00Tcm4TlvDq8ikWAM")  # Rachel (stock)
os.environ.setdefault("ELEVENLABS_VOICE_JA", "21m00Tcm4TlvDq8ikWAM")  # multilingual_v2 handles JP


def main():
    manifest = json.load(open(os.path.join(GEN_DIR, "manifest.json")))
    provider = ElevenLabsProvider()
    made = 0
    for entry in manifest:
        out = os.path.join(GEN_DIR, entry["id"] + ".mp3")
        if os.path.exists(out):
            print("skip (exists):", out)
            continue
        audio = provider.synthesize(entry["text"], entry["language"])
        with open(out, "wb") as f:
            f.write(audio)
        made += 1
        print(f"generated: {out} ({len(audio)} bytes)")
    print(f"\nDone. {made} new clip(s).")


if __name__ == "__main__":
    sys.exit(main())
