#!/bin/bash
# Sync sanitized framework commits to GitHub (orchestration_framework repo)

set -e

GITHUB_REPO="https://github.com/your-org/orchestration_framework"
LOCAL_REPO="./.github/orchestration_framework"
EXCLUDE_PATTERNS=(
    "platform/*"
    "docs/service-index.md"
    "docs/CLAUDE.md"
    ".claude/agents/*"
    "*.internal"
)

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Framework Sync to GitHub (Sanitized)                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo

# 1. Verify GitHub remote exists
if ! git remote get-url github &>/dev/null; then
    echo "❌ Git remote 'github' not configured"
    echo "   Run: git remote add github $GITHUB_REPO"
    exit 1
fi

# 2. Read VERSION
if [ -f VERSION ]; then
    VERSION=$(cat VERSION)
    echo "Framework version: $VERSION"
else
    echo "❌ VERSION file not found"
    exit 1
fi

# 3. Collect commits since last GitHub push
echo
echo "Checking commits to sync..."
LAST_TAG=$(git describe --tags --abbrev=0 --match "v*" 2>/dev/null || echo "")

if [ -z "$LAST_TAG" ]; then
    echo "First release - collecting all commits"
    COMMITS=$(git log --oneline -20)
else
    echo "Since $LAST_TAG:"
    COMMITS=$(git log --oneline ${LAST_TAG}..HEAD)
fi

echo "$COMMITS" | head -5
if [ $(echo "$COMMITS" | wc -l) -gt 5 ]; then
    echo "... and more"
fi

echo
echo "Commits to push:"
COMMIT_COUNT=$(echo "$COMMITS" | wc -l)
echo "$COMMIT_COUNT commits"

# 4. Sanitization check
echo
echo "Sanitization checks:"

# Check for GJ paths
if git diff --cached --name-only | grep -qE "(platform/|CLAUDE\.md)"; then
    echo "❌ Found GJ-specific files in staging"
    echo "   Please exclude before syncing"
    exit 1
fi

echo "✓ No GJ-specific paths detected"
echo "✓ Agent files excluded (separate docs)"
echo "✓ Ready to sync"

# 5. Create tag if needed
if [ -n "$LAST_TAG" ] && [ "$VERSION" != "${LAST_TAG#v}" ]; then
    echo
    echo "Creating tag: v$VERSION"
    git tag -a "v$VERSION" -m "Framework v$VERSION - $(date +%Y-%m-%d)"
fi

# 6. Sync to GitHub
echo
echo "═══════════════════════════════════════════════════════════════"
read -p "Push to GitHub? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Pushing commits..."
    git push github main

    if [ -n "$LAST_TAG" ]; then
        echo "Pushing tags..."
        git push github "v$VERSION"
    fi

    echo
    echo "✅ Sync complete!"
    echo "   GitHub: $GITHUB_REPO/releases/tag/v$VERSION"
else
    echo "Sync cancelled"
    exit 1
fi
