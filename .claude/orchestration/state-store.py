#!/usr/bin/env python3
"""Phase 3: Persistent State Store with SQLite + Redis Cache

Provides durable, fault-tolerant state management for orchestration framework.
- SQLite: source of truth, persistent
- Redis: hot data cache, <100ms latency
- Automatic failover if cache fails
- Audit logging for compliance
"""

import sqlite3
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class PhaseStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseState:
    run_id: str
    phase: int
    status: str
    artifact_names: List[str]
    created_at: str
    updated_at: str
    duration_seconds: float
    error_message: Optional[str] = None


class StateStore:
    """Persistent state management with SQLite + Redis cache"""

    def __init__(self, db_path: str = ".tasks/state.db", redis_url: Optional[str] = None):
        """Initialize state store

        Args:
            db_path: Path to SQLite database
            redis_url: Optional Redis URL (e.g., "redis://localhost:6379/0")
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite
        self.db = sqlite3.connect(str(self.db_path))
        self.db.row_factory = sqlite3.Row
        self._init_schema()

        # Initialize Redis cache (optional)
        self.redis = None
        self.cache_ttl = 3600  # 1 hour
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis = redis.from_url(redis_url)
                self.redis.ping()
                print(f"✓ Redis cache connected: {redis_url}")
            except Exception as e:
                print(f"⚠️  Redis unavailable (will use SQLite only): {e}")
                self.redis = None

    def _init_schema(self):
        """Initialize database schema"""
        cursor = self.db.cursor()

        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                run_id TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                worker_id TEXT,
                lock_acquired_at TEXT,
                lock_expires_at TEXT
            )
        """)

        # Phases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phases (
                run_id TEXT NOT NULL,
                phase INTEGER NOT NULL,
                status TEXT NOT NULL,
                artifact_names TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                duration_seconds REAL,
                error_message TEXT,
                PRIMARY KEY (run_id, phase),
                FOREIGN KEY (run_id) REFERENCES tasks(run_id)
            )
        """)

        # Artifacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                phase INTEGER NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                checksum TEXT,
                UNIQUE(run_id, phase, name),
                FOREIGN KEY (run_id) REFERENCES tasks(run_id)
            )
        """)

        # Locks table (durable lock registry)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locks (
                task_name TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                worker_id TEXT
            )
        """)

        # Audit log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                run_id TEXT,
                action TEXT NOT NULL,
                details TEXT,
                user TEXT
            )
        """)

        # Checkpoints (phase recovery points)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                run_id TEXT NOT NULL,
                phase INTEGER NOT NULL,
                checkpoint_name TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (run_id, phase, checkpoint_name),
                FOREIGN KEY (run_id) REFERENCES tasks(run_id)
            )
        """)

        self.db.commit()

    def register_task(self, run_id: str, task_name: str, worker_id: str = None) -> bool:
        """Register a new orchestration task"""
        now = datetime.utcnow().isoformat()

        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO tasks (run_id, task_name, created_at, updated_at, status, worker_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, task_name, now, now, "active", worker_id))

            self.db.commit()
            self._audit_log(run_id, "task_registered", f"task={task_name}, worker={worker_id}")
            self._invalidate_cache(f"task:{run_id}")

            return True
        except sqlite3.IntegrityError:
            return False

    def save_phase_state(self, run_id: str, phase: int, status: str,
                        artifact_names: List[str], duration: float,
                        error_msg: str = None) -> bool:
        """Save phase execution state"""
        now = datetime.utcnow().isoformat()

        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO phases
                (run_id, phase, status, artifact_names, created_at, updated_at, duration_seconds, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, phase, status, json.dumps(artifact_names), now, now, duration, error_msg))

            self.db.commit()
            self._audit_log(run_id, f"phase_{phase}_complete", f"status={status}, duration={duration}s")
            self._invalidate_cache(f"phase:{run_id}:{phase}")

            return True
        except Exception as e:
            print(f"❌ Failed to save phase state: {e}")
            return False

    def get_phase_state(self, run_id: str, phase: int) -> Optional[PhaseState]:
        """Get phase execution state (with cache)"""
        cache_key = f"phase:{run_id}:{phase}"

        # Try cache first
        if self.redis:
            cached = self.redis.get(cache_key)
            if cached:
                return PhaseState(**json.loads(cached))

        # Query SQLite
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM phases WHERE run_id = ? AND phase = ?
        """, (run_id, phase))

        row = cursor.fetchone()
        if not row:
            return None

        state = PhaseState(
            run_id=row['run_id'],
            phase=row['phase'],
            status=row['status'],
            artifact_names=json.loads(row['artifact_names'] or '[]'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            duration_seconds=row['duration_seconds'],
            error_message=row['error_message']
        )

        # Cache result
        if self.redis:
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(asdict(state)))

        return state

    def save_artifact(self, run_id: str, phase: int, name: str, content: str) -> bool:
        """Save phase artifact (findings, plan, report, etc.)"""
        now = datetime.utcnow().isoformat()
        checksum = hashlib.sha256(content.encode()).hexdigest()

        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO artifacts (run_id, phase, name, content, created_at, checksum)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, phase, name, content, now, checksum))

            self.db.commit()
            self._invalidate_cache(f"artifact:{run_id}:{phase}:{name}")

            return True
        except Exception as e:
            print(f"❌ Failed to save artifact: {e}")
            return False

    def get_artifact(self, run_id: str, phase: int, name: str) -> Optional[str]:
        """Get artifact content (with cache)"""
        cache_key = f"artifact:{run_id}:{phase}:{name}"

        # Try cache
        if self.redis:
            cached = self.redis.get(cache_key)
            if cached:
                return cached.decode()

        # Query SQLite
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT content FROM artifacts WHERE run_id = ? AND phase = ? AND name = ?
        """, (run_id, phase, name))

        row = cursor.fetchone()
        if not row:
            return None

        content = row[0]

        # Cache result
        if self.redis:
            self.redis.setex(cache_key, self.cache_ttl, content)

        return content

    def acquire_lock(self, task_name: str, run_id: str, worker_id: str,
                    duration_seconds: int = 7200) -> bool:
        """Acquire durable lock on task"""
        now = datetime.utcnow()
        expires_at = (now + timedelta(seconds=duration_seconds)).isoformat()

        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO locks (task_name, run_id, acquired_at, expires_at, worker_id)
                VALUES (?, ?, ?, ?, ?)
            """, (task_name, run_id, now.isoformat(), expires_at, worker_id))

            self.db.commit()
            self._invalidate_cache(f"lock:{task_name}")

            return True
        except Exception as e:
            print(f"❌ Failed to acquire lock: {e}")
            return False

    def release_lock(self, task_name: str, run_id: str) -> bool:
        """Release lock on task"""
        try:
            cursor = self.db.cursor()
            cursor.execute("DELETE FROM locks WHERE task_name = ? AND run_id = ?",
                          (task_name, run_id))

            self.db.commit()
            self._invalidate_cache(f"lock:{task_name}")

            return True
        except Exception as e:
            print(f"❌ Failed to release lock: {e}")
            return False

    def is_locked(self, task_name: str) -> tuple:
        """Check if task is locked (returns (is_locked, run_id, expires_at))"""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT run_id, expires_at FROM locks WHERE task_name = ?
        """, (task_name,))

        row = cursor.fetchone()
        if not row:
            return (False, None, None)

        # Check if lock expired
        expires_at = datetime.fromisoformat(row['expires_at'])
        if datetime.utcnow() > expires_at:
            # Lock expired, clean up
            self.release_lock(task_name, row['run_id'])
            return (False, None, None)

        return (True, row['run_id'], row['expires_at'])

    def create_checkpoint(self, run_id: str, phase: int, checkpoint_name: str, data: Dict) -> bool:
        """Create recovery checkpoint for phase"""
        now = datetime.utcnow().isoformat()

        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO checkpoints (run_id, phase, checkpoint_name, data, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, phase, checkpoint_name, json.dumps(data), now))

            self.db.commit()
            self._invalidate_cache(f"checkpoint:{run_id}:{phase}:{checkpoint_name}")

            return True
        except Exception as e:
            print(f"❌ Failed to create checkpoint: {e}")
            return False

    def restore_from_checkpoint(self, run_id: str, phase: int, checkpoint_name: str) -> Optional[Dict]:
        """Restore state from checkpoint"""
        cache_key = f"checkpoint:{run_id}:{phase}:{checkpoint_name}"

        # Try cache
        if self.redis:
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

        # Query SQLite
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT data FROM checkpoints WHERE run_id = ? AND phase = ? AND checkpoint_name = ?
        """, (run_id, phase, checkpoint_name))

        row = cursor.fetchone()
        if not row:
            return None

        data = json.loads(row[0])

        # Cache result
        if self.redis:
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(data))

        return data

    def get_task_history(self, run_id: str) -> List[Dict]:
        """Get full task execution history"""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM phases WHERE run_id = ? ORDER BY phase ASC
        """, (run_id,))

        return [dict(row) for row in cursor.fetchall()]

    def _audit_log(self, run_id: str, action: str, details: str = None, user: str = None):
        """Write to audit log"""
        now = datetime.utcnow().isoformat()

        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO audit_log (timestamp, run_id, action, details, user)
                VALUES (?, ?, ?, ?, ?)
            """, (now, run_id, action, details, user or "system"))

            self.db.commit()
        except Exception as e:
            print(f"⚠️  Audit log failed: {e}")

    def _invalidate_cache(self, key: str):
        """Invalidate cache entry"""
        if self.redis:
            try:
                self.redis.delete(key)
            except Exception as e:
                print(f"⚠️  Cache invalidation failed: {e}")

    def cleanup_expired_locks(self):
        """Clean up expired locks"""
        now = datetime.utcnow().isoformat()

        try:
            cursor = self.db.cursor()
            cursor.execute("DELETE FROM locks WHERE expires_at < ?", (now,))

            deleted = cursor.rowcount
            self.db.commit()

            if deleted > 0:
                print(f"✓ Cleaned up {deleted} expired locks")
        except Exception as e:
            print(f"⚠️  Lock cleanup failed: {e}")

    def close(self):
        """Close database connection"""
        if self.db:
            self.db.close()


# Example usage
if __name__ == "__main__":
    import sys

    # Initialize state store
    store = StateStore()

    print("State Store Example")
    print("=" * 60)

    # Register task
    run_id = "test-run-001"
    store.register_task(run_id, "OPSOMN002-XXX", worker_id="dev-001")
    print(f"✓ Task registered: {run_id}")

    # Save phase 1 state
    store.save_phase_state(
        run_id,
        phase=1,
        status="success",
        artifact_names=["findings.md"],
        duration=45.2
    )
    print("✓ Phase 1 saved")

    # Save artifact
    store.save_artifact(run_id, 1, "findings.md", "# Phase 1 Findings\n\n- Found 3 sources\n- Identified all services")
    print("✓ Artifact saved")

    # Retrieve state
    state = store.get_phase_state(run_id, 1)
    print(f"✓ Phase state: {state.status}, duration: {state.duration_seconds}s")

    # Create checkpoint
    store.create_checkpoint(run_id, 1, "data-collected", {"records": 100, "sources": 3})
    print("✓ Checkpoint created")

    # Restore from checkpoint
    checkpoint = store.restore_from_checkpoint(run_id, 1, "data-collected")
    print(f"✓ Checkpoint restored: {checkpoint}")

    # Test locks
    acquired = store.acquire_lock("OPSOMN002-XXX", run_id, "dev-001")
    print(f"✓ Lock acquired: {acquired}")

    is_locked, owner, expires = store.is_locked("OPSOMN002-XXX")
    print(f"✓ Lock status: locked={is_locked}, owner={owner}")

    store.release_lock("OPSOMN002-XXX", run_id)
    print("✓ Lock released")

    # Cleanup
    store.close()
    print("\n✅ State Store example complete")
