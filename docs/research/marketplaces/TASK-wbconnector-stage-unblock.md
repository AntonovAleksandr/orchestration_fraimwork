# ТЗ: разблокировать стенд `wbconnector` и перейти к плану PIM

**Дата:** 2026-08-25
**Кому:** отдельная сессия/исполнитель
**Статус кода:** всё нужное уже в `origin/master` репозитория
`greensight/gj/go/marketplaces/wbconnector`, последний коммит `51566f6`.
Писать код по этому ТЗ не нужно — только правка values и деплой.

## 1. Что сломано

`stage:deploy` пайплайна [99576](https://gitlab.gloria.aaanet.ru/greensight/gj/go/marketplaces/wbconnector/-/pipelines/99576)
упал:

```
Error: UPGRADE FAILED: release wbconnector-master failed, and has been rolled back
due to atomic being set: client rate limiter Wait returned an error: context deadline exceeded
```

Это не сетевой сбой и не проблема кластера. Причина: коммит `89f3322` перевёл
печать стикера на профиль «WB PNG → GoDEX EZPL» и добавил в
`Config.ValidateService()` жёсткую проверку — сервис отказывается стартовать при
любом значении, кроме `png/58/40`. На стенде в values стоит `zplv`, поэтому
новый под падает на bootstrap, никогда не становится ready,
`helm --wait --timeout=300s --atomic` выжидает 300 секунд и откатывает релиз.

Воспроизведено локально на значениях стенда:

```
WB_STICKER_FORMAT=zplv → {"level":"fatal","error":"invalid config: config:
WB_STICKER_FORMAT/WIDTH/HEIGHT must be png/58/40 for the confirmed GoDEX
EZ6350i 300 dpi renderer (got zplv/58/40)","message":"bootstrap failed"}

WB_STICKER_FORMAT=png  → wbconnector listening on :8080
```

Побочный эффект откатa: кластер остался в смешанном состоянии — CronJob
`wbconnector-cron-wbgoods` уже на образе `master-51566f69`, а Deployment
`wbconnector` и `wbconnector-bkg-wbstatus` откатились на `master-3c796e2a`.
После починки это выровняется, но проверить нужно оба типа объектов.

## 2. Новых переменных не нужно ни одной

Проверено `git diff 64426dc..HEAD` по `internal/platform/config/config.go`: ни
одного нового `getEnv` коммиты не добавили. Меняется только **значение** уже
существующей переменной.

Переменные `PIM_BASE_URL` / `PIM_TIMEOUT_MS` понадобятся позже, в Task 6
основного плана, — в этой задаче их заводить не нужно.

## 3. Что сделать

Файл: `platform/ensi/devops/ms-helm-values/stage/go/wbconnector/wbconnector.yaml`,
строки **113–118**:

```yaml
    WB_STICKER_FORMAT:
      value: "zplv"
    WB_STICKER_WIDTH:
      value: "58"
    WB_STICKER_HEIGHT:
      value: "40"
```

### Вариант A — рекомендуемый: убрать все три переменные

Заменить блок на комментарий:

```yaml
    # Профиль этикетки не настраивается: сервис принимает только PNG 58×40 от WB
    # и сам переводит его в нативный GoDEX EZPL 300 dpi (подтверждено физической
    # печатью 2026-08-24, MP-WB-FBS-099). Дефолты в коде — те же png/58/40.
```

Почему так лучше: код принимает ровно одно допустимое значение, поэтому три
переменные в values — мёртвая конфигурация, которая один раз уже уронила
выкладку. `getEnv("WB_STICKER_FORMAT", "")` при отсутствии переменной даёт
пустую строку, `LabelSpec.Normalized()` подставляет `png/58/40`, и
`ValidateService()` проходит.

**Проверено локально:** запуск вообще без этих трёх переменных даёт
`wbconnector listening on :8080`.

### Вариант B — минимальный, если правку хотят видеть явной

Оставить три переменные, поменять только формат:

```yaml
    WB_STICKER_FORMAT:
      value: "png"
```

Оба варианта рабочие. A предпочтительнее, B безопаснее с точки зрения «видно в
values, что печатается».

## 4. Как проверить до деплоя

```bash
cd $WORKSPACE/platform-new/wbconnector
env -i PATH="$PATH" HOME="$HOME" APP_ENV=stage \
  WBCONNECTOR_DB_DSN='postgres://wb:wb@localhost:55432/wbconnector?sslmode=disable' \
  WB_STATION_TOKEN=dummy WB_PRINTER_ALLOWLIST=10.0.0.1 \
  KAFKA_SECURITY_PROTOCOL=PLAINTEXT KAFKA_SASL_MECHANISMS=PLAIN \
  timeout 15 go run ./cmd/wbconnector 2>&1 | head -3
```

Ожидание: строка `wbconnector listening on :8080`, никакого `bootstrap failed`.
Для варианта B добавить `WB_STICKER_FORMAT=png WB_STICKER_WIDTH=58 WB_STICKER_HEIGHT=40`.

Локальная PostgreSQL при необходимости:

```bash
docker run -d --rm --name wbc-pg -e POSTGRES_PASSWORD=wb -e POSTGRES_USER=wb \
  -e POSTGRES_DB=wbconnector -p 55432:5432 postgres:16-alpine
```

## 5. Деплой и приёмка

1. Закоммитить правку в `ms-helm-values` (это отдельный git-репозиторий).
2. Перезапустить job `stage:deploy` пайплайна `99576` (или собрать новый на
   текущем master). `test:build` уже успешен, пересобирать образ не нужно.
3. Приёмка:
   - job `stage:deploy` — success;
   - Deployment `wbconnector` и `wbconnector-bkg-wbstatus` в namespace `stage` —
     на том же образе, что CronJob `wbconnector-cron-wbgoods`
     (`master-51566f69` или новее), `ready 1/1`;
   - в логах пода `wbconnector` (контейнер `golang`) есть
     `wbconnector listening on :8080` и нет `bootstrap failed`;
   - `GET https://wbconnector-stage.gloria-jeans.ru/testui` открывается и в
     списке появляется столбец «Источник», а сборочные задания видны, даже если
     их создавал не стенд (это изменение из `51566f6`);
   - миграции применились, включая `20260824133000_sticker_png_downgrade_fence`
     и `20260825…` из основного плана, если он уже начат.

Если `stage:deploy` упадёт снова — смотреть не helm, а логи нового пода: помимо
формата стикера `ValidateService()` требует `WB_STATION_TOKEN` и
`WB_PRINTER_ALLOWLIST` вне `APP_ENV=local`; они в values есть, но проверить
стоит.

## 6. Чего не делать

- Не заводить новых переменных окружения: в этой задаче они не нужны.
- Не менять `WB_STICKER_WIDTH`/`HEIGHT` на другие значения — код принимает
  только 58×40.
- Не трогать чужие незакоммиченные изменения в `ms-helm-values`, если они там
  окажутся: коммитить только `stage/go/wbconnector/wbconnector.yaml`.
- Не откатывать миграцию `20260824133000_sticker_png_downgrade_fence`: она
  запрещает старому поду вернуть кеш стикеров с PNG на ZPL при rolling deploy.
  Побочное следствие — cut-over на PNG односторонний: откат бинаря печать не
  восстановит, потому что старый код пишет в принтер сырой ZPL, а на станции
  стоит GoDEX. Восстановление — только вперёд.

## 7. Дальше — по основному плану

План: `docs/superpowers/plans/2026-08-25-wbconnector-pim-identifiers.md`.

Он самодостаточен (7 задач с кодом, тестами и командами), но два момента из него
легко пропустить:

- **Task 0 плана — это ровно данная задача.** Выполнив её, начинать с Task 1.
- **Task 5 и Task 6 выкатываются на стенд одним релизом.** В Task 5 появляется
  заглушка-резолвер, которая отвечает «SKU неизвестен», и с ней экспорт в OTS
  встаёт для **всех** заказов. Промежуточный деплой только Task 5 остановит
  поток заказов на склад.

## 8. Контекст, который дорого добывать заново

- **Prod-values для `wbconnector` не существует вообще** — в `ms-helm-values`
  есть только `stage/go/wbconnector/`. Job `prod:deploy` в пайплайне есть, а
  файла нет. Перед прод-релизом это отдельная работа: прод-токен WB, прод-топик
  Kafka `prod.all.ecom.fct.order-status-wb.0` и ACL консьюмера, OTS, ISMP,
  station token, allowlist принтеров.
- **Пайплайн master гейтится вручную.** `test:build` → `test:deploy` /
  `stage:deploy` / `prod:deploy` создаются в состоянии manual. Именно поэтому
  стенд с 18 августа жил на `3c796e2a`: пайплайн на `e89c7e5` от 20 августа
  никто не запускал, его `updated_at` отличается от `created_at` на полсекунды.
- **Стенд смотрит в песочницу WB** (`marketplace-api-sandbox`,
  `content-api-sandbox`), поэтому карта `goods` там содержит единицы карточек, а
  не прод-каталог. Первый прод-запуск `wbgoods` будет полным проходом по 82 228
  карточкам.
- **Cron `wbgoods` запускается без аргументов**, то есть всегда инкрементально
  по курсору `updatedAt`. Периодического полного прохода нет, и удалённые
  карточки в карте не вычищаются. Отдельная задача, вне плана.
- **Пересечение баркодов PIM × WB измерено 2026-08-25** по полному каталогу:
  покрытие настоящих GS1-баркодов 99,997 %, а весь промах 1,08 % — это баркоды
  с первой цифрой «2» (внутреннее обращение), из них 2 431 лежит в 2 035 живых
  карточках, обычно один внутренний размер из шести. Подробности и следствия —
  в плане, раздел «Пересечение баркодов PIM × WB».

## 9. Источники

- `internal/platform/config/config.go:454-457` — проверка, из-за которой падает старт.
- `internal/core/pack.go:64-85` — `DefaultLabel()` и `Normalized()`, дающие дефолт `png/58/40`.
- `platform/ensi/devops/ms-helm-values/stage/go/wbconnector/wbconnector.yaml:113-118` — место правки.
- Лог упавшего job: `gitlab_get_job_log` для job `253733` проекта `greensight/gj/go/marketplaces/wbconnector`.
- `docs/superpowers/plans/2026-08-25-wbconnector-pim-identifiers.md` — основной план.
- `docs/research/marketplaces/EVIDENCE-LEDGER.md`, `MP-WB-FBS-099` — подтверждённый профиль печати.
