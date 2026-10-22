"""Adaptive threshold stats must survive process restarts."""

from infercache.core.adaptive import AdaptiveThreshold


def test_adaptive_state_roundtrip(tmp_path):
    state = str(tmp_path / "adaptive_state.json")
    emb = [0.5] * 16

    first = AdaptiveThreshold(base=0.80, error_target=0.03, state_path=state)
    for _ in range(6):
        first.record_outcome(emb, was_correct=False)
    raised = first.get_threshold(emb)
    assert raised > 0.80

    # New instance (simulated restart) reads the sidecar and keeps the lesson.
    second = AdaptiveThreshold(base=0.80, error_target=0.03, state_path=state)
    assert second.get_threshold(emb) == raised
    assert second.bucket_accuracy(emb) == 0.0


def test_adaptive_without_state_path_stays_in_memory():
    adaptive = AdaptiveThreshold(base=0.80)
    emb = [0.1] * 16
    for _ in range(6):
        adaptive.record_outcome(emb, was_correct=True)
    assert adaptive.get_threshold(emb) <= 0.80


def test_corrupt_state_file_is_ignored(tmp_path):
    state = tmp_path / "adaptive_state.json"
    state.write_text("{not json", encoding="utf-8")
    adaptive = AdaptiveThreshold(base=0.80, state_path=str(state))
    assert adaptive.get_threshold([0.2] * 16) == 0.80
