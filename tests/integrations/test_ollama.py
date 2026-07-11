"""Ollama adapter tests (mocked HTTP, no running Ollama required)."""

import json
from unittest.mock import MagicMock, patch

from infercache.integrations.adapters import OllamaAdapter
from infercache.integrations.adapters.ollama import resolve_ollama_base_url


def test_resolve_ollama_base_url_host_port():
    assert resolve_ollama_base_url("192.168.1.248:11434") == "http://192.168.1.248:11434"


def test_resolve_ollama_base_url_full():
    assert resolve_ollama_base_url("http://192.168.1.248:11434") == "http://192.168.1.248:11434"


def _mock_response(payload: dict):
    mock = MagicMock()
    mock.read.return_value = json.dumps(payload).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


@patch("infercache.integrations.adapters.ollama.urlopen")
def test_ollama_chat_caches_response(mock_urlopen):
    mock_urlopen.return_value = _mock_response(
        {"message": {"content": "Hello from Ollama!"}}
    )

    adapter = OllamaAdapter(default_model="llama3.2")
    messages = [{"role": "user", "content": "Hi"}]

    r1 = adapter.chat(messages)
    r2 = adapter.chat(messages)

    assert r1["cache_hit"] is False
    assert r2["cache_hit"] is True
    assert r1["response"] == "Hello from Ollama!"
    assert mock_urlopen.call_count == 1


@patch("infercache.integrations.adapters.ollama.urlopen")
def test_ollama_complete(mock_urlopen):
    mock_urlopen.return_value = _mock_response({"response": "Generated text"})

    adapter = OllamaAdapter(default_model="llama3.2")
    result = adapter.complete("Write a haiku")

    assert result["cache_hit"] is False
    assert result["response"] == "Generated text"
