#!/usr/bin/env python3
"""Phase 3.1 Week 1: Comprehensive Tests - Event Sourcing + Heartbeat + Watchdog

18 test cases covering:
- Event logging and reconstruction
- Idempotency token generation and tracking
- Worker heartbeat mechanism
- Coordinator watchdog stall detection
- Wait-with-timeout pattern
- State consistency verification
"""

import unittest
import time
import threading
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

from state_store import StateStore
from event_sourcing import EventLog, EventType, IdempotencyToken, Event
from heartbeat_watchdog import WorkerHeartbeat, CoordinatorWatchdog, CoordinatorWaitWithTimeout


class TestEventSourcing(unittest.TestCase):
    """Event sourcing tests"""

    def setUp(self):
        """Setup for each test"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.store = StateStore(self.db_path)
        self.event_log = EventLog(self.store)

    def tearDown(self):
        """Cleanup"""
        self.temp_dir.cleanup()

    def test_event_logging(self):
        """Test 1: Log immutable events"""
        run_id = "test-run-001"

        event = self.event_log.log_event(
            run_id=run_id,
            event_type=EventType.TASK_REGISTERED,
            data={"task_id": "TASK-001"}
        )

        self.assertIsNotNone(event.id)
        self.assertEqual(event.run_id, run_id)
        self.assertEqual(event.type, EventType.TASK_REGISTERED)
        self.assertEqual(event.sequence, 0)

    def test_event_sequence_ordering(self):
        """Test 2: Events maintain sequence order"""
        run_id = "test-run-002"

        for i in range(5):
            self.event_log.log_event(
                run_id=run_id,
                event_type=EventType.PHASE_STARTED,
                data={"phase": i},
                phase=i
            )

        events = self.event_log.get_events(run_id)
        self.assertEqual(len(events), 5)

        for i, event in enumerate(events):
            self.assertEqual(event.sequence, i)

    def test_state_reconstruction_from_events(self):
        """Test 3: Reconstruct state from event log"""
        run_id = "test-run-003"

        # Log sequence of events
        self.event_log.log_event(
            run_id=run_id,
            event_type=EventType.TASK_REGISTERED,
            data={"task_id": "TASK-003"}
        )

        self.event_log.log_event(
            run_id=run_id,
            event_type=EventType.PHASE_STARTED,
            data={},
            phase=1
        )

        self.event_log.log_event(
            run_id=run_id,
            event_type=EventType.WORKER_HEARTBEAT,
            data={"phase": 1},
            worker_id="worker-001",
            phase=1
        )

        # Reconstruct state
        state = self.event_log.replay_events(run_id)

        self.assertEqual(state['status'], 'running')
        self.assertIn(1, state['phases'])
        self.assertEqual(state['phases'][1]['status'], 'running')
        self.assertIn('worker-001', state['workers'])

    def test_event_filtering_by_type(self):
        """Test 4: Filter events by type"""
        run_id = "test-run-004"

        self.event_log.log_event(
            run_id=run_id,
            event_type=EventType.TASK_REGISTERED,
            data={"task_id": "TASK-004"}
        )

        self.event_log.log_event(
            run_id=run_id,
            event_type=EventType.PHASE_STARTED,
            data={},
            phase=1
        )

        # Get only PHASE_STARTED events
        phase_events = self.event_log.get_events_by_type(run_id, EventType.PHASE_STARTED)
        self.assertEqual(len(phase_events), 1)
        self.assertEqual(phase_events[0].type, EventType.PHASE_STARTED)

    def test_audit_trail_export(self):
        """Test 5: Export audit trail for compliance"""
        run_id = "test-run-005"

        self.event_log.log_event(
            run_id=run_id,
            event_type=EventType.TASK_REGISTERED,
            data={"task_id": "TASK-005"}
        )

        audit_trail = self.event_log.export_audit_trail(run_id)

        self.assertEqual(len(audit_trail), 1)
        self.assertEqual(audit_trail[0]['type'], EventType.TASK_REGISTERED.value)


class TestIdempotency(unittest.TestCase):
    """Idempotency token tests"""

    def setUp(self):
        """Setup for each test"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.store = StateStore(self.db_path)
        self.idempotency = IdempotencyToken(self.store)

    def tearDown(self):
        """Cleanup"""
        self.temp_dir.cleanup()

    def test_deterministic_token_generation(self):
        """Test 6: Tokens are deterministic"""
        run_id = "test-run-006"
        phase = 1

        token1 = IdempotencyToken.generate(run_id, phase)
        token2 = IdempotencyToken.generate(run_id, phase)

        self.assertEqual(token1, token2)

    def test_token_execution_tracking(self):
        """Test 7: Track token execution"""
        run_id = "test-run-007"
        phase = 1
        token = IdempotencyToken.generate(run_id, phase)

        # Not executed yet
        self.assertFalse(self.idempotency.is_already_executed(token))

        # Mark as executed
        result = {"status": "success"}
        self.idempotency.mark_executed(token, result)

        # Now executed
        self.assertTrue(self.idempotency.is_already_executed(token))

    def test_previous_result_retrieval(self):
        """Test 8: Retrieve previous execution result"""
        run_id = "test-run-008"
        phase = 1
        token = IdempotencyToken.generate(run_id, phase)

        expected_result = {"status": "success", "output": "test"}
        self.idempotency.mark_executed(token, expected_result)

        actual_result = self.idempotency.get_previous_result(token)

        self.assertEqual(actual_result, expected_result)

    def test_retry_count_affects_token(self):
        """Test 9: Retry count creates different token"""
        run_id = "test-run-009"
        phase = 1

        token_retry0 = IdempotencyToken.generate(run_id, phase, retry_count=0)
        token_retry1 = IdempotencyToken.generate(run_id, phase, retry_count=1)

        self.assertNotEqual(token_retry0, token_retry1)


class TestWorkerHeartbeat(unittest.TestCase):
    """Worker heartbeat tests"""

    def setUp(self):
        """Setup for each test"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.store = StateStore(self.db_path)

    def tearDown(self):
        """Cleanup"""
        self.temp_dir.cleanup()

    def test_heartbeat_starts_and_stops(self):
        """Test 10: Heartbeat thread lifecycle"""
        run_id = "test-run-010"

        hb = WorkerHeartbeat(
            run_id=run_id,
            phase=1,
            state_store=self.store,
            interval_seconds=1
        )

        # Heartbeat is running
        self.assertTrue(hb._running)

        # Stop it
        hb.stop()
        self.assertFalse(hb._running)

    def test_heartbeat_updates_timestamp(self):
        """Test 11: Heartbeat sends periodic updates"""
        run_id = "test-run-011"

        hb = WorkerHeartbeat(
            run_id=run_id,
            phase=1,
            state_store=self.store,
            interval_seconds=0.1  # 100ms for testing
        )

        # Let it beat a few times
        time.sleep(0.3)

        # Check that heartbeat was recorded
        workers = self.store.get_run_workers(run_id)
        self.assertTrue(len(workers) > 0)
        self.assertIsNotNone(workers[0]['last_heartbeat'])

        hb.stop()


class TestCoordinatorWatchdog(unittest.TestCase):
    """Coordinator watchdog tests"""

    def setUp(self):
        """Setup for each test"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.store = StateStore(self.db_path)

    def tearDown(self):
        """Cleanup"""
        self.temp_dir.cleanup()

    def test_watchdog_starts_and_stops(self):
        """Test 12: Watchdog thread lifecycle"""
        watchdog = CoordinatorWatchdog(
            state_store=self.store,
            stall_timeout_seconds=30,
            check_interval_seconds=5
        )

        self.assertTrue(watchdog._running)

        watchdog.stop()
        self.assertFalse(watchdog._running)

    def test_watchdog_detects_stalled_worker(self):
        """Test 13: Watchdog detects stalled workers"""
        run_id = "test-run-013"

        # Create a stalled worker manually
        old_timestamp = (datetime.utcnow() - timedelta(seconds=45)).isoformat() + "Z"
        self.store.update_worker_heartbeat(run_id, "worker-001", 1, old_timestamp)

        stall_detected = []
        def on_stall(run_id, worker_id):
            stall_detected.append((run_id, worker_id))

        watchdog = CoordinatorWatchdog(
            state_store=self.store,
            stall_timeout_seconds=30,
            check_interval_seconds=1,
            on_stalled_callback=on_stall
        )

        # Let it check once
        time.sleep(1.5)

        # Should have detected stall
        self.assertTrue(len(stall_detected) > 0)

        watchdog.stop()

    def test_watchdog_callback_invoked(self):
        """Test 14: Watchdog calls callback on stall"""
        run_id = "test-run-014"

        # Create stalled worker
        old_timestamp = (datetime.utcnow() - timedelta(seconds=45)).isoformat() + "Z"
        self.store.update_worker_heartbeat(run_id, "worker-001", 1, old_timestamp)

        callback_invocations = []
        def track_callback(run_id, worker_id):
            callback_invocations.append({'run_id': run_id, 'worker_id': worker_id})

        watchdog = CoordinatorWatchdog(
            state_store=self.store,
            stall_timeout_seconds=30,
            check_interval_seconds=1,
            on_stalled_callback=track_callback
        )

        time.sleep(1.5)

        self.assertEqual(len(callback_invocations), 1)
        self.assertEqual(callback_invocations[0]['worker_id'], "worker-001")

        watchdog.stop()


class TestCoordinatorWaitWithTimeout(unittest.TestCase):
    """Coordinator wait-with-timeout tests"""

    def setUp(self):
        """Setup for each test"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.store = StateStore(self.db_path)
        self.waiter = CoordinatorWaitWithTimeout(self.store)

    def tearDown(self):
        """Cleanup"""
        self.temp_dir.cleanup()

    def test_wait_for_completed_workers(self):
        """Test 15: Wait for workers to complete"""
        run_id = "test-run-015"

        # Create a worker
        self.store.update_worker_heartbeat(run_id, "worker-001", 1, datetime.utcnow().isoformat() + "Z")

        # Mark as completed
        self.store.mark_worker_complete(run_id, "worker-001")

        results = self.waiter.wait_for_workers(
            run_id=run_id,
            worker_ids=["worker-001"],
            timeout_seconds=5
        )

        self.assertEqual(results["worker-001"], "success")

    def test_wait_timeout_for_hanging_workers(self):
        """Test 16: Timeout on workers that don't complete"""
        run_id = "test-run-016"

        # Create a worker
        self.store.update_worker_heartbeat(run_id, "worker-001", 1, datetime.utcnow().isoformat() + "Z")

        # Don't mark as complete
        results = self.waiter.wait_for_workers(
            run_id=run_id,
            worker_ids=["worker-001"],
            timeout_seconds=1
        )

        self.assertEqual(results["worker-001"], "timeout")

    def test_wait_for_multiple_workers(self):
        """Test 17: Wait for multiple workers with mixed outcomes"""
        run_id = "test-run-017"

        # Create workers
        self.store.update_worker_heartbeat(run_id, "worker-001", 1, datetime.utcnow().isoformat() + "Z")
        self.store.update_worker_heartbeat(run_id, "worker-002", 1, datetime.utcnow().isoformat() + "Z")

        # One completes, one doesn't
        self.store.mark_worker_complete(run_id, "worker-001")

        results = self.waiter.wait_for_workers(
            run_id=run_id,
            worker_ids=["worker-001", "worker-002"],
            timeout_seconds=1
        )

        self.assertEqual(results["worker-001"], "success")
        self.assertEqual(results["worker-002"], "timeout")

    def test_wait_for_failed_worker(self):
        """Test 18: Handle failed workers in wait"""
        run_id = "test-run-018"

        # Create a worker
        self.store.update_worker_heartbeat(run_id, "worker-001", 1, datetime.utcnow().isoformat() + "Z")

        # Manually set to failed (simulating failure)
        # In real scenario, this would be set by worker/coordinator
        from sqlite3 import connect
        with connect(self.store.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE workers SET status = 'failed' WHERE run_id = ? AND worker_id = ?",
                         (run_id, "worker-001"))
            conn.commit()

        results = self.waiter.wait_for_workers(
            run_id=run_id,
            worker_ids=["worker-001"],
            timeout_seconds=1
        )

        self.assertEqual(results["worker-001"], "failed")


class TestStateConsistency(unittest.TestCase):
    """State consistency tests"""

    def setUp(self):
        """Setup for each test"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.store = StateStore(self.db_path)

    def tearDown(self):
        """Cleanup"""
        self.temp_dir.cleanup()

    def test_state_store_persistence(self):
        """Test 1: State persists across connections"""
        run_id = "test-persist-001"

        # Write data
        self.store.update_worker_heartbeat(run_id, "worker-001", 1, datetime.utcnow().isoformat() + "Z")

        # Create new store instance
        store2 = StateStore(self.db_path)

        # Read should still work
        workers = store2.get_run_workers(run_id)
        self.assertEqual(len(workers), 1)
        self.assertEqual(workers[0]['worker_id'], "worker-001")


# Run all tests
if __name__ == "__main__":
    unittest.main(verbosity=2)
