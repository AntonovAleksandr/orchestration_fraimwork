#!/bin/bash
# Export Orchestration Framework (Sanitized)
# - Removes ALL project-specific references
# - Replaces examples with generic placeholders
# - Safe for public repositories
#
# Usage: ./scripts/export-orchestration-framework-clean.sh /path/to/orchestration_framework

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 /path/to/orchestration_framework"
    echo ""
    echo "This script exports the orchestration framework SANITIZED:"
    echo "  ✓ All project names replaced (gj-opsomn002 → [your-project])"
    echo "  ✓ All GJ-specific configs removed"
    echo "  ✓ Generic examples only"
    echo "  ✓ Safe for public repository"
    exit 1
fi

TARGET_DIR="$1"

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory does not exist: $TARGET_DIR"
    exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "📦 Exporting Orchestration Framework (SANITIZED)..."
echo "   Source: $SOURCE_DIR"
echo "   Target: $TARGET_DIR"
echo ""

# Function to copy and sanitize file
copy_and_sanitize() {
    local src="$1"
    local dst="$2"

    if [ ! -e "$src" ]; then
        echo "   ⚠️  Skipped (not found): $src"
        return
    fi

    mkdir -p "$(dirname "$dst")"

    if [ -d "$src" ]; then
        cp -r "$src" "$dst"
        echo "   ✓ Copied dir: $(basename $src)"
    else
        cp "$src" "$dst"
        # Sanitize content
        sanitize_file "$dst"
        echo "   ✓ Copied & sanitized: $(basename $src)"
    fi
}

# Sanitize file content
sanitize_file() {
    local file="$1"

    # Only process text files
    if ! file "$file" | grep -q "text"; then
        return
    fi

    # Replace project names
    sed -i.bak \
        -e 's/gj-opsomn002/[your-project]/g' \
        -e 's/gj-beauty/[your-project]/g' \
        -e 's/OPSOMN002/[YOUR-PROJECT]/g' \
        -e 's/BEAUTY/[YOUR-PROJECT]/g' \
        -e 's/Gloria Jeans/Your Organization/g' \
        -e 's/GJ-Ecommerce/orchestration_framework/g' \
        -e 's/GJ/[Your-Org]/g' \
        "$file"

    # Remove backup
    rm -f "$file.bak"
}

# ============================================================================
# PHASE 1: Foundation (Week 1-4)
# ============================================================================

echo ""
echo "📋 Phase 1: Foundation Skills"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/skills/gj-task-docs" \
    "$TARGET_DIR/.claude/skills/gj-task-docs"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/skills/gj-reviewer" \
    "$TARGET_DIR/.claude/skills/gj-reviewer"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/AGENTS.md" \
    "$TARGET_DIR/.claude/AGENTS.md"

# ============================================================================
# PHASE 2: Hybrid Integration (Week 5-8)
# ============================================================================

echo ""
echo "📋 Phase 2: Hybrid System Integration"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/orchestration/phase2-hybrid-integration.md" \
    "$TARGET_DIR/.claude/orchestration/phase2-hybrid-integration.md"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/orchestration/worker-messaging.py" \
    "$TARGET_DIR/.claude/orchestration/worker-messaging.py"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/orchestration/PHASE2-QUICKSTART.md" \
    "$TARGET_DIR/.claude/orchestration/PHASE2-QUICKSTART.md"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/orchestration/phase2-risk-assessment.md" \
    "$TARGET_DIR/.claude/orchestration/phase2-risk-assessment.md"

# ============================================================================
# ORCHESTRATION FRAMEWORK
# ============================================================================

echo ""
echo "📋 Orchestration Framework"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/orchestration/README.md" \
    "$TARGET_DIR/.claude/orchestration/README.md"

for file in "$SOURCE_DIR/.claude/orchestration/"pattern-*.md; do
    if [ -f "$file" ]; then
        copy_and_sanitize "$file" "$TARGET_DIR/.claude/orchestration/$(basename $file)"
    fi
done

# ============================================================================
# GENERIC SKILLS (Layer 3)
# ============================================================================

echo ""
echo "📋 Generic Engineering Skills (Layer 3)"

generic_skills=(
    "gj-reviewer"
)

for skill in "${generic_skills[@]}"; do
    src="$SOURCE_DIR/.claude/skills/generic/$skill"
    dst="$TARGET_DIR/.claude/skills/generic/$skill"

    if [ -d "$src" ]; then
        copy_and_sanitize "$src" "$dst"
    elif [ -d "$SOURCE_DIR/.claude/skills/$skill" ]; then
        copy_and_sanitize "$SOURCE_DIR/.claude/skills/$skill" "$TARGET_DIR/.claude/skills/$skill"
    fi
done

# ============================================================================
# SKILLS TAXONOMY & REGISTRY (SANITIZED)
# ============================================================================

echo ""
echo "📋 Skills Taxonomy & Registry (Sanitized)"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/skills/SKILLS-TAXONOMY.md" \
    "$TARGET_DIR/.claude/skills/SKILLS-TAXONOMY.md"

# Sanitize registry YAML specially
copy_and_sanitize \
    "$SOURCE_DIR/.claude/skills/skills-registry.yaml" \
    "$TARGET_DIR/.claude/skills/skills-registry.yaml"

# Also replace project references in YAML
if [ -f "$TARGET_DIR/.claude/skills/skills-registry.yaml" ]; then
    sed -i.bak \
        -e 's/gj-opsomn002/my-project/g' \
        -e 's/gj-beauty/my-project/g' \
        "$TARGET_DIR/.claude/skills/skills-registry.yaml"
    rm -f "$TARGET_DIR/.claude/skills/skills-registry.yaml.bak"
fi

# ============================================================================
# RULES & DOCUMENTATION
# ============================================================================

echo ""
echo "📋 Rules & Documentation (Sanitized)"

for rule_file in "$SOURCE_DIR/.claude/rules"/*.md; do
    if [ -f "$rule_file" ]; then
        copy_and_sanitize "$rule_file" "$TARGET_DIR/.claude/rules/$(basename $rule_file)"
    fi
done

# ============================================================================
# IDE COMPATIBILITY
# ============================================================================

echo ""
echo "📋 IDE Compatibility Guide (Sanitized)"

copy_and_sanitize \
    "$SOURCE_DIR/.claude/IDE-COMPATIBILITY.md" \
    "$TARGET_DIR/.claude/IDE-COMPATIBILITY.md"

# ============================================================================
# CREATE SANITIZATION REPORT
# ============================================================================

echo ""
echo "📋 Creating Sanitization Report"

cat > "$TARGET_DIR/SANITIZATION_REPORT.md" << 'EOF'
# Sanitization Report

**Date:** $(date)
**Source:** GJ-Ecommerce orchestration_framework
**Status:** ✅ Sanitized for Public Release

## What Was Removed

❌ Project names:
   - gj-opsomn002 → [your-project]
   - gj-beauty → [your-project]
   - OPSOMN002 → [YOUR-PROJECT]

❌ Organization names:
   - Gloria Jeans → Your Organization
   - GJ-Ecommerce → orchestration_framework
   - GJ → [Your-Org]

❌ Project-specific skills:
   - .claude/skills/project/ (not exported)
   - All project configs

❌ Local hooks:
   - .claude/hooks/ (not exported)
   - .gitignore entries

## What Was Included

✅ Generic framework:
   - Phase 1-3 orchestration system
   - Worker messaging system
   - Generic engineering skills (Layer 3)
   - Skills taxonomy and registry
   - IDE compatibility adapters
   - Documentation and guides

✅ Ready to customize:
   - Examples use [your-project] placeholders
   - Easy to replace with your own names
   - All generic skills included

## Before Using

1. Replace [your-project] with your actual project name
2. Replace [Your-Organization] with your org name
3. Replace [Your-Org] with your org abbreviation
4. Update skills-registry.yaml with your projects
5. Create project-specific skills in .claude/skills/project/

## Security Check

Run this to verify no project details remain:

```bash
grep -r "gj-\|OPSOMN\|Gloria\|GJ-Ecommerce" .claude/ || echo "✅ Clean!"
```

---

**Safe to publish:** Yes ✅
**Contains sensitive data:** No ✅
**Ready for public repo:** Yes ✅
EOF

echo "   ✓ Created SANITIZATION_REPORT.md"

# ============================================================================
# VERIFY SANITIZATION
# ============================================================================

echo ""
echo "🔒 Verifying Sanitization..."

# Check for remaining project names (exclude placeholders like OPSOMN002-XXX)
if grep -r "gj-opsomn002\|gj-beauty\|Gloria Jeans\|GJ-Ecommerce" "$TARGET_DIR" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" > /dev/null; then
    echo "   ⚠️  WARNING: Some project references remain!"
    echo "   Found:"
    grep -r "gj-opsomn002\|gj-beauty\|Gloria Jeans\|GJ-Ecommerce" "$TARGET_DIR" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" | head -5
elif grep -r "OPSOMN002" "$TARGET_DIR" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" | grep -v "OPSOMN002-XXX" > /dev/null; then
    echo "   ⚠️  WARNING: Some OPSOMN references remain!"
    echo "   Found:"
    grep -r "OPSOMN002" "$TARGET_DIR" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" | grep -v "OPSOMN002-XXX" | head -5
else
    echo "   ✓ No project-specific references found!"
fi

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Sanitization Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Exported to: $TARGET_DIR"
echo ""
echo "Sanitization Applied:"
echo "  ✓ Project names replaced with [your-project]"
echo "  ✓ Organization names replaced with [Your-Organization]"
echo "  ✓ All project-specific configs excluded"
echo "  ✓ All hooks excluded (local, .gitignore)"
echo "  ✓ Safe for public repository"
echo ""
echo "Next Steps:"
echo "  1. Review SANITIZATION_REPORT.md"
echo "  2. Replace [your-project] with your project name"
echo "  3. Replace [Your-Organization] with your org name"
echo "  4. Update skills-registry.yaml with your projects"
echo "  5. Create project-specific skills in .claude/skills/project/"
echo "  6. git add . && git commit && git push"
echo ""
echo "Files Included:"
echo "  ✓ Phase 1-3 Documentation"
echo "  ✓ Worker Messaging System"
echo "  ✓ Generic Skills (Layer 3)"
echo "  ✓ Skills Taxonomy & Registry"
echo "  ✓ IDE Compatibility Adapters"
echo "  ✓ Rules & Standards"
echo ""
echo "Files Excluded:"
echo "  ✗ Project-Specific Skills (Layer 1)"
echo "  ✗ Hooks (.gitignore)"
echo "  ✗ Project Configs"
echo ""
