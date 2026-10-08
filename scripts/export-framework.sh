#!/bin/bash
# Export framework commits (sanitized) for GitHub

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       Framework Export (Sanitized for orchestration_framework)  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo

# 1. Read version
if [ ! -f VERSION ]; then
    echo "❌ VERSION file not found"
    exit 1
fi

VERSION=$(cat VERSION)
echo "Exporting framework v$VERSION"
echo

# 2. Verify no GJ paths in commits
echo "Scanning commits for project-specific content..."
FOUND_GJ=0

if git log -10 --all --name-status | grep -q "platform/"; then
    echo "❌ Found platform/ references in recent commits"
    FOUND_GJ=1
fi

if git log -10 --all --grep="OPSOMN\|gloria\|beauty\|Glory" -i | grep -q .; then
    echo "❌ Found project-specific commit messages"
    FOUND_GJ=1
fi

if [ $FOUND_GJ -eq 0 ]; then
    echo "✓ No project-specific content detected"
fi

echo

# 3. Files to include in export
echo "Files included in export:"
EXPORT_FILES=(
    "VERSION"
    "CHANGELOG.md"
    "README.md"
    ".claude/cli/claude-skills.py"
    ".claude/orchestration/worker-isolation.py"
    ".claude/orchestration/concurrent-safety.py"
    ".claude/skills/generic/"
    ".claude/skills/stack/"
    ".claude/skills/project/"
    ".claude/ui/"
    "docs/ARCHITECTURE-RISKS.md"
    "docs/TASK-WORKFLOW-DETERMINISTIC.md"
    "scripts/validate-agent-skills-improved.py"
    "scripts/validate-agent-skills.py"
    "scripts/add-skill-versioning.py"
)

for file in "${EXPORT_FILES[@]}"; do
    if [ -e "$file" ]; then
        echo "  ✓ $file"
    fi
done

echo
echo "═══════════════════════════════════════════════════════════════"
echo "Export summary:"
echo "  Version: $VERSION"
echo "  Commits: $(git log --oneline | wc -l)"
echo "  Status: Ready for GitHub publication"
echo "═══════════════════════════════════════════════════════════════"
echo
echo "Next steps:"
echo "  1. git tag -a v$VERSION -m 'Framework v$VERSION'"
echo "  2. git remote add github https://github.com/your-org/orchestration_framework"
echo "  3. git push github main --tags"
echo
