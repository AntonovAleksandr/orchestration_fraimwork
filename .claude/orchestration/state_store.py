#!/usr/bin/env python3
"""Phase 3.1: Unified State Store - SQLite + Redis + Event Log

Persistent state management with:
- SQLite for durability
- Redis for fast cache/heartbeat
- Event log for state reconstruction
- Worker heartbeat tracking
- Stall detection support
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class StateStore:
    """Unified state store with SQLite + Redis + Event support"""

    def __init__(self, db_path: str = ".tasks/state.db"):
        """Initialize state store"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize SQLite schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Phases table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS phases (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    phase_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    data TEXT NOT NULL
                )
            """)

            # Workers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workers (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    phase INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    last_heartbeat TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Events table (for event sourcing)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    worker_id TEXT,
                    phase INTEGER
                )
            """)

            # Execution tokens (for idempotency)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_tokens (
                    token TEXT PRIMARY KEY,
                    result TEXT NOT NULL,
                    executed_at TEXT NOT NULL
                )
            """)

            # Checkpoints table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    phase INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            conn.commit()

    def save_event(self, event_dict: Dict) -> None:
        """Save event to log (append-only)"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO events (id, run_id, type, data, timestamp, sequence, worker_id, phase)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_dict['id'],
                    event_dict['run_id'],
                    event_dict['type'],
                    json.dumps(event_dict['data']),
                    event_dict['timestamp'],
                    event_dict['sequence'],
                    event_dict.get('worker_id'),
                    event_dict.get('phase')
                ))
                conn.commit()

    def get_events(self, run_id: str, from_sequence: int = 0, to_sequence: Optional[int] = None) -> List[Dict]:
        """Get events in order"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if to_sequence is None:
                cursor.execute("""
                    SELECT id, run_id, type, data, timestamp, sequence, worker_id, phase
                    FROM events
                    WHERE run_id = ? AND sequence >= ?
                    ORDER BY sequence ASC
                """, (run_id, from_sequence))
            else:
                cursor.execute("""
                    SELECT id, run_id, type, data, timestamp, sequence, worker_id, phase
                    FROM events
                    WHERE run_id = ? AND sequence >= ? AND sequence <= ?
                    ORDER BY sequence ASC
                """, (run_id, from_sequence, to_sequence))

            return [
                {
                    'id': row[0],
                    'run_id': row[1],
                    'type': row[2],
                    'data': json.loads(row[3]),
                    'timestamp': row[4],
                    'sequence': row[5],
                    'worker_id': row[6],
                    'phase': row[7]
                }
                for row in cursor.fetchall()
            ]

    def update_worker_heartbeat(self, run_id: str, worker_id: str, phase: int, timestamp: str) -> None:
        """Update worker heartbeat timestamp"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check if worker exists
                cursor.execute("SELECT id FROM workers WHERE run_id = ? AND worker_id = ?", (run_id, worker_id))
                worker = cursor.fetchone()

                if worker:
                    # Update existing
                    cursor.execute("""
                        UPDATE workers
                        SET last_heartbeat = ?, updated_at = ?
                        WHERE run_id = ? AND worker_id = ?
                    """, (timestamp, datetime.utcnow().isoformat() + "Z", run_id, worker_id))
                else:
                    # Create new
                    import uuid
                    cursor.execute("""
                        INSERT INTO workers (id, run_id, worker_id, phase, status, last_heartbeat, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()),
                        run_id,
                        worker_id,
                        phase,
                        'running',
                        timestamp,
                        datetime.utcnow().isoformat() + "Z",
                        datetime.utcnow().isoformat() + "Z"
                    ))

                conn.commit()

    def get_run_workers(self, run_id: str) -> List[Dict]:
        """Get all workers for a run"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, run_id, worker_id, phase, status, last_heartbeat, created_at, updated_at
                FROM workers
                WHERE run_id = ?
            """, (run_id,))

            return [
                {
                    'id': row[0],
                    'run_id': row[1],
                    'worker_id': row[2],
                    'phase': row[3],
                    'status': row[4],
                    'last_heartbeat': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                }
                for row in cursor.fetchall()
            ]

    def get_active_runs(self) -> List[Dict]:
        """Get all active runs"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT run_id FROM workers WHERE status IN ('running', 'pending')
            """)

            return [{'id': row[0]} for row in cursor.fetchall()]

    def mark_worker_stalled(self, run_id: str, worker_id: str) -> None:
        """Mark worker as stalled"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE workers
                    SET status = 'stalled', updated_at = ?
                    WHERE run_id = ? AND worker_id = ?
                """, (datetime.utcnow().isoformat() + "Z", run_id, worker_id))
                conn.commit()

    def get_worker_status(self, run_id: str, worker_id: str) -> Optional[str]:
        """Get worker status"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status FROM workers WHERE run_id = ? AND worker_id = ?
            """, (run_id, worker_id))

            row = cursor.fetchone()
            return row[0] if row else None

    def mark_worker_complete(self, run_id: str, worker_id: str) -> None:
        """Mark worker as complete"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE workers
                    SET status = 'completed', updated_at = ?
                    WHERE run_id = ? AND worker_id = ?
                """, (datetime.utcnow().isoformat() + "Z", run_id, worker_id))
                conn.commit()

    def mark_worker_timeout(self, run_id: str, worker_id: str) -> None:
        """Mark worker as timed out"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE workers
                    SET status = 'timeout', updated_at = ?
                    WHERE run_id = ? AND worker_id = ?
                """, (datetime.utcnow().isoformat() + "Z", run_id, worker_id))
                conn.commit()

    def get_run_state(self, run_id: str) -> Dict:
        """Get current run state"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get task
            cursor.execute("SELECT status FROM tasks WHERE run_id = ?", (run_id,))
            task = cursor.fetchone()

            # Get phases
            cursor.execute("""
                SELECT phase_number, status FROM phases WHERE run_id = ? ORDER BY phase_number
            """, (run_id,))
            phases = {row[0]: {'status': row[1]} for row in cursor.fetchall()}

            # Get workers
            cursor.execute("""
                SELECT worker_id, status FROM workers WHERE run_id = ?
            """, (run_id,))
            workers = {row[0]: {'status': row[1]} for row in cursor.fetchall()}

            # Get errors
            cursor.execute("""
                SELECT type, data FROM events WHERE run_id = ? AND type = 'error_detected'
            """, (run_id,))
            errors = [json.loads(row[1]) for row in cursor.fetchall()]

            return {
                'run_id': run_id,
                'status': task[0] if task else 'pending',
                'phases': phases,
                'workers': workers,
                'errors': errors
            }

    def has_execution_token(self, token: str) -> bool:
        """Check if token was already executed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM execution_tokens WHERE token = ?", (token,))
            return cursor.fetchone() is not None

    def save_execution_token(self, token: str, result: Dict) -> None:
        """Mark token as executed"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO execution_tokens (token, result, executed_at)
                    VALUES (?, ?, ?)
                """, (token, json.dumps(result), datetime.utcnow().isoformat() + "Z"))
                conn.commit()

    def get_execution_result(self, token: str) -> Optional[Dict]:
        """Get result of previous execution"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT result FROM execution_tokens WHERE token = ?", (token,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None

    def health(self) -> Dict[str, str]:
        """Check state store health"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tasks")
                count = cursor.fetchone()[0]
            return {'sqlite': 'healthy', 'tasks_count': count}
        except Exception as e:
            return {'sqlite': 'unhealthy', 'error': str(e)}


if __name__ == "__main__":
    # Quick test
    store = StateStore(".tasks/state-test.db")
    print("✅ State Store initialized")
    print(f"Health: {store.health()}")
