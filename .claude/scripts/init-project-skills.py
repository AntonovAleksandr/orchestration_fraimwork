#!/usr/bin/env python3
"""Interactive project skills initialization script

Usage:
  python init-project-skills.py <project-name>
  python init-project-skills.py beauty-marking
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path


class ProjectSkillInitializer:
    """Initialize project-specific skills with guided questionnaire"""

    def __init__(self, project_name):
        self.project_name = project_name
        self.skills_base = Path(".claude/skills/PROJECT")
        self.project_path = self.skills_base / project_name
        self.responses = {}

    def validate_project_name(self):
        """Check if project already exists"""
        if self.project_path.exists():
            print(f"❌ Project already exists: {self.project_path}")
            return False

        # Valid naming: lowercase, hyphens, alphanumeric
        if not all(c.isalnum() or c == '-' for c in self.project_name):
            print(f"❌ Invalid project name. Use lowercase, hyphens, alphanumeric only")
            return False

        return True

    def create_structure(self):
        """Create directory structure"""
        self.project_path.mkdir(parents=True, exist_ok=True)
        (self.project_path / "examples").mkdir(exist_ok=True)
        print(f"✅ Created: {self.project_path}")

    def ask_questions(self):
        """Interactive questionnaire"""
        print("\n" + "="*70)
        print(f"🎯 Setting up project skills for: {self.project_name}")
        print("="*70)
        print()

        # Q1: What does it do?
        print("1️⃣  PROJECT PURPOSE")
        desc = input("   What does this project do? (one sentence): ").strip()
        self.responses['description'] = desc

        # Q2: Which platforms?
        print("\n2️⃣  PLATFORMS")
        print("   Available: ensi, site, mobile, oms, integration, gloriaots, 1c, arm, data-analytics")
        platforms = input("   Which platforms does it touch? (comma-separated): ").strip()
        self.responses['platforms'] = [p.strip() for p in platforms.split(',')]

        # Q3: Domain
        print("\n3️⃣  BUSINESS DOMAIN")
        print("   Examples: orders, catalog, customers, payments, inventory, delivery, returns")
        domain = input("   Main business domain: ").strip()
        self.responses['domain'] = domain

        # Q4: Tech stack
        print("\n4️⃣  TECHNOLOGY STACK")
        print("   Available: php, typescript, java, go, dotnet, python, sql")
        tech = input("   Tech stack? (comma-separated): ").strip()
        self.responses['tech_stack'] = [t.strip() for t in tech.split(',')]

        # Q5: Related systems
        print("\n5️⃣  RELATED SYSTEMS")
        print("   Examples: ENSI, OMS, Integration, Gloria OTS, ARM, 1C, DWH")
        systems = input("   List related systems (comma-separated): ").strip()
        self.responses['related_systems'] = [s.strip() for s in systems.split(',')]

        # Q6: Dependencies
        print("\n6️⃣  SKILL DEPENDENCIES")
        print("   Examples: ensi-stack-anatomy, site-angular-conventions, git-workflow")
        deps = input("   What skills does this project need? (comma-separated): ").strip()
        self.responses['dependencies'] = [d.strip() for d in deps.split(',') if d.strip()]

        # Q7: Key problems
        print("\n7️⃣  KEY PROBLEMS")
        print("   What business/technical problems does this solve?")
        problems = input("   Problems (one per line, enter empty to finish):\n   ")
        self.responses['problems'] = [p.strip() for p in problems.split('\n') if p.strip()]

        # Q8: Success criteria
        print("\n8️⃣  SUCCESS CRITERIA")
        print("   How do we measure success?")
        criteria = input("   Success criteria (one per line, enter empty to finish):\n   ")
        self.responses['criteria'] = [c.strip() for c in criteria.split('\n') if c.strip()]

        # Q9: Related agents
        print("\n9️⃣  AGENTS THAT NEED THIS SKILL")
        print("   Which agents will use this skill?")
        agents = input("   Agent names (comma-separated): ").strip()
        self.responses['agents'] = [a.strip() for a in agents.split(',') if a.strip()]

        # Q10: Priority
        print("\n🔟 PRIORITY LEVEL")
        print("   critical (blocks release), high (important), medium (nice-to-have), low (future)")
        priority = input("   Priority level [medium]: ").strip() or "medium"
        self.responses['priority'] = priority

    def generate_skill_md(self):
        """Generate SKILL.md"""
        timestamp = datetime.utcnow().isoformat() + "Z"

        deps_yaml = "\n".join([f"  - {d}" for d in self.responses.get('dependencies', [])])
        platforms_yaml = "\n".join([f"  - {p}" for p in self.responses.get('platforms', [])])
        tech_yaml = "\n".join([f"  - {t}" for t in self.responses.get('tech_stack', [])])
        systems_yaml = "\n".join([f"  - {s}" for s in self.responses.get('related_systems', [])])
        agents_yaml = "\n".join([f"  - {a}" for a in self.responses.get('agents', [])])

        problems_md = "\n".join([f"- {p}" for p in self.responses.get('problems', [])])
        criteria_md = "\n".join([f"- {c}" for c in self.responses.get('criteria', [])])

        content = f"""---
name: {self.project_name}
description: {self.responses['description']}
version: 1.0.0
compatibility: ">=1.5.0,<3.0.0"
depends_on:
{deps_yaml if deps_yaml else "  # No dependencies"}
platforms:
{platforms_yaml}
domain: {self.responses['domain']}
tech_stack:
{tech_yaml}
related_systems:
{systems_yaml}
used_by:
{agents_yaml if agents_yaml else "  # To be filled"}
priority: {self.responses['priority']}
status: development
last_updated: {timestamp}
---

# {self.project_name.replace('-', ' ').title()} Skill

{self.responses['description']}

## Problem Solved

{problems_md}

## Success Criteria

{criteria_md}

## Architecture & Design

### System Components

Describe the main components of this system:

- Component 1: Description
- Component 2: Description
- Component 3: Description

### Data Flow

```
[Source] → [Processing] → [Storage] → [Consumer]
```

### Integration Points

- System A: How we integrate
- System B: How we integrate
- System C: How we integrate

## API & Contracts

### Key Endpoints/Functions

- `endpoint_1`: Input/output contract
- `endpoint_2`: Input/output contract

### Event Contracts

- `event_1`: Schema and purpose
- `event_2`: Schema and purpose

## Error Handling

### Error Types

| Error | Cause | Recovery |
|-------|-------|----------|
| Error 1 | Cause | Recovery |
| Error 2 | Cause | Recovery |

### Resilience Strategy

- Timeouts: X seconds
- Retries: X times
- Fallback: Local/skip/abort

## Testing Strategy

### Unit Tests

- Component 1 tests
- Component 2 tests

### Integration Tests

- Test with System A
- Test with System B

### E2E Tests

- Full workflow test
- Error scenario test

## Deployment

### Checklist

- [ ] Code review complete
- [ ] Tests passing
- [ ] Performance benchmarked
- [ ] Security review done
- [ ] Documentation complete
- [ ] Monitoring configured
- [ ] Rollback plan documented

### Rollout Strategy

- Phase 1: Deploy to staging
- Phase 2: Deploy to production (10% traffic)
- Phase 3: Gradual rollout (100% by end of day)

## Monitoring & Observability

### Key Metrics

- Metric 1: What it measures
- Metric 2: What it measures
- Metric 3: What it measures

### Alerts

- Alert 1: When to trigger
- Alert 2: When to trigger

### Logs

- Key log entries
- Error signatures

## Known Limitations

- Limitation 1
- Limitation 2
- Future improvement: ?

## References

- Related documentation
- Related skills
- External resources

## Troubleshooting

### Issue: Common problem 1

**Symptoms:** How it manifests
**Cause:** Root cause
**Solution:** How to fix

### Issue: Common problem 2

**Symptoms:** How it manifests
**Cause:** Root cause
**Solution:** How to fix

## See Also

- Related skill: `skill-x`
- Related skill: `skill-y`
- Documentation: `docs/related.md`
"""

        skill_file = self.project_path / "SKILL.md"
        skill_file.write_text(content)
        print(f"✅ Created: {skill_file}")

    def generate_config_yaml(self):
        """Generate project config YAML"""
        content = f"""# {self.project_name.replace('-', ' ').title()} Configuration

project:
  name: {self.project_name}
  description: {self.responses['description']}
  domain: {self.responses['domain']}
  priority: {self.responses['priority']}

platforms:
"""
        for p in self.responses['platforms']:
            content += f"  - {p}\n"

        content += f"""
tech_stack:
"""
        for t in self.responses['tech_stack']:
            content += f"  - {t}\n"

        content += f"""
integrations:
  related_systems:
"""
        for s in self.responses['related_systems']:
            content += f"    - {s}\n"

        if self.responses['dependencies']:
            content += f"""
dependencies:
"""
            for d in self.responses['dependencies']:
                content += f"  - {d}\n"

        content += f"""
checklist:
  development:
    - [ ] Architecture documented
    - [ ] API contracts defined
    - [ ] Error handling strategy documented
    - [ ] Testing strategy documented
    - [ ] Database schema (if applicable)

  quality_assurance:
    - [ ] Unit tests pass (>80% coverage)
    - [ ] Integration tests pass
    - [ ] E2E tests pass
    - [ ] Performance benchmarks run
    - [ ] Security review complete

  deployment:
    - [ ] Documentation complete
    - [ ] Deployment plan documented
    - [ ] Rollback procedure documented
    - [ ] Monitoring configured
    - [ ] Alerts configured
    - [ ] Log aggregation configured

  post_launch:
    - [ ] Metrics verified
    - [ ] Alerts tested
    - [ ] Support team trained
    - [ ] Runbook created

skill_owners:
  primary: ?
  secondary: ?

agents_using_this_skill:
"""
        for a in self.responses.get('agents', []):
            content += f"  - {a}\n"

        config_file = self.project_path / f"{self.project_name}.yaml"
        config_file.write_text(content)
        print(f"✅ Created: {config_file}")

    def generate_examples(self):
        """Generate examples template"""
        content = f"""# {self.project_name.replace('-', ' ').title()} Examples

## Example 1: Basic Usage

### Scenario
Describe what this example demonstrates

### Code
\\`\\`\\`python
# Your code example here
\\`\\`\\`

### Expected Output
\\`\\`\\`
Expected result
\\`\\`\\`

---

## Example 2: Error Handling

### Scenario
Describe error scenario

### Code
\\`\\`\\`python
# Error handling example
\\`\\`\\`

### Expected Output
\\`\\`\\`
Error output
\\`\\`\\`

---

## Example 3: Integration with Another System

### Scenario
Describe integration scenario

### Code
\\`\\`\\`python
# Integration example
\\`\\`\\`

### Expected Output
\\`\\`\\`
Integration result
\\`\\`\\`

---

## Running the Examples

1. Prerequisites
2. Setup
3. Run commands
4. Verify results
"""

        examples_file = self.project_path / "examples" / "EXAMPLES.md"
        examples_file.write_text(content)
        print(f"✅ Created: {examples_file}")

    def generate_readme(self):
        """Generate folder README"""
        content = """# PROJECT SKILLS

Project-specific skills for individual initiatives, features, or domains.

## What Goes Here?

- Skills for specific Gloria Jeans projects/features
- Domain-specific orchestration patterns
- Project-wide conventions and best practices
- Problem-solving patterns for this project
- Temporary skills during project lifecycle

## Structure

Each project skill folder contains:
- `SKILL.md` - Main skill documentation
- `<project-name>.yaml` - Configuration and checklist
- `examples/` - Working code examples

## How to Add a New Project Skill

\\`\\`\\`bash
python ../_scripts/init-project-skills.py <project-name>
\\`\\`\\`

This creates an interactive questionnaire to describe your system.

## Life Cycle

1. **Development** - Skill being developed
2. **Production** - Skill in use by agents
3. **Maintenance** - Regular updates and fixes
4. **Archive** - Project complete, skill no longer needed

## See Also

- Platform skills: `../PLATFORM/`
- Generic skills: `../GENERIC/`
- Skill registry: `../REGISTRY.json`
"""

        if not (self.skills_base / "PROJECT" / "_README.md").exists():
            readme_file = self.skills_base / "PROJECT" / "_README.md"
            readme_file.write_text(content)
            print(f"✅ Created: {readme_file}")

    def run(self):
        """Run initialization"""
        print("\n🚀 Project Skills Initializer")
        print("="*70)

        if not self.validate_project_name():
            return False

        self.create_structure()
        self.generate_readme()
        self.ask_questions()
        self.generate_skill_md()
        self.generate_config_yaml()
        self.generate_examples()

        print("\n" + "="*70)
        print(f"✅ PROJECT SKILL INITIALIZED: {self.project_name}")
        print("="*70)
        print("\n📝 Next steps:")
        print(f"  1. Edit {self.project_path}/SKILL.md with detailed documentation")
        print(f"  2. Edit {self.project_path}/{self.project_name}.yaml with your checklist")
        print(f"  3. Add code examples to {self.project_path}/examples/")
        print(f"  4. Integrate agents that use this skill into SKILL.md")
        print(f"  5. Run: python ../_scripts/verify-skills.py")
        print()

        return True


def main():
    if len(sys.argv) < 2:
        print("Usage: init-project-skills.py <project-name>")
        print("Example: init-project-skills.py beauty-marking")
        sys.exit(1)

    project_name = sys.argv[1]
    initializer = ProjectSkillInitializer(project_name)

    success = initializer.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
