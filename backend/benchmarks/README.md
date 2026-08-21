# Backend Benchmarks

## Topic Graph Build

Run from `backend/`:

```bash
.venv/bin/python -m benchmarks.benchmark_knowledge_graph \
  --output benchmark-results/knowledge-graph.json
```

The benchmark executes the production Graph Build orchestration with an
in-memory database and a deterministic 20 ms fake LLM. It measures:

- Three isolated 100-topic builds, including p95 wall time and orchestration
  overhead.
- Five cumulative builds at 20, 40, 60, 80, and 100 topics, matching repeated
  document ingestion.
- LLM call count and peak concurrency.

The call-count checks are upper bounds, so optimizations that use fewer calls
or introduce safe concurrency will pass rather than locking in today's design.

The default CI limits are 3 seconds for the isolated-build p95 and 7 seconds
for the cumulative build. They are intentionally above the current baseline
to tolerate shared-runner variance while still detecting material regressions.

This is an orchestration benchmark, not an Azure OpenAI benchmark. It is stable
and credential-free by design. Production monitoring must separately measure
real model latency, token usage, database latency, and error rates.
