#!/usr/bin/env python3
"""Phase 3 Integration Tests

Tests for State Store, Autonomous Workers, and Cloud Client
"""

import unittest
import json
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock

# Import Phase 3 components
from state_store import StateStore
from autonomous_worker import AutonomousWorker, ErrorClassifier
from cloud_client import CloudClient, WorkerInvocation, CloudProvider


class TestStateStore(unittest.TestCase):
  """State Store Tests"""

  def setUp(self):
    """Create temporary database for testing"""
    self.temp_dir = tempfile.mkdtemp()
    self.db_path = os.path.join(self.temp_dir, "test.db")
    self.store = StateStore(self.db_path, redis_url=None)

  def tearDown(self):
    """Clean up temporary files"""
    if os.path.exists(self.db_path):
      os.remove(self.db_path)
    os.rmdir(self.temp_dir)

  def test_task_registration(self):
    """Test task registration"""
    self.store.register_task("run-001", "TASK-001", "worker-001")
    task = self.store.get_task("run-001")

    self.assertEqual(task["id"], "run-001")
    self.assertEqual(task["task_id"], "TASK-001")
    self.assertEqual(task["worker_id"], "worker-001")

  def test_phase_state_save_and_retrieve(self):
    """Test phase state persistence"""
    self.store.register_task("run-001", "TASK-001", "worker-001")

    # Save phase state
    self.store.save_phase_state(
      run_id="run-001",
      phase=1,
      status="success",
      artifact_names=["output.json"],
      duration_seconds=45.2
    )

    # Retrieve phase state
    state = self.store.get_phase_state("run-001", 1)
    self.assertEqual(state["status"], "success")
    self.assertEqual(state["duration"], 45.2)
    self.assertIn("output.json", state["artifact_names"])

  def test_artifact_storage(self):
    """Test artifact storage and retrieval"""
    self.store.register_task("run-001", "TASK-001", "worker-001")

    # Save artifact
    content = b"{'key': 'value'}"
    self.store.save_artifact("run-001", 1, "test.json", content)

    # Retrieve artifact
    retrieved = self.store.get_artifact("run-001", 1, "test.json")
    self.assertEqual(retrieved, content)

  def test_checkpoint_recovery(self):
    """Test checkpoint creation and restoration"""
    self.store.register_task("run-001", "TASK-001", "worker-001")

    # Create checkpoint
    checkpoint_data = {"records": 1000, "last_id": 999}
    self.store.create_checkpoint(
      run_id="run-001",
      phase=1,
      checkpoint_name="data-collected",
      state=checkpoint_data
    )

    # Restore checkpoint
    restored = self.store.restore_from_checkpoint(
      run_id="run-001",
      phase=1,
      checkpoint_name="data-collected"
    )

    self.assertEqual(restored["records"], 1000)
    self.assertEqual(restored["last_id"], 999)

  def test_lock_acquire_release(self):
    """Test distributed lock functionality"""
    # Acquire lock
    acquired = self.store.acquire_lock(
      lock_name="test-lock",
      run_id="run-001",
      worker_id="worker-001"
    )
    self.assertTrue(acquired)

    # Check lock status
    locked = self.store.is_locked("test-lock")
    self.assertTrue(locked)

    # Release lock
    self.store.release_lock("test-lock")
    locked = self.store.is_locked("test-lock")
    self.assertFalse(locked)


class TestErrorClassifier(unittest.TestCase):
  """Error Classifier Tests"""

  def test_timeout_is_recoverable(self):
    """Test that timeout errors are classified as recoverable"""
    severity, strategies = ErrorClassifier.classify(
      "TimeoutError",
      "Connection timed out"
    )

    self.assertEqual(severity.value, "recoverable")
    self.assertTrue(len(strategies) > 0)

  def test_connection_error_is_recoverable(self):
    """Test that connection errors are recoverable"""
    severity, strategies = ErrorClassifier.classify(
      "ConnectionError",
      "Database unreachable"
    )

    self.assertEqual(severity.value, "recoverable")

  def test_permission_denied_is_fatal(self):
    """Test that permission errors are fatal"""
    severity, strategies = ErrorClassifier.classify(
      "PermissionError",
      "Access denied to resource"
    )

    self.assertEqual(severity.value, "fatal")
    self.assertEqual(len(strategies), 0)  # No recovery strategies

  def test_schema_mismatch_is_escalatable(self):
    """Test that schema mismatches are escalatable"""
    severity, strategies = ErrorClassifier.classify(
      "ValueError",
      "Schema mismatch"
    )

    self.assertEqual(severity.value, "escalatable")
    self.assertTrue(len(strategies) > 0)

  def test_unknown_error_escalates(self):
    """Test that unknown errors escalate to coordinator"""
    severity, strategies = ErrorClassifier.classify(
      "CustomError",
      "Something went wrong"
    )

    self.assertEqual(severity.value, "unknown")


class TestAutonomousWorker(unittest.TestCase):
  """Autonomous Worker Tests"""

  def setUp(self):
    """Create worker with mock coordinator"""
    self.worker = AutonomousWorker("worker-001")
    self.coordinator_called = False

  def mock_coordinator(self, context):
    """Mock coordinator callback"""
    self.coordinator_called = True
    return "retry"

  def test_successful_phase_execution(self):
    """Test successful phase execution without errors"""
    def phase_fn(config):
      return {"status": "success"}

    result = self.worker.execute_phase(1, {}, phase_fn)

    self.assertEqual(result["status"], "success")
    self.assertEqual(result["retries"], 0)

  def test_auto_recovery_timeout(self):
    """Test auto-recovery of timeout errors"""
    call_count = [0]

    def phase_fn(config):
      call_count[0] += 1
      if call_count[0] == 1:
        raise TimeoutError("Connection timed out")
      return {"status": "success"}

    result = self.worker.execute_phase(1, {}, phase_fn)

    # Should retry and succeed
    self.assertEqual(result["status"], "success")
    self.assertEqual(result["retries"], 1)

  def test_fatal_error_no_recovery(self):
    """Test that fatal errors don't trigger recovery"""
    def phase_fn(config):
      raise PermissionError("Access denied")

    result = self.worker.execute_phase(1, {}, phase_fn)

    self.assertEqual(result["status"], "fatal")
    self.assertIsNone(result.get("recovery_action"))

  def test_coordinator_escalation(self):
    """Test escalation to coordinator"""
    self.worker.coordinator_callback = self.mock_coordinator

    def phase_fn(config):
      raise ValueError("Schema mismatch")

    result = self.worker.execute_phase(1, {}, phase_fn)

    # Coordinator should have been called
    self.assertTrue(self.coordinator_called)


class TestCloudClient(unittest.TestCase):
  """Cloud Client Tests"""

  @patch('cloud_client.boto3')
  def test_cloud_client_initialization_aws(self, mock_boto3):
    """Test AWS Lambda client initialization"""
    config = {
      "provider": "aws_lambda",
      "region": "us-east-1",
      "cost_monitoring": True
    }

    client = CloudClient(config)
    self.assertEqual(client.provider, CloudProvider.AWS_LAMBDA)
    self.assertEqual(client.region, "us-east-1")

  @patch('cloud_client.run_v2')
  def test_cloud_client_initialization_gcp(self, mock_run_v2):
    """Test GCP Cloud Run client initialization"""
    config = {
      "provider": "gcp_cloud_run",
      "region": "us-central1"
    }

    client = CloudClient(config)
    self.assertEqual(client.provider, CloudProvider.GCP_CLOUD_RUN)

  def test_cost_estimation_aws_lambda(self):
    """Test AWS Lambda cost estimation"""
    config = {"provider": "aws_lambda", "cost_monitoring": True}
    client = CloudClient(config)

    invocation = WorkerInvocation(
      phase=1,
      phase_config={},
      worker_location="aws",
      timeout_seconds=300,
      max_retries=3
    )

    cost = client._estimate_cost(invocation)
    # Should estimate some cost
    self.assertGreater(cost, 0)

  def test_cost_calculation_lambda(self):
    """Test AWS Lambda cost calculation"""
    config = {"provider": "aws_lambda"}
    client = CloudClient(config)

    # 300 seconds with 1GB = 300 GB-seconds
    # $0.0000002 per GB-second = $0.00006 = 0.6 cents
    cost = client._calculate_lambda_cost(300)
    self.assertAlmostEqual(cost, 0.006, places=3)  # 0.6 cents

  def test_cost_calculation_cloud_run(self):
    """Test GCP Cloud Run cost calculation"""
    config = {"provider": "gcp_cloud_run"}
    client = CloudClient(config)

    # 300 seconds with 1 vCPU = 300 CPU-seconds
    # $0.00001667 per CPU-second = $0.005 = 0.5 cents
    cost = client._calculate_cloudrun_cost(300)
    self.assertAlmostEqual(cost, 0.5001, places=3)  # ~0.5 cents


class TestIntegration(unittest.TestCase):
  """Integration Tests - State Store + Worker + Cloud Client"""

  def setUp(self):
    """Set up for integration tests"""
    self.temp_dir = tempfile.mkdtemp()
    self.db_path = os.path.join(self.temp_dir, "integration.db")

    self.state_store = StateStore(self.db_path, redis_url=None)
    self.worker = AutonomousWorker("integration-worker")
    self.cloud_client = CloudClient({
      "provider": "aws_lambda",
      "fallback_to_local": True
    })

  def test_full_orchestration_flow(self):
    """Test full orchestration: register → phase → save state"""
    run_id = "run-integration-001"

    # 1. Register task
    self.state_store.register_task(run_id, "TASK-001", "worker-001")

    # 2. Execute phase with state
    def phase_fn(config):
      return {"data": "test", "count": 100}

    result = self.worker.execute_phase(1, {}, phase_fn)

    # 3. Save phase state
    self.state_store.save_phase_state(
      run_id=run_id,
      phase=1,
      status=result["status"],
      duration_seconds=result.get("duration", 0)
    )

    # 4. Save artifact
    self.state_store.save_artifact(
      run_id=run_id,
      phase=1,
      name="result.json",
      content=json.dumps(result).encode()
    )

    # 5. Verify state was saved
    phase_state = self.state_store.get_phase_state(run_id, 1)
    self.assertEqual(phase_state["status"], "success")

    artifact = self.state_store.get_artifact(run_id, 1, "result.json")
    self.assertIsNotNone(artifact)


def run_tests():
  """Run all tests"""
  # Create test suite
  loader = unittest.TestLoader()
  suite = unittest.TestSuite()

  suite.addTests(loader.loadTestsFromTestCase(TestStateStore))
  suite.addTests(loader.loadTestsFromTestCase(TestErrorClassifier))
  suite.addTests(loader.loadTestsFromTestCase(TestAutonomousWorker))
  suite.addTests(loader.loadTestsFromTestCase(TestCloudClient))
  suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

  # Run tests
  runner = unittest.TextTestRunner(verbosity=2)
  result = runner.run(suite)

  return result.wasSuccessful()


if __name__ == "__main__":
  success = run_tests()
  exit(0 if success else 1)
