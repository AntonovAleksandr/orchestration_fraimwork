#!/bin/bash
# .claude/scripts/verify-project-skills.sh
# Verify project skills structure and completeness
# Usage: verify-project-skills.sh [project-name]

set -e

SKILLS_DIR="./.claude/skills/PROJECT"
PROJECT_NAME="${1:}"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
ERRORS=0
WARNINGS=0
PASSED=0

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Project Skills Verification"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# If project name specified, verify only that one
if [ -n "$PROJECT_NAME" ]; then
    PROJECTS=("$PROJECT_NAME")
else
    PROJECTS=($(ls "$SKILLS_DIR" 2>/dev/null || echo ""))
    if [ ${#PROJECTS[@]} -eq 0 ]; then
        echo "No project skills found in $SKILLS_DIR"
        exit 0
    fi
fi

for PROJECT in "${PROJECTS[@]}"; do
    PROJECT_PATH="$SKILLS_DIR/$PROJECT"

    if [ ! -d "$PROJECT_PATH" ]; then
        echo -e "${RED}❌ Project not found: $PROJECT${NC}"
        ((ERRORS++))
        continue
    fi

    echo -e "${BLUE}📦 Checking: $PROJECT${NC}"

    # Check 1: SKILL.md exists
    if [ -f "$PROJECT_PATH/SKILL.md" ]; then
        echo -e "  ${GREEN}✅ SKILL.md exists${NC}"
        ((PASSED++))
    else
        echo -e "  ${RED}❌ SKILL.md missing${NC}"
        ((ERRORS++))
    fi

    # Check 2: SKILL.md has frontmatter
    if [ -f "$PROJECT_PATH/SKILL.md" ]; then
        if head -1 "$PROJECT_PATH/SKILL.md" | grep -q "^---"; then
            echo -e "  ${GREEN}✅ Frontmatter present${NC}"
            ((PASSED++))
        else
            echo -e "  ${RED}❌ Missing frontmatter (expected: ---)${NC}"
            ((ERRORS++))
        fi
    fi

    # Check 3: Required frontmatter fields
    REQUIRED_FIELDS=("name" "description" "version" "compatibility" "domain" "status")
    for FIELD in "${REQUIRED_FIELDS[@]}"; do
        if [ -f "$PROJECT_PATH/SKILL.md" ]; then
            if grep -q "^$FIELD:" "$PROJECT_PATH/SKILL.md"; then
                echo -e "  ${GREEN}✅ Field '$FIELD' present${NC}"
                ((PASSED++))
            else
                echo -e "  ${YELLOW}⚠️  Field '$FIELD' missing${NC}"
                ((WARNINGS++))
            fi
        fi
    done

    # Check 4: YAML config exists
    if [ -f "$PROJECT_PATH/${PROJECT}.yaml" ]; then
        echo -e "  ${GREEN}✅ ${PROJECT}.yaml exists${NC}"
        ((PASSED++))
    else
        echo -e "  ${YELLOW}⚠️  ${PROJECT}.yaml missing (optional)${NC}"
        ((WARNINGS++))
    fi

    # Check 5: Examples directory
    if [ -d "$PROJECT_PATH/examples" ]; then
        EXAMPLE_COUNT=$(find "$PROJECT_PATH/examples" -type f ! -name ".gitkeep" | wc -l)
        if [ "$EXAMPLE_COUNT" -gt 0 ]; then
            echo -e "  ${GREEN}✅ Examples present ($EXAMPLE_COUNT files)${NC}"
            ((PASSED++))
        else
            echo -e "  ${YELLOW}⚠️  Examples directory empty${NC}"
            ((WARNINGS++))
        fi
    else
        echo -e "  ${YELLOW}⚠️  Examples directory missing${NC}"
        ((WARNINGS++))
    fi

    # Check 6: SKILL.md content quality
    if [ -f "$PROJECT_PATH/SKILL.md" ]; then
        SECTIONS=("Problem Solved" "Architecture" "Error Handling" "Testing Strategy" "See Also")
        for SECTION in "${SECTIONS[@]}"; do
            if grep -q "^## $SECTION" "$PROJECT_PATH/SKILL.md"; then
                echo -e "  ${GREEN}✅ Section '## $SECTION' found${NC}"
                ((PASSED++))
            else
                echo -e "  ${YELLOW}⚠️  Section '## $SECTION' missing${NC}"
                ((WARNINGS++))
            fi
        done
    fi

    echo ""
done

# Summary
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Verification Summary"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo -e "  ${GREEN}✅ Passed:  $PASSED${NC}"
echo -e "  ${YELLOW}⚠️  Warnings: $WARNINGS${NC}"
echo -e "  ${RED}❌ Errors:   $ERRORS${NC}"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review SKILL.md and complete any TODO sections"
    echo "  2. Add examples to examples/ directory"
    echo "  3. Wire skill into agents: .claude/agents/<agent>.md"
    echo "  4. Test: .claude/scripts/validate-agent-skills.sh"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Fix errors before committing${NC}"
    echo ""
    echo "Issues to address:"
    [ $ERRORS -gt 0 ] && echo "  • $ERRORS critical errors found"
    [ $WARNINGS -gt 0 ] && echo "  • $WARNINGS warnings (non-blocking)"
    echo ""
    exit 1
fi
