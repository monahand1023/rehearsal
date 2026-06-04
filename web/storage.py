import json
import os
import uuid
from datetime import datetime, timezone

# Optional: when REHEARSAL_RECORDINGS_BUCKET is set, each practice attempt's audio +
# transcript + feedback is written to that private S3 bucket (for review + training).
# Unset (local default) = save nothing, fully stateless.

CONTENT_TYPES = {
    ".webm": "audio/webm", ".mp4": "audio/mp4", ".m4a": "audio/mp4",
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg",
}


def recordings_bucket():
    return os.environ.get("REHEARSAL_RECORDINGS_BUCKET") or None


def save_attempt(audio_bytes: bytes, suffix: str, report: dict, *,
                 mode: str = "", language: str = "", client=None, now=None) -> str | None:
    """Write audio + report JSON to S3 under recordings/<date>/<time>-<id>/. Returns the
    key prefix, or None when storage is disabled. boto3 is imported lazily (the Lambda
    runtime provides it; local skips it because the bucket is unset)."""
    bucket = recordings_bucket()
    if not bucket:
        return None
    if client is None:
        import boto3
        client = boto3.client("s3")
    now = now or datetime.now(timezone.utc)
    prefix = f"recordings/{now:%Y-%m-%d}/{now:%H%M%S}-{uuid.uuid4().hex[:8]}"
    client.put_object(
        Bucket=bucket, Key=f"{prefix}/audio{suffix}", Body=audio_bytes,
        ContentType=CONTENT_TYPES.get(suffix, "application/octet-stream"),
        ServerSideEncryption="AES256",  # encrypt at rest (also enforced at the bucket)
    )
    meta = {"saved_at": now.isoformat(), "mode": mode, "language": language, "report": report}
    client.put_object(
        Bucket=bucket, Key=f"{prefix}/report.json",
        Body=json.dumps(meta, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )
    return prefix
