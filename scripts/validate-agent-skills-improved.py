#!/usr/bin/env python3
"""Validate agent-to-skill references (improved false-positive filtering)"""

import re
import sys
from pathlib import Path
from collections import defaultdict

# Common false positives to exclude
FALSE_POSITIVES = {
    "readme", "docs", "guide", "description", "feature", "file", "name", "type",
    "json", "yaml", "xml", "python", "typescript", "javascript", "bash", "shell",
    "action", "data", "code", "error", "status", "phase", "message", "worker",
    "platform", "module", "package", "import", "export", "function", "class",
    "method", "property", "field", "value", "result", "output", "input",
    "request", "response", "handler", "controller", "service", "router",
    "middleware", "adapter", "client", "server", "api", "schema", "model",
    "view", "component", "test", "mock", "stub", "config", "env", "build",
    "deploy", "release", "version", "tag", "branch", "merge", "commit",
    "pull", "push", "checkout", "clone", "fetch", "current", "main", "master",
    "development", "staging", "production", "demo", "testing", "build", "5",
    "abstract", "adjacent", "affected", "appropriate", "architect", "brainstorming",
    "business", "chosen", "cmd", "complete", "concurrent", "confluence",
    "considered", "coverage", "create", "current", "database", "dependencies",
    "deprecated", "description", "derived", "dict", "disk", "dist", "document",
    "existing", "explicit", "flow", "freshness", "future", "generated",
    "gh", "health", "http", "httptest", "i", "id_rsa", "if", "import",
    "integration", "issue", "item", "keytool", "key", "legacy", "lineage",
    "list", "location", "lock", "logs", "master", "metrics", "mid", "migration",
    "minutes", "mission", "missing", "most", "need", "next", "nullable",
    "number", "of", "operational", "option", "or", "ownership", "patch_package",
    "pay_service", "per", "place", "plan", "port", "postal", "potentially",
    "prepare", "prevent", "properties", "protocol", "python_m", "query",
    "readme", "recovery", "redis", "reduce", "reference", "rn_yookassa",
    "safety", "sandbox", "sample", "sass", "scale", "search", "secret",
    "security", "send", "sequence", "setting", "shared", "shipping", "signal",
    "simple", "since", "site_en", "site_kz", "site_ru", "size", "socket",
    "source", "specific", "specify", "sql", "src", "stability", "stack",
    "staging", "state", "step", "storage", "store", "string", "structure",
    "subscribe", "sync", "system", "tag", "target_type", "task", "team",
    "test", "testing", "than", "that", "the", "them", "then", "there",
    "these", "they", "time", "timing", "tips", "tool", "topic", "total",
    "trace", "track", "transaction", "transform", "transport", "trigger",
    "tuple", "type", "typing", "ui", "ui_kit", "unable", "unit", "until",
    "update", "upgrade", "url", "use", "used", "user", "using", "utility",
    "validate", "validation", "value", "version", "verification", "view",
    "visual", "warning", "watch", "way", "when", "where", "while", "who",
    "why", "width", "window", "with", "without", "work", "working", "world",
    "write", "writer", "written", "yet", "zone",
}

def extract_skill_references(content: str) -> list:
    """Extract skill references from agent prompts"""
    # Only match hyphen-separated names (pattern-development-ensi style)
    # This filters out most false positives
    pattern = r"(?:[-•]\s+|Use\s+|skill[s]?[:=]\s+)([a-z][a-z0-9]*(?:-[a-z0-9]+)+)"

    matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)

    # Normalize and filter
    skills = set()
    for match in matches:
        skill = match.lower()
        # Only include if:
        # 1. Contains hyphen (pattern-style)
        # 2. Not a common false positive
        # 3. At least 2 parts (part1-part2)
        if '-' in skill and skill not in FALSE_POSITIVES:
            skills.add(skill)

    return sorted(list(skills))

def get_available_skills() -> dict:
    """Get all available skills"""
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
    """Validate all agents"""
    agents_dir = Path(".claude/agents")
    if not agents_dir.exists():
        print("❌ No agents directory")
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

        refs = extract_skill_references(content)
        total_refs += len(refs)

        for ref in refs:
            if ref not in available_skills:
                issues[agent_name].append(ref)
            else:
                valid_refs += 1

    # Report
    print(f"Validated {agent_count} agents")
    print(f"✓ {valid_refs} valid references")
    if total_refs > valid_refs:
        print(f"✗ {total_refs - valid_refs} missing")
    print()

    if issues:
        print("❌ BROKEN REFERENCES:\n")
        for agent_name in sorted(issues.keys()):
            print(f"  {agent_name}:")
            for skill in sorted(set(issues[agent_name])):
                print(f"    → {skill} (NOT FOUND)")
        print()
        return False
    else:
        print("✅ All references valid!")
        return True

if __name__ == "__main__":
    success = validate_agents()
    sys.exit(0 if success else 1)
