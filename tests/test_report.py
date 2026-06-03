from engine.delivery import DeliveryMetrics, Pause
from engine.fillers import FillerReport, FillerHit
from engine.prosody import ProsodyMetrics
from engine.content import ContentFeedback
from engine.report import build_report


def test_build_report_shape(make_transcript):
    tr = make_transcript([("hello", 0.0, 0.5), ("world", 0.6, 1.0)], duration=2.0)
    delivery = DeliveryMetrics(
        total_audio_time=2.0, talk_time=1.0, time_to_first_word=0.0,
        words_per_minute=120.0, pauses=[Pause(0.5, 0.6)], long_pause_count=0,
    )
    fillers = FillerReport(hits=[FillerHit("um", 0.4, 0.6)], count=1, per_minute=0.5)
    prosody = ProsodyMetrics(150.0, 30.0, 90.0, False, 60.0)
    content = ContentFeedback(
        answered_question=True, answered_explanation="ok",
        star_present={"situation": True, "task": True, "action": True, "result": False},
        star_missing=["result"], issues=[], tighter_rewrite="x",
        coaching_notes=["a", "b", "c"],
    )

    report = build_report(tr, delivery, fillers, prosody, content)

    assert report["transcript"]["text"] == "hello world"
    assert report["delivery"]["words_per_minute"] == 120.0
    assert report["fillers"]["count"] == 1
    assert report["prosody"]["monotone"] is False
    assert report["content"]["star_missing"] == ["result"]


def test_build_report_includes_clarity(make_transcript):
    from engine.delivery import DeliveryMetrics
    from engine.fillers import FillerReport
    from engine.prosody import ProsodyMetrics
    from engine.report import build_report
    tr = make_transcript([("hi", 0.0, 0.4)], duration=1.0)  # Word.probability defaults 1.0
    report = build_report(tr, DeliveryMetrics(1.0, 0.4, 0.0, 0.0, [], 0),
                          FillerReport([], 0, 0.0),
                          ProsodyMetrics(0.0, 0.0, 0.0, True, 0.0), None)
    assert report["clarity"]["mean_confidence"] == 1.0
    assert report["clarity"]["low_confidence_words"] == []


def test_build_report_without_content(make_transcript):
    tr = make_transcript([("hi", 0.0, 0.4)], duration=1.0)
    delivery = DeliveryMetrics(1.0, 0.4, 0.0, 0.0, [], 0)
    fillers = FillerReport([], 0, 0.0)
    prosody = ProsodyMetrics(0.0, 0.0, 0.0, True, 0.0)
    report = build_report(tr, delivery, fillers, prosody, None)
    assert report["content"] is None


def test_analyze_answer_uses_llm_provider(monkeypatch):
    import engine.report as report
    from engine.types import Word, Transcript
    from engine.delivery import DeliveryMetrics
    from engine.fillers import FillerReport
    from engine.prosody import ProsodyMetrics
    from engine.content import ContentFeedback

    sentinel_client = object()
    monkeypatch.setattr(report, "get_client", lambda: sentinel_client)
    monkeypatch.setattr(report, "default_model", lambda: "gpt-4o")
    monkeypatch.setattr(report, "to_wav", lambda p: p)
    monkeypatch.setattr(report, "transcribe",
                        lambda wav, language="en": Transcript([Word("hi", 0.0, 0.4)], "hi", 1.0, language))
    monkeypatch.setattr(report, "analyze_delivery",
                        lambda tr: DeliveryMetrics(1.0, 0.4, 0.0, 0.0, [], 0))
    monkeypatch.setattr(report, "detect_fillers",
                        lambda tr, wav_path=None: FillerReport([], 0, 0.0))
    monkeypatch.setattr(report, "analyze_prosody",
                        lambda wav: ProsodyMetrics(0.0, 0.0, 0.0, True, 0.0))
    monkeypatch.setattr(report, "compose_spoken_summary", lambda *a, **k: "summary")

    captured = {}
    def fake_content(q, a, model=None, client=None):
        captured["model"] = model
        captured["client"] = client
        return ContentFeedback(True, "ok", {}, ["situation", "task", "action", "result"], [], "", [])
    monkeypatch.setattr(report, "analyze_content", fake_content)

    report.analyze_answer("a.wav", "Q", mode="interview")
    assert captured["model"] == "gpt-4o"
    assert captured["client"] is sentinel_client


def test_cloud_providers_selectable(monkeypatch):
    monkeypatch.setenv("REHEARSAL_LLM_PROVIDER", "openai")
    monkeypatch.setenv("REHEARSAL_TRANSCRIBE_PROVIDER", "openai")
    from engine import llm
    from engine.llm_openai import OpenAIChatClient
    assert isinstance(llm.get_client(), OpenAIChatClient)
    assert llm.default_model() == "gpt-4o"
    import engine.transcribe as t
    captured = {}
    monkeypatch.setattr("engine.transcribe_openai.transcribe_openai",
                        lambda wav, language="en": captured.setdefault("hit", True))
    t.transcribe("x.wav", language="ja")
    assert captured.get("hit") is True
