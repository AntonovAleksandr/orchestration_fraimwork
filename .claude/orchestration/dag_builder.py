#!/usr/bin/env python3
"""Phase 3.3 Week 3: DAG Builder - Orchestration Graph Visualization

Builds directed acyclic graph for:
- Phase execution order
- Worker dependencies
- Timeline visualization
- Real-time status tracking
"""

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Node execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class EdgeType(Enum):
    """Dependency edge type"""
    PHASE_DEPENDENCY = "phase_dependency"      # Phase depends on phase
    WORKER_DEPENDENCY = "worker_dependency"    # Worker depends on worker
    TEMPORAL = "temporal"                      # Sequence in time


@dataclass
class Node:
    """DAG node (phase or worker)"""
    id: str
    type: str  # "phase" or "worker"
    name: str
    status: NodeStatus = NodeStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: int = 0
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "metadata": self.metadata
        }

    def update_status(self, status: NodeStatus, timestamp: str = None) -> None:
        """Update node status with timing"""
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat() + "Z"

        if status == NodeStatus.RUNNING and not self.started_at:
            self.started_at = timestamp
        elif status in [NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.TIMEOUT]:
            self.completed_at = timestamp
            if self.started_at:
                start = datetime.fromisoformat(self.started_at.replace('Z', '+00:00'))
                end = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                self.duration_ms = int((end - start).total_seconds() * 1000)

        self.status = status


@dataclass
class Edge:
    """DAG edge (dependency)"""
    from_node: str
    to_node: str
    edge_type: EdgeType
    weight: int = 1  # Importance/criticality
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "type": self.edge_type.value,
            "weight": self.weight,
            "metadata": self.metadata
        }


class DAGBuilder:
    """Builds and manages orchestration DAG"""

    def __init__(self, run_id: str):
        """Initialize DAG for a run"""
        self.run_id = run_id
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._lock = __import__("threading").Lock()

    def add_phase(self, phase_num: int, name: str = None) -> Node:
        """Add phase node to DAG"""
        node_id = f"phase-{phase_num}"
        node_name = name or f"Phase {phase_num}"

        node = Node(
            id=node_id,
            type="phase",
            name=node_name,
            metadata={"phase_number": phase_num}
        )

        with self._lock:
            self.nodes[node_id] = node

        logger.info(f"➕ Added phase node: {node_id}")
        return node

    def add_worker(
        self,
        phase_num: int,
        worker_num: int,
        name: str = None
    ) -> Node:
        """Add worker node to DAG"""
        node_id = f"phase-{phase_num}-worker-{worker_num}"
        node_name = name or f"Phase {phase_num} Worker {worker_num}"

        node = Node(
            id=node_id,
            type="worker",
            name=node_name,
            metadata={
                "phase_number": phase_num,
                "worker_number": worker_num
            }
        )

        with self._lock:
            self.nodes[node_id] = node

        logger.info(f"➕ Added worker node: {node_id}")
        return node

    def add_phase_dependency(
        self,
        from_phase: int,
        to_phase: int,
        critical: bool = True
    ) -> Edge:
        """Add phase-to-phase dependency"""
        from_id = f"phase-{from_phase}"
        to_id = f"phase-{to_phase}"

        edge = Edge(
            from_node=from_id,
            to_node=to_id,
            edge_type=EdgeType.PHASE_DEPENDENCY,
            weight=2 if critical else 1
        )

        with self._lock:
            self.edges.append(edge)

        logger.info(f"🔗 Phase {from_phase} → Phase {to_phase}")
        return edge

    def add_worker_dependency(self, from_worker_id: str, to_worker_id: str) -> Edge:
        """Add worker-to-worker dependency"""
        edge = Edge(
            from_node=from_worker_id,
            to_node=to_worker_id,
            edge_type=EdgeType.WORKER_DEPENDENCY
        )

        with self._lock:
            self.edges.append(edge)

        return edge

    def add_temporal_edge(self, from_id: str, to_id: str) -> Edge:
        """Add temporal sequence edge (used for visualization)"""
        edge = Edge(
            from_node=from_id,
            to_node=to_id,
            edge_type=EdgeType.TEMPORAL,
            weight=0  # Not critical, just for ordering
        )

        with self._lock:
            self.edges.append(edge)

        return edge

    def update_node_status(
        self,
        node_id: str,
        status: NodeStatus,
        timestamp: str = None,
        error: str = None
    ) -> None:
        """Update node status"""
        if node_id not in self.nodes:
            logger.warning(f"Node not found: {node_id}")
            return

        with self._lock:
            node = self.nodes[node_id]
            node.update_status(status, timestamp)
            if error:
                node.error = error

        logger.info(f"🔄 {node_id}: {status.value}")

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get node by ID"""
        return self.nodes.get(node_id)

    def get_all_nodes(self) -> List[Node]:
        """Get all nodes"""
        return list(self.nodes.values())

    def get_all_edges(self) -> List[Edge]:
        """Get all edges"""
        return self.edges

    def get_phase_nodes(self, phase_num: int) -> List[Node]:
        """Get all nodes for a phase (phase + workers)"""
        phase_id = f"phase-{phase_num}"
        result = []

        if phase_id in self.nodes:
            result.append(self.nodes[phase_id])

        # Add workers in this phase
        prefix = f"phase-{phase_num}-worker-"
        for node_id, node in self.nodes.items():
            if node_id.startswith(prefix):
                result.append(node)

        return result

    def get_critical_path(self) -> List[str]:
        """Get critical path (longest dependency chain)"""
        # Simplified: find nodes with no incoming edges (start)
        # and trace to completion

        start_nodes = []
        incoming = set()

        for edge in self.edges:
            if edge.edge_type == EdgeType.PHASE_DEPENDENCY:
                incoming.add(edge.to_node)

        for node_id in self.nodes:
            if node_id not in incoming:
                start_nodes.append(node_id)

        # DFS to find longest path
        def dfs(node_id: str, path: List[str]) -> List[str]:
            path = path + [node_id]

            # Find next nodes
            next_nodes = [
                e.to_node for e in self.edges
                if e.from_node == node_id
            ]

            if not next_nodes:
                return path

            longest = path
            for next_id in next_nodes:
                candidate = dfs(next_id, path)
                if len(candidate) > len(longest):
                    longest = candidate

            return longest

        critical_path = []
        for start_id in start_nodes:
            path = dfs(start_id, [])
            if len(path) > len(critical_path):
                critical_path = path

        return critical_path

    def get_node_predecessors(self, node_id: str) -> List[str]:
        """Get immediate predecessors"""
        return [e.from_node for e in self.edges if e.to_node == node_id]

    def get_node_successors(self, node_id: str) -> List[str]:
        """Get immediate successors"""
        return [e.to_node for e in self.edges if e.from_node == node_id]

    def to_dict(self) -> Dict:
        """Export DAG as dictionary"""
        return {
            "run_id": self.run_id,
            "nodes": [n.to_dict() for n in self.get_all_nodes()],
            "edges": [e.to_dict() for e in self.get_all_edges()],
            "critical_path": self.get_critical_path()
        }

    def to_json(self) -> str:
        """Export DAG as JSON"""
        return json.dumps(self.to_dict(), indent=2)

    def to_mermaid(self) -> str:
        """Export DAG as Mermaid diagram"""
        lines = ["graph TD"]

        # Add nodes with status colors
        status_colors = {
            NodeStatus.PENDING: "pending",
            NodeStatus.RUNNING: "running",
            NodeStatus.COMPLETED: "done",
            NodeStatus.FAILED: "crit",
            NodeStatus.TIMEOUT: "crit",
            NodeStatus.SKIPPED: "skipped"
        }

        for node in self.get_all_nodes():
            color_class = status_colors.get(node.status, "pending")
            label = f"{node.name}"
            if node.duration_ms > 0:
                label += f" ({node.duration_ms}ms)"
            lines.append(f"  {node.id}[\"{label}\"] ::::{color_class}")

        # Add edges
        for edge in self.edges:
            if edge.edge_type == EdgeType.PHASE_DEPENDENCY:
                lines.append(f"  {edge.from_node} --> {edge.to_node}")

        # Style definitions
        lines.append("")
        lines.append("  classDef running fill:#FF9800,stroke:#333,color:#fff")
        lines.append("  classDef done fill:#4CAF50,stroke:#333,color:#fff")
        lines.append("  classDef crit fill:#F44336,stroke:#333,color:#fff")
        lines.append("  classDef pending fill:#9E9E9E,stroke:#333,color:#fff")
        lines.append("  classDef skipped fill:#607D8B,stroke:#333,color:#fff")

        return "\n".join(lines)

    def get_execution_stats(self) -> Dict:
        """Get execution statistics"""
        nodes = self.get_all_nodes()

        total = len(nodes)
        completed = sum(1 for n in nodes if n.status == NodeStatus.COMPLETED)
        failed = sum(1 for n in nodes if n.status == NodeStatus.FAILED)
        running = sum(1 for n in nodes if n.status == NodeStatus.RUNNING)
        pending = sum(1 for n in nodes if n.status == NodeStatus.PENDING)

        total_duration = sum(n.duration_ms for n in nodes if n.status == NodeStatus.COMPLETED)
        avg_duration = total_duration / completed if completed > 0 else 0

        return {
            "total_nodes": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
            "success_rate": (completed / total * 100) if total > 0 else 0,
            "total_duration_ms": total_duration,
            "avg_duration_ms": avg_duration,
            "critical_path_length": len(self.get_critical_path())
        }


# Example usage
if __name__ == "__main__":
    print("\n" + "="*60)
    print("DAG BUILDER DEMO")
    print("="*60 + "\n")

    dag = DAGBuilder("demo-run-phase33")

    # Build DAG
    print("Building DAG...")
    dag.add_phase(1, "Data Preparation")
    dag.add_phase(2, "Processing")
    dag.add_phase(3, "Validation")

    # Add workers
    for i in range(2):
        dag.add_worker(1, i+1, f"Prepare Data {i+1}")
        dag.add_worker(2, i+1, f"Process {i+1}")

    # Add dependencies
    dag.add_phase_dependency(1, 2)
    dag.add_phase_dependency(2, 3)

    print("\n✅ DAG built\n")

    # Simulate execution
    print("Simulating execution...")
    dag.update_node_status("phase-1", NodeStatus.RUNNING)
    dag.update_node_status("phase-1-worker-1", NodeStatus.RUNNING)

    import time
    time.sleep(0.5)

    dag.update_node_status("phase-1-worker-1", NodeStatus.COMPLETED)
    dag.update_node_status("phase-1-worker-2", NodeStatus.RUNNING)

    time.sleep(0.3)

    dag.update_node_status("phase-1-worker-2", NodeStatus.COMPLETED)
    dag.update_node_status("phase-1", NodeStatus.COMPLETED)

    print("\nDAG Statistics:")
    stats = dag.get_execution_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.1f}")
        else:
            print(f"  {key}: {value}")

    # Export
    print("\n📊 Mermaid Diagram:")
    print(dag.to_mermaid())

    print("\n✨ DAG Builder working!")
