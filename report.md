# InferCache Benchmark Report

Model: `gpt-4o-mini` | Requests: 100 | Wall time: 1.32s

## Cache performance

| Metric | Value |
|--------|-------|
| Hit rate | 29.0% |
| Exact hits | 26 |
| Semantic hits | 3 |
| Misses | 71 |

## Token savings

| Direction | Saved | Spent |
|-----------|-------|-------|
| Input | 203 | 335 |
| Output | 1,770 | 4,228 |

## Cost

| Metric | Value |
|--------|-------|
| Saved | $0.0182 |
| Spent | $0.0431 |
| **Reduction** | **29.7%** |

## Latency (ms)

| Path | Avg | P95 |
|------|-----|-----|
| Cache hit | 1.9 | 22.35 |
| Cache miss (LLM) | 17.73 | 29.26 |
