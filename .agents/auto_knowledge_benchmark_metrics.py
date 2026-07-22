from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from statistics import median
from typing import Any


@dataclass(frozen=True)
class BenchmarkConfig:
    projected_records: int = 5000
    serial_reference_run_duration_ms: int | None = 243_527


@dataclass(frozen=True)
class BenchmarkObservation:
    sample_size: int
    expected_knowledge_count: int
    generated_count: int
    approved_count: int
    duplicate_count: int
    failed_count: int
    pii_source_count: int
    masked_sensitive_source_count: int
    rag_questions: int
    rag_hits_at_3: int
    before_fact_correct: int
    after_fact_correct: int
    manual_seconds_per_record: float
    manual_minutes_per_item: float
    review_minutes_per_candidate: float
    run_duration_ms: int
    retrieval_latencies_ms: list[int]


def _rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0
    return round(numerator / denominator, 4)


def _round(value: float) -> float:
    return round(value, 2)


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    if percentile <= 0:
        return ordered[0]
    if percentile >= 1:
        return ordered[-1]
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def simulate_projected_batches(
    observation: BenchmarkObservation,
    batches: int,
    noise_ratio: float = 0.04,
    seed: int = 20260722,
) -> dict[str, Any]:
    if batches <= 0 or observation.sample_size <= 0:
        return {
            "batches": max(0, batches),
            "noise_ratio": noise_ratio,
            "projected_records_mean": 0,
            "projected_records_low": 0,
            "projected_records_high": 0,
            "generated_count_mean": 0,
            "approved_count_mean": 0,
            "hours_saved_mean": 0,
        }

    rng = random.Random(seed)
    records: list[int] = []
    generated: list[int] = []
    approved: list[int] = []
    hours_saved: list[float] = []

    generated_rate = _rate(observation.generated_count, observation.sample_size)
    approved_rate = _rate(observation.approved_count, observation.sample_size)
    manual_minutes_rate = observation.manual_seconds_per_record / 60
    review_minutes_rate = observation.generated_count * observation.review_minutes_per_candidate / observation.sample_size
    saved_minutes_rate = max(0.0, manual_minutes_rate - review_minutes_rate)
    auto_seconds_rate = observation.run_duration_ms / 1000 / observation.sample_size

    for _ in range(batches):
        multiplier = 1 + rng.uniform(-noise_ratio, noise_ratio)
        batch_records = max(0, round(observation.sample_size * multiplier))
        records.append(batch_records)
        generated.append(round(batch_records * generated_rate))
        approved.append(round(batch_records * approved_rate))
        hours_saved.append(batch_records * saved_minutes_rate / 60)

    aggregate_noise_ratio = noise_ratio / 2
    auto_seconds = sum(record_count * auto_seconds_rate for record_count in records)
    return {
        "batches": batches,
        "noise_ratio": noise_ratio,
        "projected_records_mean": observation.sample_size * batches,
        "projected_records_simulated": round(sum(records)),
        "projected_records_low": round(observation.sample_size * batches * (1 - aggregate_noise_ratio)),
        "projected_records_high": round(observation.sample_size * batches * (1 + aggregate_noise_ratio)),
        "generated_count_mean": round(sum(generated)),
        "approved_count_mean": round(sum(approved)),
        "auto_minutes_mean": _round(auto_seconds / 60),
        "hours_saved_mean": _round(sum(hours_saved)),
        "seed": seed,
    }


def compute_benchmark_metrics(observation: BenchmarkObservation, config: BenchmarkConfig) -> dict[str, Any]:
    run_seconds_sample = observation.run_duration_ms / 1000
    auto_seconds_per_record = run_seconds_sample / observation.sample_size if observation.sample_size else 0
    manual_minutes_sample = observation.sample_size * observation.manual_seconds_per_record / 60
    review_minutes_sample = observation.generated_count * observation.review_minutes_per_candidate
    sample_saved_minutes = max(0.0, manual_minutes_sample - review_minutes_sample)
    scale_factor = _rate(config.projected_records, observation.sample_size)
    auto_seconds_projected = run_seconds_sample * scale_factor
    manual_minutes_projected = manual_minutes_sample * scale_factor
    review_minutes_projected = review_minutes_sample * scale_factor
    manual_seconds_projected = config.projected_records * observation.manual_seconds_per_record
    speedup_vs_manual = manual_seconds_projected / auto_seconds_projected if auto_seconds_projected > 0 else 0
    serial_speedup = (
        config.serial_reference_run_duration_ms / observation.run_duration_ms
        if config.serial_reference_run_duration_ms and observation.run_duration_ms > 0
        else 0
    )

    before_accuracy = _rate(observation.before_fact_correct, observation.rag_questions)
    after_accuracy = _rate(observation.after_fact_correct, observation.rag_questions)

    return {
        "sample": {
            "sample_size": observation.sample_size,
            "expected_knowledge_count": observation.expected_knowledge_count,
            "measurement_scope": "100-record benchmark sample",
        },
        "quality": {
            "candidate_precision": _rate(observation.approved_count, observation.generated_count),
            "knowledge_recall": _rate(observation.approved_count, observation.expected_knowledge_count),
            "candidate_yield": _rate(observation.generated_count, observation.sample_size),
            "duplicate_rate": _rate(observation.duplicate_count, observation.generated_count + observation.duplicate_count),
            "failure_rate": _rate(observation.failed_count, max(observation.generated_count, observation.sample_size)),
        },
        "safety": {
            "pii_mask_rate": _rate(observation.masked_sensitive_source_count, observation.pii_source_count),
            "pii_source_count": observation.pii_source_count,
        },
        "rag_effect": {
            "rag_hit_at_3": _rate(observation.rag_hits_at_3, observation.rag_questions),
            "business_fact_accuracy_before": before_accuracy,
            "business_fact_accuracy_after": after_accuracy,
            "fact_accuracy_lift": round(after_accuracy - before_accuracy, 4),
        },
        "efficiency": {
            "manual_seconds_per_record": observation.manual_seconds_per_record,
            "manual_minutes_per_item": observation.manual_minutes_per_item,
            "review_minutes_per_candidate": observation.review_minutes_per_candidate,
            "auto_seconds_per_record": _round(auto_seconds_per_record),
            "auto_minutes_sample": _round(run_seconds_sample / 60),
            "manual_minutes_sample": _round(manual_minutes_sample),
            "review_minutes_sample": _round(review_minutes_sample),
            "minutes_saved_sample": _round(sample_saved_minutes),
            "maintenance_time_saved_rate": _rate(sample_saved_minutes, manual_minutes_sample),
            "pipeline_time_reduction_rate": _rate(
                max(0.0, manual_minutes_sample - run_seconds_sample / 60),
                manual_minutes_sample,
            ),
        },
        "projection": {
            "projected_records": config.projected_records,
            "scale_factor": scale_factor,
            "basis": "projected_records / measured_sample_size",
            "auto_minutes_projected": _round(auto_seconds_projected / 60),
            "auto_hours_projected": _round(auto_seconds_projected / 3600),
            "manual_hours_projected": _round(manual_minutes_projected / 60),
            "review_hours_projected": _round(review_minutes_projected / 60),
            "hours_saved_projected": _round(max(0.0, manual_minutes_projected - review_minutes_projected) / 60),
            "automation_hours_saved_projected": _round(
                max(0.0, manual_seconds_projected - auto_seconds_projected) / 3600
            ),
            "speedup_vs_manual": _round(speedup_vs_manual),
            "time_reduction_rate_vs_manual": _rate(
                max(0.0, manual_seconds_projected - auto_seconds_projected),
                manual_seconds_projected,
            ),
            "simulation": simulate_projected_batches(
                observation,
                batches=round(scale_factor) if scale_factor else 0,
            ),
            "disclaimer": (
                "Projected from the measured 100-record benchmark sample; "
                "not a production cumulative record count."
            ),
        },
        "performance": {
            "run_duration_ms": observation.run_duration_ms,
            "serial_reference_run_duration_ms": config.serial_reference_run_duration_ms or 0,
            "pipeline_speedup_vs_serial": _round(serial_speedup),
            "retrieval_latency_p50_ms": int(median(observation.retrieval_latencies_ms))
            if observation.retrieval_latencies_ms
            else 0,
            "retrieval_latency_p95_ms": _percentile(observation.retrieval_latencies_ms, 0.95),
        },
    }


def render_markdown_report(metrics: dict[str, Any]) -> str:
    sample = metrics["sample"]
    quality = metrics["quality"]
    rag = metrics["rag_effect"]
    efficiency = metrics["efficiency"]
    projection = metrics["projection"]
    simulation = projection["simulation"]
    safety = metrics["safety"]
    performance = metrics["performance"]

    return "\n".join(
        [
            "# Auto Knowledge Benchmark Report",
            "",
            "## Scope",
            f"- Measured sample: {sample['sample_size']} operations chat records.",
            f"- Expected reusable knowledge items: {sample['expected_knowledge_count']}.",
            f"- Projection: {projection['projected_records']} records = measured sample x {projection['scale_factor']}.",
            f"- Projection note: {projection['disclaimer']}",
            "",
            "## Quality",
            f"- Candidate precision: {quality['candidate_precision']:.2%}",
            f"- Knowledge recall: {quality['knowledge_recall']:.2%}",
            f"- Candidate yield: {quality['candidate_yield']:.2%}",
            f"- Duplicate rate: {quality['duplicate_rate']:.2%}",
            f"- Failure rate: {quality['failure_rate']:.2%}",
            "",
            "## Business QA Effect",
            f"- RAG hit@3: {rag['rag_hit_at_3']:.2%}",
            f"- Fact accuracy before knowledge: {rag['business_fact_accuracy_before']:.2%}",
            f"- Fact accuracy after knowledge: {rag['business_fact_accuracy_after']:.2%}",
            f"- Fact accuracy lift: {rag['fact_accuracy_lift']:.2%}",
            "",
            "## Efficiency Estimate",
            f"- Manual baseline: {efficiency['manual_seconds_per_record']} seconds per source chat record.",
            f"- Review baseline: {efficiency['review_minutes_per_candidate']} minutes per generated candidate.",
            f"- Automatic pipeline: {efficiency['auto_seconds_per_record']} seconds per source chat record.",
            f"- Sample automatic processing time: {efficiency['auto_minutes_sample']} minutes.",
            f"- Sample manual effort: {efficiency['manual_minutes_sample']} minutes.",
            f"- Sample review effort: {efficiency['review_minutes_sample']} minutes.",
            f"- Sample time saved: {efficiency['minutes_saved_sample']} minutes.",
            f"- Sample maintenance time saved rate: {efficiency['maintenance_time_saved_rate']:.2%}.",
            f"- Projected automatic processing time: {projection['auto_minutes_projected']} minutes.",
            f"- Projected manual effort: {projection['manual_hours_projected']} hours.",
            f"- Projected automation saved effort: {projection['automation_hours_saved_projected']} hours.",
            f"- Projected review effort: {projection['review_hours_projected']} hours.",
            f"- Projected saved effort: {projection['hours_saved_projected']} hours.",
            f"- Projected speedup vs manual baseline: {projection['speedup_vs_manual']}x.",
            f"- Projected time reduction vs manual baseline: {projection['time_reduction_rate_vs_manual']:.2%}.",
            (
                f"- 50-batch noisy simulation: mean {simulation['projected_records_mean']} records, "
                f"bounded batch range {simulation['projected_records_low']}-{simulation['projected_records_high']} "
                f"records, mean automatic time {simulation['auto_minutes_mean']} minutes, "
                f"mean saved effort {simulation['hours_saved_mean']} hours."
            ),
            "",
            "## Safety And Performance",
            f"- PII mask rate: {safety['pii_mask_rate']:.2%} across {safety['pii_source_count']} sensitive samples.",
            f"- Run duration: {performance['run_duration_ms']} ms.",
            f"- Pipeline speedup vs serial extraction: {performance['pipeline_speedup_vs_serial']}x.",
            f"- Retrieval latency p50/p95: {performance['retrieval_latency_p50_ms']} ms / {performance['retrieval_latency_p95_ms']} ms.",
            "",
            "## Resume-Safe Wording",
            (
                "Validated the Auto Knowledge pipeline on a measured 100-record operations chat benchmark, "
                "covering collection, cleaning, PII masking, LLM extraction, deduplication, review, "
                "knowledge-base publishing, and RAG retrieval. The 5000+ record figure is projected as "
                "100 measured records x 50 equivalent batches, not claimed as production traffic."
            ),
        ]
    )


def write_reports(metrics: dict[str, Any], report_dir: Path) -> tuple[Path, Path]:
    import json

    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "auto_knowledge_benchmark.json"
    md_path = report_dir / "auto_knowledge_benchmark.md"
    json_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(metrics), encoding="utf-8")
    return json_path, md_path
