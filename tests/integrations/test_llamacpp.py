"""llama.cpp adapter tests (mocked HTTP, no running llama-server required)."""

import json
from unittest.mock import MagicMock, patch

from infercache.integrations.adapters import LlamaCppAdapter
from infercache.integrations.adapters.llamacpp import resolve_llamacpp_base_url


def test_resolve_llamacpp_base_url_host_port():
    assert resolve_llamacpp_base_url("127.0.0.1:8080") == "http://127.0.0.1:8080"


def test_resolve_llamacpp_base_url_full():
    assert resolve_llamacpp_base_url("http://127.0.0.1:8080/") == "http://127.0.0.1:8080"


def _mock_response(payload: dict):
    mock = MagicMock()
    mock.read.return_value = json.dumps(payload).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


@patch("infercache.integrations.adapters.llamacpp.urlopen")
def test_llamacpp_chat_caches_response(mock_urlopen):
    mock_urlopen.return_value = _mock_response(
        {"choices": [{"message": {"content": "Hello from llama.cpp!"}}]}
    )

    adapter = LlamaCppAdapter(default_model="local")
    messages = [{"role": "user", "content": "Hi"}]

    r1 = adapter.chat(messages)
    r2 = adapter.chat(messages)

    assert r1["cache_hit"] is False
    assert r2["cache_hit"] is True
    assert r1["response"] == "Hello from llama.cpp!"
    assert r1["provider"] == "llamacpp"
    assert mock_urlopen.call_count == 1


@patch("infercache.integrations.adapters.llamacpp.urlopen")
def test_llamacpp_complete(mock_urlopen):
    mock_urlopen.return_value = _mock_response(
        {"choices": [{"message": {"content": "Generated text"}}]}
    )

    adapter = LlamaCppAdapter(default_model="local")
    result = adapter.complete("Write a haiku")

    assert result["cache_hit"] is False
    assert result["response"] == "Generated text"
    assert result["provider"] == "llamacpp"


@patch("infercache.integrations.adapters.llamacpp.urlopen")
def test_llamacpp_list_models(mock_urlopen):
    mock_urlopen.return_value = _mock_response(
        {"data": [{"id": "model.gguf"}, {"id": "other"}]}
    )
    adapter = LlamaCppAdapter()
    assert adapter.list_models() == ["model.gguf", "other"]
