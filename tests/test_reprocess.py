from web.reprocess import iter_audio_keys, reprocess_one, summarize, readiness, SYNTHETIC_BASELINE


class FakeS3:
    """Minimal in-memory S3 stand-in: paginated list, download, put, head."""

    def __init__(self, objects, pages=None):
        self.objects = dict(objects)        # key -> bytes
        self.pages = pages                  # optional list of list_objects_v2 responses
        self._page_i = 0
        self.put = {}                       # key -> {"Body":..., "SSE":...}

    def list_objects_v2(self, **kw):
        if self.pages is not None:
            resp = self.pages[self._page_i]
            self._page_i += 1
            return resp
        contents = [{"Key": k} for k in sorted(self.objects)]
        return {"Contents": contents, "IsTruncated": False}

    def download_fileobj(self, bucket, key, fh):
        fh.write(self.objects[key])

    def head_object(self, Bucket, Key):
        if Key not in self.objects and Key not in self.put:
            raise Exception("NoSuchKey")
        return {}

    def put_object(self, Bucket, Key, Body, **kw):
        self.objects[Key] = Body
        self.put[Key] = {"Body": Body, "SSE": kw.get("ServerSideEncryption")}


def test_iter_audio_keys_filters_and_paginates():
    pages = [
        {"Contents": [{"Key": "recordings/2026-06-01/aaa/audio.webm"},
                      {"Key": "recordings/2026-06-01/aaa/report.json"}],
         "IsTruncated": True, "NextContinuationToken": "t1"},
        {"Contents": [{"Key": "recordings/2026-06-02/bbb/audio.mp4"},
                      {"Key": "recordings/2026-06-02/bbb/report_native.json"}],
         "IsTruncated": False},
    ]
    s3 = FakeS3({}, pages=pages)
    keys = list(iter_audio_keys(s3, "bkt"))
    assert keys == ["recordings/2026-06-01/aaa/audio.webm",
                    "recordings/2026-06-02/bbb/audio.mp4"]   # only audio, both pages


def test_iter_audio_keys_respects_limit():
    objs = {f"recordings/d/{i}/audio.webm": b"x" for i in range(5)}
    s3 = FakeS3(objs)
    assert len(list(iter_audio_keys(s3, "bkt", limit=2))) == 2


def test_reprocess_one_writes_encrypted_native_report():
    s3 = FakeS3({"recordings/2026-06-01/aaa/audio.webm": b"AUDIObytes"})
    captured = {}

    def fake_analyze(path, q, language="ja", mode="japanese", run_content=False):
        with open(path, "rb") as f:
            captured["bytes"] = f.read()        # the downloaded audio reached analyze
        return {"fillers": {"count": 2, "hits": [
            {"text": "あの", "source": "lexicon"},
            {"text": "(uh)", "source": "acoustic"}]}}

    out = reprocess_one(s3, "bkt", "recordings/2026-06-01/aaa/audio.webm",
                        analyze=fake_analyze)
    assert captured["bytes"] == b"AUDIObytes"
    assert out["native_fillers"] == 2
    assert out["acoustic_fillers"] == 1
    written = s3.put["recordings/2026-06-01/aaa/report_native.json"]
    assert written["SSE"] == "AES256"          # encrypted at rest like the originals


def test_summarize_counts_audio_and_processed():
    objs = {
        "recordings/d/a/audio.webm": b"x", "recordings/d/a/report.json": b"{}",
        "recordings/d/a/report_native.json": b"{}",        # processed
        "recordings/d/b/audio.mp4": b"x", "recordings/d/b/report.json": b"{}",
    }
    s = summarize(FakeS3(objs), "bkt")
    assert s == {"recordings": 2, "processed": 1}


def test_readiness_gate():
    # Below the synthetic baseline + threshold -> not ready.
    objs = {f"recordings/d/{i}/audio.webm": b"x" for i in range(SYNTHETIC_BASELINE + 3)}
    r = readiness(FakeS3(objs), "bkt")
    assert r["natural"] == 3 and r["ready"] is False
    # Plenty of natural clips -> ready.
    objs = {f"recordings/d/{i}/audio.webm": b"x" for i in range(SYNTHETIC_BASELINE + 40)}
    assert readiness(FakeS3(objs), "bkt")["ready"] is True


def test_reprocess_one_is_idempotent():
    s3 = FakeS3({"recordings/d/aaa/audio.webm": b"x",
                 "recordings/d/aaa/report_native.json": b"{}"})  # already processed
    called = []
    out = reprocess_one(s3, "bkt", "recordings/d/aaa/audio.webm",
                        analyze=lambda *a, **k: called.append(1) or {})
    assert out is None and not called          # skipped, analysis not run
