#!/usr/bin/env python3
"""Phase 3.3 Week 3: Prometheus Metrics - Observability Integration

Exports orchestration metrics for monitoring:
- Phase execution times
- Worker heartbeat tracking
- Error rates
- Skill loading
- Cost tracking
"""

from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PrometheusMetrics:
    """Prometheus metrics collector for orchestration"""

    def __init__(self, run_id: str):
        """Initialize metrics collector"""
        self.run_id = run_id
        self.metrics = {
            # Counters (monotonically increasing)
            "orchestration_tasks_total": 0,
            "orchestration_phases_completed": 0,
            "orchestration_phases_failed": 0,
            "orchestration_workers_spawned": 0,
            "orchestration_workers_completed": 0,
            "orchestration_workers_failed": 0,
            "orchestration_workers_stalled": 0,
            "orchestration_skills_loaded": 0,
            "orchestration_skills_failed": 0,
            "orchestration_circular_deps_detected": 0,
            "orchestration_errors_total": 0,
            "orchestration_recoveries": 0,

            # Gauges (can go up and down)
            "orchestration_workers_running": 0,
            "orchestration_phases_pending": 0,
            "orchestration_cache_size_bytes": 0,
            "orchestration_state_db_size_bytes": 0,

            # Histograms (recorded as separate values)
            "orchestration_phase_duration_seconds": [],
            "orchestration_worker_duration_seconds": [],
            "orchestration_skill_validation_ms": [],
            "orchestration_event_log_latency_ms": [],
            "orchestration_heartbeat_latency_ms": [],

            # Metadata
            "start_time": datetime.utcnow().isoformat()
        }

    def record_phase_started(self, phase: int) -> None:
        """Record phase start"""
        self.metrics["orchestration_phases_pending"] += 1
        logger.info(f"📊 Phase {phase} started")

    def record_phase_completed(self, phase: int, duration_seconds: float) -> None:
        """Record phase completion"""
        self.metrics["orchestration_phases_completed"] += 1
        self.metrics["orchestration_phases_pending"] -= 1
        self.metrics["orchestration_phase_duration_seconds"].append(duration_seconds)
        logger.info(f"📊 Phase {phase} completed in {duration_seconds:.2f}s")

    def record_phase_failed(self, phase: int, error: str) -> None:
        """Record phase failure"""
        self.metrics["orchestration_phases_failed"] += 1
        self.metrics["orchestration_phases_pending"] -= 1
        self.metrics["orchestration_errors_total"] += 1
        logger.error(f"📊 Phase {phase} failed: {error}")

    def record_worker_spawned(self) -> None:
        """Record worker spawn"""
        self.metrics["orchestration_workers_spawned"] += 1
        self.metrics["orchestration_workers_running"] += 1

    def record_worker_completed(self, duration_seconds: float) -> None:
        """Record worker completion"""
        self.metrics["orchestration_workers_completed"] += 1
        self.metrics["orchestration_workers_running"] -= 1
        self.metrics["orchestration_worker_duration_seconds"].append(duration_seconds)

    def record_worker_failed(self) -> None:
        """Record worker failure"""
        self.metrics["orchestration_workers_failed"] += 1
        self.metrics["orchestration_workers_running"] -= 1
        self.metrics["orchestration_errors_total"] += 1

    def record_worker_stalled(self) -> None:
        """Record worker stall"""
        self.metrics["orchestration_workers_stalled"] += 1
        self.metrics["orchestration_errors_total"] += 1

    def record_recovery_attempt(self) -> None:
        """Record recovery attempt"""
        self.metrics["orchestration_recoveries"] += 1

    def record_skill_loaded(self) -> None:
        """Record skill loaded"""
        self.metrics["orchestration_skills_loaded"] += 1

    def record_skill_validation(self, duration_ms: float) -> None:
        """Record skill validation latency"""
        self.metrics["orchestration_skill_validation_ms"].append(duration_ms)

    def record_skill_failed(self) -> None:
        """Record skill load failure"""
        self.metrics["orchestration_skills_failed"] += 1
        self.metrics["orchestration_errors_total"] += 1

    def record_circular_dependency(self) -> None:
        """Record circular dependency detection"""
        self.metrics["orchestration_circular_deps_detected"] += 1

    def record_event_latency(self, latency_ms: float) -> None:
        """Record event log latency"""
        self.metrics["orchestration_event_log_latency_ms"].append(latency_ms)

    def record_heartbeat_latency(self, latency_ms: float) -> None:
        """Record heartbeat latency"""
        self.metrics["orchestration_heartbeat_latency_ms"].append(latency_ms)

    def update_state_db_size(self, size_bytes: int) -> None:
        """Update state database size"""
        self.metrics["orchestration_state_db_size_bytes"] = size_bytes

    def get_metrics_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format"""
        lines = []

        # Header
        lines.append("# HELP orchestration Orchestration framework metrics")
        lines.append("# TYPE orchestration counter")
        lines.append("")

        # Counters
        counter_metrics = {
            "orchestration_tasks_total": self.metrics["orchestration_tasks_total"],
            "orchestration_phases_completed": self.metrics["orchestration_phases_completed"],
            "orchestration_phases_failed": self.metrics["orchestration_phases_failed"],
            "orchestration_workers_spawned": self.metrics["orchestration_workers_spawned"],
            "orchestration_workers_completed": self.metrics["orchestration_workers_completed"],
            "orchestration_workers_failed": self.metrics["orchestration_workers_failed"],
            "orchestration_workers_stalled": self.metrics["orchestration_workers_stalled"],
            "orchestration_skills_loaded": self.metrics["orchestration_skills_loaded"],
            "orchestration_errors_total": self.metrics["orchestration_errors_total"],
            "orchestration_recoveries": self.metrics["orchestration_recoveries"],
        }

        for metric_name, value in counter_metrics.items():
            lines.append(f'{metric_name}{{run_id="{self.run_id}"}} {value}')

        lines.append("")
        lines.append("# TYPE orchestration_workers_running gauge")

        # Gauges
        gauge_metrics = {
            "orchestration_workers_running": self.metrics["orchestration_workers_running"],
            "orchestration_phases_pending": self.metrics["orchestration_phases_pending"],
            "orchestration_state_db_size_bytes": self.metrics["orchestration_state_db_size_bytes"],
        }

        for metric_name, value in gauge_metrics.items():
            lines.append(f'{metric_name}{{run_id="{self.run_id}"}} {value}')

        lines.append("")
        lines.append("# TYPE orchestration_phase_duration_seconds histogram")

        # Histograms (simplified to summary)
        if self.metrics["orchestration_phase_duration_seconds"]:
            values = self.metrics["orchestration_phase_duration_seconds"]
            lines.append(
                f'orchestration_phase_duration_seconds_count{{run_id="{self.run_id}"}} {len(values)}'
            )
            lines.append(
                f'orchestration_phase_duration_seconds_sum{{run_id="{self.run_id}"}} {sum(values):.2f}'
            )

        if self.metrics["orchestration_skill_validation_ms"]:
            values = self.metrics["orchestration_skill_validation_ms"]
            avg = sum(values) / len(values)
            lines.append(
                f'orchestration_skill_validation_ms{{run_id="{self.run_id}"}} {avg:.2f}'
            )

        lines.append("")

        return "\n".join(lines)

    def get_metrics_summary(self) -> Dict:
        """Get human-readable metrics summary"""
        phase_durations = self.metrics["orchestration_phase_duration_seconds"]
        worker_durations = self.metrics["orchestration_worker_duration_seconds"]
        validation_ms = self.metrics["orchestration_skill_validation_ms"]

        def percentile(values, p):
            if not values:
                return 0
            sorted_vals = sorted(values)
            idx = int(len(sorted_vals) * p / 100)
            return sorted_vals[min(idx, len(sorted_vals) - 1)]

        return {
            "run_id": self.run_id,
            "start_time": self.metrics["start_time"],
            "counters": {
                "phases_completed": self.metrics["orchestration_phases_completed"],
                "phases_failed": self.metrics["orchestration_phases_failed"],
                "workers_completed": self.metrics["orchestration_workers_completed"],
                "workers_failed": self.metrics["orchestration_workers_failed"],
                "workers_stalled": self.metrics["orchestration_workers_stalled"],
                "skills_loaded": self.metrics["orchestration_skills_loaded"],
                "total_errors": self.metrics["orchestration_errors_total"],
                "recovery_attempts": self.metrics["orchestration_recoveries"],
            },
            "gauges": {
                "workers_running": self.metrics["orchestration_workers_running"],
                "phases_pending": self.metrics["orchestration_phases_pending"],
            },
            "latencies": {
                "phase_duration_avg_sec": sum(phase_durations) / len(phase_durations) if phase_durations else 0,
                "phase_duration_p95_sec": percentile(phase_durations, 95) if phase_durations else 0,
                "worker_duration_avg_sec": sum(worker_durations) / len(worker_durations) if worker_durations else 0,
                "skill_validation_avg_ms": sum(validation_ms) / len(validation_ms) if validation_ms else 0,
            },
            "success_rate": (
                self.metrics["orchestration_phases_completed"] /
                (self.metrics["orchestration_phases_completed"] + self.metrics["orchestration_phases_failed"])
                if (self.metrics["orchestration_phases_completed"] + self.metrics["orchestration_phases_failed"]) > 0
                else 0
            ) * 100
        }

    def export_json(self) -> str:
        """Export metrics as JSON"""
        import json
        summary = self.get_metrics_summary()
        return json.dumps(summary, indent=2, default=str)


# Example usage
if __name__ == "__main__":
    print("\n" + "="*60)
    print("PROMETHEUS METRICS DEMO")
    print("="*60 + "\n")

    metrics = PrometheusMetrics("demo-run-phase33")

    # Simulate events
    print("Recording metrics...")

    metrics.record_phase_started(1)
    metrics.record_worker_spawned()
    metrics.record_worker_spawned()

    import time
    time.sleep(0.2)

    metrics.record_worker_completed(0.15)
    metrics.record_worker_completed(0.18)
    metrics.record_phase_completed(1, 0.25)

    metrics.record_skill_loaded()
    metrics.record_skill_validation(5.2)

    print("\n📊 Metrics Summary:")
    summary = metrics.get_metrics_summary()
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"\n{key}:")
            for k, v in value.items():
                if isinstance(v, float):
                    print(f"  {k}: {v:.2f}")
                else:
                    print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")

    print("\n📝 Prometheus Format:")
    prometheus_text = metrics.get_metrics_prometheus_format()
    print(prometheus_text[:500] + "...")

    print("\n✨ Prometheus Metrics working!")
