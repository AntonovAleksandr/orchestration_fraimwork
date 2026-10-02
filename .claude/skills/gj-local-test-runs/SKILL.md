---
name: gj-local-test-runs
description: Use when running PHP tests locally for ENSI services in this workspace (baskets, customers-api-web, pim, catalog-cache…) — setting up the DB and .env, choosing the PHP binary, narrowing by path or group, running php-cs-fixer and phpstan, or debugging why a run does not start. Covers the concrete traps found here: Pest failing on paths with a leading dot, symlinked vendor breaking class resolution, 500 instead of an assertion in component tests, factory-driven flakiness, shared clones occupied by peer sessions. Triggers on "прогони тесты", "запусти pest", "тесты не стартуют", "Unable to create test case", "500 в компонентном тесте", "как проверить правку локально".
---

# Локальный прогон тестов ENSI-сервисов

Проверено на `platform/ensi/apps/orders/baskets` и `platform/ensi/apps/customers-api-web`.
Остальные PHP-сервисы ENSI устроены так же: Laravel/Lumen + Pest, компонентные тесты через HTTP.

## Бинарь PHP

Проекты требуют `php ^8.1`, системный — 8.5, на нём часть инструментов падает. Всегда явно:

```bash
/opt/homebrew/opt/php@8.2/bin/php -d memory_limit=2G artisan test <путь>
```

`memory_limit` обязателен: с дефолтным набор не доходит до конца.

## Зависимости

```bash
COMPOSER_MEMORY_LIMIT=-1 /opt/homebrew/opt/php@8.2/bin/php /opt/homebrew/bin/composer install \
  --ignore-platform-reqs --no-interaction --prefer-dist
```

- `--ignore-platform-reqs` обязателен: в `require` есть `ext-rdkafka`, локально его нет, тестам он не нужен.
- Пакеты `ensi/*` тянутся из корпоративного GitLab — нужен живой VPN и `~/.composer/auth.json`.
- Часть пакетов ставится из source, поэтому `vendor` распухает: в `customers-api-web` это ~18 ГБ.
  Учитывать при копировании и при работе в воркtree.

## База и окружение

Компонентные тесты используют `DatabaseTransactions`, а не `RefreshDatabase` — **база должна
существовать и быть промигрирована заранее**.

```bash
cp .env.example .env
/opt/homebrew/opt/php@8.2/bin/php artisan key:generate
psql -h 127.0.0.1 -p 5432 -d postgres -c "CREATE DATABASE orders_baskets_test"
DB_DATABASE=orders_baskets_test /opt/homebrew/opt/php@8.2/bin/php artisan migrate --force
```

- `.env.example` смотрит на контейнерные хосты (`database.gj.127.0.0.1.nip.io`, роль `postgres`).
  Локальный homebrew-postgres роли `postgres` не имеет — правь `DB_HOST=127.0.0.1`,
  `DB_USERNAME=$(whoami)`, пустой пароль.
- Переменные окружения перебивают `.env`, поэтому базу удобно выбирать на ходу:
  `DB_DATABASE=orders_baskets_test2 … artisan test`.
- Витрина (`customers-api-web`) базы не требует — только `.env` с ключом приложения.
- После смены ветки прогонять `artisan migrate` заново: миграции соседних задач.

## Как сужать прогон

- один файл: `artisan test app/Http/ApiV1/Modules/Baskets/Tests/BasketsCustomerSetRegionComponentTest.php`
- один тест: `--filter "часть названия"` (русский текст в названии работает);
- группа: `--group=baskets`, `--group=orders-commit`, `--group=set-items` (см. `uses()->group(...)`).

**Один путь на прогон.** `artisan test A B` молча отрабатывает только первый аргумент — если нужно
несколько путей, вызывать по очереди в `{ …; …; }` и складывать в лог.

**Полный набор долгий.** baskets — 15–18 минут последовательно (в CI 9 секунд, потому что там
ParaTest в 12 процессов). Гонять в фоне (`run_in_background`) и складывать в файл, иначе упрётся
в таймаут Bash. `--parallel` локально требует прав на создание баз `<db>_1..N`.

**Полный набор ходит во внешние сервисы и может встать в сетевом таймауте.** Моки в части тестов
покрывают не все вызовы, поэтому запросы уходят наружу по-настоящему: baskets — в сервер скидок
(`DISCOUNT_API_URL`, таймаут в `.env.example` — **1800 секунд**), customers-api-web — в OMS на
тестах доставки. При нестабильной корпоративной сети прогон встаёт намертво и выглядит как
«просто долго». Подставлять заведомо мёртвый адрес:

```bash
DISCOUNT_API_URL=http://127.0.0.1:9/api/Query DISCOUNT_API_TIMEOUT=2 \
  artisan test --without-tty < /dev/null          # baskets
OMS_URL=http://127.0.0.1:9 artisan test --without-tty --group=orders-commit < /dev/null   # витрина
```

**Как отличить зависание от «долго» — по приросту тестов, а не по CPU.** Загрузка обманывает:
процесс в сетевом ожидании даёт ненулевые доли процента и выглядит живым. Надёжный признак —
счётчик пройденных тестов в логе за минуту:

```bash
sed 's/\x1b\[[0-9;]*m//g' run.log | grep -acE "✓|⨯"   # замерить, подождать 60 с, замерить снова
```

Не сдвинулся — встал. Дальше смотреть последний тест в логе: он назовёт внешний сервис.

**В фоне запускать только с `--without-tty` и `< /dev/null`.** Иначе прогон может **зависнуть
навсегда**: принтер Collision пытается работать интерактивно, дочерний Pest блокируется на чтении
stdin, и процесс висит при 0% CPU без сокетов — выглядит как «просто долго». Так в CI и сделано:
`composer test-ci` = `artisan test --without-tty --parallel`. Как отличить зависание от долгого
прогона:

```bash
ps -o pid,etime,%cpu,stat -p <pid>          # 0.0% CPU + STAT S = висит
lsof -a -p <pid> -i -n -P                   # пусто = сети не ждёт
pgrep -P <pid>                              # дочерний Pest; у него fd 0 — пайп без писателя
```

## Ловушки, на которые уже наступали

**`Unable to create test case for test file at …` (ParseError).** Pest не может собрать класс, если
в пути проекта есть сегмент, начинающийся с точки. Воркtree вида `apps/.wt-capi-274` не заработает —
переносить в путь без точки.

**Symlink на `vendor` ломает прогон.** В воркtree нельзя просто слинковать `vendor` из основного
клона: Pest резолвит корень проекта через vendor и путается. Нужен настоящий каталог — `cp -a`
или отдельный `composer install`.

**Клон занят соседней сессией.** Перед работой смотреть `git branch --show-current` и
`git status --porcelain`: в общем дереве **не переключать ветку** и не сташить чужие изменения —
делать `git worktree add` (см. `.claude/rules/local-code-first.mdc`).

**Shallow-клоны.** `git fetch origin <branch>` может не сдвинуть remote-ref. Явно:
`git fetch origin +refs/heads/<branch>:refs/remotes/origin/<branch>`.

**500 вместо внятной ошибки в компонентном тесте.** Компонентные кейсы валидируют ответ против
OpenAPI (`ValidatesAgainstOpenApiSpec`), и любое `null` в обязательном поле превращается в 500.
Причина обычно — забытый или неполный мок. Чтобы увидеть текст:

```php
$this->withoutExceptionHandling();
```

**Флейки из фабрик.** Фабрики генерируют случайные данные, поэтому неполный мок падает не всегда:
`SearchByCardResponseFactory::new()->success()` без `withBonuses()` отдаёт объект-заглушку и роняет
типизированный аргумент; `ProductCardFactory` без `include(['images'])` даёт `image = null` и 500 по
схеме. Правило: в новом тесте задавать все поля, от которых зависит проверка, явно, и прогонять
кейс 5–8 раз, если он трогает фабрики.

**Чужие флейки.** Перед тем как считать падение своим, прогнать тот же файл на базовой ревизии
(`git stash` или `git checkout <base> -- <path>`): в `ApiMobileV3 SearchComponentTest` падение
плавающее и к правкам корзины отношения не имеет.

**Отключённые тесты.** `grep -n "skip()" <файл>` по задетым ручкам. `skip()` часто означает «ручка
сломана давно» — CI на новый регресс промолчит.

**Сгенерированный клиент под заглушкой.** Тест, где мокается `*Api` клиента, не видит ошибки
разбора ответа: `Class CertificateTypeEnum not found` прошёл все тесты загрузчика. Правка
клиента или подъём его в замке проверяется черновым `vendor` на версиях из замка,
`GuzzleHttp\Handler\MockHandler` с реальным телом ответа и настоящим вызовом метода чтения
(`*Api::search…`). [02.10.2026, webapi-connector !44; `docs/tasks/2026-10-02-opsomn002-268-skills-rules.md` п. 8]

## Статика

```bash
PHP_CS_FIXER_IGNORE_ENV=1 /opt/homebrew/opt/php@8.2/bin/php vendor/bin/php-cs-fixer fix \
  --config .php-cs-fixer.php --dry-run --diff --path-mode=intersection $(git diff --name-only | tr '\n' ' ')

/opt/homebrew/opt/php@8.2/bin/php -d memory_limit=2G vendor/bin/phpstan analyse --no-progress
```

- `PHP_CS_FIXER_IGNORE_ENV=1` нужен, потому что fixer поддерживает php до 8.1.
- **В CI ни fixer, ни phpstan не запускаются** — в пайплайне только `test:php-test-ci`. Зелёный
  пайплайн статику не доказывает, гонять локально.
- `phpstan-baseline.neon` устарел: в baskets 121 ошибка «из коробки». Новые тесты сбивают счётчики
  ignored-паттернов — сравнивать число ошибок с базовой ревизией, а не с нулём.

## Порядок проверки правки

1. точечный прогон затронутых файлов;
2. **guard**: вернуть файл к базовой ревизии `git checkout <base> -- <файл>`, прогнать новый тест —
   он обязан упасть, затем `git checkout HEAD -- <файл>`. Восстановление вешать на `trap`, иначе
   прерывание прогона (Ctrl+C, kill) оставит репозиторий с откаченной правкой:

   ```bash
   trap 'git checkout HEAD -- "$F"' EXIT INT TERM
   git checkout <base> -- "$F" && artisan test --without-tty --filter "…" < /dev/null
   ```

   После любого прерванного прогона — `git status` и проверка, что своя правка на месте.

   **`git checkout <base> -- <файл>` переписывает и индекс.** Восстановление `git checkout -- <файл>`
   после него берёт файл из индекса, то есть возвращает **базовую** версию, а не правку — правка
   молча пропадает, а следующий прогон становится зелёным «на пустом месте». В свежем воркtree, где
   `HEAD` и есть база, `git checkout HEAD -- <файл>` из trap'а даёт ровно тот же эффект. Надёжно:
   `cp <файл> <файл>.bak` до подмены, `git show <base>:<файл> > <файл>` для подмены и `cp` обратно;
   после guard'а — `grep` по своей правке, а не только `git status`.

   **Не `git stash push`**: если правка уже закоммичена, сташить нечего, команда молча ничего не
   делает, тест проходит — и создаётся ложное чувство доказанности. После guard'а обязательно
   `git status`: откат файла смывает другие незакоммиченные правки в нём (так у меня пропала
   уже применённая правка порядка импортов);
3. вернуть правку, прогнать группу или полный набор в фоне;
4. fixer и phpstan на изменённых файлах;
5. для межсервисных правок — тест на границе систем, см. `.claude/skills/gj-task-execution/SKILL.md`.

## Известный нестабильный тест PIM

`app/Domain/Imports/ExcelReaders/Tests/CatalogAttributesReaderIntegrationTest.php` → тест `Import with directory property value` (набор `(3, 2, 2)`) в PIM падает в CI нестабильно: `Failed asserting that a row in the table [product_property_values] matches ... The table is empty`, при этом предшествующие ассерты проходят — `status = DONE`, `chunks_count = 2`, предупреждений ноль.

Наблюдалось 15.09.2026 на ветке `task-opsomn002-366-crumbs-beauty-groups` (pipeline 101000, job 257763). Тот же коммит: локальный прогон файла — 24/24, перезапуск джобы (257764) — 1076 passed. До этого тест дважды проходил на той же ветке (pipelines 100909, 100998).

Гипотеза, не доказанная: `composer test-ci` = `php artisan test --parallel`, и добавление тестов сдвигает раскладку по процессам, обнажая порядковую 
