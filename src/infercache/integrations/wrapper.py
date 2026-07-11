"""Decorator and middleware for wrapping LLM calls."""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from infercache.config import CacheConfig
from infercache.core import InferCache

F = TypeVar("F", bound=Callable[..., Any])

_DEFAULT_CACHE: InferCache | None = None


def get_default_cache() -> InferCache:
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = InferCache()
    return _DEFAULT_CACHE


def configure(config: CacheConfig | None = None) -> InferCache:
    global _DEFAULT_CACHE
    _DEFAULT_CACHE = InferCache(config=config)
    return _DEFAULT_CACHE


def cached_llm_call(
    cache: InferCache | None = None,
    model: str = "",
    prompt_arg: str = "prompt",
    messages_arg: str = "messages",
) -> Callable[[F], F]:
    """Decorator to cache LLM function calls by prompt or messages kwarg."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            c = cache or get_default_cache()
            if messages_arg in kwargs:
                result = c.get_or_call_messages(
                    kwargs[messages_arg],
                    lambda msgs: fn(*args, **{**kwargs, messages_arg: msgs}),
                    model=model or kwargs.get("model", ""),
                )
            elif prompt_arg in kwargs:
                result = c.get_or_call(
                    kwargs[prompt_arg],
                    lambda p: fn(*args, **{**kwargs, prompt_arg: p}),
                    model=model or kwargs.get("model", ""),
                )
            elif args:
                result = c.get_or_call(str(args[0]), lambda p: fn(p, *args[1:], **kwargs), model=model)
            else:
                return fn(*args, **kwargs)

            if isinstance(result, dict) and "response" in result:
                return result["response"]
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
