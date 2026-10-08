# Architecture Risks & Prevention Strategies

**Date:** 2026-10-09  
**Status:** Preventive analysis for Phase 2+3  
**Score:** 8/10 architecture resilience

---

## 1. SKILLS VERSION COMPATIBILITY (Medium Risk → High if ignored)

### Problem
Skills can change but agents reference them by name only. No versioning.
```
Current:
Agent prompt → "Use: pattern-development-ensi"
Skill file → pattern-development-ensi.md (any version)
           ↓
Result: Silent breaking changes
```

### Why It Breaks
- Developer updates skill, breaks downstream agents
- No way to pin agent to specific skill version
- Framework export has no version guarantees

### Prevention (Do Now - 2 hours)
1. **Add skill frontmatter versioning:**
```yaml
---
name: pattern-development-ensi
version: 1.0.0
layer: generic
platforms: [ENSI, Site, OMS]
compatibility:
  framework: ">=1.0.0,<2.0.0"
  agents:
    - ensi-backend-engineer: ">=1.0"
    - ensi-navigator: ">=1.0"
deprecated: false
---
```

2. **CLI validates versions:**
```bash
claude-skills validate --check-compatibility
# Output: ✅ All agent→skill links valid
#         ⚠️  3 agents using deprecated skills
```

3. **Automatic agent prompts update:**
```bash
claude-skills sync-agents --dry-run
# Shows: Would update 5 agent prompts
```

---

## 2. WORKER STATE ISOLATION (High Risk)

### Problem
Workers write to `.tasks/` which is shared. Concurrent runs can collide.
```
Worker A: .tasks/phase-1.msg ← write (lock acquired)
Worker B: .tasks/phase-1.msg ← write (blocked!)
           ↓
Result: Deadlock or data loss
```

### Why It Breaks
- Two `orchestrate.sh task` calls use same `.tasks/` directory
- No run_id isolation
- fcntl locks don't work across machines (NFS, shared volumes)

### Prevention (Do Now - 1 hour)
1. **Add run_id to all state paths:**
```python
RUN_ID = uuid.uuid4()
msg_file = Path(f".tasks/{RUN_ID}/phase-{phase}.msg")
state_file = Path(f".tasks/{RUN_ID}/state.json")
```

2. **Namespace environment variables:**
```bash
export ORCA_RUN_ID=$(uuidgen)
orchestrate.sh task --run-id $ORCA_RUN_ID
```

3. **Garbage collection for old runs:**
```bash
# Auto-cleanup runs older than 30 days
find .tasks -type d -mtime +30 -exec rm -rf {} \;
```

---

## 3. PHASE CHECKPOINTS & RECOVERY (Medium Risk)

### Problem
If Phase 2 fails at hour 1.5/2, restarting loses progress.
```
Phase 1: Research (1 hour)     ✅ Complete
Phase 2: Analysis (2 hours)    ⚠️  FAILED at 1:30
         ↓ Restart
         ↓ Reruns from start (1 hour wasted)
Phase 3: Synthesis (1.5 hours) ❌ Never reached
```

### Why It Breaks
- No checkpoints within phases
- Resumption always starts from beginning
- Long phases (2-3 hours) → high failure cost

### Prevention (Do Now - 2 hours)
1. **Add checkpoints inside phases:**
```python
@checkpoint("phase-2/step-1-data-collection")
def collect_data():
    # If interrupted, resumes from here
    pass

@checkpoint("phase-2/step-2-analysis")
def analyze():
    pass
```

2. **Persist intermediate results:**
```
.tasks/{run_id}/
├── phase-1/
│   ├── checkpoint-1.json
│   ├── checkpoint-2.json
│   └── output.json ✅
├── phase-2/
│   ├── checkpoint-1.json
│   ├── checkpoint-2.json (failed here)
│   └── output.json (incomplete)
```

3. **Resume from checkpoint:**
```bash
orchestrate.sh resume --run-id $RUN_ID --from-checkpoint phase-2/checkpoint-2
```

---

## 4. AGENT PROMPT DRIFT (High Risk)

### Problem
Agent prompts reference skills that may be deleted or renamed.
```
Agent prompt says:  "Available: pattern-development-ensi, ..."
Skill file:        Doesn't exist (renamed to ensi-patterns)
                   ↓
Result: Agent references non-existent skill
```

### Why It Breaks
- Developers rename skills without updating agents
- No validation on what agents actually have
- Framework export includes broken references

### Prevention (Do Now - 1.5 hours)
1. **Build skill inventory from disk:**
```python
def validate_agent_skills():
    agents = glob(".claude/agents/*.md")
    skills = glob(".claude/skills/**/*.md")
    skill_names = {Path(f).stem for f in skills}
    
    for agent_file in agents:
        mentioned = extract_skill_names(agent_file)
        missing = mentioned - skill_names
        if missing:
            print(f"❌ {agent_file}: {missing} not found")
```

2. **CI check for broken references:**
```bash
# .gitlab-ci.yml
validate-skills:
  script:
    - python .claude/cli/validate-skills.py --strict
```

3. **Deprecation grace period:**
```yaml
# In skill frontmatter
deprecated: true
deprecation_date: 2026-11-01
replacement_skill: ensi-patterns
warning: "Use ensi-patterns instead (migration guide in docs/)"
```

---

## 5. IDE ADAPTER INCOMPATIBILITY (Medium Risk)

### Problem
Cursor adapter uses symlinks, but VSCode/JetBrains will use different mechanism.
```
Claude Code:  Native          (always works)
Cursor:       Symlinks        (works on POSIX)
VSCode:       ?? unknown      
JetBrains:    ?? unknown
Windows:      ⚠️  Symlinks don't work!
```

### Why It Breaks
- Cursor adapter breaks on Windows
- VSCode/JetBrains will have different rule loading
- Exported framework doesn't document IDE requirements

### Prevention (Do Now - 2 hours)
1. **Abstract IDE adapter interface:**
```python
class IDEAdapter(ABC):
    @abstractmethod
    def load_rules(self): pass
    
    @abstractmethod
    def load_skills(self): pass

class CursorAdapter(IDEAdapter):
    def load_rules(self):
        # Symlink strategy
        
class VSCodeAdapter(IDEAdapter):
    def load_rules(self):
        # settings.json strategy
```

2. **Auto-detect IDE and configure:**
```bash
orchestrate.sh init --detect-ide
# Detects: cursor (via .cursor/settings.json)
# Configures: Symlink adapter loaded
```

3. **Compatibility matrix in docs:**
```
IDE         | Platform | Status  | Adapter
------------|----------|---------|----------
Claude Code | All      | ✅      | Native
Cursor      | macOS    | ✅      | Symlink
Cursor      | Windows  | ❌      | Not supported
VSCode      | TBD      | 🚧      | Phase 3
JetBrains   | TBD      | 🚧      | Phase 3
```

---

## 6. DOCUMENTATION DRIFT (Medium Risk)

### Problem
Docs say X but code does Y. Framework users get confused.
```
PHASE2-QUICKSTART.md says:
  "Skills are in .claude/skills/"
  
Code:
  Skills are in .claude/skills/project/, .../stack/, .../generic/
  
Result: User follows docs, finds skills missing
```

### Why It Breaks
- Docs updated separately from code
- No continuous validation
- Exported framework docs may be stale

### Prevention (Do Now - 1.5 hours)
1. **Extract examples from actual code:**
```bash
# In PHASE2-QUICKSTART.md
## Skills Discovery

> **Auto-generated from .claude/cli/claude-skills.py**

Available commands:
\`\`\`bash
<!-- START claude-skills help -->
<!-- Auto-generated: claude-skills --help -->
<!-- END claude-skills help -->
\`\`\`
```

2. **CI validates doc examples work:**
```bash
# Extract code blocks, run them, verify output
./scripts/validate-doc-examples.sh PHASE2-QUICKSTART.md
```

3. **Version docs with releases:**
```
docs/
├── PHASE2-QUICKSTART.md (v1.0.0)
├── PHASE2-QUICKSTART.v1.0.0.md (archived)
└── README.md (links to versioned docs)
```

---

## 7. FRAMEWORK EXPORT VALIDATION (High Risk)

### Problem
Exported framework works in GJ but breaks in another project.
```
GJ Project:
  .claude/skills/project/  ← GJ-specific skills

Exported Framework:
  .claude/skills/generic/  ← Generic-only
  
Result: Other projects can't use project skills
         Framework docs reference non-existent files
```

### Why It Breaks
- Export process removes GJ references but may miss some
- No test in other project before release
- Users can't distinguish what's reusable

### Prevention (Do Now - 2 hours)
1. **Test export in separate directory:**
```bash
# Before pushing orchestration_framework to GitHub
./scripts/test-export.sh
# Creates /tmp/test-framework/, runs QUICKSTART
# Verifies: CLI works, skills load, example task runs
```

2. **Mark exported-only in skills:**
```yaml
---
name: pattern-development-flow
layer: generic
reusable: true  # ← Can be exported
export_notice: "This is part of the public framework"
---
```

3. **Release checklist:**
```markdown
## Before Exporting
- [ ] All GJ-specific skills moved to project/
- [ ] No hardcoded paths to /Users/user/...
- [ ] Test export runs in clean dir
- [ ] Docs reference only exported files
- [ ] Version number bumped
```

---

## 8. CONCURRENT ORCHESTRATION ISOLATION (High Risk)

### Problem
Two developers run orchestrations simultaneously → collisions.
```
Dev A: orchestrate.sh task --name analysis
Dev B: orchestrate.sh task --name analysis  (same name!)
       ↓
       Both write to .tasks/analysis/phase-*.msg
       Data corruption
```

### Why It Breaks
- No lock on task name
- Shared `.tasks/` directory
- No user/session isolation

### Prevention (Do Now - 1 hour)
1. **Enforce unique run IDs:**
```bash
RUN_ID="$(whoami)-$(date +%s)-$(uuidgen | head -c 8)"
orchestrate.sh task --run-id $RUN_ID
# run-id: aleksandr-1728470400-a1b2c3d4
```

2. **Task registry with locks:**
```python
# .tasks/registry.json
{
  "aleksandr-1728470400-a1b2c3d4": {
    "created": "2026-10-09T10:00:00Z",
    "status": "running",
    "phases": ["1", "2", "3"],
    "lock": true
  }
}
```

3. **Cleanup on exit:**
```bash
# Trap to release lock on Ctrl+C
trap 'orchestrate.sh release-lock --run-id $RUN_ID' EXIT
```

---

## 9. SKILL DEPRECATION STRATEGY (Medium Risk)

### Problem
Need to rename/delete skill but agents still use it.
```
Old skill: pattern-review-standard (8 agents)
New skill: code-review-8-point (better name)

How to migrate without breaking 8 agents?
```

### Why It Breaks
- No migration path
- Developers don't know about deprecation
- Exported framework has old references

### Prevention (Do Now - 1.5 hours)
1. **Deprecation timeline:**
```yaml
# Old skill
deprecated: true
deprecation_date: 2026-12-01
replacement_skill: code-review-8-point
migration_guide: "See docs/migration-v1-v2.md"
```

2. **Auto-migration script:**
```bash
./scripts/migrate-skill.sh pattern-review-standard code-review-8-point
# Updates: 8 agent prompts, registry, docs
```

3. **Deprecation warnings:**
```bash
claude-skills load --project gj-opsomn002
# ⚠️  3 deprecated skills used:
#     - pattern-review-standard → use code-review-8-point
#     Migration deadline: 2026-12-01
```

---

## 10. MONITORING & OBSERVABILITY (Medium Risk)

### Problem
Phase fails but no one knows why. Where's the log?
```
orchestrate.sh task --name analysis
# ... runs for 2 hours ...
# ❌ FAILED (error message?)
# Where to look? .tasks/run-id/phase-2.log?
```

### Why It Breaks
- No structured logging
- No trace aggregation
- Hard to debug in production
- Exported framework has no observability

### Prevention (Do Now - 2 hours)
1. **Structured logging from start:**
```python
import logging
import json

logger = logging.getLogger(__name__)
handler = logging.FileHandler(f".tasks/{RUN_ID}/phase-{phase}.log")
formatter = logging.Formatter('{"time": "%(asctime)s", "level": "%(levelname)s", "msg": "%(message)s"}')
handler.setFormatter(formatter)
logger.addHandler(handler)
```

2. **Log aggregation tool:**
```bash
orchestrate.sh logs --run-id $RUN_ID
# Shows: Phase 1 ✅ (00:45)
#        Phase 2 ⚠️  (timeout at 01:59)
#        Phase 3 ❌ (skipped)

orchestrate.sh logs --run-id $RUN_ID --phase 2 --tail 50
# Last 50 lines of phase 2 log
```

3. **Trace correlation:**
```
.tasks/{run_id}/traces.json
{
  "phase_1": {
    "start": "2026-10-09T10:00:00Z",
    "end": "2026-10-09T10:45:00Z",
    "status": "success",
    "output": "..."
  }
}
```

---

## Summary Table

| Risk | Severity | Effort | Impact | Priority |
|------|----------|--------|--------|----------|
| Skills version compatibility | High | 2h | Silent breaking changes | **P0** |
| Worker state isolation | High | 1h | Data loss/deadlock | **P0** |
| IDE adapter incompatibility | Medium | 2h | Windows/VSCode fail | **P1** |
| Agent prompt drift | High | 1.5h | Broken references | **P0** |
| Phase checkpoints | Medium | 2h | 1h+ lost on retry | **P1** |
| Documentation drift | Medium | 1.5h | User confusion | **P1** |
| Framework export validation | High | 2h | Broken in other projects | **P0** |
| Concurrent orchestration | High | 1h | Data corruption | **P0** |
| Skill deprecation | Medium | 1.5h | Orphaned code | **P1** |
| Observability | Medium | 2h | Debugging nightmare | **P1** |
| **TOTAL** | - | **17 hours** | - | - |

---

## Recommended Implementation Order

### TODAY (P0 - 5 hours)
1. ✅ Skills versioning (2h) → Framework export proof
2. ✅ Worker isolation (1h) → Concurrent run safety
3. ✅ Agent prompt validation (1.5h) → Drift detection
4. ✅ Concurrent orchestration (1h) → Run ID isolation

### THIS WEEK (P1 - 12 hours)
5. Phase checkpoints (2h) → Recovery capability
6. IDE adapter abstraction (2h) → Windows support
7. Documentation validation (1.5h) → Doc sync
8. Framework export testing (2h) → Quality gate
9. Skill deprecation policy (1.5h) → Lifecycle mgmt
10. Observability (2h) → Debugging support

---

## Next Steps

**Choose one:**

### Option A: Fix All P0 (5 hours) + P1 (12 hours) = 17 hours
→ Production-grade architecture (Phase 2.5)

### Option B: Fix P0 Only (5 hours)
→ Safe for production, P1 can wait

### Option C: Continue to Phase 3
→ P0 blocks handled, P1 deferred

**Recommendation:** Do P0 (5 hours) this week. This prevents data loss, corruption, and broken exports. Phase 3 can address P1 features.

---

**Author:** Architecture Review, 2026-10-09  
**Status:** Ready for implementation
