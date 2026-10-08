#!/bin/bash
# Export Orchestration Framework to Separate Repository
# Usage: ./scripts/export-orchestration-framework.sh /path/to/orchestration_framework
#
# This script copies all orchestration system files EXCEPT project-specific skills
# to a separate repository that can be used in other projects.

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 /path/to/orchestration_framework"
    echo ""
    echo "This script exports:"
    echo "  - Phase 1-3 orchestration system"
    echo "  - Generic engineering skills (Layer 3)"
    echo "  - Stack-specific skills (Layer 2)"
    echo "  - Orchestration documentation"
    echo ""
    echo "Excludes:"
    echo "  - Project-specific skills (gj-opsomn002, gj-beauty, etc)"
    echo "  - Project-specific configs"
    exit 1
fi

TARGET_DIR="$1"

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory does not exist: $TARGET_DIR"
    exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "📦 Exporting Orchestration Framework..."
echo "   Source: $SOURCE_DIR"
echo "   Target: $TARGET_DIR"
echo ""

# Function to copy file or directory
copy_item() {
    local src="$1"
    local dst="$2"

    if [ ! -e "$src" ]; then
        echo "   ⚠️  Skipped (not found): $src"
        return
    fi

    # Create parent directory
    mkdir -p "$(dirname "$dst")"

    if [ -d "$src" ]; then
        # Copy directory (preserve structure)
        cp -r "$src" "$dst"
        echo "   ✓ Copied dir: $(basename $src)"
    else
        # Copy file
        cp "$src" "$dst"
        echo "   ✓ Copied file: $(basename $src)"
    fi
}

# ============================================================================
# PHASE 1: Foundation (Week 1-4)
# ============================================================================

echo ""
echo "📋 Phase 1: Foundation Skills"

# gj-task-docs (generic, not project-specific!)
copy_item \
    "$SOURCE_DIR/.claude/skills/gj-task-docs" \
    "$TARGET_DIR/.claude/skills/gj-task-docs"

# gj-reviewer (generic)
copy_item \
    "$SOURCE_DIR/.claude/skills/gj-reviewer" \
    "$TARGET_DIR/.claude/skills/gj-reviewer"

# Hooks (local, not committed)
echo "   ℹ️  Note: Hooks are local (.gitignore), create manually:"
echo "       - guard_secrets.py"
echo "       - comment_budget.py"
echo "       See: .claude/hooks/README.md for details"

# Phase 1 documentation
copy_item \
    "$SOURCE_DIR/.claude/AGENTS.md" \
    "$TARGET_DIR/.claude/AGENTS.md"

# ============================================================================
# PHASE 2: Hybrid Integration (Week 5-8)
# ============================================================================

echo ""
echo "📋 Phase 2: Hybrid System Integration"

copy_item \
    "$SOURCE_DIR/.claude/orchestration/phase2-hybrid-integration.md" \
    "$TARGET_DIR/.claude/orchestration/phase2-hybrid-integration.md"

copy_item \
    "$SOURCE_DIR/.claude/orchestration/worker-messaging.py" \
    "$TARGET_DIR/.claude/orchestration/worker-messaging.py"

copy_item \
    "$SOURCE_DIR/.claude/orchestration/PHASE2-QUICKSTART.md" \
    "$TARGET_DIR/.claude/orchestration/PHASE2-QUICKSTART.md"

copy_item \
    "$SOURCE_DIR/.claude/orchestration/phase2-risk-assessment.md" \
    "$TARGET_DIR/.claude/orchestration/phase2-risk-assessment.md"

# ============================================================================
# PHASE 3: Architecture (Week 9-26) - if exists
# ============================================================================

echo ""
echo "📋 Phase 3: Architecture (if implemented)"

if [ -f "$SOURCE_DIR/.claude/orchestration/phase3-architecture.md" ]; then
    copy_item \
        "$SOURCE_DIR/.claude/orchestration/phase3-architecture.md" \
        "$TARGET_DIR/.claude/orchestration/phase3-architecture.md"
else
    echo "   ℹ️  Phase 3 not yet implemented (planned for Week 9)"
fi

# ============================================================================
# ORCHESTRATION FRAMEWORK
# ============================================================================

echo ""
echo "📋 Orchestration Framework"

copy_item \
    "$SOURCE_DIR/.claude/orchestration/README.md" \
    "$TARGET_DIR/.claude/orchestration/README.md"

copy_item \
    "$SOURCE_DIR/.claude/orchestration/LIVE_EXECUTION_TRACE.md" \
    "$TARGET_DIR/.claude/orchestration/LIVE_EXECUTION_TRACE.md"

copy_item \
    "$SOURCE_DIR/.claude/orchestration/ORCHESTRATOR_CONSOLE.md" \
    "$TARGET_DIR/.claude/orchestration/ORCHESTRATOR_CONSOLE.md"

# Pattern files
for pattern in pattern-*.md; do
    if [ -f "$SOURCE_DIR/.claude/orchestration/$pattern" ]; then
        copy_item \
            "$SOURCE_DIR/.claude/orchestration/$pattern" \
            "$TARGET_DIR/.claude/orchestration/$pattern"
    fi
done

# ============================================================================
# GENERIC SKILLS (Layer 3: always applicable)
# ============================================================================

echo ""
echo "📋 Generic Engineering Skills (Layer 3)"

# These skills exist in the current directory structure
# If they don't exist yet, they should be created later

generic_skills=(
    "gj-reviewer"                          # already copied above
    "test-driven-development"
    "data-driven-validation"
    "systematic-debugging"
    "performance-optimization"
    "security-best-practices"
    "documentation-standards"
)

for skill in "${generic_skills[@]}"; do
    src="$SOURCE_DIR/.claude/skills/generic/$skill"
    dst="$TARGET_DIR/.claude/skills/generic/$skill"

    if [ -d "$src" ]; then
        copy_item "$src" "$dst"
    elif [ -d "$SOURCE_DIR/.claude/skills/$skill" ]; then
        # Fallback: check if skill is in main skills directory
        copy_item "$SOURCE_DIR/.claude/skills/$skill" "$TARGET_DIR/.claude/skills/$skill"
    else
        echo "   ℹ️  Skill not yet implemented: $skill"
    fi
done

# ============================================================================
# SKILLS TAXONOMY & REGISTRY
# ============================================================================

echo ""
echo "📋 Skills Taxonomy & Registry"

copy_item \
    "$SOURCE_DIR/.claude/skills/SKILLS-TAXONOMY.md" \
    "$TARGET_DIR/.claude/skills/SKILLS-TAXONOMY.md"

copy_item \
    "$SOURCE_DIR/.claude/skills/skills-registry.yaml" \
    "$TARGET_DIR/.claude/skills/skills-registry.yaml"

# ============================================================================
# RULES & DOCUMENTATION
# ============================================================================

echo ""
echo "📋 Rules & Documentation"

# Copy all rules (generic, not project-specific)
for rule_file in "$SOURCE_DIR/.claude/rules"/*.md; do
    if [ -f "$rule_file" ]; then
        basename=$(basename "$rule_file")
        copy_item "$rule_file" "$TARGET_DIR/.claude/rules/$basename"
    fi
done

# ============================================================================
# CREATE README FOR ORCHESTRATION FRAMEWORK
# ============================================================================

echo ""
echo "📋 Creating Framework README"

cat > "$TARGET_DIR/ORCHESTRATION_FRAMEWORK.md" << 'EOF'
# Orchestration Framework

**Version:** 1.0
**Status:** Production-Ready (Phase 1-2)
**Purpose:** Reusable orchestration system for multi-agent agentic workflows

This is a standalone framework extracted from GJ-Ecommerce project.
It provides:

## Phases

- **Phase 1 (Foundation):** Mandatory documentation + independent review + protection hooks
- **Phase 2 (Hybrid 10/10):** Async messaging, parallel phases, data-driven validation
- **Phase 3 (Architecture):** State store, autonomous workers, cloud branches, dashboard

## Structure

```
.claude/
├── skills/
│   ├── gj-task-docs/           (Phase 1: documentation)
│   ├── gj-reviewer/            (Phase 1: code review)
│   ├── generic/                (Layer 3: universal skills)
│   ├── stack/                  (Layer 2: stack-specific skills)
│   └── SKILLS-TAXONOMY.md      (documentation)
│
├── orchestration/
│   ├── phase2-hybrid-integration.md
│   ├── worker-messaging.py
│   ├── PHASE2-QUICKSTART.md
│   └── phase2-risk-assessment.md
│
├── rules/                      (code style, git workflow, etc)
└── AGENTS.md                   (skills registry)
```

## Quick Start

1. Copy this framework into your project
2. Load Phase 1 skills: `claude-skills load --layer project-generic`
3. Implement project-specific skills in: `.claude/skills/project/[your-project]/`
4. Follow PHASE2-QUICKSTART.md when ready for Week 5

## Customization

### Project-Specific Skills

Create in: `.claude/skills/project/[your-project]/`

Example:
```
.claude/skills/project/
├── my-project/
│   ├── my-task-docs/SKILL.md
│   ├── my-workflow-flow/SKILL.md
│   └── my-architecture/SKILL.md
```

### Stack-Specific Skills

Already included for:
- PHP 8.1 + Swoole
- Angular 20 + Nx
- React Native 0.74
- Java + Spring Boot
- .NET 10

Add new stacks in: `.claude/skills/stack/[your-stack]/`

### Generic Skills

Always included (apply to all projects/stacks):
- gj-reviewer (code review)
- test-driven-development
- data-driven-validation
- systematic-debugging
- performance-optimization
- security-best-practices
- documentation-standards

## Integration

### In Your Project

1. Clone this framework
2. Update `.claude/skills/project/your-project/` with your specifics
3. Update `.claude/skills/skills-registry.yaml` with your project metadata
4. Load skills via: `claude-skills load --project your-project`

### In Your Agents

Add to agent prompts:

```markdown
## Available Skills

### Project Skills
- [your-project-skill]

### Stack Skills
- [your-stack-skill]

### Generic Skills
- gj-reviewer (8-point code review checklist)
- data-driven-validation (test on real data)
- test-driven-development (TDD workflow)
```

## Documentation

- `PHASE2-QUICKSTART.md`: Step-by-step guide for launching hybrid system
- `phase2-risk-assessment.md`: 6 critical risks + mitigation strategies
- `phase2-hybrid-integration.md`: Complete integration plan
- `SKILLS-TAXONOMY.md`: Understanding skills layering

## Support

For issues or improvements:
1. Check existing documentation
2. Review phase2-risk-assessment.md for known issues
3. Submit issues to this repository

## License

Same as parent project (GJ-Ecommerce)

---

**Note:** This framework is extracted from GJ-Ecommerce production system.
Use at your own risk in other projects. Customize for your needs.
EOF

echo "   ✓ Created ORCHESTRATION_FRAMEWORK.md"

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Export Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Exported to: $TARGET_DIR"
echo ""
echo "Next Steps:"
echo "  1. Review exported files"
echo "  2. Customize project-specific skills"
echo "  3. Update skills-registry.yaml for your project"
echo "  4. Add to git repository"
echo "  5. Follow PHASE2-QUICKSTART.md when ready"
echo ""
echo "Files Included:"
echo "  ✓ Phase 1-3 Documentation"
echo "  ✓ Worker Messaging System"
echo "  ✓ Generic Skills (Layer 3)"
echo "  ✓ Stack-Specific Skills (Layer 2)"
echo "  ✓ Orchestration Framework"
echo "  ✓ Rules & Documentation"
echo ""
echo "Files Excluded (create per project):"
echo "  ✗ Project-Specific Skills (Layer 1)"
echo "  ✗ Hooks (local, .gitignore)"
echo "  ✗ Project configs"
echo ""
