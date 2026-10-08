#!/usr/bin/env python3
"""Validate that all agent skill references point to existing skills"""

import re
import sys
from pathlib import Path
from collections import defaultdict

def extract_skill_references(content: str) -> list:
    """Extract skill names from agent prompts"""
    # Match patterns like:
    # - skill-name
    # * skill-name
    # skill-name (in code blocks)
    patterns = [
        r"[-•]\s+([a-z0-9\-]+(?:_[a-z0-9\-]+)*)",  # List items
        r"`([a-z0-9\-]+(?:_[a-z0-9\-]+)*)`",  # Backticks
        r'"([a-z0-9\-]+(?:_[a-z0-9\-]+)*)"',  # Quotes
    ]

    skills = set()
    for pattern in patterns:
        matches = re.findall(pattern, content)
        skills.update(matches)

    return list(skills)

def get_available_skills() -> dict:
    """Get all available skills from .claude/skills"""
    skills_dir = Path(".claude/skills")
    available = {}

    for layer_dir in skills_dir.glob("*/"):
        if not layer_dir.is_dir():
            continue

        layer = layer_dir.name
        for skill_file in layer_dir.glob("*.md"):
            skill_name = skill_file.stem
            available[skill_name] = {
                "file": str(skill_file),
                "layer": layer,
            }

    return available

def validate_agents():
    """Validate all agent prompts"""
    agents_dir = Path(".claude/agents")
    if not agents_dir.exists():
        print("❌ No agents directory found")
        return False

    available_skills = get_available_skills()
    print(f"Found {len(available_skills)} available skills\n")

    issues = defaultdict(list)
    agent_count = 0
    total_refs = 0
    valid_refs = 0

    for agent_file in sorted(agents_dir.glob("*.md")):
        agent_name = agent_file.stem
        agent_count += 1

        with open(agent_file) as f:
            content = f.read()

        # Extract skill references
        refs = extract_skill_references(content)

        # Filter out common false positives
        refs = [r for r in refs if r not in [
            "readme", "docs", "guide", "description", "feature",
            "file", "name", "type", "json", "yaml", "xml", "python",
            "typescript", "javascript", "bash", "shell"
        ]]

        total_refs += len(refs)

        for ref in refs:
            if ref not in available_skills:
                issues[agent_name].append(ref)
            else:
                valid_refs += 1

    # Print results
    print(f"Validated {agent_count} agents")
    print(f"Valid skill references: {valid_refs}")
    print(f"Total references: {total_refs}")
    print()

    if issues:
        print("❌ ISSUES FOUND:\n")
        for agent_name, missing_skills in sorted(issues.items()):
            print(f"  {agent_name}:")
            for skill in sorted(set(missing_skills)):
                print(f"    ✗ {skill} (not found)")
        print()
        return False
    else:
        print("✅ All agent skill references valid!")
        return True

def generate_report(output_file: str = None):
    """Generate detailed validation report"""
    agents_dir = Path(".claude/agents")
    available_skills = get_available_skills()

    report = []
    report.append("# Agent-to-Skill Validation Report\n")

    for agent_file in sorted(agents_dir.glob("*.md")):
        agent_name = agent_file.stem

        with open(agent_file) as f:
            content = f.read()

        refs = extract_skill_references(content)
        refs = [r for r in refs if r not in [
            "readme", "docs", "guide", "description", "feature",
            "file", "name", "type", "json", "yaml", "xml", "python",
            "typescript", "javascript", "bash", "shell"
        ]]

        report.append(f"## {agent_name}\n")

        if refs:
            report.append("**Skills Referenced:**\n")
            for ref in sorted(set(refs)):
                if ref in available_skills:
                    info = available_skills[ref]
                    report.append(f"- ✓ `{ref}` ({info['layer']}) @ {info['file']}\n")
                else:
                    report.append(f"- ✗ `{ref}` (**NOT FOUND**)\n")
        else:
            report.append("No skill references found\n")

        report.append("\n")

    report_text = "".join(report)

    if output_file:
        Path(output_file).write_text(report_text)
        print(f"Report saved: {output_file}")
    else:
        print(report_text)

    return report_text

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate agent-to-skill references")
    parser.add_argument("--report", help="Generate detailed report to file")
    parser.add_argument("--strict", action="store_true", help="Exit with error if issues found")

    args = parser.parse_args()

    if args.report:
        generate_report(args.report)

    success = validate_agents()

    if args.strict and not success:
        sys.exit(1)
