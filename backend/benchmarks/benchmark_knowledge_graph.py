#!/usr/bin/env python3
"""Deterministic benchmark for Topic Graph build orchestration."""

import argparse
import asyncio
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

from services.topic_graph_builder import TopicGraphBuilder


class _InMemoryStore:
    def __init__(self):
        self.relationships = {}

    async def has_relationships(self, project_id):
        return bool(self.relationships.get(project_id))

    async def clear_relationships(self, project_id):
        self.relationships[project_id] = []

    async def upsert_relationships(self, edges):
        for edge in edges:
            self.relationships.setdefault(edge["project_id"], []).append(edge)


class _FakeRelationshipGenerator:
    def __init__(self, latency_seconds, batch_concurrency):
        self.latency_seconds = latency_seconds
        self.batch_concurrency = batch_concurrency
        self.calls = 0
        self.active_calls = 0
        self.peak_concurrency = 0

    async def generate(self, project_id, batch_topics, all_topics):
        self.calls += 1
        self.active_calls += 1
        self.peak_concurrency = max(self.peak_concurrency, self.active_calls)
        await asyncio.sleep(self.latency_seconds)
        self.active_calls -= 1
        return []


async def _run_scenario(generator, topic_counts, project_id):
    builder = TopicGraphBuilder(
        _InMemoryStore(), generator, batch_concurrency=generator.batch_concurrency
    )
    calls_before = generator.calls
    provider_latency_floor = 0.0
    started = time.perf_counter()
    for topic_count in topic_counts:
        build_calls_before = generator.calls
        await builder.build(
            project_id,
            [f"Topic {index}" for index in range(topic_count)],
            force_rebuild=True,
        )
        build_calls = generator.calls - build_calls_before
        provider_latency_floor += (
            math.ceil(build_calls / generator.batch_concurrency)
            * generator.latency_seconds
        )

    elapsed = time.perf_counter() - started
    calls = generator.calls - calls_before
    return {
        "elapsed_seconds": round(elapsed, 6),
        "llm_calls": calls,
        "provider_latency_floor_seconds": round(provider_latency_floor, 6),
        "orchestration_overhead_seconds": round(
            elapsed - provider_latency_floor, 6
        ),
    }


def _percentile(samples, percentile):
    ordered = sorted(samples)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


async def _benchmark(args):
    generator = _FakeRelationshipGenerator(
        args.fake_llm_latency_ms / 1000, args.batch_concurrency
    )

    await _run_scenario(generator, [100], "warmup")

    single_runs = []
    for index in range(args.iterations):
        single_runs.append(await _run_scenario(generator, [100], f"single-{index}"))

    cumulative_run = await _run_scenario(
        generator,
        [20, 40, 60, 80, 100],
        "cumulative",
    )
    single_elapsed = [run["elapsed_seconds"] for run in single_runs]
    single_p95 = _percentile(single_elapsed, 0.95)

    failures = []
    if any(run["llm_calls"] > 5 for run in single_runs):
        failures.append("100-topic build exceeds the 5-call LLM budget")
    if cumulative_run["llm_calls"] > 15:
        failures.append("cumulative build exceeds the 15-call LLM budget")
    expected_peak = min(args.batch_concurrency, 5)
    if generator.peak_concurrency != expected_peak:
        failures.append(
            f"peak LLM concurrency {generator.peak_concurrency} does not equal "
            f"expected {expected_peak}"
        )
    if single_p95 > args.max_single_p95_seconds:
        failures.append(
            f"single-build p95 {single_p95:.3f}s exceeds "
            f"{args.max_single_p95_seconds:.3f}s"
        )
    if cumulative_run["elapsed_seconds"] > args.max_cumulative_seconds:
        failures.append(
            f"cumulative build {cumulative_run['elapsed_seconds']:.3f}s exceeds "
            f"{args.max_cumulative_seconds:.3f}s"
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "iterations": args.iterations,
            "fake_llm_latency_ms": args.fake_llm_latency_ms,
            "batch_concurrency": args.batch_concurrency,
            "max_single_p95_seconds": args.max_single_p95_seconds,
            "max_cumulative_seconds": args.max_cumulative_seconds,
        },
        "single_100_topic_build": {
            "runs": single_runs,
            "p95_seconds": single_p95,
        },
        "five_cumulative_document_builds": cumulative_run,
        "peak_llm_concurrency": generator.peak_concurrency,
        "passed": not failures,
        "failures": failures,
    }


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--fake-llm-latency-ms", type=float, default=20)
    parser.add_argument("--batch-concurrency", type=int, default=2)
    parser.add_argument("--max-single-p95-seconds", type=float, default=3.0)
    parser.add_argument("--max-cumulative-seconds", type=float, default=7.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")
    if args.batch_concurrency < 1:
        parser.error("--batch-concurrency must be at least 1")
    return args


def main():
    args = _parse_args()
    report = asyncio.run(_benchmark(args))
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
