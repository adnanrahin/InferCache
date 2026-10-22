"""Sampling scope must split cache identity without swallowing provider kwargs."""

from infercache.core.scope import sampling_scope


def test_sampling_scope_keeps_only_generation_fields():
    body = {
        "temperature": 0.2,
        "seed": 7,
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
        "keep_alive": "5m",
    }
    assert sampling_scope(body) == {"temperature": 0.2, "seed": 7}


def test_sampling_scope_empty_when_absent():
    assert sampling_scope({"model": "local"}) == {}
