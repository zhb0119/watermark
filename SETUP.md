# Setup — Memory Watermark Experiments

This repo contains AgentMark + the Memory Watermark design (`README.md`).

The experiments depend on six external research repos (memory backends + benchmarks). They are intentionally **not** vendored — each is its own upstream repo with its own license. Clone them as siblings of this repo (or anywhere on `PYTHONPATH`) before running experiments.

## Reference repos with clone commands

```bash
# Memory backends (Cognee / A-MEM / Graphiti / Letta)
git clone https://github.com/topoteretes/cognee.git           # cognee
git clone https://github.com/agiresearch/A-mem.git            # A-MEM
git clone https://github.com/getzep/graphiti.git              # Graphiti
git clone https://github.com/letta-ai/letta.git               # Letta (optional fourth backend)

# Long-term memory benchmarks
git clone https://github.com/snap-research/locomo.git              # LoCoMo
git clone https://github.com/xiaowu0162/LongMemEval.git            # LongMemEval
git clone https://github.com/HUST-AI-HYZ/MemoryAgentBench.git      # MemoryAgentBench (ICLR 2026)
```

## Versions used (for reproducibility)

If you need to pin to the exact commits the design doc was written against, use these:

| Repo | Pinned commit |
|------|---------------|
| `cognee` | `4893c8819` |
| `A-mem` | `ceffb86` |
| `graphiti` | `56cf7b3` |
| `letta` | `bb52a8900` |
| `locomo` | `3eb6f2c` |
| `MemoryAgentBench` | `569241d` |

## After cloning

See `README.md` for:

- §4.2.3 — backend adapter interface
- §5 — system shape (which LLM to use, harness, audit store)
- §10 — full experiment protocol
