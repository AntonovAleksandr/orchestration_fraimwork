#!/bin/bash
# Export Orchestration Framework to Directory and Setup for GitHub Push
# Usage: ./scripts/export-and-setup.sh /path/to/local/repo [git-remote-url]

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 /path/to/orchestration_framework [https://github.com/user/repo.git]"
    echo ""
    echo "This script:"
    echo "  1. Exports sanitized framework to target directory"
    echo "  2. Initializes git (if needed)"
    echo "  3. Stages changes for commit"
    echo "  4. Shows what's ready to push"
    echo ""
    echo "Example:"
    echo "  mkdir ~/orchestration_framework"
    echo "  ./scripts/export-and-setup.sh ~/orchestration_framework"
    echo "  cd ~/orchestration_framework"
    echo "  git remote add origin https://github.com/user/repo.git"
    echo "  git push -u origin main"
    exit 1
fi

TARGET_DIR="$1"
GIT_REMOTE="${2:-}"

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Orchestration Framework Export & Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Source:      $SOURCE_DIR"
echo "Target:      $TARGET_DIR"
if [ -n "$GIT_REMOTE" ]; then
    echo "Git Remote:  $GIT_REMOTE"
fi
echo ""

# ============================================================================
# STEP 1: Create Target Directory
# ============================================================================

echo "📁 Step 1: Creating target directory..."

if [ -d "$TARGET_DIR" ]; then
    echo "   ✓ Directory exists: $TARGET_DIR"
else
    mkdir -p "$TARGET_DIR"
    echo "   ✓ Created: $TARGET_DIR"
fi

echo ""

# ============================================================================
# STEP 2: Initialize Git (if needed)
# ============================================================================

echo "🔧 Step 2: Initializing git repository..."

cd "$TARGET_DIR"

if [ -d ".git" ]; then
    echo "   ✓ Git repository already initialized"
else
    git init
    echo "   ✓ Initialized git repository"
fi

echo ""

# ============================================================================
# STEP 3: Add Git Remote (if provided)
# ============================================================================

if [ -n "$GIT_REMOTE" ]; then
    echo "🔗 Step 3: Adding git remote..."

    if git remote get-url origin > /dev/null 2>&1; then
        echo "   ✓ Remote already exists"
    else
        git remote add origin "$GIT_REMOTE"
        echo "   ✓ Added remote: $GIT_REMOTE"
    fi

    echo ""
fi

# ============================================================================
# STEP 4: Run Sanitized Export
# ============================================================================

echo "📦 Step 4: Exporting sanitized framework..."

if [ ! -f "$SOURCE_DIR/scripts/export-orchestration-framework-clean.sh" ]; then
    echo "❌ Error: export script not found"
    exit 1
fi

chmod +x "$SOURCE_DIR/scripts/export-orchestration-framework-clean.sh"
"$SOURCE_DIR/scripts/export-orchestration-framework-clean.sh" "$TARGET_DIR"

echo ""

# ============================================================================
# STEP 5: Verify Sanitization
# ============================================================================

echo "🔒 Step 5: Verifying sanitization..."

# Check for real project references (exclude placeholders like OPSOMN002-XXX)
if grep -r "gj-opsomn002\|gj-beauty\|Gloria Jeans\|GJ-Ecommerce" "$TARGET_DIR/.claude" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" > /dev/null; then
    echo "❌ ERROR: Project references found!"
    echo ""
    grep -r "gj-opsomn002\|gj-beauty\|Gloria Jeans\|GJ-Ecommerce" "$TARGET_DIR/.claude" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" | head -5
    exit 1
elif grep -r "OPSOMN002" "$TARGET_DIR/.claude" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" | grep -v "OPSOMN002-XXX" > /dev/null; then
    echo "❌ ERROR: Real OPSOMN002 references found!"
    echo ""
    grep -r "OPSOMN002" "$TARGET_DIR/.claude" 2>/dev/null | grep -v "SANITIZATION_REPORT.md" | grep -v "OPSOMN002-XXX" | head -5
    exit 1
else
    echo "   ✓ No real project references found (placeholders OK)"
fi

echo ""

# ============================================================================
# STEP 6: Create Initial README
# ============================================================================

echo "📝 Step 6: Creating initial README..."

cat > "$TARGET_DIR/README.md" << 'EOFREADME'
# Orchestration Framework

**Version:** 1.0
**Status:** Production-Ready (Phase 1-2)
**Purpose:** Reusable orchestration system for multi-agent agentic workflows

This framework enables structured multi-agent coordination across phases with mandatory documentation, independent review, async messaging, parallel execution, and data-driven validation.

## Quick Start

1. **Clone this repository**
2. **Customize for your project**
   - Create `.claude/skills/project/[your-project]/`
   - Update `.claude/skills/skills-registry.yaml`
3. **Load skills:** `claude-skills load --project your-project`
4. **Follow** `PHASE2-QUICKSTART.md` to begin

## What's Included

- **Phase 1:** Mandatory documentation + independent review + protection hooks
- **Phase 2:** Async messaging, parallel phases, data-driven validation
- **Phase 3:** (Planned) State store, autonomous workers, cloud branches
- **Generic Skills (Layer 3):** Always applicable across projects
- **Stack-Specific Skills (Layer 2):** PHP, Angular, Java, React Native, .NET
- **IDE Compatibility:** Claude Code, Cursor, Codex, VSCode, JetBrains
- **Framework Documentation:** Architecture, quick-start guides, risk assessment

## Documentation

- **PHASE2-QUICKSTART.md** — Step-by-step guide for implementing hybrid system
- **phase2-risk-assessment.md** — Known risks + mitigation strategies
- **SKILLS-TAXONOMY.md** — Understanding skills layering (3 layers)
- **SANITIZATION_REPORT.md** — What was sanitized for public use
- **IDE-COMPATIBILITY.md** — Supporting multiple IDEs

## Structure

```
.claude/
├── skills/
│   ├── gj-task-docs/           (Phase 1: documentation)
│   ├── gj-reviewer/            (Phase 1: code review)
│   ├── generic/                (Layer 3: universal skills)
│   ├── stack/                  (Layer 2: stack-specific)
│   ├── project/                (Layer 1: PROJECT-SPECIFIC — create per project)
│   └── SKILLS-TAXONOMY.md
│
├── orchestration/
│   ├── phase2-hybrid-integration.md
│   ├── worker-messaging.py
│   ├── PHASE2-QUICKSTART.md
│   └── phase2-risk-assessment.md
│
├── rules/                      (Code standards, review format, git workflow)
├── adapters/                   (IDE adapters)
└── IDE-COMPATIBILITY.md

scripts/
└── export-orchestration-framework-clean.sh
```

## Customization

### For Your Project

1. Create project-specific skills:
   ```bash
   mkdir -p .claude/skills/project/my-project
   # → Add my-project-task-docs/, my-project-workflow/, etc.
   ```

2. Update skills registry:
   ```yaml
   # .claude/skills/skills-registry.yaml
   projects:
     my-project:
       name: "My Project"
       skills:
         - my-project-task-docs
   ```

3. Load skills in agent prompts:
   ```markdown
   ## Available Skills
   - my-project-task-docs (Phase 1 documentation)
   - my-project-workflow (your workflow skill)
   ```

### For Your Stack

If using a tech stack not in Layer 2, create:
```bash
mkdir -p .claude/skills/stack/my-stack
```

## Integration

Use in your Claude Code, Cursor, or other IDE:

1. Copy framework into your project
2. Symlink rules (Cursor): `.cursor/rules/ → ../../.claude/rules/`
3. Load skills in agent system prompts
4. Follow phase guidelines from `PHASE2-QUICKSTART.md`

## Safety & Sanitization

This framework was exported from a production project and **sanitized** for public use:

- ✅ All project names replaced: `gj-opsomn002` → `[your-project]`
- ✅ All org names replaced: `Gloria Jeans` → `Your Organization`
- ✅ No project-specific configs included
- ✅ No hooks or credentials included

See `SANITIZATION_REPORT.md` for details. Before using, update placeholders with your actual project/org names.

## License

Same as source project. Use at your own risk; customize for your needs.

## Support

- Read `PHASE2-QUICKSTART.md` for step-by-step guidance
- Check `phase2-risk-assessment.md` for known issues
- Refer to `SKILLS-TAXONOMY.md` to understand skills layering

---

**Ready to begin?** Start with `PHASE2-QUICKSTART.md`.

EOFREADME

echo "   ✓ Created README.md"

echo ""

# ============================================================================
# STEP 7: Git Status
# ============================================================================

echo "📊 Step 7: Git status..."

cd "$TARGET_DIR"

git status

echo ""

# ============================================================================
# SUCCESS
# ============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Export & Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📁 Directory: $TARGET_DIR"
echo ""
echo "Next steps:"
if [ -z "$GIT_REMOTE" ]; then
    echo "  1. cd $TARGET_DIR"
    echo "  2. git remote add origin https://github.com/YOUR-USER/YOUR-REPO.git"
    echo "  3. git add ."
    echo "  4. git commit -m \"feat: initial orchestration framework\""
    echo "  5. git push -u origin main"
else
    echo "  1. cd $TARGET_DIR"
    echo "  2. git add ."
    echo "  3. git commit -m \"feat: initial orchestration framework\""
    echo "  4. git push -u origin main"
fi
echo ""
echo "After push:"
echo "  - Customize .claude/skills/project/[your-project]/"
echo "  - Update .claude/skills/skills-registry.yaml"
echo "  - Follow PHASE2-QUICKSTART.md"
echo ""
