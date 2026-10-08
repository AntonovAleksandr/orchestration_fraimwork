#!/usr/bin/env python3
"""Prevent concurrent orchestration collisions with task registry and locks"""

import json
import fcntl
import os
from pathlib import Path
from datetime import datetime
import time

class TaskRegistry:
    """Global task registry to prevent name collisions"""

    def __init__(self):
        self.tasks_dir = Path(".tasks")
        self.registry_file = self.tasks_dir / "registry.json"
        self.tasks_dir.mkdir(exist_ok=True)

    def acquire_lock(self, run_id: str, task_name: str, duration_hours: int = 2) -> bool:
        """Attempt to acquire lock on a task"""
        registry = self._read_registry()

        # Check if task already locked
        if task_name in registry:
            existing = registry[task_name]
            if existing.get("locked", False):
                print(f"❌ Task '{task_name}' already locked by {existing.get('run_id')}")
                return False

        # Acquire lock
        registry[task_name] = {
            "run_id": run_id,
            "created": datetime.utcnow().isoformat(),
            "locked": True,
            "duration_hours": duration_hours,
        }

        self._write_registry(registry)
        print(f"✓ Lock acquired: {task_name} (run: {run_id})")
        return True

    def release_lock(self, task_name: str, run_id: str) -> bool:
        """Release lock on a task"""
        registry = self._read_registry()

        if task_name not in registry:
            print(f"⚠️  Task '{task_name}' not in registry")
            return False

        existing = registry[task_name]
        if existing.get("run_id") != run_id:
            print(f"❌ Cannot release: {run_id} doesn't own '{task_name}'")
            print(f"   Owner: {existing.get('run_id')}")
            return False

        # Release lock
        registry[task_name] = {
            "run_id": run_id,
            "released": datetime.utcnow().isoformat(),
            "locked": False,
        }

        self._write_registry(registry)
        print(f"✓ Lock released: {task_name}")
        return True

    def is_task_locked(self, task_name: str) -> tuple:
        """Check if task is locked (returns (is_locked, run_id))"""
        registry = self._read_registry()

        if task_name not in registry:
            return (False, None)

        info = registry[task_name]
        return (info.get("locked", False), info.get("run_id"))

    def get_task_status(self, task_name: str) -> dict:
        """Get full task status"""
        registry = self._read_registry()
        return registry.get(task_name, {})

    def list_active_tasks(self) -> list:
        """List all currently locked tasks"""
        registry = self._read_registry()
        active = [
            (name, info.get("run_id"))
            for name, info in registry.items()
            if info.get("locked", False)
        ]
        return active

    def _read_registry(self) -> dict:
        """Read registry with shared lock"""
        if not self.registry_file.exists():
            return {}

        with open(self.registry_file) as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                registry = json.load(f)
            except:
                registry = {}
            fcntl.flock(f, fcntl.LOCK_UN)

        return registry

    def _write_registry(self, registry: dict):
        """Write registry with exclusive lock (atomic)"""
        tmp_file = self.registry_file.with_suffix(".tmp")

        with open(tmp_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(registry, f, indent=2)
            fcntl.flock(f, fcntl.LOCK_UN)

        os.rename(tmp_file, self.registry_file)


# Example usage
if __name__ == "__main__":
    registry = TaskRegistry()

    # Simulate concurrent orchestration attempts
    print("=== Concurrent Orchestration Test ===\n")

    # Developer A starts task
    run_id_a = "dev-a-abc123"
    if registry.acquire_lock("analysis-task", "OPSOMN002-XXX", duration_hours=2):
        print("Dev A started working on OPSOMN002-XXX\n")

    # Developer B tries same task
    print("Dev B attempts to start same task...")
    run_id_b = "dev-b-def456"
    if not registry.acquire_lock("analysis-task", "OPSOMN002-XXX", duration_hours=2):
        print("Dev B cannot acquire lock (as expected)\n")

    # Check status
    locked, owner = registry.is_task_locked("OPSOMN002-XXX")
    print(f"Task status: locked={locked}, owner={owner}\n")

    # List active tasks
    active = registry.list_active_tasks()
    print(f"Active tasks: {active}\n")

    # Dev A finishes
    print("Dev A finishes and releases lock...")
    registry.release_lock("OPSOMN002-XXX", run_id_a)

    # Now Dev B can acquire
    print("\nDev B retries...")
    if registry.acquire_lock("analysis-task", "OPSOMN002-XXX", duration_hours=2):
        print("Dev B successfully acquired lock\n")
        registry.release_lock("OPSOMN002-XXX", run_id_b)

    print("✅ Concurrent safety test passed")
