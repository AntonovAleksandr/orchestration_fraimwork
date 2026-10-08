---
name: SKILL
version: 1.0.0
layer: codegraph-usage
platform: Generic
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# codegraph — code intelligence + index maintenance

Codegraph = SQLite knowledge graph всех символов/рёбер/файлов. Читается за <1мс, индекс отстаёт от правок ~1с через file-watcher. Консультироваться **до** написания/правки кода.

## Специфика этого workspace (ВАЖНО)

- **Индексирован только `platform/mobile-app/gj-app`** (`.codegraph/` есть только там). Остальные платформы (ensi, starfish24, site, integration, gloriaots, …) НЕ проиндексированы — codegraph по ним не работает, используй Grep/Read или заведи индекс (`codegraph init <path>`).
- **MCP-сервер запущен как `codegraph serve --mcp` без `--path`** → tools падают с `No CodeGraph project is loaded`. **Обходить: передавать `projectPath` в КАЖДЫЙ `mcp__codegraph__*` вызов:**
  `projectPath: "/Users/user/StudioProjects/gj/development-platform/platform/mobile-app/gj-app"`
- CLI: `/opt/homebrew/bin/codegraph` (в PATH как `codegraph`).

## MCP-инструменты (приоритет использования)

Отвечай **напрямую** — не делегируй разведку в саб-агента и не устраивай grep+read цикл; codegraph это уже готовый индекс.

- **`codegraph_explore`** — ПЕРВЫЙ и обычно ЕДИНСТВЕННЫЙ вызов. «как работает X», архитектура, баг, где/что X, обзор области. Возвращает verbatim-исходник релевантных символов по файлам (Read-эквивалент — не переоткрывай показанные файлы). Query = NL-вопрос ИЛИ набор имён символов/файлов.
- **`codegraph_search`** — быстрый поиск символа по имени (только локации, без кода). Когда нужно найти точное имя.
- **`codegraph_node`** — ОДИН символ целиком (сигнатура, тело при `includeCode:true`, трейл callers/callees). Для перегруженных имён отдаёт все определения; уточнить `file`/`line`.
- **`codegraph_callers` / `codegraph_callees`** — кто вызывает X / что вызывает X.
- **`codegraph_impact`** — что затронет изменение символа (перед рефактором), `depth` по умолчанию 2.
- **`codegraph_files`** — дерево проиндексированных файлов (быстрее Glob для раскладки).
- **`codegraph_status`** — здоровье индекса (files/nodes/edges). Пропускать, кроме отладки.

Все — с `projectPath` (см. выше).

## CLI — индексация и обслуживание

```bash
codegraph status  platform/mobile-app/gj-app     # статистика индекса
codegraph sync    platform/mobile-app/gj-app     # инкрементально: только изменения с прошлого индекса (быстро) — предпочтительно после правок
codegraph index   platform/mobile-app/gj-app     # ПОЛНАЯ переиндексация (перестроить всё)
codegraph unlock  platform/mobile-app/gj-app     # снять залипший lock, блокирующий индексацию
codegraph init    <path>                         # первичная инициализация + сборка индекса для НОВОГО проекта
codegraph uninit  <path>                         # удалить .codegraph/
```

- Крупный проект (gj-app ~1800 файлов) индексируется не мгновенно → запускать `index` **в фоне** (`run_in_background`), дождаться завершения.
- `node_modules` в индекс не входит (init настраивает ignore) — не пытаться индексировать его отдельно.
- Watcher обычно сам подхватывает правки; ручной `sync`/`index` — если результаты MCP выглядят устаревшими, после крупных изменений или переключения ветки.
- «Переиндексация» (запрос пользователя) = `codegraph index`; для просто «подхватить мои правки» достаточно `codegraph sync` (быстрее).

## Anti-patterns

- Забыть `projectPath` в MCP-вызове → `No project loaded` (в этом workspace обязателен).
- Ожидать, что codegraph знает про ensi/starfish/site/… — проиндексирован только gj-app.
- Grep+Read там, где `codegraph_explore` отвечает одним вызовом.
- Переоткрывать Read'ом файлы, которые `codegraph_explore` уже показал verbatim.
- Индексировать `node_modules` / vendor.
