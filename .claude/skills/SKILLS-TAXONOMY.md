# Skills Taxonomy & Layering

**Версия:** 1.0  
**Статус:** Design Phase  
**Цель:** Разделить скилы на слои для переиспользования при смене проекта/стека

---

## 📊 Трёхслойная архитектура

```
┌────────────────────────────────────────────────┐
│ PROJECT-SPECIFIC SKILLS (Проектные)            │
│ ├─ gj-task-docs (OPSOMN002 tasks)             │
│ ├─ beauty-pdp-flow                            │
│ ├─ checkout-integration                       │
│ └─ [новый проект] → новые скилы               │
├────────────────────────────────────────────────┤
│ STACK-SPECIFIC SKILLS (Стек-специфические)    │
│ ├─ PHP/Laravel: ensi-php-conventions          │
│ ├─ Angular: site-angular-testing              │
│ ├─ React Native: mobile-rn-patterns           │
│ ├─ Java: oms-spring-boot-conventions          │
│ └─ .NET: gloriaots-csharp-conventions         │
├────────────────────────────────────────────────┤
│ GENERIC ENGINEERING SKILLS (Общие)            │
│ ├─ test-driven-development                    │
│ ├─ systematic-debugging                       │
│ ├─ code-review (gj-reviewer)                  │
│ ├─ performance-optimization                   │
│ ├─ security-checklist                         │
│ └─ documentation-best-practices               │
└────────────────────────────────────────────────┘
```

---

## 🎯 Layer 1: PROJECT-SPECIFIC SKILLS

**Когда менять:** При смене проекта/задачи  
**Когда переиспользовать:** Внутри одного проекта  
**Примеры:**

```yaml
gj-task-docs:
  level: PROJECT
  for_projects:
    - OPSOMN002-XXX
    - OPSOMN002-YYY
  description: "Mandatory task documentation (findings/plan/summary)"
  templates:
    - findings.md (project-specific sections)
    - plan.md (with gj-specific architecture)
    - summary.md (with OPSOMN metrics)

beauty-pdp-product-workflow:
  level: PROJECT
  for_projects:
    - BEAUTY-302
    - BEAUTY-334
  description: "PDP product flow: assortment → swatches → carousel"
  dependencies:
    - gj-reviewer (generic)
    - site-angular-testing (stack)

checkout-integration-flow:
  level: PROJECT
  for_projects:
    - OPSOMN002-46
    - OPSOMN002-239
  description: "Express delivery checkout integration (OMS/Integration/Site)"
  dependencies:
    - data-driven-validation (generic)
    - site-angular-testing (stack)
    - oms-java-patterns (stack)
```

**Как структурировать:**

```
.claude/skills/
├── project/
│   ├── gj-opsomn002/          ← все OPSOMN002 скилы
│   │   ├── gj-task-docs/
│   │   ├─ opsomn002-checkout-flow/
│   │   └── opsomn002-architecture/
│   │
│   ├── gj-beauty/              ← все BEAUTY скилы
│   │   ├── beauty-pdp-flow/
│   │   ├── beauty-assortment/
│   │   └── beauty-marking/
│   │
│   └── [новый-проект]/
│       └── [проектные-скилы]/
```

---

## 🔧 Layer 2: STACK-SPECIFIC SKILLS

**Когда менять:** При смене технологического стека  
**Когда переиспользовать:** Все проекты на этом стеке  
**Примеры:**

```yaml
# PHP/Laravel Stack
ensi-php-conventions:
  level: STACK
  stacks: [php-swoole, php-fpm]
  description: "PHP code style, patterns, best practices"
  covers:
    - Classes, namespaces, autoloading
    - Error handling, exceptions
    - Testing with PHPUnit/Pest
    - Performance patterns

site-angular-testing:
  level: STACK
  stacks: [angular-20, nx-monorepo]
  description: "Angular testing patterns for site"
  covers:
    - Jest unit tests
    - Cypress e2e tests
    - NgRx state testing
    - Component testing

mobile-rn-patterns:
  level: STACK
  stacks: [react-native-0.74]
  description: "React Native development patterns for mobile"
  covers:
    - Navigation patterns
    - State management (Redux)
    - Native modules (iOS/Android)
    - Performance optimization

oms-spring-boot-conventions:
  level: STACK
  stacks: [java-spring-boot]
  description: "Spring Boot conventions for OMS"
  covers:
    - Controllers, services, repositories
    - JPA/Hibernate patterns
    - Testing with Mockito/JUnit5
    - Performance tuning

gloriaots-csharp-conventions:
  level: STACK
  stacks: [dotnet-10, aspnet-core]
  description: ".NET conventions for Gloria OTS"
  covers:
    - DDD patterns in C#
    - EF Core migrations
    - Async/await patterns
    - Testing with xUnit/Moq
```

**Как структурировать:**

```
.claude/skills/
├── stack/
│   ├── php-swoole/            ← все PHP/Swoole скилы
│   │   ├── ensi-php-conventions/
│   │   ├── integration-php-testing/
│   │   └── ensi-performance/
│   │
│   ├── angular-20/             ← все Angular скилы
│   │   ├── site-angular-testing/
│   │   ├── site-ngrx-patterns/
│   │   └── site-ssr-debugging/
│   │
│   ├── react-native-074/      ← все RN скилы
│   │   ├── mobile-rn-patterns/
│   │   ├── mobile-navigation/
│   │   └── mobile-native-modules/
│   │
│   ├── java-spring-boot/      ← все Java скилы
│   │   ├── oms-spring-boot-conventions/
│   │   ├── oms-jpa-patterns/
│   │   └── oms-testing/
│   │
│   └── dotnet-10/             ← все .NET скилы
│       ├── gloriaots-csharp-conventions/
│       ├── gloriaots-ef-core/
│       └── gloriaots-async-patterns/
```

---

## 🏗️ Layer 3: GENERIC ENGINEERING SKILLS

**Когда менять:** Редко (только если меняется методология)  
**Когда переиспользовать:** ВСЕ проекты, ВСЕ стеки  
**Примеры:**

```yaml
# Core Engineering Practices
gj-reviewer:
  level: GENERIC
  applies_to: all_projects
  applies_to_stacks: all
  description: "Independent code review with 8-point checklist"
  reusable: 100%

test-driven-development:
  level: GENERIC
  applies_to: all_projects
  applies_to_stacks: all
  description: "TDD workflow: red → green → refactor"
  covers:
    - Unit test patterns
    - Integration test setup
    - Test isolation
    - Mocking strategies

systematic-debugging:
  level: GENERIC
  applies_to: all_projects
  applies_to_stacks: all
  description: "Debugging workflow: hypothesis → test → validate"
  covers:
    - Logging strategy
    - Breakpoint debugging
    - Trace analysis
    - Root cause identification

data-driven-development:
  level: GENERIC
  applies_to: all_projects
  applies_to_stacks: all
  description: "Test code on real data before merge"
  covers:
    - Stage database access
    - Query writing
    - Result validation
    - Edge case testing

performance-optimization:
  level: GENERIC
  applies_to: all_projects
  applies_to_stacks: all
  description: "Identify and fix performance issues"
  covers:
    - N+1 queries
    - Memory leaks
    - Algorithm optimization
    - Caching strategies

security-checklist:
  level: GENERIC
  applies_to: all_projects
  applies_to_stacks: all
  description: "Security best practices"
  covers:
    - Input validation
    - SQL injection prevention
    - XSS prevention
    - CSRF protection
    - Secret management

documentation-best-practices:
  level: GENERIC
  applies_to: all_projects
  applies_to_stacks: all
  description: "Code documentation standards"
  covers:
    - Docstrings
    - API documentation
    - README structure
    - Architecture docs
```

**Как структурировать:**

```
.claude/skills/
├── generic/
│   ├── gj-reviewer/                    ← code review (all projects)
│   ├── test-driven-development/        ← TDD (all stacks)
│   ├── systematic-debugging/           ← debugging (all)
│   ├── data-driven-validation/         ← real data testing (all)
│   ├── performance-optimization/       ← perf (all)
│   ├── security-best-practices/        ← security (all)
│   └── documentation-standards/        ← docs (all)
```

---

## 📋 Usage Examples

### Сценарий 1: Меняю Проект (OPSOMN002 → BEAUTY)

```
Было:
├─ project/gj-opsomn002/gj-task-docs/
├─ project/gj-opsomn002/opsomn002-checkout-flow/
├─ stack/php-swoole/ensi-php-conventions/
├─ stack/angular-20/site-angular-testing/
└─ generic/gj-reviewer/ (переиспользуется)

Меняю:
├─ project/gj-opsomn002/ ← ОТКЛЮЧИТЬ
├─ project/gj-beauty/ ← ВКЛЮЧИТЬ (новые скилы!)
├─ stack/php-swoole/ (переиспользуется)
├─ stack/angular-20/ (переиспользуется)
└─ generic/ (переиспользуется)

Время: 5 минут (просто swap project/ папку)
```

### Сценарий 2: Меняю Стек (Angular → React)

```
Было:
├─ project/gj-opsomn002/ (переиспользуется)
├─ stack/angular-20/site-angular-testing/
└─ generic/ (переиспользуется)

Меняю:
├─ project/gj-opsomn002/ (переиспользуется)
├─ stack/react-18/ ← НОВЫЕ скилы!
│  ├─ site-react-testing/
│  ├─ site-redux-patterns/
│  └─ site-ssr-react/
└─ generic/ (переиспользуется)

Время: 10 минут (load new stack/ skills)
```

### Сценарий 3: Гибридный Проект (OPSOMN002 + несколько стеков)

```
.claude/agents/architect-opsomn002.md:
  skills:
    - gj-task-docs              (project/gj-opsomn002)
    - opsomn002-checkout-flow   (project/gj-opsomn002)
    - ensi-php-conventions      (stack/php-swoole)
    - site-angular-testing      (stack/angular-20)
    - oms-spring-boot           (stack/java-spring-boot)
    - gj-reviewer               (generic)
    - data-driven-validation    (generic)
```

---

## 🔄 Load Mechanism

### Idea: Skills Registry (YAML или JSON)

```yaml
# .claude/skills-registry.yaml

projects:
  gj-opsomn002:
    skills:
      - gj-task-docs
      - opsomn002-checkout-flow
      - opsomn002-architecture
    depends_on_stacks:
      - php-swoole
      - angular-20
      - java-spring-boot
  
  gj-beauty:
    skills:
      - beauty-pdp-flow
      - beauty-assortment
      - beauty-marking
    depends_on_stacks:
      - php-swoole
      - angular-20

stacks:
  php-swoole:
    skills:
      - ensi-php-conventions
      - integration-php-testing
      - ensi-performance
  
  angular-20:
    skills:
      - site-angular-testing
      - site-ngrx-patterns
      - site-ssr-debugging
  
  java-spring-boot:
    skills:
      - oms-spring-boot-conventions
      - oms-jpa-patterns
      - oms-testing

generic:
  skills:
    - gj-reviewer
    - test-driven-development
    - systematic-debugging
    - data-driven-validation
    - performance-optimization
    - security-best-practices
    - documentation-standards
```

### Как Использовать

```bash
# Load для проекта
claude-skills load --project gj-opsomn002
# → Автоматически загружает:
#   - project/gj-opsomn002/* ✓
#   - stack/php-swoole/* ✓
#   - stack/angular-20/* ✓
#   - stack/java-spring-boot/* ✓
#   - generic/* ✓

# Load для стека
claude-skills load --stack angular-20
# → Загружает:
#   - stack/angular-20/* ✓
#   - generic/* ✓

# Load конкретных скилов
claude-skills load gj-task-docs gj-reviewer site-angular-testing
```

---

## 📈 Структура на Диске

```
.claude/skills/
├── SKILLS-TAXONOMY.md              ← этот файл (документация)
├── skills-registry.yaml            ← реестр всех скилов (metadata)
│
├── project/                        ←層 1: Проектные
│   ├── gj-opsomn002/
│   │   ├── gj-task-docs/SKILL.md
│   │   ├── opsomn002-checkout-flow/SKILL.md
│   │   └── opsomn002-architecture/SKILL.md
│   │
│   ├── gj-beauty/
│   │   ├── beauty-pdp-flow/SKILL.md
│   │   ├── beauty-assortment/SKILL.md
│   │   └── beauty-marking/SKILL.md
│   │
│   └── [future-project]/
│       └── [project-skills]/
│
├── stack/                          ←層 2: Стек-специфические
│   ├── php-swoole/
│   │   ├── ensi-php-conventions/SKILL.md
│   │   ├── integration-php-testing/SKILL.md
│   │   └── ensi-performance/SKILL.md
│   │
│   ├── angular-20/
│   │   ├── site-angular-testing/SKILL.md
│   │   ├── site-ngrx-patterns/SKILL.md
│   │   └── site-ssr-debugging/SKILL.md
│   │
│   ├── react-native-074/
│   │   ├── mobile-rn-patterns/SKILL.md
│   │   └── mobile-navigation/SKILL.md
│   │
│   ├── java-spring-boot/
│   │   ├── oms-spring-boot-conventions/SKILL.md
│   │   └── oms-jpa-patterns/SKILL.md
│   │
│   └── dotnet-10/
│       └── gloriaots-csharp-conventions/SKILL.md
│
└── generic/                        ←層 3: Общие инженерные
    ├── gj-reviewer/SKILL.md
    ├── test-driven-development/SKILL.md
    ├── systematic-debugging/SKILL.md
    ├── data-driven-validation/SKILL.md
    ├── performance-optimization/SKILL.md
    ├── security-best-practices/SKILL.md
    └── documentation-standards/SKILL.md
```

---

## 🎯 Benefits of This Structure

| Преимущество | Результат |
|-------------|----------|
| **Modular** | Легко add/remove скилы |
| **Reusable** | Generic skills используются везде |
| **Maintainable** | Stack skills in one place |
| **Scalable** | New projects → new project/ folder |
| **Flexible** | Mix and match как нужно |

---

## 🚀 Migration Plan (Implement This)

### Phase 1: Taxonomy (Week 1)
- [ ] Create SKILLS-TAXONOMY.md (this file)
- [ ] Create skills-registry.yaml
- [ ] Classify existing skills:
  - [ ] gj-task-docs → project/gj-opsomn002/
  - [ ] gj-reviewer → generic/
  - [ ] data-driven-* → generic/

### Phase 2: Reorganize (Week 2)
- [ ] Create folder structure:
  - [ ] .claude/skills/project/
  - [ ] .claude/skills/stack/
  - [ ] .claude/skills/generic/
- [ ] Move existing skills to new locations
- [ ] Update AGENTS.md with new paths

### Phase 3: Registry (Week 3)
- [ ] Implement skills-registry.yaml
- [ ] Create claude-skills CLI tool
- [ ] Test load mechanisms

### Phase 4: Documentation (Week 4)
- [ ] Document per layer (what, when, why)
- [ ] Add templates for new skills
- [ ] Update onboarding guide

---

## История

| Версия | Дата | Изменения |
|--------|------|----------|
| 1.0 | 2026-10-08 | Initial: 3-layer taxonomy with examples, structure, and migration plan |
