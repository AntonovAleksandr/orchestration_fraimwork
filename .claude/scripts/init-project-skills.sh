#!/bin/bash
# .claude/scripts/init-project-skills.sh
# Initialize project skills structure and questionnaire for new projects
# Usage: init-project-skills.sh <project-name>
# Example: init-project-skills.sh beauty-marking

set -e

PROJECT_NAME="${1:?Usage: init-project-skills.sh <project-name>}"
PROJECT_PATH="./.claude/skills/PROJECT/${PROJECT_NAME}"

# Validate
if [ -d "$PROJECT_PATH" ]; then
    echo "❌ Project already exists: $PROJECT_PATH"
    exit 1
fi

# Create structure
mkdir -p "$PROJECT_PATH/examples"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Project Skills Setup for: $PROJECT_NAME"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Interactive questionnaire
read -p "1️⃣  What does this project do? (one sentence): " PROJECT_DESC
read -p "2️⃣  Which platforms? (ensi/site/mobile/oms/integration/all): " PLATFORMS
read -p "3️⃣  Business domain? (orders/catalog/customers/payments/delivery/other): " DOMAIN
read -p "4️⃣  Tech stack? (php/typescript/java/go/dotnet/mixed): " TECH_STACK
read -p "5️⃣  Related systems? (comma-separated, e.g., ensi-catalog,oms-delivery): " RELATED_SYSTEMS
read -p "6️⃣  GitHub repo URL (optional): " GITHUB_REPO
read -p "7️⃣  Jira/Linear project key (optional): " PROJECT_KEY

# Create SKILL.md with frontmatter
cat > "$PROJECT_PATH/SKILL.md" << 'EOFSKILL'
---
name: PROJECT_NAME_PLACEHOLDER
description: PROJECT_DESC_PLACEHOLDER
version: 1.0.0
compatibility: ">=1.5.0,<3.0.0"
depends_on: []
platforms:
PLATFORMS_PLACEHOLDER
domain: DOMAIN_PLACEHOLDER
tech_stack:
TECH_STACK_PLACEHOLDER
related_systems:
RELATED_SYSTEMS_PLACEHOLDER
repository: GITHUB_REPO_PLACEHOLDER
project_key: PROJECT_KEY_PLACEHOLDER
status: development
created_at: DATE_PLACEHOLDER
authors:
  - You
---

# PROJECT_NAME_PLACEHOLDER

PROJECT_DESC_PLACEHOLDER

## Problem Solved

- What business problem does this project solve?
- Why is this project necessary?
- What are the success criteria?

## Key Concepts

### Concept 1
Description

### Concept 2
Description

## Architecture Overview

```
System flow diagram or ASCII art

Component A ─→ Component B ─→ Component C
   ↓
Component D
```

## System Integration Points

### Upstream Dependencies
What systems feed data into this project?

### Downstream Consumers
What systems depend on this project's output?

### External Integrations
Any third-party APIs or services?

## Data Model

Key entities and their relationships

## API / Contract

Key interfaces (if exposed):

- Endpoint 1: `POST /api/v1/resource`
- Endpoint 2: `GET /api/v1/resource/{id}`

## Error Handling Strategy

How are errors classified and handled?

- Recoverable errors:
- Escalatable errors:
- Fatal errors:

## Testing Strategy

- Unit tests:
- Integration tests:
- E2E tests:
- Load tests:

## Deployment Strategy

- Environments: development, staging, production
- Deployment method:
- Rollback procedure:
- Health checks:

## Monitoring & Observability

- Key metrics:
- Alerting rules:
- Log aggregation:
- Dashboard:

## Security Considerations

- Authentication:
- Authorization:
- Data protection:
- Audit logging:

## Performance Requirements

- Throughput:
- Latency:
- Scalability:
- Resource limits:

## When to Use This Skill

This skill is invoked when:

- Task type 1
- Task type 2
- Context: specific scenarios

## NOT for This Skill

When this skill should NOT be used:

- Anti-pattern 1
- Anti-pattern 2

## Examples

See the `examples/` directory for working code samples.

## Related Documentation

- Architecture Decision Records (ADRs)
- API specifications
- Database schema diagrams
- Deployment runbooks

## Troubleshooting

### Common Issue 1
**Symptom:** What happens when this breaks?
**Root Cause:** Why does it fail?
**Solution:** How to fix it

### Common Issue 2
**Symptom:**
**Root Cause:**
**Solution:**

## Glossary

- **Term 1:** Definition
- **Term 2:** Definition

## See Also

- Related skills
- Related documentation
- Related services

EOFSKILL

# Replace placeholders
sed -i "" "s|PROJECT_NAME_PLACEHOLDER|$PROJECT_NAME|g" "$PROJECT_PATH/SKILL.md"
sed -i "" "s|PROJECT_DESC_PLACEHOLDER|$PROJECT_DESC|g" "$PROJECT_PATH/SKILL.md"
sed -i "" "s|DOMAIN_PLACEHOLDER|$DOMAIN|g" "$PROJECT_PATH/SKILL.md"
sed -i "" "s|GITHUB_REPO_PLACEHOLDER|${GITHUB_REPO:-N/A}|g" "$PROJECT_PATH/SKILL.md"
sed -i "" "s|PROJECT_KEY_PLACEHOLDER|${PROJECT_KEY:-N/A}|g" "$PROJECT_PATH/SKILL.md"
sed -i "" "s|DATE_PLACEHOLDER|$(date -u +%Y-%m-%d)|g" "$PROJECT_PATH/SKILL.md"

# Replace lists
{
    for plat in $(echo "$PLATFORMS" | tr ',' ' '); do
        echo "  - $plat"
    done
} > /tmp/platforms.txt
sed -i "" "/PLATFORMS_PLACEHOLDER/{
    r /tmp/platforms.txt
    d
}" "$PROJECT_PATH/SKILL.md"

{
    for tech in $(echo "$TECH_STACK" | tr ',' ' '); do
        echo "  - $tech"
    done
} > /tmp/tech.txt
sed -i "" "/TECH_STACK_PLACEHOLDER/{
    r /tmp/tech.txt
    d
}" "$PROJECT_PATH/SKILL.md"

{
    for sys in $(echo "$RELATED_SYSTEMS" | tr ',' ' '); do
        [ -n "$sys" ] && echo "  - $sys"
    done
} > /tmp/systems.txt
sed -i "" "/RELATED_SYSTEMS_PLACEHOLDER/{
    r /tmp/systems.txt
    d
}" "$PROJECT_PATH/SKILL.md"

# Create project configuration
cat > "$PROJECT_PATH/${PROJECT_NAME}.yaml" << EOF
# $PROJECT_NAME Project Configuration

project:
  name: $PROJECT_NAME
  description: $PROJECT_DESC
  domain: $DOMAIN
  created: $(date -u +%Y-%m-%d)
  owner: # Your name
  status: development

platforms:
$(for plat in $(echo "$PLATFORMS" | tr ',' ' '); do echo "  - $plat"; done)

tech_stack:
  languages:
$(for tech in $(echo "$TECH_STACK" | tr ',' ' '); do echo "    - $tech"; done)
  frameworks: []
  databases: []
  messaging: []

integrations:
  external_systems: []
  internal_systems:
$(for sys in $(echo "$RELATED_SYSTEMS" | tr ',' ' '); do [ -n "$sys" ] && echo "    - $sys"; done)

github:
  repository: ${GITHUB_REPO:-N/A}
  branch: main

project_management:
  jira_key: ${PROJECT_KEY:-N/A}
  board_url: # Link to board

stakeholders:
  business_owner:
    name: # Name
    email: # Email
  technical_lead:
    name: # Name
    email: # Email

requirements:
  availability: 99.9%  # SLA target
  throughput: # requests/sec
  latency_p99: # milliseconds
  data_retention: # days

checklist:
  architecture:
    - [ ] System architecture documented
    - [ ] Components identified
    - [ ] Data flow defined

  contracts:
    - [ ] API specs written
    - [ ] Kafka topic contracts defined
    - [ ] Database schema documented

  quality:
    - [ ] Error handling strategy
    - [ ] Testing strategy (unit, integration, e2e)
    - [ ] Code review checklist

  operations:
    - [ ] Deployment plan
    - [ ] Rollback procedure
    - [ ] Health check endpoints
    - [ ] Monitoring & alerting

  security:
    - [ ] Security review completed
    - [ ] Authentication designed
    - [ ] Authorization designed
    - [ ] Secrets management

  documentation:
    - [ ] README written
    - [ ] API documentation
    - [ ] Architecture diagrams
    - [ ] Runbooks

notes: |
  Add any additional context here about the project.
EOF

# Create examples directory
cat > "$PROJECT_PATH/examples/README.md" << EOF
# $PROJECT_NAME Examples

## Example 1: Basic Usage

\`\`\`python
# Code example
\`\`\`

**Explanation:**
What does this example show?

## Example 2: Error Handling

\`\`\`python
# Error handling example
\`\`\`

**Explanation:**
Common error scenarios and how to handle them.

## Example 3: Integration

\`\`\`python
# Integration example
\`\`\`

**Explanation:**
How to integrate with other systems.

## Example 4: Testing

\`\`\`python
# Test example
\`\`\`

**Explanation:**
How to test this component.
EOF

# Create .gitkeep for tracking
touch "$PROJECT_PATH/examples/.gitkeep"

# Success message
echo ""
echo "✅ Project skill structure created!"
echo ""
echo "📁 Location: $PROJECT_PATH"
echo ""
echo "📝 Next steps:"
echo "  1. Edit SKILL.md with detailed documentation"
echo "  2. Edit ${PROJECT_NAME}.yaml with configuration"
echo "  3. Add examples to examples/"
echo "  4. Run: .claude/scripts/verify-project-skills.sh $PROJECT_NAME"
echo "  5. Integrate with agents in .claude/agents/"
echo ""
echo "🔍 Verify structure:"
echo "  ls -la $PROJECT_PATH/"
echo ""
echo "💾 Stage for git:"
echo "  git add .claude/skills/PROJECT/$PROJECT_NAME/"
echo ""
