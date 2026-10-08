#!/usr/bin/env python3
"""Phase 3: Autonomous Worker with Error Recovery & Decision Logic

Implements worker autonomy levels:
- Level 1: Auto-recovery (retry, backoff, fallback)
- Level 2: Coordinator escalation (ask for decision)
- Level 3: Full autonomy (solve independently - future)
"""

import time
import json
from enum import Enum
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta


class ErrorSeverity(Enum):
    """Error classification"""
    RECOVERABLE = "recoverable"      # Can auto-recover
    ESCALATABLE = "escalatable"      # Need coordinator decision
    FATAL = "fatal"                  # Must fail
    UNKNOWN = "unknown"              # Can't classify


class RecoveryStrategy(Enum):
    """Recovery strategies available"""
    RETRY_BACKOFF = "retry_backoff"           # Retry with exponential backoff
    FALLBACK_VALUE = "fallback_value"         # Use default/fallback value
    SKIP_PHASE = "skip_phase"                 # Skip this phase
    CHECKPOINT_RESTORE = "checkpoint_restore" # Restore from checkpoint
    COORDINATOR_ASK = "coordinator_ask"       # Ask coordinator


@dataclass
class ErrorContext:
    """Error information for classification"""
    error_type: str
    error_message: str
    timestamp: str
    phase: int
    retry_count: int = 0
    recoveries_attempted: int = 0


class ErrorClassifier:
    """Classify errors and determine recovery strategy"""

    RECOVERABLE_ERRORS = {
        "timeout": (ErrorSeverity.RECOVERABLE, [
            RecoveryStrategy.RETRY_BACKOFF,
            RecoveryStrategy.CHECKPOINT_RESTORE,
        ]),
        "connection_error": (ErrorSeverity.RECOVERABLE, [
            RecoveryStrategy.RETRY_BACKOFF,
            RecoveryStrategy.COORDINATOR_ASK,
        ]),
        "rate_limit": (ErrorSeverity.RECOVERABLE, [
            RecoveryStrategy.RETRY_BACKOFF,
            RecoveryStrategy.SKIP_PHASE,
        ]),
        "temporary_failure": (ErrorSeverity.RECOVERABLE, [
            RecoveryStrategy.RETRY_BACKOFF,
        ]),
        "quota_exceeded": (ErrorSeverity.ESCALATABLE, [
            RecoveryStrategy.COORDINATOR_ASK,
        ]),
        "schema_mismatch": (ErrorSeverity.ESCALATABLE, [
            RecoveryStrategy.COORDINATOR_ASK,
        ]),
        "validation_failed": (ErrorSeverity.ESCALATABLE, [
            RecoveryStrategy.COORDINATOR_ASK,
        ]),
    }

    FATAL_ERRORS = {
        "permission_denied",
        "resource_not_found",
        "corrupted_data",
        "invalid_config",
    }

    @classmethod
    def classify(cls, error_type: str, error_msg: str) -> tuple:
        """Classify error and get recovery strategies

        Returns: (severity, strategies)
        """
        error_type_lower = error_type.lower()

        # Check fatal errors first
        for fatal in cls.FATAL_ERRORS:
            if fatal in error_type_lower or fatal in error_msg.lower():
                return (ErrorSeverity.FATAL, [])

        # Check recoverable errors
        if error_type_lower in cls.RECOVERABLE_ERRORS:
            return cls.RECOVERABLE_ERRORS[error_type_lower]

        # Check by message patterns
        msg_lower = error_msg.lower()
        if "timeout" in msg_lower or "deadline" in msg_lower:
            return cls.RECOVERABLE_ERRORS.get("timeout", (ErrorSeverity.UNKNOWN, []))
        if "connection" in msg_lower or "network" in msg_lower:
            return cls.RECOVERABLE_ERRORS.get("connection_error", (ErrorSeverity.UNKNOWN, []))
        if "quota" in msg_lower or "limit" in msg_lower:
            return cls.RECOVERABLE_ERRORS.get("quota_exceeded", (ErrorSeverity.UNKNOWN, []))

        return (ErrorSeverity.UNKNOWN, [RecoveryStrategy.COORDINATOR_ASK])


class AutonomousWorker:
    """Worker with autonomous error recovery"""

    def __init__(self, worker_id: str, coordinator_callback: Optional[Callable] = None):
        """Initialize autonomous worker

        Args:
            worker_id: Unique worker identifier
            coordinator_callback: Function to ask coordinator for decisions
        """
        self.worker_id = worker_id
        self.coordinator_callback = coordinator_callback
        self.max_retries = 3
        self.initial_backoff = 1  # seconds
        self.max_backoff = 60  # seconds

    def execute_phase(self, phase: int, phase_config: Dict, phase_fn: Callable) -> Dict:
        """Execute phase with autonomous error recovery

        Args:
            phase: Phase number
            phase_config: Phase configuration
            phase_fn: Function to execute (should raise exceptions on error)

        Returns: {status, result, error, recovery_action}
        """
        print(f"[Worker {self.worker_id}] Executing Phase {phase}...")

        start_time = time.time()
        retry_count = 0

        while retry_count < self.max_retries:
            try:
                # Execute phase
                result = phase_fn(phase_config)

                duration = time.time() - start_time
                return {
                    "status": "success",
                    "result": result,
                    "duration": duration,
                    "retries": retry_count,
                }

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)

                # Classify error
                severity, strategies = ErrorClassifier.classify(error_type, error_msg)
                print(f"[Worker {self.worker_id}] Error detected: {error_type} (severity: {severity.value})")

                # Handle based on severity
                if severity == ErrorSeverity.FATAL:
                    print(f"[Worker {self.worker_id}] ❌ FATAL ERROR - cannot recover")
                    return {
                        "status": "fatal",
                        "error": error_msg,
                        "error_type": error_type,
                        "recovery_action": None,
                    }

                elif severity == ErrorSeverity.RECOVERABLE:
                    # Try auto-recovery
                    recovery_action = self._auto_recover(error_type, strategies, retry_count)

                    if recovery_action == RecoveryStrategy.RETRY_BACKOFF:
                        backoff = min(self.initial_backoff * (2 ** retry_count), self.max_backoff)
                        print(f"[Worker {self.worker_id}] ⏳ Retry in {backoff}s (attempt {retry_count + 1}/{self.max_retries})")
                        time.sleep(backoff)
                        retry_count += 1
                        continue

                    elif recovery_action == RecoveryStrategy.CHECKPOINT_RESTORE:
                        print(f"[Worker {self.worker_id}] 🔄 Attempting checkpoint restore...")
                        # Checkpoint restore would be implemented here
                        return {
                            "status": "partial",
                            "error": error_msg,
                            "recovery_action": "checkpoint_restored",
                        }

                    elif recovery_action == RecoveryStrategy.SKIP_PHASE:
                        print(f"[Worker {self.worker_id}] ⏭️  Skipping phase")
                        return {
                            "status": "skipped",
                            "reason": error_msg,
                            "recovery_action": "skipped",
                        }

                elif severity == ErrorSeverity.ESCALATABLE:
                    # Ask coordinator
                    if self.coordinator_callback:
                        decision = self._ask_coordinator(phase, error_type, error_msg, strategies)

                        if decision == "retry":
                            print(f"[Worker {self.worker_id}] 🔄 Coordinator says: retry")
                            time.sleep(1)
                            retry_count += 1
                            continue
                        elif decision == "skip":
                            print(f"[Worker {self.worker_id}] ⏭️  Coordinator says: skip")
                            return {
                                "status": "skipped",
                                "reason": f"Coordinator decision: {error_msg}",
                                "recovery_action": "coordinator_skip",
                            }
                        elif decision == "abort":
                            print(f"[Worker {self.worker_id}] ❌ Coordinator says: abort")
                            return {
                                "status": "failed",
                                "error": error_msg,
                                "recovery_action": "coordinator_abort",
                            }
                    else:
                        # No coordinator, can't escalate
                        return {
                            "status": "escalation_required",
                            "error": error_msg,
                            "error_type": error_type,
                            "severity": severity.value,
                        }

                else:  # UNKNOWN
                    # Unknown error - escalate if possible
                    if self.coordinator_callback:
                        decision = self._ask_coordinator(phase, error_type, error_msg, strategies)
                        if decision == "retry":
                            retry_count += 1
                            continue

                    return {
                        "status": "failed",
                        "error": error_msg,
                        "error_type": error_type,
                        "severity": "unknown",
                    }

        # Max retries exceeded
        return {
            "status": "failed",
            "error": "Max retries exceeded",
            "retries": retry_count,
            "recovery_action": "max_retries_exceeded",
        }

    def _auto_recover(self, error_type: str, strategies: list, retry_count: int) -> Optional[RecoveryStrategy]:
        """Decide which auto-recovery to attempt"""
        if not strategies:
            return None

        # Prefer strategies based on retry count
        if retry_count < 2:
            # Early retries: prefer retry-backoff
            if RecoveryStrategy.RETRY_BACKOFF in strategies:
                return RecoveryStrategy.RETRY_BACKOFF

        # Try strategies in order
        for strategy in strategies:
            if strategy in [RecoveryStrategy.RETRY_BACKOFF, RecoveryStrategy.SKIP_PHASE]:
                return strategy

        return strategies[0] if strategies else None

    def _ask_coordinator(self, phase: int, error_type: str, error_msg: str,
                        strategies: list) -> str:
        """Ask coordinator for decision

        Returns: "retry", "skip", or "abort"
        """
        if not self.coordinator_callback:
            return "abort"

        context = {
            "phase": phase,
            "error_type": error_type,
            "error_message": error_msg,
            "possible_actions": [s.value for s in strategies],
            "worker_id": self.worker_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        decision = self.coordinator_callback(context)
        return decision or "abort"


# Example usage and scenarios
if __name__ == "__main__":
    print("Autonomous Worker Examples")
    print("=" * 60)

    # Scenario 1: Recoverable error with auto-retry
    print("\n1. Timeout error (auto-recoverable)")
    print("-" * 60)

    def phase_1_with_timeout(config):
        """Simulate phase that times out once"""
        if not hasattr(phase_1_with_timeout, 'called'):
            phase_1_with_timeout.called = True
            raise TimeoutError("Connection timed out (temporary)")
        return {"data": "success"}

    worker = AutonomousWorker("worker-001")
    result = worker.execute_phase(1, {}, phase_1_with_timeout)
    print(f"Result: {result}")

    # Scenario 2: Escalatable error needing coordinator
    print("\n2. Schema mismatch (escalatable)")
    print("-" * 60)

    def coordinator_mock(context):
        """Mock coordinator that decides based on error"""
        print(f"  [Coordinator] Received: {context['error_type']}")
        print(f"  [Coordinator] Possible actions: {context['possible_actions']}")
        return "retry"

    def phase_2_with_schema_error(config):
        raise ValueError("Schema mismatch in response")

    worker2 = AutonomousWorker("worker-002", coordinator_callback=coordinator_mock)
    result2 = worker2.execute_phase(2, {}, phase_2_with_schema_error)
    print(f"Result: {result2}")

    # Scenario 3: Fatal error
    print("\n3. Fatal error (permission denied)")
    print("-" * 60)

    def phase_3_with_fatal_error(config):
        raise PermissionError("Access denied to resource")

    worker3 = AutonomousWorker("worker-003")
    result3 = worker3.execute_phase(3, {}, phase_3_with_fatal_error)
    print(f"Result: {result3}")

    print("\n✅ Autonomous Worker examples complete")
