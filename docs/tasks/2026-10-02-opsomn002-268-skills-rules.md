# OPSOMN002-268 — правила из разбора ревью, перенесённые в скиллы

- Дата: 02.10.2026. Эпик OPSOMN002-268 «Сертификаты оценки соответствия в карточке товара (546-ФЗ)».
- Источники: ревью catalog-cache !111, webapi-connector !30 и !44 (отчёты ревьюеров, разделы
  «что зафиксировать в скиллах»), разбор эксплуатации `docs/research/2026-09-25-opsomn002-268-ops-review.md`.
- Отчёты ревьюеров лежат в `.tasks/` и в git не попадают — нужные факты перенесены сюда.

## Правила и доказательства

| № | Правило | Факт, на котором стоит | Где записано |
|---|---|---|---|
| 1 | Секрет в заголовке исходящего клиента, кроме `Authorization`, сверять с маской w4-logger | маска пакета — `authorization`, `password`, `x-stress-test`; на стенде `W4_HTTP_OUT_HEADERS: 'true'` (`ms-helm-values/stage/common-env.yaml`); `API-Key` реестра ФГИС ушёл бы в Elasticsearch открытым (!30) | `ensi-gitlab-mr-review` |
| 2 | Поле, которое потребитель узнаёт только из событий, у старых записей не появится — нужна первичная загрузка и её место в выкатке | в PIM поле есть у N записей, в кеше — у меньшего числа; `push-model-changes --since` отбирает по `sku_products.updated_at`, импорт документов её не трогает (!111, стадия 2 §4) | `ensi-gitlab-mr-review`, `ensi-kafka` (Payload Design п. 7), `gj-task-execution` §7 |
| 3 | Запись в родителя из события дочерней сущности теряет данные | `Product::find(...)` → `return`; на стенде catalog-cache у 25 283 из 92 848 товаров (27%) запись создана позже первого SKU (!111) | `ensi-gitlab-mr-review`, `ensi-kafka` (Consumer Best Practices п. 6) |
| 4 | Событие, замещающее состав дочерних строк целиком, — с ключом сообщения по id сущности | `HighLevelProducer::sendOne(string $message)` — ключа в сигнатуре нет (`vendor/ensi/laravel-phprdkafka-producer/src/HighLevelProducer.php:64`) (!111) | `ensi-kafka` (Payload Design п. 6), `ensi-gitlab-mr-review` |
| 5 | Подъём замка на коммит клиента `dev-master` — по `git log старый..новый` и `require` клиента | одна строка `reference` в `composer.lock` тянула мажорную линию guzzle/psr7; сборка по замку не ломалась, сломался бы первый `composer update` (!44) | `ensi-gitlab-mr-review`, `gj-task-execution` §8 |
| 6 | Утверждение ТЗ о форме выгрузки — сверять с промежуточной таблицей загрузчика до логики замещения | ФТ §2.3: «по SKU одна строка»; `imported_items` стенда: 225 265 SKU, у 4 292 несколько документов, у 103 — три и больше (!30) | `ensi-gitlab-mr-review`, `gj-task-execution` §1 |
| 7 | Исправление, предложенное ревьюером, проверять у потребителя так же, как находку | предложение разбирать даты в `Europe/Moscow` дало бы `2019-05-29T21:00:00Z` вместо `2019-05-30`: PIM хранит `timestamp` без пояса и отдаёт UTC (!30) | `gj-review-delegation` |
| 8 | Ошибку разбора ответа сгенерированного клиента тесты с заглушкой не ловят | `Class CertificateTypeEnum not found` не поймал ни один тест загрузчика; поймал черновой vendor по замку + `MockHandler` + реальный вызов `searchCertificates` (!44) | `gj-local-test-runs`, ссылка в `gj-task-execution` §5 |
| 9 | Стоп-проверка роста строкового ключа — `strcmp`, а не `<=` | `"2" <= "100"` → true: PHP сравнивает похожие на числа строки как числа, порядок базы задаёт collation (!44) | `gj-task-execution` §5 |
| 10 | Расписание ENSI задают `cronjobs:` в ms-helm-values, а не `Kernel::schedule()` | `schedule:run` нет ни в одном values; CronJob'ы с `concurrencyPolicy: Forbid` (`ms-helm-chart/templates/cron-cj.yaml`); `Kernel` 03:06/04:40 против helm `45-57/5 4` и `20 5` (!30) | `gj-ci-deploy-map` (ловушка 4), `ensi-gitlab-mr-review`, `gj-task-execution` §7 |
| 11 | Смена настроек индекса catalog-cache = новый хеш = пустой индекс; порядок cc-indexer → очередь пуста → cc-main, после отката переиндексация | имя `…_products_<md5(settings)>`, алиаса нет; `elastic:check-index-exists` проверяет наличие; в проде ~97 тыс. заданий (разбор эксплуатации §4) | `gj-ci-deploy-map` (ловушка 5), `ensi-gitlab-mr-review` |
| 12 | Тест `deleted`-наблюдателя с соседней записью через `updateOrCreate` проходит без удаления | `updateOrCreate` вызывает `saved` и без изменений; `ListenSkuProductIntegrationTest.php:214-242` с `atLeast()->once()` (!111) | `ensi-tests` (Observer Tests), `ensi-gitlab-mr-review` |

Правило 12 добавлено сверх сведённого списка координатора: оно было в отчёте !111.
Пятый пункт отчёта !30 (нет грантов `gj_buddy` на `stage_pim.certificates`) — пример к памяти
о новых таблицах, а не правило скилла; в скиллы не вносился.

## Доходит ли до работников

Проверено по `scripts/gj/orchestrate.sh` (`skills_for`) и цепочкам загрузки в самих скиллах.

| Кто | Что загружает | Какие правила видит |
|---|---|---|
| Ревью ENSI (`orchestrate.sh review`) | `gj-review-delegation` → `gj-gitlab-mr-review` → `ensi-gitlab-mr-review` → `ensi-code-style`, `ensi-tests` всегда, `ensi-kafka` при событиях | все 12: сводный раздел «Checks Learned From Past Reviews» в addendum ENSI, правило 7 — в `gj-review-delegation` |
| Работник задачи (`task`, `front`) | `gj-task-orchestration`, `gj-task-execution`, `gj-subagent-delegation` | 2, 5, 6, 9, 10 — прямо в `gj-task-execution`; 8 — ссылкой на `gj-local-test-runs` |
| Подагент деплоя | `gj-ci-deploy-map`, `gj-gitlab-git` | 10, 11 |

Поэтому правила для ревью собраны в `ensi-gitlab-mr-review` — его загружает каждое ревью ENSI,
а `ensi-kafka` и `gj-ci-deploy-map` ревьюер загружает не всегда. Детали остаются в
профильных скиллах, addendum ссылается на них.

## Кандидаты, не внесённые в скиллы

Сверка всех ревью эпика (стадии 1 и 2, ревью 294/295, разбор эксплуатации) дала ещё правила,
которых нет в скиллах. В этой задаче не вносились: координатор ограничил объём сведённым списком.
Самые весомые:

- признак, сведённый с дочерних записей на родителя внутри пакета, затирается следующим пакетом
  (стадия 2 §3, P2) — хранить на дочерней, сводить по всем;
- массовый `delete()`/`update()` через построитель не вызывает наблюдателей модели (ревью 294/295);
- «поля нет» ≠ «пустой перечень»: `?? []` при замещении стирает данные на старом формате (!111);
- реальные данные (ИНН) в тестовых фикстурах — секрет в истории ветки, сквош не спасает
  (разбор эксплуатации §1) → `gj-gitlab-git`;
- cronjob, тратящий лимит внешнего API: `concurrencyPolicy: Forbid`, `backoffLimit` 0–1,
  `activeDeadlineSeconds` (разбор эксплуатации §5) → `gj-ci-deploy-map`;
- `composer.lock` потребителя на клиенте без нового API — 500 в рантайме; перелочка — отдельный
  шаг выкатки (разбор эксплуатации §2);
- отклонённые и ненайденные строки импорта повторяются бессрочно — нужен счётчик и отчёт;
  ошибка одной строки на весь пакет (422) блокирует его каждый прогон;
- `ADD COLUMN` берёт ACCESS EXCLUSIVE и встаёт за длинной транзакцией (разбор эксплуатации §3);
- nullable-сеттер сгенерированного DTO без `openAPINullablesSetToNull` теряет явный `null` (ревью 294/295);
- даты без времени не разбирать в локальной зоне (!30) — частный случай правила 7.
