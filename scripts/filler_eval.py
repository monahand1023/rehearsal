import json
import os
import sys

from engine.audio import to_wav
from engine.transcribe import transcribe
from engine.fillers.lexicon import detect_lexicon_fillers
from engine.fillers.acoustic import detect_acoustic_fillers
from engine.fillers import merge_hits

SPIKE = os.path.join("tests", "fixtures", "spike")


def main():
    labels = json.load(open(os.path.join(SPIKE, "labels.json")))
    tot_true = tot_lex = tot_comb = 0
    print(f"{'file':16} {'expected':>8} {'lexicon':>8} {'combined':>9}")
    for item in labels:
        wav = to_wav(os.path.join(SPIKE, item["file"]))
        tr = transcribe(wav)
        lex = detect_lexicon_fillers(tr)
        comb = merge_hits(lex, detect_acoustic_fillers(tr, wav))
        tot_true += item["fillers"]
        tot_lex += len(lex)
        tot_comb += len(comb)
        print(f"{item['file']:16} {item['fillers']:>8} {len(lex):>8} {len(comb):>9}")
    lex_ratio = tot_lex / tot_true if tot_true else 0.0
    comb_ratio = tot_comb / tot_true if tot_true else 0.0
    print(f"\nExpected: {tot_true}")
    print(f"Lexicon detected:  {tot_lex}  (detected/expected = {lex_ratio:.2f})")
    print(f"Combined detected: {tot_comb}  (detected/expected = {comb_ratio:.2f})")


if __name__ == "__main__":
    sys.exit(main())
