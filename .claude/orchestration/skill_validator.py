#!/usr/bin/env python3
"""Phase 3.2 Week 2: Skill Validator - Pre-Execution Validation

Validates skills before phase execution:
- Dependency resolution
- Circular dependency detection
- Version compatibility
- Resource requirements
- Integrates with Phase 3.1 event log
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

from skill_registry import SkillRegistry, SkillStatus
from event_sourcing import EventLog, EventType
from state_store import StateStore

logger = logging.getLogger(__name__)


class SkillValidator:
    """Validates skills before execution"""

    def __init__(self, registry: SkillRegistry, event_log: EventLog = None):
        """Initialize validator"""
        self.registry = registry
        self.event_log = event_log
        self._validation_cache = {}  # Cache validation results

    def pre_execute_validation(
        self,
        run_id: str,
        phase: int,
        required_skills: List[str]
    ) -> Tuple[bool, List[str], List[Dict]]:
        """
        Comprehensive pre-execution validation

        Args:
            run_id: orchestration run ID
            phase: phase number
            required_skills: list of skills needed for this phase

        Returns:
            (is_valid, errors, skill_details)
        """
        errors = []
        skill_details = []

        # Step 1: Load all skills from registry
        if not self.registry._loaded:
            logger.info(f"Loading skills for phase {phase}...")
            count, load_errors = self.registry.load_all_skills()
            if load_errors:
                errors.extend(load_errors)

            # Log event
            if self.event_log:
                self.event_log.log_event(
                    run_id=run_id,
                    event_type=EventType.SKILL_REGISTRY_LOADED,
                    data={
                        "phase": phase,
                        "skills_loaded": count,
                        "errors": load_errors
                    },
                    phase=phase
                )

        # Step 2: Validate each required skill exists
        for skill_name in required_skills:
            skill = self.registry.get_skill(skill_name)

            if not skill:
                error = f"Skill not found: {skill_name}"
                errors.append(error)

                if self.event_log:
                    self.event_log.log_event(
                        run_id=run_id,
                        event_type=EventType.SKILL_VALIDATION_FAILED,
                        data={"skill": skill_name, "reason": "not_found"},
                        phase=phase
                    )
                continue

            skill_details.append({
                "name": skill_name,
                "version": skill.version,
                "status": "found"
            })

        # Step 3: Validate dependency graph
        is_graph_valid, graph_issues = self.registry.graph.validate_structure()
        if not is_graph_valid:
            errors.extend(graph_issues)

            if self.event_log:
                self.event_log.log_event(
                    run_id=run_id,
                    event_type=EventType.SKILL_VALIDATION_FAILED,
                    data={"reason": "graph_invalid", "issues": graph_issues},
                    phase=phase
                )

        # Step 4: Validate each skill can execute
        for skill_name in required_skills:
            skill_valid, skill_issues = self.registry.validate_skill_execution(skill_name)

            if not skill_valid:
                errors.extend(skill_issues)

                if self.event_log:
                    self.event_log.log_event(
                        run_id=run_id,
                        event_type=EventType.SKILL_VALIDATION_FAILED,
                        data={
                            "skill": skill_name,
                            "issues": skill_issues
                        },
                        phase=phase
                    )

            else:
                # Skill is valid
                if self.event_log:
                    self.event_log.log_event(
                        run_id=run_id,
                        event_type=EventType.SKILL_VALIDATION_PASSED,
                        data={"skill": skill_name},
                        phase=phase
                    )

        # Step 5: Check for circular dependencies
        cycles = self.registry.graph.find_circular_dependencies()
        if cycles:
            for cycle in cycles:
                cycle_str = " → ".join(cycle)
                error = f"Circular dependency: {cycle_str}"
                errors.append(error)

                if self.event_log:
                    self.event_log.log_event(
                        run_id=run_id,
                        event_type=EventType.SKILL_VALIDATION_FAILED,
                        data={"reason": "circular_dependency", "cycle": cycle},
                        phase=phase
                    )

        # Step 6: Log final validation result
        is_valid = len(errors) == 0

        if self.event_log:
            if is_valid:
                self.event_log.log_event(
                    run_id=run_id,
                    event_type=EventType.SKILL_VALIDATION_PASSED,
                    data={
                        "phase": phase,
                        "skills_validated": len(required_skills)
                    },
                    phase=phase
                )
            else:
                self.event_log.log_event(
                    run_id=run_id,
                    event_type=EventType.SKILL_VALIDATION_FAILED,
                    data={
                        "phase": phase,
                        "error_count": len(errors),
                        "errors": errors[:5]  # First 5
                    },
                    phase=phase
                )

        logger.info(
            f"🔍 Phase {phase} validation: {'✅ PASS' if is_valid else '❌ FAIL'} "
            f"({len(required_skills)} skills, {len(errors)} errors)"
        )

        return is_valid, errors, skill_details

    def validate_skill_compatibility(
        self,
        skill_name: str,
        required_version: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate skill version compatibility

        Args:
            skill_name: skill to validate
            required_version: version requirement (e.g., ">=1.0.0", "1.2.x")

        Returns:
            (is_compatible, actual_version)
        """
        skill = self.registry.get_skill(skill_name)

        if not skill:
            return False, None

        # Simple version parsing (not full semver)
        actual_version = skill.version
        if required_version.startswith(">="):
            required = required_version[2:]
            return actual_version >= required, actual_version
        elif required_version.endswith(".x"):
            base = required_version[:-2]
            return actual_version.startswith(base), actual_version
        else:
            return actual_version == required_version, actual_version

    def get_dependency_chain(self, skill_name: str) -> Dict:
        """Get full dependency chain for a skill"""
        return self.registry.get_skill_dependencies_tree(skill_name)

    def suggest_execution_order(self, required_skills: List[str]) -> List[str]:
        """Suggest optimal execution order for skills"""
        # Get topological sort from registry
        all_order = self.registry.get_execution_order()

        # Filter to only required skills, maintaining order
        return [s for s in all_order if s in required_skills]


# Extended EventType for Phase 3.2
class ExtendedEventType:
    """Add Phase 3.2 event types"""
    SKILL_REGISTRY_LOADED = "skill_registry_loaded"
    SKILL_VALIDATION_STARTED = "skill_validation_started"
    SKILL_VALIDATION_PASSED = "skill_validation_passed"
    SKILL_VALIDATION_FAILED = "skill_validation_failed"
    CIRCULAR_DEPENDENCY_DETECTED = "circular_dependency_detected"


# Monkey-patch EventType to include Phase 3.2 events
from enum import Enum as _Enum


def _add_phase32_events():
    """Add Phase 3.2 event types to EventType enum"""
    if not hasattr(EventType, 'SKILL_REGISTRY_LOADED'):
        # Add new attributes to existing enum
        EventType.SKILL_REGISTRY_LOADED = 'skill_registry_loaded'
        EventType.SKILL_VALIDATION_STARTED = 'skill_validation_started'
        EventType.SKILL_VALIDATION_PASSED = 'skill_validation_passed'
        EventType.SKILL_VALIDATION_FAILED = 'skill_validation_failed'
        EventType.CIRCULAR_DEPENDENCY_DETECTED = 'circular_dependency_detected'


# Apply monkey-patch
_add_phase32_events()


# Example usage
if __name__ == "__main__":
    from state_store import StateStore

    print("\n" + "="*60)
    print("SKILL VALIDATOR DEMO")
    print("="*60 + "\n")

    # Initialize components
    registry = SkillRegistry(".claude/skills")
    store = StateStore(".tasks/demo.db")
    event_log = EventLog(store)
    validator = SkillValidator(registry, event_log)

    # Load registry
    count, _ = registry.load_all_skills()
    print(f"✅ Registry loaded: {count} skills\n")

    # Simulate validation for a phase
    run_id = "demo-phase32-001"
    required_skills = ["ensi-backend-engineer", "site-engineer"]

    print(f"Validating phase 1...")
    is_valid, errors, details = validator.pre_execute_validation(
        run_id=run_id,
        phase=1,
        required_skills=required_skills
    )

    print(f"\nValidation Result: {'✅ PASS' if is_valid else '❌ FAIL'}")
    print(f"Skills validated: {len(details)}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for error in errors[:3]:
            print(f"  - {error}")

    print("\n✨ Skill Validator working!")
