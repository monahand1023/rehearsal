import json
import os
import sys

from engine.audio import to_wav
from engine.transcribe import transcribe
from engine.fillers import detect_fillers

SPIKE = os.path.join("tests", "fixtures", "spike")


def main():
    labels = json.load(open(os.path.join(SPIKE, "labels.json")))
    total_true = total_pred = 0
    print(f"{'file':16} {'expected':>8} {'detected':>8}")
    for item in labels:
        wav = to_wav(os.path.join(SPIKE, item["file"]))
        tr = transcribe(wav)
        rep = detect_fillers(tr)
        total_true += item["fillers"]
        total_pred += rep.count
        print(f"{item['file']:16} {item['fillers']:>8} {rep.count:>8}")
    recall_proxy = total_pred / total_true if total_true else 0.0
    print(f"\nTotal expected: {total_true}  detected: {total_pred}  "
          f"(detected/expected = {recall_proxy:.2f})")


if __name__ == "__main__":
    sys.exit(main())
