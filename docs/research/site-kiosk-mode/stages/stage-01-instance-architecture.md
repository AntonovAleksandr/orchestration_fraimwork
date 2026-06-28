# Stage 01 — Архитектура инстанса киоска (ASM-эталон; инстанс vs флаг)

**Дата:** TBD · **Статус:** pending
**Требования:** KR-1, KR-12 (см. `../00-requirements.md`)

## 0. Scope и гипотезы
- Как заведён режим **ASM/аватар** (колл-центр) — отдельное app в `apps/`, отдельный билд-флейвор или флаг/конфиг.
- Где конфигурируется домен/окружение инстанса.
- Решение: завести отдельный **`site-kiosk`** (по образцу ASM) **vs** feature-flag/конфиг-режим на текущем фронте (что быстрее для пилота, KR-12).
- Гипотеза владельца: отдельный инстанс с отдельным доменом и слегка модифицированным фронтом.

## 1. As-is — живая правда (разведка 2026-06-28)
- **ASM-режим = НЕ отдельное Angular-app и НЕ build-флейвор**, а **runtime-флаг** `window.asmModeEnabled` + **отдельный Docker-таргет** на том же артефакте сборки:
  - флаг: `apps/site-ru/src/index.html:54`, чтение `libs/core/src/lib/utils/is-asm.ts:3-10` (⚠️ флаг только в site-ru → ASM = RU-only);
  - деплой: `configs/build/configuration/front.dockerfile:33-46` (таргет `front-static-asm`, nginx без SSR), `asm.sh:3` (`sed` флага `false→true` в задеплоенном `index.html`);
  - разделение домена/API: `app.config.ts:126-139` (`ASM_MODE_ENABLED`, `BASE_API_URL`), `environment.prod.ts:35,38` (`baseAsmUrl`, `asmBaseApiUrl`), ENV→флаг `tools/generators/generate-build-version.js:9`;
  - guard/маршрут/вход по токену: `routes.ts:195-204` (`loginAsm`), `asm-mode.guard.ts:18-22`, `asm-page.component.ts:18-34`.
- **Apps:** `site-ru/en/kz` (+e2e); build configurations `apps/site-ru/project.json:36-92`; новый app = `nx g @nx/angular:application site-kiosk` (`nx.json:17-23`).
- Полные якоря — `../00-source-inventory.md` §1.

## 2. Целевое — для режима киоска
- KR-1: инстанс киоска (отдельный домен, минимально модифицированный фронт).
- KR-12: на 1-й фазе — минимум модификаций.

## 3. Решение + матрица разрывов
Два кандидата (выбрать на этой стадии):
- **Вариант A (дёшево, по образцу ASM):** новый runtime-флаг `window.kioskModeEnabled` + копия Docker-таргета `front-static-kiosk` + `kiosk.sh` + nginx-конфиг + свой домен/API. Тот же артефакт сборки, **без нового app, без SSR**. Минимум модификаций (KR-12).
- **Вариант B (полноценно):** отдельный app `site-kiosk` по образцу `site-ru` (свой `project.json`, environments, SSR/локализация). Дороже, нужен если киоску важен SSR.

| Под-область | KR | Verdict | Подход / разрыв | Evidence |
|---|---|---|---|---|
| Эталон ASM | KR-1 | 🟢 | runtime-флаг + Docker-таргет — готовый шаблон | `front.dockerfile:33-46`; `asm.sh:3` |
| site-kiosk vs flag | KR-1,12 | TBD | склоняемся к **Варианту A** для пилота | — |

## 4. Оценка (две оси)
| Под-фича | Ось A | Ось B | Срок | Что ускорит |
|---|---|---|---|---|
| Завести инстанс/флаг | TBD (S–L) | решение инстанс/флаг | TBD | раннее решение по архитектуре |

## 5. Открытые вопросы
- Отдельный инстанс или флаг для скорости пилота?

## 6. Acceptance-gates
- [ ] Принято решение инстанс vs флаг с обоснованием по сроку.

## 7. Записи в EVIDENCE-LEDGER.md
- K-01-1, K-01-2, K-01-3.

## 8. Resume pointer
- Начать с разбора ASM-режима по итогам разведки `site-researcher`.
