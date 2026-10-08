#!/usr/bin/env python3
"""Worker isolation with RUN_ID for concurrent orchestration safety"""

import os
import uuid
import json
import fcntl
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta

class WorkerIsolation:
    """Manage isolated worker state with RUN_ID"""

    def __init__(self, run_id: str = None):
        """Initialize with optional run_id (auto-generate if not provided)"""
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.tasks_dir = Path(".tasks")
        self.run_dir = self.tasks_dir / self.run_id
        self.registry_file = self.tasks_dir / "registry.json"

        # Ensure directories exist
        self.tasks_dir.mkdir(exist_ok=True)
        self.run_dir.mkdir(exist_ok=True)

    def register_run(self, task_name: str, phases: list):
        """Register this run in the global registry"""
        registry = self._read_registry()

        registry[self.run_id] = {
            "created": datetime.utcnow().isoformat(),
            "task": task_name,
            "phases": phases,
            "status": "active",
            "lock": True,
        }

        self._write_registry(registry)
        print(f"✓ Run {self.run_id} registered")

    def release_run(self):
        """Release lock and mark run as complete"""
        registry = self._read_registry()

        if self.run_id in registry:
            registry[self.run_id]["status"] = "complete"
            registry[self.run_id]["lock"] = False
            registry[self.run_id]["completed"] = datetime.utcnow().isoformat()

        self._write_registry(registry)
        print(f"✓ Run {self.run_id} released")

    def send_phase_message(self, phase: int, status: str, data: dict = None):
        """Send atomic message for phase completion"""
        phase_dir = self.run_dir / f"phase-{phase}"
        phase_dir.mkdir(exist_ok=True)

        msg_file = phase_dir / "status.json"
        message = {
            "timestamp": datetime.utcnow().isoformat(),
            "phase": phase,
            "status": status,  # "running", "success", "failed", "partial"
            "data": data or {},
        }

        # Atomic write with lock
        tmp_file = msg_file.with_suffix(".tmp")
        with open(tmp_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(message, f, indent=2)
            fcntl.flock(f, fcntl.LOCK_UN)

        # Atomic rename
        os.rename(tmp_file, msg_file)
        print(f"✓ Phase {phase} message: {status}")

    def get_phase_message(self, phase: int) -> dict:
        """Read phase message safely"""
        msg_file = self.run_dir / f"phase-{phase}" / "status.json"

        if not msg_file.exists():
            return None

        with open(msg_file) as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            msg = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)

        return msg

    def save_artifact(self, phase: int, artifact_name: str, content: str):
        """Save phase artifact (findings, plan, report, etc.)"""
        phase_dir = self.run_dir / f"phase-{phase}"
        phase_dir.mkdir(exist_ok=True)

        artifact_file = phase_dir / f"{artifact_name}.md"
        artifact_file.write_text(content)
        print(f"✓ Artifact saved: phase-{phase}/{artifact_name}.md")

    def get_artifact(self, phase: int, artifact_name: str) -> str:
        """Read phase artifact"""
        artifact_file = self.run_dir / f"phase-{phase}" / f"{artifact_name}.md"

        if artifact_file.exists():
            return artifact_file.read_text()
        return None

    def cleanup_old_runs(self, days: int = 30):
        """Cleanup runs older than N days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        registry = self._read_registry()

        cleaned = 0
        for run_id, info in list(registry.items()):
            if info.get("status") == "complete" and info.get("completed"):
                completed = datetime.fromisoformat(info["completed"])
                if completed < cutoff:
                    run_path = self.tasks_dir / run_id
                    if run_path.exists():
                        shutil.rmtree(run_path)
                    del registry[run_id]
                    cleaned += 1

        if cleaned > 0:
            self._write_registry(registry)
            print(f"✓ Cleaned {cleaned} old runs")

    def _read_registry(self) -> dict:
        """Read global task registry"""
        if self.registry_file.exists():
            with open(self.registry_file) as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                registry = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)
                return registry
        return {}

    def _write_registry(self, registry: dict):
        """Write global task registry atomically"""
        tmp_file = self.registry_file.with_suffix(".tmp")
        with open(tmp_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(registry, f, indent=2)
            fcntl.flock(f, fcntl.LOCK_UN)

        os.rename(tmp_file, self.registry_file)


# Example usage
if __name__ == "__main__":
    # Create isolated worker for this run
    worker = WorkerIsolation()

    print(f"Run ID: {worker.run_id}")
    print(f"Run directory: {worker.run_dir}")
    print()

    # Register run
    worker.register_run("OPSOMN002-XXX", phases=[1, 2, 3, 4, 5])

    # Simulate phase execution
    for phase in [1, 2, 3]:
        print(f"\n--- Phase {phase} ---")
        worker.send_phase_message(phase, "running")
        time.sleep(0.1)

        # Save artifact
        artifact = f"# Phase {phase} Results\n\nData here."
        worker.save_artifact(phase, f"output", artifact)

        worker.send_phase_message(phase, "success", {"duration": "45s"})

    # Release and cleanup
    worker.release_run()
    print(f"\n✅ Worker {worker.run_id} complete")
