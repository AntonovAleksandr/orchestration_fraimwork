#!/usr/bin/env python3
"""Phase 3.2 Week 2: Tests for Skill Registry and Validator

14 comprehensive tests covering:
- Skill loading and metadata parsing
- Dependency graph construction
- Circular dependency detection
- Pre-execution validation
- Version compatibility
- Integration with Phase 3.1 event log
"""

import unittest
import tempfile
import json
from pathlib import Path

from skill_registry import SkillRegistry, SkillMetadata, DependencyGraph
from skill_validator import SkillValidator
from state_store import StateStore
from event_sourcing import EventLog


class TestDependencyGraph(unittest.TestCase):
    """Dependency graph tests"""

    def setUp(self):
        """Setup for each test"""
        self.graph = DependencyGraph()

    def test_add_skill_to_graph(self):
        """Test 1: Add skill to graph"""
        skill = SkillMetadata(
            name="skill-a",
            version="1.0.0",
            description="Test skill",
            path="/path/to/skill-a",
            depends_on=[],
            required_version={}
        )

        self.graph.add_skill(skill)

        self.assertIn("skill-a", self.graph.nodes)
        self.assertEqual(self.graph.get_skill("skill-a").name, "skill-a")

    def test_dependency_edges(self):
        """Test 2: Dependency edges are tracked"""
        skill_a = SkillMetadata(
            name="skill-a",
            version="1.0.0",
            description="",
            path="",
            depends_on=["skill-b"],
            required_version={}
        )
        skill_b = SkillMetadata(
            name="skill-b",
            version="1.0.0",
            description="",
            path="",
            depends_on=[],
            required_version={}
        )

        self.graph.add_skill(skill_a)
        self.graph.add_skill(skill_b)

        deps = self.graph.get_dependencies("skill-a")
        self.assertIn("skill-b", deps)

    def test_transitive_closure(self):
        """Test 3: Transitive closure calculates all dependencies"""
        # A -> B -> C
        skills = [
            ("skill-a", ["skill-b"]),
            ("skill-b", ["skill-c"]),
            ("skill-c", [])
        ]

        for name, deps in skills:
            skill = SkillMetadata(
                name=name,
                version="1.0.0",
                description="",
                path="",
                depends_on=deps,
                required_version={}
            )
            self.graph.add_skill(skill)

        closure = self.graph.get_transitive_closure("skill-a")

        self.assertIn("skill-b", closure)
        self.assertIn("skill-c", closure)
        self.assertEqual(len(closure), 2)

    def test_circular_dependency_detection(self):
        """Test 4: Detect simple circular dependency (A -> B -> A)"""
        # A -> B -> A
        skill_a = SkillMetadata(
            name="skill-a",
            version="1.0.0",
            description="",
            path="",
            depends_on=["skill-b"],
            required_version={}
        )
        skill_b = SkillMetadata(
            name="skill-b",
            version="1.0.0",
            description="",
            path="",
            depends_on=["skill-a"],
            required_version={}
        )

        self.graph.add_skill(skill_a)
        self.graph.add_skill(skill_b)

        cycles = self.graph.find_circular_dependencies()

        self.assertTrue(len(cycles) > 0)

    def test_complex_circular_dependency(self):
        """Test 5: Detect complex circular dependency (A -> B -> C -> A)"""
        # A -> B -> C -> A
        skills = [
            ("skill-a", ["skill-b"]),
            ("skill-b", ["skill-c"]),
            ("skill-c", ["skill-a"])
        ]

        for name, deps in skills:
            skill = SkillMetadata(
                name=name,
                version="1.0.0",
                description="",
                path="",
                depends_on=deps,
                required_version={}
            )
            self.graph.add_skill(skill)

        cycles = self.graph.find_circular_dependencies()

        self.assertTrue(len(cycles) > 0)

    def test_topological_sort(self):
        """Test 6: Topological sort respects dependencies"""
        # A -> B -> C (no cycles)
        skills = [
            ("skill-a", ["skill-b"]),
            ("skill-b", ["skill-c"]),
            ("skill-c", [])
        ]

        for name, deps in skills:
            skill = SkillMetadata(
                name=name,
                version="1.0.0",
                description="",
                path="",
                depends_on=deps,
                required_version={}
            )
            self.graph.add_skill(skill)

        order = self.graph.topological_sort()

        # C should come before B, B before A
        c_idx = order.index("skill-c")
        b_idx = order.index("skill-b")
        a_idx = order.index("skill-a")

        self.assertTrue(c_idx < b_idx < a_idx)

    def test_graph_validation_success(self):
        """Test 7: Validate graph with no issues"""
        skill = SkillMetadata(
            name="skill-a",
            version="1.0.0",
            description="",
            path="",
            depends_on=[],
            required_version={}
        )

        self.graph.add_skill(skill)

        is_valid, issues = self.graph.validate_structure()

        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)

    def test_graph_validation_missing_dependency(self):
        """Test 8: Detect missing dependency"""
        skill = SkillMetadata(
            name="skill-a",
            version="1.0.0",
            description="",
            path="",
            depends_on=["skill-missing"],
            required_version={}
        )

        self.graph.add_skill(skill)

        is_valid, issues = self.graph.validate_structure()

        self.assertFalse(is_valid)
        self.assertTrue(any("Missing dependency" in issue for issue in issues))


class TestSkillRegistry(unittest.TestCase):
    """Skill registry tests"""

    def setUp(self):
        """Setup for each test"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry = SkillRegistry(self.temp_dir.name)

    def tearDown(self):
        """Cleanup"""
        self.temp_dir.cleanup()

    def test_registry_initialization(self):
        """Test 9: Initialize empty registry"""
        self.assertFalse(self.registry._loaded)
        self.assertEqual(len(self.registry.graph.nodes), 0)

    def test_load_skills_from_json(self):
        """Test 10: Load skill from skill.json"""
        # Create a test skill
        skill_dir = Path(self.temp_dir.name) / "test-skill"
        skill_dir.mkdir()

        skill_json = skill_dir / "skill.json"
        with open(skill_json, "w") as f:
            json.dump({
                "name": "test-skill",
                "version": "1.0.0",
                "description": "Test skill",
                "depends_on": [],
                "required_version": {}
            }, f)

        # Load
        count, errors = self.registry.load_all_skills()

        self.assertEqual(count, 1)
        self.assertEqual(len(errors), 0)
        self.assertIsNotNone(self.registry.get_skill("test-skill"))

    def test_registry_health_check(self):
        """Test 11: Registry health check"""
        health = self.registry.health_check()

        self.assertIn("loaded", health)
        self.assertIn("total_skills", health)
        self.assertIn("circular_dependencies", health)
        self.assertIn("is_valid", health)

    def test_skill_execution_validation(self):
        """Test 12: Validate skill can execute"""
        # Create skill without dependencies
        skill_dir = Path(self.temp_dir.name) / "simple-skill"
        skill_dir.mkdir()

        skill_json = skill_dir / "skill.json"
        with open(skill_json, "w") as f:
            json.dump({
                "name": "simple-skill",
                "version": "1.0.0",
                "description": "Simple skill",
                "depends_on": [],
                "required_version": {}
            }, f)

        self.registry.load_all_skills()

        is_valid, issues = self.registry.validate_skill_execution("simple-skill")

        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)


class TestSkillValidator(unittest.TestCase):
    """Skill validator tests"""

    def setUp(self):
        """Setup for each test"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry = SkillRegistry(self.temp_dir.name)
        self.store = StateStore(str(Path(self.temp_dir.name) / "test.db"))
        self.event_log = EventLog(self.store)
        self.validator = SkillValidator(self.registry, self.event_log)

    def tearDown(self):
        """Cleanup"""
        self.temp_dir.cleanup()

    def test_pre_execute_validation_empty(self):
        """Test 13: Validate with empty skills list"""
        self.registry.load_all_skills()

        is_valid, errors, details = self.validator.pre_execute_validation(
            run_id="test-run",
            phase=1,
            required_skills=[]
        )

        self.assertTrue(is_valid)

    def test_pre_execute_validation_with_events(self):
        """Test 14: Validation logs events to event log"""
        # Create a test skill
        skill_dir = Path(self.temp_dir.name) / "test-skill"
        skill_dir.mkdir()

        skill_json = skill_dir / "skill.json"
        with open(skill_json, "w") as f:
            json.dump({
                "name": "test-skill",
                "version": "1.0.0",
                "description": "Test",
                "depends_on": [],
                "required_version": {}
            }, f)

        self.registry.load_all_skills()

        run_id = "test-run-events"
        is_valid, errors, details = self.validator.pre_execute_validation(
            run_id=run_id,
            phase=1,
            required_skills=["test-skill"]
        )

        # Check events were logged
        events = self.event_log.get_events(run_id)

        self.assertTrue(len(events) > 0)
        self.assertTrue(is_valid)


# Run tests
if __name__ == "__main__":
    unittest.main(verbosity=2)
