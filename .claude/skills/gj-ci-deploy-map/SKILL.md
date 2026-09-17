---
name: gj-ci-deploy-map
description: Use when a GitLab job fails, a deploy does not reach a stand, you need to know whether a fix actually got to prod, or you are about to run or retry a deploy job in this workspace. Covers the known CI traps measured here — the Teams-notification proxy that kills a deploy before helm runs, images built only on a web trigger, stage feed cronjobs disabled by default, and how to prove something is really in prod. Branch layout lives in docs/deploy/branch-registry.md. Triggers on "джоба упала", "деплой не прошёл", "почему не задеплоилось", "доехало ли до прода", "перезапусти джобу", "проверь пайплайн", "фид не собрался", "пустой стенд".
---

# CI и деплой: карта ловушек

Собрано по разборам сентября 2026. Каждая запись — уже потерянное время, а не теория.
Раскладка веток — `docs/deploy/branch-registry.md`, сверка — `scripts/gj/branch-registry.sh`.

## Сначала: на каком шаге упало

Прежде чем чинить, посмотреть лог и понять, **докуда дошло**:

| В логе есть | Значит |
|---|---|
| нет `Cloning into 'ms-helm-values'` | упало на уведомлении в Teams — см. ниже, деплоя не было вовсе |
| есть clone, нет `helm secrets ... upgrade` | values скачаны, до helm не дошло |
| есть `helm ... upgrade`, падение на `pre-upgrade hooks` | образа нет — см. «образ собирается только веб-триггером» |

Вывод «деплой упал» без этого различения бесполезен: три разные причины лечатся по-разному.

## Ловушка 1: уведомление в Teams роняет деплой до helm

Общий шаблон (`greensight/gj/devops/gitlab-ci` → `parts/addons/notification.yml`) **первым
шагом** `script` шлёт уведомление в Teams через прокси `exit-narnia.gloj.ru`. Если раннер
не резолвит это имя — джоба падает **до** клонирования чартов и запуска helm. Ничего не
задеплоено, values даже не скачаны.

Три симптома одного и того же шага, все на первом `curl`:

- `curl: (5) Could not resolve proxy` — раннер не резолвит имя;
- `Proxy CONNECT aborted` — прокси рвёт соединение;
- `CONNECT tunnel failed, response 500` — прокси отвечает 500 на CONNECT.

**Лечение — повторить джобу**, но не рассчитывать, что поможет с первого раза. Замер
15.09.2026, `customers-api-web`, пайплайн 101028: `-mob` прошёл сразу, `-asm` со второго
раза, `-web` упал четыре раза подряд, в том числе при одиночных запусках с интервалом
семь минут. Конфиги трёх джоб идентичны — барахлит сам прокси, а не сервис.

Обойти со своей стороны нельзя: у шага нет `|| true`. Если повтор не помогает — это к
DevOps, и ломается **любой** деплой через общий шаблон, а не конкретный сервис.

Повтор через API: `POST /api/v4/projects/<id>/jobs/<job_id>/retry` — возвращает новую джобу.

## Ловушка 2: образ собирается только веб-триггером

`parts/build/backend-build.yml`, job `test:build`: правила дают сборку на `uat` и `master`
(вручную), на одной прибитой release-ветке и при `$CI_PIPELINE_SOURCE == "web"`. Обычный
push в `release-*` джобу **не запускает**, и деплой падает на pre-upgrade hooks без образа.

Это не поломка, а окно: на `release-*` можно править вперёд без ревёрта релиза.

## Ловушка 3: фиды на stage выключены по умолчанию

В `ms-helm-values/stage/catalog/feed/feed.yaml` у всех 31 задания `enabled: false` — фид
на стенде не пересоберётся сам никогда. Файл может быть годами старше прода (`rocket.json`
лежал от 02.04.2025 до 13.09.2026). Причина — нагрузка на стенд; правило команды: включать
по одному-два, проверить, выключить.

Как проверить правку фида на stage (проверено 13.09.2026):

1. MR в `ms-helm-values` (project 444): у нужного задания `enabled: true` и временное
   расписание почаще (`30 * * * *` вместо `0 3 * * *`).
2. Влить MR — деплой берёт values из `master` в момент запуска.
3. Повторить `stage:deploy` в пайплайне сервиса (`catalog/feed` = project 447). Образ
   пересобирать не нужно, если уже собран.
4. Проверить файл на `https://es-public-preprod.gloria-jeans.ru/catalog/feeds/<name>`.
5. **Обязательно** вторым MR вернуть `enabled: false` и расписание, плюс ещё раз
   `stage:deploy` — иначе задание останется в кластере.

Число записей на stage своё (1210 против 856 на проде) — проверять не абсолютное значение,
а соотношение: искомое по числу записей, старое — ноль.

**Не путать сервисы:** `rocket.json` собирает PHP-сервис `catalog/feed` командой
`php artisan feeds:rocket-data`. Go-сервис `gj-feed-generator-products` умеет писать такой
же файл, но его cronjob и на stage, и на проде запускается без флагов — только товарные фиды.

## Доказать, что фикс в проде

Два условия вместе, по отдельности каждое лжёт:

1. коммит — предок головы прод-ветки (`/repository/merge_base`);
2. на этой голове есть **успешная** джоба прод-деплоя (`/jobs?scope=success`, имя содержит `prod`).

Слияние в `master` ≠ прод: в ENSI прод-деплой ручной, и у `customers`, `cms`,
`admin-gui-backend` джоба месяцами висела незапущенной.

Окружения (`/environments`) и теги в этом GitLab не заполнены — на них опираться нельзя.

## Номер сборки мобильного

`versionCode = CI_PIPELINE_IID + OFFSET_PARAM`, где `OFFSET_PARAM = 85000`. В логе джобы —
строки `Version name (IMPORTANT!!!)` и `Version code (IMPORTANT!!!)`. По `package.json`
номер определить нельзя: там лежит маркетинговая версия.

## Смежные скиллы

- `gj-task-orchestration` § Сдача — порядок выкатки и что не трогать.
- `gj-gitlab-git` — токен и запись в GitLab.
- `gj-session-analytics` — если нужно посчитать, как часто падает.
