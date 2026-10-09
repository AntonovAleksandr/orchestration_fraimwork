#!/usr/bin/env python3
"""Phase 3.1 Week 1: Heartbeat + Watchdog - Stall Detection & Recovery

Worker sends heartbeat every 5 seconds.
Coordinator watchdog checks every 10 seconds for stalled workers.
Automatic detection and restart of stalled workers.
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class WorkerStatus:
    """Current status of a worker"""
    worker_id: str
    run_id: str
    phase: int
    last_heartbeat: str  # ISO timestamp
    is_stalled: bool = False
    stall_detected_at: Optional[str] = None
    restart_attempts: int = 0


class WorkerHeartbeat:
    """Worker sends heartbeat to prove it's alive"""

    def __init__(self, run_id: str, phase: int, state_store, interval_seconds: int = 5):
        """
        Start heartbeat thread

        Args:
            run_id: orchestration run ID
            phase: current phase number
            state_store: StateStore instance
            interval_seconds: heartbeat interval (default 5 sec)
        """
        self.run_id = run_id
        self.phase = phase
        self.state_store = state_store
        self.interval = interval_seconds

        self._running = True
        self._thread = threading.Thread(target=self._beat_loop, daemon=True)
        self._thread.start()

        logger.info(f"🫀 Heartbeat started: {run_id} phase {phase}")

    def _beat_loop(self):
        """Send heartbeat every interval"""
        while self._running:
            try:
                self.send_heartbeat()
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            time.sleep(self.interval)

    def send_heartbeat(self):
        """Send heartbeat to state store"""
        timestamp = datetime.utcnow().isoformat() + "Z"

        self.state_store.update_worker_heartbeat(
            run_id=self.run_id,
            worker_id=f"worker-{self.phase}",
            phase=self.phase,
            timestamp=timestamp
        )

    def stop(self):
        """Stop heartbeat"""
        self._running = False
        self._thread.join(timeout=5)
        logger.info(f"🫀 Heartbeat stopped: {self.run_id}")


class CoordinatorWatchdog:
    """Coordinator monitors for stalled workers"""

    def __init__(
        self,
        state_store,
        stall_timeout_seconds: int = 30,
        check_interval_seconds: int = 10,
        on_stalled_callback: Optional[Callable] = None
    ):
        """
        Start watchdog thread

        Args:
            state_store: StateStore instance
            stall_timeout_seconds: max time without heartbeat (default 30 sec)
            check_interval_seconds: how often to check (default 10 sec)
            on_stalled_callback: function to call when stall detected
        """
        self.state_store = state_store
        self.stall_timeout = timedelta(seconds=stall_timeout_seconds)
        self.check_interval = check_interval_seconds
        self.on_stalled_callback = on_stalled_callback

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

        logger.info(f"👁️  Watchdog started (timeout: {stall_timeout_seconds}s, check interval: {check_interval_seconds}s)")

    def _watch_loop(self):
        """Monitor for stalled workers"""
        while self._running:
            try:
                self._check_workers()
            except Exception as e:
                logger.error(f"Watchdog error: {e}")

            time.sleep(self.check_interval)

    def _check_workers(self):
        """Check all active workers for stalls"""
        # Get all active runs
        active_runs = self.state_store.get_active_runs()

        for run in active_runs:
            run_id = run['id']

            # Get all workers for this run
            workers = self.state_store.get_run_workers(run_id)

            for worker in workers:
                worker_id = worker['worker_id']
                last_heartbeat_str = worker.get('last_heartbeat')

                if not last_heartbeat_str:
                    continue

                # Parse timestamp
                try:
                    last_heartbeat = datetime.fromisoformat(last_heartbeat_str.replace('Z', '+00:00'))
                except:
                    continue

                # Check if stalled
                age = datetime.utcnow().replace(tzinfo=None) - last_heartbeat.replace(tzinfo=None)

                if age > self.stall_timeout:
                    self._handle_stalled_worker(run_id, worker_id, age)

    def _handle_stalled_worker(self, run_id: str, worker_id: str, age: timedelta):
        """Handle detection of stalled worker"""
        logger.warning(f"⚠️  Stalled worker detected: {worker_id} (no heartbeat for {age.total_seconds():.0f}s)")

        # Mark as stalled
        self.state_store.mark_worker_stalled(run_id, worker_id)

        # Call callback if registered
        if self.on_stalled_callback:
            try:
                self.on_stalled_callback(run_id, worker_id)
            except Exception as e:
                logger.error(f"Stall callback error: {e}")

    def stop(self):
        """Stop watchdog"""
        self._running = False
        self._thread.join(timeout=5)
        logger.info(f"👁️  Watchdog stopped")


class CoordinatorWaitWithTimeout:
    """Async wait for workers with timeout"""

    def __init__(self, state_store, default_timeout_seconds: int = 300):
        """
        Initialize wait helper

        Args:
            state_store: StateStore instance
            default_timeout_seconds: default timeout (5 min)
        """
        self.state_store = state_store
        self.default_timeout = default_timeout_seconds

    def wait_for_workers(
        self,
        run_id: str,
        worker_ids: list,
        timeout_seconds: Optional[int] = None,
        check_interval_seconds: float = 5.0
    ) -> Dict[str, str]:
        """
        Wait for workers to complete with timeout

        Args:
            run_id: orchestration run ID
            worker_ids: list of worker IDs to wait for
            timeout_seconds: max wait time (or use default)
            check_interval_seconds: how often to check status

        Returns:
            dict mapping worker_id → status (success/timeout/failed)
        """
        timeout = timeout_seconds or self.default_timeout
        start_time = time.time()
        results = {}
        pending = set(worker_ids)

        logger.info(f"⏳ Waiting for {len(worker_ids)} workers (timeout: {timeout}s)")

        while pending and (time.time() - start_time) < timeout:
            # Check status of pending workers
            completed = []

            for worker_id in pending:
                status = self.state_store.get_worker_status(run_id, worker_id)

                if status == "completed":
                    results[worker_id] = "success"
                    completed.append(worker_id)
                    logger.info(f"✅ Worker completed: {worker_id}")

                elif status == "failed":
                    results[worker_id] = "failed"
                    completed.append(worker_id)
                    logger.warning(f"❌ Worker failed: {worker_id}")

                elif status == "stalled":
                    results[worker_id] = "stalled"
                    completed.append(worker_id)
                    logger.error(f"⚠️  Worker stalled: {worker_id}")

            # Remove completed workers
            for worker_id in completed:
                pending.discard(worker_id)

            if not pending:
                break

            # Wait before next check
            time.sleep(check_interval_seconds)

        # Handle timeout
        remaining_time = timeout - (time.time() - start_time)

        if pending and remaining_time <= 0:
            logger.error(f"⏱️  Timeout waiting for workers: {pending}")

            for worker_id in pending:
                results[worker_id] = "timeout"
                self.state_store.mark_worker_timeout(run_id, worker_id)

        logger.info(f"✅ Wait complete: {results}")
        return results


# Example usage
if __name__ == "__main__":
    from state_store import StateStore

    # Initialize
    store = StateStore(".tasks/state.db")

    print("Heartbeat + Watchdog Setup")
    print("=" * 60)

    # Start heartbeat for a worker
    run_id = "run-phase31-002"

    hb = WorkerHeartbeat(
        run_id=run_id,
        phase=1,
        state_store=store,
        interval_seconds=3  # Every 3 sec for demo
    )
    print("✅ Worker heartbeat started")

    # Start watchdog
    def on_stall(run_id, worker_id):
        print(f"🔴 STALL DETECTED: {worker_id} - initiating auto-restart")

    watchdog = CoordinatorWatchdog(
        state_store=store,
        stall_timeout_seconds=10,  # 10 sec for demo
        check_interval_seconds=5,
        on_stalled_callback=on_stall
    )
    print("✅ Coordinator watchdog started")

    # Wait with timeout
    waiter = CoordinatorWaitWithTimeout(store)
    print("\n⏳ Simulating worker wait...")

    # Simulate worker completing
    time.sleep(2)
    store.mark_worker_complete(run_id, "worker-1")

    results = waiter.wait_for_workers(
        run_id=run_id,
        worker_ids=["worker-1", "worker-2"],
        timeout_seconds=15
    )

    print(f"\n✅ Results: {results}")

    # Cleanup
    hb.stop()
    watchdog.stop()

    print("\n✨ Heartbeat + Watchdog working!")
