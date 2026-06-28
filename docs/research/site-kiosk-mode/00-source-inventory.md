# Режим киоска — инвентаризация источников

Источники для проекта. На старте утверждённого требования нет — основной источник это **бриф владельца**
(`00-requirements.md`). Код-якоря заполняются по мере разведки (фоновый `site-researcher`, Stage 01–04).

## 0. Caveat по коду (2026-06-28)

`platform/site/gj-ng-front` не зафастфорвардился при `sync-platform-repos.sh site`: ветка **`OPSOMN001-386`**,
ahead 3 / behind 1, **рабочее дерево чистое**, последний коммит **2026-06-23**. Для архитектурных фактов
(ASM-режим, фильтр магазина, auth) это приемлемо. Принудительных git-операций не делаем; на стадиях, где нужна
строгая свежесть, переключиться/обновить ветку отдельно и отметить.

## 1. Код (локально) — якоря из разведки `site-researcher` (2026-06-28)

Все пути относительно `platform/site/gj-ng-front/`.

| Домен | Ключевые якоря `file:line` | Заметка |
|---|---|---|
| **ASM-эталон: runtime-флаг** | `apps/site-ru/src/index.html:54` (`window.asmModeEnabled=false`); `libs/core/src/lib/utils/is-asm.ts:3-10` (`isAsm()`) | ⚠️ флаг только в **site-ru** (ASM = RU-only). На SSR всегда false |
| **ASM-эталон: деплой инстанса** | `configs/build/configuration/front.dockerfile:33-46` (таргет `front-static-asm`); `asm.sh:3` (`sed` флага в задеплоенном `index.html`); сравнение — обычный `front-static` `:12-31` (SSR) | тот же артефакт сборки + nginx `nginx-default-asm.conf` (без SSR-renderer) |
| **ASM-эталон: разделение хоста/окружения** | `apps/site-ru/src/app/app.config.ts:126-139` (`ASM_MODE_ENABLED`, `BASE_API_URL`); `environment.prod.ts:35,38` (`baseAsmUrl`, `asmBaseApiUrl`); `libs/core/src/lib/providers/app-base-url.provider.ts:18,23`; DI-токен `libs/core/src/lib/tokens/environment.ts:13`; ENV→флаг `tools/generators/generate-build-version.js:9` | шаблон «свой домен/API для инстанса» |
| **ASM-эталон: guard / маршрут / передача сессии** | `libs/routing/src/lib/routes.ts:195-204` (`loginAsm`); `libs/shared/src/lib/guards/asm-mode.guard.ts:18-22`; `libs/modules/asm/src/lib/asm-page/asm-page.component.ts:18-34` (токены из query→localStorage); `libs/data-access/.../link-interceptor.service.ts:20` (active при isAsm) | вход «в аватар» по ссылке с токенами |
| **Фильтр магазина (`shopId`)** | enum `libs/data-access/src/lib/constants/filters/filter-code.enum.ts:19` (`SHOP_ID='shopId'`); маппинг `.../catalog/listing/listing-filters.const.ts:66-68`; UI `libs/shared/.../filters/store-filter/store-filter.component.ts` (лимит 3 `:16`) | в API уходит `filters.shopId: string[]` |
| **Фильтр магазина: API** | `libs/data-access/src/lib/services/catalog/catalog.service.ts:169` (`shopId` в `filters`); модель `.../search-products-params.interface.ts:32`; резолв названий `store.service.ts:46-63`, список `ENDPOINTS.STORES` `:30-34` | — |
| **Привязка магазина через URL** | `shopId` кодируется в путь матрицей `:shopId:NNN` — `libs/shared/src/lib/components/listing-parent/listing-parent.component.ts:478`; ⚠️ при смене региона очищается `:476-489` | готового механизма «store через cookie/конфиг» нет |
| **Auth: токен/refresh** | `libs/data-access/src/lib/services/auth/helpers/auth-token.service.ts:10-22` (`localStorage['token']`, JSON `{accessToken,refreshToken,expiresIn}`); refresh `auth-helper.service.ts:30-98` (`:72`) | — |
| **Auth: logout** | `auth.service.ts:120-126` (GET `LOGOUT`); `auth-helper.service.ts:100-119` (`logout()`, `clearStore()` + reload, `logoutWithAuth(fragment)`) | крючок для KR-5/6/10 |
| **Idle/автологаут** | **отсутствует** (нет dedicated сервиса) | KR-6 реализуем с нуля поверх `clearStore()/logoutWithAuth()` |
| **Точка «заказ создан»** | маршрут `checkout/orderConfirmation/:id` → `routes.ts:83-94` (`THANK_YOU`, `canActivate:[AuthGuard]`); `libs/modules/checkout/src/lib/thank-you-page/thank-you-page.component.ts` | лучшее место для авто-разлогина (KR-5) |
| **Главная vs каталог root** | home — кастомный `matcher` `routes.ts:13-23,25-40` (`@gj/home-page`); каталог = `catalog/:id` `:69-82` (нет «root/all»); дефолт `apps/site-ru/src/environments/external.ts:11` (`/catalog/girls`) | старт в каталоге = правка корневого маршрута |
| **Apps / флейворы** | apps: `site-ru/en/kz` (+e2e); configurations `apps/site-ru/project.json:36-92` (prod default, demo/testing/staging/development), SSR `:149-218`; скрипты `package.json:51-70` (ru/kz; en — без скриптов); Nx-генератор `nx.json:17-23`, `defaultProject:site :32` | новый app = `nx g @nx/angular:application site-kiosk` |
| **Бэкенд auth покупателя** | `platform/ensi/apps/customers/customer-auth`, `platform/ensi/apps/customers-api-web` | логин/сессия, гостевой режим (KR-8) — Stage 06 |
| **Чекаут backend (гость)** | `platform/integration/integration/www`, OMS `/order/create` | гостевой заказ через ИС→OMS (KR-8) — Stage 06 |

## 2. Confluence / Jira

На старте — **нет утверждённого требования**; бриф владельца — единственный источник. По мере согласования:
- Завести Confluence-страницу требований киоска (зафиксировать `page_id` здесь).
- Завести Jira-эпик/стори (зафиксировать key здесь).
- Проверить, нет ли уже наработок: CQL `text ~ "киоск" OR text ~ "kiosk"`, JQL `text ~ "киоск" OR text ~ "kiosk"`.

| Источник | ID | Роль |
|---|---|---|
| Confluence требования киоска | TBD | завести при согласовании |
| Jira эпик/стори киоска | TBD | завести при согласовании |
| Реестр задач (Confluence) | `165404013` | логировать задачу проекта при необходимости |

## 3. Связанные наши доки / скиллы

| Файл / скилл | Релевантность |
|---|---|
| `docs/research/2026-05-20-checkout-order-creation.md` | чекаут / создание заказа (KR-5, KR-8) |
| скилл `gj-checkout-order-flow` | поток чекаута/заказа |
| скилл `site-stack-anatomy`, `site-nx-commands`, `site-angular-conventions` | устройство фронта, Nx, конвенции |
| скилл `gj-evidence-ledger-research` | методика этого research |
| `docs/research/r20-order-splits/` | образец структуры проекта |

## 4. Разведка as-is (завершена 2026-06-28)

`site-researcher` отработал; якоря перенесены в §1, ledger обновлён (K-01..K-04). Ключевые выводы:

- **ASM = не отдельный app и не флейвор**, а **runtime-флаг** `window.asmModeEnabled` + **отдельный Docker-таргет** `front-static-asm` (тот же артефакт сборки, nginx без SSR, `asm.sh` делает `sed` флага, отдельный домен/API-хост). → **Самый дешёвый шаблон для `site-kiosk`**, если киоску не нужен SSR. Если нужен полноценный SSR/локализация — заводить отдельный app `site-kiosk` по образцу `site-ru`. Решение — Stage 01.
- **Фильтр магазина уже есть** (`shopId`, в URL как `:shopId:NNN`) → привязка киоска к магазину дёшева, но ⚠️ `shopId` очищается при смене региона.
- **Точка «заказ создан»** = thank-you `checkout/orderConfirmation/:id` → готовый крючок для авто-разлогина (KR-5).
- **Idle/автологаута нет** → KR-6 пишем с нуля поверх `AuthHelperService.clearStore()/logoutWithAuth()`; токен в `localStorage['token']`.
- **Каталога «root/all» нет** — листинг всегда `catalog/:id`; нужно выбрать категорию-старт (в коде дефолт `/catalog/girls`).

## 5. Железо / kiosk-режим (Stage 05)

- Пилотное железо: Ubuntu (есть). Режим: полноэкранный браузер (chromium `--kiosk`), автозапуск на URL киоска.
- Провижининг/MDM/защита от выхода — при необходимости через `devops-architect`.
- Альтернатива (P2): Android-устройство + спец-приложение (KR-9) — оценивать отдельно.
