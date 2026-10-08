# Orchestration Framework Export

**Версия:** 1.0  
**Дата:** 2026-10-08  
**Цель:** Дублировать систему оркестрации в отдельный репозиторий для переиспользования

---

## 🎯 Что экспортируется

### ✅ Включено (Reusable)

```
.claude/skills/
├── gj-task-docs/               (Phase 1: mandatory documentation)
├── gj-reviewer/                (Phase 1: code review)
├── generic/                    (Layer 3: 7 universal skills)
│   ├── test-driven-development/
│   ├── data-driven-validation/
│   ├── systematic-debugging/
│   ├── performance-optimization/
│   ├── security-best-practices/
│   └── documentation-standards/
├── stack/                      (Layer 2: stack-specific)
│   ├── php-swoole/
│   ├── angular-20/
│   ├── java-spring-boot/
│   ├── react-native-074/
│   └── dotnet-10/
└── SKILLS-TAXONOMY.md

.claude/orchestration/
├── phase2-hybrid-integration.md
├── worker-messaging.py
├── PHASE2-QUICKSTART.md
├── phase2-risk-assessment.md
└── [другие файлы]

.claude/rules/
├── code-comments.md
├── code-review-comments-format.md
├── git-mr-workflow.md
└── [другие правила]

scripts/
└── export-orchestration-framework.sh
```

### ❌ Исключено (Project-Specific)

```
.claude/skills/project/
├── gj-opsomn002/               ← ИСКЛЮЧЕНО
├── gj-beauty/                  ← ИСКЛЮЧЕНО
└── [другие проекты]            ← ИСКЛЮЧЕНО

.claude/hooks/                  ← ИСКЛЮЧЕНО (локально, .gitignore)

[Все project-specific конфиги]  ← ИСКЛЮЧЕНО
```

---

## 🚀 Как Экспортировать

### Шаг 1: Запустить скрипт экспорта

```bash
# В GJ-Ecommerce репозитории:
cd /Users/user/orca/workspaces/development-platform/betta

# Экспортировать в orchestration_framework репо:
./scripts/export-orchestration-framework.sh /path/to/orchestration_framework
```

### Шаг 2: Проверить экспортированные файлы

```bash
cd /path/to/orchestration_framework

# Проверить структуру:
ls -la .claude/skills/
ls -la .claude/orchestration/
ls -la .claude/rules/

# Проверить скрипт:
ls -la scripts/
```

### Шаг 3: Добавить в git

```bash
# Добавить все файлы
git add .

# Создать коммит
git commit -m "feat: add orchestration framework from gj-ecommerce

Exported:
- Phase 1-3 orchestration system
- Generic engineering skills (Layer 3)
- Stack-specific skills (Layer 2)
- Worker messaging system
- Risk assessment & documentation
- Skills taxonomy & registry

Excludes:
- Project-specific skills (to be created per project)
- Local hooks (.gitignore)

Ready to use in other projects. See ORCHESTRATION_FRAMEWORK.md"

# Push
git push origin main
```

---

## 📥 Как Использовать в Новом Проекте

### Вариант 1: Клонировать Фреймворк

```bash
# Создать новый проект
mkdir my-project
cd my-project
git init

# Добавить orchestration framework как submodule
git submodule add https://github.com/AntonovAleksandr/orchestration_framework .claude-framework

# Или просто скопировать файлы
cp -r orchestration_framework/.claude ./
```

### Вариант 2: Запустить Скрипт в Новом Проекте

```bash
# Если скрипт есть в submodule:
./.claude-framework/scripts/export-orchestration-framework.sh $(pwd)

# Или скопировать скрипт:
cp orchestration_framework/scripts/export-orchestration-framework.sh ./scripts/
./scripts/export-orchestration-framework.sh $(pwd)
```

### Вариант 3: Ручное Копирование

```bash
# Копировать основные папки
cp -r orchestration_framework/.claude ./
cp -r orchestration_framework/scripts ./

# Это даст вам всё кроме project-specific skills
# которые нужно создать отдельно
```

---

## ✅ Создание Project-Specific Skills

После экспорта нужно добавить ваши project-specific skills:

### Структура

```
.claude/skills/project/
└── your-project/
    ├── your-task-docs/SKILL.md
    ├── your-workflow/SKILL.md
    └── your-architecture/SKILL.md
```

### Пример: your-task-docs

```markdown
# your-task-docs Skill

Версия: 1.0  
Статус: Active  
Назначение: Mandatory task documentation for your project

## Phases

- Phase 1 (UNDERSTANDING): findings.md
- Phase 2 (PLANNING): plan.md
- Phase 5 (VERIFICATION): summary.md

## Templates

### findings.md

- Problem Statement
- Sources Found
- Key Findings
- Edge Cases
- Open Questions

### plan.md

- Approach
- Detailed Plan (step by step)
- Edge Cases & Mitigations
- Success Criteria

### summary.md

- What Was Done
- Results
- Learnings
- Metrics
- Recommendations
```

---

## 🔄 Обновление Фреймворка

Если в основном репозитории (gj-ecommerce) обновлена система оркестрации:

### Способ 1: Переэкспортировать

```bash
# В GJ-Ecommerce:
./scripts/export-orchestration-framework.sh /path/to/orchestration_framework

# Это перезапишет файлы (но не project-specific skills)
```

### Способ 2: Git Merge (если submodule)

```bash
cd .claude-framework
git pull origin main
cd ..
git add .claude-framework/
git commit -m "chore: update orchestration framework to latest"
```

### Способ 3: Ручное Обновление

Скопировать только обновлённые файлы.

---

## 📊 Что Получишь

После экспорта у тебя будет:

### ✅ Phase 1: Foundation
- gj-task-docs (документирование)
- gj-reviewer (code review)
- Правила и standards

### ✅ Phase 2: Hybrid System (Week 5-8)
- Worker-messaging система
- Async фазы (3.5 ∥ 4)
- Data-driven validation
- Risk assessment

### ✅ Phase 3: Architecture (Week 9-26)
- State store patterns
- Autonomous workers
- Cloud branches
- Dashboard & monitoring

### ✅ Generic Skills (все проекты)
- TDD workflow
- Debugging methodology
- Performance optimization
- Security practices
- Documentation standards

### ✅ Stack-Specific Skills
- PHP/Swoole patterns
- Angular testing
- Java conventions
- React Native patterns
- .NET best practices

---

## 🎯 Быстрый Старт

```bash
# 1. Экспортировать framework:
./scripts/export-orchestration-framework.sh /path/to/orchestration_framework

# 2. Создать project-specific skills:
mkdir .claude/skills/project/my-project
# → добавить свои скилы

# 3. Обновить skills-registry.yaml:
# → добавить ваш проект

# 4. Загрузить skills:
# claude-skills load --project my-project

# 5. Запустить фазы:
# Follow PHASE2-QUICKSTART.md
```

---

## 📋 Чек-Лист для Нового Проекта

- [ ] Экспортировать framework
- [ ] Создать .claude/skills/project/[your-project]/
- [ ] Создать [your-project]-task-docs skill
- [ ] Обновить skills-registry.yaml
- [ ] Добавить в git
- [ ] Следовать PHASE2-QUICKSTART.md
- [ ] Запустить первую пилотную задачу (Week 5)
- [ ] Собрать метрики (Week 8)

---

## 🔗 Ссылки

- **ORCHESTRATION_FRAMEWORK.md**: Описание фреймворка
- **PHASE2-QUICKSTART.md**: Пошаговый гайд (неделя 5-8)
- **phase2-risk-assessment.md**: 6 критических рисков
- **SKILLS-TAXONOMY.md**: 3-слойная архитектура скилов
- **skills-registry.yaml**: Реестр всех скилов

---

## 🤝 Контрибьютинг

Если нашёл ошибку или улучшение в фреймворке:

1. Fix в своём проекте
2. Скопировать fix обратно в orchestration_framework
3. Submit PR в orchestration_framework репо

Это улучшит фреймворк для других!

---

## ⚠️ Важно

1. **Project-specific skills** нужно создавать для каждого проекта
2. **Hooks** локальные (.gitignore) — создать самостоятельно
3. **Фреймворк** предоставляет структуру и лучшие практики
4. **Настройка** под ваш проект обязательна

---

## 📞 Вопросы?

Смотри:
- `ORCHESTRATION_FRAMEWORK.md` в экспортированном репо
- `PHASE2-QUICKSTART.md` для деталей
- `phase2-risk-assessment.md` для known issues
- `SKILLS-TAXONOMY.md` для понимания архитектуры

---

**Status:** Ready for Export ✅

Фреймворк полностью готов к дублированию в отдельный репозиторий!
