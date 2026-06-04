"""Offline batch reprocessing of saved S3 recordings.

The deployed cloud runs in "lite" mode (OpenAI Whisper only — no parselmouth prosody, no
acoustic filler detector). This script runs OFFLINE on a machine with the native audio deps
(ffmpeg + parselmouth + faster-whisper) over the recordings archived in S3, producing a
fuller `report_native.json` next to each clip: prosody (Expression), acoustic gap-fillers,
and a lite-vs-native filler comparison.

Purpose:
  1. Recover fillers that leave a true silence gap (the lite path can't — see fillers-spike.md).
  2. Add the prosody/Expression signal the lite path drops.
  3. Turn the son's REAL recordings into the labeled natural-speech dataset needed to build a
     transcript-independent filled-pause detector (the open problem — synthetic clips mislead).

This module never runs in Lambda; boto3 + the native pipeline are imported lazily so the
cloud deploy doesn't need them. Run: `python -m web.reprocess --limit 20`.
"""
import argparse
import json
import os
import tempfile

from engine.constants import LANG_JA, MODE_JAPANESE


def iter_audio_keys(client, bucket, prefix="recordings/", limit=None):
    """Yield audio object keys under the recordings prefix (paginated, oldest-first by key)."""
    token = None
    n = 0
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        resp = client.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if "/audio" in key and not key.endswith(".json"):
                yield key
                n += 1
                if limit and n >= limit:
                    return
        if not resp.get("IsTruncated"):
            return
        token = resp.get("NextContinuationToken")


def summarize(client, bucket, prefix="recordings/"):
    """One list pass: count audio recordings and how many have a report_native.json."""
    audio = native = 0
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        resp = client.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.endswith("report_native.json"):
                native += 1
            elif "/audio" in key:
                audio += 1
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return {"recordings": audio, "processed": native}


# Recordings present from smoke-testing on 2026-06-03 (synthetic ja_clean/ja_fillers TTS, not
# natural speech). Recordings beyond this are the son's real practice = useful tuning data.
SYNTHETIC_BASELINE = 8
# Minimum natural clips before it's worth building/validating the detector (precision-first).
BUILD_THRESHOLD = 25


def readiness(client, bucket):
    s = summarize(client, bucket)
    natural = max(0, s["recordings"] - SYNTHETIC_BASELINE)
    return {**s, "natural": natural, "ready": natural >= BUILD_THRESHOLD}


def _exists(client, bucket, key):
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def reprocess_one(client, bucket, audio_key, *, analyze=None, force=False):
    """Download one recording, run the full NATIVE analysis, and write report_native.json
    (encrypted) next to it. Idempotent: skips clips already done unless force=True. Returns a
    summary dict, or None if skipped."""
    base = audio_key.rsplit("/", 1)[0]
    native_key = f"{base}/report_native.json"
    if not force and _exists(client, bucket, native_key):
        return None

    ext = os.path.splitext(audio_key)[1] or ".webm"
    fd, path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        with open(path, "wb") as fh:
            client.download_fileobj(bucket, audio_key, fh)
        if analyze is None:
            from engine.report import analyze_answer
            analyze = analyze_answer
        os.environ["REHEARSAL_AUDIO_NATIVE"] = "true"   # real prosody + acoustic fillers
        report = analyze(path, "", language=LANG_JA, mode=MODE_JAPANESE, run_content=False)
    finally:
        os.unlink(path)

    body = json.dumps({"audio_key": audio_key, "report": report}, ensure_ascii=False)
    client.put_object(Bucket=bucket, Key=native_key, Body=body.encode("utf-8"),
                      ContentType="application/json", ServerSideEncryption="AES256")
    acoustic = sum(1 for h in report["fillers"]["hits"] if h.get("source") == "acoustic")
    return {"audio_key": audio_key, "native_fillers": report["fillers"]["count"],
            "acoustic_fillers": acoustic}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reprocess S3 recordings with the native pipeline.")
    ap.add_argument("--bucket", default=os.environ.get("REHEARSAL_RECORDINGS_BUCKET"))
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-west-2"))
    ap.add_argument("--limit", type=int, default=None, help="process at most N clips")
    ap.add_argument("--force", action="store_true", help="redo clips already processed")
    ap.add_argument("--dry-run", action="store_true", help="list what would be processed")
    ap.add_argument("--status", action="store_true",
                    help="report how many natural recordings have accumulated (readiness gate)")
    args = ap.parse_args(argv)
    if not args.bucket:
        ap.error("no bucket (set REHEARSAL_RECORDINGS_BUCKET or pass --bucket)")

    import boto3
    client = boto3.client("s3", region_name=args.region)

    if args.status:
        r = readiness(client, args.bucket)
        print(f"{r['recordings']} recordings ({r['processed']} processed); "
              f"~{r['natural']} beyond the {SYNTHETIC_BASELINE} synthetic test clips")
        if r["ready"]:
            print(f"READY: >= {BUILD_THRESHOLD} natural clips — time to build the filler detector "
                  f"(see docs/superpowers/specs/2026-06-03-filler-detector-plan.md).")
        else:
            print(f"waiting: {r['natural']}/{BUILD_THRESHOLD} natural recordings toward the detector.")
        return

    keys = list(iter_audio_keys(client, args.bucket, limit=args.limit))
    print(f"{len(keys)} recording(s) under s3://{args.bucket}/recordings/")
    if args.dry_run:
        for k in keys:
            print("  would process:", k)
        return

    done = skipped = total_acoustic = 0
    for key in keys:
        result = reprocess_one(client, args.bucket, key, force=args.force)
        if result is None:
            skipped += 1
            continue
        done += 1
        total_acoustic += result["acoustic_fillers"]
        print(f"  {key}: {result['native_fillers']} fillers "
              f"(+{result['acoustic_fillers']} acoustic)")
    print(f"done: {done} processed, {skipped} already done, "
          f"{total_acoustic} acoustic fillers recovered across the batch")


if __name__ == "__main__":
    main()
