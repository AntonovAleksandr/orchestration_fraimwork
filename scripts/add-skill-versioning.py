#!/usr/bin/env python3
"""Add versioning frontmatter to all skills"""

import re
from pathlib import Path

skills_dir = Path(".claude/skills")
framework_version = "1.0.0"

def add_versioning(skill_file):
    """Add versioning frontmatter to a skill file"""
    with open(skill_file) as f:
        content = f.read()

    # Check if already has versioning
    if "version:" in content[:200]:
        print(f"  ✓ {skill_file.stem} (already versioned)")
        return

    # Extract layer and name
    layer = skill_file.parent.name
    skill_name = skill_file.stem

    # Determine platform
    platforms = {
        "ensi": "ENSI",
        "oms": "OMS",
        "site": "Site",
        "mobile": "Mobile",
        "integration": "Integration",
        "gloriaots": "Gloria OTS",
        "go": "Go",
    }
    platform = "Generic"
    for key, val in platforms.items():
        if key in skill_name:
            platform = val
            break

    # Add frontmatter
    frontmatter = f"""---
name: {skill_name}
version: 1.0.0
layer: {layer}
platform: {platform}
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---

"""

    # Check if starts with ---
    if content.startswith("---"):
        # Replace existing frontmatter
        match = re.search(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if match:
            content = frontmatter + content[match.end():]
    else:
        # Add new frontmatter
        content = frontmatter + content

    with open(skill_file, 'w') as f:
        f.write(content)

    print(f"  ✓ {skill_file.stem} added versioning")

# Process all skills
print("Adding versioning to skills...")
print()

for layer_dir in skills_dir.glob("*/"):
    if not layer_dir.is_dir():
        continue

    print(f"Layer: {layer_dir.name}")
    for skill_file in sorted(layer_dir.glob("*.md")):
        add_versioning(skill_file)
    print()

print("✅ All skills versioned!")
