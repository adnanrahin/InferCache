"""AWS Bedrock adapter."""

from __future__ import annotations

from typing import Any

from infercache.config import CacheConfig
from infercache.core import InferCache
from infercache.integrations.adapters.base import BaseAdapter


def _to_bedrock_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-style messages to Bedrock Converse format."""
    bedrock_msgs = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "system":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            blocks = [{"text": content}]
        elif isinstance(content, list):
            blocks = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    blocks.append({"text": part.get("text", "")})
                elif isinstance(part, dict) and "text" in part:
                    blocks.append({"text": part["text"]})
        else:
            blocks = [{"text": str(content)}]
        bedrock_msgs.append({"role": role, "content": blocks})
    return bedrock_msgs


def _extract_system(messages: list[dict[str, Any]]) -> list[dict[str, str]] | None:
    system_blocks = []
    for msg in messages:
        if msg.get("role") != "system":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            system_blocks.append({"text": content})
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    system_blocks.append({"text": part.get("text", str(part))})
    return system_blocks or None


class BedrockAdapter(BaseAdapter):
    """
    Wrap AWS Bedrock Converse API with InferCache.

    Requires boto3 and AWS credentials (env, ~/.aws/credentials, or IAM role).

    Install: pip install "infercache[bedrock]"
    """

    def __init__(
        self,
        client: Any | None = None,
        cache: InferCache | None = None,
        config: CacheConfig | None = None,
        default_model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name: str | None = None,
    ) -> None:
        super().__init__(cache=cache, config=config)
        self._client = client
        self.default_model = default_model
        self.region_name = region_name

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError as exc:
            raise ImportError('Install infercache[bedrock] (pip install "infercache[bedrock]")') from exc
        kwargs = {}
        if self.region_name:
            kwargs["region_name"] = self.region_name
        self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    def _invoke(self, messages: list[dict[str, Any]], model: str, **kwargs: Any) -> str:
        client = self._get_client()
        bedrock_msgs = _to_bedrock_messages(messages)
        system = _extract_system(messages)

        params: dict[str, Any] = {
            "modelId": model,
            "messages": bedrock_msgs,
            **kwargs,
        }
        if system:
            params["system"] = system

        resp = client.converse(**params)
        blocks = resp.get("output", {}).get("message", {}).get("content", [])
        return "".join(b.get("text", "") for b in blocks if "text" in b)

    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        model = model or self.default_model
        optimized = self.cache.optimizer.build_cache_control_blocks(
            self.cache.optimizer.optimize_messages(messages)[0]
        )

        def call(msgs: list[dict[str, Any]]) -> str:
            return self._invoke(msgs, model, **kwargs)

        result = self.cache.get_or_call_messages(optimized, call, model=model)
        result["provider"] = "bedrock"
        return result

    def complete(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        model = model or self.default_model
        messages = [{"role": "user", "content": prompt}]

        def call(p: str) -> str:
            return self._invoke([{"role": "user", "content": p}], model, **kwargs)

        result = self.cache.get_or_call(prompt, call, model=model)
        result["provider"] = "bedrock"
        return result
