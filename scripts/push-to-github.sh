#!/bin/bash
# Push Orchestration Framework to GitHub
# Usage: ./scripts/push-to-github.sh

set -e

GITHUB_REPO="https://github.com/AntonovAleksandr/orchestration_framework"
TEMP_CLONE_DIR="/tmp/orchestration_framework_push_$$"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Orchestration Framework → GitHub Push"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Target: $GITHUB_REPO"
echo "Temp:   $TEMP_CLONE_DIR"
echo ""

# ============================================================================
# STEP 1: Clone Target Repository
# ============================================================================

echo "📥 Step 1: Cloning target repository..."
git clone "$GITHUB_REPO" "$TEMP_CLONE_DIR" 2>&1 | grep -v "^Cloning\|^Receiving\|Resolving\|Compressing"

cd "$TEMP_CLONE_DIR"

echo "   ✓ Cloned to $TEMP_CLONE_DIR"
echo ""

# ============================================================================
# STEP 2: Run Sanitized Export
# ============================================================================

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/orca/workspaces/development-platform/betta"

echo "📦 Step 2: Running sanitized export..."
echo "   Source: $SOURCE_DIR"
echo "   Target: $TEMP_CLONE_DIR"
echo ""

if [ ! -f "$SOURCE_DIR/scripts/export-orchestration-framework-clean.sh" ]; then
    echo "❌ Error: export script not found at $SOURCE_DIR/scripts/export-orchestration-framework-clean.sh"
    exit 1
fi

chmod +x "$SOURCE_DIR/scripts/export-orchestration-framework-clean.sh"
"$SOURCE_DIR/scripts/export-orchestration-framework-clean.sh" "$TEMP_CLONE_DIR"

echo ""

# ============================================================================
# STEP 3: Verify Sanitization
# ============================================================================

echo "🔒 Step 3: Verifying sanitization..."

if grep -r "gj-opsomn002\|gj-beauty\|OPSOMN002\|Gloria Jeans\|GJ-Ecommerce" "$TEMP_CLONE_DIR/.claude" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" > /dev/null; then
    echo "❌ ERROR: Project references found in exported files!"
    echo ""
    grep -r "gj-opsomn002\|gj-beauty\|OPSOMN002\|Gloria Jeans\|GJ-Ecommerce" "$TEMP_CLONE_DIR/.claude" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" | head -10
    echo ""
    echo "Cleanup required. Aborting push."
    exit 1
else
    echo "   ✓ No project references found"
fi

echo ""

# ============================================================================
# STEP 4: Commit Changes
# ============================================================================

echo "📝 Step 4: Committing changes..."

git add .

# Check if there are changes
if git diff --cached --quiet; then
    echo "   ℹ️  No changes to commit (framework already up-to-date)"
else
    git config user.name "Claude Haiku 4.5"
    git config user.email "noreply@anthropic.com"

    git commit -m "feat: orchestration framework from gj-ecommerce

Exported:
- Phase 1 Foundation: mandatory documentation + independent review
- Phase 2 Hybrid 10/10: async messaging, parallel phases, data-driven validation
- Phase 3 Architecture: (planned) state store, autonomous workers, cloud branches
- Generic engineering skills (Layer 3): always applicable
- Stack-specific skills (Layer 2): PHP/Swoole, Angular, Java, React Native, .NET
- Worker messaging system: atomic file-based coordination
- Risk assessment & mitigation strategies
- Skills taxonomy & registry (3-layer architecture)
- IDE compatibility adapters (Claude Code, Cursor, Codex, VSCode, JetBrains)
- Code standards & review guidelines

Excludes:
- Project-specific skills (gj-opsomn002, gj-beauty, etc)
- Local hooks (.gitignore)
- GJ-specific configurations

All project names and references sanitized [your-project] for public use.
Ready for import into other projects. See SANITIZATION_REPORT.md.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

    echo "   ✓ Committed"
fi

echo ""

# ============================================================================
# STEP 5: Push to GitHub
# ============================================================================

echo "🚀 Step 5: Pushing to GitHub..."

# Try to push with authentication
if git push origin main 2>&1; then
    echo "   ✓ Pushed to $GITHUB_REPO/main"
else
    echo ""
    echo "❌ Push failed. This might be due to:"
    echo "   - Authentication issues (SSH key or PAT not configured)"
    echo "   - Network connectivity"
    echo "   - Branch protection rules"
    echo ""
    echo "Manual push:"
    echo "   cd $TEMP_CLONE_DIR"
    echo "   git push origin main"
    exit 1
fi

echo ""

# ============================================================================
# STEP 6: Cleanup
# ============================================================================

echo "🧹 Step 6: Cleaning up temp directory..."

cd /
rm -rf "$TEMP_CLONE_DIR"

echo "   ✓ Cleaned up"
echo ""

# ============================================================================
# SUCCESS
# ============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Push Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 Repository: $GITHUB_REPO"
echo "🔗 Branch: main"
echo ""
echo "What was pushed:"
echo "  ✓ Phase 1-3 Orchestration system (sanitized)"
echo "  ✓ Generic engineering skills"
echo "  ✓ Stack-specific skills"
echo "  ✓ Worker messaging system (Python)"
echo "  ✓ Risk assessment & mitigation"
echo "  ✓ Skills taxonomy & registry"
echo "  ✓ IDE compatibility guide"
echo "  ✓ Code standards & rules"
echo ""
echo "What's NOT included (project-specific):"
echo "  ✗ gj-opsomn002, gj-beauty, etc skills"
echo "  ✗ Hooks (.gitignore)"
echo "  ✗ GJ-specific configs"
echo ""
echo "Next: Create project-specific skills in .claude/skills/project/[your-project]/"
echo ""
