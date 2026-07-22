from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".agents"))

from auto_knowledge_benchmark_metrics import (  # noqa: E402
    BenchmarkConfig,
    BenchmarkObservation,
    compute_benchmark_metrics,
    simulate_projected_batches,
)


def test_compute_benchmark_metrics_tracks_quality_and_efficiency():
    observation = BenchmarkObservation(
        sample_size=100,
        expected_knowledge_count=60,
        generated_count=55,
        approved_count=50,
        duplicate_count=5,
        failed_count=0,
        pii_source_count=10,
        masked_sensitive_source_count=10,
        rag_questions=20,
        rag_hits_at_3=17,
        before_fact_correct=4,
        after_fact_correct=16,
        manual_seconds_per_record=20.0,
        manual_minutes_per_item=3.0,
        review_minutes_per_candidate=0.75,
        run_duration_ms=120_000,
        retrieval_latencies_ms=[80, 100, 120, 200],
    )

    metrics = compute_benchmark_metrics(observation, BenchmarkConfig(projected_records=5000))

    assert metrics["sample"]["sample_size"] == 100
    assert metrics["quality"]["candidate_precision"] == 0.9091
    assert metrics["quality"]["knowledge_recall"] == 0.8333
    assert metrics["quality"]["duplicate_rate"] == 0.0833
    assert metrics["safety"]["pii_mask_rate"] == 1.0
    assert metrics["rag_effect"]["fact_accuracy_lift"] == 0.6
    assert metrics["efficiency"]["manual_seconds_per_record"] == 20.0
    assert metrics["efficiency"]["auto_seconds_per_record"] == 1.2
    assert metrics["efficiency"]["auto_minutes_sample"] == 2.0
    assert metrics["efficiency"]["manual_minutes_sample"] == 33.33
    assert metrics["efficiency"]["review_minutes_sample"] == 41.25
    assert metrics["efficiency"]["maintenance_time_saved_rate"] == 0.0
    assert metrics["efficiency"]["pipeline_time_reduction_rate"] == 0.94
    assert metrics["projection"]["projected_records"] == 5000
    assert metrics["projection"]["scale_factor"] == 50.0
    assert metrics["projection"]["auto_minutes_projected"] == 100.0
    assert metrics["projection"]["auto_hours_projected"] == 1.67
    assert metrics["projection"]["manual_hours_projected"] == 27.78
    assert metrics["projection"]["review_hours_projected"] == 34.38
    assert metrics["projection"]["hours_saved_projected"] == 0.0
    assert metrics["projection"]["automation_hours_saved_projected"] == 26.11
    assert metrics["projection"]["speedup_vs_manual"] == 16.67
    assert metrics["projection"]["time_reduction_rate_vs_manual"] == 0.94
    assert metrics["performance"]["pipeline_speedup_vs_serial"] == 2.03
    assert metrics["performance"]["retrieval_latency_p50_ms"] == 110
    assert metrics["performance"]["retrieval_latency_p95_ms"] == 200


def test_compute_benchmark_metrics_handles_zero_denominators():
    observation = BenchmarkObservation(
        sample_size=0,
        expected_knowledge_count=0,
        generated_count=0,
        approved_count=0,
        duplicate_count=0,
        failed_count=0,
        pii_source_count=0,
        masked_sensitive_source_count=0,
        rag_questions=0,
        rag_hits_at_3=0,
        before_fact_correct=0,
        after_fact_correct=0,
        manual_seconds_per_record=20.0,
        manual_minutes_per_item=3.0,
        review_minutes_per_candidate=0.75,
        run_duration_ms=0,
        retrieval_latencies_ms=[],
    )

    metrics = compute_benchmark_metrics(observation, BenchmarkConfig(projected_records=5000))

    assert metrics["quality"]["candidate_precision"] == 0
    assert metrics["quality"]["knowledge_recall"] == 0
    assert metrics["safety"]["pii_mask_rate"] == 0
    assert metrics["projection"]["scale_factor"] == 0
    assert metrics["projection"]["hours_saved_projected"] == 0


def test_simulate_projected_batches_adds_bounded_deterministic_noise():
    observation = BenchmarkObservation(
        sample_size=100,
        expected_knowledge_count=60,
        generated_count=55,
        approved_count=50,
        duplicate_count=5,
        failed_count=0,
        pii_source_count=10,
        masked_sensitive_source_count=10,
        rag_questions=20,
        rag_hits_at_3=17,
        before_fact_correct=4,
        after_fact_correct=16,
        manual_seconds_per_record=20.0,
        manual_minutes_per_item=3.0,
        review_minutes_per_candidate=0.75,
        run_duration_ms=120_000,
        retrieval_latencies_ms=[80, 100, 120, 200],
    )

    simulation = simulate_projected_batches(observation, batches=50, noise_ratio=0.04, seed=7)

    assert simulation["batches"] == 50
    assert simulation["projected_records_mean"] == 5000
    assert 4900 <= simulation["projected_records_low"] <= 5000
    assert 5000 <= simulation["projected_records_high"] <= 5100
    assert 2400 <= simulation["approved_count_mean"] <= 2600
    assert simulation == simulate_projected_batches(observation, batches=50, noise_ratio=0.04, seed=7)
