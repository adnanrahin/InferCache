"""
FastAPI app pattern — how customers integrate InferCache into their API.

Install:
  pip install "infercache[bedrock]" fastapi uvicorn
  # or for Ollama only:
  pip install infercache fastapi uvicorn

Run (Ollama):
  set PROVIDER=ollama
  set OLLAMA_HOST=192.168.1.248:11434
  uvicorn examples.fastapi_app:app --reload --port 8080

Run (Bedrock):
  set PROVIDER=bedrock
  set AWS_REGION=us-east-1
  uvicorn examples.fastapi_app:app --reload --port 8080
"""

from __future__ import annotations

import os
from typing import Any, Callable

from fastapi import FastAPI
from pydantic import BaseModel

from infercache import CacheConfig, InferCache
from infercache.integrations.adapters import BedrockAdapter, OllamaAdapter

app = FastAPI(title="InferCache API", version="0.1.0")

PROVIDER = os.environ.get("PROVIDER", "ollama")

cache = InferCache(
    CacheConfig(
        similarity_threshold=0.55,
        ttl_seconds=int(os.environ.get("CACHE_TTL", "3600")),
        max_cache_entries=50_000,
    )
)

if PROVIDER == "bedrock":
    adapter = BedrockAdapter(
        cache=cache,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        default_model=os.environ.get(
            "BEDROCK_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0"
        ),
    )

    def llm_call(messages: list[dict[str, Any]]) -> str:
        return adapter._invoke(messages, adapter.default_model)

else:
    adapter = OllamaAdapter(
        cache=cache,
        base_url=os.environ.get("OLLAMA_HOST", "192.168.1.248:11434"),
        default_model=os.environ.get("OLLAMA_MODEL", "qwen3.5:latest"),
    )

    def llm_call(messages: list[dict[str, Any]]) -> str:
        return adapter._chat_uncached(messages, adapter.default_model)


class ChatRequest(BaseModel):
    user_id: str = "default"
    prompt: str | None = None
    messages: list[dict[str, Any]] | None = None


class ChatResponse(BaseModel):
    response: str
    cache_hit: bool
    provider: str


@app.post("/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    InferCache sits between your users and the LLM.

    user_id is included in the cache key so each user gets isolated entries.
    """
    messages = req.messages or [{"role": "user", "content": req.prompt or ""}]

    result = cache.get_or_call_messages(
        messages,
        llm_call,
        model=adapter.default_model,
        user_id=req.user_id,
    )

    return ChatResponse(
        response=result["response"],
        cache_hit=bool(result.get("cache_hit")),
        provider=PROVIDER,
    )


@app.get("/v1/stats")
def stats() -> dict:
    return cache.stats()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": PROVIDER}
