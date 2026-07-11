"""Bedrock adapter tests (mocked, no AWS required)."""

from unittest.mock import MagicMock, patch

from infercache.integrations.adapters import BedrockAdapter
from infercache.integrations.adapters.bedrock import _to_bedrock_messages


def test_to_bedrock_messages():
    msgs = [
        {"role": "system", "content": "Be brief"},
        {"role": "user", "content": "Hello"},
    ]
    bedrock = _to_bedrock_messages(msgs)
    assert len(bedrock) == 1
    assert bedrock[0]["content"] == [{"text": "Hello"}]


@patch.object(BedrockAdapter, "_get_client")
def test_bedrock_chat_caches(mock_get_client):
    mock_client = MagicMock()
    mock_client.converse.return_value = {
        "output": {"message": {"content": [{"text": "Cached answer"}]}}
    }
    mock_get_client.return_value = mock_client

    adapter = BedrockAdapter(default_model="anthropic.claude-3-5-sonnet-20241022-v2:0")
    messages = [{"role": "user", "content": "Hi"}]

    r1 = adapter.chat(messages)
    r2 = adapter.chat(messages)

    assert r1["cache_hit"] is False
    assert r2["cache_hit"] is True
    assert mock_client.converse.call_count == 1
