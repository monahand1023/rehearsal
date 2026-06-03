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


def test_build_report_without_content(make_transcript):
    tr = make_transcript([("hi", 0.0, 0.4)], duration=1.0)
    delivery = DeliveryMetrics(1.0, 0.4, 0.0, 0.0, [], 0)
    fillers = FillerReport([], 0, 0.0)
    prosody = ProsodyMetrics(0.0, 0.0, 0.0, True, 0.0)
    report = build_report(tr, delivery, fillers, prosody, None)
    assert report["content"] is None
