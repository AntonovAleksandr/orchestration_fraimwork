# IDE Compatibility & Adapter Guide

**Версия:** 1.0  
**Статус:** Design Phase  
**Цель:** Поддержать работу orchestration framework в разных IDE (Claude Code, Cursor, Codex, etc)

---

## 🎯 Поддерживаемые IDE

| IDE | Status | Notes |
|-----|--------|-------|
| **Claude Code** | ✅ Full | Primary development environment |
| **Cursor** | ✅ Full | Symlink adapter (.cursor/rules) |
| **Codex** | 🔄 Partial | Via OpenAI API adapter |
| **VS Code** | 🔄 Partial | VSCode extensions support |
| **JetBrains** | ⏳ Planned | IntelliJ IDEA, PyCharm, etc |

---

## 🔌 Architecture: IDE-Agnostic Layers

```
┌────────────────────────────────────────────┐
│ IDE Layer (UI, shortcuts, integration)      │
├────────────────────────────────────────────┤
│ Adapter Layer (translate IDE → framework)   │
├────────────────────────────────────────────┤
│ Framework Layer (skills, rules, orchestration)
└────────────────────────────────────────────┘

Framework Layer = same for all IDEs
Adapter Layer = custom per IDE
```

---

## ✅ Claude Code (Default)

**Status:** Primary development environment  
**Setup:** No adapter needed

### Configuration

```yaml
# .claude/settings.json
{
  "ide": "claude-code",
  "hooks": {
    "pre-commit": ".claude/hooks/guard_secrets.py",
    "post-review": ".claude/hooks/comment_budget.py"
  },
  "skills_loader": "native"
}
```

### Usage

```bash
# Direct skill loading
claude-skills load --project gj-opsomn002

# Phase commands
orchestrate phase run understanding --task OPSOMN002-XXX

# Hooks work automatically
# → guard_secrets triggered on git commit
# → comment_budget triggered after review
```

### Keyboard Shortcuts (configurable)

```
Cmd+Shift+K    → Load orchestration console
Cmd+Shift+L    → List available skills
Cmd+Shift+P    → Phase command palette
```

---

## 🔗 Cursor (IDE Adapter)

**Status:** Fully supported via .cursor/rules symlinks  
**Setup:** Automatic (already in CLAUDE.md)

### How It Works

```
.claude/rules/
├── code-comments.md
├── code-review-comments-format.md
└── git-mr-workflow.md

↓ (symlink)

.cursor/rules/
├── code-comments.mdc → ../../.claude/rules/code-comments.md
├── code-review-comments-format.mdc → ...
└── git-mr-workflow.mdc → ...
```

### Cursor Configuration

```json
// .cursor/settings.json (auto-generated)
{
  "rulesFiles": [
    ".cursor/rules/code-comments.mdc",
    ".cursor/rules/code-review-comments-format.mdc",
    ".cursor/rules/git-mr-workflow.mdc"
  ],
  "skills": {
    "path": "../.claude/skills",
    "loader": "cursor-native"
  }
}
```

### Usage in Cursor

```
Cursor reads rules from .cursor/rules/
↓
Rules point to .claude/rules/ (single source of truth)
↓
All IDE-specific stuff in .cursor/, framework in .claude/

Benefits:
- One rule file to maintain
- Cursor gets latest rules automatically
- No duplication
```

---

## 🔮 Codex / OpenAI API Adapter

**Status:** Partial support via wrapper API  
**Setup:** Via adapter service

### How It Works

```
┌─────────────────────────────┐
│ Codex / OpenAI Client       │
└─────────────────────────────┘
              ↓
┌─────────────────────────────┐
│ Adapter Service             │
│ (translate requests)        │
└─────────────────────────────┘
              ↓
┌─────────────────────────────┐
│ Orchestration Framework     │
│ (.claude/ skills/rules)     │
└─────────────────────────────┘
```

### Adapter Implementation

```python
# .claude/adapters/codex_adapter.py

class CodexOrchestratedAdapter:
    """Translate Codex requests to orchestration framework"""
    
    def __init__(self, framework_path):
        self.framework = load_framework(framework_path)
    
    def handle_request(self, request):
        """
        request = {
            "model": "codex",
            "prompt": "create a test for function X",
            "ide": "codex",
            "project": "gj-opsomn002"
        }
        """
        # 1. Load project-specific skills
        skills = self.framework.load_skills(project=request["project"])
        
        # 2. Load generic skills
        skills.extend(self.framework.load_skills(layer="generic"))
        
        # 3. Create system prompt with skills + rules
        system_prompt = self.build_system_prompt(skills)
        
        # 4. Call Codex with augmented prompt
        response = codex.complete(
            prompt=request["prompt"],
            system_prompt=system_prompt
        )
        
        return response
    
    def build_system_prompt(self, skills):
        """Inject skills into Codex system prompt"""
        prompt = f"""
You are a code-generating agent using orchestration framework.

Project: {self.framework.current_project}

RULES:
{self.load_rules()}

SKILLS:
{self.load_skills_summary(skills)}

Guidelines:
- Follow code-review-comments-format.md
- Use test-driven-development skill
- Validate with data-driven-validation skill
"""
        return prompt
```

### Usage with Codex

```python
# Example: Using Codex with orchestration

from codex_adapter import CodexOrchestratedAdapter

adapter = CodexOrchestratedAdapter(
    framework_path=".claude"
)

response = adapter.handle_request({
    "model": "codex",
    "prompt": "write a test for calculatePrice function",
    "project": "gj-opsomn002"
})

# Codex now uses:
# ✓ project-specific skills
# ✓ generic skills
# ✓ orchestration rules
# ✓ code review standards
```

---

## 🆚 VS Code Extensions

**Status:** Partial support via VSCode extension  
**Setup:** Via marketplace (future)

### Extension Architecture

```
.vscode/settings.json
├── extensions.recommendations
│   └── "Claude Code", "Cursor", "Codex extension"
└── orchestration
    ├── frameworkPath: ".claude"
    ├── skillsLoader: "vscode-extension"
    └── hooksEnabled: true
```

### Supported Features

```
✓ Syntax highlighting for .mdc rules
✓ Skills discovery (Ctrl+Shift+S)
✓ Phase command palette
✓ Hook integration (pre-commit, post-review)
✗ Live orchestration (requires VSCode API extensions)
```

---

## 📋 JetBrains (Planned)

**Status:** Planned (future releases)  
**Framework:** ORCA SDK for JetBrains

### Roadmap

```
Phase 1: Read-only support
  ├─ Rules browser
  ├─ Skills discovery
  └─ Documentation viewer

Phase 2: Integration
  ├─ Phase command palette
  ├─ Hook support
  └─ Live skill loading

Phase 3: Full orchestration
  ├─ Autonomous phase execution
  ├─ Real-time metrics
  └─ Dashboard integration
```

---

## 🔄 Switching Between IDEs

### Scenario: Claude Code → Cursor

```bash
# 1. Clone repo
git clone <repo>

# 2. Setup is automatic!
#    - .cursor/rules/ symlinks already exist
#    - .claude/ framework ready
#    - settings.json in both places

# 3. Open in Cursor
cursor .

# 4. Start using skills
#    Cursor automatically loads from .claude/
```

### Scenario: Cursor → Codex

```bash
# 1. Install adapter
pip install orchestration-framework-codex-adapter

# 2. Configure Codex
export ORCHESTRATION_FRAMEWORK_PATH=.claude

# 3. Use adapter
from codex_adapter import CodexOrchestratedAdapter
adapter = CodexOrchestratedAdapter(".claude")

# 4. Make requests
response = adapter.handle_request({
    "prompt": "write tests",
    "project": "gj-opsomn002"
})
```

---

## 🛠️ Adapter File Structure

### Generic Adapter Interface

```python
# .claude/adapters/base_adapter.py

class OrchestratedAdapter(ABC):
    """Base class for IDE adapters"""
    
    @abstractmethod
    def load_skills(self, project=None, layer=None):
        """Load skills from framework"""
        pass
    
    @abstractmethod
    def load_rules(self):
        """Load rules from framework"""
        pass
    
    @abstractmethod
    def execute_phase(self, phase, task_key):
        """Execute orchestration phase"""
        pass
    
    @abstractmethod
    def handle_hooks(self, hook_type, context):
        """Handle pre-commit, post-review, etc"""
        pass
```

### IDE-Specific Adapters

```
.claude/adapters/
├── base_adapter.py           (abstract interface)
├── claude_code_adapter.py    (native)
├── cursor_adapter.py         (symlink-based)
├── codex_adapter.py          (API wrapper)
├── vscode_adapter.py         (extension wrapper)
└── jetbrains_adapter.py      (future)
```

---

## 📝 Configuration per IDE

### .claude/settings.json (Framework)

```json
{
  "framework_version": "1.0",
  "supported_ides": [
    "claude-code",
    "cursor",
    "codex",
    "vscode"
  ],
  "default_ide": "claude-code",
  "skills_path": ".claude/skills",
  "rules_path": ".claude/rules",
  "orchestration_path": ".claude/orchestration",
  "adapters_path": ".claude/adapters"
}
```

### .cursor/settings.json (Cursor Specific)

```json
{
  "ide": "cursor",
  "inherits_from": "../.claude/settings.json",
  "rules_symlink_prefix": "../../.claude/rules/",
  "skills_loader": "inherit-from-.claude",
  "hooks_enabled": true
}
```

### .vscode/settings.json (VSCode Specific)

```json
{
  "orchestration.frameworkPath": ".claude",
  "orchestration.adapter": "vscode-extension",
  "orchestration.skillsLoader": "vscode-discovery",
  "extensions.recommendations": [
    "anthropic.claude-code",
    "anysphere.cursor",
    "orchestration.framework"
  ]
}
```

---

## 🚀 Adding New IDE Support

### Step 1: Create Adapter Class

```python
# .claude/adapters/myide_adapter.py

from base_adapter import OrchestratedAdapter

class MyIDEAdapter(OrchestratedAdapter):
    def __init__(self, framework_path):
        self.framework = load_framework(framework_path)
    
    def load_skills(self, project=None, layer=None):
        # Implement skill loading
        pass
    
    def execute_phase(self, phase, task_key):
        # Implement phase execution
        pass
    
    # ... other methods
```

### Step 2: Register Adapter

```yaml
# .claude/skills/skills-registry.yaml

adapters:
  my-ide:
    name: "My IDE"
    adapter_class: "myide_adapter.MyIDEAdapter"
    supported_features:
      - load_skills: true
      - execute_phases: true
      - hooks: true
    status: "beta"
```

### Step 3: Test Integration

```bash
# Test that adapter works
pytest .claude/adapters/test_myide_adapter.py

# Verify it loads rules correctly
python -c "from myide_adapter import MyIDEAdapter; a = MyIDEAdapter('.claude'); print(a.load_rules())"
```

---

## 📊 IDE Support Matrix

| Feature | Claude Code | Cursor | Codex | VSCode | JetBrains |
|---------|-------------|--------|-------|--------|-----------|
| Load Skills | ✅ | ✅ | ✅ | ✅ | ⏳ |
| Load Rules | ✅ | ✅ | ✅ | ✅ | ⏳ |
| Execute Phases | ✅ | ⏳ | ⏳ | ⏳ | ❌ |
| Hooks (pre-commit) | ✅ | ✅ | ⏳ | ⏳ | ❌ |
| Live Dashboard | ✅ | ⏳ | ❌ | ⏳ | ⏳ |
| Command Palette | ✅ | ✅ | ⏳ | ✅ | ⏳ |

---

## 🔗 Key Principle

**Single Source of Truth:**

```
.claude/
├── skills/              ← Framework (IDE-agnostic)
├── rules/               ← Framework (IDE-agnostic)
├── orchestration/       ← Framework (IDE-agnostic)
└── adapters/            ← IDE-specific wrappers

.cursor/rules/ ──symlink→ ../../.claude/rules/
.vscode/settings.json ──reference→ .claude/settings.json
.codex/adapter.py ──inherits→ .claude/adapters/base_adapter.py

Benefit:
✅ Update rules once, all IDEs get the change
✅ Skills same everywhere
✅ Framework version-controlled, adapters version-controlled
```

---

## История

| Версия | Дата | Изменения |
|--------|------|----------|
| 1.0 | 2026-10-08 | Initial: IDE compatibility architecture + adapters for Claude Code, Cursor, Codex, VSCode, JetBrains |
