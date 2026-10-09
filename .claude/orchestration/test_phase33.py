#!/usr/bin/env python3
"""Phase 3.3 Week 3: Tests for DAG Builder and Prometheus Metrics

12 comprehensive tests covering:
- DAG node and edge management
- Dependency tracking
- Critical path detection
- Prometheus metrics collection
- Export formats (JSON, Prometheus, Mermaid)
"""

import unittest
import json
from dag_builder import DAGBuilder, Node, Edge, NodeStatus, EdgeType
from prometheus_metrics import PrometheusMetrics


class TestDAGBuilder(unittest.TestCase):
    """DAG Builder tests"""

    def setUp(self):
        """Setup for each test"""
        self.dag = DAGBuilder("test-run-phase33")

    def test_add_phase_node(self):
        """Test 1: Add phase node to DAG"""
        node = self.dag.add_phase(1, "Phase 1")

        self.assertIn("phase-1", self.dag.nodes)
        self.assertEqual(node.type, "phase")
        self.assertEqual(node.status, NodeStatus.PENDING)

    def test_add_worker_node(self):
        """Test 2: Add worker node to DAG"""
        node = self.dag.add_worker(1, 1, "Worker 1")

        self.assertIn("phase-1-worker-1", self.dag.nodes)
        self.assertEqual(node.type, "worker")
        self.assertEqual(node.metadata["phase_number"], 1)

    def test_add_phase_dependency(self):
        """Test 3: Add phase-to-phase dependency"""
        self.dag.add_phase(1)
        self.dag.add_phase(2)

        edge = self.dag.add_phase_dependency(1, 2)

        self.assertIn(edge, self.dag.edges)
        self.assertEqual(edge.edge_type, EdgeType.PHASE_DEPENDENCY)

    def test_update_node_status(self):
        """Test 4: Update node status with timing"""
        node = self.dag.add_phase(1)

        self.dag.update_node_status("phase-1", NodeStatus.RUNNING)
        self.assertEqual(node.status, NodeStatus.RUNNING)
        self.assertIsNotNone(node.started_at)

        self.dag.update_node_status("phase-1", NodeStatus.COMPLETED)
        self.assertEqual(node.status, NodeStatus.COMPLETED)
        self.assertIsNotNone(node.completed_at)
        self.assertGreater(node.duration_ms, 0)

    def test_get_phase_nodes(self):
        """Test 5: Get all nodes for a phase"""
        self.dag.add_phase(1)
        self.dag.add_worker(1, 1)
        self.dag.add_worker(1, 2)

        phase_nodes = self.dag.get_phase_nodes(1)

        self.assertEqual(len(phase_nodes), 3)  # Phase + 2 workers

    def test_get_node_predecessors(self):
        """Test 6: Get predecessor nodes"""
        self.dag.add_phase(1)
        self.dag.add_phase(2)
        self.dag.add_phase_dependency(1, 2)

        predecessors = self.dag.get_node_predecessors("phase-2")

        self.assertIn("phase-1", predecessors)

    def test_get_node_successors(self):
        """Test 7: Get successor nodes"""
        self.dag.add_phase(1)
        self.dag.add_phase(2)
        self.dag.add_phase_dependency(1, 2)

        successors = self.dag.get_node_successors("phase-1")

        self.assertIn("phase-2", successors)

    def test_critical_path_detection(self):
        """Test 8: Find critical path"""
        # Create chain: 1 -> 2 -> 3
        self.dag.add_phase(1)
        self.dag.add_phase(2)
        self.dag.add_phase(3)
        self.dag.add_phase_dependency(1, 2)
        self.dag.add_phase_dependency(2, 3)

        critical_path = self.dag.get_critical_path()

        self.assertEqual(len(critical_path), 3)
        self.assertEqual(critical_path[0], "phase-1")
        self.assertEqual(critical_path[2], "phase-3")

    def test_execution_stats(self):
        """Test 9: Get execution statistics"""
        self.dag.add_phase(1)
        self.dag.add_phase(2)

        self.dag.update_node_status("phase-1", NodeStatus.COMPLETED)

        stats = self.dag.get_execution_stats()

        self.assertEqual(stats["total_nodes"], 2)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["pending"], 1)

    def test_dag_export_json(self):
        """Test 10: Export DAG as JSON"""
        self.dag.add_phase(1)

        dag_json = self.dag.to_json()

        # Should be valid JSON
        data = json.loads(dag_json)
        self.assertEqual(data["run_id"], "test-run-phase33")
        self.assertIn("nodes", data)
        self.assertIn("edges", data)

    def test_dag_export_mermaid(self):
        """Test 11: Export DAG as Mermaid diagram"""
        self.dag.add_phase(1)
        self.dag.add_phase(2)
        self.dag.add_phase_dependency(1, 2)

        mermaid = self.dag.to_mermaid()

        self.assertIn("graph TD", mermaid)
        self.assertIn("phase-1", mermaid)
        self.assertIn("phase-2", mermaid)
        self.assertIn("-->", mermaid)


class TestPrometheusMetrics(unittest.TestCase):
    """Prometheus Metrics tests"""

    def setUp(self):
        """Setup for each test"""
        self.metrics = PrometheusMetrics("test-run-phase33")

    def test_record_phase_events(self):
        """Test 12: Record phase lifecycle events"""
        self.metrics.record_phase_started(1)
        self.metrics.record_phase_completed(1, 2.5)

        self.assertEqual(self.metrics.metrics["orchestration_phases_completed"], 1)
        self.assertIn(2.5, self.metrics.metrics["orchestration_phase_duration_seconds"])

    def test_record_worker_events(self):
        """Test 13: Record worker lifecycle events"""
        self.metrics.record_worker_spawned()
        self.metrics.record_worker_spawned()
        self.metrics.record_worker_completed(1.2)
        self.metrics.record_worker_completed(1.5)

        self.assertEqual(self.metrics.metrics["orchestration_workers_spawned"], 2)
        self.assertEqual(self.metrics.metrics["orchestration_workers_completed"], 2)
        self.assertEqual(self.metrics.metrics["orchestration_workers_running"], 0)

    def test_record_error_events(self):
        """Test 14: Record error events"""
        self.metrics.record_worker_failed()
        self.metrics.record_skill_failed()
        self.metrics.record_worker_stalled()

        self.assertEqual(self.metrics.metrics["orchestration_errors_total"], 3)
        self.assertEqual(self.metrics.metrics["orchestration_workers_failed"], 1)
        self.assertEqual(self.metrics.metrics["orchestration_skills_failed"], 1)
        self.assertEqual(self.metrics.metrics["orchestration_workers_stalled"], 1)

    def test_record_latency_metrics(self):
        """Test 15: Record latency measurements"""
        self.metrics.record_skill_validation(5.2)
        self.metrics.record_skill_validation(6.1)
        self.metrics.record_event_latency(0.5)

        self.assertEqual(len(self.metrics.metrics["orchestration_skill_validation_ms"]), 2)
        self.assertIn(0.5, self.metrics.metrics["orchestration_event_log_latency_ms"])

    def test_metrics_summary(self):
        """Test 16: Generate metrics summary"""
        self.metrics.record_phase_started(1)
        self.metrics.record_phase_completed(1, 1.5)
        self.metrics.record_phase_started(2)
        self.metrics.record_phase_failed(2, "error")

        summary = self.metrics.get_metrics_summary()

        self.assertIn("counters", summary)
        self.assertIn("gauges", summary)
        self.assertIn("latencies", summary)
        self.assertIn("success_rate", summary)

    def test_prometheus_format_export(self):
        """Test 17: Export metrics in Prometheus text format"""
        self.metrics.record_phase_completed(1, 1.2)
        self.metrics.record_skill_loaded()

        prometheus_text = self.metrics.get_metrics_prometheus_format()

        # Should contain metric names
        self.assertIn("orchestration_phases_completed", prometheus_text)
        self.assertIn("orchestration_skills_loaded", prometheus_text)
        # Should contain values
        self.assertIn("1", prometheus_text)

    def test_json_export(self):
        """Test 18: Export metrics as JSON"""
        self.metrics.record_phase_completed(1, 1.0)

        json_text = self.metrics.export_json()

        # Should be valid JSON
        data = json.loads(json_text)
        self.assertIn("run_id", data)
        self.assertIn("counters", data)


# Run tests
if __name__ == "__main__":
    unittest.main(verbosity=2)
