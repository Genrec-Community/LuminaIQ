#!/usr/bin/env python3
"""Deterministic benchmark for Topic Graph build orchestration."""

import argparse
import asyncio
import importlib.util
import json
import math
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _Query:
    def select(self, *args, **kwargs):
        return self

    def delete(self, *args, **kwargs):
        return self

    def upsert(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


class _Database:
    def table(self, name):
        return _Query()


class _FakeLLM:
    def __init__(self, latency_seconds):
        self.latency_seconds = latency_seconds
        self.calls = 0
        self.active_calls = 0
        self.peak_concurrency = 0

    async def chat_completion(self, *args, **kwargs):
        self.calls += 1
        self.active_calls += 1
        self.peak_concurrency = max(self.peak_concurrency, self.active_calls)
        await asyncio.sleep(self.latency_seconds)
        self.active_calls -= 1
        return "[]"


def _stub_module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module


def _load_graph_class(fake_llm):
    async def async_db(callable_fn):
        return callable_fn()

    database = _Database()
    _stub_module(
        "db.client",
        get_supabase_client=lambda: database,
        async_db=async_db,
    )
    _stub_module("services.llm_service", llm_service=fake_llm)
    _stub_module("utils.logger", logger=_Logger())

    service_path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "knowledge_graph_service.py"
    )
    spec = importlib.util.spec_from_file_location(
        "knowledge_graph_service_under_benchmark", service_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.KnowledgeGraph


async def _run_scenario(graph_class, fake_llm, topic_counts, project_id):
    graph = graph_class()
    calls_before = fake_llm.calls
    started = time.perf_counter()
    for topic_count in topic_counts:
        result = await graph.build_graph_from_topics(
            project_id,
            [f"Topic {index}" for index in range(topic_count)],
            force_rebuild=True,
        )
        if result["message"].startswith("Error:"):
            raise RuntimeError(result["message"])

    elapsed = time.perf_counter() - started
    calls = fake_llm.calls - calls_before
    return {
        "elapsed_seconds": round(elapsed, 6),
        "llm_calls": calls,
        "orchestration_overhead_seconds": round(
            elapsed - calls * fake_llm.latency_seconds, 6
        ),
    }


def _percentile(samples, percentile):
    ordered = sorted(samples)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


async def _benchmark(args):
    fake_llm = _FakeLLM(args.fake_llm_latency_ms / 1000)
    graph_class = _load_graph_class(fake_llm)

    await _run_scenario(graph_class, fake_llm, [100], "warmup")

    single_runs = []
    for index in range(args.iterations):
        single_runs.append(
            await _run_scenario(
                graph_class, fake_llm, [100], f"single-{index}"
            )
        )

    cumulative_run = await _run_scenario(
        graph_class,
        fake_llm,
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
            "max_single_p95_seconds": args.max_single_p95_seconds,
            "max_cumulative_seconds": args.max_cumulative_seconds,
        },
        "single_100_topic_build": {
            "runs": single_runs,
            "p95_seconds": single_p95,
        },
        "five_cumulative_document_builds": cumulative_run,
        "peak_llm_concurrency": fake_llm.peak_concurrency,
        "passed": not failures,
        "failures": failures,
    }


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--fake-llm-latency-ms", type=float, default=20)
    parser.add_argument("--max-single-p95-seconds", type=float, default=3.0)
    parser.add_argument("--max-cumulative-seconds", type=float, default=7.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")
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
