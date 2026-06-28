# Режим киоска — EVIDENCE-LEDGER (реестр решений/находок/разрывов)

Сквозной реестр: одна строка = одно решение/находка/разрыв. Засеян требованиями (`KR-NN`); **verdict = TBD**
до сверки на стадиях. Заполняется по мере исполнения; приземляет оркестратор после ревью стадии.

**Verdict-легенда:** 🟢 готово/переиспользуем · 🟡 частично/доработать · 🟠 обходной путь · 🔴 нет/новое · `TBD` не проверено.

| K-id | KR | Домен | Гипотеза / вопрос (до проверки) | Verdict | Evidence (file:line / page / jira) | Стадия |
|---|---|---|---|---|---|---|
| K-01-1 | KR-1 | site/инстанс | ASM = НЕ app/флейвор, а **runtime-флаг** `window.asmModeEnabled` + Docker-таргет `front-static-asm` (тот же билд, nginx без SSR, `sed` флага) | 🟢 | `index.html:54`; `is-asm.ts:3-10`; `front.dockerfile:33-46`; `asm.sh:3` | 01 |
| K-01-2 | KR-1 | site/инстанс | Домен/окружение инстанса = `asmBaseApiUrl`/`baseAsmUrl` + DI-флаг; ENV→флаг через build-version | 🟢 | `app.config.ts:126-139`; `environment.prod.ts:35,38`; `generate-build-version.js:9` | 01 |
| K-01-3 | KR-1,12 | site/DevOps | Решение: site-kiosk как копия `front-static-asm` (без SSR, дёшево) vs отдельный app `site-kiosk` (SSR/локализация) | TBD | (решается на Stage 01) | 01 |
| K-02-1 | KR-2 | site/роутинг | Каталога «root/all» нет — листинг всегда `catalog/:id`; home через кастомный `matcher`. Старт в каталоге = правка корневого маршрута; нужна категория-старт | 🟡 | `routes.ts:13-40,69-82`; `external.ts:11` (`/catalog/girls`) | 02 |
| K-02-2 | KR-3 | site/layout | Build configurations и планшетный layout есть; точечные kiosk-правки поверх | TBD | `project.json:36-92` | 02 |
| K-03-1 | KR-4 | site/каталог | Фильтр магазина есть: `shopId`, в API `filters.shopId: string[]` | 🟢 | `filter-code.enum.ts:19`; `catalog.service.ts:169`; `search-products-params.interface.ts:32` | 03 |
| K-03-2 | KR-4 | site/привязка | Привязка через URL-матрицу `:shopId:NNN`; ⚠️ очищается при смене региона; cookie/конфиг-механизма нет | 🟡 | `listing-parent.component.ts:478,476-489` | 03 |
| K-04-1 | KR-5 | site/auth | Точка «заказ создан» = thank-you `checkout/orderConfirmation/:id` — крючок для авто-разлогина | 🟢 | `routes.ts:83-94`; `thank-you-page.component.ts` | 04 |
| K-04-2 | KR-6 | site/сессия | Idle/автологаута **нет** — реализуем с нуля поверх `clearStore()/logoutWithAuth()` | 🔴 | `auth-helper.service.ts:100-119` | 04 |
| K-04-3 | KR-10 | site/безопасность | Токен в `localStorage['token']`; `clearStore()` чистит токен+промокоды+reload — проверить полноту (корзина/профиль/форма) | 🟡 | `auth-token.service.ts:10-22`; `auth-helper.service.ts:100-119` | 04 |
| K-04-4 | KR-(вопрос) | site/auth | Как покупатель логинится на общем экране (телефон+СМС?) — база для KR-5/6 | TBD | (вопрос на согласование) | 04 |
| K-05-1 | KR-7 | DevOps/железо | Ubuntu chromium `--kiosk`: автозапуск, URL, защита от выхода — конфиг провижининга | TBD | — | 05 |
| K-05-2 | KR-9 | устройство | Альтернатива Android + спец-приложение — оценка трудозатрат/сроков отдельно | TBD | — | 05 |
| K-06-1 | KR-8 | бэкенд/гость | Гостевой чекаут: поддерживает ли customer-auth/customers/checkout заказ без аккаунта | TBD | — | 06 |
| K-06-2 | KR-8 | Integration/OMS | Проброс гостевого заказа (ФИО+тел+адрес) через ИС в OMS; идемпотентность/идентификация клиента | TBD | — | 06 |
| K-07-1 | все | синтез | Критический путь MVP (согласование→реализация→UAT→релиз), а не сумма фич | TBD | — | 07 |
| K-07-2 | KR-11 | аналитика | Маркировка трафика киоска (источник=kiosk+магазин) для отчётности | TBD | — | 07 |

> Добавлять новые строки по мере находок (K-NN-x). «Упущенные нюансы» (тихо ломающие сценарий общего девайса) — тоже сюда.
