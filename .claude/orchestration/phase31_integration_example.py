#!/usr/bin/env python3
"""Phase 3.1 Integration Example - Complete End-to-End Orchestration

Demonstrates all Phase 3.1 Week 1 components working together:
- Event sourcing for state reconstruction
- Worker heartbeat for liveness detection
- Coordinator watchdog for automatic stall recovery
- Idempotency tokens for retry-safety
- State persistence and consistency
"""

import time
import threading
from datetime import datetime
import logging

from state_store import StateStore
from event_sourcing import EventLog, EventType, IdempotencyToken
from heartbeat_watchdog import WorkerHeartbeat, CoordinatorWatchdog, CoordinatorWaitWithTimeout

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class OrchestrationCoordinator:
    """Coordinates multi-phase orchestration with worker autonomy"""

    def __init__(self, run_id: str, db_path: str = ".tasks/state.db"):
        """Initialize coordinator"""
        self.run_id = run_id
        self.store = StateStore(db_path)
        self.event_log = EventLog(self.store)
        self.idempotency = IdempotencyToken(self.store)

        self.phases = []
        self.workers = []
        self.watchdog = None
        self.waiter = CoordinatorWaitWithTimeout(self.store)

        logger.info(f"🚀 Coordinator initialized for run: {run_id}")

    def register_task(self, task_id: str, num_phases: int) -> None:
        """Register a new orchestration task"""
        logger.info(f"📋 Registering task: {task_id} with {num_phases} phases")

        # Log event
        self.event_log.log_event(
            run_id=self.run_id,
            event_type=EventType.TASK_REGISTERED,
            data={"task_id": task_id, "num_phases": num_phases}
        )

        self.phases = list(range(1, num_phases + 1))

    def start_orchestration(self) -> None:
        """Start the orchestration"""
        logger.info(f"🎬 Starting orchestration: {len(self.phases)} phases")

        # Log event
        self.event_log.log_event(
            run_id=self.run_id,
            event_type=EventType.TASK_STARTED,
            data={}
        )

        # Start watchdog
        self._start_watchdog()

    def _start_watchdog(self) -> None:
        """Start coordinator watchdog for stall detection"""
        def on_stall(run_id, worker_id):
            logger.error(f"⚠️  STALL DETECTED: {worker_id}")
            self.event_log.log_event(
                run_id=run_id,
                event_type=EventType.WORKER_STALLED,
                data={"worker_id": worker_id},
                worker_id=worker_id
            )
            # Trigger Level 2 auto-recovery
            self._escalate_recovery(run_id, worker_id)

        self.watchdog = CoordinatorWatchdog(
            state_store=self.store,
            stall_timeout_seconds=15,  # 15s for demo
            check_interval_seconds=5,
            on_stalled_callback=on_stall
        )
        logger.info("👁️  Watchdog started")

    def execute_phase(self, phase_num: int) -> Dict:
        """Execute a single phase with workers"""
        logger.info(f"\n{'='*60}")
        logger.info(f"PHASE {phase_num} START")
        logger.info(f"{'='*60}")

        # Log phase start
        self.event_log.log_event(
            run_id=self.run_id,
            event_type=EventType.PHASE_STARTED,
            data={"phase": phase_num},
            phase=phase_num
        )

        # Check idempotency
        token = IdempotencyToken.generate(self.run_id, phase_num)
        if self.idempotency.is_already_executed(token):
            logger.info(f"✅ Phase {phase_num} already executed, using cached result")
            return self.idempotency.get_previous_result(token)

        # Create checkpoint
        checkpoint_data = {
            "phase": phase_num,
            "started_at": datetime.utcnow().isoformat(),
            "workers": []
        }

        # Spawn workers for this phase
        worker_ids = []
        for i in range(2):  # 2 workers per phase for demo
            worker_id = f"worker-phase{phase_num}-{i}"

            # Create worker thread
            worker_thread = threading.Thread(
                target=self._run_worker,
                args=(worker_id, phase_num),
                daemon=True
            )
            worker_thread.start()

            worker_ids.append(worker_id)
            checkpoint_data["workers"].append(worker_id)

            logger.info(f"  ➕ Spawned: {worker_id}")

        # Wait for all workers in this phase
        logger.info(f"⏳ Waiting for {len(worker_ids)} workers...")
        results = self.waiter.wait_for_workers(
            run_id=self.run_id,
            worker_ids=worker_ids,
            timeout_seconds=30
        )

        # Process results
        phase_result = self._process_phase_results(phase_num, results)

        # Log phase completion
        if phase_result["success"]:
            self.event_log.log_event(
                run_id=self.run_id,
                event_type=EventType.PHASE_COMPLETED,
                data={"phase": phase_num, "results": phase_result},
                phase=phase_num
            )
            logger.info(f"✅ PHASE {phase_num} COMPLETE")
        else:
            self.event_log.log_event(
                run_id=self.run_id,
                event_type=EventType.PHASE_FAILED,
                data={"phase": phase_num, "reason": phase_result["reason"]},
                phase=phase_num
            )
            logger.error(f"❌ PHASE {phase_num} FAILED: {phase_result['reason']}")

        # Mark idempotency token
        self.idempotency.mark_executed(token, phase_result)

        return phase_result

    def _run_worker(self, worker_id: str, phase_num: int) -> None:
        """Worker thread: execute work with heartbeat"""
        logger.info(f"    👷 {worker_id} starting...")

        # Log worker start
        self.event_log.log_event(
            run_id=self.run_id,
            event_type=EventType.WORKER_STARTED,
            data={"worker_id": worker_id},
            worker_id=worker_id,
            phase=phase_num
        )

        # Start heartbeat
        hb = WorkerHeartbeat(
            run_id=self.run_id,
            phase=phase_num,
            state_store=self.store,
            interval_seconds=2  # 2s for demo
        )

        try:
            # Simulate work (random duration 1-3 seconds)
            import random
            duration = random.uniform(1, 3)
            logger.info(f"    👷 {worker_id} working for {duration:.1f}s...")
            time.sleep(duration)

            # Log worker completion
            self.event_log.log_event(
                run_id=self.run_id,
                event_type=EventType.WORKER_FAILED if random.random() < 0.1 else EventType.TASK_COMPLETED,
                data={"worker_id": worker_id},
                worker_id=worker_id,
                phase=phase_num
            )

            # Mark complete
            self.store.mark_worker_complete(self.run_id, worker_id)
            logger.info(f"    ✅ {worker_id} complete")

        except Exception as e:
            logger.error(f"    ❌ {worker_id} failed: {e}")
            self.store.mark_worker_timeout(self.run_id, worker_id)
        finally:
            hb.stop()

    def _process_phase_results(self, phase_num: int, results: Dict) -> Dict:
        """Process worker results for a phase"""
        success_count = sum(1 for r in results.values() if r == "success")
        total_count = len(results)

        return {
            "phase": phase_num,
            "success": success_count == total_count,
            "success_count": success_count,
            "total_count": total_count,
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": None if success_count == total_count else f"{total_count - success_count} workers failed"
        }

    def _escalate_recovery(self, run_id: str, worker_id: str) -> None:
        """Level 2 auto-recovery: escalate to coordinator"""
        logger.warning(f"🔴 Escalating {worker_id} to Level 2 recovery")

        self.event_log.log_event(
            run_id=run_id,
            event_type=EventType.ESCALATION_TO_COORDINATOR,
            data={"worker_id": worker_id},
            worker_id=worker_id
        )

        # Coordinator decision: restart or skip
        decision = "restart"

        self.event_log.log_event(
            run_id=run_id,
            event_type=EventType.COORDINATOR_DECISION,
            data={"worker_id": worker_id, "decision": decision},
            worker_id=worker_id
        )

        logger.info(f"🎯 Coordinator decision: {decision}")

    def complete_orchestration(self) -> None:
        """Complete the orchestration"""
        logger.info(f"\n{'='*60}")
        logger.info(f"ORCHESTRATION COMPLETE")
        logger.info(f"{'='*60}")

        # Reconstruct state from events
        state = self.event_log.replay_events(self.run_id)

        logger.info(f"\nFinal State:")
        logger.info(f"  Status: {state['status']}")
        logger.info(f"  Phases: {state['phases']}")
        logger.info(f"  Workers: {state['workers']}")
        logger.info(f"  Errors: {len(state['errors'])}")

        # Export audit trail
        audit_trail = self.event_log.export_audit_trail(self.run_id)
        logger.info(f"\nAudit Trail: {len(audit_trail)} events")

        for i, event in enumerate(audit_trail[-5:]):  # Last 5 events
            logger.info(f"  [{i}] {event['type']} @ {event['timestamp']}")

        # Log final status
        self.event_log.log_event(
            run_id=self.run_id,
            event_type=EventType.TASK_COMPLETED,
            data={"final_state": state}
        )

        # Cleanup
        if self.watchdog:
            self.watchdog.stop()

    def verify_consistency(self) -> bool:
        """Verify state consistency"""
        is_consistent = self.event_log.verify_consistency(self.run_id)

        if is_consistent:
            logger.info("✅ State consistency verified")
        else:
            logger.error("❌ State inconsistency detected")

        return is_consistent


# ============================================================================
# MAIN EXAMPLE
# ============================================================================

if __name__ == "__main__":
    import sys

    print("\n" + "="*70)
    print("PHASE 3.1 INTEGRATION EXAMPLE")
    print("Event Sourcing + Heartbeat + Watchdog")
    print("="*70 + "\n")

    # Initialize coordinator
    run_id = "demo-phase31-run-001"
    coordinator = OrchestrationCoordinator(run_id, ".tasks/demo.db")

    try:
        # Register and start
        coordinator.register_task("DEMO-TASK-001", num_phases=2)
        coordinator.start_orchestration()

        # Execute phases
        for phase in coordinator.phases:
            result = coordinator.execute_phase(phase)

            if not result["success"]:
                logger.error(f"Phase {phase} failed, stopping")
                break

            time.sleep(1)  # Delay between phases

        # Complete
        coordinator.complete_orchestration()

        # Verify consistency
        coordinator.verify_consistency()

        logger.info("\n✨ Demo complete!\n")

    except KeyboardInterrupt:
        logger.info("\n⚠️  Demo interrupted")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)
