"""
Live demo: how InferCache saves tokens with exact-match caching.

Run:
  conda activate infer_cache
  python examples/demo_how_it_works.py

Shows two paths:
  1) Library  - one Python app wraps get_or_call
  2) Gateway  - any OpenAI-compatible app points base_url at InferCache
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from infercache import CacheConfig, InferCache
from infercache.gateway import GatewayConfig, create_gateway

PROMPT = "What is the capital of France?"
ANSWER = "Paris."


def section(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def demo_library() -> None:
    section("1) Library path - same app, second call is free")
    llm_calls = {"n": 0}

    def fake_llm(prompt: str) -> str:
        llm_calls["n"] += 1
        print(f"    LLM CALL #{llm_calls['n']}  (this is what you pay for)")
        time.sleep(0.15)
        return ANSWER

    cache = InferCache(
        CacheConfig(
            backend="memory",
            enable_prompt_compression=False,
            ttl_seconds=None,
        )
    )

    t0 = time.perf_counter()
    r1 = cache.get_or_call(PROMPT, fake_llm, model="demo")
    t1 = (time.perf_counter() - t0) * 1000
    print(f"    first : hit={r1['cache_hit']}  {t1:.0f} ms  -> {r1['response']}")

    t0 = time.perf_counter()
    r2 = cache.get_or_call(PROMPT, fake_llm, model="demo")
    t2 = (time.perf_counter() - t0) * 1000
    print(f"    second: hit={r2['cache_hit']}  {t2:.0f} ms  -> {r2['response']}")
    print(f"    upstream LLM calls: {llm_calls['n']}  (must be 1)")
    print(f"    stats: {json.dumps(cache.stats(), indent=2)}")


class _MockOpenAI(BaseHTTPRequestHandler):
    calls = 0

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        _MockOpenAI.calls += 1
        print(f"    UPSTREAM LLM CALL #{_MockOpenAI.calls}  (this is what you pay for)")
        body = json.dumps(
            {
                "id": "chatcmpl-demo",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": ANSWER},
                        "finish_reason": "stop",
                    }
                ],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _chat(url: str, prompt: str) -> dict:
    payload = json.dumps(
        {
            "model": "demo-model",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def demo_gateway() -> None:
    section("2) Gateway path - any app changes base_url, second call is free")

    mock = ThreadingHTTPServer(("127.0.0.1", 0), _MockOpenAI)
    mock_port = mock.server_address[1]
    threading.Thread(target=mock.serve_forever, daemon=True).start()

    gw = create_gateway(
        GatewayConfig(
            host="127.0.0.1",
            port=0,
            openai_upstream=f"http://127.0.0.1:{mock_port}",
            cache=CacheConfig(
                backend="memory",
                enable_prompt_compression=False,
                ttl_seconds=None,
            ),
        )
    )
    gw_port = gw.server_address[1]
    threading.Thread(target=gw.serve_forever, daemon=True).start()
    time.sleep(0.2)

    chat_url = f"http://127.0.0.1:{gw_port}/v1/chat/completions"
    print(f"    mock LLM  : http://127.0.0.1:{mock_port}")
    print(f"    gateway   : {chat_url}")
    print("    your app  : OpenAI(base_url=gateway)  - no other code change")

    t0 = time.perf_counter()
    a = _chat(chat_url, PROMPT)
    t1 = (time.perf_counter() - t0) * 1000
    print(
        f"    first : cache_hit={a.get('infercache', {}).get('cache_hit')}  "
        f"{t1:.0f} ms  -> {a['choices'][0]['message']['content']}"
    )

    t0 = time.perf_counter()
    b = _chat(chat_url, PROMPT)
    t2 = (time.perf_counter() - t0) * 1000
    print(
        f"    second: cache_hit={b.get('infercache', {}).get('cache_hit')}  "
        f"{t2:.0f} ms  -> {b['choices'][0]['message']['content']}"
    )
    print(f"    upstream LLM calls: {_MockOpenAI.calls}  (must be 1)")

    with urllib.request.urlopen(f"http://127.0.0.1:{gw_port}/stats", timeout=5) as resp:
        stats = json.loads(resp.read().decode())
    print(f"    gateway /stats: hit_rate={stats.get('hit_rate')}  "
          f"exact_hits={stats.get('exact_hits')}  misses={stats.get('misses')}")

    gw.shutdown()
    mock.shutdown()


if __name__ == "__main__":
    print("InferCache - how token savings actually work")
    print("Exact match: same model + same messages -> skip the LLM the second time.")
    demo_library()
    demo_gateway()
    print("\nDone. Next: point a real app at `infercache gateway` instead of this mock.\n")
