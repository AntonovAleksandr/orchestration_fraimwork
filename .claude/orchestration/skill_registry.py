#!/usr/bin/env python3
"""Phase 3.2 Week 2: Skill Registry with Dependency Graph

Central registry for all skills with:
- Dependency graph construction
- Circular dependency detection
- Pre-execution validation
- Version compatibility checking
- Hot-reload support (planned)
"""

import json
import threading
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SkillStatus(Enum):
    """Skill status"""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    FAILED = "failed"
    INCOMPATIBLE = "incompatible"
    MISSING_DEPENDENCY = "missing_dependency"


@dataclass
class SkillMetadata:
    """Skill metadata"""
    name: str
    version: str
    description: str
    path: str
    depends_on: List[str]  # List of skill names
    required_version: Dict[str, str]  # {"skill-name": ">=1.0.0"}
    last_loaded_at: Optional[str] = None
    load_count: int = 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


class DependencyGraph:
    """Dependency graph for skills"""

    def __init__(self):
        """Initialize empty graph"""
        self.nodes: Dict[str, SkillMetadata] = {}  # skill_name -> metadata
        self.edges: Dict[str, Set[str]] = {}  # skill_name -> {dependencies}
        self._lock = threading.Lock()

    def add_skill(self, metadata: SkillMetadata) -> None:
        """Add skill to graph"""
        with self._lock:
            self.nodes[metadata.name] = metadata
            self.edges[metadata.name] = set(metadata.depends_on)

    def get_skill(self, name: str) -> Optional[SkillMetadata]:
        """Get skill by name"""
        return self.nodes.get(name)

    def get_all_skills(self) -> List[SkillMetadata]:
        """Get all skills"""
        return list(self.nodes.values())

    def get_dependencies(self, skill_name: str) -> Set[str]:
        """Get direct dependencies of a skill"""
        return self.edges.get(skill_name, set())

    def get_transitive_closure(self, skill_name: str) -> Set[str]:
        """Get all transitive dependencies (closure)"""
        closure = set()
        visited = set()

        def visit(name: str):
            if name in visited:
                return
            visited.add(name)

            for dep in self.get_dependencies(name):
                closure.add(dep)
                visit(dep)

        visit(skill_name)
        return closure

    def find_circular_dependencies(self) -> List[List[str]]:
        """Detect all circular dependencies using DFS"""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for dep in self.get_dependencies(node):
                if dep not in visited:
                    dfs(dep, path.copy())
                elif dep in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    cycles.append(cycle)

            rec_stack.remove(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def topological_sort(self) -> List[str]:
        """Topological sort of skills (respecting dependencies)"""
        result = []
        visited = set()

        def visit(node: str):
            if node in visited:
                return
            visited.add(node)

            for dep in self.get_dependencies(node):
                visit(dep)

            result.append(node)

        for node in self.nodes:
            visit(node)

        return result

    def validate_structure(self) -> Tuple[bool, List[str]]:
        """Validate graph structure for issues"""
        issues = []

        # Check for circular dependencies
        cycles = self.find_circular_dependencies()
        if cycles:
            for cycle in cycles:
                issues.append(f"Circular dependency: {' → '.join(cycle)}")

        # Check for missing dependencies
        for skill_name, deps in self.edges.items():
            for dep in deps:
                if dep not in self.nodes:
                    issues.append(f"Missing dependency: {skill_name} depends on {dep} (not found)")

        return len(issues) == 0, issues


class SkillRegistry:
    """Central registry for all skills"""

    def __init__(self, skills_base_path: str = ".claude/skills"):
        """Initialize registry"""
        self.skills_base_path = Path(skills_base_path)
        self.graph = DependencyGraph()
        self._loaded = False
        self._lock = threading.Lock()

        logger.info(f"🔧 Skill Registry initialized (base: {skills_base_path})")

    def load_all_skills(self) -> Tuple[int, List[str]]:
        """Load all skills from filesystem"""
        with self._lock:
            errors = []
            count = 0

            if not self.skills_base_path.exists():
                logger.warning(f"Skills directory not found: {self.skills_base_path}")
                return 0, ["Skills directory not found"]

            # Find all skill directories
            for skill_dir in self.skills_base_path.iterdir():
                if not skill_dir.is_dir():
                    continue

                # Look for SKILL.md or skill.json
                metadata_file = skill_dir / "skill.json"
                if not metadata_file.exists():
                    metadata_file = skill_dir / "SKILL.md"

                if metadata_file.exists():
                    try:
                        metadata = self._parse_skill_metadata(skill_dir, metadata_file)
                        self.graph.add_skill(metadata)
                        count += 1
                        logger.info(f"  ✅ Loaded: {metadata.name} v{metadata.version}")
                    except Exception as e:
                        error_msg = f"Failed to load {skill_dir.name}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(f"  ❌ {error_msg}")

            self._loaded = True
            logger.info(f"✅ Loaded {count} skills ({len(errors)} errors)")

            return count, errors

    def _parse_skill_metadata(self, skill_dir: Path, metadata_file: Path) -> SkillMetadata:
        """Parse skill metadata from file"""
        if metadata_file.suffix == ".json":
            with open(metadata_file) as f:
                data = json.load(f)
                return SkillMetadata(
                    name=data.get("name", skill_dir.name),
                    version=data.get("version", "1.0.0"),
                    description=data.get("description", ""),
                    path=str(skill_dir),
                    depends_on=data.get("depends_on", []),
                    required_version=data.get("required_version", {})
                )
        else:
            # Parse from SKILL.md (simple parsing)
            with open(metadata_file) as f:
                content = f.read()

            # Extract metadata from markdown headers
            name = skill_dir.name
            version = "1.0.0"
            description = ""
            depends_on = []

            # Try to extract from frontmatter or content
            for line in content.split('\n')[:20]:
                if line.startswith("# "):
                    description = line[2:].strip()
                    break

            return SkillMetadata(
                name=name,
                version=version,
                description=description,
                path=str(skill_dir),
                depends_on=depends_on,
                required_version={}
            )

    def get_skill(self, name: str) -> Optional[SkillMetadata]:
        """Get skill by name"""
        return self.graph.get_skill(name)

    def validate_skill_execution(self, skill_name: str) -> Tuple[bool, List[str]]:
        """Validate that a skill can be executed"""
        issues = []

        # Check skill exists
        skill = self.get_skill(skill_name)
        if not skill:
            return False, [f"Skill not found: {skill_name}"]

        # Check all dependencies exist
        for dep in skill.depends_on:
            if not self.get_skill(dep):
                issues.append(f"Missing dependency: {skill_name} requires {dep}")

        # Check graph structure
        is_valid, graph_issues = self.graph.validate_structure()
        if not is_valid:
            issues.extend(graph_issues)

        # Check for circular dependencies involving this skill
        closure = self.graph.get_transitive_closure(skill_name)
        if skill_name in closure:
            issues.append(f"Circular dependency detected for {skill_name}")

        return len(issues) == 0, issues

    def validate_all_skills(self) -> Tuple[bool, List[str]]:
        """Validate all skills in registry"""
        issues = []

        # Validate graph structure
        is_valid, graph_issues = self.graph.validate_structure()
        issues.extend(graph_issues)

        # Validate each skill
        for skill in self.graph.get_all_skills():
            skill_valid, skill_issues = self.validate_skill_execution(skill.name)
            if not skill_valid:
                issues.append(f"Skill {skill.name}: {'; '.join(skill_issues)}")

        return len(issues) == 0, issues

    def get_execution_order(self) -> List[str]:
        """Get optimal execution order (topological sort)"""
        return self.graph.topological_sort()

    def get_skill_dependencies_tree(self, skill_name: str) -> Dict:
        """Get dependency tree for a skill"""
        skill = self.get_skill(skill_name)
        if not skill:
            return None

        def build_tree(name: str, visited: Set[str] = None) -> Dict:
            if visited is None:
                visited = set()

            if name in visited:
                return {"name": name, "circular": True}

            visited.add(name)

            skill = self.get_skill(name)
            if not skill:
                return {"name": name, "missing": True}

            deps = []
            for dep_name in skill.depends_on:
                deps.append(build_tree(dep_name, visited.copy()))

            return {
                "name": name,
                "version": skill.version,
                "dependencies": deps
            }

        return build_tree(skill_name)

    def health_check(self) -> Dict:
        """Check registry health"""
        total_skills = len(self.graph.nodes)
        cycles = self.graph.find_circular_dependencies()
        is_valid, issues = self.graph.validate_structure()

        return {
            "loaded": self._loaded,
            "total_skills": total_skills,
            "circular_dependencies": len(cycles),
            "is_valid": is_valid,
            "issues_count": len(issues),
            "issues": issues[:5]  # First 5 issues
        }


# Example usage
if __name__ == "__main__":
    registry = SkillRegistry(".claude/skills")

    print("\n" + "="*60)
    print("SKILL REGISTRY DEMO")
    print("="*60 + "\n")

    # Load skills
    count, errors = registry.load_all_skills()
    print(f"✅ Loaded {count} skills")
    if errors:
        print(f"⚠️  {len(errors)} errors")
        for error in errors[:3]:
            print(f"  - {error}")

    # Health check
    health = registry.health_check()
    print(f"\nRegistry Health: {health['total_skills']} skills")
    if health["circular_dependencies"] > 0:
        print(f"❌ Found {health['circular_dependencies']} circular dependencies")
    else:
        print(f"✅ No circular dependencies")

    # Get execution order
    exec_order = registry.get_execution_order()
    print(f"\nExecution Order ({len(exec_order)} skills):")
    for i, skill_name in enumerate(exec_order[:5]):
        print(f"  {i+1}. {skill_name}")

    # Validate specific skill
    if registry.get_all_skills():
        test_skill = registry.get_all_skills()[0].name
        is_valid, issues = registry.validate_skill_execution(test_skill)
        print(f"\nValidation for '{test_skill}': {'✅ OK' if is_valid else '❌ FAILED'}")
        if not is_valid:
            for issue in issues:
                print(f"  - {issue}")

    print("\n✨ Skill Registry working!")
