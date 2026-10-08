# AGENTS & SKILLS Registry

**Версия:** 1.0  
**Дата:** 2026-10-08  
**Статус:** Phase 1 Foundation (Active)

Реестр всех агентов, скиллов и инструментов доступных в этом workspace.

---

## 🎯 Phase 1 Foundation Skills (NEW)

### gj-task-docs
**Версия:** 1.0  
**Статус:** Active (Phase 1)  
**Назначение:** Обязательное документирование для каждой задачи

Регулирует создание трёх документов:
- `findings.md` (Phase 1: UNDERSTANDING) — что нужно делать
- `plan.md` (Phase 2: PLANNING) — подход и решение
- `summary.md` (Phase 5: VERIFICATION) — что было сделано

**Использование:**
```bash
# Автоматически срабатывает в Phase 1
orchestrate task create --key OPSOMN002-XXX
# → координатор запускает Phase 1 с gj-task-docs
# → создаётся findings.md
```

**Файл:** `.claude/skills/gj-task-docs/SKILL.md`

---

### gj-reviewer
**Версия:** 1.0  
**Статус:** Active (Phase 1)  
**Назначение:** Независимый код-ревью и проверка качества

Третий независимый агент, который:
- Читает diff и план (но НЕ писал код)
- Проверяет по фиксированному чек-листу
- Отправляет комментарии в MR ([MUST], [SHOULD], [NIT])
- Может заблокировать MR если найдёт [MUST] проблему

**Использование:**
```bash
# Параллельно с тестами в Phase 4 (TESTING)
orchestrate phase run testing \
  --agent gj-reviewer \
  --mr 1234
```

**Чек-лист:**
1. Correctness (правильность)
2. Tests (тестирование)
3. Performance (производительность)
4. Code Quality (качество кода)
5. API & Contracts (контракты)
6. Migration & Data (миграции)
7. Documentation (документация)
8. Integration (интеграции)

**Файл:** `.claude/skills/gj-reviewer/SKILL.md`

---

## 🔐 Hooks (Local Protection)

### guard_secrets
**Назначение:** Блокирует коммиты с паролями, ключами, токенами

**Срабатывает:** `git commit`

**Проверяет:**
- Passwords, API Keys, Tokens
- AWS/GCP/Azure credentials
- SSH Private Keys
- Database URLs with credentials
- GitHub/GitLab URLs with auth

**Действие:** Блокирует коммит + показывает рекомендации

**Файл:** `.claude/hooks/guard_secrets.py`

---

### comment_budget
**Назначение:** Предупреждает если слишком много комментариев в review

**Срабатывает:** После code review комментариев

**Бюджеты:**
- Bug fix: 5 комментариев
- Feature: 10 комментариев
- Refactor: 8 комментариев
- Docs: 3 комментария

**Действие:** Warn if exceeds + рекомендации для consolidation

**Файл:** `.claude/hooks/comment_budget.py`

---

## 🛠️ Existing Skills (from previous phases)

### data-driven-implementation
**Версия:** TBD  
**Статус:** Available (Phase 2)  
**Назначение:** Реализация изменений на основе реальных данных

Интегрирует Phase 3.5 (DATA-DRIVEN-VALIDATION).

**Файл:** `.claude/skills/data-driven-implementation/SKILL.md`

---

### data-driven-review
**Версия:** TBD  
**Статус:** Available (Phase 2)  
**Назначение:** Ревью с проверкой на реальных данных

**Файл:** `.claude/skills/data-driven-review/SKILL.md`

---

## 📋 Phase 1 Deliverables

### Completed ✅

- [x] **gj-task-docs skill** — документирование (findings, plan, summary)
- [x] **gj-reviewer skill** — независимый ревью (8-point checklist)
- [x] **guard_secrets hook** — защита от утечки секретов
- [x] **comment_budget hook** — контроль качества review'ов
- [x] **AGENTS.md registry** — реестр всех компонентов

### In Progress 🔄

- [ ] Merge MR !10 (ARCH-FIX-2026)
- [ ] Integration tests для hooks
- [ ] Documentation в README

### Pending ⏳

- [ ] Phase 2: Integrate skills в orchestration
- [ ] Phase 2: Live testing на реальных задачах

---

## 🔗 How to Use

### For Development

1. **Creating task:**
   ```bash
   orchestrate task create --key OPSOMN002-XXX
   ```

2. **Phase 1 (UNDERSTANDING):**
   - Автоматически использует `gj-task-docs`
   - Создаёт `findings.md`
   - Выход: `send-phase-complete understanding success`

3. **Phase 2 (PLANNING):**
   - Обновляет `gj-task-docs`
   - Создаёт `plan.md`
   - Выход: `send-phase-complete planning success`

4. **Phase 4 (TESTING):**
   - Запускает `gj-reviewer` параллельно с тестами
   - Отправляет комментарии в MR
   - Проверяет: нет ли [MUST] issues

5. **Phase 5 (VERIFICATION):**
   - Обновляет `summary.md`
   - Проверяет: MR merged, tests pass
   - Выход: `send-phase-complete verification success`

### For Review

```bash
# Manual review (вне orchestration)
# Claude Code: используй skill gj-reviewer

# Automatic review (в orchestration)
orchestrate phase run testing --agent gj-reviewer --mr 1234
```

### For Protection

```bash
# Pre-commit check
python3 .claude/hooks/guard_secrets.py

# Review quality check
python3 .claude/hooks/comment_budget.py \
  --mr 1234 \
  --comments 8 \
  --title "feat(basket): add promo"
```

---

## 📊 Metrics & Status

### Phase 1 Completion

| Component | Status | File | Tests |
|-----------|--------|------|-------|
| gj-task-docs | ✅ Complete | SKILL.md | Planned |
| gj-reviewer | ✅ Complete | SKILL.md | Planned |
| guard_secrets | ✅ Complete | .py | Manual |
| comment_budget | ✅ Complete | .py | Manual |
| AGENTS.md | ✅ Complete | this file | N/A |

### Timeline

- Week 1: Merge MR !10, Create gj-task-docs
- Week 2: Create gj-reviewer
- Week 3-4: Add hooks + integration
- Week 5-8: Phase 2 (Hybrid 10/10)

---

## 🚀 Next Steps

### Immediate (Week 1)

1. Merge MR !10 (ARCH-FIX-2026)
2. Test gj-task-docs with real task
3. Verify hooks work on local machine

### Short-term (Week 2-4)

1. Integrate gj-reviewer into Phase 4
2. Add hook handlers to orchestration
3. Live testing on 2-3 real tasks
4. Collect metrics and feedback

### Medium-term (Week 5-8)

1. Phase 2: Launch hybrid 10/10 system
2. Add worker-initiated messaging (Phase 3.5)
3. Enable parallel phase execution
4. Data-driven validation on all tasks

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-10-08 | Initial registry: Phase 1 skills + hooks + status |

---

## 📚 Related Documents

- `.claude/skills/gj-task-docs/SKILL.md` — Task documentation skill
- `.claude/skills/gj-reviewer/SKILL.md` — Code review skill
- `.claude/hooks/README.md` — Hooks documentation
- `.claude/orchestration/YAML` — Orchestration configuration (TBD)
- `docs/TASK-WORKFLOW-DETERMINISTIC.md` — Task phase definitions

---

## 🤝 Contributing

To add a new skill or agent:

1. Create folder: `.claude/skills/my-skill/`
2. Create `SKILL.md` with:
   - Версия, статус, назначение
   - Как использовать (примеры)
   - Чек-лист/правила
3. Update this `AGENTS.md`
4. Add to git + commit

Example:
```markdown
### my-skill
**Версия:** 1.0  
**Статус:** Active/Testing/Planned  
**Назначение:** What this skill does

Description and usage.

**Файл:** `.claude/skills/my-skill/SKILL.md`
```
