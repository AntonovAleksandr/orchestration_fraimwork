#!/usr/bin/env python3
"""
Worker-Initiated Messaging System for Orchestration

Асинхронное взаимодействие между Worker'ом и Coordinator'ом.

Использование:
  from worker_messaging import send_phase_complete

  send_phase_complete(
    task_key="OPSOMN002-XXX",
    phase=3,
    status="success",
    data={"branch": "feat/assortment", "tests_passed": True}
  )
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class PhaseMessage:
    """Сообщение от Worker'а к Coordinator'у"""
    task_key: str
    phase: int
    status: str  # "success", "partial", "blocked"
    timestamp: str
    data: Dict[str, Any]
    worker_id: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class WorkerMessaging:
    """Система обмена сообщениями между worker'ами и coordinator'ом"""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.tasks_dir = self.workspace_root / ".tasks"
        self.tasks_dir.mkdir(exist_ok=True)

    def send_phase_complete(
        self,
        task_key: str,
        phase: int,
        status: str,
        data: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None
    ) -> str:
        """
        Worker отправляет сообщение что phase завершена.

        Args:
            task_key: OPSOMN002-XXX
            phase: 1-6 (или 3.5 для data-driven)
            status: "success", "partial", "blocked"
            data: дополнительные данные (branch, commit, etc)
            worker_id: ID worker'а (опционально)

        Returns:
            message_id (для отслеживания)

        Example:
            send_phase_complete(
                task_key="OPSOMN002-289",
                phase=3,
                status="success",
                data={"branch": "feat/assortment", "commit": "abc123"}
            )
        """
        data = data or {}

        message = PhaseMessage(
            task_key=task_key,
            phase=phase,
            status=status,
            timestamp=datetime.now().isoformat(),
            data=data,
            worker_id=worker_id
        )

        # Создать директорию для задачи если её нет
        task_dir = self.tasks_dir / task_key
        task_dir.mkdir(exist_ok=True)

        # Сохранить сообщение
        message_file = task_dir / f"phase-{phase}.msg"
        with open(message_file, 'w') as f:
            f.write(message.to_json())

        # Создать message_id на основе hash
        message_id = hashlib.md5(
            f"{task_key}-{phase}-{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8]

        # Логировать
        print(f"✅ Phase message sent: {task_key} Phase {phase} = {status}")
        print(f"   Message ID: {message_id}")
        print(f"   File: {message_file}")

        return message_id

    def read_phase_message(self, task_key: str, phase: int) -> Optional[PhaseMessage]:
        """
        Coordinator читает сообщение от worker'а о завершении фазы.
        """
        message_file = self.tasks_dir / task_key / f"phase-{phase}.msg"

        if not message_file.exists():
            return None

        with open(message_file, 'r') as f:
            data = json.load(f)

        return PhaseMessage(**data)

    def poll_for_messages(self, task_key: str) -> Dict[int, PhaseMessage]:
        """
        Coordinator проверяет все сообщения от worker'а для задачи.
        """
        messages = {}
        task_dir = self.tasks_dir / task_key

        if not task_dir.exists():
            return messages

        # Найти все файлы *.msg
        for msg_file in task_dir.glob("phase-*.msg"):
            # Извлечь номер фазы из имени
            phase = int(msg_file.stem.split('-')[1])

            with open(msg_file, 'r') as f:
                data = json.load(f)

            messages[phase] = PhaseMessage(**data)

        return messages

    def wait_for_phase(
        self,
        task_key: str,
        phase: int,
        timeout_seconds: int = 3600
    ) -> PhaseMessage:
        """
        Coordinator ждёт сообщение от worker'а о завершении фазы.
        Может быть асинхронным (polling) или синхронным (wait).
        """
        import time

        start_time = time.time()
        poll_interval = 5  # проверяй каждые 5 секунд

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout_seconds:
                raise TimeoutError(
                    f"Phase {phase} of {task_key} not completed within "
                    f"{timeout_seconds} seconds"
                )

            message = self.read_phase_message(task_key, phase)

            if message is not None:
                print(f"✅ Received message: {task_key} Phase {phase} = {message.status}")
                return message

            # Не блокировать - sleep и retry
            time.sleep(poll_interval)

    def decide_next_phase(
        self,
        task_key: str,
        current_phase: int
    ) -> int:
        """
        Coordinator решает какую фазу запустить дальше.

        Returns:
            next_phase: номер следующей фазы (или None если конец)
        """
        # Прочитать сообщение от worker'а о текущей фазе
        message = self.read_phase_message(task_key, current_phase)

        if message is None:
            print(f"⚠️  No message received for phase {current_phase}")
            return None

        print(f"📊 Phase {current_phase} status: {message.status}")

        if message.status == "success":
            # Все OK, переходить дальше

            if current_phase == 3:
                # Special case: запустить Phase 3.5 и 4 ПАРАЛЛЕЛЬНО!
                return "parallel_3_5_and_4"

            elif current_phase == 3.5:
                # Data-driven завершена, но не переходить сразу
                # Ждём пока Phase 4 тоже завершится
                return None  # Coordinator сам решит

            elif current_phase == 4:
                # Testing завершена, переходить к verification
                return 5

            else:
                # Стандартный случай: next = current + 1
                return current_phase + 1

        elif message.status == "partial":
            # Worker говорит что есть issues но они не блокирующие
            print(f"⚠️  Phase {current_phase}: partial completion")
            print(f"   Data: {message.data}")
            # Можно попробовать следующую фазу
            return current_phase + 1

        else:  # blocked
            # Критическая ошибка, задача заблокирована
            print(f"🚨 Phase {current_phase}: BLOCKED")
            print(f"   Reason: {message.data.get('reason', 'unknown')}")
            return None


# Exported functions for worker'ов

_messaging = WorkerMessaging()


def send_phase_complete(
    task_key: str,
    phase: int,
    status: str,
    data: Optional[Dict[str, Any]] = None,
    worker_id: Optional[str] = None
) -> str:
    """
    Worker: отправить сообщение координатору что фаза завершена.

    Example:
        send_phase_complete(
            task_key="OPSOMN002-289",
            phase=3,
            status="success",
            data={"branch": "feat/assortment"}
        )
    """
    return _messaging.send_phase_complete(task_key, phase, status, data, worker_id)


def phase_success(
    task_key: str,
    phase: int,
    branch: str = "",
    commit: str = "",
    notes: str = ""
) -> str:
    """
    Convenience function: отправить успешное завершение фазы.
    """
    data = {
        "branch": branch,
        "commit": commit,
        "notes": notes,
        "completed_at": datetime.now().isoformat()
    }
    return send_phase_complete(
        task_key=task_key,
        phase=phase,
        status="success",
        data=data
    )


def phase_partial(
    task_key: str,
    phase: int,
    reason: str,
    needs_review: bool = True
) -> str:
    """
    Convenience function: фаза выполнена частично (есть issues).
    """
    data = {
        "reason": reason,
        "needs_review": needs_review,
        "completed_at": datetime.now().isoformat()
    }
    return send_phase_complete(
        task_key=task_key,
        phase=phase,
        status="partial",
        data=data
    )


def phase_blocked(
    task_key: str,
    phase: int,
    reason: str,
    escalate_to: str = "human"
) -> str:
    """
    Convenience function: фаза заблокирована.
    """
    data = {
        "reason": reason,
        "escalate_to": escalate_to,
        "blocked_at": datetime.now().isoformat()
    }
    return send_phase_complete(
        task_key=task_key,
        phase=phase,
        status="blocked",
        data=data
    )


if __name__ == "__main__":
    # Демонстрация
    print("Worker-Messaging System Demo\n")

    # Simulate Phase 3 complete
    print("1. Worker завершил Phase 3 (IMPLEMENTATION)")
    msg_id = phase_success(
        task_key="OPSOMN002-999",
        phase=3,
        branch="feat/demo-feature",
        commit="abc123def456"
    )
    print(f"   Message ID: {msg_id}\n")

    # Simulate coordinator polling
    print("2. Coordinator проверяет сообщения")
    messaging = WorkerMessaging()
    messages = messaging.poll_for_messages("OPSOMN002-999")
    for phase, msg in messages.items():
        print(f"   Phase {phase}: {msg.status} at {msg.timestamp}")

    # Simulate coordinator deciding next phase
    print("\n3. Coordinator решает что делать дальше")
    next_phase = messaging.decide_next_phase("OPSOMN002-999", 3)
    print(f"   Next phase: {next_phase}")

    print("\n✅ Demo complete!")
