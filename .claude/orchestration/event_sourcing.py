#!/usr/bin/env python3
"""Phase 3.1 Week 1: Event Sourcing - Immutable Event Log

Enables complete state reconstruction and recovery from any point.
All state changes logged as immutable events.

Pattern: Temporal-style event sourcing
"""

import json
import uuid
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict


class EventType(Enum):
    """All possible events in orchestration"""
    # Task lifecycle
    TASK_REGISTERED = "task_registered"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Phase lifecycle
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    PHASE_SKIPPED = "phase_skipped"

    # Worker lifecycle
    WORKER_STARTED = "worker_started"
    WORKER_HEARTBEAT = "worker_heartbeat"
    WORKER_STALLED = "worker_stalled"
    WORKER_RESTARTED = "worker_restarted"
    WORKER_FAILED = "worker_failed"

    # Error recovery
    ERROR_DETECTED = "error_detected"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_SUCCEEDED = "recovery_succeeded"
    RECOVERY_FAILED = "recovery_failed"
    ESCALATION_TO_COORDINATOR = "escalation_to_coordinator"
    COORDINATOR_DECISION = "coordinator_decision"

    # Checkpoint
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"


@dataclass
class Event:
    """Immutable event in the orchestration log"""
    id: str  # Unique event ID
    run_id: str  # Which run this belongs to
    type: EventType
    data: Dict[str, Any]  # Event payload
    timestamp: str  # ISO format
    sequence: int  # Order within run
    worker_id: Optional[str] = None
    phase: Optional[int] = None

    def to_dict(self) -> Dict:
        """Convert to dict for storage"""
        return {
            'id': self.id,
            'run_id': self.run_id,
            'type': self.type.value,
            'data': self.data,
            'timestamp': self.timestamp,
            'sequence': self.sequence,
            'worker_id': self.worker_id,
            'phase': self.phase
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Event':
        """Create from stored dict"""
        data['type'] = EventType(data['type'])
        return cls(**data)


class EventLog:
    """Immutable event log for complete state reconstruction"""

    def __init__(self, state_store):
        """Initialize event log with persistence"""
        self.state_store = state_store
        self._sequence_counter = {}  # per run_id
        self._lock = threading.Lock()

    def log_event(
        self,
        run_id: str,
        event_type: EventType,
        data: Dict[str, Any],
        worker_id: Optional[str] = None,
        phase: Optional[int] = None
    ) -> Event:
        """Log an immutable event"""
        with self._lock:
            # Generate sequence number
            if run_id not in self._sequence_counter:
                self._sequence_counter[run_id] = 0

            sequence = self._sequence_counter[run_id]
            self._sequence_counter[run_id] += 1

        # Create event
        event = Event(
            id=str(uuid.uuid4()),
            run_id=run_id,
            type=event_type,
            data=data,
            timestamp=datetime.utcnow().isoformat() + "Z",
            sequence=sequence,
            worker_id=worker_id,
            phase=phase
        )

        # Persist (append-only)
        self.state_store.save_event(event.to_dict())

        return event

    def get_events(
        self,
        run_id: str,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None
    ) -> List[Event]:
        """Get events for a run in order"""
        events = self.state_store.get_events(run_id, from_sequence, to_sequence)
        return [Event.from_dict(e) for e in events]

    def get_events_by_type(
        self,
        run_id: str,
        event_type: EventType
    ) -> List[Event]:
        """Get all events of a specific type"""
        all_events = self.state_store.get_events(run_id)
        return [
            Event.from_dict(e) for e in all_events
            if e['type'] == event_type.value
        ]

    def replay_events(self, run_id: str) -> Dict[str, Any]:
        """Reconstruct state by replaying all events"""
        events = self.get_events(run_id)

        state = {
            'run_id': run_id,
            'status': 'pending',
            'phases': {},
            'workers': {},
            'checkpoints': {},
            'errors': [],
            'recoveries': []
        }

        for event in events:
            state = self._apply_event(state, event)

        return state

    def _apply_event(self, state: Dict, event: Event) -> Dict:
        """Apply single event to state"""
        if event.type == EventType.TASK_REGISTERED:
            state['status'] = 'running'
            state['task_id'] = event.data.get('task_id')

        elif event.type == EventType.PHASE_STARTED:
            phase = event.phase
            state['phases'][phase] = {'status': 'running', 'started_at': event.timestamp}

        elif event.type == EventType.PHASE_COMPLETED:
            phase = event.phase
            state['phases'][phase]['status'] = 'completed'
            state['phases'][phase]['completed_at'] = event.timestamp

        elif event.type == EventType.WORKER_HEARTBEAT:
            worker_id = event.worker_id
            if worker_id not in state['workers']:
                state['workers'][worker_id] = {}
            state['workers'][worker_id]['last_heartbeat'] = event.timestamp
            state['workers'][worker_id]['phase'] = event.phase

        elif event.type == EventType.WORKER_STALLED:
            worker_id = event.worker_id
            state['workers'][worker_id]['status'] = 'stalled'
            state['workers'][worker_id]['stalled_at'] = event.timestamp

        elif event.type == EventType.CHECKPOINT_CREATED:
            checkpoint_name = event.data.get('checkpoint_name')
            if event.phase not in state['checkpoints']:
                state['checkpoints'][event.phase] = {}
            state['checkpoints'][event.phase][checkpoint_name] = {
                'created_at': event.timestamp,
                'data': event.data.get('data')
            }

        elif event.type == EventType.ERROR_DETECTED:
            state['errors'].append({
                'timestamp': event.timestamp,
                'type': event.data.get('error_type'),
                'message': event.data.get('error_message'),
                'phase': event.phase,
                'worker_id': event.worker_id
            })

        elif event.type == EventType.RECOVERY_STARTED:
            state['recoveries'].append({
                'timestamp': event.timestamp,
                'strategy': event.data.get('strategy'),
                'phase': event.phase
            })

        elif event.type == EventType.TASK_COMPLETED:
            state['status'] = 'completed'
            state['completed_at'] = event.timestamp

        elif event.type == EventType.TASK_FAILED:
            state['status'] = 'failed'
            state['failed_at'] = event.timestamp
            state['failure_reason'] = event.data.get('reason')

        return state

    def verify_consistency(self, run_id: str) -> bool:
        """Verify that current state matches replayed state"""
        current_state = self.state_store.get_run_state(run_id)
        replayed_state = self.replay_events(run_id)

        # Compare critical fields
        checks = [
            current_state.get('status') == replayed_state.get('status'),
            current_state.get('phases') == replayed_state.get('phases'),
            len(current_state.get('errors', [])) == len(replayed_state.get('errors', []))
        ]

        is_consistent = all(checks)

        if not is_consistent:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"State inconsistency detected for {run_id}")
            logger.error(f"Current: {current_state}")
            logger.error(f"Replayed: {replayed_state}")

        return is_consistent

    def export_audit_trail(self, run_id: str) -> List[Dict]:
        """Export full audit trail for compliance"""
        events = self.get_events(run_id)
        return [e.to_dict() for e in events]


class IdempotencyToken:
    """Prevents duplicate work via idempotent tokens"""

    def __init__(self, state_store):
        self.state_store = state_store

    @staticmethod
    def generate(run_id: str, phase: int, retry_count: int = 0) -> str:
        """Generate deterministic token for phase execution"""
        token_data = f"{run_id}:{phase}:{retry_count}"
        import hashlib
        return hashlib.sha256(token_data.encode()).hexdigest()

    def is_already_executed(self, token: str) -> bool:
        """Check if this token was already executed"""
        return self.state_store.has_execution_token(token)

    def mark_executed(self, token: str, result: Dict):
        """Mark token as executed with result"""
        self.state_store.save_execution_token(token, result)

    def get_previous_result(self, token: str) -> Optional[Dict]:
        """Get result of previous execution (if exists)"""
        return self.state_store.get_execution_result(token)


# Example usage
if __name__ == "__main__":
    from state_store import StateStore

    # Initialize
    store = StateStore(".tasks/state.db")
    event_log = EventLog(store)
    idempotency = IdempotencyToken(store)

    print("Event Sourcing Setup Complete")
    print("=" * 60)

    # Example: Log some events
    run_id = "run-phase31-001"

    event_log.log_event(
        run_id=run_id,
        event_type=EventType.TASK_REGISTERED,
        data={"task_id": "OPSOMN002-310"}
    )
    print("✅ Task registered event logged")

    event_log.log_event(
        run_id=run_id,
        event_type=EventType.PHASE_STARTED,
        data={"phase_config": {}},
        phase=1
    )
    print("✅ Phase 1 started event logged")

    event_log.log_event(
        run_id=run_id,
        event_type=EventType.WORKER_HEARTBEAT,
        data={"phase": 1},
        worker_id="worker-001",
        phase=1
    )
    print("✅ Worker heartbeat logged")

    # Reconstruct state from events
    state = event_log.replay_events(run_id)
    print(f"\n✅ State reconstructed from events:")
    print(f"   Status: {state['status']}")
    print(f"   Phases: {state['phases']}")
    print(f"   Workers: {state['workers']}")

    # Idempotency example
    token = IdempotencyToken.generate(run_id, phase=1)
    print(f"\n✅ Idempotency token: {token[:16]}...")

    if not idempotency.is_already_executed(token):
        print("   (Not yet executed)")
        idempotency.mark_executed(token, {"result": "success"})
    else:
        print("   Already executed - skipping")

    print("\n✨ Event Sourcing & Idempotency working!")
