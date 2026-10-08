---
name: ARCHITECTURE_DIAGRAM
version: 1.0.0
layer: project
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---

# Архитектура системы скилов: визуальное представление

## Диаграмма 1: Фазы выполнения и роли агентов

```mermaid
graph TD
    Start["📋 Требование<br/>(Jira Ticket)"]
    
    subgraph Phase0["PHASE 0: Инициализация (2 мин)"]
        Coord0["🎯 Координатор<br/>coord-task-orchestration"]
    end
    
    subgraph Phase1["PHASE 1: Research (25 мин) - ПАРАЛЛЕЛЬНО"]
        Conf["🔍 Conf-researcher<br/>research-confluence"]
        CodeENSI["🔍 Code-researcher ENSI<br/>research-code-ensi"]
        CodeOMS["🔍 Code-researcher OMS<br/>research-code-oms"]
        CodeInt["🔍 Code-researcher Intg<br/>research-code-integration"]
        Logs["🔍 Logs-detective<br/>research-logs"]
        BlackBox["🔍 Black-box<br/>research-blackbox"]
    end
    
    subgraph Phase2["PHASE 2: Analysis (5 мин)"]
        Analyst["📊 Аналитик<br/>analyze-synthesis<br/>analyze-requirements"]
    end
    
    subgraph Phase3["PHASE 3: Development (30-60 мин)"]
        Dev["💻 Разработчик<br/>develop-[platform]"]
    end
    
    subgraph Phase45["PHASE 4-5: Review (20 мин) - ПАРАЛЛЕЛЬНО"]
        Rev1["✅ Reviewer-1<br/>review-business<br/>review-architecture"]
        Rev2["✅ Reviewer-2<br/>review-security<br/>review-performance<br/>review-design"]
    end
    
    subgraph Phase67["PHASE 6-7: Merge + Metrics (5 мин)"]
        Coord7["🎯 Координатор<br/>coord-metrics<br/>coord-blockers"]
    end
    
    Start --> Phase0
    Phase0 --> Phase1
    
    Conf --> Analyst
    CodeENSI --> Analyst
    CodeOMS --> Analyst
    CodeInt --> Analyst
    Logs --> Analyst
    BlackBox --> Analyst
    
    Analyst --> Phase2
    Phase2 --> Dev
    Dev --> Phase45
    
    Dev --> Rev1
    Dev --> Rev2
    
    Rev1 --> Phase67
    Rev2 --> Phase67
    
    Phase67 --> End["✅ Merge + отчёт"]
    
    style Phase0 fill:#fff3cd
    style Phase1 fill:#cfe2ff
    style Phase2 fill:#d1ecf1
    style Phase3 fill:#d1e7dd
    style Phase45 fill:#e2e3e5
    style Phase67 fill:#d3d3ff
    style End fill:#d1e7dd
```

---

## Диаграмма 2: Граф зависимостей скилов

```mermaid
graph LR
    subgraph Shared["🔗 SHARED (используют все)"]
        MD["shared-claude-md<br/>reference"]
        SI["shared-service<br/>-index"]
        Buddy["shared-gj-buddy<br/>-mcp"]
        Git["shared-git<br/>-workflow"]
        Sec["shared-security<br/>-checklist"]
        Perf["shared-performance<br/>-basics"]
        Style["shared-code<br/>-style"]
    end
    
    subgraph Research["🔍 RESEARCH"]
        Conf["research-confluence"]
        CodeE["research-code-ensi"]
        CodeO["research-code-oms"]
        CodeI["research-code-integration"]
        Logs["research-logs"]
        BB["research-blackbox"]
    end
    
    subgraph Analysis["📊 ANALYSIS"]
        Syn["analyze-synthesis"]
        Req["analyze-requirements"]
        Blk["analyze-blockers"]
    end
    
    subgraph Development["💻 DEVELOPMENT"]
        DevE["develop-ensi"]
        DevO["develop-oms-java"]
        DevI["develop-integration"]
        DevS["develop-site"]
        DevM["develop-mobile"]
    end
    
    subgraph Review["✅ REVIEW"]
        Rev1["review-business<br/>-architecture"]
        Rev2["review-security<br/>-performance-design"]
        Chk["review-checklist<br/>-by-platform"]
    end
    
    subgraph Coordination["🎯 COORDINATION"]
        Orch["coord-task<br/>-orchestration"]
        Met["coord-metrics<br/>-collection"]
        BlkMgmt["coord-blocker<br/>-management"]
        Par["coord-parallel<br/>-execution"]
    end
    
    MD --> Conf
    SI --> Conf
    Buddy --> Conf
    
    MD --> CodeE
    SI --> CodeE
    
    MD --> CodeO
    SI --> CodeO
    
    MD --> CodeI
    SI --> CodeI
    
    Buddy --> Logs
    
    Buddy --> BB
    
    MD --> Syn
    SI --> Syn
    
    MD --> Req
    
    Buddy --> Blk
    
    Style --> DevE
    Sec --> DevE
    
    Style --> DevO
    Sec --> DevO
    
    Style --> DevI
    Sec --> DevI
    
    Style --> DevS
    Sec --> DevS
    
    Style --> DevM
    Sec --> DevM
    
    MD --> Rev1
    SI --> Rev1
    Chk --> Rev1
    
    Sec --> Rev2
    Perf --> Rev2
    Chk --> Rev2
    
    MD --> Orch
    SI --> Orch
    Buddy --> Orch
    
    Orch --> Met
    
    Buddy --> BlkMgmt
    
    Orch --> Par
    
    Conf -.->|выводы| Syn
    CodeE -.->|выводы| Syn
    CodeO -.->|выводы| Syn
    CodeI -.->|выводы| Syn
    Logs -.->|выводы| Syn
    BB -.->|выводы| Syn
    
    Syn -.->|постановка| DevE
    Syn -.->|постановка| DevO
    Syn -.->|постановка| DevI
    Syn -.->|постановка| DevS
    Syn -.->|постановка| DevM
    
    DevE -.->|дифф| Rev1
    DevE -.->|дифф| Rev2
    
    style Shared fill:#fff3cd,stroke:#ff9800
    style Research fill:#cfe2ff,stroke:#2196f3
    style Analysis fill:#d1ecf1,stroke:#17a2b8
    style Development fill:#d1e7dd,stroke:#28a745
    style Review fill:#e2e3e5,stroke:#6c757d
    style Coordination fill:#d3d3ff,stroke:#6f42c1
```

---

## Диаграмма 3: Поток данных между фазами (с циклическим ревью)

```mermaid
sequenceDiagram
    participant U as User
    participant Coord as Координатор
    participant R as Researchers (5)
    participant A as Аналитик
    participant D as Разработчик
    participant Rev1 as Reviewer-1
    participant Rev2 as Reviewer-2
    
    U->>Coord: Требование (Jira)
    Coord->>R: Запустить исследование (Phase 1)
    par Research
        R->>R: Conf, CodeE, CodeO, CodeI, Logs, BB<br/>параллельно (25 мин)
    end
    
    R->>A: 5 выводов исследователей
    A->>A: Синтез + валидация (5 мин)
    A->>Coord: [BLOCKER] вопрос?
    alt BLOCKER
        Coord->>U: Спросить уточнение
        U->>Coord: Ответ
        Coord->>A: Ответ
    end
    
    A->>D: Постановка (требование)
    Coord->>Rev1: Запустить ревью
    Coord->>Rev2: Запустить ревью
    
    par Development + Review
        D->>D: Написать код (30-60 мин)
        par Parallel Review (Iteration 1)
            Rev1->>Rev1: Ревью бизнес+архитектура (20 мин)
            Rev2->>Rev2: Ревью безопасность+перф+дизайн (20 мин)
        end
    end
    
    Note over Rev1,Rev2: ИТЕРАЦИЯ 1
    Rev1->>D: Замечания [MUST], [SHOULD], [NIT]
    Rev2->>D: Замечания [SECURITY], [PERF], [DESIGN]
    
    D->>D: Фиксить замечания (10 мин)
    D->>Rev1: Обновлённый MR
    D->>Rev2: Обновлённый MR
    
    alt Все замечания закрыты?
        Rev1->>Coord: Approved ✓
        Rev2->>Coord: Approved ✓
        Coord->>Coord: Merge (5 мин)
        Coord->>Coord: Собрать метрики
        Coord->>U: Отчёт + рекомендации
    else Есть новые замечания или не все fixed
        Rev1->>Rev1: Перепроверка (10 мин) — ИТЕРАЦИЯ 2
        Rev2->>Rev2: Перепроверка (10 мин)
        Rev1->>D: Новые/оставшиеся замечания
        Rev2->>D: Новые/оставшиеся замечания
        
        D->>D: Фиксить (5-10 мин)
        D->>Rev1: Обновлённый MR
        D->>Rev2: Обновлённый MR
        
        Rev1->>Coord: Approved ✓
        Rev2->>Coord: Approved ✓
        
        Coord->>Coord: Merge
        Coord->>U: Отчёт
    end
```

---

## Диаграмма 4: Параллелизм в Phase 1 (Research)

```mermaid
timeline
    title Параллельное исследование (Phase 1)
    
    section Conf-researcher
        t=0: Старт Confluence
        t=2: Читает ТЗ
        t=4: Читает AC
        t=5: Читает историю
        t=8: Выводы готовы
    
    section Code-researcher (ENSI)
        t=0: Старт кода ENSI
        t=5: Codegraph
        t=8: OpenAPI
        t=10: Выводы готовы
    
    section Code-researcher (OMS)
        t=0: Старт кода OMS
        t=6: BPMN процесс
        t=10: Handlers
        t=12: Выводы готовы
    
    section Code-researcher (Integration)
        t=0: Старт кода Integration
        t=4: Маршруты
        t=7: Контракты
        t=10: Выводы готовы
    
    section Logs-detective
        t=0: Старт логов
        t=5: Стенд запрос
        t=8: Лаг анализ
        t=10: Edge-case check
        t=15: Выводы готовы
    
    section Black-box-researcher
        t=0: Старт API
        t=3: Запросы на тест
        t=6: Ответы анализ
        t=8: Edge-cases
        t=12: Воспроизводимость
        t=15: Выводы готовы
```

→ **Итого: 25 мин (не 100 мин последовательно!)**

---

## Диаграмма 5: Параллелизм в Phase 4-5 (Review)

```mermaid
timeline
    title Параллельный ревью (Phase 4-5)
    
    section Reviewer-1 (Бизнес+Архитектура)
        t=0: Прочитать дифф
        t=5: AC проверка
        t=10: Архитектура
        t=15: Расширяемость
        t=20: Замечания готовы
    
    section Reviewer-2 (Security+Perf+Design)
        t=0: Прочитать дифф (параллельно!)
        t=5: Security check
        t=10: Performance check
        t=15: Design check
        t=20: Замечания готовы
    
    section Developer (параллельно)
        t=20: Видит замечания (обоих!)
        t=22: Фиксит [MUST]
        t=30: Пушит фиксы
        t=35: Перепроверка (Rev1+Rev2)
```

→ **Итого: 35 мин (не 60 мин последовательно!)**

---

## Диаграмма 6: Связность скилов — как они не теряются

```mermaid
graph TB
    Start["Требование (Jira)"]
    
    Start -->|Coord запускает| R1["research-confluence<br/>research-code-{e,o,i}<br/>research-logs<br/>research-blackbox"]
    
    R1 -->|Researchers используют| Shared1["shared-claude-md<br/>shared-service-index<br/>shared-gj-buddy-mcp"]
    
    R1 -->|Выводы идут к| Analyst["analyze-synthesis<br/>analyze-requirements<br/>analyze-blockers"]
    
    Analyst -->|Аналитик использует| Shared2["shared-claude-md<br/>shared-service-index"]
    
    Analyst -->|Если [BLOCKER]| Coord["coord-blocker<br/>-management"]
    
    Analyst -->|Постановка идёт к| Dev["develop-ensi<br/>develop-oms-java<br/>develop-integration<br/>develop-site<br/>develop-mobile"]
    
    Dev -->|Developer использует| Shared3["shared-code-style<br/>shared-security-checklist<br/>shared-performance-basics<br/>shared-git-workflow"]
    
    Dev -->|MR дифф идёт к| Rev["review-business<br/>-architecture<br/>+<br/>review-security<br/>-performance-design"]
    
    Rev -->|Reviewers используют| Shared4["shared-security-checklist<br/>shared-performance-basics<br/>review-checklist<br/>-by-platform"]
    
    Rev -->|Замечания идут к| Dev2["Developer фиксит"]
    
    Dev2 -->|Фиксы к| Rev2["Reviewers перепроверяют"]
    
    Rev2 -->|Approved| Coord2["coord-metrics<br/>-collection"]
    
    Coord2 -->|Отчёт| End["✅ Merge + Metrics"]
    
    style Start fill:#fff3cd
    style Shared1 fill:#ffe0b2
    style Shared2 fill:#ffe0b2
    style Shared3 fill:#ffe0b2
    style Shared4 fill:#ffe0b2
    style End fill:#d1e7dd
```

**Ключевой принцип:** 
- **Входит** → скилл загружается
- **Использует SHARED** → скилл опирается на общие скилы
- **Выводит** → информация передаётся следующему агенту
- **Не теряется** → каждый скилл явно загружается на нужную фазу

---

## Диаграмма 7: Разделение ролей — кто что делает

```mermaid
graph LR
    subgraph Roles["РОЛИ И СКИЛЫ"]
        Coord["🎯 КООРДИНАТОР<br/>----<br/>coord-task-orchestration<br/>coord-metrics-collection<br/>coord-blocker-management<br/>coord-parallel-execution<br/>shared-*"]
        
        Researchers["🔍 5 ИССЛЕДОВАТЕЛЕЙ<br/>----<br/>research-confluence<br/>research-code-ensi<br/>research-code-oms<br/>research-code-integration<br/>research-logs<br/>research-blackbox<br/>shared-*"]
        
        Analyst["📊 АНАЛИТИК<br/>----<br/>analyze-synthesis<br/>analyze-requirements<br/>analyze-blockers<br/>shared-*"]
        
        Developers["💻 РАЗРАБОТЧИКИ<br/>----<br/>develop-ensi<br/>develop-oms-java<br/>develop-oms-go<br/>develop-integration<br/>develop-site<br/>develop-mobile<br/>develop-gloriaots<br/>develop-go-new<br/>shared-*"]
        
        Reviewers["✅ 2 РЕВЬЮВЕРА<br/>----<br/>review-business-architecture<br/>review-security-performance<br/>review-checklist<br/>shared-*"]
        
        CI["⚙️ CI/АВТОМАТ<br/>----<br/>ESLint, Phpstan, SonarQube<br/>Prettier, gofmt<br/>(не скилы, но важны)"]
    end
    
    Coord -->|управляет| Researchers
    Researchers -->|выводы| Analyst
    Analyst -->|постановка| Developers
    Developers -->|дифф| Reviewers
    Reviewers -->|approved| Coord
    
    CI -.->|блокирует merge| Developers
    
    style Coord fill:#d3d3ff
    style Researchers fill:#cfe2ff
    style Analyst fill:#d1ecf1
    style Developers fill:#d1e7dd
    style Reviewers fill:#e2e3e5
    style CI fill:#f0f0f0
```

---

## Как проверить связность системы скилов?

### Checklist для валидации

- [ ] Каждый скилл явно указан в SKILLS_INDEX.md
- [ ] Каждый скилл разделён по роли ([RESEARCH], [DEVELOPMENT] и т.д.)
- [ ] Каждый скилл имеет "Входит", "Выходит", "Процесс", "Правила"
- [ ] Shared скилы используются всеми кто их нуждается
- [ ] Нет дублирования (один скилл = одно назначение)
- [ ] Граф зависимостей ацикличен (нет циклов в скилах)
- [ ] [BLOCKER] вопросы явно идут к Координатору
- [ ] [NB] вопросы не блокируют Development
- [ ] Ревьюеры не пишут код, только комментируют
- [ ] Разработчик не ревьюит себя
- [ ] Исследователи не пишут код
- [ ] Координатор не пишет код, только управляет
- [ ] Каждый агент получает нужный контекст (<20K токенов)

---

## Быстрая диаграмма: "Как запустить задачу"

```mermaid
flowchart LR
    Start["Требование"]
    
    Start -->|1. Coord запускает<br/>task-research-and-analyze| Phase1["Phase 1: Research<br/>25 мин"]
    
    Phase1 -->|2. Conf, Code×3,<br/>Logs, BB работают<br/>параллельно| Outputs["5 выводов"]
    
    Outputs -->|3. Analyst синтезирует| Phase2["Phase 2: Analysis<br/>5 мин"]
    
    Phase2 -->|4. Postановка<br/>или [BLOCKER]| Decision{Есть<br/>[BLOCKER]?}
    
    Decision -->|Да| Coord["Coord спрашивает<br/>человека"]
    Coord -->|Ответ| Phase2
    
    Decision -->|Нет| Phase3["Phase 3: Development<br/>30-60 мин"]
    
    Phase3 -->|5. Developer пишет| MR["MR готов"]
    
    MR -->|6. Запустить ревью| Phase45["Phase 4-5: Review<br/>20 мин параллельно"]
    
    Phase45 -->|7. Rev1 + Rev2| Comments["Замечания"]
    
    Comments -->|8. Developer фиксит| Dev2["Фиксы"]
    
    Dev2 -->|9. Перепроверка| Approved{Approved<br/>both?}
    
    Approved -->|Да| Phase67["Phase 6-7: Merge"]
    Approved -->|Нет| Dev2
    
    Phase67 -->|10. Coord merge| End["✅ Done"]
    
    style Start fill:#fff3cd
    style Phase1 fill:#cfe2ff
    style Phase2 fill:#d1ecf1
    style Phase3 fill:#d1e7dd
    style Phase45 fill:#e2e3e5
    style Phase67 fill:#d3d3ff
    style End fill:#d1e7dd
```

---

## Диаграмма 8: Циклический процесс ревью (ВАЖНО!)

```mermaid
graph TD
    Start["Developer запушил MR"]
    
    ReviewStart["🔄 ITERATION N<br/>Reviewer-1 + Reviewer-2<br/>оба смотрят параллельно"]
    
    FindComments["Находят замечания"]
    
    Counter{Есть замечания?}
    
    NoComments["❌ Нет замечаний<br/>→ Status: Approved ✓"]
    
    YesComments["✅ Да, есть замечания<br/>[MUST: X], [SHOULD: Y]"]
    
    DevFix["Developer фиксит замечания"]
    
    ResolveCycles{Все ревьюеры<br/>дали Approved?}
    
    NoApprove["❌ Нет, есть неolved<br/>→ Вернуться к Review Start"]
    
    AllApprove["✅ Да, ОБА Approved"]
    
    Merge["Merge в main/release"]
    
    Start --> ReviewStart
    ReviewStart --> FindComments
    FindComments --> Counter
    
    Counter -->|Нет| NoComments
    Counter -->|Да| YesComments
    
    YesComments --> DevFix
    DevFix -->|Pushes updated MR| ReviewStart
    
    NoComments --> ResolveCycles
    ResolveCycles -->|Нет| NoApprove
    NoApprove -->|Iteration + 1| ReviewStart
    ResolveCycles -->|Да| AllApprove
    
    AllApprove --> Merge
    Merge --> End["✅ Задача закрыта"]
    
    style ReviewStart fill:#cfe2ff
    style DevFix fill:#d1e7dd
    style Merge fill:#d1e7dd
    style End fill:#d1e7dd
```

**Ключевые моменты:**
- ♾️ **Цикл может повторяться 2-3 раза** (редко более)
- **Оба ревьюера должны дать Approved** перед merge
- Developer фиксит в цикле, не последовательно
- Каждая итерация: Review (20 мин) + Fix (10 мин) = 30 мин за цикл

---

## Диаграмма 9: Временная шкала с циклическим ревью

```mermaid
timeline
    title Реальный пример: 2 цикла ревью
    
    section Development
        t=0: Старт разработки (30-60 мин)
        t=45: Developer запушил MR
    
    section Review Iteration 1
        t=45: Rev1+Rev2 смотрят параллельно
        t=55: Rev1 готов → 8 замечаний
        t=58: Rev2 готов → 6 замечаний
    
    section Fix Iteration 1
        t=58: Developer видит замечания
        t=60: Фиксит [MUST] замечания
        t=68: Пушит обновлённый MR
    
    section Review Iteration 2
        t=68: Rev1+Rev2 перепроверяют
        t=73: Rev1 → 2 новых замечания (из фиксов)
        t=75: Rev2 → все ОК (Approved)
        t=78: Rev1 → Approved (замечания resolved)
    
    section Merge
        t=78: ОБА Approved → Merge
```

→ **Итого: 78 мин на ревью + фиксы (вместо 90+ если бы последовательно)**

---

**Диаграммы обновлены:** 2026-10-06  
**Версия:** 1.1 (добавлено циклическое ревью)  
**Ссылка на mermaid.live:** https://mermaid.live/ (копируй-вставляй диаграммы)
