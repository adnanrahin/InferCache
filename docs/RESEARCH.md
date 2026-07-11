# InferCache Research Bibliography

Comprehensive reference list of papers and systems on LLM token optimization, caching, and cost reduction. InferCache implements techniques from these works.

## Semantic & Response Caching

| Paper | Year | Key Contribution | Reported Savings |
|-------|------|------------------|------------------|
| [GPTCache](https://aclanthology.org/2023.nlposs-1.24.pdf) (Bang et al.) | 2023 | Open-source semantic cache with embedding similarity | 2–10× faster responses; fewer API calls |
| [GPT Semantic Cache](https://arxiv.org/abs/2411.05276) | 2024 | Redis + ANN embedding cache for query-response pairs | Up to 68.8% API call reduction; 97%+ accuracy |
| [vCache](https://openreview.net/forum?id=zF0A0xw3HZ) (Schroeder et al.) | ICLR 2026 | Verified semantic cache with user-defined error bounds | Up to 26× hit rate vs static thresholds |
| [VectorQ](https://arxiv.org/abs/2502.03771) | 2025 | Adaptive embedding-specific similarity thresholds | Up to 26× hit rate; 74–92% error reduction |

## Prefix & KV Cache Reuse

| Paper | Year | Key Contribution | Reported Savings |
|-------|------|------------------|------------------|
| [Prompt Cache](https://proceedings.mlsys.org/paper_files/paper/2024/file/a66caa1703fe34705a4368c3014c1966-Paper-Conference.pdf) (Gim et al., MLSys 2024) | 2024 | Modular attention reuse across prompt modules | 8–60× latency reduction |
| [SemShareKV](https://aclanthology.org/2025.findings-ijcnlp.25.pdf) | 2025 | Semantic KV cache sharing via LSH token matching | 6.25× speedup; 42% memory reduction |
| Anthropic Prefix Caching | 2024 | Provider-side KV cache for static prefixes | Up to 90% cost reduction on cached tokens |
| OpenAI Prompt Caching | 2024 | Automatic prefix caching (≥1024 tokens) | 50% cost on cache-hit input tokens |

## Prompt Compression

| Paper | Year | Key Contribution | Reported Savings |
|-------|------|------------------|------------------|
| [LLMLingua](https://arxiv.org/abs/2310.05736) (Jiang et al.) | 2023 | Coarse-to-fine perplexity-based compression | Up to 20× compression, minimal loss |
| [LongLLMLingua](https://aclanthology.org/2024.acl-long.91) | 2024 | Question-aware long-context compression | ~4× fewer tokens; 94% cost reduction (LooGLE) |
| [LLMLingua-2](https://arxiv.org/abs/2403.12968) | 2024 | Token classification compression model | Higher efficiency, task-agnostic |
| [Prompt Compression Survey](https://arxiv.org/abs/2402.05968) | NAACL 2025 | Taxonomy of hard/soft prompt compression | Survey of methods and tradeoffs |
| [DSPC](https://arxiv.org/abs/2501.xxxxx) | 2025 | Dual-stage progressive compression | Improved long-context reasoning under budget |

## Inference & Memory Optimization

| Paper | Year | Key Contribution |
|-------|------|------------------|
| [PagedAttention / vLLM](https://arxiv.org/abs/2309.06180) (Kwon et al.) | 2023 | Efficient KV cache memory management |
| [H2O](https://arxiv.org/abs/2306.14048) | 2023 | Heavy-hitter KV cache eviction |
| [StreamingLLM](https://arxiv.org/abs/2309.17453) | 2023 | Attention sink for infinite context |
| [CacheBlend](https://arxiv.org/abs/2405.16444) | 2024 | KV cache reuse for RAG |
| [SGLang RadixAttention](https://arxiv.org/abs/2312.07104) | 2024 | Radix tree prefix caching for serving |

## Tool & Plan Caching

| Paper | Year | Key Contribution |
|-------|------|------------------|
| [FrugalGPT](https://arxiv.org/abs/2305.05176) | 2023 | LLM cascade for cost-quality tradeoff |
| [Model Stock](https://arxiv.org/abs/2403.15778) | 2024 | Response routing across model tiers |
| Plan caching / tool memoization | 2025 | Cache tool execution results (complements semantic cache) |

## InferCache Implementation Mapping

| InferCache Feature | Research Basis |
|--------------------|----------------|
| Exact hash cache | Standard deduplication |
| Semantic TF-IDF/hash embeddings | GPTCache, GPT Semantic Cache |
| Adaptive thresholds | VectorQ, vCache |
| Prompt compression | LLMLingua (heuristic variant) |
| History pruning | Long-context cost control |
| Prefix reordering + cache_control | Prompt Cache, Anthropic/OpenAI prefix caching |
| Multi-tier metrics | Combined savings measurement |

## Industry Reports

- Microsoft Azure: [Semantic Caching for Azure OpenAI](https://techcommunity.microsoft.com/blog/azurearchitectureblog/optimize-azure-openai-applications-with-semantic-caching/4106867) — 20–30% queries servable from cache
- Research: ~31% of production LLM queries exhibit semantic similarity (Introl, 2025)

## Target: 20%+ Token Reduction

Achievable through layered optimization:

1. **Semantic cache hits** (20–68% of queries in repetitive workloads)
2. **Prompt compression** (10–30% input token reduction)
3. **History pruning** (variable, scales with conversation length)
4. **Provider prefix caching** (50–90% on static prefix tokens when configured)

Run `infercache benchmark` to simulate savings for your workload pattern.
