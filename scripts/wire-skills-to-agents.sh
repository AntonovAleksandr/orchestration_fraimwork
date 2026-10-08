#!/bin/bash
# Wire all skills to their corresponding agents
# This script updates each agent's prompt with available skills

set -e

cd /Users/user/orca/workspaces/development-platform/betta

echo "🔌 WIRING SKILLS TO AGENTS"
echo "========================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Define skill mappings for each agent
declare -A AGENT_SKILLS

# ARCHITECT AGENTS - need patterns + architecture skills
AGENT_SKILLS["architect.md"]="pattern-analysis-synthesis.md,pattern-development-flow.md,architect-skills.md"
AGENT_SKILLS["ensi-architect.md"]="pattern-development-ensi.md,pattern-analysis-synthesis.md,pattern-review-standard.md"
AGENT_SKILLS["integration-architect.md"]="pattern-development-integration.md,pattern-analysis-synthesis.md"
AGENT_SKILLS["camunda-bpm-engineer.md"]="pattern-development-flow.md,pattern-review-standard.md"
AGENT_SKILLS["corporate-architect.md"]="pattern-analysis-synthesis.md,architect-skills.md"
AGENT_SKILLS["data-analytics-architect.md"]="pattern-development-flow.md,architect-skills.md"
AGENT_SKILLS["devops-architect.md"]="pattern-development-flow.md,architect-skills.md"

# ENGINEER AGENTS - need domain patterns + development + review
AGENT_SKILLS["ensi-backend-engineer.md"]="pattern-development-ensi.md,pattern-development-flow.md,pattern-review-standard.md,gj-reviewer.md,test-driven-development.md,data-driven-validation.md"
AGENT_SKILLS["integration-engineer.md"]="pattern-development-integration.md,pattern-development-flow.md,pattern-review-standard.md,gj-reviewer.md"
AGENT_SKILLS["site-engineer.md"]="develop-site-ui.md,develop-site-state.md,develop-site-routing.md,develop-site-ssr.md,develop-site-i18n.md,develop-site-testing.md,pattern-development-flow.md,pattern-review-standard.md,gj-reviewer.md"
AGENT_SKILLS["mobile-engineer.md"]="pattern-development-mobile.md,pattern-development-flow.md,pattern-review-standard.md,gj-reviewer.md,test-driven-development.md"
AGENT_SKILLS["oms-java-engineer.md"]="pattern-development-oms.md,pattern-development-flow.md,pattern-review-standard.md,gj-reviewer.md,test-driven-development.md"
AGENT_SKILLS["gloriaots-engineer.md"]="develop-gloriaots-applications.md,develop-gloriaots-database.md,develop-gloriaots-infrastructure.md,develop-gloriaots-testing.md,develop-gloriaots-workers.md,pattern-review-standard.md,gj-reviewer.md"
AGENT_SKILLS["go-service-engineer.md"]="pattern-development-go.md,pattern-development-flow.md,pattern-review-standard.md,gj-reviewer.md,test-driven-development.md"
AGENT_SKILLS["go-library-engineer.md"]="pattern-development-go.md,pattern-development-flow.md,pattern-review-standard.md,gj-reviewer.md,test-driven-development.md"
AGENT_SKILLS["go-api-contract-engineer.md"]="pattern-development-go.md,pattern-review-standard.md,gj-reviewer.md"
AGENT_SKILLS["go-test-engineer.md"]="pattern-development-go.md,test-driven-development.md,gj-reviewer.md"

# RESEARCHER AGENTS - need research + discovery patterns
AGENT_SKILLS["ensi-researcher.md"]="pattern-research-discovery.md,pattern-analysis-synthesis.md"
AGENT_SKILLS["integration-researcher.md"]="pattern-research-discovery.md,pattern-analysis-synthesis.md"
AGENT_SKILLS["site-researcher.md"]="pattern-research-discovery.md,pattern-analysis-synthesis.md"
AGENT_SKILLS["mobile-researcher.md"]="pattern-research-discovery.md,pattern-analysis-synthesis.md"
AGENT_SKILLS["oms-researcher.md"]="pattern-research-discovery.md,pattern-analysis-synthesis.md"
AGENT_SKILLS["gloriaots-researcher.md"]="pattern-research-discovery.md,pattern-analysis-synthesis.md"
AGENT_SKILLS["go-debugger.md"]="pattern-research-discovery.md,systematic-debugging.md"
AGENT_SKILLS["go-code-reviewer.md"]="pattern-review-standard.md,gj-reviewer.md"
AGENT_SKILLS["logs-detective.md"]="pattern-research-discovery.md,systematic-debugging.md"

# NAVIGATOR AGENTS - need research + discovery
AGENT_SKILLS["ensi-navigator.md"]="pattern-research-discovery.md"
AGENT_SKILLS["integration-navigator.md"]="pattern-research-discovery.md"
AGENT_SKILLS["site-navigator.md"]="pattern-research-discovery.md"
AGENT_SKILLS["mobile-navigator.md"]="pattern-research-discovery.md"
AGENT_SKILLS["oms-navigator.md"]="pattern-research-discovery.md"
AGENT_SKILLS["gloriaots-navigator.md"]="pattern-research-discovery.md"
AGENT_SKILLS["gitlab-investigator.md"]="pattern-research-discovery.md"

# Function to add skills section to agent
add_skills_section() {
    local agent_file="$1"
    local skills="$2"

    # Convert comma-separated skills to markdown list
    local skills_list=$(echo "$skills" | tr ',' '\n' | sed 's/^/- /' | sed "s/\.md//g")

    # Check if agent already has Available Skills section
    if grep -q "## Available Skills" "$agent_file"; then
        echo -e "${BLUE}ℹ️  ${agent_file}: Already has Available Skills section${NC}"
        return
    fi

    # Find a good place to insert - before "Verification" or "Anti-patterns" section
    # If not found, add before the last section

    # Create temp file with inserted skills section
    local temp_file="${agent_file}.tmp"

    # Look for common insertion points
    if grep -q "## Verification" "$agent_file"; then
        # Insert before Verification
        sed "/^## Verification/i\\
\\
## Available Skills\\
\\
$skills_list\\
" "$agent_file" > "$temp_file"
    elif grep -q "## Anti-patterns" "$agent_file"; then
        # Insert before Anti-patterns
        sed "/^## Anti-patterns/i\\
\\
## Available Skills\\
\\
$skills_list\\
" "$agent_file" > "$temp_file"
    else
        # Append at end of file
        echo "" >> "$agent_file"
        echo "## Available Skills" >> "$agent_file"
        echo "" >> "$agent_file"
        echo "$skills_list" >> "$agent_file"
        return
    fi

    mv "$temp_file" "$agent_file"
}

# Process each agent
count=0
updated=0

for agent_file in .claude/agents/*.md; do
    agent_name=$(basename "$agent_file")
    ((count++))

    # Check if we have skills mapped for this agent
    if [[ -v AGENT_SKILLS["$agent_name"] ]]; then
        skills="${AGENT_SKILLS[$agent_name]}"
        echo -e "${GREEN}✓${NC} $agent_name"
        echo "  Skills: $(echo $skills | tr ',' ' ' | sed 's/.md//g')"
        add_skills_section "$agent_file" "$skills"
        ((updated++))
    else
        echo "⚠️  $agent_name (no skills mapped - will add generic skills)"
        # Add generic skills to all agents
        generic_skills="gj-reviewer.md,test-driven-development.md,data-driven-validation.md"
        add_skills_section "$agent_file" "$generic_skills"
        ((updated++))
    fi
done

echo ""
echo "========================="
echo -e "${GREEN}✅ WIRING COMPLETE${NC}"
echo "========================="
echo ""
echo "Summary:"
echo "  Total agents: $count"
echo "  Updated: $updated"
echo ""
echo "Next step:"
echo "  1. Review changes in .claude/agents/*.md"
echo "  2. Test that agents can reference skills"
echo "  3. Commit: 'fix: wire all skills to agents'"
echo ""
